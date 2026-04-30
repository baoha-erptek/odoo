"""GearmentAdapter — Protocol + concrete impl wrapping GearmentApiClient.

Spec 005 P0-16b2 EtsyApiAdapter pattern mirrored here.

Out of scope for P0-18b1:
- live POST draft/confirm (P4-01 + owner sign-off)
- webhook signature discovery (P0-18b2)

Idempotency belt-and-braces: HTTP `Idempotency-Key` header + body
`reference_id` field, both derived from `payload.external_order_id`.
P0-18b2 will determine which Gearment honors.
"""
import json
import logging
import time
from typing import Protocol

from .gearment_api_client import GearmentApiClient
from .gearment_payload import GearmentOrderPayload

_logger = logging.getLogger(__name__)

# PII keys dropped from `gearment.api.log.request_payload_summary` (audit hygiene).
# Mirrors P0-17 etsy.api.log scrubbing pattern.
_PII_KEYS = frozenset({
    'buyer_name',
    'address_line_1',
    'address_line_2',
    'street_1',
    'street_2',
    'email',
    'phone',
    'notes',
    'address',
})


def _scrub_pii(payload_dict: dict) -> dict:
    """Return a new dict with PII keys removed (immutable input).

    Used by adapter before storing payload in gearment.api.log.
    """
    return {k: v for k, v in payload_dict.items() if k not in _PII_KEYS}


class GearmentAdapter(Protocol):
    """Protocol shape for Gearment-style fulfillment adapters."""

    def test_connection(self) -> bool: ...

    def push_order(self, payload: GearmentOrderPayload) -> dict: ...

    def get_quote(self, partner_ref: str) -> dict: ...

    def confirm(self, partner_ref: str) -> dict: ...

    def register_webhooks(self, callback_url: str, events: list) -> list: ...

    def parse_webhook_payload(self, headers: dict, body: bytes) -> dict: ...


class GearmentApiAdapter:
    """Concrete adapter wrapping GearmentApiClient (P0-18a).

    Constructor accepts optional `env` (for `gearment.api.log` writes) and
    optional `client` (for testing). Default-instantiates `GearmentApiClient`.
    Tests mock `requests.Session` at the client module level — see test docs.
    """

    def __init__(self, env=None, client=None):
        self.env = env
        self.client = client if client is not None else GearmentApiClient()

    def _log_call(
        self,
        endpoint: str,
        source: str,
        http_status: int | None = None,
        duration_ms: int | None = None,
        request_payload: dict | None = None,
        response_data: dict | None = None,
        error_message: str | None = None,
        sale_order_id: int | None = None,
    ) -> None:
        """Persist a gearment.api.log row (best-effort; never raises).

        request_payload is PII-scrubbed before storage; Authorization headers
        are never accepted as payload keys.
        """
        if self.env is None:
            return  # Logging requires Odoo env; tests without env get a no-op
        try:
            scrubbed = _scrub_pii(request_payload or {})
            payload_summary = json.dumps(scrubbed, default=str)[:4000]
            response_summary = (
                json.dumps(response_data, default=str)[:4000]
                if response_data is not None else None
            )
            # sudo: cron / system writes only; sale_manager has read-only ACL.
            # Adapter callers run within trusted Odoo env; bypass record rules
            # so non-privileged callers still produce audit trail.
            self.env['gearment.api.log'].sudo().create({
                'sale_order_id': sale_order_id,
                'endpoint': endpoint,
                'http_status': http_status,
                'duration_ms': duration_ms,
                'request_payload_summary': payload_summary,
                'response_summary': response_summary,
                'error_message': error_message,
                'source': source,
            })
        except Exception:  # noqa: BLE001
            _logger.exception("gearment.api.log write failed; skipping audit row")

    # ------------------------------------------------------------- Protocol API

    def test_connection(self) -> bool:
        """Validate connectivity by pinging /api/v3/catalog."""
        try:
            self._fetch_catalog(limit=1)
            return True
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Gearment test_connection failed: %s", exc)
            return False

    def push_order(self, payload: GearmentOrderPayload) -> dict:
        """POST /api/v3/orders with Idempotency-Key header + reference_id body.

        Returns: {'partner_ref', 'price_quote', 'quote_expires_at'}.
        """
        body = payload.serialize()
        headers = {'Idempotency-Key': payload.idempotency_key}
        endpoint = 'POST /api/v3/orders'
        started = time.monotonic()
        try:
            resp = self.client._request(
                'POST', 'api/v3/orders', json=body, headers=headers,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='draft',
                http_status=200, duration_ms=duration_ms,
                request_payload=body, response_data=resp,
            )
            return {
                'partner_ref': resp.get('order_id'),
                'price_quote': resp.get('price_quote'),
                'quote_expires_at': resp.get('quote_expires_at'),
            }
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='draft',
                http_status=None, duration_ms=duration_ms,
                request_payload=body, error_message=str(exc),
            )
            raise

    def get_quote(self, partner_ref: str) -> dict:
        """GET /api/v3/orders/{partner_ref} returns quote dict."""
        endpoint = f'GET /api/v3/orders/{partner_ref}'
        started = time.monotonic()
        try:
            resp = self.client._request(
                'GET', f'api/v3/orders/{partner_ref}',
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='quote',
                http_status=200, duration_ms=duration_ms,
                response_data=resp,
            )
            return {
                'price_quote': resp.get('price_quote'),
                'shipping_estimate': resp.get('shipping_estimate'),
                'quote_expires_at': resp.get('quote_expires_at'),
            }
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='quote',
                duration_ms=duration_ms, error_message=str(exc),
            )
            raise

    def confirm(self, partner_ref: str) -> dict:
        """Stub: live confirm requires owner sign-off + state machine.

        Implementation lives in P4-01.
        """
        raise NotImplementedError(
            "P4-01: live confirm requires owner sign-off + full state machine"
        )

    def register_webhooks(self, callback_url: str, events: list) -> list:
        """Stub: webhook registration deferred to P0-18b2.

        Requires ngrok tunnel for inbound POST signature discovery.
        """
        raise NotImplementedError(
            "P0-18b2: webhook signature discovery pending (needs ngrok + HMAC secret)"
        )

    def parse_webhook_payload(self, headers: dict, body: bytes) -> dict:
        """Stub: HMAC algorithm + signature header name pending.

        Will be unblocked by P0-18b2 inspecting first inbound POST.
        """
        raise NotImplementedError(
            "P0-18b2: HMAC algorithm + signature header pending"
        )

    # ------------------------------------------------------------- Helpers

    def _fetch_catalog(self, limit: int = 1) -> dict:
        """Internal helper: GET /api/v3/catalog?limit={limit}."""
        return self.client._request(
            'GET', 'api/v3/catalog', params={'limit': limit},
        )
