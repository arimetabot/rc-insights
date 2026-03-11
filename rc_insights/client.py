"""RevenueCat Charts API v2 client."""

from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any

import httpx

from rc_insights.models import (
    ChartData,
    ChartName,
    OverviewMetrics,
    Resolution,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.revenuecat.com/v2"


class ChartsClientError(Exception):
    """Base exception for ChartsClient errors."""

    def __init__(self, message: str, status_code: int | None = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(ChartsClientError):
    """Raised when API key is invalid or lacks permissions."""


class RateLimitError(ChartsClientError):
    """Raised when rate limited by the API."""


class ChartsClient:
    """Client for RevenueCat's Charts API v2.

    Usage:
        client = ChartsClient(api_key="sk_...", project_id="proj1ab2c3d4")
        overview = client.get_overview()
        revenue = client.get_chart("revenue", start_date="2025-01-01", end_date="2025-12-31")
    """

    def __init__(
        self,
        api_key: str,
        project_id: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.project_id = project_id
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        self.max_retries = max_retries

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make an authenticated request with retry logic."""
        url = f"/projects/{self.project_id}{path}"

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, url, **kwargs)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid API key or insufficient permissions.",
                        status_code=401,
                        response=response.json(),
                    )
                elif response.status_code == 403:
                    body = response.json()
                    raise AuthenticationError(
                        f"Access denied: {body.get('message', 'Unknown error')}",
                        status_code=403,
                        response=body,
                    )
                elif response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        retry_after = int(response.headers.get("Retry-After", "5"))
                        logger.warning("Rate limited. Retrying in %ss...", retry_after)
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        "Rate limit exceeded. Please try again later.",
                        status_code=429,
                    )
                elif response.status_code in (500, 502, 503, 504):
                    if attempt < self.max_retries - 1:
                        wait = 2**attempt
                        logger.warning(
                            "Server error %s, retrying in %ss (attempt %s/%s)...",
                            response.status_code,
                            wait,
                            attempt + 1,
                            self.max_retries,
                        )
                        time.sleep(wait)
                        continue
                    body = (
                        response.json()
                        if response.headers.get("content-type", "").startswith("application/json")
                        else {"message": response.text}
                    )
                    msg = body.get("message", response.text)
                    raise ChartsClientError(
                        f"Server error {response.status_code}: {msg}",
                        status_code=response.status_code,
                        response=body,
                    )
                else:
                    body = (
                        response.json()
                        if response.headers.get("content-type", "").startswith("application/json")
                        else {"message": response.text}
                    )
                    raise ChartsClientError(
                        f"API error {response.status_code}: {body.get('message', response.text)}",
                        status_code=response.status_code,
                        response=body,
                    )
            except (AuthenticationError, RateLimitError, ChartsClientError):
                raise  # Never retry auth/client errors caught above
            except httpx.HTTPError as e:
                if attempt < self.max_retries - 1:
                    wait = 2**attempt
                    logger.warning("HTTP error (attempt %s): %s", attempt + 1, e)
                    time.sleep(wait)
                    continue
                raise ChartsClientError(
                        f"HTTP error after {self.max_retries} retries: {e}"
                    ) from e

        raise ChartsClientError("Max retries exceeded")

    def get_overview(self, *, currency: str = "USD") -> OverviewMetrics:
        """Get overview metrics for the project.

        Returns key metrics like MRR, active subscribers, churn rate, etc.
        """
        params: dict[str, str] = {}
        if currency != "USD":
            params["currency"] = currency

        data = self._request("GET", "/metrics/overview", params=params)
        return OverviewMetrics.model_validate(data)

    def get_chart(
        self,
        chart_name: str | ChartName,
        *,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        resolution: str | Resolution = Resolution.DAY,
        segment: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        selectors: dict[str, str] | None = None,
        aggregate: list[str] | None = None,
        currency: str = "USD",
        realtime: bool = True,
    ) -> ChartData:
        """Get chart data for a specific metric.

        Args:
            chart_name: Name of the chart (e.g., "revenue", "mrr", "churn").
            start_date: Start date (ISO 8601). Defaults to 30 days ago.
            end_date: End date (ISO 8601). Defaults to today.
            resolution: Time resolution (Resolution enum or numeric string "0"-"4").
                        Note: the RC Charts API uses numeric codes — "0"=day, "1"=week,
                        "2"=month, "3"=quarter, "4"=year.
            segment: Segment dimension (e.g., "country", "product").
            filters: JSON array of chart filters.
            selectors: JSON object of chart selectors.
            aggregate: Comma-separated aggregate operations.
            currency: ISO 4217 currency code.
            realtime: Use v3 (realtime) charts. Set False for v2.
        """
        if isinstance(chart_name, ChartName):
            chart_name = chart_name.value
        if isinstance(resolution, Resolution):
            resolution_id = resolution.value
        else:
            resolution_id = resolution

        # Default date range: last 30 days
        if start_date is None:
            start_date = (date.today() - timedelta(days=30)).isoformat()
        elif isinstance(start_date, date):
            start_date = start_date.isoformat()

        if end_date is None:
            end_date = date.today().isoformat()
        elif isinstance(end_date, date):
            end_date = end_date.isoformat()

        params: dict[str, str] = {
            "start_date": start_date,
            "end_date": end_date,
            "resolution": resolution_id,
            "currency": currency,
            "realtime": str(realtime).lower(),
        }

        if segment:
            params["segment"] = segment
        if filters:
            params["filters"] = json.dumps(filters)
        if selectors:
            params["selectors"] = json.dumps(selectors)
        if aggregate:
            params["aggregate"] = ",".join(aggregate)

        data = self._request("GET", f"/charts/{chart_name}", params=params)
        return ChartData.model_validate(data)

    def get_chart_options(
        self,
        chart_name: str | ChartName,
        *,
        realtime: bool = True,
    ) -> dict[str, Any]:
        """Get available options for a chart (resolutions, segments, filters)."""
        if isinstance(chart_name, ChartName):
            chart_name = chart_name.value

        return self._request(
            "GET",
            f"/charts/{chart_name}/options",
            params={"realtime": str(realtime).lower()},
        )

    def get_all_core_charts(
        self,
        *,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        resolution: Resolution = Resolution.DAY,
    ) -> dict[str, ChartData]:
        """Fetch all core charts in one call. Used for health reports.

        Returns a dict mapping chart name -> ChartData.
        """
        # Only confirmed-working chart slugs (verified against live API for proj058a6330).
        # All 9 of these return HTTP 200. Others that returned 400 have been excluded.
        # Resolution enum uses numeric codes: DAY="0", WEEK="1", MONTH="2", etc.
        core_charts = [
            ChartName.REVENUE,
            ChartName.MRR,
            ChartName.MRR_MOVEMENT,
            ChartName.CHURN,
            ChartName.REFUND_RATE,
            ChartName.ACTIVES,
            ChartName.ACTIVES_NEW,
            ChartName.CUSTOMERS_NEW,
            ChartName.CUSTOMERS_ACTIVE,
        ]

        results: dict[str, ChartData] = {}
        for chart in core_charts:
            try:
                data = self.get_chart(
                    chart,
                    start_date=start_date,
                    end_date=end_date,
                    resolution=resolution,
                )
                results[chart.value] = data
                logger.info("Fetched chart: %s", chart.value)
            except ChartsClientError as e:
                logger.warning("Failed to fetch chart %s: %s", chart.value, e)

        return results

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> ChartsClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
