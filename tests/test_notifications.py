"""Tests for Slack and Discord notification senders."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from rc_insights.models import (
    HealthReport,
    Insight,
    OverviewMetric,
    OverviewMetrics,
)
from rc_insights.notifications import (
    DiscordNotifier,
    SlackNotifier,
    _discord_color,
    _health_emoji,
    _health_grade,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_report() -> HealthReport:
    """A bare-minimum HealthReport with no overview or insights."""
    return HealthReport(
        project_id="proj_test",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        overall_health_score=75.0,
        generated_at=datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture()
def full_report() -> HealthReport:
    """A fully populated HealthReport with overview, insights, and summary."""
    overview = OverviewMetrics(
        metrics=[
            OverviewMetric(
                id="mrr",
                name="MRR",
                value=12_000.0,
                unit="$",
                period="last_28_days",
                description="Monthly Recurring Revenue",
            ),
            OverviewMetric(
                id="churn",
                name="Churn Rate",
                value=2.5,
                unit="%",
                period="last_28_days",
                description="Churn rate",
            ),
            OverviewMetric(
                id="active_subscribers",
                name="Active Subscribers",
                value=800.0,
                unit="number",
                period="last_28_days",
                description="Active subscribers",
            ),
            OverviewMetric(
                id="active_trials",
                name="Active Trials",
                value=120.0,
                unit="number",
                period="last_28_days",
                description="Active trials",
            ),
        ]
    )
    insights = [
        Insight(
            category="revenue",
            severity="positive",
            title="MRR Growing Steadily",
            description="MRR increased 15% over the past month.",
            recommendation="Continue current acquisition strategy.",
            metric_value="$12,000",
            trend="up",
        ),
        Insight(
            category="churn",
            severity="warning",
            title="Churn Spike in Week 3",
            description="Churn jumped 0.8 pp in week 3.",
            recommendation="Investigate cohort behaviour.",
            metric_value="2.5%",
            trend="up",
        ),
        Insight(
            category="billing",
            severity="critical",
            title="Billing Failures Elevated",
            description="3.1% billing failure rate detected.",
            recommendation="Review payment processor error codes.",
        ),
        Insight(
            category="growth",
            severity="info",
            title="Trial-to-Paid Stable",
            description="Conversion rate unchanged at 35%.",
            recommendation="",
        ),
    ]
    return HealthReport(
        project_id="proj_full",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        overall_health_score=62.0,
        overview=overview,
        insights=insights,
        summary="Overall health is good. Watch billing failures.",
        generated_at=datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHealthGrade:
    def test_a_grade(self) -> None:
        assert _health_grade(85.0) == "A"
        assert _health_grade(80.0) == "A"

    def test_b_grade(self) -> None:
        assert _health_grade(70.0) == "B"
        assert _health_grade(60.0) == "B"

    def test_c_grade(self) -> None:
        assert _health_grade(55.0) == "C"
        assert _health_grade(40.0) == "C"

    def test_d_grade(self) -> None:
        assert _health_grade(30.0) == "D"
        assert _health_grade(20.0) == "D"

    def test_f_grade(self) -> None:
        assert _health_grade(10.0) == "F"
        assert _health_grade(0.0) == "F"


class TestHealthEmoji:
    def test_green_above_70(self) -> None:
        assert _health_emoji(71.0) == "🟢"
        assert _health_emoji(100.0) == "🟢"

    def test_yellow_40_to_70(self) -> None:
        assert _health_emoji(40.0) == "🟡"
        assert _health_emoji(70.0) == "🟡"  # boundary: > 70 → green, so 70 stays yellow

    def test_red_below_40(self) -> None:
        assert _health_emoji(39.9) == "🔴"
        assert _health_emoji(0.0) == "🔴"


class TestDiscordColor:
    def test_green(self) -> None:
        assert _discord_color(75.0) == 0x2ECC71

    def test_yellow(self) -> None:
        assert _discord_color(55.0) == 0xF39C12
        assert _discord_color(70.0) == 0xF39C12

    def test_red(self) -> None:
        assert _discord_color(39.0) == 0xE74C3C
        assert _discord_color(0.0) == 0xE74C3C


# ---------------------------------------------------------------------------
# SlackNotifier tests
# ---------------------------------------------------------------------------


class TestSlackNotifierFormatBlocks:
    def test_returns_dict_with_blocks(self, minimal_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(minimal_report)
        assert "blocks" in payload
        assert isinstance(payload["blocks"], list)
        assert len(payload["blocks"]) >= 2  # at least header + context

    def test_header_contains_grade(self, minimal_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(minimal_report)
        header = payload["blocks"][0]
        assert header["type"] == "header"
        header_text = header["text"]["text"]
        assert "Grade:" in header_text
        assert "B" in header_text  # score=75 → grade B

    def test_project_id_in_blocks(self, minimal_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(minimal_report)
        # Check the second block (summary/meta section)
        section = payload["blocks"][1]
        assert "proj_test" in section["text"]["text"]

    def test_overview_metrics_included(self, full_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(full_report)
        # Collect all text content
        all_text = json.dumps(payload)
        assert "12,000.00" in all_text  # MRR formatted
        assert "2.50%" in all_text      # churn rate

    def test_only_top_3_insights(self, full_report: HealthReport) -> None:
        """4 insights in the report, but only top 3 should appear."""
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(full_report)
        all_text = json.dumps(payload)
        # First 3 insight titles should appear
        assert "MRR Growing Steadily" in all_text
        assert "Churn Spike in Week 3" in all_text
        assert "Billing Failures Elevated" in all_text
        # 4th insight should NOT appear
        assert "Trial-to-Paid Stable" not in all_text

    def test_severity_emojis_present(self, full_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(full_report)
        # Use ensure_ascii=False so emoji characters survive JSON serialization intact
        all_text = json.dumps(payload, ensure_ascii=False)
        assert "🟢" in all_text  # positive insight
        assert "🟡" in all_text  # warning insight
        assert "🔴" in all_text  # critical insight severity

    def test_summary_included(self, full_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(full_report)
        all_text = json.dumps(payload)
        assert "Watch billing failures" in all_text

    def test_no_overview_skips_metrics_section(
        self, minimal_report: HealthReport
    ) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(minimal_report)
        all_text = json.dumps(payload)
        # These metric labels should not appear when there's no overview
        assert "MRR" not in all_text
        assert "Churn Rate" not in all_text

    def test_footer_has_generated_at(self, minimal_report: HealthReport) -> None:
        notifier = SlackNotifier("https://hooks.slack.com/test")
        payload = notifier._format_blocks(minimal_report)
        last_block = payload["blocks"][-1]
        assert last_block["type"] == "context"
        footer_text = last_block["elements"][0]["text"]
        assert "2024-02-01" in footer_text


class TestSlackNotifierSendReport:
    def test_returns_true_on_200(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp):
            notifier = SlackNotifier("https://hooks.slack.com/test")
            result = notifier.send_report(minimal_report)

        assert result is True

    def test_returns_false_on_non_200(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "invalid_payload"

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp):
            notifier = SlackNotifier("https://hooks.slack.com/test")
            result = notifier.send_report(minimal_report)

        assert result is False

    def test_returns_false_on_request_error(self, minimal_report: HealthReport) -> None:
        import httpx

        with patch(
            "rc_insights.notifications.httpx.post",
            side_effect=httpx.RequestError("network error"),
        ):
            notifier = SlackNotifier("https://hooks.slack.com/test")
            result = notifier.send_report(minimal_report)

        assert result is False

    def test_posts_to_correct_url(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        url = "https://hooks.slack.com/services/T000/B000/xxxx"

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp) as mock_post:
            notifier = SlackNotifier(url)
            notifier.send_report(minimal_report)

        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert call_url == url

    def test_payload_has_blocks_key(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp) as mock_post:
            notifier = SlackNotifier("https://hooks.slack.com/test")
            notifier.send_report(minimal_report)

        call_kwargs = mock_post.call_args[1]
        assert "json" in call_kwargs
        assert "blocks" in call_kwargs["json"]


# ---------------------------------------------------------------------------
# DiscordNotifier tests
# ---------------------------------------------------------------------------


class TestDiscordNotifierFormatEmbed:
    def test_returns_dict(self, minimal_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(minimal_report)
        assert isinstance(embed, dict)

    def test_title_present(self, minimal_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(minimal_report)
        assert "title" in embed
        assert "RC Insights" in embed["title"]

    def test_color_green_for_high_score(self) -> None:
        report = HealthReport(
            project_id="p",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            overall_health_score=85.0,
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(report)
        assert embed["color"] == 0x2ECC71

    def test_color_yellow_for_mid_score(self) -> None:
        report = HealthReport(
            project_id="p",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            overall_health_score=55.0,
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(report)
        assert embed["color"] == 0xF39C12

    def test_color_red_for_low_score(self) -> None:
        report = HealthReport(
            project_id="p",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            overall_health_score=20.0,
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(report)
        assert embed["color"] == 0xE74C3C

    def test_fields_include_health_score(self, minimal_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(minimal_report)
        names = [f["name"] for f in embed["fields"]]
        assert any("Health Score" in n for n in names)

    def test_metrics_fields_present(self, full_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(full_report)
        all_text = json.dumps(embed)
        assert "MRR" in all_text
        assert "Churn" in all_text
        assert "12,000.00" in all_text

    def test_insights_field_limited_to_3(self, full_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(full_report)
        all_text = json.dumps(embed)
        assert "MRR Growing Steadily" in all_text
        assert "Churn Spike in Week 3" in all_text
        assert "Billing Failures Elevated" in all_text
        assert "Trial-to-Paid Stable" not in all_text

    def test_description_from_summary(self, full_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(full_report)
        assert "description" in embed
        assert "Watch billing failures" in embed["description"]

    def test_no_description_when_no_summary(self, minimal_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(minimal_report)
        assert "description" not in embed

    def test_footer_has_period(self, full_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(full_report)
        assert "footer" in embed
        assert "2024-01-01" in embed["footer"]["text"]

    def test_timestamp_is_iso(self, minimal_report: HealthReport) -> None:
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
        embed = notifier._format_embed(minimal_report)
        assert "timestamp" in embed
        # Should parse back without error
        datetime.fromisoformat(embed["timestamp"])


class TestDiscordNotifierSendReport:
    def test_returns_true_on_204(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp):
            notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
            result = notifier.send_report(minimal_report)

        assert result is True

    def test_returns_false_on_non_204(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp):
            notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
            result = notifier.send_report(minimal_report)

        assert result is False

    def test_returns_false_on_request_error(self, minimal_report: HealthReport) -> None:
        import httpx

        with patch(
            "rc_insights.notifications.httpx.post",
            side_effect=httpx.RequestError("timeout"),
        ):
            notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
            result = notifier.send_report(minimal_report)

        assert result is False

    def test_posts_embeds_json(self, minimal_report: HealthReport) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("rc_insights.notifications.httpx.post", return_value=mock_resp) as mock_post:
            notifier = DiscordNotifier("https://discord.com/api/webhooks/test")
            notifier.send_report(minimal_report)

        call_kwargs = mock_post.call_args[1]
        assert "json" in call_kwargs
        assert "embeds" in call_kwargs["json"]
        assert len(call_kwargs["json"]["embeds"]) == 1
