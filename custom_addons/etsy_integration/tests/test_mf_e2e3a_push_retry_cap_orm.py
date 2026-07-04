"""MF-E2E-3a Phase 2 ORM — tracking-push retry cap.

Repro (2026-07-04, staging): `_cron_push_tracking` re-picks any order with
status in (none, pending, failed) forever — a permanently-failing order
(legacy shop without etsy_api_shop_id) was retried every 5 minutes since
deployment, flooding etsy.api.log with guard rows. Contract pinned here:

- every failed push increments `etsy_tracking_push_attempts`
- a successful push resets the counter
- the cron skips orders at/over `_MAX_TRACKING_PUSH_ATTEMPTS`
- the manual form button is NOT capped (operator override)
"""

from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.models.sale_order import (
    _MAX_TRACKING_PUSH_ATTEMPTS,
)
from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
    EtsyTrackingPusher,
)


@tagged('post_install', '-at_install')
class TestTrackingPushRetryCap(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Cap Test Shop',
            # deliberately NO etsy_api_shop_id → push always guard-fails
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Cap Buyer'})
        cls.product = cls.env['product.product'].create({
            'name': 'Cap Product', 'list_price': 10.0,
        })
        cls.carrier = cls.env['shipping.carrier'].create({
            'name': 'Cap USPS', 'code': 'cap_usps',
            'etsy_carrier_name': 'usps',
        })

    def _order_with_tracking(self, attempts=0):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_order_id': 'cap-%s-%s' % (id(self), attempts),
            'etsy_shop_id': self.shop.id,
            'etsy_tracking_push_attempts': attempts,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0, 'price_unit': 10.0,
            })],
        })
        self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899220000000001',
            'shipping_carrier_id': self.carrier.id,
        })
        return order

    def test_failed_push_increments_attempts(self):
        order = self._order_with_tracking()
        self.assertEqual(order.etsy_tracking_push_attempts, 0)
        EtsyTrackingPusher(self.env).push(order)  # guard-fails: no api shop id
        self.assertEqual(order.etsy_tracking_push_status, 'failed')
        self.assertEqual(order.etsy_tracking_push_attempts, 1)
        EtsyTrackingPusher(self.env).push(order)
        self.assertEqual(order.etsy_tracking_push_attempts, 2)

    def test_successful_push_resets_attempts(self):
        shop_ok = self.env['etsy.shop'].create({
            'name': 'Cap OK Shop', 'etsy_api_shop_id': '60752399',
        })
        order = self._order_with_tracking(attempts=3)
        order.etsy_shop_id = shop_ok
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as ClientCls:
            client = mock.MagicMock()
            # push_tracking returns (ok, err, http_status)
            client.push_tracking.return_value = (True, '', 200)
            client.last_http_status = 200
            ClientCls.return_value = client
            ok = EtsyTrackingPusher(self.env).push(order)
        self.assertTrue(ok)
        self.assertEqual(order.etsy_tracking_push_attempts, 0)

    def test_cron_skips_orders_at_cap(self):
        capped = self._order_with_tracking(attempts=_MAX_TRACKING_PUSH_ATTEMPTS)
        capped.etsy_tracking_push_status = 'failed'
        fresh = self._order_with_tracking(attempts=0)
        fresh.etsy_order_id = 'cap-fresh-%s' % id(self)
        fresh.etsy_tracking_push_status = 'failed'
        with mock.patch.object(EtsyTrackingPusher, 'push') as push_mock:
            self.env['sale.order']._cron_push_tracking()
        pushed_orders = {c.args[0].id for c in push_mock.call_args_list}
        self.assertNotIn(capped.id, pushed_orders,
                         'cron must skip orders at the retry cap')
        self.assertIn(fresh.id, pushed_orders,
                      'cron must still push orders below the cap')
