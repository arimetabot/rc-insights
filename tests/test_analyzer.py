"""Tests for SubscriptionAnalyzer — heuristic analysis and report generation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from rc_insights.analyzer import SubscriptionAnalyzer
from rc_insights.client import AuthenticationError, ChartsClientError
from rc_insights.models import ChartData, OverviewMetrics

# ---------------------------------------------------------------------------
# Module-level helpers (kept for internal use; shared versions live in conftest)
# ---------------------------------------------------------------------------


def _make_analyzer() -> SubscriptionAnalyzer:
    """Return a throw-away analyzer pointed at a fake test project."""
    return SubscriptionAnalyzer(rc_api_key="sk_test", rc_project_id="proj_test")


def _make_overview(
    mrr: float = 5000.0,
    churn_rate: float = 3.0,
    active_subscribers: float = 500.0,
) -> OverviewMetrics:
    """Build a minimal OverviewMetrics for test assertions."""
    from rc_insights.models import OverviewMetric

    return OverviewMetrics(
        metrics=[
            OverviewMetric(
                id="mrr", name="MRR", value=mrr, unit="$",
                period="last_28_days", description="MRR",
            ),
            OverviewMetric(
                id="churn", name="Churn", value=churn_rate, unit="%",
                period="last_28_days", description="Churn Rate",
            ),
            OverviewMetric(
                id="active_subscribers", name="Active Subscribers",
                value=active_subscribers, unit="number",
                period="last_28_days", description="Active Subscribers",
            ),
        ]
    )


def _make_chart(
    name: str,
    start_val: float = 100.0,
    end_val: float = 110.0,
    n_points: int = 30,
) -> ChartData:
    """Create a chart with a linear trend from *start_val* to *end_val*."""
    values = []
    for i in range(n_points):
        ts = 1704067200000 + (i * 86_400_000)  # 1-day intervals
        val = start_val + (end_val - start_val) * i / max(n_points - 1, 1)
        values.append([ts, val])
    return ChartData(
        display_name=name,
        description=f"{name} chart",
        values=values,
    )


# ---------------------------------------------------------------------------
# Heuristic analysis tests
# ---------------------------------------------------------------------------


class TestHeuristicAnalysis:
    """Tests for _analyze_with_heuristics."""

    def test_returns_score_in_range(self) -> None:
        """Health score is always between 0 and 100."""
        analyzer = _make_analyzer()
        score, _, _ = analyzer._analyze_with_heuristics(_make_overview(), {})
        assert 0.0 <= score <= 100.0

    def test_returns_non_empty_summary(self) -> None:
        """Summary string is always populated."""
        analyzer = _make_analyzer()
        _, summary, _ = analyzer._analyze_with_heuristics(_make_overview(), {})
        assert len(summary) > 0

    def test_returns_at_least_one_insight(self) -> None:
        """At least one insight is always generated."""
        analyzer = _make_analyzer()
        _, _, insights = analyzer._analyze_with_heuristics(_make_overview(), {})
        assert len(insights) > 0

    def test_low_churn_generates_positive_insight(self) -> None:
        """Churn rate < 5% → positive severity insight."""
        analyzer = _make_analyzer()
        _, _, insights = analyzer._analyze_with_heuristics(_make_overview(churn_rate=2.0), {})
        churn = [i for i in insights if i.category == "churn"]
        assert len(churn) > 0
        assert churn[0].severity == "positive"

    def test_moderate_churn_generates_warning(self) -> None:
        """Churn rate 5-10% → warning severity insight."""
        analyzer = _make_analyzer()
        _, _, insights = analyzer._analyze_with_heuristics(_make_overview(churn_rate=7.0), {})
        churn = [i for i in insights if i.category == "churn"]
        assert len(churn) > 0
        assert churn[0].severity == "warning"

    def test_high_churn_generates_critical_and_penalizes_score(self) -> None:
        """Churn rate > 10% → critical insight and reduced health score."""
        analyzer = _make_analyzer()
        score, _, insights = analyzer._analyze_with_heuristics(_make_overview(churn_rate=15.0), {})
        churn = [i for i in insights if i.category == "churn"]
        assert len(churn) > 0
        assert churn[0].severity == "critical"
        assert score < 65  # Starting at 60 then -20 = 40, capped to ≥0

    def test_declining_mrr_generates_warning_or_critical_insight(self) -> None:
        """MRR drop >5% week-over-week → warning or critical insight."""
        analyzer = _make_analyzer()
        # 1000→800 is a ~20% decline over 30 points
        charts = {"mrr": _make_chart("MRR", start_val=1000.0, end_val=800.0)}
        _, _, insights = analyzer._analyze_with_heuristics(_make_overview(), charts)
        bad = [i for i in insights if i.severity in ("critical", "warning")
               and i.category == "revenue"]
        assert len(bad) > 0

    def test_growing_mrr_generates_positive_insight(self) -> None:
        """MRR growth >10% → positive insight and higher score."""
        analyzer = _make_analyzer()
        charts = {"mrr": _make_chart("MRR", start_val=1000.0, end_val=1200.0)}
        score, _, insights = analyzer._analyze_with_heuristics(_make_overview(), charts)
        positive = [i for i in insights if i.severity == "positive"]
        assert len(positive) > 0
        assert score >= 50

    def test_slow_customer_acquisition_generates_warning(self) -> None:
        """New customer decline >15% → warning insight."""
        analyzer = _make_analyzer()
        # 100→60 is a ~40% decline — above the 15% threshold
        charts = {"customers_new": _make_chart("New Customers", start_val=100.0, end_val=60.0)}
        _, _, insights = analyzer._analyze_with_heuristics(_make_overview(), charts)
        warnings = [
            i for i in insights
            if i.category == "growth" and i.severity == "warning"
        ]
        assert len(warnings) > 0

    def test_empty_data_produces_info_insight(self) -> None:
        """No overview and no charts → single 'info' category insight."""
        analyzer = _make_analyzer()
        _, _, insights = analyzer._analyze_with_heuristics(None, {})
        assert len(insights) > 0
        # The fallback "Insufficient Data" insight uses category="info"
        categories = {i.category for i in insights}
        assert "info" in categories

    def test_all_insight_categories_are_valid(self) -> None:
        """All generated insights use documented category values."""
        valid_categories = {"revenue", "churn", "growth", "retention", "trials", "refunds", "info"}
        analyzer = _make_analyzer()
        overview = _make_overview(churn_rate=12.0)
        charts = {
            "mrr": _make_chart("MRR", 1000.0, 800.0),
            "churn": _make_chart("Churn", 5.0, 20.0),
        }
        _, _, insights = analyzer._analyze_with_heuristics(overview, charts)
        for insight in insights:
            assert insight.category in valid_categories, (
                f"Unexpected category '{insight.category}' in insight '{insight.title}'"
            )

    def test_all_insight_severities_are_valid(self) -> None:
        """All generated insights use documented severity values."""
        valid_severities = {"critical", "warning", "positive", "info"}
        analyzer = _make_analyzer()
        _, _, insights = analyzer._analyze_with_heuristics(_make_overview(), {})
        for insight in insights:
            assert insight.severity in valid_severities, (
                f"Unexpected severity '{insight.severity}' in insight '{insight.title}'"
            )

    def test_score_clamped_to_zero(self) -> None:
        """Score never goes below 0 even with many penalties."""
        analyzer = _make_analyzer()
        # Very high churn + declining everything
        overview = _make_overview(churn_rate=99.0)
        charts = {
            "mrr": _make_chart("MRR", 1000.0, 100.0),
            "churn": _make_chart("Churn", 10.0, 100.0),
        }
        score, _, _ = analyzer._analyze_with_heuristics(overview, charts)
        assert score >= 0.0

    def test_score_clamped_to_hundred(self) -> None:
        """Score never exceeds 100."""
        analyzer = _make_analyzer()
        overview = _make_overview(churn_rate=0.5)
        charts = {
            "mrr": _make_chart("MRR", 1000.0, 5000.0),
            "revenue": _make_chart("Revenue", 1000.0, 5000.0),
            "actives": _make_chart("Actives", 100.0, 1000.0),
        }
        score, _, _ = analyzer._analyze_with_heuristics(overview, charts)
        assert score <= 100.0


# ---------------------------------------------------------------------------
# generate_report() error propagation tests
# ---------------------------------------------------------------------------


class TestGenerateReportErrors:
    """Tests for error handling in generate_report."""

    def test_auth_error_propagates_from_get_overview(self) -> None:
        """AuthenticationError from get_overview is NOT swallowed — it raises."""
        analyzer = _make_analyzer()

        with patch.object(
            analyzer.client,
            "get_overview",
            side_effect=AuthenticationError("Invalid API key", status_code=401),
        ):
            with patch.object(analyzer.client, "get_all_core_charts", return_value={}):
                with pytest.raises(AuthenticationError):
                    analyzer.generate_report(include_ai=False)

    def test_non_auth_client_error_is_caught_and_overview_is_none(self) -> None:
        """Non-auth ChartsClientError is caught gracefully; report continues with overview=None."""
        analyzer = _make_analyzer()

        with patch.object(
            analyzer.client,
            "get_overview",
            side_effect=ChartsClientError("Service unavailable", status_code=503),
        ):
            with patch.object(analyzer.client, "get_all_core_charts", return_value={}):
                report = analyzer.generate_report(include_ai=False)

        assert report.overview is None
        assert report.project_id == "proj_test"
        assert report.overall_health_score >= 0

    def test_report_generated_without_ai(self) -> None:
        """generate_report(include_ai=False) runs heuristic analysis end-to-end."""
        analyzer = _make_analyzer()
        overview = _make_overview()
        charts = {"mrr": _make_chart("MRR")}

        with patch.object(analyzer.client, "get_overview", return_value=overview):
            with patch.object(analyzer.client, "get_all_core_charts", return_value=charts):
                report = analyzer.generate_report(include_ai=False)

        assert report.project_id == "proj_test"
        assert report.overview is not None
        assert len(report.insights) > 0
        assert 0.0 <= report.overall_health_score <= 100.0
        assert len(report.summary) > 0

    def test_report_date_range_respects_days_param(self) -> None:
        """The days parameter controls period_start correctly."""
        from datetime import date, timedelta

        analyzer = _make_analyzer()

        with patch.object(analyzer.client, "get_overview", return_value=_make_overview()):
            with patch.object(analyzer.client, "get_all_core_charts", return_value={}):
                report = analyzer.generate_report(days=7, include_ai=False)

        expected_start = date.today() - timedelta(days=7)
        assert report.period_start == expected_start

    def test_ai_fallback_to_heuristics_on_openai_error(self) -> None:
        """When OpenAI raises an exception, analysis falls back to heuristics."""
        analyzer = SubscriptionAnalyzer(
            rc_api_key="sk_test",
            rc_project_id="proj_test",
            openai_api_key="sk-fake-key",
        )
        overview = _make_overview()

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_openai_cls.return_value.chat.completions.create.side_effect = (
                Exception("OpenAI API error")
            )
            score, summary, insights = analyzer._analyze_with_ai(overview, {})

        # Should have fallen back to heuristics
        assert 0.0 <= score <= 100.0
        assert len(summary) > 0


# ---------------------------------------------------------------------------
# Fixture-injected tests (use shared conftest fixtures)
# ---------------------------------------------------------------------------


class TestSharedFixtures:
    """Smoke-test the conftest fixtures to ensure they produce valid objects."""

    def test_make_overview_fixture_defaults(self, make_overview) -> None:
        """make_overview() returns OverviewMetrics with expected default metrics."""
        ov = make_overview()
        assert ov.mrr == 5000.0
        assert ov.churn_rate == 3.0
        assert ov.active_subscribers == 500.0

    def test_make_overview_fixture_custom_values(self, make_overview) -> None:
        """make_overview() respects keyword arguments."""
        ov = make_overview(mrr=9999.0, churn_rate=1.5)
        assert ov.mrr == 9999.0
        assert ov.churn_rate == 1.5

    def test_make_chart_fixture_returns_chartdata(self, make_chart) -> None:
        """make_chart() returns a ChartData with the correct number of data points."""
        chart = make_chart("MRR", start_val=100.0, end_val=200.0, n_points=10)
        assert chart.display_name == "MRR"
        points = chart.data_points
        assert len(points) == 10
        # First value should equal start_val
        assert abs(points[0][1] - 100.0) < 0.01
        # Last value should equal end_val
        assert abs(points[-1][1] - 200.0) < 0.01

    def test_make_analyzer_fixture_returns_analyzer(self, make_analyzer) -> None:
        """make_analyzer() returns a SubscriptionAnalyzer wired to test credentials."""
        analyzer = make_analyzer()
        assert analyzer.client is not None
        analyzer.close()

    def test_fixture_analyzer_runs_heuristics(
        self, make_analyzer, make_overview, make_chart
    ) -> None:
        """Fixture-built objects work end-to-end with heuristic analysis."""
        analyzer = make_analyzer()
        overview = make_overview(mrr=8000.0, churn_rate=4.0)
        charts = {"mrr": make_chart("MRR", start_val=7000.0, end_val=8000.0)}
        score, summary, insights = analyzer._analyze_with_heuristics(overview, charts)
        assert 0.0 <= score <= 100.0
        assert len(summary) > 0
        assert len(insights) > 0
        analyzer.close()
