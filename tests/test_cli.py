"""Smoke tests for the CLI — verify the app loads and help text renders."""

from __future__ import annotations

from typer.testing import CliRunner

from rc_insights.cli import app

runner = CliRunner()


def test_app_help_loads() -> None:
    """rc-insights --help exits 0 and shows the app name."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "rc-insights" in result.output.lower() or "subscription" in result.output.lower()


def test_charts_command_lists_charts() -> None:
    """rc-insights charts lists available chart types without requiring API keys."""
    result = runner.invoke(app, ["charts"])
    assert result.exit_code == 0
    assert "mrr" in result.output
    assert "churn" in result.output
    assert "revenue" in result.output


def test_report_command_help() -> None:
    """rc-insights report --help shows options."""
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output


def test_overview_command_help() -> None:
    """rc-insights overview --help shows help text."""
    result = runner.invoke(app, ["overview", "--help"])
    assert result.exit_code == 0


def test_check_command_help() -> None:
    """rc-insights check --help shows help text."""
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0


def test_chart_command_help() -> None:
    """rc-insights chart --help shows options."""
    result = runner.invoke(app, ["chart", "--help"])
    assert result.exit_code == 0


def test_missing_api_key_exits_with_error() -> None:
    """Commands that need API keys exit with code 1 when env vars are absent."""
    from unittest.mock import patch

    # patch.dict sets keys to empty string, which _get_config() treats as missing
    # (load_dotenv at module-level may have populated os.environ from .env — this overrides it)
    with patch.dict("os.environ", {"RC_API_KEY": "", "RC_PROJECT_ID": ""}):
        result = runner.invoke(app, ["overview"])
    assert result.exit_code == 1
    assert "RC_API_KEY" in result.output or "missing" in result.output.lower()
