"""Tests for the email notification module."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from rc_insights.emails import EmailConfig, EmailSender
from rc_insights.models import HealthReport, Insight


def _make_report(score: float = 72.0) -> HealthReport:
    """Create a test health report."""
    return HealthReport(
        project_id="proj_test",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 3, 1),
        overall_health_score=score,
        summary="MRR is stable but trial conversion needs attention.",
        insights=[
            Insight(
                title="Trial Conversion Declining",
                description="Trial-to-paid conversion dropped 12% week-over-week.",
                recommendation="A/B test paywall timing — try showing at day 3 instead of day 7.",
                severity="warning",
                category="trials",
                metric_value="38%",
                trend="down",
            ),
            Insight(
                title="MRR Growth Steady",
                description="Monthly recurring revenue grew 3.2% this period.",
                recommendation="Current trajectory is healthy — maintain acquisition efforts.",
                severity="positive",
                category="revenue",
                metric_value="$4,537",
                trend="up",
            ),
        ],
        overview=None,
    )


class TestEmailConfig:
    def test_config_defaults(self) -> None:
        config = EmailConfig(api_key="re_test_123")
        assert config.api_key == "re_test_123"
        assert "rc-insights" in config.from_address.lower() or "RC Insights" in config.from_address
        assert config.reply_to is None

    def test_config_custom(self) -> None:
        config = EmailConfig(
            api_key="re_test_123",
            from_address="Custom <custom@example.com>",
            reply_to="reply@example.com",
        )
        assert config.from_address == "Custom <custom@example.com>"
        assert config.reply_to == "reply@example.com"


class TestEmailSender:
    def test_init_with_config(self) -> None:
        config = EmailConfig(api_key="re_test_123")
        sender = EmailSender(config=config)
        assert sender.config.api_key == "re_test_123"
        sender.close()

    def test_init_from_env(self) -> None:
        with patch.dict("os.environ", {"RESEND_API_KEY": "re_env_key"}):
            sender = EmailSender()
            assert sender.config.api_key == "re_env_key"
            sender.close()

    def test_init_no_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="RESEND_API_KEY"):
                EmailSender()

    @patch("httpx.Client.post")
    def test_send_report_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "msg_test_123"},
        )

        config = EmailConfig(api_key="re_test")
        sender = EmailSender(config=config)
        result = sender.send_report("user@example.com", _make_report())

        assert result.success is True
        assert result.message_id == "msg_test_123"

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["to"] == ["user@example.com"]
        assert "72" in payload["subject"]
        sender.close()

    @patch("httpx.Client.post")
    def test_send_report_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=422,
            text="Validation error",
        )

        config = EmailConfig(api_key="re_test")
        sender = EmailSender(config=config)
        result = sender.send_report("bad@", _make_report())

        assert result.success is False
        assert "422" in (result.error or "")
        sender.close()

    @patch("httpx.Client.post")
    def test_send_alert(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "msg_alert_1"},
        )

        config = EmailConfig(api_key="re_test")
        sender = EmailSender(config=config)
        result = sender.send_alert(
            to="ops@example.com",
            alert_title="Churn spike detected",
            alert_body="Churn rate exceeded 8% threshold.",
            severity="critical",
        )

        assert result.success is True
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "🔴" in payload["subject"]
        sender.close()

    @patch("httpx.Client.post")
    def test_welcome_sequence_sends_3_emails(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "msg_seq"},
        )

        config = EmailConfig(api_key="re_test")
        sender = EmailSender(config=config)
        results = sender.send_welcome_sequence("new@example.com", "Dark Noise")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_post.call_count == 3
        sender.close()

    def test_context_manager(self) -> None:
        config = EmailConfig(api_key="re_test")
        with EmailSender(config=config) as sender:
            assert sender.config.api_key == "re_test"

    @patch("httpx.Client.post")
    def test_report_html_escapes_content(self, mock_post: MagicMock) -> None:
        """Verify that report content is HTML-escaped to prevent XSS."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "msg_xss"},
        )

        report = _make_report()
        report.summary = '<script>alert("xss")</script>'

        config = EmailConfig(api_key="re_test")
        sender = EmailSender(config=config)
        sender.send_report("user@example.com", report)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "<script>" not in payload["html"]
        assert "&lt;script&gt;" in payload["html"]
        sender.close()
