"""FLW-04 — Etsy shipping service → Gearment shipping_method (spec 015,
product-flow audit 2026-07-06).

Only METHOD_STANDARD is proven on the Gearment wire (live 200, 2026-07-05);
the vendor doc crawl exposes no other MethodType enum values, so mapping to
unverified METHOD_* constants would 400 the draft. This slice therefore:

- routes the payload's shipping_method through a resolver seam
  (`_resolve_shipping_method`) keyed off the channel-agnostic
  `sale.order.shipping_service_label`, and
- replaces the SILENT downgrade with a loud WARNING when the buyer paid
  for an expedited Etsy service — the actual harm found by the audit.

Once Gearment confirms its MethodType enum, the mapping table in the
resolver grows entries with no structural change.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services import (
    gearment_payload_builder,
)


@tagged('post_install', '-at_install', 'flw04_shipping_method')
class TestShippingMethodResolution(TransactionCase):

    def setUp(self):
        super().setUp()
        partner = self.env['res.partner'].create({
            'name': 'Buyer Method',
            'street': '123 Main St',
            'city': 'Boston',
            'state_id': self.env.ref('base.state_us_22').id,
            'zip': '02108',
            'country_id': self.env.ref('base.us').id,
        })
        product = self.env['product.product'].create({
            'name': 'Method Mug', 'type': 'consu', 'list_price': 9.0,
        })
        product.product_tmpl_id.x_gearment_sku = 'GM0249020374'
        self.product = product
        self.partner = partner

    def _order(self, shipping_service=''):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'shipping_service_label': shipping_service,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1,
            })],
        })
        self.env['design.file'].create({
            'name': 'art',
            'order_line_id': order.order_line[0].id,
            'file_url': 'https://x/a.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        return order

    def _push(self, order):
        return gearment_payload_builder.build_payload(
            order, order.order_line.design_file_ids)

    def test_standard_service_maps_to_method_standard(self):
        order = self._order('Standard Shipping')
        self.assertEqual(self._push(order).shipping_method, 'METHOD_STANDARD')

    def test_empty_service_defaults_to_method_standard(self):
        order = self._order('')
        self.assertEqual(self._push(order).shipping_method, 'METHOD_STANDARD')

    def test_expedited_service_warns_instead_of_silent_downgrade(self):
        order = self._order('USPS Priority Mail Express')
        with self.assertLogs(
            'odoo.addons.multichannel_hub_fulfillment.services.'
            'gearment_payload_builder',
            level='WARNING',
        ) as logs:
            payload = self._push(order)
        self.assertEqual(payload.shipping_method, 'METHOD_STANDARD')
        joined = '\n'.join(logs.output)
        self.assertIn(order.name, joined)
        self.assertIn('Priority Mail Express', joined)

    def test_standard_service_does_not_warn(self):
        order = self._order('Standard Int\'l Postage')
        try:
            with self.assertLogs(
                'odoo.addons.multichannel_hub_fulfillment.services.'
                'gearment_payload_builder',
                level='WARNING',
            ):
                self._push(order)
        except AssertionError:
            return  # no warnings — expected
        self.fail('standard service must not trigger the expedited warning')
