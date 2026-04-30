"""Gearment API adapter for P0-18b1 order submission and quote retrieval.

Implements the GearmentAdapter Protocol (6 methods) and provides the concrete
GearmentApiAdapter class. Includes PII scrubbing for API logs per FR-017.
"""

import json
import logging
from typing import Any, Optional, Protocol

_logger = logging.getLogger(__name__)

# PII fields to scrub from logs per FR-017 (write-level defense)
_PII_KEYS = {
    'buyer_name',
    'address_line_1',
    'address_line_2',
    'email',
    'phone',
    'notes',
    'name',  # generic buyer name
    'first_name',
    'last_name',
}


def _scrub_pii(payload: dict) -> dict:
    """Remove PII fields from payload dict, preserving business data.

    Removes: buyer_name, address_line_1/2, email, phone, notes, etc.
    Preserves: product_id, platform, quantity, shipping_method, etc.

    Args:
        payload: dict potentially containing PII

    Returns:
        new dict with PII fields removed
    """
    return {k: v for k, v in payload.items() if k not in _PII_KEYS}


class GearmentAdapter(Protocol):
    """Protocol for Gearment fulfillment adapter.

    Any class implementing these 6 methods can be used as a fulfillment backend.
    """

    def test_connection(self) -> bool:
        """Test connection to Gearment API.

        Returns:
            True if auth succeeds (ping endpoint returns 200), False otherwise.
        """
        ...

    def push_order(self, payload: 'GearmentOrderPayload') -> dict:
        """Submit order to Gearment API.

        Args:
            payload: GearmentOrderPayload with order details

        Returns:
            dict with at least {partner_ref, price_quote} from Gearment response
        """
        ...

    def get_quote(self, order_id: str) -> dict:
        """Get quote/price for existing order.

        Args:
            order_id: Gearment order ID (e.g., 'gm_123')

        Returns:
            dict with at least {price_quote, quote_expires_at}
        """
        ...

    def confirm(self, order_id: str) -> dict:
        """Confirm order for production (P4-01 stub).

        Args:
            order_id: Gearment order ID

        Raises:
            NotImplementedError: deferred to P4-01
        """
        ...

    def register_webhooks(self, base_url: str, events: list) -> dict:
        """Register webhook endpoints (P0-18b2 stub).

        Args:
            base_url: webhook base URL (e.g., 'http://example.com/webhook')
            events: list of event types to subscribe

        Raises:
            NotImplementedError: deferred to P0-18b2 (HMAC signature discovery)
        """
        ...

    def parse_webhook_payload(self, headers: dict, body: bytes) -> dict:
        """Parse and verify webhook signature (P0-18b2 stub).

        Args:
            headers: HTTP headers from webhook delivery
            body: raw request body

        Returns:
            parsed event dict

        Raises:
            NotImplementedError: deferred to P0-18b2 (HMAC algorithm)
        """
        ...


