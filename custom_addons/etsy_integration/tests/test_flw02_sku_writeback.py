"""FLW-02 — persist publish-time variant SKUs (spec 015, product-flow audit
2026-07-06).

`push_inventory` synthesizes `{base}-{SLUG}` SKUs for variants whose
`default_code` is empty and sends them to Etsy — but stored them nowhere.
An order returning with that SKU resolved to NOTHING in Odoo
(`etsy.listing.product._match_variant` and the order-ingest
`_resolve_default_code_product` both key on `default_code`), so the ingest
fell through to name-match and picked an arbitrary variant.

Fix under test: at push time, the synthesized SKU is written back to the
variant's `default_code` (only when empty — operator-set codes never
overwritten), closing the publish→order round-trip.
"""
from odoo.tests.common import tagged

from odoo.addons.etsy_integration.tests.test_p_bug_esty_188_phase2_orm_iter3 import (
    _IterTestBase,
)


@tagged('post_install', '-at_install', 'flw02_sku_writeback')
class TestSynthesizedSkuWriteback(_IterTestBase):

    def _build_template(self, with_default_codes=False):
        attr, values = self._make_size_axis()
        tmpl = self.Template.create({
            'name': 'FLW02 Tray',
            'list_price': 7.0,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attr.id,
                'value_ids': [(6, 0, [v.id for v in values])],
            })],
        })
        tmpl.default_code = 'FT'
        tmpl.x_sku_v2_status = 'ba_approved_legacy'
        if with_default_codes:
            for variant, code in zip(tmpl.product_variant_ids,
                                     ('FT-S', 'FT-M', 'FT-L')):
                variant.default_code = code
        return tmpl

    def _push(self, tmpl, shop, listing_id='LST-FLW02'):
        from unittest.mock import patch
        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )
        listing = self._wire_listing(tmpl, shop, listing_id)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
            return client.put.call_args[1]['json']

    def test_synthesized_sku_written_back_to_empty_default_code(self):
        shop = self._make_shop(api_id='60752341')
        tmpl = self._build_template(with_default_codes=False)
        self.assertFalse(any(tmpl.product_variant_ids.mapped('default_code')))
        payload = self._push(tmpl, shop)
        pushed = sorted(p['sku'] for p in payload['products'])
        stored = sorted(tmpl.product_variant_ids.mapped('default_code'))
        self.assertEqual(
            stored, pushed,
            'every SKU sent to Etsy must be persisted on its variant '
            '(round-trip integrity); pushed=%r stored=%r' % (pushed, stored),
        )

    def test_operator_set_default_code_never_overwritten(self):
        shop = self._make_shop(api_id='60752342')
        tmpl = self._build_template(with_default_codes=True)
        self._push(tmpl, shop)
        self.assertEqual(
            sorted(tmpl.product_variant_ids.mapped('default_code')),
            ['FT-L', 'FT-M', 'FT-S'],
        )

    def test_written_back_sku_resolves_exact_variant(self):
        """Order-ingest resolution path: default_code search must return the
        exact variant the SKU was synthesized for."""
        shop = self._make_shop(api_id='60752343')
        tmpl = self._build_template(with_default_codes=False)
        payload = self._push(tmpl, shop)
        for entry in payload['products']:
            match = self.env['product.product'].search(
                [('default_code', '=', entry['sku'])])
            self.assertEqual(
                len(match), 1,
                'synthesized SKU %r must resolve to exactly one variant'
                % entry['sku'],
            )
            self.assertEqual(match.product_tmpl_id, tmpl)
