"""Data models for RC Insights."""

from __future__ import annotations

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Resolution(str, Enum):
    """Time resolution for chart data.

    The RevenueCat Charts API v2 uses numeric codes for resolution:
    "0"=day, "1"=week, "2"=month, "3"=quarter, "4"=year.
    (Verified via RC dashboard URL parameters, e.g. resolution=2 for monthly.)
    """

    DAY = "0"
    WEEK = "1"
    MONTH = "2"
    QUARTER = "3"
    YEAR = "4"

    @property
    def display_name(self) -> str:
        return {
            "0": "day",
            "1": "week",
            "2": "month",
            "3": "quarter",
            "4": "year",
        }[self.value]


class ChartName(str, Enum):
    """Available chart types in RevenueCat.

    Chart slugs verified against a live RevenueCat Charts API v2 response
    for project proj058a6330 (Dark Noise). Only confirmed-working slugs are
    included — charts that returned HTTP 400 have been excluded.

    Confirmed working (9 charts):
        revenue, mrr, churn, refund_rate, actives, actives_new,
        customers_new, customers_active, mrr_movement

    Excluded (returned 400 errors):
        annual_recurring_revenue, active_subscriptions, active_trials,
        new_customers, new_subscriptions, trial_conversion,
        realized_ltv_per_customer, initial_conversion,
        active_subscriptions_movement
    """

    # Revenue
    REVENUE = "revenue"
    MRR = "mrr"
    MRR_MOVEMENT = "mrr_movement"

    # Subscribers
    ACTIVES = "actives"
    ACTIVES_NEW = "actives_new"
    CUSTOMERS_NEW = "customers_new"
    CUSTOMERS_ACTIVE = "customers_active"

    # Health
    CHURN = "churn"
    REFUND_RATE = "refund_rate"


class OverviewMetric(BaseModel):
    """A single overview metric from RevenueCat."""

    id: str
    name: str
    value: float
    unit: str
    period: str
    description: str
    last_updated_at_iso8601: str | None = None


class OverviewMetrics(BaseModel):
    """Collection of overview metrics."""

    object: str = "overview_metrics"
    metrics: list[OverviewMetric] = Field(default_factory=list)

    def get_metric(self, metric_id: str) -> OverviewMetric | None:
        """Get a specific metric by ID."""
        return next((m for m in self.metrics if m.id == metric_id), None)

    @property
    def mrr(self) -> float:
        m = self.get_metric("mrr")
        return m.value if m else 0.0

    @property
    def revenue(self) -> float:
        m = self.get_metric("revenue")
        return m.value if m else 0.0

    @property
    def active_subscribers(self) -> float:
        m = self.get_metric("active_subscribers")
        return m.value if m else 0.0

    @property
    def active_trials(self) -> float:
        m = self.get_metric("active_trials")
        return m.value if m else 0.0

    @property
    def churn_rate(self) -> float:
        m = self.get_metric("churn")
        return m.value if m else 0.0


class ChartData(BaseModel):
    """Response from the Charts API."""

    object: str = "chart_data"
    category: str = ""
    display_type: str = ""
    display_name: str = ""
    description: str = ""
    resolution: str = "day"
    start_date: int | None = None
    end_date: int | None = None
    yaxis_currency: str = "USD"
    yaxis: str = ""
    values: list[Any] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    measures: list[dict[str, Any]] | None = None
    segments: list[Any] | None = None

    @property
    def data_points(self) -> list[tuple[datetime | None, float]]:
        """Parse values into (timestamp, value) tuples.

        Malformed data points (e.g. non-numeric values) are skipped with a warning
        rather than crashing the entire report.
        """
        points: list[tuple[datetime | None, float]] = []
        for row in self.values:
            if isinstance(row, list) and len(row) >= 2:
                ts = datetime.fromtimestamp(row[0] / 1000) if row[0] else None
                try:
                    val = float(row[1]) if row[1] is not None else 0.0
                except (TypeError, ValueError):
                    logger.warning(
                        "Skipping malformed data point value: %r (expected numeric)", row[1]
                    )
                    continue
                points.append((ts, val))
            elif isinstance(row, dict):
                ts_raw = row.get("date") or row.get("timestamp")
                try:
                    val = float(row.get("value", 0))
                except (TypeError, ValueError):
                    logger.warning(
                        "Skipping malformed data point value: %r (expected numeric)",
                        row.get("value"),
                    )
                    continue
                ts = None
                if isinstance(ts_raw, int):
                    ts = datetime.fromtimestamp(ts_raw / 1000)
                elif isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw)
                points.append((ts, val))
        return points


class Insight(BaseModel):
    """An AI-generated insight about the subscription business."""

    category: str  # "revenue", "churn", "growth", "retention", "trials", "refunds", "info"
    severity: str  # "critical", "warning", "positive", "info"
    title: str
    description: str
    recommendation: str
    metric_value: str | None = None
    trend: str | None = None  # "up", "down", "stable"


class HealthReport(BaseModel):
    """Complete subscription health report."""

    generated_at: datetime = Field(default_factory=datetime.now)
    project_id: str
    period_start: date
    period_end: date
    overview: OverviewMetrics | None = None
    charts_data: dict[str, ChartData] = Field(default_factory=dict)
    insights: list[Insight] = Field(default_factory=list)
    overall_health_score: float = 0.0  # 0-100
    summary: str = ""

    @property
    def critical_insights(self) -> list[Insight]:
        return [i for i in self.insights if i.severity == "critical"]

    @property
    def warnings(self) -> list[Insight]:
        return [i for i in self.insights if i.severity == "warning"]

    @property
    def positive_insights(self) -> list[Insight]:
        return [i for i in self.insights if i.severity == "positive"]
