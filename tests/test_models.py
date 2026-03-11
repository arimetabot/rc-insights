"""Tests for data models."""

import logging
from datetime import date, datetime

from rc_insights.models import (
    ChartData,
    ChartName,
    HealthReport,
    Insight,
    OverviewMetric,
    OverviewMetrics,
    Resolution,
)


def test_resolution_display_name():
    assert Resolution.DAY.display_name == "day"
    assert Resolution.WEEK.display_name == "week"
    assert Resolution.MONTH.display_name == "month"


def test_resolution_values():
    assert Resolution.DAY.value == "0"
    assert Resolution.WEEK.value == "1"
    assert Resolution.MONTH.value == "2"
    assert Resolution.QUARTER.value == "3"
    assert Resolution.YEAR.value == "4"


def test_chart_name_enum():
    assert ChartName.MRR.value == "mrr"
    assert ChartName.CHURN.value == "churn"
    assert ChartName.REVENUE.value == "revenue"
    # 9 confirmed-working chart slugs (verified against live RevenueCat API)
    assert len(ChartName) == 9


def test_overview_metrics():
    metrics = OverviewMetrics(
        metrics=[
            OverviewMetric(
                id="mrr",
                name="MRR",
                value=5432.10,
                unit="$",
                period="last_28_days",
                description="Monthly Recurring Revenue",
            ),
            OverviewMetric(
                id="churn",
                name="Churn",
                value=3.2,
                unit="%",
                period="last_28_days",
                description="Churn Rate",
            ),
        ]
    )

    assert metrics.mrr == 5432.10
    assert metrics.churn_rate == 3.2
    assert metrics.get_metric("mrr") is not None
    assert metrics.get_metric("nonexistent") is None


def test_chart_data_points_from_list():
    chart = ChartData(
        display_name="Revenue",
        description="Total revenue",
        values=[
            [1704067200000, 100.0],  # 2024-01-01
            [1704153600000, 150.0],  # 2024-01-02
            [1704240000000, 200.0],  # 2024-01-03
        ],
    )

    points = chart.data_points
    assert len(points) == 3
    assert points[0][1] == 100.0
    assert points[1][1] == 150.0
    assert points[2][1] == 200.0
    assert isinstance(points[0][0], datetime)


def test_chart_data_points_from_dict():
    chart = ChartData(
        display_name="MRR",
        description="Monthly recurring revenue",
        values=[
            {"date": 1704067200000, "value": 1000},
            {"date": 1704153600000, "value": 1100},
        ],
    )

    points = chart.data_points
    assert len(points) == 2
    assert points[0][1] == 1000.0


def test_chart_data_empty():
    chart = ChartData(display_name="Empty", description="No data")
    assert chart.data_points == []


def test_insight_model():
    insight = Insight(
        category="revenue",
        severity="critical",
        title="MRR Declining",
        description="MRR dropped 15% this month.",
        recommendation="Investigate churn causes.",
        metric_value="-15%",
        trend="down",
    )

    assert insight.severity == "critical"
    assert insight.trend == "down"


def test_health_report():
    report = HealthReport(
        project_id="proj123",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        overall_health_score=72.0,
        summary="Test summary",
        insights=[
            Insight(
                category="revenue",
                severity="critical",
                title="Bad",
                description="Very bad",
                recommendation="Fix it",
            ),
            Insight(
                category="growth",
                severity="positive",
                title="Good",
                description="Very good",
                recommendation="Keep going",
            ),
            Insight(
                category="churn",
                severity="warning",
                title="Hmm",
                description="Watch this",
                recommendation="Monitor",
            ),
        ],
    )

    assert report.overall_health_score == 72.0
    assert len(report.critical_insights) == 1
    assert len(report.positive_insights) == 1
    assert len(report.warnings) == 1


def test_health_report_empty():
    report = HealthReport(
        project_id="proj123",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
    )

    assert report.overall_health_score == 0.0
    assert report.critical_insights == []
    assert report.summary == ""


def test_chart_data_points_skips_malformed_string_value(caplog):
    """Non-numeric value in data row is skipped with a warning (no crash)."""
    chart = ChartData(
        display_name="Revenue",
        description="Test",
        values=[
            [1704067200000, 100.0],   # valid
            [1704153600000, "N/A"],   # malformed — should be skipped
            [1704240000000, 200.0],   # valid
        ],
    )
    with caplog.at_level(logging.WARNING, logger="rc_insights.models"):
        points = chart.data_points

    assert len(points) == 2
    assert points[0][1] == 100.0
    assert points[1][1] == 200.0
    assert any("malformed" in r.message for r in caplog.records)


def test_chart_data_points_skips_malformed_dict_value(caplog):
    """Non-numeric dict value is skipped with a warning."""
    chart = ChartData(
        display_name="MRR",
        description="Test",
        values=[
            {"date": 1704067200000, "value": "not_a_number"},
            {"date": 1704153600000, "value": 500.0},
        ],
    )
    with caplog.at_level(logging.WARNING, logger="rc_insights.models"):
        points = chart.data_points

    assert len(points) == 1
    assert points[0][1] == 500.0


def test_chart_data_points_handles_none_value():
    """None value in data row defaults to 0.0 without error."""
    chart = ChartData(
        display_name="MRR",
        description="Test",
        values=[[1704067200000, None]],
    )
    points = chart.data_points
    assert len(points) == 1
    assert points[0][1] == 0.0


def test_chart_data_no_chart_data_point_class():
    """ChartDataPoint dead code was removed — it should not exist in models."""
    import rc_insights.models as models_module
    assert not hasattr(models_module, "ChartDataPoint"), (
        "ChartDataPoint was dead code and should have been removed"
    )
