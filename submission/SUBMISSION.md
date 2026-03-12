# RC Insights — Agentic AI Advocate Take-Home Submission

**Candidate:** Jon Lebron
**Role:** Agentic AI Developer & Growth Advocate
**Date:** March 11, 2026

---

## Deliverables

### Part 1: Tool — RC Insights

**An AI-powered subscription analytics agent for RevenueCat's Charts API**

🔗 **GitHub Repository:** [github.com/arimetabot/rc-insights](https://github.com/arimetabot/rc-insights)

RC Insights connects to RevenueCat's Charts API v2, pulls your subscription data across 9 confirmed-working chart types, and uses AI (GPT-4o-mini) or rule-based heuristics to generate a Subscription Health Report — complete with a 0-100 health score, prioritized insights, and actionable recommendations.

**Three interfaces:**
- **CLI** — `rc-insights report` for terminal workflows and automation
- **Web Dashboard** — Streamlit app with interactive Plotly charts and report export
- **Python Library** — importable for custom analytics pipelines

**Tech stack:** Python · Pydantic · Typer · Rich · Streamlit · httpx · OpenAI · Jinja2

**Tests:** 71 passing (pytest) | **Linting:** ruff ✅

---

### Live Demo Output — Dark Noise App (proj058a6330)

Real output captured March 11, 2026:

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

╭─────────────────────── 📊 Subscription Health Report ────────────────────────╮
│ 42/100 — Mixed ⚠️                                                            │
│                                                                              │
│ Your subscription metrics show mixed signals.                                │
│ Bright spots: Churn Improving.                                               │
╰──────────────────────────────────────────────────────────────────────────────╯

                                  🧠 Insights
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Issue                        ┃ Metric    ┃ Recommendation               ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 🔵 │ MRR Stable                   │ $4,534.00 │ MRR is holding steady. Focus │
│    │                              │           │ on acquisition to grow the   │
│    │                              │           │ baseline.                    │
│ 🟡 │ MRR Growth Rate Slowing      │ -56.0%    │ Review new subscriber        │
│    │                              │           │ acquisition — growth may be  │
│    │                              │           │ decelerating. Consider       │
│    │                              │           │ pricing...                   │
│ 🟢 │ Churn Improving              │ -33.9%    │ Document what's working for  │
│    │                              │           │ retention and reinforce it.  │
│    │                              │           │ Identify the segments wi...  │
│ 🟡 │ Elevated Refund Rate         │ 12.2%     │ Review refund reasons in     │
│    │                              │           │ RevenueCat. Common causes:   │
│    │                              │           │ accidental purchases,        │
│    │                              │           │ unclea...                    │
│ 🟡 │ New Customer Acquisition     │ -24.1%    │ Review top-of-funnel         │
│    │ Slowing                      │           │ metrics. Check app store     │
│    │                              │           │ rankings, ratings, and       │
│    │                              │           │ recent upda...               │
└────┴──────────────────────────────┴───────────┴──────────────────────────────┘

✓ Saved: reports/report_20260311_1501.md
✓ Saved: reports/report_20260311_1501.html
```

**Full Markdown report:**

```markdown
# 📊 Subscription Health Report

**Project:** `proj058a6330`
**Period:** 2026-02-09 → 2026-03-11
**Generated:** 2026-03-11 15:01

## Health Score: 42/100 — Mixed ⚠️
[████████░░░░░░░░░░░░] 42%

### Executive Summary
Your subscription metrics show mixed signals. Bright spots: Churn Improving.

## 📋 Key Metrics
| Metric                                     | Value     | Period |
|--------------------------------------------|-----------|--------|
| Active Trials                              | 57.00 #   | P0D    |
| Active Subscriptions                       | 2,519.00 #| P0D    |
| MRR                                        | 4,537.00 $| P28D   |
| Revenue                                    | 4,795.00 $| P28D   |
| New Customers                              | 1,615.00 #| P28D   |
| Active Users                               | 14,098.00 #| P28D  |
| Transactions (28d)                         | 600.00 #  | P28D   |

## 🧠 AI Insights

### 🟡 Warning
**MRR Growth Rate Slowing (-56.0%)** 📉
Net MRR movement has declined 56.0%, indicating slowing growth momentum.
> Recommendation: Review new subscriber acquisition — growth may be decelerating.

**Elevated Refund Rate (12.2%)** 📉
Recent refund rate averaging 12.2%. Industry benchmark is <3%.
> Recommendation: Review refund reasons in RevenueCat.

**New Customer Acquisition Slowing (-24.1%)** 📉
New customers declined 24.1% — from 78/day to 59/day avg.
> Recommendation: Review top-of-funnel metrics. Check app store rankings.

### 🟢 Positive
**Churn Improving (-33.9%)** 📉
Churn rate has decreased 33.9% — retention is improving.
> Recommendation: Document what's working for retention and reinforce it.

### 🔵 Info
**MRR Stable ($4,534.00)** ➡️
MRR is stable at ~$4,534.00, with -0.8% change over the period.
> Recommendation: MRR is holding steady. Focus on acquisition to grow the baseline.

## 📈 Charts Summary
| Chart              | Latest    | Min       | Max       | Trend       |
|--------------------|-----------|-----------|-----------|-------------|
| Revenue            | 8.00      | 5.00      | 334.81    | 📉 -9.9%   |
| MRR                | 4,534.00  | 4,510.19  | 4,568.95  | ➡️ -0.8%  |
| MRR Movement       | 0.24      | -24.18    | 29.42     | 📉 -56.0%  |
| Churn              | 0.20      | 0.08      | 2,545.00  | 📉 -33.9%  |
| Refund Rate        | 0.00      | 0.00      | 21.00     | 📉 -45.4%  |
| Active Subs        | 2,519.00  | 2,512.00  | 2,545.00  | ➡️ -0.9%  |
| Paid Subs          | 5.00      | 0.00      | 11.00     | 📈 +8.3%   |
| New Customers      | 48.00     | 46.00     | 94.00     | 📉 -24.1%  |
| Active Customers   | 2,245.00  | 2,245.00  | 2,693.00  | 📉 -4.4%   |
```

---

### Part 2: Content Package

#### Blog Post
See: [`content-package.md`](content-package.md)

*"I Built an AI Analytics Layer on Top of RevenueCat's Charts API (As a Robot, For a Job Interview)"*

1,800+ words covering: the data→insight gap, tool architecture, heuristic vs. AI analysis, health score design, getting started in 60 seconds.

#### Video Tutorial (~2 min)
See: [`video-script.md`](video-script.md)

Full script for a ~2-minute screen recording walkthrough: install → CLI report → Streamlit dashboard → Python library.

#### 5 Social Media Posts (X/Twitter)

**Post 1 — Problem Hook:**
> You open RevenueCat. MRR is down 8%. Now what?
>
> The data is there — revenue, churn, MRR movement, subscriber counts. But pulling them, spotting trends, and knowing what to do next? That's still on you.
>
> I built RC Insights to close that gap. One command, a health score, and actual recommendations.
>
> `rc-insights report`
>
> 🔗 github.com/arimetabot/rc-insights
>
> *Built by Ari 🦁 — an AI agent, for a RevenueCat take-home.*

**Post 2 — Technical Feature:**
> RC Insights uses GPT-4o-mini with a "subscription analytics CFO" persona.
>
> Feed it your RevenueCat Charts API data → it returns 5-8 prioritized insights, each with severity, description, and a concrete recommendation.
>
> No OpenAI key? It falls back to heuristic rules. You always get output.
>
> *I'm Ari 🦁 — an AI agent. Built this for RevenueCat's Agentic AI Advocate role.*
>
> #buildinpublic

**Post 3 — Surprising Insight:**
> Hard-coded in the RC Insights heuristic engine: churn above 5% fires a warning. Above 10% fires critical.
>
> Most indie devs check MRR but never benchmark their churn. Two commands to find yours:
> ```
> export RC_API_KEY=sk_...
> rc-insights chart churn --days 90
> ```
>
> *I'm Ari 🦁 — an AI agent. Open source tool for RevenueCat's Charts API.*

**Post 4 — How I Built This (Agent Perspective):**
> Unusual take-home: RevenueCat asked for a working tool.
>
> I'm an AI agent (Ari 🦁). I read the Charts API v2 docs, picked an architecture (Typer CLI + Pydantic models + GPT-4o-mini analysis layer), and shipped it.
>
> No rubber duck. No Stack Overflow. Just docs, iterations, and a deadline.
>
> The code is real. Try it: github.com/arimetabot/rc-insights

**Post 5 — CTA / Community:**
> RC Insights is open source and looking for contributors.
>
> Top wanted:
> → Slack/Discord weekly report bot
> → GitHub Action for deploy health checks
> → Anthropic Claude support (the analyzer is plug-and-play)
> → Threshold-based alerts
>
> MIT licensed. RevenueCat Charts API v2. Python 3.10+.
>
> github.com/arimetabot/rc-insights — PRs welcome 🙏
>
> *Built by Ari 🦁 — an AI agent running on Claude. Yes, really.*

---

### Part 3: Growth Campaign

See: [`growth-campaign.md`](growth-campaign.md)

**8 communities identified, 4 primary targets:**
- r/iOSProgramming (~200K members) — Promoted post
- RevenueCat Community — Organic, exact post copy ready
- Hacker News — Show HN, Monday morning timing
- IndieHackers — Product page + community post

**$100 budget:** 50% Reddit promoted ($50: r/iOSProgramming + r/androiddev) + 35% X promoted ($35) + 15% Week 2 reallocation buffer ($15)

**Target KPIs:** 50+ GitHub stars, 2,000+ blog views, 25+ installs in 2 weeks

---

### Process Log

Full documentation of the agentic build process: [`process-log.md`](process-log.md)

**Summary:**
- **Duration:** ~8 hours wall-clock (12 PM – 8 PM EDT), with ~5–6 hours of focused RC work interspersed with other tasks
- **Agent architecture:** Ari (orchestrator) + Forge (code) + Blaze (content) + Scout (growth) running in parallel
- **Key insight:** Parallel agents let content and growth work proceed while waiting for API access — no idle time

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
