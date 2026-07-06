"""FLW-05 — personalization vs the Gearment draft wire (spec 015,
product-flow audit 2026-07-06).

Vendor contract check (docs/vendor/gearment/api_api.order.v1.vendororderapi.md):
the draft request's line_items schema is {variant_id, legacy_id, quantity,
printing_options, barcode_url} — there is NO per-line personalization text
field. The order-level `gift_message_body` IS part of the draft request
(adds a fee, which the buyer already paid on Etsy).

So the audit's FLW-05 lands inverted:
- STOP emitting `personalisation` on line items — Gearment's strict proto
  validator 400s on wrong shapes (Defect-2026-05-10-05 history); the field
  only rode along safely so far because it was always empty (None dropped).
  Personalization text reaches production via the DESIGN workflow (baked
  into the approved artwork); the buyer text stays visible on the order line.
- START emitting `gift_message_body` from the channel-agnostic
  `sale.order.gift_message` shadow — a real, documented draft field.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services import (
    gearment_payload_builder,
)


@tagged('post_install', '-at_install', 'flw05_personalization_wire')
class TestPersonalizationWire(TransactionCase):

    def setUp(self):
        super().setUp()
        partner = self.env['res.partner'].create({
            'name': 'Buyer Gift',
            'street': '123 Main St',
            'city': 'Boston',
            'state_id': self.env.ref('base.state_us_22').id,
            'zip': '02108',
            'country_id': self.env.ref('base.us').id,
        })
        product = self.env['product.product'].create({
            'name': 'Gift Mug', 'type': 'consu', 'list_price': 9.0,
        })
        product.product_tmpl_id.x_gearment_sku = 'GM0249020374'
        self.product = product
        self.partner = partner

    def _order(self, gift_message=''):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'gift_message': gift_message,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1,
            })],
        })
        line = order.order_line[0]
        for fname in ('personalisation', 'etsy_personalisation'):
            if fname in line._fields:
                line[fname] = 'Name: MAX'
        self.env['design.file'].create({
            'name': 'art',
            'order_line_id': line.id,
            'file_url': 'https://x/a.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        return order

    def _body(self, order):
        payload = gearment_payload_builder.build_payload(
            order, order.order_line.design_file_ids)
        return payload.serialize()

    def test_line_items_carry_no_personalisation_key(self):
        """Unknown fields risk a strict-validator 400 — must stay off wire."""
        body = self._body(self._order())
        for item in body['data']['line_items']:
            self.assertNotIn('personalisation', item)
            self.assertNotIn('personalization', item)

    def test_gift_message_emitted_as_gift_message_body(self):
        body = self._body(self._order(gift_message='Happy Birthday - S.'))
        self.assertEqual(
            body['data'].get('gift_message_body'), 'Happy Birthday - S.')

    def test_no_gift_message_key_when_empty(self):
        body = self._body(self._order(gift_message=''))
        self.assertNotIn('gift_message_body', body['data'])
