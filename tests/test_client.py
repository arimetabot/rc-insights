"""Tests for the Charts API client (_request retry logic, auth, rate limiting)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from rc_insights.client import (
    AuthenticationError,
    ChartsClient,
    ChartsClientError,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, body: dict, headers: dict | None = None) -> MagicMock:
    """Build a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    resp.headers = {"content-type": "application/json", **(headers or {})}
    return resp


def _client(max_retries: int = 3) -> ChartsClient:
    return ChartsClient(api_key="sk_test", project_id="proj_test", max_retries=max_retries)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_get_overview_success() -> None:
    """Successful 200 overview fetch returns parsed OverviewMetrics."""
    resp = _mock_response(200, {"object": "overview_metrics", "metrics": []})
    with patch.object(httpx.Client, "request", return_value=resp):
        result = _client().get_overview()
    assert result.metrics == []
    assert result.object == "overview_metrics"


def test_get_chart_success() -> None:
    """Successful 200 chart fetch returns parsed ChartData."""
    body = {
        "object": "chart_data",
        "display_name": "MRR",
        "description": "Monthly Recurring Revenue",
        "values": [[1704067200000, 1000.0], [1704153600000, 1100.0]],
    }
    resp = _mock_response(200, body)
    with patch.object(httpx.Client, "request", return_value=resp):
        result = _client().get_chart("mrr")
    assert result.display_name == "MRR"
    assert len(result.values) == 2


def test_get_chart_with_resolution_enum() -> None:
    """Resolution enum value is passed correctly as its numeric string."""
    from rc_insights.models import Resolution

    resp = _mock_response(200, {"object": "chart_data", "values": []})
    with patch.object(httpx.Client, "request", return_value=resp) as mock_req:
        _client().get_chart("mrr", resolution=Resolution.MONTH)
    _, kwargs = mock_req.call_args
    assert kwargs["params"]["resolution"] == "2"


# ---------------------------------------------------------------------------
# Auth errors
# ---------------------------------------------------------------------------


def test_401_raises_auth_error() -> None:
    """HTTP 401 raises AuthenticationError immediately (no retry)."""
    resp = _mock_response(401, {"message": "Unauthorized"})
    with patch.object(httpx.Client, "request", return_value=resp) as mock_req:
        with pytest.raises(AuthenticationError) as exc_info:
            _client(max_retries=3).get_overview()
    assert exc_info.value.status_code == 401
    assert mock_req.call_count == 1  # Must NOT retry auth errors


def test_403_raises_auth_error() -> None:
    """HTTP 403 raises AuthenticationError immediately (no retry)."""
    resp = _mock_response(403, {"message": "Access denied"})
    with patch.object(httpx.Client, "request", return_value=resp) as mock_req:
        with pytest.raises(AuthenticationError) as exc_info:
            _client(max_retries=3).get_overview()
    assert exc_info.value.status_code == 403
    assert mock_req.call_count == 1


def test_auth_error_is_subclass_of_charts_client_error() -> None:
    """AuthenticationError inherits from ChartsClientError for broad catching."""
    err = AuthenticationError("bad key", status_code=401)
    assert isinstance(err, ChartsClientError)
    assert err.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting (429)
# ---------------------------------------------------------------------------


def test_429_retries_and_succeeds() -> None:
    """429 triggers retry-after sleep, then succeeds on second attempt."""
    rate_limit = _mock_response(429, {}, headers={"Retry-After": "0"})
    success = _mock_response(200, {"object": "overview_metrics", "metrics": []})

    with patch.object(httpx.Client, "request", side_effect=[rate_limit, success]):
        with patch("time.sleep") as mock_sleep:
            result = _client(max_retries=3).get_overview()
    assert result.metrics == []
    mock_sleep.assert_called_once_with(0)  # Retry-After=0


def test_429_exhausts_retries_raises_rate_limit_error() -> None:
    """Persistent 429s after max_retries raise RateLimitError."""
    rate_limit = _mock_response(429, {}, headers={"Retry-After": "0"})

    with patch.object(httpx.Client, "request", return_value=rate_limit):
        with patch("time.sleep"):
            with pytest.raises(RateLimitError):
                _client(max_retries=2).get_overview()


