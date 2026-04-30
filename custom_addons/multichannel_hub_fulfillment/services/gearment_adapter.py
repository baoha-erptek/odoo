"""GearmentAdapter Protocol and GearmentApiAdapter concrete implementation (P0-18b1).

GearmentAdapter defines the interface for fulfillment adapters targeting
Gearment's API v3. GearmentApiAdapter is the concrete implementation that
wraps GearmentApiClient and handles:

  1. Connection testing (test_connection → ping catalog endpoint)
  2. Order submission (push_order → POST /api/v3/orders with idempotency)
  3. Quote retrieval (get_quote → GET /api/v3/orders/{partner_ref})
  4. Logging all calls to gearment.api.log with PII scrubbing
  5. Stubs for webhook + confirm (P4-01, P0-18b2 future phases)

Auth: Passed via GearmentApiClient (not managed by adapter).

Logging: Every call writes a gearment.api.log row with:
  - endpoint: 'METHOD /path'
  - http_status: response code (or NULL on error)
  - request_payload_summary: serialized payload with PII scrubbed
  - response_summary: truncated response body
  - error_message: exception details on failure
  - source: 'probe', 'draft', 'quote', 'confirm', 'callback', 'health_check'
"""

import json
import logging
import time
from typing import Protocol

from .gearment_payload import GearmentOrderPayload, _scrub_pii

_logger = logging.getLogger(__name__)


class GearmentAdapter(Protocol):
    """Fulfillment adapter protocol for Gearment API v3."""

    def test_connection(self) -> bool:
        """Validate API credentials and connectivity.

        Returns True if auth + network are OK, False on any error.
        """
        ...

    def push_order(self, payload: GearmentOrderPayload) -> dict:
        """Submit a new order to Gearment.

        Returns dict with keys:
          - partner_ref: Gearment's order_id
          - price_quote: USD quote amount
          - quote_expires_at: ISO 8601 expiration timestamp
        """
        ...

    def get_quote(self, partner_ref: str) -> dict:
        """Retrieve quote for an existing order.

        Args:
            partner_ref: Gearment's order_id (from push_order response).

        Returns dict with keys:
          - price_quote: USD quote amount
          - shipping_estimate: USD shipping cost (if available)
          - quote_expires_at: ISO 8601 expiration timestamp
        """
        ...

    def confirm(self, partner_ref: str) -> dict:
        """Confirm a quoted order for production (P4-01 stub).

        Not implemented until owner sign-off on live workflow.
        """
        ...

    def register_webhooks(
        self, callback_url: str, events: list[str],
    ) -> list[str]:
        """Register webhooks for order status callbacks (P0-18b2 stub).

        Not implemented until webhook signature algorithm is finalized.
        """
        ...

    def parse_webhook_payload(
        self, headers: dict, body: bytes,
    ) -> dict:
        """Parse and verify webhook payload (P0-18b2 stub).

        Not implemented until webhook signature algorithm is finalized.
        """
        ...


