"""RC Insights CLI — AI-powered subscription analytics from your terminal."""

from __future__ import annotations

import os
from datetime import date, timedelta

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rc_insights.alerts import AlertEngine
from rc_insights.analyzer import SubscriptionAnalyzer
from rc_insights.client import ChartsClient, ChartsClientError
from rc_insights.cohort import CohortAnalyzer
from rc_insights.models import Resolution
from rc_insights.report import save_report

load_dotenv()

def _version_callback(value: bool) -> None:
    if value:
        from rc_insights import __version__
        typer.echo(f"rc-insights {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="rc-insights",
    help="🧠 AI-powered subscription analytics for RevenueCat",
    add_completion=False,
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit", callback=_version_callback, is_eager=True),
) -> None:
    """🧠 AI-powered subscription analytics for RevenueCat."""


def _get_config(
    api_key_arg: str | None = None,
    project_id_arg: str | None = None,
    llm_key_arg: str | None = None,
) -> tuple[str, str, str | None]:
    """Get API keys from CLI args, environment, or .env file.

    LLM key resolution order: --llm-key arg → LLM_API_KEY env → OPENAI_API_KEY env.
    litellm also reads provider-specific env vars automatically (ANTHROPIC_API_KEY, etc.).
    """
    api_key = api_key_arg or os.getenv("RC_API_KEY", "")
    project_id = project_id_arg or os.getenv("RC_PROJECT_ID", "")
    llm_key = llm_key_arg or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        console.print("[red]Missing RC_API_KEY environment variable[/red]")
        console.print("Set it: export RC_API_KEY=sk_your_key_here")
        raise typer.Exit(1)

    if not project_id:
        console.print("[red]Missing RC_PROJECT_ID environment variable[/red]")
        console.print("Set it: export RC_PROJECT_ID=proj1ab2c3d4")
        raise typer.Exit(1)

    return api_key, project_id, llm_key


@app.command()
def report(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    resolution: str = typer.Option("day", "--resolution", "-r", help="Time resolution: day, week, month, quarter, year"),
    output: str = typer.Option("./reports", "--output", "-o", help="Output directory"),
    format: str = typer.Option("all", "--format", "-f", help="Output format: md, html, all"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI analysis, use heuristics only"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model string (e.g. gpt-4o-mini, claude-sonnet-4-5, ollama/llama3, groq/llama-3.1-70b)"),
    llm_key: str | None = typer.Option(None, "--llm-key", help="LLM API key (also reads LLM_API_KEY or provider-specific env vars)"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key (overrides RC_API_KEY env var)"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID (overrides RC_PROJECT_ID env var)"),
) -> None:
    """📊 Generate a subscription health report."""
    api_key, project_id, resolved_llm_key = _get_config(api_key, project_id, llm_key)

    res_map = {
        "day": Resolution.DAY,
        "week": Resolution.WEEK,
        "month": Resolution.MONTH,
        "quarter": Resolution.QUARTER,
        "year": Resolution.YEAR,
    }
    if resolution not in res_map:
        console.print(f"[red]Invalid resolution '{resolution}'.[/red] Choose from: {', '.join(res_map)}")
        raise typer.Exit(1)
    res = res_map[resolution]

    with console.status("[bold blue]Analyzing your subscription metrics...[/bold blue]"):
        try:
            analyzer = SubscriptionAnalyzer(
                rc_api_key=api_key,
                rc_project_id=project_id,
                llm_api_key=resolved_llm_key if not no_ai else None,
                llm_model=model,
            )
            health_report = analyzer.generate_report(
                days=days,
                resolution=res,
                include_ai=not no_ai,
            )
            analyzer.close()
        except ChartsClientError as e:
            console.print(f"[red]API Error:[/red] {e}")
            raise typer.Exit(1) from e

    # Display summary
    score = health_report.overall_health_score
    if score >= 70:
        score_color = "green"
        grade = "Healthy ✅"
    elif score >= 40:
        score_color = "yellow"
        grade = "Mixed ⚠️"
    else:
        score_color = "red"
        grade = "Critical 🚨"

    console.print()
    console.print(
        Panel(
            f"[bold {score_color}]{score:.0f}/100[/bold {score_color}] — {grade}\n\n"
            f"{health_report.summary}",
            title="📊 Subscription Health Report",
            border_style=score_color,
        )
    )

    # Show insights
    if health_report.insights:
        table = Table(title="🧠 Insights", show_header=True, border_style="dim")
        table.add_column("", width=2)
        table.add_column("Issue", style="bold")
        table.add_column("Metric")
        table.add_column("Recommendation", style="dim")

        severity_emoji = {"critical": "🔴", "warning": "🟡", "positive": "🟢", "info": "🔵"}
        for insight in health_report.insights:
            table.add_row(
                severity_emoji.get(insight.severity, "·"),
                insight.title,
                insight.metric_value or "—",
                insight.recommendation[:80] + "..."
                    if len(insight.recommendation) > 80
                    else insight.recommendation,
            )

        console.print(table)

    # Save files
    formats = ["md", "html"] if format == "all" else [format]
    files = save_report(health_report, output, formats=formats)

    console.print()
    for f in files:
        console.print(f"[green]✓[/green] Saved: {f}")


