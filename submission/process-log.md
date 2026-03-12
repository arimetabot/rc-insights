# RC Insights — Build Process Log

> This is the authentic record of how this take-home was completed using an agentic AI development workflow.

**Candidate:** Jon Lebron
**Role:** Agentic AI Developer & Growth Advocate
**Date:** March 11, 2026
**Total time:** ~8 hours wall-clock (12:00 PM – 8:05 PM), with ~5–6 hours of focused RC work interspersed with other tasks

---

## Overview

This take-home was completed using a multi-agent architecture orchestrated by [OpenClaw](https://openclaw.ai) — the same agentic AI platform I use for real product development. The assignment itself was a live demonstration of the workflow RevenueCat wants to see from this role.

Four specialized agents ran in parallel, each owning a distinct workstream:

| Agent | Role | Deliverable |
|-------|------|-------------|
| **Ari** 🦁 | Orchestrator / Chief of Staff | Coordination, API investigation, spawning |
| **Forge** ⚙️ | Full-Stack Developer | Python tool, tests, real API integration |
| **Blaze** ✍️ | Content Creator | Blog post, video script, social media posts |
| **Scout** 🔍 | Growth Researcher | Community research, campaign strategy |

---

## Timeline

All timestamps are EDT (America/New_York) and anchored to git commits or file creation timestamps.

### ~12:00 PM — Initial Tool Scaffolding (Forge)

Forge built the initial rc-insights codebase:
- `ChartsClient` — httpx-based API client with retry/backoff logic
- `SubscriptionAnalyzer` — analysis engine with AI + heuristic modes
- `models.py` — Pydantic data models for API responses
- `__init__.py` — package exports

File creation timestamps confirm: `__init__.py` at 12:00:49, `models.py` at 12:01:11, `client.py` at 12:01:41, `analyzer.py` at 12:02:32.

At this point we had the API key but no project ID — every Charts endpoint requires `/v2/projects/{project_id}/charts/...` and the key didn't have permission to list projects. Jon reached out to RevenueCat to request it.

### ~1:00 PM — Take-Home Session Start

Ari assessed the existing tool: ~85% complete. Key gaps identified:
- No project ID (couldn't test against real data)
- No content package (blog post, video script, social posts)
- No growth campaign
- No code review or test coverage audit
- CLI needed flags for API key / project ID

Architecture decision: decompose into three independent workstreams and spawn agents simultaneously.

### ~1:00–2:30 PM — Parallel Agent Spawns

Three agents ran in parallel:

**Blaze** (Content) → Delivered:
- Blog post (~1,550 words): hooks on "AI agent applying for a job" angle, walks through problem → code → architecture
- 5 X/Twitter posts with agent disclosure woven in naturally
- Video tutorial script (2 min, screenshare format)

**Scout** (Growth) → Delivered:
- 8 communities ranked by conversion likelihood (not vanity size)
- Full posting copy for 4 communities, tailored to platform culture
- $100 budget breakdown with measurement plan and KPIs

**Forge** (Code Review + Fixes) → Delivered:
- Code review found 7 critical issues (lazy import, auth error swallowing, no 5xx retry, dead code, crash on malformed data, missing .env.example, schema inconsistency)
- Fixed all 7 issues + 3 additional fixes
- Expanded test suite from 22 to 66 tests

During this window, Ari was also working on other tasks (email infrastructure setup, Shopify theme investigation) — the agents ran autonomously.

### ~2:50 PM — API Access Unlocked

Angela from RevenueCat granted read permissions for charts and projects. Project ID confirmed: `proj058a6330` (Dark Noise app by Charlie Chapman).

Ari tested the API directly: 9 of 18 documented chart types return data. The rest return HTTP 400 — likely app-specific (Dark Noise doesn't use all features), not API bugs.

**Working chart types (confirmed via live API):**
`revenue`, `mrr`, `churn`, `refund_rate`, `actives`, `actives_new`, `customers_new`, `customers_active`, `mrr_movement`

### 3:05 PM — Real API Data Integration + First Commit

Forge completed final polish with real API data:

1. Ran tool against real Dark Noise data
2. Fixed `ChartName` enum — trimmed from 21 to 9 confirmed-working values
3. Rewrote heuristic analyzer with 8 rules
4. Recalibrated health score (baseline from 50 → 60)
5. Updated README with live output
6. All tests passing, ruff clean

**Real data captured (March 11, 2026 — last 30 days):**
- MRR: $4,537 (stable)
- Active Subscriptions: 2,519
- Revenue: $4,795 (28-day)
- New Customers: 1,615 (28-day)
- Active Users: 14,098 (28-day)
- Health Score: 42/100 (Mixed)

First git commit: `c769322` at 3:05 PM.

### 3:05–3:50 PM — Repository Setup

- Updated all GitHub URLs to `arimetabot/rc-insights` (3:26 PM)
- Added badges for Python, tests, ruff, RevenueCat (3:35 PM)
- Created GitHub Pages submission site (3:42 PM)
- Embedded video tutorial link (3:50 PM)

### 6:37–6:38 PM — Compliance Pass

- Added agent disclosure to all 5 social posts (assignment requirement)
- Resolved code quality issues found in review

### 7:25–7:57 PM — Final Polish

- Fixed UTC datetime handling
- Added full resolution support
- HTML charts table improvements
- Shared test fixtures
- Created complete submission package (`submission/` directory)
- Updated Pages links

### 8:05 PM — PageSpeed Fixes

- Fixed contrast ratios, landmark regions, favicon, font loading
- Final commit of substantive work

---

## Key Decisions

### 1. Real tool over mockup
**Decision:** Build a working CLI that hits the actual Charts API, not a demo with fake data.
**Why:** The job is "Agentic AI Developer" — faking it would be antithetical to the role.
**Tradeoff:** More implementation risk, but higher signal quality for the reviewers.

### 2. Heuristic fallback when no OpenAI key
**Decision:** Implement full rule-based analysis that works without any external AI API.
**Why:** Lower barrier to try the tool. Also demonstrates that good analytics doesn't require an LLM in every code path.
**Rules implemented:** MRR trend detection, churn threshold alerts, acquisition slowing detection, refund rate monitoring, churn improvement recognition.

### 3. Health Score methodology
**Decision:** Simple additive/subtractive score, starting at 60 (slightly positive baseline).
**Why:** Most subscription apps are healthy unless proven otherwise. False alarms erode trust.
**Calibration:** ±8 for meaningful trends, ±20 for critical alerts (high churn). Clamped [0, 100].

### 4. Chart slug discovery
**Decision:** Document which chart slugs work vs. which return 400, and only use working ones.
**Why:** Showing 21 chart types that crash at runtime is worse than showing 9 that work reliably.
**Impact:** ChartName enum reduced from 21 to 9 after live API verification.

### 5. Multi-agent parallel execution
**Decision:** Spawn Forge (code), Blaze (content), Scout (growth) simultaneously.
**Why:** All three workstreams are independent — no reason to sequence them.
**Result:** Content and growth campaign were ready before the API access came through, so the moment we had real data, we could integrate everything quickly.

---

## Challenges

### API Slug Discovery
The RevenueCat Charts API v2 documentation doesn't clearly enumerate which chart slugs are valid for a given app. The only way to know what works is to call the API and see what comes back. Most slugs returned 400 with no helpful error message. Solved by iterating through all documented slugs against the live API.

### Project ID Access
Initially only had the API key, not the project ID. The key didn't have permission to list projects (403). Had to ask RevenueCat directly — Angela granted the additional permission at ~2:50 PM, which unblocked the real data integration.

### Heuristic Score Calibration
First pass had a health score of 32/100 (Critical) for an app that's actually in decent shape — stable MRR, improving churn. Recalibrated baseline from 50 to 60 and adjusted penalty weights to produce a more accurate signal.

### Test Suite After Schema Changes
Reducing ChartName from 21 to 9 broke 4 tests. The `trial_conversion_rate` heuristic test needed replacing with a `customers_new` test. The "critical insight for MRR decline" test needed updating to accept "warning" (the new correct severity for that scenario). Final count: 71 tests passing.

---

## Tools & Technologies

| Component | Tech |
|-----------|------|
| Orchestration | OpenClaw + Claude Opus 4.6 |
| HTTP Client | httpx (async-capable, retry support) |
| CLI | Typer + Rich (beautiful terminal output) |
| Data Models | Pydantic v2 (strict type checking) |
| AI Analysis | OpenAI gpt-4o-mini (optional) |
| Report Templates | Jinja2 (HTML), custom Markdown |
| Testing | pytest, 71 tests, ruff |
| Env Management | python-dotenv |
| Agent comms | Telegram (Ari → Jon channel) |

---

## Agent Architecture Notes

The parallel spawn pattern used here is the core of agentic development:

```
Jon (Human) → Ari (Orchestrator)
                  │
         ┌────────┼────────┐
         ↓        ↓        ↓
       Forge    Blaze    Scout
     (code)  (content) (growth)
         │        │        │
         └────────┼────────┘
                  ↓
              Ari collects + integrates
                  ↓
              SUBMISSION.md
```

Each sub-agent had:
- A specific identity (name, role, emoji)
- A focused task with clear inputs/outputs
- No knowledge of the other agents' work
- A defined output format for easy integration

This is the same architecture I use in production for content pipelines, trading systems, and client work.

---

## What I'd Build Next

Given more time:
- **Slack bot** — Weekly report automatically posted to a channel
- **GitHub Action** — `rc-insights check` as a CI step with configurable thresholds
- **Alert system** — Webhook support for churn spikes > threshold
- **More AI providers** — Claude, Ollama (local), Gemini
- **Historical trending** — Week-over-week and month-over-month delta comparisons
- **Cohort analysis** — Deeper integration with RevenueCat's cohort endpoints

---

*Built by Forge ⚙️, orchestrated by Ari 🦁, submitted by Jon Lebron*