class GearmentApiAdapter:
    """Gearment API v3 adapter (P0-18b1) — concrete implementation."""

    def __init__(self, env=None, client=None):
        """Initialize adapter.

        Args:
            env: Odoo Environment (optional, for log writes). If None,
                 logs are not written to gearment.api.log.
            client: GearmentApiClient instance (optional). If None, a fresh
                    instance is created from environment variables.
        """
        self.env = env
        if client is None:
            from .gearment_api_client import GearmentApiClient

            client = GearmentApiClient()
        self.client = client

    def test_connection(self) -> bool:
        """Validate connectivity by fetching the first catalog product."""
        try:
            self._fetch_catalog(limit=1)
            return True
        except Exception as e:  # pylint: disable=broad-except
            _logger.warning("Gearment connection test failed: %s", str(e))
            return False

    def push_order(self, payload: GearmentOrderPayload) -> dict:
        """Submit order to Gearment.

        Includes Idempotency-Key header to prevent duplicates on retry.
        Logs the call with PII scrubbing.

        Returns dict with partner_ref, price_quote, quote_expires_at.
        """
        request_started_at = time.time()
        endpoint = 'POST /api/v3/orders'
        http_status = None
        error_message = None
        response_summary = None

        try:
            # Serialize payload and set up headers
            body = payload.serialize()
            headers = {
                'Idempotency-Key': payload.idempotency_key,
            }

            # Submit order
            response = self.client._request(
                'POST', 'api/v3/orders',
                json=body,
                headers=headers,
            )

            http_status = 200  # Gearment returns 200 on success
            response_summary = json.dumps({
                'order_id': response.get('order_id'),
                'price_quote': response.get('price_quote'),
                'quote_expires_at': response.get('quote_expires_at'),
            }, default=str)[:4096]

            result = {
                'partner_ref': response.get('order_id'),
                'price_quote': response.get('price_quote'),
                'quote_expires_at': response.get('quote_expires_at'),
            }
        except Exception as e:  # pylint: disable=broad-except
            error_message = str(e)
            _logger.warning("push_order failed: %s", error_message)
            raise

        finally:
            # Log the call (with PII scrubbing)
            if self.env:
                duration_ms = int((time.time() - request_started_at) * 1000)
                scrubbed = _scrub_pii(payload.serialize())
                self.env['gearment.api.log'].create({
                    'endpoint': endpoint,
                    'http_status': http_status,
                    'request_started_at': None,  # Auto-fill from field default
                    'duration_ms': duration_ms,
                    'request_payload_summary': json.dumps(scrubbed, default=str)[:2048],
                    'response_summary': response_summary,
                    'error_message': error_message,
                    'source': 'draft',
                })

        return result

    def get_quote(self, partner_ref: str) -> dict:
        """Retrieve quote for an existing order."""
        request_started_at = time.time()
        endpoint = f'GET /api/v3/orders/{partner_ref}'
        http_status = None
        error_message = None
        response_summary = None

        try:
            response = self.client._request(
                'GET', f'api/v3/orders/{partner_ref}',
            )

            http_status = 200
            response_summary = json.dumps({
                'price_quote': response.get('price_quote'),
                'shipping_estimate': response.get('shipping_estimate'),
                'quote_expires_at': response.get('quote_expires_at'),
            }, default=str)[:4096]

            result = {
                'price_quote': response.get('price_quote'),
                'shipping_estimate': response.get('shipping_estimate'),
                'quote_expires_at': response.get('quote_expires_at'),
            }
        except Exception as e:  # pylint: disable=broad-except
            error_message = str(e)
            _logger.warning("get_quote failed: %s", error_message)
            raise

        finally:
            # Log the call
            if self.env:
                duration_ms = int((time.time() - request_started_at) * 1000)
                self.env['gearment.api.log'].create({
                    'endpoint': endpoint,
                    'http_status': http_status,
                    'request_started_at': None,
                    'duration_ms': duration_ms,
                    'request_payload_summary': json.dumps(
                        {'order_id': partner_ref}, default=str
                    )[:2048],
                    'response_summary': response_summary,
                    'error_message': error_message,
                    'source': 'quote',
                })

        return result

    def confirm(self, partner_ref: str) -> dict:
        """Stub: confirm is deferred to P4-01 pending owner sign-off."""
        raise NotImplementedError(
            "P4-01: live confirm requires owner sign-off on fulfillment workflow"
        )

    def register_webhooks(
        self, callback_url: str, events: list[str],
    ) -> list[str]:
        """Stub: webhook registration deferred to P0-18b2."""
        raise NotImplementedError(
            "P0-18b2: webhook signature discovery pending"
        )

    def parse_webhook_payload(
        self, headers: dict, body: bytes,
    ) -> dict:
        """Stub: webhook parsing deferred to P0-18b2."""
        raise NotImplementedError(
            "P0-18b2: HMAC algorithm pending"
        )

    def _fetch_catalog(self, limit: int = 1) -> dict:
        """Fetch product catalog (helper for test_connection and discovery).

        Used by:
          - test_connection (limit=1) for lightweight probe
          - live_api tests (limit=100) for print_location discovery
        """
        return self.client._request(
            'GET', 'api/v3/catalog',
            params={'limit': limit},
        )