@app.command()
def overview(
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key (overrides RC_API_KEY env var)"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID (overrides RC_PROJECT_ID env var)"),
) -> None:
    """📋 Show current overview metrics."""
    api_key, project_id, _ = _get_config(api_key, project_id)

    with console.status("[bold blue]Fetching overview metrics...[/bold blue]"):
        try:
            client = ChartsClient(api_key=api_key, project_id=project_id)
            metrics = client.get_overview()
            client.close()
        except ChartsClientError as e:
            console.print(f"[red]API Error:[/red] {e}")
            raise typer.Exit(1) from e

    table = Table(title="📋 Overview Metrics", show_header=True, border_style="blue")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Unit")
    table.add_column("Period", style="dim")

    for m in metrics.metrics:
        table.add_row(m.name, f"{m.value:,.2f}", m.unit, m.period)

    console.print(table)


@app.command()
def chart(
    name: str = typer.Argument(help="Chart name (e.g., mrr, revenue, churn)"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days"),
    resolution: str = typer.Option("day", "--resolution", "-r", help="Resolution: day, week, month, quarter, year"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key (overrides RC_API_KEY env var)"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID (overrides RC_PROJECT_ID env var)"),
) -> None:
    """📈 Fetch and display a specific chart."""
    api_key, project_id, _ = _get_config(api_key, project_id)

    res_map = {
        "day": Resolution.DAY,
        "week": Resolution.WEEK,
        "month": Resolution.MONTH,
        "quarter": Resolution.QUARTER,
        "year": Resolution.YEAR,
    }
    if resolution not in res_map:
        console.print(f"[red]Invalid resolution '{resolution}'.[/red] Choose from: {', '.join(res_map)}")
        raise typer.Exit(1)
    res = res_map[resolution]

    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days)

    with console.status(f"[bold blue]Fetching {name} chart...[/bold blue]"):
        try:
            client = ChartsClient(api_key=api_key, project_id=project_id)
            data = client.get_chart(name, start_date=start, end_date=end, resolution=res)
            client.close()
        except ChartsClientError as e:
            console.print(f"[red]API Error:[/red] {e}")
            raise typer.Exit(1) from e

    console.print(f"\n[bold]{data.display_name}[/bold]")
    console.print(f"[dim]{data.description}[/dim]\n")

    points = data.data_points
    if not points:
        console.print("[yellow]No data points returned.[/yellow]")
        return

    table = Table(show_header=True, border_style="blue")
    table.add_column("Date", style="dim")
    table.add_column("Value", justify="right")

    for ts, val in points[-20:]:  # Show last 20 points
        date_str = ts.strftime("%Y-%m-%d") if ts else "—"
        table.add_row(date_str, f"{val:,.2f}")

    if len(points) > 20:
        console.print(f"[dim](Showing last 20 of {len(points)} data points)[/dim]")

    console.print(table)

    # Quick stats
    values = [v for _, v in points if v is not None]
    if values:
        console.print(f"\n[dim]Latest: {values[-1]:,.2f} | "
                      f"Min: {min(values):,.2f} | "
                      f"Max: {max(values):,.2f} | "
                      f"Avg: {sum(values)/len(values):,.2f}[/dim]")


@app.command(name="charts")
def list_charts() -> None:
    """📝 List all available chart types."""
    table = Table(title="Available Charts", show_header=True, border_style="blue")
    table.add_column("Name", style="bold")
    table.add_column("Category")

    # Only charts confirmed working against live API (proj058a6330, Mar 2026)
    categories = {
        "Revenue": ["revenue", "mrr", "mrr_movement"],
        "Subscribers": ["actives", "actives_new", "customers_new", "customers_active"],
        "Health": ["churn", "refund_rate"],
    }

    for category, charts in categories.items():
        for c in charts:
            table.add_row(c, category)

    console.print(table)


