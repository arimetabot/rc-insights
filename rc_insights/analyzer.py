"""AI-powered subscription analytics engine."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any

from rc_insights.client import AuthenticationError, ChartsClient, ChartsClientError
from rc_insights.models import (
    ChartData,
    HealthReport,
    Insight,
    OverviewMetrics,
    Resolution,
)

logger = logging.getLogger(__name__)


def _format_metrics_for_llm(
    overview: OverviewMetrics | None,
    charts: dict[str, ChartData],
) -> str:
    """Format metrics data into a concise text summary for the LLM."""
    parts: list[str] = []

    if overview:
        parts.append("## Current Overview Metrics")
        for m in overview.metrics:
            unit = f" {m.unit}" if m.unit and m.unit != "number" else ""
            parts.append(f"- **{m.name}**: {m.value:,.2f}{unit} ({m.period})")

    for _chart_name, chart in charts.items():
        parts.append(f"\n## {chart.display_name}")
        parts.append(f"*{chart.description}*")
        points = chart.data_points
        if points:
            values_only = [v for _, v in points if v is not None]
            if values_only:
                parts.append(f"- Period: {len(points)} data points")
                parts.append(f"- Latest: {values_only[-1]:,.2f}")
                parts.append(f"- Min: {min(values_only):,.2f}")
                parts.append(f"- Max: {max(values_only):,.2f}")
                parts.append(f"- Average: {sum(values_only) / len(values_only):,.2f}")

                # Trend analysis
                if len(values_only) >= 7:
                    first_week = sum(values_only[:7]) / 7
                    last_week = sum(values_only[-7:]) / 7
                    if first_week > 0:
                        change_pct = ((last_week - first_week) / first_week) * 100
                        direction = "↑" if change_pct > 0 else "↓"
                        parts.append(
                            f"- Trend (first week avg → last week avg): "
                            f"{direction} {abs(change_pct):.1f}%"
                        )
        elif chart.summary:
            parts.append(f"- Summary: {json.dumps(chart.summary, indent=2)}")

    return "\n".join(parts)


ANALYSIS_SYSTEM_PROMPT = """You are a subscription analytics expert analyzing RevenueCat Charts API data for an indie app developer. Your job is to:

1. Identify the most important trends and patterns
2. Flag critical issues (churn spikes, MRR drops, trial conversion problems)
3. Highlight positive signals (growth, improving retention, expanding LTV)
4. Provide specific, actionable recommendations

Be data-driven and specific. Reference actual numbers. Think like a CFO advising a founder.

Output your analysis as a JSON object with this exact structure:
{
    "overall_health_score": <0-100 integer>,
    "summary": "<2-3 sentence executive summary>",
    "insights": [
        {
            "category": "<revenue|churn|growth|retention|trials|refunds|info>",
            "severity": "<critical|warning|positive|info>",
            "title": "<short title>",
            "description": "<what's happening, with specific numbers>",
            "recommendation": "<specific action to take>",
            "metric_value": "<key number as string>",
            "trend": "<up|down|stable>"
        }
    ]
}

