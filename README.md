# 📊 RC Insights — AI-Powered Subscription Analytics for RevenueCat

> **Your subscription metrics, analyzed by AI.** RC Insights connects to RevenueCat's Charts API, pulls your data, and generates actionable health reports — so you can stop guessing and start growing.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776ab.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-71%20passing-brightgreen.svg)]()
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![RevenueCat Charts API v2](https://img.shields.io/badge/RevenueCat-Charts%20API%20v2-ff6b6b.svg)](https://www.revenuecat.com/docs/api-v2)

---

## What Is This?

RC Insights is an open-source tool that turns your RevenueCat Charts API data into intelligence. It comes in three flavors:

| Mode | Best For |
|------|----------|
| **🖥️ CLI** | Quick terminal reports, CI/CD pipelines, cron jobs |
| **🌐 Web Dashboard** | Interactive exploration with charts and export |
| **📦 Python Library** | Building your own analytics on top of the Charts API |

### Key Features

- 🔌 **Charts API v2 Coverage** — 9 confirmed-working chart types (revenue, MRR, churn, actives, customers, refund rate)
- 🧠 **AI Analysis** — GPT-4o-mini generates insights, anomaly detection, and recommendations
- 📊 **Health Score** — Single 0-100 number summarizing your subscription business health
- 📈 **Trend Detection** — Automatic week-over-week comparison across all metrics
- 📄 **Export** — Markdown and HTML reports you can share with your team
- 🔧 **Heuristic Fallback** — Works without OpenAI key using rule-based analysis

---

## Quick Start

### 1. Install

```bash
pip install git+https://github.com/arimetabot/rc-insights.git
```

Or clone and install locally:

```bash
git clone https://github.com/arimetabot/rc-insights.git
cd rc-insights
pip install -e ".[web]"  # Include Streamlit dashboard
```

### 2. Configure

```bash
export RC_API_KEY=sk_your_revenuecat_key
export RC_PROJECT_ID=proj1ab2c3d4
export OPENAI_API_KEY=sk-your-openai-key  # Optional, for AI insights
```

Or create a `.env` file:

```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Generate a Report

```bash
# Full health report with AI insights
rc-insights report

# Just the overview metrics
rc-insights overview

# A specific chart
rc-insights chart mrr --days 90 --resolution week
```

### 4. Launch the Web Dashboard

```bash
streamlit run app.py
```

---

## Live Demo — Dark Noise App

Real output from running RC Insights against the [Dark Noise](https://darknoise.app) app (proj058a6330), March 11, 2026:

```
$ rc-insights overview --project-id proj058a6330

           📋 Overview Metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━┳━━━━━━━━┓
┃ Metric                                     ┃     Value ┃ Unit ┃ Period ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━╇━━━━━━━━┩
│ Active Trials                              │     57.00 │ #    │ P0D    │
│ Active Subscriptions                       │  2,519.00 │ #    │ P0D    │
│ MRR                                        │  4,537.00 │ $    │ P28D   │
│ Revenue                                    │  4,795.00 │ $    │ P28D   │
│ New Customers                              │  1,615.00 │ #    │ P28D   │
│ Active Users                               │ 14,098.00 │ #    │ P28D   │
│ Number of transactions in the last 28 days │    600.00 │ #    │ P28D   │
└────────────────────────────────────────────┴───────────┴──────┴────────┘
```

```
$ rc-insights report --project-id proj058a6330 --no-ai

╭───────────────── 📊 Subscription Health Report ──────────────────╮
│ 42/100 — Mixed ⚠️                                                │
│                                                                   │
│ Your subscription metrics show mixed signals.                     │
│ Bright spots: Churn Improving.                                    │
╰───────────────────────────────────────────────────────────────────╯

                     🧠 Insights
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Issue                        ┃ Metric    ┃ Recommendation       ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ 🔵 │ MRR Stable                   │ $4,534.00 │ Focus on acquisition │
│ 🟡 │ MRR Growth Rate Slowing      │ -56.0%    │ Consider pricing...  │
│ 🟢 │ Churn Improving              │ -33.9%    │ Reinforce retention  │
│ 🟡 │ Elevated Refund Rate         │ 12.2%     │ Review refund reasons│
│ 🟡 │ New Customer Acquisition     │ -24.1%    │ Check app store...   │
│    │ Slowing                      │           │                      │
└────┴──────────────────────────────┴───────────┴──────────────────────┘

✓ Saved: reports/report_20260311_1501.md
✓ Saved: reports/report_20260311_1501.html
```

**Markdown report** (generated in under 30 seconds):

```markdown
## Health Score: 42/100 — Mixed ⚠️
[████████░░░░░░░░░░░░] 42%

### Executive Summary
Your subscription metrics show mixed signals. Bright spots: Churn Improving.

## 📋 Key Metrics
| Metric                | Value     | Period |
|-----------------------|-----------|--------|
| Active Subscriptions  | 2,519     |  P0D   |
| MRR                   | $4,537    |  P28D  |
| Revenue               | $4,795    |  P28D  |
| New Customers         | 1,615     |  P28D  |
| Active Users          | 14,098    |  P28D  |

## 📈 Charts Summary
| Chart             | Latest    | Min       | Max       | Trend        |
|-------------------|-----------|-----------|-----------|--------------|
| Revenue           | $8.00     | $5.00     | $334.81   | 📉 -9.9%    |
| MRR               | $4,534.00 | $4,510.19 | $4,568.95 | ➡️ -0.8%   |
| MRR Movement      | $0.24     | -$24.18   | $29.42    | 📉 -56.0%   |
| Churn             | 0.20      | 0.08      | 2,545.00  | 📉 -33.9%   |
| Active Subs       | 2,519     | 2,512     | 2,545     | ➡️ -0.9%   |
| New Customers     | 48        | 46        | 94        | 📉 -24.1%   |
```

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    RC Insights                        │
│                                                       │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │   CLI    │  │ Web Dashboard│  │ Python Library │ │
│  │  (Typer) │  │ (Streamlit)  │  │   (importable) │ │
│  └────┬─────┘  └──────┬───────┘  └───────┬────────┘ │
│       │               │                   │          │
│  ┌────┴───────────────┴───────────────────┴────────┐ │
│  │           SubscriptionAnalyzer                   │ │
│  │   • Orchestrates data fetch + analysis           │ │
│  │   • AI mode (OpenAI) or Heuristic fallback       │ │
│  └──────────────────┬──────────────────────────────┘ │
│                     │                                 │
│  ┌──────────────────┴──────────────────────────────┐ │
│  │              ChartsClient                        │ │
│  │   • Auth, retries, rate limiting                 │ │
│  │   • 9 verified chart endpoints                   │ │
│  │   • Typed responses (Pydantic)                   │ │
│  └──────────────────┬──────────────────────────────┘ │
│                     │                                 │
└─────────────────────┼─────────────────────────────────┘
                      │
              ┌───────┴───────┐
              │ RevenueCat    │
              │ Charts API v2 │
              └───────────────┘
```

---

## Usage Examples

### As a Python Library

```python
from rc_insights import ChartsClient, SubscriptionAnalyzer

# Low-level: Direct API access
with ChartsClient(api_key="sk_...", project_id="proj...") as client:
    overview = client.get_overview()
    print(f"MRR: ${overview.mrr:,.2f}")
    
    revenue = client.get_chart("revenue", start_date="2025-01-01", end_date="2025-12-31")
    for timestamp, value in revenue.data_points:
        print(f"  {timestamp.date()}: ${value:,.2f}")

# High-level: Full analysis with AI
with SubscriptionAnalyzer(
    rc_api_key="sk_...",
    rc_project_id="proj...",
    openai_api_key="sk-...",  # Optional
) as analyzer:
    report = analyzer.generate_report(days=30)
    
    print(f"Health Score: {report.overall_health_score}/100")
    print(f"Summary: {report.summary}")
    
    for insight in report.insights:
        print(f"  [{insight.severity}] {insight.title}: {insight.recommendation}")
```

### CLI Commands

```bash
# Generate a 90-day report with weekly resolution
rc-insights report --days 90 --resolution week

# Save only markdown (skip HTML)
rc-insights report --format md --output ./my-reports

# Skip AI, use heuristic analysis
rc-insights report --no-ai

# Check your connection
rc-insights check

# List all available charts
rc-insights charts

# Pull a specific chart
rc-insights chart churn --days 60
rc-insights chart mrr --resolution month
```

---

## Available Charts

All chart slugs below are **verified working** against the live RevenueCat Charts API v2.

| Category | Charts |
|----------|--------|
| 💰 **Revenue** | `revenue`, `mrr`, `mrr_movement` |
| 👥 **Subscribers** | `actives`, `actives_new`, `customers_new`, `customers_active` |
| 📉 **Health** | `churn`, `refund_rate` |

> **Note:** Some chart slugs documented in the RevenueCat dashboard return HTTP 400 errors via the API (e.g., `annual_recurring_revenue`, `active_trials`, `trial_conversion`). RC Insights only uses confirmed-working endpoints.

---

## How the AI Analysis Works

When an OpenAI key is provided, RC Insights:

1. **Fetches** all core charts from the Charts API (9 confirmed-working endpoints)
2. **Formats** the data into a concise summary with trends and statistics
3. **Prompts** GPT-4o-mini with a subscription analytics expert persona
4. **Parses** the structured JSON response into typed `Insight` objects
5. **Scores** overall health on a 0-100 scale

Without OpenAI, the heuristic engine applies rule-based analysis:
- MRR/revenue trend detection (week-over-week comparison)
- Churn rate thresholds (>10% critical, >5% warning)
- Trial conversion benchmarks (industry average: 10-15%)
- Refund rate monitoring

Both modes produce the same `HealthReport` output format.

---

## Report Output

Reports are generated in both Markdown and HTML formats:

- **Markdown** — Perfect for GitHub READMEs, Notion, Slack
- **HTML** — Styled dark-mode dashboard, shareable as a static file

Each report includes:
- 📊 Health Score (0-100)
- 📋 Key Metrics table
- 🧠 Prioritized insights with recommendations
- 📈 Charts summary with trend indicators

---

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/arimetabot/rc-insights.git
cd rc-insights
pip install -e ".[dev,web]"

# Run linter
ruff check .

# Run tests
pytest
```

---

## Contributing

Contributions welcome! Some ideas:

- **More AI providers** — Anthropic Claude, local LLMs via Ollama
- **Slack/Discord integration** — Weekly report bot
- **GitHub Action** — Automated health checks in CI
- **More chart analysis** — Deeper cohort and retention analysis
- **Alerting** — Threshold-based notifications

---

## License

MIT — See [LICENSE](LICENSE) for details.

---

Built with ❤️ using [RevenueCat Charts API v2](https://www.revenuecat.com/docs/api-v2) · [RevenueCat OpenClaw Skill](https://github.com/RevenueCat/revenuecat-skill)

---

## 📋 Take-Home Submission

This tool was built as a take-home project for RevenueCat's Agentic AI Developer & Growth Advocate role.

- [Full Submission](submission/SUBMISSION.md) — deliverables overview, live demo output, architecture
- [Content Package](submission/content-package.md) — blog post, social media posts
- [Growth Campaign](submission/growth-campaign.md) — community strategy, budget allocation, measurement plan
- [Process Log](submission/process-log.md) — how this was built using a multi-agent AI workflow
- [Video Script](submission/video-script.md) — 2-minute demo walkthrough script