@app.command()
def check(
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model to check"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID"),
) -> None:
    """🔍 Check your configuration and API connectivity."""
    console.print("[bold]Configuration Check[/bold]\n")

    # Check RC credentials
    rc_key = api_key or os.getenv("RC_API_KEY", "")
    rc_project = project_id or os.getenv("RC_PROJECT_ID", "")

    if rc_key:
        console.print(f"  RC API Key:    [green]✅ {'*' * 8}{rc_key[-4:]}[/green]")
    else:
        console.print("  RC API Key:    [red]❌ Missing — set RC_API_KEY or pass --api-key[/red]")

    if rc_project:
        console.print(f"  Project ID:    [green]✅ {rc_project}[/green]")
    else:
        console.print("  Project ID:    [red]❌ Missing — set RC_PROJECT_ID or pass --project-id[/red]")

    # Check LLM keys
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    console.print()
    if llm_key:
        console.print(f"  LLM Key:       [green]✅ {'*' * 8}{llm_key[-4:]}[/green]")
    elif anthropic_key:
        console.print(f"  Anthropic Key: [green]✅ {'*' * 8}{anthropic_key[-4:]}[/green]")
    else:
        console.print("  LLM Key:       [yellow]⚠️  Not set — will use heuristic analysis (no AI insights)[/yellow]")

    console.print(f"  LLM Model:     [dim]{model}[/dim]")

    # API connectivity test (only if credentials are present)
    if rc_key and rc_project:
        console.print()
        with console.status("[bold blue]Testing API connection...[/bold blue]"):
            try:
                client = ChartsClient(api_key=rc_key, project_id=rc_project)
                overview = client.get_overview()
                client.close()
                console.print(f"  API Connection: [green]✅ Connected — {overview.active_subscribers:.0f} active subscribers[/green]")
            except Exception as e:
                console.print(f"  API Connection: [red]❌ Failed — {e}[/red]")
    elif not rc_key or not rc_project:
        console.print("\n  [dim]Skipping API test — set both RC_API_KEY and RC_PROJECT_ID to test connectivity[/dim]")

    console.print()


@app.command(name="models")
def list_models() -> None:
    """🤖 List popular supported LLM models and their configuration."""
    table = Table(title="Supported LLM Models (powered by litellm)", show_header=True, border_style="blue")
    table.add_column("Model String", style="bold cyan")
    table.add_column("Provider")
    table.add_column("Env Var Required")
    table.add_column("Notes", style="dim")

    supported = [
        ("gpt-4o-mini", "OpenAI", "OPENAI_API_KEY", "Default — fast & affordable"),
        ("gpt-4o", "OpenAI", "OPENAI_API_KEY", "Better reasoning, higher cost"),
        ("claude-sonnet-4-5", "Anthropic", "ANTHROPIC_API_KEY", "Fast & smart"),
        ("claude-opus-4-5", "Anthropic", "ANTHROPIC_API_KEY", "Most capable"),
        ("ollama/llama3", "Ollama (local)", "None — run `ollama serve`", "Free, private, offline"),
        ("ollama/mistral", "Ollama (local)", "None — run `ollama serve`", "Lightweight"),
        ("ollama/phi3", "Ollama (local)", "None — run `ollama serve`", "Very small & fast"),
        ("groq/llama-3.1-70b-versatile", "Groq", "GROQ_API_KEY", "Very fast inference"),
        ("groq/mixtral-8x7b-32768", "Groq", "GROQ_API_KEY", "Good balance"),
        ("mistral/mistral-medium", "Mistral AI", "MISTRAL_API_KEY", "European alternative"),
        ("azure/gpt-4o", "Azure OpenAI", "AZURE_API_KEY + AZURE_API_BASE", "Enterprise"),
        ("gemini/gemini-1.5-flash", "Google", "GEMINI_API_KEY", "Fast multimodal"),
        ("cohere/command-r-plus", "Cohere", "COHERE_API_KEY", "Good for RAG"),
    ]

    for model_str, provider, env_var, notes in supported:
        table.add_row(model_str, provider, env_var, notes)

    console.print(table)
    console.print()
    console.print("[bold]Usage examples:[/bold]")
    console.print("  rc-insights report --model gpt-4o-mini")
    console.print("  rc-insights report --model claude-sonnet-4-5")
    console.print("  rc-insights report --model ollama/llama3   [dim]# local, no API key[/dim]")
    console.print("  rc-insights report --model groq/llama-3.1-70b-versatile")
    console.print()
    console.print("[dim]Full provider list: https://docs.litellm.ai/docs/providers[/dim]")


