"""Tests for cohort retention analysis (rc_insights.cohort)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from rc_insights.cohort import Cohort, CohortAnalyzer
from rc_insights.models import ChartData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chart(n_points: int, start_val: float = 100.0, end_val: float = 120.0) -> ChartData:
    """Build a synthetic ChartData with a linear ramp."""
    values = []
    for i in range(n_points):
        ts = 1704067200000 + (i * 7 * 86_400_000)  # weekly intervals from 2024-01-01
        val = start_val + (end_val - start_val) * i / max(n_points - 1, 1)
        values.append([ts, val])
    return ChartData(display_name="test", description="test chart", values=values)


def _mock_client(
    new_customers_chart: ChartData | None = None,
    actives_chart: ChartData | None = None,
    raise_new_customers: bool = False,
    raise_actives: bool = False,
) -> MagicMock:
    """Build a mock ChartsClient."""
    client = MagicMock()

    def get_chart(name, **kwargs):
        if name in ("customers_new", "actives_new"):
            if raise_new_customers:
                from rc_insights.client import ChartsClientError
                raise ChartsClientError("not found")
            return new_customers_chart or _make_chart(16, 100, 120)
        if name == "actives":
            if raise_actives:
                from rc_insights.client import ChartsClientError
                raise ChartsClientError("not found")
            return actives_chart or _make_chart(16, 800, 900)
        raise ValueError(f"Unexpected chart: {name}")

    client.get_chart.side_effect = get_chart
    return client


# ---------------------------------------------------------------------------
# Cohort dataclass
# ---------------------------------------------------------------------------


class TestCohortDataclass:
    def test_basic_construction(self):
        c = Cohort(start_date="2025-01-06", size=100, retention={0: 100.0, 1: 85.0})
        assert c.start_date == "2025-01-06"
        assert c.size == 100
        assert c.retention[0] == pytest.approx(100.0)
        assert c.retention[1] == pytest.approx(85.0)

    def test_default_retention_is_empty(self):
        c = Cohort(start_date="2025-01-06", size=50)
        assert c.retention == {}

    def test_size_zero_allowed(self):
        c = Cohort(start_date="2025-01-06", size=0)
        assert c.size == 0


# ---------------------------------------------------------------------------
# CohortAnalyzer._compute_survival_rate
# ---------------------------------------------------------------------------


class TestComputeSurvivalRate:
    def _analyzer(self) -> CohortAnalyzer:
        return CohortAnalyzer(client=MagicMock())

    def _pts(self, values: list[float]) -> list[tuple[datetime | None, float]]:
        ts = datetime(2024, 1, 1)
        return [(ts, v) for v in values]

    def test_returns_default_for_empty_data(self):
        analyzer = self._analyzer()
        rate = analyzer._compute_survival_rate([], [])
        assert rate == pytest.approx(CohortAnalyzer._DEFAULT_SURVIVAL_RATE)

    def test_returns_default_for_single_point(self):
        analyzer = self._analyzer()
        pts = self._pts([100.0])
        rate = analyzer._compute_survival_rate(pts, pts)
        assert rate == pytest.approx(CohortAnalyzer._DEFAULT_SURVIVAL_RATE)

    def test_perfect_retention_stable_actives_no_new(self):
        """If actives stay flat and no new customers, survival ≈ 1.0."""
        analyzer = self._analyzer()
        new_pts = self._pts([0.0, 0.0, 0.0, 0.0])
        act_pts = self._pts([100.0, 100.0, 100.0, 100.0])
        rate = analyzer._compute_survival_rate(new_pts, act_pts)
        assert rate == pytest.approx(1.0)

    def test_high_churn_scenario(self):
        """Actives drop heavily even with new customers → lower survival rate."""
        analyzer = self._analyzer()
        new_pts = self._pts([20.0, 20.0, 20.0])
        act_pts = self._pts([200.0, 160.0, 130.0])
        rate = analyzer._compute_survival_rate(new_pts, act_pts)
        # surviving: week1 = 160-20=140 → 140/200=0.70; week2 = 130-20=110 → 110/160=0.6875
        expected = (0.70 + 0.6875) / 2
        assert rate == pytest.approx(expected, rel=0.01)

    def test_clamped_to_minimum(self):
        """Survival rate is clamped to [0.5, 1.0] to stay realistic."""
        analyzer = self._analyzer()
        new_pts = self._pts([0.0, 0.0, 0.0])
        act_pts = self._pts([100.0, 1.0, 1.0])  # 99 % weekly churn
        rate = analyzer._compute_survival_rate(new_pts, act_pts)
        assert rate >= 0.5

    def test_clamped_to_maximum(self):
        """Survival rate is clamped to 1.0 even if maths exceeds it."""
        analyzer = self._analyzer()
        new_pts = self._pts([0.0, 50.0, 50.0])
        act_pts = self._pts([100.0, 200.0, 300.0])  # growing fast
        rate = analyzer._compute_survival_rate(new_pts, act_pts)
        assert rate <= 1.0


# ---------------------------------------------------------------------------
# CohortAnalyzer.analyze
# ---------------------------------------------------------------------------


class TestCohortAnalyzerAnalyze:
    def test_returns_list_of_cohorts(self):
        client = _mock_client()
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=4)
        assert isinstance(cohorts, list)
        assert all(isinstance(c, Cohort) for c in cohorts)

    def test_cohort_count_matches_requested_weeks(self):
        # We have 16 data points; requesting 4 cohorts
        client = _mock_client(
            new_customers_chart=_make_chart(16),
            actives_chart=_make_chart(16, 800, 900),
        )
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=4)
        assert len(cohorts) == 4

    def test_week_zero_always_100_pct(self):
        client = _mock_client()
        cohorts = CohortAnalyzer(client).analyze(weeks=3)
        for c in cohorts:
            assert c.retention.get(0) == pytest.approx(100.0)

    def test_retention_decreases_over_weeks(self):
        """Each subsequent week should have equal or lower retention."""
        client = _mock_client()
        cohorts = CohortAnalyzer(client).analyze(weeks=8)
        # Check the oldest cohort (most weeks of data)
        oldest = cohorts[0]
        weeks_sorted = sorted(oldest.retention.keys())
        for i in range(1, len(weeks_sorted)):
            assert oldest.retention[weeks_sorted[i]] <= oldest.retention[weeks_sorted[i - 1]] + 0.01

    def test_newest_cohort_only_has_week_zero(self):
        client = _mock_client()
        cohorts = CohortAnalyzer(client).analyze(weeks=4)
        newest = cohorts[-1]
        assert list(newest.retention.keys()) == [0]

    def test_cohort_size_positive(self):
        client = _mock_client()
        cohorts = CohortAnalyzer(client).analyze(weeks=4)
        for c in cohorts:
            assert c.size >= 1

    def test_start_date_is_string(self):
        client = _mock_client()
        cohorts = CohortAnalyzer(client).analyze(weeks=4)
        for c in cohorts:
            assert isinstance(c.start_date, str)
            assert len(c.start_date) > 0

    def test_fallback_to_actives_new_when_customers_new_fails(self):
        """If customers_new chart fails, fall back to actives_new."""
        actives_new_chart = _make_chart(16, 50, 70)

        client = MagicMock()

        def get_chart(name, **kwargs):
            if name == "customers_new":
                from rc_insights.client import ChartsClientError
                raise ChartsClientError("not found")
            if name == "actives_new":
                return actives_new_chart
            if name == "actives":
                return _make_chart(16, 800, 900)
            raise ValueError(name)

        client.get_chart.side_effect = get_chart
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=4)
        assert len(cohorts) > 0

    def test_returns_empty_when_no_data(self):
        """Returns [] when both new-customer charts are unavailable."""
        client = MagicMock()

        def get_chart(name, **kwargs):
            from rc_insights.client import ChartsClientError
            raise ChartsClientError("not found")

        client.get_chart.side_effect = get_chart
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=4)
        assert cohorts == []

    def test_fewer_data_points_than_weeks(self):
        """Handles gracefully when the API returns fewer points than requested weeks."""
        client = _mock_client(
            new_customers_chart=_make_chart(3),   # only 3 weeks of data
            actives_chart=_make_chart(3, 800, 810),
        )
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=12)
        # Should return at most the available data points
        assert len(cohorts) <= 3


# ---------------------------------------------------------------------------
# CohortAnalyzer.render_table
# ---------------------------------------------------------------------------


class TestRenderTable:
    def test_returns_string(self):
        client = _mock_client()
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=4)
        result = analyzer.render_table(cohorts)
        assert isinstance(result, str)

    def test_empty_cohorts_returns_message(self):
        client = MagicMock()
        analyzer = CohortAnalyzer(client)
        result = analyzer.render_table([])
        assert "No cohort data" in result

    def test_output_contains_cohort_dates(self):
        client = _mock_client()
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=2)
        output = analyzer.render_table(cohorts)
        # At least one cohort date should appear in the rendered text
        assert any(c.start_date[:7] in output for c in cohorts)

    def test_output_contains_week_0(self):
        client = _mock_client()
        analyzer = CohortAnalyzer(client)
        cohorts = analyzer.analyze(weeks=4)
        output = analyzer.render_table(cohorts)
        assert "Wk 0" in output or "100%" in output

    def test_single_cohort_renders(self):
        cohort = Cohort(start_date="2025-01-06", size=100, retention={0: 100.0})
        client = MagicMock()
        analyzer = CohortAnalyzer(client)
        result = analyzer.render_table([cohort])
        assert isinstance(result, str)
        assert len(result) > 0
