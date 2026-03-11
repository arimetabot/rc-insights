"""RC Insights — AI-powered subscription analytics for RevenueCat."""

__version__ = "0.1.0"

from rc_insights.analyzer import SubscriptionAnalyzer
from rc_insights.client import ChartsClient
from rc_insights.models import ChartData, HealthReport, OverviewMetrics

__all__ = [
    "ChartsClient",
    "SubscriptionAnalyzer",
    "ChartData",
    "OverviewMetrics",
    "HealthReport",
]