class GearmentApiAdapter:
    """Concrete implementation of GearmentAdapter for Gearment API v3.

    Lazy-initializes GearmentApiClient only when first method is called
    (avoids env var errors during test setup).

    Logs every API call to gearment.api.log with source='draft'|'confirm'|'quote'|'probe'.
    Scrubs PII from request_payload_summary per FR-017.
    """

    def __init__(self, env=None, client=None):
        """Initialize adapter.

        Args:
            env: Odoo environment (optional; used for ORM access)
            client: GearmentApiClient instance (optional; lazy-created if None)
        """
        self.env = env
        self._client = client  # May be None; lazy-initialized on first use

    @property
    def client(self):
        """Lazy-initialize client on first access.

        Allows tests to inject a mock client without triggering env var reads.
        """
        if self._client is None:
            from .gearment_api_client import GearmentApiClient
            self._client = GearmentApiClient()
        return self._client

    def _log_api_call(self, endpoint: str, http_status: int, request_summary: str,
                      response_summary: str, source: str = 'draft',
                      error_message: str = None, duration_ms: int = 0) -> None:
        """Write API call to gearment.api.log if env is available.

        Args:
            endpoint: e.g., 'POST /api/v3/orders'
            http_status: HTTP response code
            request_summary: JSON string (with PII scrubbed)
            response_summary: JSON string
            source: 'draft' | 'quote' | 'probe' | 'confirm' | 'callback' | 'health_check'
            error_message: error text if any
            duration_ms: request duration
        """
        if self.env is None:
            return

        try:
            self.env['gearment.api.log'].create({
                'endpoint': endpoint,
                'http_status': http_status,
                'request_payload_summary': request_summary,
                'response_summary': response_summary,
                'source': source,
                'error_message': error_message,
                'duration_ms': duration_ms,
                'rate_limit_remaining': None,
            })
        except Exception as e:
            _logger.warning(f"Failed to log API call: {e}")

    def test_connection(self) -> bool:
        """Test connection to Gearment API (ping /api/v3/catalog?limit=1).

        Returns:
            True if ping succeeds, False on any error.
        """
        try:
            response = self.client.ping()
            # If we got a response, auth passed
            return True
        except Exception as e:
            _logger.debug(f"Gearment ping failed: {e}")
            return False

    def _fetch_catalog(self, limit: int = 1) -> dict:
        """Fetch product catalog from Gearment.

        Args:
            limit: max products to return (for discovery)

        Returns:
            dict with 'data' key containing product list
        """
        response = self.client._request('GET', 'api/v3/catalog', params={'limit': limit})
        return response

    def push_order(self, payload: 'GearmentOrderPayload') -> dict:
        """Submit order to Gearment API POST /api/v3/orders.

        Sets Idempotency-Key header from payload.idempotency_key.
        Sets reference_id in body from payload.external_order_id.
        Logs call with source='draft' and scrubbed PII.

        Args:
            payload: GearmentOrderPayload

        Returns:
            dict with partner_ref and price_quote from Gearment response
        """
        import time
        start_time = time.time()

        body = payload.serialize()
        scrubbed_body = _scrub_pii(body)
        request_summary = json.dumps(scrubbed_body)

        headers = {
            'Idempotency-Key': payload.idempotency_key,
        }

        try:
            response = self.client._request(
                'POST',
                'api/v3/orders',
                json=body,
                headers=headers,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            response_summary = json.dumps({
                'order_id': response.get('order_id'),
                'price_quote': response.get('price_quote'),
                'quote_expires_at': response.get('quote_expires_at'),
            })

            self._log_api_call(
                'POST /api/v3/orders',
                200,
                request_summary,
                response_summary,
                source='draft',
                duration_ms=duration_ms,
            )

            return {
                'partner_ref': response.get('order_id'),
                'price_quote': response.get('price_quote'),
                'quote_expires_at': response.get('quote_expires_at'),
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_api_call(
                'POST /api/v3/orders',
                500,
                request_summary,
                '{}',
                source='draft',
                error_message=str(e),
                duration_ms=duration_ms,
            )
            raise

    def get_quote(self, order_id: str) -> dict:
        """Retrieve quote for existing order.

        Args:
            order_id: Gearment order ID (e.g., 'gm_123')

        Returns:
            dict with price_quote, shipping_estimate, quote_expires_at
        """
        import time
        start_time = time.time()

        try:
            response = self.client._request('GET', f'api/v3/orders/{order_id}')

            duration_ms = int((time.time() - start_time) * 1000)
            response_summary = json.dumps({
                'price_quote': response.get('price_quote'),
                'shipping_estimate': response.get('shipping_estimate'),
                'quote_expires_at': response.get('quote_expires_at'),
            })

            self._log_api_call(
                'GET /api/v3/orders/{order_id}',
                200,
                json.dumps({'order_id': order_id}),
                response_summary,
                source='quote',
                duration_ms=duration_ms,
            )

            return {
                'price_quote': response.get('price_quote'),
                'shipping_estimate': response.get('shipping_estimate'),
                'quote_expires_at': response.get('quote_expires_at'),
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_api_call(
                'GET /api/v3/orders/{order_id}',
                500,
                json.dumps({'order_id': order_id}),
                '{}',
                source='quote',
                error_message=str(e),
                duration_ms=duration_ms,
            )
            raise

    def confirm(self, order_id: str) -> dict:
        """Confirm order for production (P4-01 stub).

        Raises:
            NotImplementedError: deferred to P4-01 (live confirm requires owner sign-off)
        """
        raise NotImplementedError(
            "P4-01: live confirm requires owner sign-off"
        )

    def register_webhooks(self, base_url: str, events: list) -> dict:
        """Register webhook endpoints (P0-18b2 stub).

        Raises:
            NotImplementedError: deferred to P0-18b2 (webhook signature discovery)
        """
        raise NotImplementedError(
            "P0-18b2: webhook signature discovery pending"
        )

    def parse_webhook_payload(self, headers: dict, body: bytes) -> dict:
        """Parse and verify webhook signature (P0-18b2 stub).

        Raises:
            NotImplementedError: deferred to P0-18b2 (HMAC algorithm)
        """
        raise NotImplementedError(
            "P0-18b2: HMAC algorithm pending"
        )
