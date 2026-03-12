"""RC Insights — Email Report Delivery via Resend.

Send health reports and alerts via email. Supports single sends
and automated drip sequences for onboarding new users.

Requires: pip install rc-insights[email]
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from datetime import datetime

import httpx

from rc_insights.models import HealthReport

RESEND_API = "https://api.resend.com"


@dataclass
class EmailConfig:
    """Email delivery configuration."""

    api_key: str
    from_address: str = "RC Insights <reports@rc-insights.dev>"
    reply_to: str | None = None


@dataclass
class EmailResult:
    """Result of an email send attempt."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class EmailSender:
    """Send health reports and alerts via Resend."""

    def __init__(self, config: EmailConfig | None = None):
        if config is None:
            api_key = os.getenv("RESEND_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "Set RESEND_API_KEY env var or pass EmailConfig(api_key=...)"
                )
            config = EmailConfig(api_key=api_key)
        self.config = config
        self._client = httpx.Client(
            base_url=RESEND_API,
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=30.0,
        )

    def send_report(self, to: str | list[str], report: HealthReport) -> EmailResult:
        """Send a formatted health report email."""
        if isinstance(to, str):
            to = [to]

        subject = f"📊 RC Insights — Health Score: {report.overall_health_score:.0f}/100"
        body_html = self._format_report_html(report)

        return self._send(to=to, subject=subject, html=body_html)

    def send_alert(
        self,
        to: str | list[str],
        alert_title: str,
        alert_body: str,
        severity: str = "warning",
    ) -> EmailResult:
        """Send a threshold alert email."""
        if isinstance(to, str):
            to = [to]

        emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚠️")
        subject = f"{emoji} RC Insights Alert — {alert_title}"
        body_html = self._format_alert_html(alert_title, alert_body, severity)

        return self._send(to=to, subject=subject, html=body_html)

    def send_welcome_sequence(self, to: str, project_name: str = "your app") -> list[EmailResult]:
        """Send the 3-email onboarding welcome sequence immediately.

        In production, these would be spaced over 7 days via a job queue.
        For the demo, all 3 are sent together to show the content.
        """
        results = []
        for email_fn in (
            self._welcome_email_1, self._welcome_email_2, self._welcome_email_3
        ):
            subject, body = email_fn(project_name)
            result = self._send(to=[to], subject=subject, html=body)
            results.append(result)
        return results

    def _send(self, to: list[str], subject: str, html: str) -> EmailResult:
        """Send an email via Resend API."""
        payload: dict = {
            "from": self.config.from_address,
            "to": to,
            "subject": subject,
            "html": html,
        }
        if self.config.reply_to:
            payload["reply_to"] = self.config.reply_to

        try:
            resp = self._client.post("/emails", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return EmailResult(success=True, message_id=data.get("id"))
            return EmailResult(success=False, error=f"HTTP {resp.status_code}: {resp.text}")
        except httpx.HTTPError as e:
            return EmailResult(success=False, error=str(e))

    def _format_report_html(self, report: HealthReport) -> str:
        """Format a health report as a styled HTML email."""
        score = report.overall_health_score
        if score >= 70:
            color, grade = "#22c55e", "Healthy ✅"
        elif score >= 40:
            color, grade = "#eab308", "Mixed ⚠️"
        else:
            color, grade = "#ef4444", "Critical 🚨"

        insights_html = ""
        severity_colors = {
            "critical": "#ef4444",
            "warning": "#eab308",
            "positive": "#22c55e",
            "info": "#6366f1",
        }
        for insight in (report.insights or [])[:5]:
            ic = severity_colors.get(insight.severity, "#6366f1")
            insights_html += f"""
            <tr>
              <td style="padding: 8px 12px; border-left: 3px solid {ic};">
                <strong>{html.escape(insight.title)}</strong><br>
                <span style="color: #666; font-size: 14px;">{html.escape(insight.description)}</span><br>
                <span style="color: #444; font-size: 13px;">💡 {html.escape(insight.recommendation)}</span>
              </td>
            </tr>
            """

        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h1 style="font-size: 20px; color: #111;">📊 Subscription Health Report</h1>

          <div style="text-align: center; padding: 24px; background: #f9fafb; border-radius: 12px; margin: 16px 0;">
            <div style="font-size: 48px; font-weight: 700; color: {color};">{score:.0f}</div>
            <div style="font-size: 16px; color: {color}; font-weight: 600;">{grade}</div>
          </div>

          <p style="color: #374151; line-height: 1.6;">{html.escape(report.summary)}</p>

          <h2 style="font-size: 16px; color: #111; margin-top: 24px;">Key Insights</h2>
          <table style="width: 100%; border-collapse: collapse;">
            {insights_html}
          </table>

          <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
          <p style="color: #9ca3af; font-size: 12px;">
            Generated by <a href="https://github.com/arimetabot/rc-insights" style="color: #6366f1;">RC Insights</a>
            on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
          </p>
        </div>
        """

    def _format_alert_html(self, title: str, body: str, severity: str) -> str:
        """Format an alert as a styled HTML email."""
        colors = {"critical": "#ef4444", "warning": "#eab308", "info": "#6366f1"}
        color = colors.get(severity, "#eab308")

        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <div style="border-left: 4px solid {color}; padding: 16px; background: #f9fafb; border-radius: 0 8px 8px 0;">
            <h2 style="font-size: 18px; color: #111; margin: 0 0 8px 0;">⚠️ {html.escape(title)}</h2>
            <p style="color: #374151; line-height: 1.6; margin: 0;">{html.escape(body)}</p>
          </div>

          <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
          <p style="color: #9ca3af; font-size: 12px;">
            Alert from <a href="https://github.com/arimetabot/rc-insights" style="color: #6366f1;">RC Insights</a>
          </p>
        </div>
        """

    def _welcome_email_1(self, project_name: str) -> tuple[str, str]:
        """Email 1: Welcome + Quick Start (Day 0)."""
        subject = "🚀 RC Insights is ready — run your first health check"
        body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h1 style="font-size: 20px; color: #111;">Welcome to RC Insights 👋</h1>

          <p style="color: #374151; line-height: 1.6;">
            You're set up and connected to <strong>{html.escape(project_name)}</strong>.
            Here's how to get your first subscription health report in 60 seconds:
          </p>

          <div style="background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 8px; font-family: monospace; font-size: 14px; margin: 16px 0;">
            <span style="color: #89b4fa;">$</span> rc-insights report --days 30<br><br>
            <span style="color: #a6e3a1;">📊 Health Score: 72/100 — Mixed ⚠️</span><br>
            <span style="color: #f9e2af;">⚠️ Trial conversion dropped 12% this week</span><br>
            <span style="color: #89b4fa;">💡 Consider A/B testing your paywall timing</span>
          </div>

          <p style="color: #374151; line-height: 1.6;">
            <strong>What you'll see:</strong>
          </p>
          <ul style="color: #374151; line-height: 1.8;">
            <li>A 0-100 health score with trend analysis</li>
            <li>AI-generated insights ranked by impact</li>
            <li>Actionable recommendations for each issue</li>
            <li>HTML + Markdown reports saved locally</li>
          </ul>

          <p style="color: #374151; line-height: 1.6;">
            Want a visual dashboard? Run <code style="background: #f3f4f6; padding: 2px 6px; border-radius: 4px;">streamlit run app.py</code>
          </p>

          <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
          <p style="color: #9ca3af; font-size: 12px;">
            <a href="https://github.com/arimetabot/rc-insights" style="color: #6366f1;">GitHub</a> ·
            <a href="https://github.com/arimetabot/rc-insights#readme" style="color: #6366f1;">Docs</a>
          </p>
        </div>
        """
        return subject, body

    def _welcome_email_2(self, project_name: str) -> tuple[str, str]:
        """Email 2: Power Features (Day 3)."""
        subject = "💡 3 things most RC Insights users miss"
        body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h1 style="font-size: 20px; color: #111;">Getting more from {html.escape(project_name)}'s data</h1>

          <p style="color: #374151; line-height: 1.6;">
            Now that you've run your first report, here are three features that make
            RC Insights dramatically more useful:
          </p>

          <h3 style="color: #111;">1. Use any LLM — not just OpenAI</h3>
          <p style="color: #374151; line-height: 1.6;">
            RC Insights supports 100+ LLM providers. Run locally with Ollama (free, private),
            or use Claude, Groq, Mistral — whatever you prefer:
          </p>
          <div style="background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 13px; margin: 12px 0;">
            <span style="color: #89b4fa;">$</span> rc-insights report --model ollama/llama3<br>
            <span style="color: #89b4fa;">$</span> rc-insights report --model claude-sonnet-4-5
          </div>

          <h3 style="color: #111;">2. Set up threshold alerts</h3>
          <p style="color: #374151; line-height: 1.6;">
            Define your own alert rules in YAML. Get notified when metrics cross your thresholds:
          </p>
          <div style="background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 13px; margin: 12px 0;">
            <span style="color: #89b4fa;">$</span> rc-insights alerts --config alerts.yml
          </div>

          <h3 style="color: #111;">3. Automate with GitHub Actions</h3>
          <p style="color: #374151; line-height: 1.6;">
            Run a weekly health check automatically. We have a ready-made workflow —
            just add your RC_API_KEY as a GitHub secret.
          </p>

          <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
          <p style="color: #9ca3af; font-size: 12px;">
            <a href="https://github.com/arimetabot/rc-insights" style="color: #6366f1;">GitHub</a> ·
            Run <code>rc-insights models</code> to see all supported providers
          </p>
        </div>
        """
        return subject, body

    def _welcome_email_3(self, project_name: str) -> tuple[str, str]:
        """Email 3: Community + Contributing (Day 7)."""
        subject = "🤝 Join the RC Insights community"
        body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h1 style="font-size: 20px; color: #111;">You've been using RC Insights for a week 🎉</h1>

          <p style="color: #374151; line-height: 1.6;">
            By now you've probably run a few reports on {html.escape(project_name)}.
            Here's what's coming next — and how you can help shape it:
          </p>

          <h3 style="color: #111;">What we're building</h3>
          <ul style="color: #374151; line-height: 1.8;">
            <li><strong>Cohort retention analysis</strong> — track how signup cohorts retain over time</li>
            <li><strong>Slack/Discord integration</strong> — weekly reports delivered to your team channel</li>
            <li><strong>RevenueCat webhooks</strong> — real-time alerts on purchases, cancellations, billing issues</li>
          </ul>

          <h3 style="color: #111;">Contribute</h3>
          <p style="color: #374151; line-height: 1.6;">
            RC Insights is MIT licensed and open to contributions. If you've built something cool
            with the tool or have ideas for new features,
            <a href="https://github.com/arimetabot/rc-insights/issues" style="color: #6366f1;">open an issue</a>
            or submit a PR.
          </p>

          <div style="text-align: center; margin: 24px 0;">
            <a href="https://github.com/arimetabot/rc-insights" style="display: inline-block; background: #6366f1; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
              ⭐ Star on GitHub
            </a>
          </div>

          <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
          <p style="color: #9ca3af; font-size: 12px;">
            Thanks for using RC Insights. If it saved you time, tell a friend. 🙏
          </p>
        </div>
        """
        return subject, body

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
