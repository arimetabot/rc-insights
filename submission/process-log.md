# RC Insights — Build Process Log

> This is the authentic record of how this take-home was completed using an agentic AI development workflow.

**Candidate:** Jon Lebron
**Role:** Agentic AI Developer & Growth Advocate
**Date:** March 11, 2026
**Total time:** ~3 hours

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

### ~1:00 PM — Assignment Intake
- Ari received the take-home prompt via Telegram
- Parsed the three deliverables: CLI tool, content package, growth campaign
- Made key architecture decision: build a real Python tool (not a mockup) that hits the actual Charts API

### ~1:10 PM — API Investigation
- Discovered RC Charts API v2 base URL: `https://api.revenuecat.com/v2/projects/{project_id}/charts`
- Challenge: didn't have a project ID yet, only the API key
- Ari made direct API calls to test which chart endpoints would respond
- Found that many chart slugs documented in the dashboard return HTTP 400 via the API

### ~1:20 PM — Architecture Decision: Parallel Spawn

Ari decomposed the work into three independent streams and spawned agents simultaneously:
- **Forge** → Build the Python CLI tool
- **Blaze** → Write the blog post and social content
- **Scout** → Research communities and build the campaign

This mirrors how a real agentic workflow handles complex, multi-part tasks — no waiting for one to finish before starting another.

### ~1:30 PM — Tool Development (Forge)

Forge built the initial rc-insights tool:
- `ChartsClient` — httpx-based API client with retry/backoff logic
- `SubscriptionAnalyzer` — analysis engine with AI + heuristic modes
- `HealthReport` + Pydantic models — typed output
- CLI (Typer + Rich) — `report`, `overview`, `chart`, `check`, `charts` commands
- HTML report template (dark mode, Jinja2)
- Test suite (pytest, 71 tests)

### ~1:45 PM — API Discovery Challenge

Initial run against the live API revealed a mismatch between documented slugs and working endpoints. Many chart names that appear in the RevenueCat dashboard return HTTP 400 via the Charts API.

**Working slugs (confirmed via live API):**
`revenue`, `mrr`, `churn`, `refund_rate`, `actives`, `actives_new`, `customers_new`, `customers_active`, `mrr_movement`

**Non-working slugs (HTTP 400):**
`annual_recurring_revenue`, `active_subscriptions`, `active_trials`, `new_customers`, `new_subscriptions`, `trial_conversion`, `realized_ltv_per_customer`, `initial_conversion`, `active_subscriptions_movement`

**Decision:** Only use confirmed-working endpoints. Remove non-working slugs from `ChartName` enum and `get_all_core_charts()`. Update README to document this behavior. Better to be accurate than to show impressive (but misleading) feature breadth.

### ~2:00 PM — Real API Data Integration (Forge)

With the confirmed project ID (`proj058a6330` — Dark Noise app by Charlie Chapman), Forge:
1. Created `.env` with real credentials
2. Fixed `ChartName` enum to 9 confirmed-working values
3. Added `--api-key` / `--project-id` CLI flags for flexibility
4. Enhanced heuristic analyzer with more meaningful rules
5. Ran tool against real API — got actual Dark Noise metrics

**Real data captured (March 11, 2026 — last 30 days):**
- MRR: $4,537 (stable)
- Active Subscriptions: 2,519
- Revenue: $4,795 (28-day)
- New Customers: 1,615 (28-day)
- Active Users: 14,098 (28-day)
- Health Score: 42/100 (Mixed)

### ~2:30 PM — Content Complete (Blaze)

Blaze delivered:
- 1,800+ word blog post (FK score ~8.5, technical but accessible)
- 5 social media posts (hook-first, concrete examples, CTA)
- Video tutorial script (2 min, screenshare format)

### ~2:45 PM — Growth Campaign Complete (Scout)

Scout identified 8 communities with post copy, exact account handles, timing, and budget allocation:
- RevenueCat Community, r/iOSProgramming (~200K members), HN Show HN, r/androiddev, IndieHackers, X/Twitter, Dev.to, Product Hunt
- $100 budget breakdown: 50% Reddit promoted ($50: r/iOSProgramming + r/androiddev), 35% X promoted ($35), 15% Week 2 reallocation buffer ($15)

### ~3:00 PM — Final Polish (Forge)

- Updated README with real CLI output from Dark Noise
- Fixed all 4 test failures (caused by ChartName enum reduction + baseline score change)
- Ruff clean (0 warnings)
- Created .env.example and verified .gitignore
- Prepared git commit

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
**Result:** 3-hour total wall clock time for a task that could take days linearly.

---

## Challenges

### API Slug Discovery
The RevenueCat Charts API v2 documentation doesn't clearly enumerate which chart slugs are valid. The only way to know what works is to call the API and see what comes back. Most returns 400 with no helpful error message. Solved by iterating through all documented slugs against the live API.

### Project ID Access
Initially only had the API key, not the project ID. Had to discover the project ID by calling the `/v2/projects` endpoint, which returned `proj058a6330`.

### Heuristic Score Calibration
First pass had a health score of 32/100 (Critical) for an app that's actually in decent shape — stable MRR, improving churn. Recalibrated baseline from 50 to 60 and adjusted penalty weights to produce a more accurate signal.

### Test Suite After Schema Changes
Reducing ChartName from 21 to 9 broke 4 tests. The `trial_conversion_rate` heuristic test needed replacing with a `customers_new` test. The "critical insight for MRR decline" test needed updating to accept "warning" (the new correct severity for that scenario).

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
