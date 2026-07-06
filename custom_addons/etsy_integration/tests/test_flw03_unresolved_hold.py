"""FLW-03 — unresolved-line hold for API ingest (spec 015, product-flow
audit 2026-07-06).

The API ingest path used the email path's forgiving fallback: unknown SKU →
name-match (`('name','=',title)` limit 1 — all variants share the template
name, so it picked the lowest-id variant) → `find_or_create_product`, which
created a brand-new product with no Gearment SKU and no pipeline, silently
routing a dropship order onto the default MTO pipeline.

Fix under test: on the API path, a line whose SKU cannot be resolved via
`etsy.listing.product` or `default_code` books against the shared
"Etsy Unresolved Item" placeholder product and the order is held —
`production_blocked=True` with a block_reason naming the unresolved lines.
The legacy email path (`process_parse_result`) keeps auto-create.
"""
from datetime import datetime

from odoo.tests.common import TransactionCase, tagged


def _build_payload(**overrides):
    from odoo.addons.etsy_integration.services.etsy_order_payload import (
        EtsyAddressPayload,
        EtsyLineItemPayload,
        EtsyOrderPayload,
    )
    defaults = dict(
        etsy_shop_id=1,
        etsy_receipt_id="REC-FLW03",
        etsy_order_id="ORD-FLW03",
        buyer_name="Holly Holder",
        buyer_country="US",
        order_date=datetime(2026, 7, 6, 10, 0, 0),
        currency="USD",
        amount_total=25.00,
        shipping_total=0.00,
        line_items=(
            EtsyLineItemPayload(
                listing_id="L-FLW03",
                transaction_id="T-FLW03-1",
                title="Mystery Tee Black XL",
                sku="NO-SUCH-SKU-XL",
                quantity=1,
                unit_price=25.00,
            ),
        ),
        shipping_address=EtsyAddressPayload(
            name="Holly Holder",
            street_1="1 Hold St",
            street_2=None,
            city="Boston",
            state="MA",
            zip="02108",
            country_code="US",
        ),
        buyer_message=None,
        buyer_email="holly-flw03@example.com",
        listing_id="L-FLW03",
        payment_status="paid",
        is_gift=False,
        gift_message=None,
        source="api",
        fetched_at=datetime(2026, 7, 6, 10, 5, 0),
        raw_source_id="receipt:REC-FLW03",
    )
    defaults.update(overrides)
    return EtsyOrderPayload(**defaults)


@tagged('post_install', '-at_install', 'flw03_unresolved_hold')
class TestApiUnresolvedLineHold(TransactionCase):

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        self.creator = OrderCreator(self.env)
        self.shop = self.env['etsy.shop'].create({'name': 'FLW03Shop'})

    def _line(self, **kw):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        defaults = dict(
            listing_id="L-FLW03", transaction_id="T-FLW03-X",
            title="Mystery Tee", sku="NO-SUCH-SKU",
            quantity=1, unit_price=10.0,
        )
        defaults.update(kw)
        return EtsyLineItemPayload(**defaults)

    def test_unknown_sku_does_not_create_product(self):
        before = self.env['product.product'].search_count([])
        order = self.creator.process_etsy_payload(_build_payload(), self.shop)
        after = self.env['product.product'].search_count([])
        self.assertTrue(order)
        self.assertEqual(
            after, before,
            'API ingest must not auto-create products for unknown SKUs',
        )

    def test_unknown_sku_books_placeholder_and_blocks_production(self):
        order = self.creator.process_etsy_payload(_build_payload(), self.shop)
        placeholder = self.env.ref(
            'etsy_integration.product_etsy_unresolved')
        self.assertEqual(
            order.order_line[0].product_id,
            placeholder.product_variant_id,
        )
        self.assertTrue(order.production_blocked)
        self.assertIn('NO-SUCH-SKU-XL', order.block_reason)

    def test_unknown_sku_keeps_buyer_facing_line_name(self):
        order = self.creator.process_etsy_payload(_build_payload(), self.shop)
        self.assertIn('Mystery Tee Black XL', order.order_line[0].name)

    def test_known_default_code_still_resolves_and_no_block(self):
        tee = self.env['product.product'].create({
            'name': 'FLW03 Known Tee', 'type': 'consu',
            'default_code': 'FLW03-KNOWN',
        })
        payload = _build_payload(
            etsy_order_id="ORD-FLW03-OK",
            etsy_receipt_id="REC-FLW03-OK",
            line_items=(self._line(
                transaction_id="T-FLW03-OK", sku="FLW03-KNOWN"),),
        )
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertEqual(order.order_line[0].product_id, tee)
        self.assertFalse(order.production_blocked)

    def test_no_sku_line_is_held_not_name_matched(self):
        """A line without any SKU must hold, not match by title (title match
        across variants picks an arbitrary sibling)."""
        decoy = self.env['product.product'].create({
            'name': 'Mystery Tee', 'type': 'consu',
        })
        payload = _build_payload(
            etsy_order_id="ORD-FLW03-NOSKU",
            etsy_receipt_id="REC-FLW03-NOSKU",
            line_items=(self._line(
                transaction_id="T-FLW03-NOSKU", title="Mystery Tee", sku=""),),
        )
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertNotEqual(order.order_line[0].product_id, decoy)
        self.assertTrue(order.production_blocked)

    def test_mixed_order_blocks_but_keeps_resolved_line(self):
        known = self.env['product.product'].create({
            'name': 'FLW03 Mug', 'type': 'consu',
            'default_code': 'FLW03-MUG',
        })
        payload = _build_payload(
            etsy_order_id="ORD-FLW03-MIX",
            etsy_receipt_id="REC-FLW03-MIX",
            line_items=(
                self._line(transaction_id="T-FLW03-M1", sku="FLW03-MUG"),
                self._line(transaction_id="T-FLW03-M2", sku="GONE-1",
                           title="Vanished Tote"),
            ),
        )
        order = self.creator.process_etsy_payload(payload, self.shop)
        products = order.order_line.mapped('product_id')
        self.assertIn(known, products)
        self.assertTrue(order.production_blocked)
        self.assertIn('GONE-1', order.block_reason)
        self.assertNotIn('FLW03-MUG', order.block_reason)
