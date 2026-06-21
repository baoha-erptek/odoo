"""Phase D#8 — Fulfillment Tracking Detail (Flow 3b mockup screen 5).

Surfaces Gearment-specific provenance on the fulfillment record and wires the
webhook dispatcher to populate it:

- ``gearment_order_ref``        — mirrors the order's Gearment outbound ref.
- ``gearment_last_webhook_at``  — stamped on every inbound business webhook.
- ``gearment_last_webhook_topic`` — which topic last touched the fulfillment.
- ``etsy_tracking_pushed`` / ``_at`` — set when the post-tracking Etsy push
  succeeds (the Flow 3b "tracking pushed back to Etsy" signal).
"""
from unittest import mock

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services.gearment_webhook_dispatcher import (
    GearmentWebhookDispatcher,
)

_PUSHER_PATH = (
    'odoo.addons.etsy_integration.services.etsy_tracking_pusher.'
    'EtsyTrackingPusher.push'
)


@tagged('post_install', '-at_install')
class TestFulfillmentDetail(TransactionCase):

    def setUp(self):
        super().setUp()
        self.dispatcher = GearmentWebhookDispatcher(self.env)
        self.partner = self.env['res.partner'].create({'name': 'D8 Partner'})

    def _order(self, name):
        # fulfillment_id auto-created via _inherits direction-A on sale.order.
        return self.env['sale.order'].create({
            'name': name, 'partner_id': self.partner.id,
        })

    def _body(self, reference, tracking=None, status=None):
        body = {'order': {'reference': reference, 'status': status or ''}}
        if tracking:
            body['tracking'] = tracking
        return body

    def test_new_fields_default(self):
        f = self._order('SO-D8-DEFAULT').fulfillment_id
        self.assertFalse(f.etsy_tracking_pushed)
        self.assertFalse(f.etsy_tracking_pushed_at)
        self.assertFalse(f.gearment_last_webhook_at)
        self.assertFalse(f.gearment_last_webhook_topic)

    def test_gearment_order_ref_mirrors_outbound_ref(self):
        order = self._order('SO-D8-REF')
        order.write({'x_gearment_outbound_ref': 'GMT-ORDER-7788'})
        self.assertEqual(order.fulfillment_id.gearment_order_ref, 'GMT-ORDER-7788')

    def test_order_completed_stamps_webhook(self):
        order = self._order('SO-D8-COMPLETE')
        self.dispatcher.dispatch('order_completed', self._body(
            'SO-D8-COMPLETE',
            tracking={'company': 'USPS', 'number': 'TRK-D8-1'}))
        f = order.fulfillment_id
        self.assertTrue(f.gearment_last_webhook_at)
        self.assertEqual(f.gearment_last_webhook_topic, 'order_completed')

    def test_tracking_update_stamps_webhook_topic(self):
        order = self._order('SO-D8-TRACK')
        self.dispatcher.dispatch('tracking_order_updated', self._body(
            'SO-D8-TRACK', tracking={'number': 'TRK-D8-2', 'company': 'UniUni'}))
        self.assertEqual(
            order.fulfillment_id.gearment_last_webhook_topic,
            'tracking_order_updated')

    def test_tracking_update_does_not_change_tracking_state(self):
        # tracking_order_updated refreshes carrier/number/url only; ship-state
        # transitions belong to other topics. Guard the invariant.
        order = self._order('SO-D8-TRACK-STATE')
        order.fulfillment_id.with_context(
            bypass_address_change_check=True,
        ).write({'tracking_state': 'label_requested'})
        self.dispatcher.dispatch('tracking_order_updated', self._body(
            'SO-D8-TRACK-STATE', tracking={'number': 'TRK-D8-5', 'company': 'USPS'}))
        self.assertEqual(
            order.fulfillment_id.tracking_state, 'label_requested')

    def test_on_hold_stamps_webhook(self):
        order = self._order('SO-D8-HOLD')
        self.dispatcher.dispatch('order_on_hold', self._body(
            'SO-D8-HOLD', status='waiting'))
        self.assertEqual(
            order.fulfillment_id.gearment_last_webhook_topic, 'order_on_hold')

    def test_etsy_tracking_pushed_set_on_successful_push(self):
        shop = self.env['etsy.shop'].create({
            'name': 'D8 Shop', 'etsy_api_shop_id': '99999777'})
        order = self._order('SO-D8-ETSYPUSH')
        order.write({'etsy_order_id': 'ETSY-RCPT-1', 'etsy_shop_id': shop.id})
        with mock.patch(_PUSHER_PATH, return_value=None) as pusher:
            self.dispatcher.dispatch('tracking_order_updated', self._body(
                'SO-D8-ETSYPUSH',
                tracking={'number': 'TRK-D8-3', 'company': 'USPS'}))
        pusher.assert_called_once()
        f = order.fulfillment_id
        self.assertTrue(f.etsy_tracking_pushed)
        self.assertTrue(f.etsy_tracking_pushed_at)

    def test_etsy_tracking_not_pushed_when_no_etsy_link(self):
        # No etsy_order_id/shop → push branch skipped → flag stays False.
        order = self._order('SO-D8-NOETSY')
        self.dispatcher.dispatch('tracking_order_updated', self._body(
            'SO-D8-NOETSY', tracking={'number': 'TRK-D8-4', 'company': 'USPS'}))
        self.assertFalse(order.fulfillment_id.etsy_tracking_pushed)
