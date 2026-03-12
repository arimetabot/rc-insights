"""Cohort retention analysis for RC Insights.

Builds approximate weekly cohort retention tables from RevenueCat time-series
data (new customers + active subscriber counts).  Because the Charts API
returns aggregate totals rather than subscriber-level events, retention is
approximated using a derived average weekly survival rate:

    survival_rate ≈ mean( (actives[k] - new_customers[k]) / actives[k-1] )

Each cohort's starting size equals the new-customer count for that week; all
cohorts share the same retention curve, compounded per week.

Usage:
    client = ChartsClient(api_key="...", project_id="...")
    analyzer = CohortAnalyzer(client)
    cohorts = analyzer.analyze(weeks=12)
    print(analyzer.render_table(cohorts))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from rc_insights.models import Resolution

if TYPE_CHECKING:
    from rc_insights.client import ChartsClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Cohort:
    """Retention data for a single weekly cohort.

    Attributes:
        start_date: ISO-formatted date string for the week start (e.g. "2025-01-06").
        size:       Number of new customers who joined that week (cohort size at week 0).
        retention:  Mapping of week_number → retention percentage.
                    Week 0 is always 100.0; subsequent weeks decrease.
    """

    start_date: str
    size: int
    retention: dict[int, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class CohortAnalyzer:
    """Derive cohort retention tables from RevenueCat aggregate chart data.

    Args:
        client: An authenticated :class:`~rc_insights.client.ChartsClient`.
    """

    # Conservative default when there's insufficient data to compute a rate.
    _DEFAULT_SURVIVAL_RATE: float = 0.85

    def __init__(self, client: ChartsClient) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, weeks: int = 12) -> list[Cohort]:
        """Build a cohort retention table from RevenueCat time-series data.

        Fetches weekly ``customers_new`` (cohort entry sizes) and ``actives``
        (total active subscribers) charts, derives an average weekly survival
        rate, and applies it to each cohort.

        Args:
            weeks: Number of weekly cohorts to include in the output.

        Returns:
            List of :class:`Cohort` objects ordered from oldest to newest.
            Returns an empty list when insufficient data is available.
        """
        buffer = 4  # extra weeks to stabilise the survival rate estimate
        end = date.today()
        start = end - timedelta(weeks=weeks + buffer)

        new_cust_pts = self._fetch_new_customers(start, end)
        actives_pts = self._fetch_actives(start, end)

        survival = self._compute_survival_rate(new_cust_pts, actives_pts)
        logger.info("Average weekly survival rate: %.3f", survival)

        # Use the most recent `weeks` data points as cohorts
        cohort_pts = new_cust_pts[-weeks:] if len(new_cust_pts) >= weeks else new_cust_pts
        total = len(cohort_pts)

        cohorts: list[Cohort] = []
        for i, (ts, size) in enumerate(cohort_pts):
            date_str = (
                ts.strftime("%Y-%m-%d")
                if isinstance(ts, datetime)
                else f"Week-{i + 1}"
            )
            cohort_size = max(1, int(round(size)))

            # Weeks of historical data available for this cohort.
            # The newest cohort (i == total-1) has 1 week (week 0 only);
            # each older cohort gets one additional week of data.
            weeks_with_data = total - i

            retention: dict[int, float] = {0: 100.0}
            for k in range(1, weeks_with_data):
                pct = round(100.0 * (survival**k), 1)
                retention[k] = pct

            cohorts.append(Cohort(start_date=date_str, size=cohort_size, retention=retention))

        return cohorts

    def render_table(self, cohorts: list[Cohort]) -> str:
        """Render a Rich heatmap table of cohort retention to stdout.

        Cell colours:
        - ≥ 80 % → green
        - ≥ 50 % → yellow
        - < 50 % → red
        - No data → dim dash

        Args:
            cohorts: List returned by :meth:`analyze`.

        Returns:
            Plain-text representation of the table (ANSI stripped).
            Also prints the coloured version to stdout as a side-effect.
        """
        if not cohorts:
            msg = "No cohort data available."
            Console().print(f"[yellow]{msg}[/yellow]")
            return msg

        table = self._build_rich_table(cohorts)

        # Print colour version to the real terminal
        Console().print(table)

        # Capture plain-text version for callers that need a string (tests, CI)
        rec = Console(record=True, width=120, highlight=False, no_color=True)
        rec.print(table)
        return rec.export_text()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_new_customers(
        self, start: date, end: date
    ) -> list[tuple[datetime | None, float]]:
        """Attempt ``customers_new`` then fall back to ``actives_new``."""
        for chart_name in ("customers_new", "actives_new"):
            try:
                chart = self.client.get_chart(
                    chart_name,
                    start_date=start,
                    end_date=end,
                    resolution=Resolution.WEEK,
                )
                pts = chart.data_points
                if pts:
                    logger.debug("Fetched %d points from %s", len(pts), chart_name)
                    return pts
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not fetch %s: %s", chart_name, exc)

        logger.warning("No new-customer data available — cohort sizes will be 0.")
        return []

    def _fetch_actives(
        self, start: date, end: date
    ) -> list[tuple[datetime | None, float]]:
        """Fetch weekly active subscriber counts."""
        try:
            chart = self.client.get_chart(
                "actives",
                start_date=start,
                end_date=end,
                resolution=Resolution.WEEK,
            )
            return chart.data_points
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch actives chart: %s", exc)
            return []

    def _compute_survival_rate(
        self,
        new_cust_pts: list[tuple[datetime | None, float]],
        actives_pts: list[tuple[datetime | None, float]],
    ) -> float:
        """Derive average weekly survival rate from aggregate time-series data.

        Formula (per week *k*):
            surviving_k = actives[k] - new_customers[k]   (subscribers retained from k-1)
            survival_k  = surviving_k / actives[k-1]

        Returns the arithmetic mean over all usable weeks, clamped to [0, 1].
        Falls back to :attr:`_DEFAULT_SURVIVAL_RATE` when data is insufficient.
        """
        n = min(len(new_cust_pts), len(actives_pts))
        if n < 2:
            return self._DEFAULT_SURVIVAL_RATE

        new_vals = [v for _, v in new_cust_pts[-n:]]
        act_vals = [v for _, v in actives_pts[-n:]]

        rates: list[float] = []
        for k in range(1, n):
            prev = act_vals[k - 1]
            curr = act_vals[k]
            new = new_vals[k]

            if prev <= 0:
                continue

            # Subscribers surviving from the previous week (excluding new arrivals)
            surviving = max(0.0, curr - new)
            rate = min(1.0, surviving / prev)
            rates.append(rate)

        if not rates:
            return self._DEFAULT_SURVIVAL_RATE

        avg = sum(rates) / len(rates)
        # Sanity clamp: survival rate should be between 50 % and 100 %
        return max(0.5, min(1.0, avg))

    @staticmethod
    def _build_rich_table(cohorts: list[Cohort]) -> Table:
        """Build a Rich Table from cohort data."""
        max_week = max(
            (max(c.retention.keys()) for c in cohorts if c.retention),
            default=0,
        )

        table = Table(
            title="📊 Cohort Retention Analysis",
            show_header=True,
            border_style="blue",
            header_style="bold cyan",
            show_lines=False,
        )

        table.add_column("Cohort", style="bold", min_width=12, no_wrap=True)
        table.add_column("Size", justify="right", min_width=6)
        for wk in range(max_week + 1):
            label = "Wk 0" if wk == 0 else f"Wk {wk}"
            table.add_column(label, justify="right", min_width=6)

        for cohort in cohorts:
            cells: list[str] = [cohort.start_date, str(cohort.size)]
            for wk in range(max_week + 1):
                pct = cohort.retention.get(wk)
                if pct is None:
                    cells.append("[dim]—[/dim]")
                elif pct >= 80:
                    cells.append(f"[green]{pct:.0f}%[/green]")
                elif pct >= 50:
                    cells.append(f"[yellow]{pct:.0f}%[/yellow]")
                elif pct > 0:
                    cells.append(f"[red]{pct:.0f}%[/red]")
                else:
                    cells.append(f"[dim]{pct:.0f}%[/dim]")
            table.add_row(*cells)

        return table
