"""RevenueCat real-time webhook receiver.

Provides a framework-agnostic processor (``WebhookReceiver``) and an optional
FastAPI application (``app``) that can be run directly with uvicorn.

Lightweight usage (no FastAPI required)::

    from rc_insights.webhooks import WebhookReceiver

    receiver = WebhookReceiver(auth_key="whsec_...")

    @receiver.on("INITIAL_PURCHASE")
    def handle_purchase(event):
        print(f"New purchase: {event.product_id} — ${event.revenue}")

    # In your WSGI/ASGI handler:
    event = receiver.process(request_body, request_headers)

FastAPI usage::

    # Run: uvicorn rc_insights.webhooks:app --host 0.0.0.0 --port 8000
    from rc_insights.webhooks import app

Or configure auth via the ``RC_WEBHOOK_AUTH_KEY`` environment variable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WebhookEvent:
    """A parsed and validated RevenueCat webhook event.

    Attributes:
        event_type: One of the ``SUPPORTED_EVENTS`` strings
            (e.g. ``"INITIAL_PURCHASE"``).
        app_user_id: The RevenueCat app user ID.
        product_id: The product / entitlement identifier.
        revenue: Revenue in USD for the transaction, or ``None`` if not
            applicable (e.g. cancellations, expirations).
        timestamp: Event timestamp (UTC).
        raw: The original ``event`` dict from the webhook payload.
    """

    event_type: str
    app_user_id: str
    product_id: str
    revenue: float | None
    timestamp: datetime
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Receiver
# ---------------------------------------------------------------------------


class WebhookReceiver:
    """Lightweight RevenueCat webhook processor.

    Parses incoming webhook payloads, optionally verifies HMAC signatures,
    and dispatches events to registered handlers.

    Usage with any ASGI/WSGI framework::

        receiver = WebhookReceiver(auth_key="whsec_...")

        @receiver.on("CANCELLATION")
        def on_cancel(event):
            send_win_back_email(event.app_user_id)

        event = receiver.process(request_body, headers)
        if event:
            # Additional handling
            ...

    Args:
        auth_key: Optional shared secret for HMAC-SHA256 signature
            verification. If ``None``, signature checks are skipped.
    """

    SUPPORTED_EVENTS: list[str] = [
        "INITIAL_PURCHASE",
        "RENEWAL",
        "CANCELLATION",
        "BILLING_ISSUE",
        "SUBSCRIBER_ALIAS",
        "PRODUCT_CHANGE",
        "EXPIRATION",
        "UNCANCELLATION",
    ]

    def __init__(self, auth_key: str | None = None) -> None:
        self.auth_key = auth_key
        self.handlers: dict[str, list[Callable]] = {}

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify a RevenueCat webhook HMAC-SHA256 signature.

        Args:
            body: Raw request body bytes.
            signature: Hex-encoded HMAC-SHA256 digest from the
                ``X-RevenueCat-Signature`` request header.

        Returns:
            ``True`` if the signature matches (or if no ``auth_key`` is
            configured — i.e. verification is disabled).
        """
        if not self.auth_key:
            return True  # verification disabled — always accept

        expected = hmac.new(
            self.auth_key.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process(
        self,
        body: bytes | str,
        headers: dict | None = None,
    ) -> WebhookEvent | None:
        """Parse and validate a RevenueCat webhook payload.

        Args:
            body: Raw HTTP request body (bytes or str).
            headers: HTTP request headers dict. Used for optional signature
                verification via ``X-RevenueCat-Signature``.

        Returns:
            A :class:`WebhookEvent` on success, or ``None`` if the payload
            is invalid, unsupported, or fails signature verification.
        """
        # Normalise to bytes
        body_bytes: bytes = body.encode() if isinstance(body, str) else body

        # Signature verification — use `is not None` so an empty dict still triggers checks
        if self.auth_key and headers is not None:
            # Header name may arrive in mixed case
            sig = (
                headers.get("X-RevenueCat-Signature")
                or headers.get("x-revenuecat-signature")
                or ""
            )
            if not self.verify_signature(body_bytes, sig):
                logger.warning(
                    "Webhook signature verification failed — discarding event"
                )
                return None

        # Parse JSON
        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Failed to parse webhook payload as JSON: %s", exc)
            return None

        # Validate top-level structure
        event_data = payload.get("event")
        if not isinstance(event_data, dict):
            logger.warning(
                "Webhook payload missing 'event' key or value is not an object"
            )
            return None

        event_type = event_data.get("type", "")
        if event_type not in self.SUPPORTED_EVENTS:
            logger.info(
                "Ignoring unsupported RevenueCat event type: %r "
                "(supported: %s)",
                event_type,
                ", ".join(self.SUPPORTED_EVENTS),
            )
            return None

        # Parse timestamp — RevenueCat uses millisecond epoch integers
        ts_ms = event_data.get("purchased_at_ms") or event_data.get(
            "event_timestamp_ms"
        )
        if ts_ms:
            try:
                timestamp = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        # Parse revenue — absent for cancellations, expirations, etc.
        revenue_raw = event_data.get("revenue_in_usd") or event_data.get(
            "price_in_purchased_currency"
        )
        try:
            revenue: float | None = (
                float(revenue_raw) if revenue_raw is not None else None
            )
        except (TypeError, ValueError):
            revenue = None

        event = WebhookEvent(
            event_type=event_type,
            app_user_id=event_data.get("app_user_id", ""),
            product_id=event_data.get("product_id", ""),
            revenue=revenue,
            timestamp=timestamp,
            raw=event_data,
        )

        # Dispatch to registered handlers
        for handler in self.handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Webhook handler %r raised an exception: %s", handler.__name__, exc
                )

        return event

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def on(self, event_type: str) -> Callable:
        """Decorator to register an event handler for a specific event type.

        Args:
            event_type: A RevenueCat event type string, e.g. ``"RENEWAL"``.

        Example::

            @receiver.on("BILLING_ISSUE")
            def notify_billing(event):
                send_alert(event.app_user_id)
        """

        def decorator(func: Callable) -> Callable:
            self.handlers.setdefault(event_type, []).append(func)
            return func

        return decorator