def test_rate_limit_error_is_subclass_of_charts_client_error() -> None:
    """RateLimitError inherits from ChartsClientError."""
    err = RateLimitError("rate limited", status_code=429)
    assert isinstance(err, ChartsClientError)


# ---------------------------------------------------------------------------
# 5xx server error retries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_5xx_retries_and_succeeds(status_code: int) -> None:
    """5xx server errors trigger exponential backoff retry, then succeed."""
    server_error = _mock_response(status_code, {"message": "Server Error"})
    success = _mock_response(200, {"object": "overview_metrics", "metrics": []})

    with patch.object(httpx.Client, "request", side_effect=[server_error, success]):
        with patch("time.sleep") as mock_sleep:
            result = _client(max_retries=3).get_overview()
    assert result.metrics == []
    mock_sleep.assert_called_once_with(1)  # 2^0 = 1 second backoff on first retry


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_5xx_exhausts_retries_raises(status_code: int) -> None:
    """Persistent 5xx errors raise ChartsClientError after max_retries."""
    server_error = _mock_response(status_code, {"message": "Server Error"})

    with patch.object(httpx.Client, "request", return_value=server_error):
        with patch("time.sleep"):
            with pytest.raises(ChartsClientError) as exc_info:
                _client(max_retries=2).get_overview()
    assert exc_info.value.status_code == status_code


def test_5xx_exponential_backoff() -> None:
    """Each 5xx retry waits 2^attempt seconds (1s, 2s, ...)."""
    server_error = _mock_response(500, {"message": "Error"})
    success = _mock_response(200, {"object": "overview_metrics", "metrics": []})

    # 2 failures then success → 2 sleeps
    with patch.object(httpx.Client, "request", side_effect=[server_error, server_error, success]):
        with patch("time.sleep") as mock_sleep:
            _client(max_retries=4).get_overview()
    assert mock_sleep.call_args_list[0][0][0] == 1  # 2^0
    assert mock_sleep.call_args_list[1][0][0] == 2  # 2^1


# ---------------------------------------------------------------------------
# Generic HTTP errors (network failures)
# ---------------------------------------------------------------------------


def test_httpx_error_retries_and_succeeds() -> None:
    """Network-level httpx.HTTPError triggers retry with backoff."""
    success = _mock_response(200, {"object": "overview_metrics", "metrics": []})

    with patch.object(
        httpx.Client, "request", side_effect=[httpx.HTTPError("Connection refused"), success]
    ):
        with patch("time.sleep"):
            result = _client(max_retries=3).get_overview()
    assert result.metrics == []


def test_httpx_error_exhausts_retries_raises() -> None:
    """Persistent network errors raise ChartsClientError after max_retries."""
    with patch.object(
        httpx.Client, "request", side_effect=httpx.HTTPError("Timeout")
    ):
        with patch("time.sleep"):
            with pytest.raises(ChartsClientError, match="HTTP error after"):
                _client(max_retries=2).get_overview()


# ---------------------------------------------------------------------------
# Other HTTP errors (4xx non-auth)
# ---------------------------------------------------------------------------


def test_404_raises_immediately() -> None:
    """Non-retryable 4xx errors (e.g. 404) raise ChartsClientError without retry."""
    resp = _mock_response(404, {"message": "Chart not found"})
    with patch.object(httpx.Client, "request", return_value=resp) as mock_req:
        with pytest.raises(ChartsClientError) as exc_info:
            _client(max_retries=3).get_chart("nonexistent_chart")
    assert exc_info.value.status_code == 404
    assert mock_req.call_count == 1  # Must NOT retry


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager_closes_client() -> None:
    """ChartsClient works as a context manager and closes cleanly."""
    with patch.object(httpx.Client, "close") as mock_close:
        with ChartsClient(api_key="sk_test", project_id="proj_test"):
            pass
    mock_close.assert_called_once()