Provide 5-8 insights, prioritized by impact. Always include at least one actionable recommendation per insight."""


class SubscriptionAnalyzer:
    """AI-powered subscription analytics engine.

    Connects to RevenueCat Charts API, pulls data, and uses any LLM
    (via litellm) to generate actionable insights and health reports.
    Supports OpenAI, Anthropic, Ollama, Groq, Mistral, Azure, and 100+ others.

    Usage:
        # OpenAI (default)
        analyzer = SubscriptionAnalyzer(
            rc_api_key="sk_...",
            rc_project_id="proj...",
            llm_api_key="sk-...",        # or set OPENAI_API_KEY env var
        )

        # Anthropic Claude
        analyzer = SubscriptionAnalyzer(
            rc_api_key="sk_...",
            rc_project_id="proj...",
            llm_model="claude-sonnet-4-5",  # or any litellm model string
        )

        # Ollama (local, no key needed)
        analyzer = SubscriptionAnalyzer(
            rc_api_key="sk_...",
            rc_project_id="proj...",
            llm_model="ollama/llama3",
        )

        report = analyzer.generate_report()
        print(report.summary)
    """

    def __init__(
        self,
        rc_api_key: str,
        rc_project_id: str,
        *,
        openai_api_key: str | None = None,   # Deprecated: use llm_api_key
        openai_model: str = "gpt-4o-mini",   # Deprecated: use llm_model
        llm_api_key: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        self.client = ChartsClient(api_key=rc_api_key, project_id=rc_project_id)
        self.project_id = rc_project_id
        # llm_api_key takes precedence; fall back to openai_api_key for backward compat
        self.llm_api_key = llm_api_key or openai_api_key
        # llm_model takes precedence; fall back to openai_model for backward compat
        self.llm_model = llm_model or openai_model
        # Backward compat attributes so existing code referencing .openai_api_key still works
        self.openai_api_key = self.llm_api_key
        self.openai_model = self.llm_model

    def _analyze_with_ai(
        self,
        overview: OverviewMetrics | None,
        charts: dict[str, ChartData],
    ) -> tuple[float, str, list[Insight]]:
        """Use any LLM (via litellm) to analyze metrics and generate insights.

        Supports OpenAI, Anthropic, Ollama, Groq, Mistral, Azure, and 100+ providers.
        Falls back to heuristic analysis if litellm is not installed or the call fails.
        """
        try:
            import litellm  # lazy import — graceful fallback if not installed

            metrics_text = _format_metrics_for_llm(overview, charts)
            messages: list[dict[str, str]] = [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Analyze these subscription metrics:\n\n{metrics_text}",
                },
            ]
            kwargs: dict[str, Any] = {
                "model": self.llm_model,
                "messages": messages,
                "temperature": 0.3,
            }
            if self.llm_api_key:
                kwargs["api_key"] = self.llm_api_key

            # Try with JSON mode first; some models don't support response_format
            try:
                response = litellm.completion(**kwargs, response_format={"type": "json_object"})
            except Exception:
                # Retry without response_format — parse JSON from raw text instead
                response = litellm.completion(**kwargs)

            content = response.choices[0].message.content or "{}"

            # Extract JSON even if the model wrapped it in markdown code blocks
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            result = json.loads(content)
            insights = [Insight.model_validate(i) for i in result.get("insights", [])]
            health_score = float(result.get("overall_health_score", 50))
            summary = result.get("summary", "Analysis complete.")

            return health_score, summary, insights

        except ImportError:
            logger.warning("litellm not installed, falling back to heuristic analysis")
            return self._analyze_with_heuristics(overview, charts)
        except Exception as e:
            logger.warning("AI analysis failed, falling back to heuristics: %s", e)
            return self._analyze_with_heuristics(overview, charts)

    def _analyze_with_heuristics(
        self,
        overview: OverviewMetrics | None,
        charts: dict[str, ChartData],
    ) -> tuple[float, str, list[Insight]]:
        """Rule-based analysis when LLM is not available."""
        insights: list[Insight] = []
        score = 60.0  # Start slightly positive — stable MRR baseline

        # Track which chart-based insights we'll generate to avoid duplication
        has_mrr_chart = "mrr" in charts

        if overview:
            # MRR from overview — only show if no chart data provides a richer view
            if overview.mrr > 0 and not has_mrr_chart:
                insights.append(
                    Insight(
                        category="revenue",
                        severity="info",
                        title="Current MRR",
                        description=f"Monthly recurring revenue is ${overview.mrr:,.2f}.",
                        recommendation="Track MRR growth rate week-over-week.",
                        metric_value=f"${overview.mrr:,.2f}",
                        trend="stable",
                    )
                )

            # Churn analysis
            if overview.churn_rate > 0:
                if overview.churn_rate > 10:
                    severity = "critical"
                    score -= 20
                elif overview.churn_rate > 5:
                    severity = "warning"
                    score -= 10
                else:
                    severity = "positive"
                    score += 10

                insights.append(
                    Insight(
                        category="churn",
                        severity=severity,
                        title="Churn Rate",
                        description=f"Current churn rate is {overview.churn_rate:.1f}%.",
                        recommendation=(
                            "Investigate cancellation reasons. Consider exit surveys."
                            if overview.churn_rate > 5
                            else "Churn is healthy. Maintain current retention strategies."
                        ),
                        metric_value=f"{overview.churn_rate:.1f}%",
                        trend="stable",
                    )
                )

        # Chart trend analysis
        for chart_name, chart in charts.items():
            points = chart.data_points
            values = [v for _, v in points if v is not None]
            if len(values) < 7:
                continue

            first_week_avg = sum(values[:7]) / 7
            last_week_avg = sum(values[-7:]) / 7
            latest = values[-1] if values else 0

            if first_week_avg > 0:
                change_pct = ((last_week_avg - first_week_avg) / first_week_avg) * 100
            else:
                change_pct = 0

            trend = "up" if change_pct > 2 else ("down" if change_pct < -2 else "stable")

            # MRR stability check
            if chart_name == "mrr":
                if change_pct < -5:
                    insights.append(
                        Insight(
                            category="revenue",
                            severity="warning",
                            title="MRR Declining",
                            description=(
                                f"MRR dropped {abs(change_pct):.1f}% from "
                                f"${first_week_avg:,.2f} to ${last_week_avg:,.2f} avg."
                            ),
                            recommendation="Investigate churn sources. Consider retention campaigns.",
                            metric_value=f"{change_pct:+.1f}%",
                            trend=trend,
                        )
                    )
                    score -= 10
                elif change_pct > 5:
                    insights.append(
                        Insight(
                            category="revenue",
                            severity="positive",
                            title="MRR Growing",
                            description=(
                                f"MRR grew {change_pct:.1f}% from "
                                f"${first_week_avg:,.2f} to ${last_week_avg:,.2f} avg."
                            ),
                            recommendation="Identify what's driving MRR growth and double down.",
                            metric_value=f"+{change_pct:.1f}%",
                            trend=trend,
                        )
                    )
                    score += 10
                else:
                    insights.append(
                        Insight(
                            category="revenue",
                            severity="info",
                            title="MRR Stable",
                            description=(
                                f"MRR is stable at ~${latest:,.2f}, with {change_pct:+.1f}% "
                                f"change over the period."
                            ),
                            recommendation=(
                                "MRR is holding steady. Focus on acquisition to grow "
                                "the baseline."
                            ),
                            metric_value=f"${latest:,.2f}",
                            trend=trend,
                        )
                    )

            # Revenue trend
            elif chart_name == "revenue" and change_pct < -10:
                insights.append(
                    Insight(
                        category="revenue",
                        severity="warning",
                        title="Revenue Declining",
                        description=(
                            f"Daily revenue dropped {abs(change_pct):.1f}% over the period. "
                            f"Latest day: ${latest:,.2f}."
                        ),
                        recommendation=(
                            "Check for seasonal patterns. Review app store performance "
                            "and recent updates."
                        ),
                        metric_value=f"{change_pct:+.1f}%",
                        trend=trend,
                    )
                )
                score -= 5

            # MRR movement (rate of MRR change)
            elif chart_name == "mrr_movement" and change_pct < -30:
                insights.append(
                    Insight(
                        category="revenue",
                        severity="warning",
                        title="MRR Growth Rate Slowing",
                        description=(
                            f"Net MRR movement has declined {abs(change_pct):.1f}%, "
                            f"indicating slowing growth momentum."
                        ),
                        recommendation=(
                            "Review new subscriber acquisition — growth may be decelerating. "
                            "Consider pricing experiments or new acquisition channels."
                        ),
                        metric_value=f"{change_pct:+.1f}%",
                        trend=trend,
                    )
                )
                score -= 8

            # Active subscriber changes
            elif chart_name == "actives" and change_pct < -10:
                insights.append(
                    Insight(
                        category="growth",
                        severity="critical",
                        title="Active Subscribers Declining",
                        description=(
                            f"Active subscriptions dropped {abs(change_pct):.1f}% "
                            f"from {first_week_avg:,.0f} to {last_week_avg:,.0f} avg."
                        ),
                        recommendation=(
                            "Immediate investigation needed. Check for billing failures, "
                            "cancellation spikes, or platform issues."
                        ),
                        metric_value=f"{change_pct:+.1f}%",
                        trend=trend,
                    )
                )
                score -= 15
            elif chart_name == "actives" and change_pct > 5:
                insights.append(
                    Insight(
                        category="growth",
                        severity="positive",
                        title="Active Subscribers Growing",
                        description=(
                            f"Active subscriptions grew {change_pct:.1f}% "
                            f"to {latest:,.0f} subscribers."
                        ),
                        recommendation="Identify acquisition channels driving growth and scale them.",
                        metric_value=f"+{change_pct:.1f}%",
                        trend=trend,
                    )
                )
                score += 10

            # Churn — declining churn is GOOD
            elif chart_name == "churn":
                if change_pct > 20:
                    insights.append(
                        Insight(
                            category="churn",
                            severity="critical",
                            title="Churn Rate Spike",
                            description=(
                                f"Churn increased {change_pct:.1f}% over the period. "
                                f"Latest rate: {latest:.2f}%."
                            ),
                            recommendation=(
                                "Check for recent app issues, pricing changes, or competitor "
                                "activity. Consider win-back campaigns."
                            ),
                            metric_value=f"+{change_pct:.1f}%",
                            trend="up",
                        )
                    )
                    score -= 20
                elif change_pct < -15:
                    insights.append(
                        Insight(
                            category="churn",
                            severity="positive",
                            title="Churn Improving",
                            description=(
                                f"Churn rate has decreased {abs(change_pct):.1f}% over the period — "
                                f"retention is improving."
                            ),
                            recommendation=(
                                "Document what's working for retention and reinforce it. "
                                "Identify the segments with highest retention."
                            ),
                            metric_value=f"{change_pct:+.1f}%",
                            trend="down",
                        )
                    )
                    score += 8

            # New customers declining
            elif chart_name == "customers_new" and change_pct < -15:
                insights.append(
                    Insight(
                        category="growth",
                        severity="warning",
                        title="New Customer Acquisition Slowing",
                        description=(
                            f"New customers declined {abs(change_pct):.1f}% — "
                            f"from {first_week_avg:.0f}/day to {last_week_avg:.0f}/day avg."
                        ),
                        recommendation=(
                            "Review top-of-funnel metrics. Check app store rankings, "
                            "ratings, and recent update impact."
                        ),
                        metric_value=f"{change_pct:+.1f}%",
                        trend=trend,
                    )
                )
                score -= 8

            # Refund rate check
            elif chart_name == "refund_rate":
                recent_nonzero = [v for v in values[-14:] if v > 0]
                if recent_nonzero and (sum(recent_nonzero) / len(recent_nonzero)) > 5:
                    avg_refund = sum(recent_nonzero) / len(recent_nonzero)
                    insights.append(
                        Insight(
                            category="refunds",
                            severity="warning",
                            title="Elevated Refund Rate",
                            description=(
                                f"Recent refund rate averaging {avg_refund:.1f}%. "
                                f"Industry benchmark is <3%."
                            ),
                            recommendation=(
                                "Review refund reasons in RevenueCat. Common causes: "
                                "accidental purchases, unclear value prop, subscription confusion."
                            ),
                            metric_value=f"{avg_refund:.1f}%",
                            trend=trend,
                        )
                    )
                    score -= 10

        # Ensure minimum insights
        if not insights:
            insights.append(
                Insight(
                    category="info",
                    severity="info",
                    title="Insufficient Data",
                    description="Not enough data points to generate meaningful insights.",
                    recommendation="Ensure the Charts API is returning data for all key metrics.",
                )
            )

        score = max(0, min(100, score))
        summary = self._generate_heuristic_summary(score, insights)

        return score, summary, insights

    def _generate_heuristic_summary(self, score: float, insights: list[Insight]) -> str:
        """Generate a text summary from heuristic analysis."""
        critical = [i for i in insights if i.severity == "critical"]
        positive = [i for i in insights if i.severity == "positive"]

        parts: list[str] = []
        if score >= 70:
            parts.append("Your subscription business looks healthy overall.")
        elif score >= 40:
            parts.append("Your subscription metrics show mixed signals.")
        else:
            parts.append("⚠️ Your subscription metrics need immediate attention.")

        if critical:
            parts.append(
                f"Critical issues: {', '.join(i.title for i in critical)}."
            )
        if positive:
            parts.append(
                f"Bright spots: {', '.join(i.title for i in positive)}."
            )

        return " ".join(parts)

    def generate_report(
        self,
        *,
        days: int = 30,
        resolution: Resolution = Resolution.DAY,
        include_ai: bool = True,
    ) -> HealthReport:
        """Generate a complete subscription health report.

        Args:
            days: Number of days to analyze.
            resolution: Time resolution for charts.
            include_ai: Whether to use AI for analysis (requires OpenAI key).

        Returns:
            HealthReport with metrics, charts, insights, and health score.
        """
        end = date.today()
        start = end - timedelta(days=days)

        logger.info("Generating report for %s to %s...", start, end)

        # Fetch overview metrics
        overview: OverviewMetrics | None = None
        try:
            overview = self.client.get_overview()
            logger.info("Fetched overview metrics")
        except AuthenticationError:
            raise  # Auth errors must surface — user needs to know their key is wrong
        except ChartsClientError as e:
            logger.warning("Could not fetch overview: %s", e)

        # Fetch core charts
        charts = self.client.get_all_core_charts(
            start_date=start,
            end_date=end,
            resolution=resolution,
        )
        logger.info("Fetched %s charts", len(charts))

        # Analyze — litellm reads provider API keys from env vars automatically
        if include_ai:
            health_score, summary, insights = self._analyze_with_ai(overview, charts)
        else:
            health_score, summary, insights = self._analyze_with_heuristics(
                overview, charts
            )

        return HealthReport(
            project_id=self.project_id,
            period_start=start,
            period_end=end,
            overview=overview,
            charts_data=charts,
            insights=insights,
            overall_health_score=health_score,
            summary=summary,
        )

    def close(self) -> None:
        """Close underlying clients."""
        self.client.close()

    def __enter__(self) -> SubscriptionAnalyzer:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
