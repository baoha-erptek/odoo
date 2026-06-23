import json
from pathlib import Path
from unittest import mock

from odoo.tests.common import TransactionCase, tagged


FIXTURE = Path(__file__).parent / 'fixtures' / 'receipt_3818231452.json'


@tagged('post_install', '-at_install')
class TestEtsyOrderCoverage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].sudo().create({
            'name': 'Coverage Shop',
            'active_source': 'api',
            'etsy_api_shop_id': '60752333',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'refresh',
        })

    def test_receipt_fixture_maps_full_order_coverage(self):
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        receipt = json.loads(FIXTURE.read_text())
        payload = EtsyApiAdapter(mock.Mock())._receipt_to_payload(
            receipt, shop_id=int(self.shop.sudo().etsy_api_shop_id))
        order = OrderCreator(self.env).process_etsy_payload(payload, self.shop)
        # Hybrid reconciliation: gift-wrap (+) and discount (-) are real lines,
        # tax stays informational (Etsy remits it), so amount_total equals the
        # buyer-paid grandtotal MINUS the marketplace-remitted tax.
        self.assertEqual(order.amount_total, 110.5)
        self.assertEqual(
            round(order.amount_total + order.etsy_tax_total, 2),
            payload.amount_total,  # = Etsy grandtotal (115.5)
        )
        self.assertFalse(order.etsy_total_mismatch)
        # Gift-wrap and discount each become their own order line.
        gift_line = order.order_line.filtered(
            lambda line: line.product_id.default_code == 'ETSY-GIFTWRAP')
        discount_line = order.order_line.filtered(
            lambda line: line.product_id.default_code == 'ETSY-DISCOUNT')
        self.assertEqual(gift_line.price_unit, 3.0)
        self.assertEqual(discount_line.price_unit, -2.5)
        self.assertEqual(order.etsy_tax_total, 5.0)
        self.assertEqual(order.etsy_receipt_status, 'paid')
        self.assertFalse(order.etsy_is_shipped)
        self.assertEqual(order.etsy_discount_amount, 2.5)
        self.assertTrue(order.etsy_needs_gift_wrap)
        line = order.order_line.filtered('etsy_transaction_id')
        self.assertEqual(line.etsy_color, 'Blue')
        self.assertEqual(line.etsy_size, 'Large')
        self.assertIn('Finish: Glossy', line.etsy_option)
        self.assertEqual(
            line.etsy_image_url,
            'https://i.etsystatic.com/test/custom-mug.jpg',
        )

    def test_total_mismatch_flags_order_without_raising(self):
        """An unreconcilable grandtotal flags the order, never blocks ingest.

        A hard failure here would wedge the sync cursor on the first taxed
        order (the syncer breaks without advancing on any exception).
        """
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        receipt = json.loads(FIXTURE.read_text())
        # Corrupt grandtotal so amount_total cannot reconcile (off by 50).
        receipt['grandtotal'] = {
            'amount': 16550, 'divisor': 100, 'currency_code': 'USD'}
        payload = EtsyApiAdapter(mock.Mock())._receipt_to_payload(
            receipt, shop_id=int(self.shop.sudo().etsy_api_shop_id))
        order = OrderCreator(self.env).process_etsy_payload(payload, self.shop)
        self.assertTrue(order)  # ingest succeeded, no UserError
        self.assertTrue(order.etsy_total_mismatch)


@tagged('post_install', '-at_install')
class TestEtsyLineProductResolution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].sudo().create({'name': 'Resolver Shop'})

    def _creator(self):
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        return OrderCreator(self.env)

    def _product(self, name, sku=False):
        return self.env['product.product'].create({
            'name': name,
            'default_code': sku or False,
        })

    def test_sku_listing_product_hit_prefers_matching_listing(self):
        product_a = self._product('Linked A', 'SKU-LINK')
        product_b = self._product('Linked B', 'SKU-LINK')
        listing_a = self.env['etsy.listing'].create({
            'shop_id': self.shop.id,
            'etsy_listing_id': '111',
            'title': 'Listing A',
            'state': 'active',
        })
        listing_b = self.env['etsy.listing'].create({
            'shop_id': self.shop.id,
            'etsy_listing_id': '222',
            'title': 'Listing B',
            'state': 'active',
        })
        self.env['etsy.listing.product'].create({
            'listing_id': listing_a.id,
            'etsy_product_id': 'p1',
            'sku': 'SKU-LINK',
            'product_id': product_a.id,
        })
        self.env['etsy.listing.product'].create({
            'listing_id': listing_b.id,
            'etsy_product_id': 'p2',
            'sku': 'SKU-LINK',
            'product_id': product_b.id,
        })
        resolved = self._creator()._resolve_line_product(
            'SKU-LINK', 'Unused', listing_id='222')
        self.assertEqual(resolved, product_b)

    def test_default_code_hit_does_not_create(self):
        product = self._product('Default Code Product', 'SKU-DC')
        before = self.env['product.product'].search_count([])
        resolved = self._creator()._resolve_line_product('SKU-DC', 'New Name')
        self.assertEqual(resolved, product)
        self.assertEqual(self.env['product.product'].search_count([]), before)

    def test_name_hit(self):
        product = self._product('Exact Name Product')
        resolved = self._creator()._resolve_line_product('', 'Exact Name Product')
        self.assertEqual(resolved, product)

    def test_create_and_flag_on_miss(self):
        resolved = self._creator()._resolve_line_product(
            'SKU-MISS', 'Auto Created Product')
        self.assertEqual(resolved.name, 'Auto Created Product')
        self.assertTrue(resolved.etsy_needs_product_review)

    def test_duplicate_default_code_uses_first_by_id(self):
        first = self._product('Duplicate First', 'SKU-DUP')
        self._product('Duplicate Second', 'SKU-DUP')
        resolved = self._creator()._resolve_line_product('SKU-DUP', 'Unused')
        self.assertEqual(resolved, first)