def _build_alert_metrics(client: ChartsClient) -> dict[str, float]:
    """Collect metrics from the RC API for alert evaluation."""
    metrics: dict[str, float] = {}

    # --- Overview (MRR, churn, active subscribers) ---
    try:
        overview = client.get_overview()
        if overview.mrr:
            metrics["mrr"] = overview.mrr
        if overview.churn_rate:
            metrics["churn"] = overview.churn_rate
        if overview.active_subscribers:
            metrics["active_subscribers"] = overview.active_subscribers
        if overview.active_trials:
            metrics["active_trials"] = overview.active_trials
        if overview.revenue:
            metrics["revenue"] = overview.revenue
    except ChartsClientError:
        pass

    # --- MRR percent change (last 4 weeks) ---
    try:
        end = date.today()
        start = end - timedelta(days=28)
        mrr_chart = client.get_chart("mrr", start_date=start, end_date=end, resolution=Resolution.WEEK)
        pts = mrr_chart.data_points
        if len(pts) >= 2:
            first_val, last_val = pts[0][1], pts[-1][1]
            if first_val > 0:
                metrics["mrr_change_pct"] = ((last_val - first_val) / first_val) * 100.0
    except ChartsClientError:
        pass

    return metrics


@app.command()
def alerts(
    config: str | None = typer.Option(None, "--config", "-c", help="Path to YAML alert config (default: built-in rules)"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key (overrides RC_API_KEY env var)"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID (overrides RC_PROJECT_ID env var)"),
) -> None:
    """🚨 Check subscription metrics against alert thresholds.

    Uses default rules (churn > 8%, MRR drop > 10%, trial conversion < 40%)
    unless --config points to a custom YAML file.
    """
    api_key, project_id, _ = _get_config(api_key, project_id)

    # Load rules
    if config:
        try:
            engine = AlertEngine.from_yaml(config)
            console.print(f"[dim]Loaded {len(engine.rules)} rules from {config}[/dim]")
        except FileNotFoundError:
            console.print(f"[red]Config file not found:[/red] {config}")
            raise typer.Exit(1)
        except (KeyError, ValueError) as e:
            console.print(f"[red]Invalid config:[/red] {e}")
            raise typer.Exit(1)
    else:
        engine = AlertEngine.default_rules()
        console.print(f"[dim]Using {len(engine.rules)} default alert rules[/dim]")

    # Fetch metrics
    with console.status("[bold blue]Fetching subscription metrics...[/bold blue]"):
        try:
            client = ChartsClient(api_key=api_key, project_id=project_id)
            metrics = _build_alert_metrics(client)
            client.close()
        except ChartsClientError as e:
            console.print(f"[red]API Error:[/red] {e}")
            raise typer.Exit(1) from e

    # Evaluate rules
    all_alerts = engine.evaluate(metrics)
    triggered = [a for a in all_alerts if a.triggered]
    passing = [a for a in all_alerts if not a.triggered]
    skipped = len(engine.rules) - len(all_alerts)

    console.print()

    if triggered:
        console.print(
            Panel(
                "\n".join(f"  🔴 {a.message}" for a in triggered),
                title=f"🚨 {len(triggered)} Alert(s) Triggered",
                border_style="red",
            )
        )
    else:
        console.print(Panel("All checks passed ✅", title="Alerts", border_style="green"))

    if passing:
        table = Table(show_header=True, border_style="dim", title="✅ Passing Checks")
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        table.add_column("Threshold", justify="right")
        for a in passing:
            table.add_row(
                a.rule.metric,
                f"{a.current_value:.2f}",
                f"{a.rule.operator} {a.rule.threshold:.2f}",
            )
        console.print(table)

    if skipped:
        console.print(f"[dim]⚠ {skipped} rule(s) skipped — metric data unavailable[/dim]")

    if triggered:
        raise typer.Exit(1)


