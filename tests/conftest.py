"""Shared pytest fixtures for RC Insights tests."""

from __future__ import annotations

import pytest

from rc_insights.analyzer import SubscriptionAnalyzer
from rc_insights.models import ChartData, OverviewMetric, OverviewMetrics


@pytest.fixture()
def make_overview():
    """Factory fixture: build an OverviewMetrics with customisable key values."""

    def _factory(
        mrr: float = 5000.0,
        churn_rate: float = 3.0,
        active_subscribers: float = 500.0,
    ) -> OverviewMetrics:
        return OverviewMetrics(
            metrics=[
                OverviewMetric(
                    id="mrr",
                    name="MRR",
                    value=mrr,
                    unit="$",
                    period="last_28_days",
                    description="MRR",
                ),
                OverviewMetric(
                    id="churn",
                    name="Churn",
                    value=churn_rate,
                    unit="%",
                    period="last_28_days",
                    description="Churn Rate",
                ),
                OverviewMetric(
                    id="active_subscribers",
                    name="Active Subscribers",
                    value=active_subscribers,
                    unit="number",
                    period="last_28_days",
                    description="Active Subscribers",
                ),
            ]
        )

    return _factory


@pytest.fixture()
def make_chart():
    """Factory fixture: build a ChartData with a linear trend between two values."""

    def _factory(
        name: str,
        start_val: float = 100.0,
        end_val: float = 110.0,
        n_points: int = 30,
    ) -> ChartData:
        """Create a chart with a linear trend from *start_val* to *end_val*.

        Args:
            name: Display name for the chart.
            start_val: Value at index 0.
            end_val: Value at index ``n_points - 1``.
            n_points: Number of daily data points to generate.

        Returns:
            A :class:`~rc_insights.models.ChartData` populated with synthetic values.
        """
        values = []
        for i in range(n_points):
            ts = 1704067200000 + (i * 86_400_000)  # 1-day intervals, starting 2024-01-01
            val = start_val + (end_val - start_val) * i / max(n_points - 1, 1)
            values.append([ts, val])
        return ChartData(
            display_name=name,
            description=f"{name} chart",
            values=values,
        )

    return _factory


@pytest.fixture()
def make_analyzer():
    """Factory fixture: build a SubscriptionAnalyzer wired to a test project."""

    def _factory(
        rc_api_key: str = "sk_test",
        rc_project_id: str = "proj_test",
        llm_api_key: str | None = None,
    ) -> SubscriptionAnalyzer:
        return SubscriptionAnalyzer(
            rc_api_key=rc_api_key,
            rc_project_id=rc_project_id,
            llm_api_key=llm_api_key,
        )

    return _factory
