"""Slack and Discord notification senders for RC Insights health reports.

Usage::

    from rc_insights.notifications import SlackNotifier, DiscordNotifier

    slack = SlackNotifier(webhook_url="https://hooks.slack.com/services/...")
    slack.send_report(report)

    discord = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/...")
    discord.send_report(report)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from rc_insights.models import HealthReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity presentation helpers
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI: dict[str, str] = {
    "critical": "🔴",
    "warning": "🟡",
    "positive": "🟢",
    "info": "🔵",
}

# Discord embed color values (decimal integers)
_COLOR_GREEN = 0x2ECC71   # health score > 70
_COLOR_YELLOW = 0xF39C12  # health score 40-70
_COLOR_RED = 0xE74C3C     # health score < 40


def _health_grade(score: float) -> str:
    """Convert a 0-100 health score to a letter grade."""
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


def _health_emoji(score: float) -> str:
    """Return a traffic-light emoji for a health score.

    Thresholds mirror the Discord color bands: green > 70, yellow 40-70, red < 40.
    """
    if score > 70:
        return "🟢"
    if score >= 40:
        return "🟡"
    return "🔴"


def _discord_color(score: float) -> int:
    """Return a Discord embed color integer for a health score."""
    if score > 70:
        return _COLOR_GREEN
    if score >= 40:
        return _COLOR_YELLOW
    return _COLOR_RED


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


class SlackNotifier:
    """Sends RevenueCat health reports to a Slack channel via Incoming Webhooks.

    Args:
        webhook_url: The Slack Incoming Webhook URL (from the Slack app config).

    Example::

        notifier = SlackNotifier("https://hooks.slack.com/services/T.../B.../xxx")
        notifier.send_report(health_report)
    """

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send_report(self, report: HealthReport) -> bool:
        """Format and send a health report summary to Slack.

        Returns:
            ``True`` if the Slack API accepted the message (HTTP 200), else ``False``.
        """
        payload = self._format_blocks(report)
        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10.0)
        except httpx.RequestError as exc:
            logger.error("Slack webhook request failed: %s", exc)
            return False

        if resp.status_code != 200:
            logger.warning(
                "Slack webhook returned HTTP %d: %s", resp.status_code, resp.text[:200]
            )
        return resp.status_code == 200

    def _format_blocks(self, report: HealthReport) -> dict:
        """Build a polished Slack Block Kit payload from a :class:`HealthReport`."""
        score = report.overall_health_score
        grade = _health_grade(score)
        emoji = _health_emoji(score)

        blocks: list[dict] = []

        # ── Header ──────────────────────────────────────────────────────────
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"RC Insights Health Report  {emoji}  Grade: {grade}",
                    "emoji": True,
                },
            }
        )

        # ── Report meta ──────────────────────────────────────────────────────
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Project:* `{report.project_id}`  •  "
                        f"*Period:* {report.period_start} → {report.period_end}  •  "
                        f"*Score:* {score:.0f}/100"
                    ),
                },
            }
        )
        blocks.append({"type": "divider"})

        # ── Key metrics (2-column fields) ────────────────────────────────────
        if report.overview:
            ov = report.overview
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*MRR*\n${ov.mrr:,.2f}"},
                        {"type": "mrkdwn", "text": f"*Churn Rate*\n{ov.churn_rate:.2f}%"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Active Subscribers*\n{ov.active_subscribers:,.0f}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Active Trials*\n{ov.active_trials:,.0f}",
                        },
                    ],
                }
            )
            blocks.append({"type": "divider"})

        # ── Top 3 insights ───────────────────────────────────────────────────
        top_insights = report.insights[:3]
        if top_insights:
            lines: list[str] = ["*Top Insights*"]
            for insight in top_insights:
                sev_icon = _SEVERITY_EMOJI.get(insight.severity, "ℹ️")
                lines.append(f"{sev_icon} *{insight.title}*")
                lines.append(f"  {insight.description}")
                if insight.recommendation:
                    lines.append(f"  _Rec:_ {insight.recommendation}")
                lines.append("")

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join(lines).strip(),
                    },
                }
            )
            blocks.append({"type": "divider"})

        # ── Executive summary ────────────────────────────────────────────────
        if report.summary:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Summary*\n{report.summary}",
                    },
                }
            )

        # ── Footer ───────────────────────────────────────────────────────────
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"🤖 Generated by RC Insights  •  "
                            f"{report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
                        ),
                    }
                ],
            }
        )

        return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------


class DiscordNotifier:
    """Sends RevenueCat health reports to a Discord channel via webhook embeds.

    Args:
        webhook_url: The Discord webhook URL
            (``https://discord.com/api/webhooks/<id>/<token>``).

    Example::

        notifier = DiscordNotifier("https://discord.com/api/webhooks/...")
        notifier.send_report(health_report)
    """

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send_report(self, report: HealthReport) -> bool:
        """Format and send a health report summary to Discord.

        Returns:
            ``True`` if Discord accepted the webhook (HTTP 204), else ``False``.
        """
        embed = self._format_embed(report)
        try:
            resp = httpx.post(
                self.webhook_url, json={"embeds": [embed]}, timeout=10.0
            )
        except httpx.RequestError as exc:
            logger.error("Discord webhook request failed: %s", exc)
            return False

        if resp.status_code != 204:
            logger.warning(
                "Discord webhook returned HTTP %d: %s", resp.status_code, resp.text[:200]
            )
        return resp.status_code == 204

    def _format_embed(self, report: HealthReport) -> dict:
        """Build a rich Discord embed with color-coded health status."""
        score = report.overall_health_score
        grade = _health_grade(score)
        emoji = _health_emoji(score)
        color = _discord_color(score)

        fields: list[dict] = []

        # Health score field
        fields.append(
            {
                "name": f"{emoji} Health Score",
                "value": f"**{score:.0f}/100** — Grade **{grade}**",
                "inline": False,
            }
        )

        # Key metrics
        if report.overview:
            ov = report.overview
            fields.extend(
                [
                    {
                        "name": "💰 MRR",
                        "value": f"${ov.mrr:,.2f}",
                        "inline": True,
                    },
                    {
                        "name": "📉 Churn Rate",
                        "value": f"{ov.churn_rate:.2f}%",
                        "inline": True,
                    },
                    {
                        "name": "👥 Active Subscribers",
                        "value": f"{ov.active_subscribers:,.0f}",
                        "inline": True,
                    },
                    {
                        "name": "🔬 Active Trials",
                        "value": f"{ov.active_trials:,.0f}",
                        "inline": True,
                    },
                ]
            )

        # Top 3 insights
        top_insights = report.insights[:3]
        if top_insights:
            insight_lines: list[str] = []
            for insight in top_insights:
                sev_icon = _SEVERITY_EMOJI.get(insight.severity, "ℹ️")
                insight_lines.append(
                    f"{sev_icon} **{insight.title}**\n{insight.description}"
                )
            fields.append(
                {
                    "name": "📊 Key Insights",
                    "value": "\n\n".join(insight_lines),
                    "inline": False,
                }
            )

        embed: dict = {
            "title": "RC Insights — Health Report",
            "color": color,
            "fields": fields,
            "footer": {
                "text": (
                    f"RC Insights  •  "
                    f"Period: {report.period_start} → {report.period_end}  •  "
                    f"{report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
                ),
            },
            "timestamp": report.generated_at.isoformat(),
        }

        if report.summary:
            embed["description"] = report.summary[:4096]  # Discord character limit

        return embed
