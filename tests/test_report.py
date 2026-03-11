"""Tests for report rendering."""

from datetime import date

from rc_insights.models import (
    HealthReport,
    Insight,
    OverviewMetric,
    OverviewMetrics,
)
from rc_insights.report import render_html, render_markdown


def _make_report() -> HealthReport:
    """Create a sample report for testing."""
    return HealthReport(
        project_id="proj_test_123",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        overall_health_score=72.0,
        summary="Your subscription business is growing steadily.",
        overview=OverviewMetrics(
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
                    id="active_subscribers",
                    name="Active Subscribers",
                    value=342,
                    unit="number",
                    period="last_28_days",
                    description="Active paying subscribers",
                ),
            ]
        ),
        insights=[
            Insight(
                category="revenue",
                severity="positive",
                title="MRR Growing",
                description="MRR grew 8.3% over the period.",
                recommendation="Identify what's driving growth.",
                metric_value="+8.3%",
                trend="up",
            ),
            Insight(
                category="trials",
                severity="warning",
                title="Low Trial Conversion",
                description="Trial conversion at 6.2%, below 10-15% benchmark.",
                recommendation="Optimize onboarding experience.",
                metric_value="6.2%",
                trend="stable",
            ),
        ],
    )


def test_render_markdown():
    report = _make_report()
    md = render_markdown(report)

    assert "Subscription Health Report" in md
    assert "72" in md
    assert "proj_test_123" in md
    assert "MRR Growing" in md
    assert "Low Trial Conversion" in md
    assert "5,432.10" in md
    assert "RC Insights" in md


def test_render_markdown_empty_report():
    report = HealthReport(
        project_id="proj_empty",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
    )
    md = render_markdown(report)
    assert "proj_empty" in md
    assert "0" in md  # Health score


def test_render_html():
    report = _make_report()
    html = render_html(report)

    assert "<!DOCTYPE html>" in html
    assert "proj_test_123" in html
    assert "72" in html
    assert "MRR Growing" in html
    assert "Low Trial Conversion" in html


def test_render_html_has_styles():
    report = _make_report()
    html = render_html(report)

    assert "<style>" in html
    assert "--bg:" in html
    assert "score-card" in html
    assert "insight " in html  # CSS class for insight cards
