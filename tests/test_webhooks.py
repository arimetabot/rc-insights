"""Tests for the RevenueCat webhook receiver."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from rc_insights.webhooks import WebhookEvent, WebhookReceiver

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(
    event_type: str = "INITIAL_PURCHASE",
    app_user_id: str = "user_42",
    product_id: str = "pro_monthly",
    revenue_in_usd: float | None = 9.99,
    purchased_at_ms: int = 1704067200000,
) -> bytes:
    """Build a minimal RevenueCat webhook payload as JSON bytes."""
    event: dict = {
        "type": event_type,
        "app_user_id": app_user_id,
        "product_id": product_id,
        "purchased_at_ms": purchased_at_ms,
    }
    if revenue_in_usd is not None:
        event["revenue_in_usd"] = revenue_in_usd
    return json.dumps({"event": event, "api_version": "1.0"}).encode()


def _sign(body: bytes, key: str) -> str:
    """Compute the expected HMAC-SHA256 signature for a body + key."""
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# WebhookReceiver.process — happy-path tests
# ---------------------------------------------------------------------------


class TestWebhookReceiverProcess:
    def test_returns_event_for_valid_payload(self) -> None:
        receiver = WebhookReceiver()
        body = _make_payload()
        event = receiver.process(body)
        assert event is not None
        assert isinstance(event, WebhookEvent)

    def test_event_type_parsed(self) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload(event_type="RENEWAL"))
        assert event is not None
        assert event.event_type == "RENEWAL"

    def test_app_user_id_parsed(self) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload(app_user_id="user_xyz"))
        assert event is not None
        assert event.app_user_id == "user_xyz"

    def test_product_id_parsed(self) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload(product_id="annual_plan"))
        assert event is not None
        assert event.product_id == "annual_plan"

    def test_revenue_parsed(self) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload(revenue_in_usd=4.99))
        assert event is not None
        assert event.revenue == pytest.approx(4.99)

    def test_revenue_none_when_absent(self) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload(revenue_in_usd=None))
        assert event is not None
        assert event.revenue is None

    def test_timestamp_parsed_from_ms(self) -> None:
        receiver = WebhookReceiver()
        # purchased_at_ms = 1704067200000 → 2024-01-01 00:00:00 UTC
        event = receiver.process(_make_payload(purchased_at_ms=1704067200000))
        assert event is not None
        assert event.timestamp.year == 2024
        assert event.timestamp.month == 1
        assert event.timestamp.day == 1
        assert event.timestamp.tzinfo is not None

    def test_raw_contains_event_data(self) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload())
        assert event is not None
        assert event.raw["type"] == "INITIAL_PURCHASE"
        assert event.raw["app_user_id"] == "user_42"

    def test_accepts_string_body(self) -> None:
        receiver = WebhookReceiver()
        body_str = _make_payload().decode()
        event = receiver.process(body_str)
        assert event is not None
        assert event.event_type == "INITIAL_PURCHASE"

    @pytest.mark.parametrize(
        "event_type",
        [
            "INITIAL_PURCHASE",
            "RENEWAL",
            "CANCELLATION",
            "BILLING_ISSUE",
            "SUBSCRIBER_ALIAS",
            "PRODUCT_CHANGE",
            "EXPIRATION",
            "UNCANCELLATION",
        ],
    )
    def test_all_supported_event_types_accepted(self, event_type: str) -> None:
        receiver = WebhookReceiver()
        event = receiver.process(_make_payload(event_type=event_type))
        assert event is not None
        assert event.event_type == event_type


# ---------------------------------------------------------------------------
# WebhookReceiver.process — error / edge-case tests
# ---------------------------------------------------------------------------


class TestWebhookReceiverProcessErrors:
    def test_returns_none_for_invalid_json(self) -> None:
        receiver = WebhookReceiver()
        result = receiver.process(b"not json at all!!!")
        assert result is None

    def test_returns_none_for_missing_event_key(self) -> None:
        receiver = WebhookReceiver()
        body = json.dumps({"api_version": "1.0"}).encode()
        result = receiver.process(body)
        assert result is None

    def test_returns_none_for_event_not_dict(self) -> None:
        receiver = WebhookReceiver()
        body = json.dumps({"event": "not-a-dict"}).encode()
        result = receiver.process(body)
        assert result is None

    def test_returns_none_for_unsupported_event_type(self) -> None:
        receiver = WebhookReceiver()
        result = receiver.process(_make_payload(event_type="UNKNOWN_EVENT"))
        assert result is None

    def test_falls_back_timestamp_when_missing(self) -> None:
        """Events without purchased_at_ms should still produce an event."""
        receiver = WebhookReceiver()
        payload = {"event": {"type": "CANCELLATION", "app_user_id": "u", "product_id": "p"}}
        before = datetime.now(timezone.utc)
        event = receiver.process(json.dumps(payload).encode())
        after = datetime.now(timezone.utc)
        assert event is not None
        assert before <= event.timestamp <= after

    def test_empty_body(self) -> None:
        receiver = WebhookReceiver()
        result = receiver.process(b"")
        assert result is None


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


class TestSignatureVerification:
    AUTH_KEY = "super_secret_key"

    def test_valid_signature_accepted(self) -> None:
        receiver = WebhookReceiver(auth_key=self.AUTH_KEY)
        body = _make_payload()
        sig = _sign(body, self.AUTH_KEY)
        headers = {"X-RevenueCat-Signature": sig}
        event = receiver.process(body, headers)
        assert event is not None

    def test_invalid_signature_rejected(self) -> None:
        receiver = WebhookReceiver(auth_key=self.AUTH_KEY)
        body = _make_payload()
        headers = {"X-RevenueCat-Signature": "deadbeef" * 8}
        event = receiver.process(body, headers)
        assert event is None

    def test_lowercase_header_accepted(self) -> None:
        receiver = WebhookReceiver(auth_key=self.AUTH_KEY)
        body = _make_payload()
        sig = _sign(body, self.AUTH_KEY)
        headers = {"x-revenuecat-signature": sig}
        event = receiver.process(body, headers)
        assert event is not None

    def test_no_auth_key_skips_verification(self) -> None:
        """When no auth_key is set, any (or missing) signature is accepted."""
        receiver = WebhookReceiver(auth_key=None)
        body = _make_payload()
        headers = {"X-RevenueCat-Signature": "wrong-signature"}
        event = receiver.process(body, headers)
        assert event is not None

    def test_verify_signature_directly_true(self) -> None:
        receiver = WebhookReceiver(auth_key=self.AUTH_KEY)
        body = b"hello world"
        sig = _sign(body, self.AUTH_KEY)
        assert receiver.verify_signature(body, sig) is True

    def test_verify_signature_directly_false(self) -> None:
        receiver = WebhookReceiver(auth_key=self.AUTH_KEY)
        assert receiver.verify_signature(b"hello", "wrongsig") is False

    def test_verify_signature_no_key_always_true(self) -> None:
        receiver = WebhookReceiver(auth_key=None)
        assert receiver.verify_signature(b"anything", "invalid") is True

    def test_missing_signature_header_rejected(self) -> None:
        """If auth_key set but no signature header, reject."""
        receiver = WebhookReceiver(auth_key=self.AUTH_KEY)
        body = _make_payload()
        # Empty string won't match the real HMAC
        headers = {}
        event = receiver.process(body, headers)
        assert event is None


# ---------------------------------------------------------------------------
# Handler registration and dispatch
# ---------------------------------------------------------------------------


class TestHandlerDispatch:
    def test_on_decorator_registers_handler(self) -> None:
        receiver = WebhookReceiver()
        calls: list[WebhookEvent] = []

        @receiver.on("INITIAL_PURCHASE")
        def handler(event: WebhookEvent) -> None:
            calls.append(event)

        assert "INITIAL_PURCHASE" in receiver.handlers
        assert handler in receiver.handlers["INITIAL_PURCHASE"]

    def test_handler_called_on_matching_event(self) -> None:
        receiver = WebhookReceiver()
        captured: list[WebhookEvent] = []

        @receiver.on("RENEWAL")
        def on_renewal(event: WebhookEvent) -> None:
            captured.append(event)

        receiver.process(_make_payload(event_type="RENEWAL"))
        assert len(captured) == 1
        assert captured[0].event_type == "RENEWAL"

    def test_handler_not_called_for_different_event(self) -> None:
        receiver = WebhookReceiver()
        calls: list = []

        @receiver.on("CANCELLATION")
        def on_cancel(event: WebhookEvent) -> None:
            calls.append(event)

        receiver.process(_make_payload(event_type="RENEWAL"))
        assert len(calls) == 0

    def test_multiple_handlers_for_same_event(self) -> None:
        receiver = WebhookReceiver()
        calls_a: list = []
        calls_b: list = []

        @receiver.on("BILLING_ISSUE")
        def handler_a(event: WebhookEvent) -> None:
            calls_a.append(event)

        @receiver.on("BILLING_ISSUE")
        def handler_b(event: WebhookEvent) -> None:
            calls_b.append(event)

        receiver.process(_make_payload(event_type="BILLING_ISSUE"))
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_handler_exception_does_not_bubble(self) -> None:
        """A crashing handler should not prevent the event from being returned."""
        receiver = WebhookReceiver()

        @receiver.on("INITIAL_PURCHASE")
        def bad_handler(event: WebhookEvent) -> None:
            raise RuntimeError("handler exploded")

        # Should not raise — exception is caught internally
        event = receiver.process(_make_payload(event_type="INITIAL_PURCHASE"))
        assert event is not None

    def test_on_returns_original_function(self) -> None:
        receiver = WebhookReceiver()

        def my_func(event: WebhookEvent) -> None:
            pass

        decorated = receiver.on("RENEWAL")(my_func)
        assert decorated is my_func


# ---------------------------------------------------------------------------
# SUPPORTED_EVENTS class attribute
# ---------------------------------------------------------------------------


class TestSupportedEvents:
    def test_supported_events_is_list(self) -> None:
        assert isinstance(WebhookReceiver.SUPPORTED_EVENTS, list)

    def test_known_events_present(self) -> None:
        assert "INITIAL_PURCHASE" in WebhookReceiver.SUPPORTED_EVENTS
        assert "RENEWAL" in WebhookReceiver.SUPPORTED_EVENTS
        assert "CANCELLATION" in WebhookReceiver.SUPPORTED_EVENTS
        assert "BILLING_ISSUE" in WebhookReceiver.SUPPORTED_EVENTS


# ---------------------------------------------------------------------------
# create_webhook_app — optional FastAPI app
# ---------------------------------------------------------------------------


class TestCreateWebhookApp:
    def test_raises_import_error_without_fastapi(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If fastapi is not importable, create_webhook_app should raise ImportError."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):  # type: ignore[return]
            if name == "fastapi":
                raise ImportError("No module named 'fastapi'")
            return real_import(name, *args, **kwargs)

        from rc_insights import webhooks

        with monkeypatch.context() as mp:
            mp.setattr(builtins, "__import__", mock_import)
            with pytest.raises(ImportError, match="(?i)fastapi"):
                webhooks.create_webhook_app()

    def test_app_created_when_fastapi_available(self) -> None:
        """If fastapi is installed, create_webhook_app returns a non-None object."""
        try:
            import fastapi  # noqa: F401
        except ImportError:
            pytest.skip("fastapi not installed in this environment")

        from rc_insights.webhooks import create_webhook_app

        app = create_webhook_app(auth_key=None)
        assert app is not None
