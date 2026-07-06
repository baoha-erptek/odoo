"""FLW-01 — variant-level Gearment mapping (spec 015, product-flow audit 2026-07-06).

`x_gearment_sku` is template-level, but Gearment's `variant_id` encodes
color+size — a multi-variant template pushed every variant with the SAME GM
id. Standard-Odoo-First fix: the Gearment vendor's `product.supplierinfo`
row pinned to the exact variant (`product_id` set) carries the GM variant_id
in the standard `product_code` field. Template `x_gearment_sku` remains the
route/vendor marker and the fallback for single-variant products.

Push is the hard gate: `build_payload` raises on a multi-variant template
whose ordered variant has no variant-specific vendor code.
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services import (
    gearment_payload_builder,
)


class _VariantSkuBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.gearment = self.env.ref(
            'multichannel_hub_fulfillment.partner_gearment_vendor')
        self.partner = self.env['res.partner'].create({
            'name': 'Buyer Variant',
            'street': '123 Main St',
            'city': 'Boston',
            'state_id': self.env.ref('base.state_us_22').id,
            'zip': '02108',
            'country_id': self.env.ref('base.us').id,
        })
        size = self.env['product.attribute'].create({
            'name': 'FLW01 Size',
            'value_ids': [(0, 0, {'name': 'S'}), (0, 0, {'name': 'M'})],
        })
        self.tmpl_multi = self.env['product.template'].create({
            'name': 'FLW01 Tee', 'type': 'consu', 'list_price': 9.0,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': size.id,
                'value_ids': [(6, 0, size.value_ids.ids)],
            })],
        })
        self.tmpl_multi.x_gearment_sku = 'GM-TEMPLATE-BASE'
        self.var_s, self.var_m = self.tmpl_multi.product_variant_ids

        tmpl_single = self.env['product.template'].create({
            'name': 'FLW01 Mug', 'type': 'consu', 'list_price': 5.0,
        })
        tmpl_single.x_gearment_sku = 'GM0249020374'
        self.var_single = tmpl_single.product_variant_ids

    def _map_variant(self, variant, code, partner=None):
        return self.env['product.supplierinfo'].create({
            'partner_id': (partner or self.gearment).id,
            'product_tmpl_id': variant.product_tmpl_id.id,
            'product_id': variant.id,
            'product_code': code,
        })

    def _order(self, *variants):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': v.id, 'product_uom_qty': 1})
                for v in variants
            ],
        })
        for line in order.order_line:
            self.env['design.file'].create({
                'name': f'art {line.id}',
                'order_line_id': line.id,
                'file_url': f'https://x/{line.id}.png',
                'storage_mode': 'url',
                'state': 'approved',
            })
        return order

    def _files(self, order):
        return order.order_line.design_file_ids


@tagged('post_install', '-at_install', 'flw01_variant_sku')
class TestVariantSkuResolution(_VariantSkuBase):
    """product.product._gearment_resolved_sku() resolution order."""

    def test_variant_supplierinfo_code_wins_over_template(self):
        self._map_variant(self.var_s, 'GM-VAR-S')
        self.assertEqual(self.var_s._gearment_resolved_sku(), 'GM-VAR-S')

    def test_template_fallback_when_no_variant_row(self):
        self.assertEqual(
            self.var_single._gearment_resolved_sku(), 'GM0249020374')

    def test_other_vendor_code_is_ignored(self):
        other = self.env['res.partner'].create({'name': 'Other Vendor'})
        self._map_variant(self.var_s, 'OTHER-1', partner=other)
        self.assertEqual(
            self.var_s._gearment_resolved_sku(), 'GM-TEMPLATE-BASE')

    def test_sibling_variant_row_not_used(self):
        """A code pinned to variant S must not leak onto variant M."""
        self._map_variant(self.var_s, 'GM-VAR-S')
        self.assertEqual(
            self.var_m._gearment_resolved_sku(), 'GM-TEMPLATE-BASE')


@tagged('post_install', '-at_install', 'flw01_variant_sku')
class TestPayloadVariantIds(_VariantSkuBase):
    """build_payload keys line items by the per-variant GM id."""

    def test_multi_variant_order_pushes_distinct_gm_ids(self):
        self._map_variant(self.var_s, 'GM-VAR-S')
        self._map_variant(self.var_m, 'GM-VAR-M')
        order = self._order(self.var_s, self.var_m)
        payload = gearment_payload_builder.build_payload(
            order, self._files(order))
        ids = sorted(item.variant_id for item in payload.line_items)
        self.assertEqual(ids, ['GM-VAR-M', 'GM-VAR-S'])

    def test_multi_variant_template_only_sku_raises(self):
        order = self._order(self.var_s)
        with self.assertRaises(UserError) as cm:
            gearment_payload_builder.build_payload(order, self._files(order))
        self.assertIn('FLW01 Tee', str(cm.exception))

    def test_single_variant_template_sku_unchanged(self):
        """Regression — MF-E2E-3b single-variant shape must not change."""
        order = self._order(self.var_single)
        payload = gearment_payload_builder.build_payload(
            order, self._files(order))
        self.assertEqual(payload.line_items[0].variant_id, 'GM0249020374')

    def test_quote_body_uses_variant_code(self):
        self._map_variant(self.var_s, 'GM-VAR-S')
        order = self._order(self.var_s)
        body = gearment_payload_builder.build_quote_body(
            order, self._files(order))
        self.assertEqual(body['line_items'][0]['variant_id'], 'GM-VAR-S')
