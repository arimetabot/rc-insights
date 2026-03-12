"""RC Insights CLI — AI-powered subscription analytics from your terminal."""

from __future__ import annotations

import os

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rc_insights.analyzer import SubscriptionAnalyzer
from rc_insights.client import ChartsClient, ChartsClientError
from rc_insights.models import Resolution
from rc_insights.report import save_report

load_dotenv()

app = typer.Typer(
    name="rc-insights",
    help="🧠 AI-powered subscription analytics for RevenueCat",
    add_completion=False,
)
console = Console()


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
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model to report on (e.g. gpt-4o-mini, claude-sonnet-4-5, ollama/llama3)"),
    api_key: str | None = typer.Option(None, "--api-key", help="RevenueCat API key (overrides RC_API_KEY env var)"),
    project_id: str | None = typer.Option(None, "--project-id", help="RevenueCat project ID (overrides RC_PROJECT_ID env var)"),
) -> None:
    """🔍 Verify your API keys and LLM configuration."""
    api_key, project_id, llm_key = _get_config(api_key, project_id)

    console.print("[bold]Checking configuration...[/bold]\n")

    # Check RC API
    console.print(f"  RC API Key: [green]{'*' * 8}{api_key[-4:]}[/green]")
    console.print(f"  Project ID: [green]{project_id}[/green]")

    try:
        client = ChartsClient(api_key=api_key, project_id=project_id)
        overview = client.get_overview()
        client.close()
        console.print(f"  RC API:     [green]✓ Connected ({len(overview.metrics)} metrics)[/green]")
    except Exception as e:
        console.print(f"  RC API:     [red]✗ {e}[/red]")

    # Check LLM configuration
    console.print(f"\n  LLM Model:  [cyan]{model}[/cyan]")
    if llm_key:
        console.print(f"  LLM Key:    [green]✓ Configured ({'*' * 8}{llm_key[-4:]})[/green]")
    else:
        # Check provider-specific env vars that litellm reads automatically
        provider_keys = {
            "ANTHROPIC_API_KEY": "Anthropic",
            "GROQ_API_KEY": "Groq",
            "MISTRAL_API_KEY": "Mistral",
            "AZURE_API_KEY": "Azure OpenAI",
            "COHERE_API_KEY": "Cohere",
        }
        found_provider = None
        for env_var, provider in provider_keys.items():
            if os.getenv(env_var):
                found_provider = f"{provider} ({env_var})"
                break

        if found_provider:
            console.print(f"  LLM Key:    [green]✓ {found_provider} configured[/green]")
        elif model.startswith("ollama/"):
            console.print("  LLM Key:    [green]✓ Ollama (local — no key needed)[/green]")
        else:
            console.print("  LLM Key:    [yellow]⚠ No key found — will use heuristic mode[/yellow]")
            console.print("              [dim]Set LLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY[/dim]")

    console.print("\n[dim]Tip: rc-insights models — list all supported LLM providers[/dim]")
    console.print("[dim]All checks complete.[/dim]")


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


if __name__ == "__main__":
    app()
