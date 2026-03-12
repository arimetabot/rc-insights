# Changelog

All notable changes to RC Insights will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-03-11

### Added
- Multi-LLM support via litellm (100+ providers: OpenAI, Anthropic, Ollama, Groq, Mistral, and more)
- Threshold alerts with custom YAML configuration (`rc-insights alerts`)
- Cohort retention analysis (`rc-insights cohorts`)
- Slack/Discord notification integration (`rc-insights notify`)
- Email reports via Resend (`rc-insights email-report`)
- RevenueCat webhook receiver (FastAPI endpoint for real-time events)
- GitHub Action for automated weekly health checks
- `--version` flag
- `py.typed` marker (PEP 561)

### Fixed
- `email-report` and `notify` commands now work correctly (fixed kwarg name)
- Streamlit dashboard properly passes `llm_api_key` to `SubscriptionAnalyzer`
- XSS hardening: escape `insight.severity` in Streamlit HTML rendering
- `check` command now works without env vars set (reports what's missing instead of crashing)
- Version in `__init__.py` now matches PyPI release

### Changed
- ChartName enum reduced from 21 to 9 confirmed-working endpoints
- Health score baseline recalibrated from 50 to 60

## [0.1.0] - 2026-03-11

### Added
- Initial release
- `ChartsClient` — typed API wrapper for RevenueCat Charts API v2
- `SubscriptionAnalyzer` — AI + heuristic analysis engine
- CLI with `report`, `overview`, `chart`, `charts`, `check`, `models` commands
- Streamlit web dashboard
- Health score (0-100) with executive summary
- Markdown and HTML report generation
- Heuristic fallback (works without any LLM key)
- 71 tests
