"""FLW-07 — Etsy quantity top-up cron for POD listings (spec 015,
product-flow audit 2026-07-06).

Quantity is pushed once at publish; Etsy decrements it per sale, and a
listing that hits 0 is auto-deactivated (lost sales). POD products carry no
Odoo stock, so re-pushing `qty_available` is meaningless — the cron re-pushes
a configured TARGET quantity to every active listing whose mirrored variant
quantity (`etsy.listing.product.quantity`) dropped below it.

Killswitch + target in one ICP: `etsy_integration.pod_topup_quantity`
(absent/0 = disabled — ships OFF; owner sets e.g. 50 to go live).
"""
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.tests.test_p_bug_esty_188_phase2_orm_iter3 import (
    _IterTestBase,
)

_ICP = 'etsy_integration.pod_topup_quantity'


@tagged('post_install', '-at_install', 'flw07_qty_topup')
class TestQtyTopupCron(_IterTestBase):

    def _wire(self, api_id, listing_id, qty, state='active'):
        shop = self._make_shop(name='TOPUP %s' % listing_id, api_id=api_id)
        tmpl = self.Template.create({
            'name': 'Topup Mug %s' % listing_id, 'type': 'consu',
            'list_price': 9.0, 'default_code': 'TU-%s' % listing_id,
        })
        tmpl.x_sku_v2_status = 'ba_approved_legacy'
        listing = self._wire_listing(tmpl, shop, listing_id)
        listing.state = state
        self.env['etsy.listing.product'].create({
            'listing_id': listing.id,
            'etsy_product_id': 'EP-%s' % listing_id,
            'sku': tmpl.default_code,
            'quantity': qty,
            'product_id': tmpl.product_variant_id.id,
        })
        return shop, tmpl, listing

    def _run_cron(self):
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            self.env['etsy.listing']._cron_topup_pod_quantities()
            return client

    def test_disabled_by_default_no_api_calls(self):
        self._wire('60752351', 'LST-TU-OFF', qty=1)
        client = self._run_cron()
        client.put.assert_not_called()

    def test_low_qty_listing_repushed_with_target(self):
        self.env['ir.config_parameter'].sudo().set_param(_ICP, '50')
        self._wire('60752352', 'LST-TU-LOW', qty=2)
        client = self._run_cron()
        self.assertTrue(client.put.called)
        body = client.put.call_args[1]['json']
        self.assertEqual(body['products'][0]['offerings'][0]['quantity'], 50)

    def test_healthy_listing_not_touched(self):
        self.env['ir.config_parameter'].sudo().set_param(_ICP, '50')
        self._wire('60752353', 'LST-TU-OK', qty=50)
        client = self._run_cron()
        client.put.assert_not_called()

    def test_inactive_listing_not_touched(self):
        self.env['ir.config_parameter'].sudo().set_param(_ICP, '50')
        self._wire('60752354', 'LST-TU-INACT', qty=1, state='inactive')
        client = self._run_cron()
        client.put.assert_not_called()

    def test_one_failing_listing_does_not_block_others(self):
        self.env['ir.config_parameter'].sudo().set_param(_ICP, '50')
        self._wire('60752355', 'LST-TU-A', qty=1)
        self._wire('60752356', 'LST-TU-B', qty=1)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.side_effect = [Exception('etsy 500'), {'products': []}]
            self.env['etsy.listing']._cron_topup_pod_quantities()
            self.assertEqual(client.put.call_count, 2)
