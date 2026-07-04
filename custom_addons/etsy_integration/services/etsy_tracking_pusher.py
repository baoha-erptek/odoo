"""EtsyTrackingPusher (Spec 005 P1-12, US3).

Pushes a fulfillment's tracking number back to Etsy via
``POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking``,
closing the ingest -> fulfill -> track loop.

Trigger model (ADR decision D-A): the Gearment ``tracking_order_updated``
webhook handler is the primary, low-latency trigger; the 5-minute
``_cron_push_tracking`` sweep and the on-demand form button are
fallbacks. The Etsy tab is a read-only mirror (owner directive
2026-05-10 D4) — no trigger originates from operator writes to the order.

Identifiers (verified against the existing P0-16c adapter
``etsy_api_adapter.py:66-69``): Etsy v3 collapses order<->receipt 1:1,
so ``sale.order.etsy_order_id`` IS the receipt_id, and the Odoo
``etsy.shop`` record id is used as the ``{shop_id}`` path segment —
``etsy.shop`` has no separate numeric-shop-id field by design.

ORM-free constructor takes ``env`` explicitly (Odoo 19 dropped implicit
``Environment.envs``); never instantiate at import time.
"""

import logging

from .etsy_api_client import EtsyApiClient

_logger = logging.getLogger(__name__)

# Etsy v3 carrier enum fallback when the carrier has no mapping (T037).
_UNMAPPED_CARRIER_CODE = 'other'
_AUDIT_SOURCE = 'tracking_push'
_ERROR_TRUNCATE = 1000


class EtsyTrackingPusher:
    """Push tracking numbers to Etsy. One instance per call site."""

    def __init__(self, env):
        self.env = env

    def push(self, order):
        """Push ``order``'s tracking number to Etsy.

        Returns True on a successful push, False on any validation or
        API failure. Always records the outcome on the order
        (``etsy_tracking_push_status`` + companions) and writes one
        ``etsy.api.log`` audit row with ``source='tracking_push'``.
        """
        order.ensure_one()

        fulfillment = self.env['sale.order.fulfillment'].search(
            [('order_id', '=', order.id),
             ('tracking_number', '!=', False)],
            order='id desc', limit=1)
        if not fulfillment:
            return self._mark_failed(
                order, 'No fulfillment with a tracking number for this order',
                shop=order.etsy_shop_id, http_status=None, api_called=False)

        shop = order.etsy_shop_id
        receipt_id = order.etsy_order_id
        tracking_number = fulfillment.tracking_number

        # See etsy_order_syncer for shared rationale: Odoo PK != Etsy
        # shop_id. Refuse to push without a real Etsy shop_id.
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            return self._mark_failed(
                order, 'Shop has no etsy_api_shop_id; cannot push tracking',
                shop=shop, http_status=None, api_called=False)

        carrier_name = fulfillment.shipping_carrier_id.etsy_carrier_name
        warning = ''
        if not carrier_name:
            carrier_name = _UNMAPPED_CARRIER_CODE
            warning = (
                'Carrier %s has no etsy_carrier_name mapping; pushed as %r'
                % (fulfillment.shipping_carrier_id.display_name or '(unset)',
                   _UNMAPPED_CARRIER_CODE))
            _logger.warning('P1-12: %s (order %s)', warning, order.name)

        endpoint = (
            'POST /v3/application/shops/%s/receipts/%s/tracking'
            % (api_shop_id, receipt_id))

        try:
            client = EtsyApiClient(shop)
            ok, http_status, err = client.push_tracking(
                shop_path_id=api_shop_id,
                receipt_id=receipt_id,
                carrier_name=carrier_name,
                tracking_number=tracking_number,
            )
        except Exception as exc:  # noqa: BLE001 — any client/API error fails the push
            return self._mark_failed(
                order, 'Etsy tracking push error: %s' % exc,
                shop=shop, http_status=None, api_called=True,
                endpoint=endpoint)

        if not ok:
            return self._mark_failed(
                order, 'Etsy tracking push rejected: %s' % (err or 'unknown'),
                shop=shop, http_status=http_status, api_called=True,
                endpoint=endpoint)

        from odoo import fields as _fields
        now = _fields.Datetime.now()
        order.write({
            'etsy_tracking_push_status': 'pushed',
            'etsy_tracking_push_at': now,
            'etsy_tracking_push_error': False,
            'etsy_tracking_push_attempts': 0,
        })
        fulfillment.write({'etsy_ship_notified_at': now})
        self._audit(
            shop, endpoint, http_status,
            response_summary='Tracking pushed (%s / %s)' % (
                carrier_name, tracking_number),
            error_message=warning or False)
        _logger.debug(
            'P1-12: tracking pushed for %s (Etsy receipt %s, carrier %s)',
            order.name, receipt_id, carrier_name)
        return True

    def _mark_failed(self, order, message, shop, http_status,
                     api_called, endpoint=None):
        """Persist the failure on the order and audit it. Returns False."""
        from odoo import fields as _fields
        order.write({
            'etsy_tracking_push_status': 'failed',
            'etsy_tracking_push_error': (message or '')[:_ERROR_TRUNCATE],
            'etsy_tracking_push_at': _fields.Datetime.now(),
            'etsy_tracking_push_attempts': order.etsy_tracking_push_attempts + 1,
        })
        self._audit(
            shop,
            endpoint or 'POST /v3/application/shops/%s/receipts/%s/tracking' % (
                (shop.sudo().etsy_api_shop_id or shop.id) if shop else 0,
                order.etsy_order_id or ''),
            http_status,
            response_summary='API called but failed' if api_called
            else 'Push not attempted (precondition failed)',
            error_message=(message or '')[:_ERROR_TRUNCATE])
        _logger.warning('P1-12: tracking push failed for %s: %s',
                        order.name, message)
        return False

    def _audit(self, shop, endpoint, http_status, response_summary,
               error_message):
        """Write one etsy.api.log row. Plain ORM create — this path runs
        under a request/cron transaction that is NOT rolled back on a
        soft failure (unlike the P1-10 controller scope-validation path
        that needed a fresh cursor), so a durable side-cursor here would
        only break TransactionCase isolation.
        """
        if not shop:
            return
        self.env['etsy.api.log'].create({
            'shop_id': shop.id,
            'endpoint': endpoint,
            'http_status': http_status,
            'source': _AUDIT_SOURCE,
            'response_summary': response_summary,
            'error_message': error_message,
        })