# ---------------------------------------------------------------------------
# Optional FastAPI application
# ---------------------------------------------------------------------------


def create_webhook_app(auth_key: str | None = None):  # type: ignore[return]
    """Create a minimal FastAPI application for receiving RevenueCat webhooks.

    The app exposes a single endpoint: ``POST /webhooks/revenuecat``

    Run with::

        uvicorn rc_insights.webhooks:app --host 0.0.0.0 --port 8000

    Or configure the auth key via the ``RC_WEBHOOK_AUTH_KEY`` environment
    variable before importing this module.

    Args:
        auth_key: HMAC shared secret for signature verification, or ``None``
            to skip verification.

    Raises:
        ImportError: If ``fastapi`` is not installed.

    Returns:
        A configured :class:`fastapi.FastAPI` application instance.
    """
    try:
        from fastapi import FastAPI, HTTPException, Request
    except ImportError as exc:
        raise ImportError(
            "FastAPI is required to run the webhook server. "
            "Install it with: pip install 'rc-insights[webhooks]'"
        ) from exc

    _app = FastAPI(
        title="RC Insights Webhook Receiver",
        description="Receives and processes RevenueCat real-time webhook events.",
        version="0.1.0",
    )
    _receiver = WebhookReceiver(auth_key=auth_key)

    @_app.post("/webhooks/revenuecat")
    async def handle_webhook(request: Request):  # type: ignore[return]
        """Receive and process a RevenueCat webhook event."""
        body = await request.body()
        headers = dict(request.headers)
        event = _receiver.process(body, headers)
        if event:
            logger.info(
                "Processed RC webhook: %s  user=%s  product=%s",
                event.event_type,
                event.app_user_id,
                event.product_id,
            )
            return {"status": "ok", "event_type": event.event_type}
        raise HTTPException(
            status_code=400, detail="Invalid or unrecognized webhook payload"
        )

    return _app


# Module-level ``app`` — configure auth via RC_WEBHOOK_AUTH_KEY env var.
# ``uvicorn rc_insights.webhooks:app`` works when fastapi is installed.
try:
    app = create_webhook_app(auth_key=os.getenv("RC_WEBHOOK_AUTH_KEY"))
except ImportError:
    app = None  # type: ignore[assignment]