@app.command()
def cohorts(
    weeks: int = typer.Option(12, "--weeks", "-w", help="Number of weekly cohorts to display"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key (overrides RC_API_KEY env var)"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID (overrides RC_PROJECT_ID env var)"),
) -> None:
    """📅 Show weekly cohort retention table.

    Derives cohort retention from new-customer and active-subscriber time-series
    data. Because the RevenueCat Charts API returns aggregate totals, retention
    is approximated using an average weekly survival rate across all cohorts.
    """
    api_key, project_id, _ = _get_config(api_key, project_id)

    with console.status(f"[bold blue]Building {weeks}-week cohort retention table...[/bold blue]"):
        try:
            client = ChartsClient(api_key=api_key, project_id=project_id)
            analyzer = CohortAnalyzer(client)
            cohort_list = analyzer.analyze(weeks=weeks)
            client.close()
        except ChartsClientError as e:
            console.print(f"[red]API Error:[/red] {e}")
            raise typer.Exit(1) from e

    console.print()

    if not cohort_list:
        console.print("[yellow]⚠ No cohort data available. Try a longer time window.[/yellow]")
        return

    analyzer.render_table(cohort_list)

    console.print()
    console.print("[dim]Retention figures are approximate (derived from aggregate data).[/dim]")
    console.print(f"[dim]Cohorts: {len(cohort_list)} | Avg cohort size: "
                  f"{sum(c.size for c in cohort_list) // len(cohort_list):,}[/dim]")


@app.command(name="email-report")
def email_report(
    to: str = typer.Option(..., "--to", help="Recipient email address"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model string"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI analysis, use heuristics only"),
    llm_key: str | None = typer.Option(None, "--llm-key", help="LLM API key"),
    resend_key: str | None = typer.Option(None, "--resend-key", help="Resend API key (also reads RESEND_API_KEY env var)"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID"),
) -> None:
    """📧 Generate a health report and email it."""
    api_key, project_id, resolved_llm_key = _get_config(api_key, project_id, llm_key)

    from rc_insights.emails import EmailConfig, EmailSender

    rkey = resend_key or os.getenv("RESEND_API_KEY", "")
    if not rkey:
        console.print("[red]Missing RESEND_API_KEY — set it or pass --resend-key[/red]")
        raise typer.Exit(1)

    with console.status("[bold blue]Generating report...[/bold blue]"):
        analyzer = SubscriptionAnalyzer(
            rc_api_key=api_key,
            rc_project_id=project_id,
            llm_api_key=resolved_llm_key,
            llm_model=model,
        )
        report_result = analyzer.generate_report(days=days, include_ai=not no_ai)

    with console.status(f"[bold blue]Emailing report to {to}...[/bold blue]"):
        config = EmailConfig(api_key=rkey)
        with EmailSender(config=config) as sender:
            result = sender.send_report(to=to, report=report_result)

    if result.success:
        console.print(f"[green]✅ Report emailed to {to}[/green] (ID: {result.message_id})")
    else:
        console.print(f"[red]❌ Failed to send: {result.error}[/red]")
        raise typer.Exit(1)


@app.command()
def notify(
    slack_url: str | None = typer.Option(None, "--slack", help="Slack incoming webhook URL"),
    discord_url: str | None = typer.Option(None, "--discord", help="Discord webhook URL"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model string"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI analysis, use heuristics only"),
    llm_key: str | None = typer.Option(None, "--llm-key", help="LLM API key"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID"),
) -> None:
    """🔔 Generate a report and send to Slack or Discord."""
    if not slack_url and not discord_url:
        console.print("[red]Provide --slack or --discord webhook URL[/red]")
        raise typer.Exit(1)

    api_key, project_id, resolved_llm_key = _get_config(api_key, project_id, llm_key)

    with console.status("[bold blue]Generating report...[/bold blue]"):
        analyzer = SubscriptionAnalyzer(
            rc_api_key=api_key,
            rc_project_id=project_id,
            llm_api_key=resolved_llm_key,
            llm_model=model,
        )
        report_result = analyzer.generate_report(days=days, include_ai=not no_ai)

    from rc_insights.notifications import DiscordNotifier, SlackNotifier

    if slack_url:
        with console.status("[bold blue]Sending to Slack...[/bold blue]"):
            notifier = SlackNotifier(webhook_url=slack_url)
            ok = notifier.send_report(report_result)
        if ok:
            console.print("[green]✅ Report sent to Slack[/green]")
        else:
            console.print("[red]❌ Failed to send to Slack[/red]")

    if discord_url:
        with console.status("[bold blue]Sending to Discord...[/bold blue]"):
            notifier = DiscordNotifier(webhook_url=discord_url)
            ok = notifier.send_report(report_result)
        if ok:
            console.print("[green]✅ Report sent to Discord[/green]")
        else:
            console.print("[red]❌ Failed to send to Discord[/red]")


if __name__ == "__main__":
    app()
