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
        # Make the receipt currency the company currency so the
        # normalize-at-ingest conversion (P1-ORD-CURRENCY-NORMALIZE) is an
        # identity here — the conversion path has its own dedicated test below.
        receipt['grandtotal']['currency_code'] = self.env.company.currency_id.name
        payload = EtsyApiAdapter(mock.Mock())._receipt_to_payload(
            receipt, shop_id=int(self.shop.sudo().etsy_api_shop_id))
        order = OrderCreator(self.env).process_etsy_payload(payload, self.shop)
        # Order is booked in the company currency.
        self.assertEqual(order.currency_id, self.env.company.currency_id)
        # Shipping (+) and gift-wrap (+) are real lines; the coupon is a per-line
        # discount %; tax stays informational (Etsy remits it). So amount_total
        # equals the buyer-paid grandtotal MINUS the marketplace-remitted tax.
        self.assertEqual(order.amount_total, 110.5)
        self.assertEqual(
            round(order.amount_total + order.etsy_tax_total, 2),
            payload.amount_total,  # = Etsy grandtotal (115.5)
        )
        self.assertFalse(order.etsy_total_mismatch)
        # Gift-wrap is its own order line; the coupon is NOT a line anymore.
        gift_line = order.order_line.filtered(
            lambda line: line.product_id.default_code == 'ETSY-GIFTWRAP')
        self.assertEqual(gift_line.price_unit, 3.0)
        self.assertFalse(order.order_line.filtered(
            lambda line: line.product_id.default_code == 'ETSY-DISCOUNT'))
        # P1-ORD-DISCOUNT-PCT — coupon (2.5) over pre-discount total (100) = 2.5%
        # booked on the product line's native discount field.
        product_line = order.order_line.filtered('etsy_transaction_id')
        self.assertEqual(product_line.discount, 2.5)
        self.assertEqual(order.etsy_tax_total, 5.0)
        self.assertEqual(order.etsy_receipt_status, 'paid')
        self.assertFalse(order.etsy_is_shipped)
        # Raw Etsy figure retained for audit.
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
            'amount': 16550, 'divisor': 100,
            'currency_code': self.env.company.currency_id.name}
        payload = EtsyApiAdapter(mock.Mock())._receipt_to_payload(
            receipt, shop_id=int(self.shop.sudo().etsy_api_shop_id))
        order = OrderCreator(self.env).process_etsy_payload(payload, self.shop)
        self.assertTrue(order)  # ingest succeeded, no UserError
        self.assertTrue(order.etsy_total_mismatch)

    def test_foreign_currency_normalized_to_company(self):
        """A receipt in a non-company currency is converted at ingest; the order
        is booked in the company currency while the raw etsy_* figures keep the
        original-currency magnitudes (P1-ORD-CURRENCY-NORMALIZE)."""
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        company_currency = self.env.company.currency_id
        # A foreign currency (VND ships in base ISO 4217 data); activate it and
        # pin a deterministic rate so the conversion is exact.
        foreign = self.env.ref('base.VND')
        if not foreign.active:
            foreign.sudo().active = True
        self.env['res.currency.rate'].sudo().create({
            'name': '2020-01-01',
            'currency_id': foreign.id,
            'company_id': self.env.company.id,
            'rate': 1000.0,  # 1 company-unit = 1000 foreign units
        })
        receipt = json.loads(FIXTURE.read_text())
        # Restate every money node in the foreign currency, divisor 1. The
        # source values use divisor 100 (cents); *10 keeps the cent precision
        # (e.g. 250 cents -> 2500 VND) once the divisor drops to 1.
        for node in ('grandtotal', 'subtotal', 'total_price',
                     'total_shipping_cost', 'total_tax_cost', 'total_vat_cost',
                     'discount_amt', 'gift_wrap_price'):
            if node in receipt:
                receipt[node] = {
                    'amount': receipt[node]['amount'] * 10,
                    'divisor': 1, 'currency_code': 'VND'}
        for txn in receipt['transactions']:
            txn['price'] = {
                'amount': txn['price']['amount'] * 10,
                'divisor': 1, 'currency_code': 'VND'}
        payload = EtsyApiAdapter(mock.Mock())._receipt_to_payload(
            receipt, shop_id=int(self.shop.sudo().etsy_api_shop_id))
        order = OrderCreator(self.env).process_etsy_payload(payload, self.shop)
        # Booked in company currency, not VND.
        self.assertEqual(order.currency_id, company_currency)
        # 100_000 VND product line / 1000 rate = 100 company units, less 2.5%
        # discount = 97.5; + shipping 10 + gift 3 = 110.5 company units.
        self.assertAlmostEqual(order.amount_total, 110.5, places=2)
        # Raw audit figure keeps the VND magnitude (discount 2500 VND).
        self.assertAlmostEqual(order.etsy_discount_amount, 2500.0, places=2)


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
