"""GearmentAdapter — Protocol + concrete impl wrapping GearmentApiClient.

P4-01-B (2026-05-10) corrected the URL constants and response parsing per the
readiness probe in `specs/004-fulfillment-routing/findings.md` 2026-05-09:

- G1 fix: `POST /api/v3/orders` → `POST /api/v3/orders/draft`
- G2 fix: payload schema regen — see `gearment_payload.py`
- G3 fix: `/orders/{ref}/price` returns Money proto shape
  `{currency_code, units, nanos}` for `order_*` fields; `_money_to_decimal()`
  decodes them into `(Decimal, currency_code)` tuples.
- G4 fix: `confirm()` calls `POST /api/v3/orders/draft/labeled`.

Idempotency belt-and-braces (carried forward from P0-18b1):
- HTTP `Idempotency-Key: sha256(reference_id)` header
- body `reference_id` field

State machine + operator-review wizard live in P4-01-C (follow-up slice).
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .gearment_api_client import GearmentApiClient
from .gearment_payload import GearmentOrderPayload


def _idempotency_key(reference_id: str) -> str:
    """SHA-256 hex of reference_id — matches `GearmentOrderPayload.idempotency_key`.

    Hashing prevents HTTP header injection if `reference_id` ever contains
    CRLF (the value is sourced from `sale.order.channel_order_ref` which is
    user-editable in some flows). Also keeps the Idempotency-Key contract
    symmetric between `push_order` and `confirm`.
    """
    return hashlib.sha256(reference_id.encode()).hexdigest()

_logger = logging.getLogger(__name__)

# URL constants — see findings.md 2026-05-09 for the probe evidence.
_DRAFT_URL = 'api/v3/orders/draft'
_PRICE_URL = 'api/v3/orders/{ref}/price'
_LABELED_URL = 'api/v3/orders/draft/labeled'

# PII keys dropped from `gearment.api.log.request_payload_summary` (audit hygiene).
# Mirrors P0-17 etsy.api.log scrubbing pattern. Now also covers the new
# `addresses[].first_name/last_name/street_*/email/phone` keys via deep scrub.
_PII_KEYS = frozenset({
    'first_name',
    'last_name',
    'buyer_name',
    'address_line_1',
    'address_line_2',
    'street_1',
    'street_2',
    'email',
    'phone',
    'notes',
    'address',
    'addresses',
})


def _scrub_pii(value):
    """Recursively drop PII keys. Returns a new structure (immutable input)."""
    if isinstance(value, dict):
        return {
            k: _scrub_pii(v)
            for k, v in value.items()
            if k not in _PII_KEYS
        }
    if isinstance(value, list):
        return [_scrub_pii(item) for item in value]
    return value


def _money_to_decimal(money) -> tuple[Decimal, str]:
    """Decode Gearment's proto-Money shape `{currency_code, units, nanos}`.

    `units` is the integer part (string in JSON to avoid JS precision loss).
    `nanos` is the fractional part in nano-units (1 nano = 1e-9). Both can be
    missing if Gearment returns a partial Money on degraded endpoints. We
    degrade to zero rather than KeyError so the wizard can still display a
    line item with currency code preserved.
    """
    if not money:
        return (Decimal('0E-9'), '')
    currency = money.get('currency_code', '') or ''
    units_raw = money.get('units', '0') or '0'
    nanos = money.get('nanos', 0) or 0
    try:
        units = Decimal(str(units_raw))
        nanos_dec = Decimal(nanos) / Decimal('1000000000')
    except (ValueError, TypeError, ArithmeticError):
        return (Decimal('0E-9'), currency)
    # Quantize to 9 decimal places so test assertions on (45 + 0.99) parts
    # produce a stable representation.
    return ((units + nanos_dec).quantize(Decimal('0.000000001')), currency)


@dataclass(frozen=True)
class GearmentQuote:
    """Decoded quote response from `/orders/{ref}/price`. P4-01-B."""

    currency: str
    order_total: Decimal
    order_sub_total: Decimal
    order_shipping_fee: Decimal
    order_tax: Decimal
    order_discount: Decimal
    order_handle_fee: Decimal
    order_gift_message_fee: Decimal
    order_fee: Decimal


class GearmentAdapter(Protocol):
    """Protocol shape for Gearment-style fulfillment adapters."""

    def test_connection(self) -> bool: ...

    def push_order(self, payload: GearmentOrderPayload) -> dict: ...

    def get_quote(self, reference_id: str) -> dict: ...

    def confirm(self, reference_id: str, options: dict | None = None) -> dict: ...

    def register_webhooks(self, callback_url: str, events: list) -> list: ...

    def parse_webhook_payload(self, headers: dict, body: bytes) -> dict: ...


class GearmentApiAdapter:
    """Concrete adapter wrapping GearmentApiClient (P0-18a)."""

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
        response_text: str | None = None,
        error_message: str | None = None,
        sale_order_id: int | None = None,
        direction: str | None = None,
    ) -> None:
        """Persist a gearment.api.log row (best-effort; never raises).

        `response_text` carries the raw response body when the call failed
        (e.g. 4xx HTTPError) so operators can read the vendor's validation
        messages without scraping logs. Truncated to 4000 chars; takes
        precedence over `response_data` (which is the JSON-decoded form
        only set on success). See P4-01-FIX-LOG-LINKAGE +
        feedback_capture_response_body_before_blackbox_probe (memory).

        P4-01-FIX-LOG-LINKAGE-EXCEPTION-PATH (Defect-2026-05-11-02,
        2026-05-11): writes go through a fresh registry cursor with an
        explicit ``cr.commit()`` so the audit row survives an outer
        transaction rollback — caller is expected to ``raise`` after a
        4xx/5xx, which Odoo's XML-RPC dispatcher then converts to a
        request-level rollback. The original same-cursor write was
        rolled back with everything else, leaving operators blind to
        vendor failures (Defect-05 visibility regression).
        """
        if self.env is None:
            return
        scrubbed = _scrub_pii(request_payload or {})
        payload_summary = json.dumps(scrubbed, default=str)[:4000]
        if response_text is not None:
            response_summary = response_text[:4000]
        elif response_data is not None:
            response_summary = json.dumps(response_data, default=str)[:4000]
        else:
            response_summary = None
        vals = {
            'sale_order_id': sale_order_id,
            'endpoint': endpoint,
            'http_status': http_status,
            'duration_ms': duration_ms,
            'request_payload_summary': payload_summary,
            'response_summary': response_summary,
            'error_message': error_message,
            'source': source,
            'direction': direction,
        }
        try:
            # Fresh cursor + explicit commit so the row survives even if the
            # caller (or the request dispatcher) rolls back. See docstring.
            # sudo: cron / system writes only; sale_manager has read-only ACL.
            with self.env.registry.cursor() as cr:
                cr_env = self.env(cr=cr)
                cr_env['gearment.api.log'].sudo().create(vals)
                cr.commit()
        except Exception:  # noqa: BLE001
            _logger.exception("gearment.api.log write failed; skipping audit row")

    @staticmethod
    def _extract_failure_meta(exc: Exception) -> tuple[int | None, str | None]:
        """Pull (http_status, response_body) off a `requests.HTTPError`.

        Other exceptions (timeout, connection error, our own ValueError) yield
        (None, None). The status + body live on `exc.response` for HTTPError;
        this helper hides the import-time check from the call site.
        """
        response = getattr(exc, 'response', None)
        if response is None:
            return None, None
        status = getattr(response, 'status_code', None)
        text = getattr(response, 'text', None)
        return status, text

    # ------------------------------------------------------------- Protocol API

    def test_connection(self) -> bool:
        """Validate connectivity by pinging /api/v3/catalog."""
        try:
            self._fetch_catalog(limit=1)
            return True
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Gearment test_connection failed: %s", exc)
            return False

    def push_order(
        self,
        payload: GearmentOrderPayload,
        sale_order_id: int | None = None,
    ) -> dict:
        """POST /api/v3/orders/draft with Idempotency-Key + reference_id body.

        Returns: {'reference_id', 'order_id', 'raw_response'}.

        `sale_order_id` is forwarded into `gearment.api.log.sale_order_id` so
        operators can trace which order produced which API failure (P4-01-
        FIX-LOG-LINKAGE / Defect-2026-05-10-03).
        """
        body = payload.serialize()
        headers = {'Idempotency-Key': payload.idempotency_key}
        endpoint = f'POST /{_DRAFT_URL}'
        started = time.monotonic()
        try:
            resp = self.client._request(
                'POST', _DRAFT_URL, json=body, headers=headers,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='draft', direction='outbound',
                http_status=200, duration_ms=duration_ms,
                request_payload=body, response_data=resp,
                sale_order_id=sale_order_id,
            )
            data = resp.get('data', {}) if isinstance(resp, dict) else {}
            return {
                'reference_id': data.get('reference_id') or payload.reference_id,
                'order_id': data.get('order_id') or data.get('id'),
                'raw_response': resp,
            }
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            status, response_text = self._extract_failure_meta(exc)
            self._log_call(
                endpoint=endpoint, source='draft', direction='outbound',
                http_status=status, duration_ms=duration_ms,
                request_payload=body, response_text=response_text,
                error_message=str(exc), sale_order_id=sale_order_id,
            )
            raise

    def get_quote(self, reference_id: str) -> dict:
        """GET /api/v3/orders/{reference_id}/price returns decoded quote.

        Returns dict with keys: currency, order_total, order_sub_total,
        order_shipping_fee, order_tax, order_discount, order_handle_fee,
        order_gift_message_fee, order_fee, raw_response.
        """
        path = _PRICE_URL.format(ref=reference_id)
        endpoint = f'GET /{path}'
        started = time.monotonic()
        try:
            resp = self.client._request('GET', path)
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='quote',
                http_status=200, duration_ms=duration_ms,
                response_data=resp,
            )
            data = resp.get('data', {}) if isinstance(resp, dict) else {}
            currency = ''
            decoded = {}
            for key in (
                'order_total', 'order_sub_total', 'order_shipping_fee',
                'order_tax', 'order_discount', 'order_handle_fee',
                'order_gift_message_fee', 'order_fee',
            ):
                amount, cur = _money_to_decimal(data.get(key))
                decoded[key] = amount
                # First non-empty currency wins (probe shows all are USD-aligned).
                if cur and not currency:
                    currency = cur
            decoded['currency'] = currency
            decoded['raw_response'] = resp
            return decoded
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='quote',
                duration_ms=duration_ms, error_message=str(exc),
            )
            raise

    def confirm(self, reference_id: str, options: dict | None = None) -> dict:
        """POST /api/v3/orders/draft/labeled — submit labeled draft.

        `options` is forwarded as the request body's `data.options` entry so
        future per-confirm settings (e.g. operator approval flag) thread
        through without an interface change. P4-01-C wizard wires this up.

        Returns the full Gearment response dict so callers can inspect status
        + any returned partner_ref / tracking metadata.

        Raises `ValueError` on empty/whitespace `reference_id` (defense at
        the boundary; Gearment would reject it but we want a clean Odoo-side
        error before the audit-log write fires).
        """
        if not isinstance(reference_id, str) or not reference_id.strip():
            raise ValueError("confirm() requires a non-empty reference_id")
        body = {'data': {'reference_id': reference_id}}
        if options:
            body['data']['options'] = options
        endpoint = f'POST /{_LABELED_URL}'
        started = time.monotonic()
        try:
            resp = self.client._request(
                'POST', _LABELED_URL, json=body,
                headers={'Idempotency-Key': _idempotency_key(reference_id)},
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='confirm',
                http_status=200, duration_ms=duration_ms,
                request_payload=body, response_data=resp,
            )
            return resp if isinstance(resp, dict) else {}
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log_call(
                endpoint=endpoint, source='confirm',
                http_status=None, duration_ms=duration_ms,
                request_payload=body, error_message=str(exc),
            )
            raise

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
