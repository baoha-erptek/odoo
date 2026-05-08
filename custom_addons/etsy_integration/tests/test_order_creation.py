"""Integration tests for order creation in Odoo.

These tests require a running Odoo environment (TransactionCase).
"""
from odoo.tests.common import TransactionCase


class TestOrderCreation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _make_parse_result(self, order_id='TEST001', shop='Viktor',
                            transaction_id='TXN001', product_name='Test Ring Dish',
                            price=19.70, quantity=1):
        """Helper to create a ParseResult-like object for testing."""
        from ..services.email_parser import (
            ParseResult, ShippingAddress, Transaction,
        )
        return ParseResult(
            order_id=order_id,
            shop=shop,
            date='Thu, 05 Jun 2025 16:14:27 +0000 (UTC)',
            note_from_buyer='Test note',
            gift_message='',
            shipping_address=ShippingAddress(
                name='Test Customer',
                address1='123 Test St',
                address2='',
                city='Test City',
                state='CA',
                zipcode='90210',
                country='United States',
                country_code='US',
                phone='',
                email='test@example.com',
            ),
            shipping_service='Standard',
            processing_time='5-7 business days',
            shipping_cost=3.96,
            discount_code='',
            subtotal=19.70,
            transactions=[
                Transaction(
                    transaction_id=transaction_id,
                    product_name=product_name,
                    sku='',
                    quantity=quantity,
                    price=price,
                    personalisation='Custom text',
                    option='',
                    color='Gold',
                    size='Small',
                    side='',
                    face_mask_size='',
                    image_url='https://i.etsystatic.com/test/300x300.jpg',
                    design_link_front='',
                    design_link_back='',
                ),
            ],
        )

    def test_create_shop(self):
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        shop = creator.find_or_create_shop('TestShop')
        self.assertEqual(shop.name, 'TestShop')
        self.assertTrue(shop.active)
        shop2 = creator.find_or_create_shop('TestShop')
        self.assertEqual(shop.id, shop2.id)

    def test_create_partner(self):
        from ..services.email_parser import ShippingAddress
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        shipping = ShippingAddress(
            name='John Doe', address1='123 Main St', address2='',
            city='Springfield', state='IL', zipcode='62701',
            country='United States', country_code='US',
            phone='555-1234', email='john@example.com',
        )
        partner = creator.find_or_create_partner(shipping, 'JohnD')
        self.assertEqual(partner.name, 'John Doe')
        self.assertTrue(partner.is_etsy_customer)
        self.assertEqual(partner.email, 'john@example.com')
        partner2 = creator.find_or_create_partner(shipping, 'JohnD')
        self.assertEqual(partner.id, partner2.id)

    def test_create_product(self):
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        product = creator.find_or_create_product(
            'Unique Ring Dish', 'https://example.com/img.jpg')
        self.assertTrue(product.is_etsy_product)
        self.assertEqual(product.name, 'Unique Ring Dish')
        product2 = creator.find_or_create_product(
            'Unique Ring Dish', 'https://example.com/img.jpg')
        self.assertEqual(product.id, product2.id)

    def test_create_full_order(self):
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        email_log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'test_msg_001',
            'parse_status': 'failed',
        })
        parse_result = self._make_parse_result()
        order = creator.process_parse_result(parse_result, email_log.id)
        self.assertIsNotNone(order)
        self.assertEqual(order.etsy_order_id, 'TEST001')
        self.assertEqual(order.state, 'draft')
        # 2 lines: 1 product transaction + 1 shipping line (T016 of 002 MVP).
        self.assertEqual(len(order.order_line), 2)
        product_line = order.order_line.filtered(lambda l: l.etsy_transaction_id == 'TXN001')
        self.assertTrue(product_line, "Product line should exist")
        self.assertAlmostEqual(product_line.price_unit, 19.70)
        self.assertEqual(product_line.etsy_color, 'Gold')
        self.assertEqual(product_line.etsy_personalisation, 'Custom text')
        shipping_line = order.order_line - product_line
        self.assertEqual(len(shipping_line), 1, "Shipping line should exist")
        self.assertAlmostEqual(shipping_line.price_unit, 3.96)

    def test_order_linked_to_shop(self):
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        email_log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'test_msg_002',
            'parse_status': 'failed',
        })
        parse_result = self._make_parse_result(shop='Carina')
        order = creator.process_parse_result(parse_result, email_log.id)
        self.assertEqual(order.etsy_shop_id.name, 'Carina')

    def test_order_partner_is_etsy_customer(self):
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        email_log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'test_msg_003',
            'parse_status': 'failed',
        })
        parse_result = self._make_parse_result()
        order = creator.process_parse_result(parse_result, email_log.id)
        self.assertTrue(order.partner_id.is_etsy_customer)

    def test_email_path_stamps_sales_channel_etsy(self):
        """Regression: email-parser must set sales_channel='etsy' (not 'other').

        Surfaced 2026-05-08 staging E2E run — orders S00040–S00043 from the
        live Gmail ingest path defaulted to 'other' and required manual
        fixup before Operations Dashboard etsy filters and Gearment
        auto-push could reach them. Same expectation for channel_order_ref:
        must mirror etsy_order_id so the GKE tracking-import wizard can
        match by Etsy order number without a manual JOIN.
        """
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        email_log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'test_msg_004',
            'parse_status': 'failed',
        })
        parse_result = self._make_parse_result(order_id='ETSY-CHN-001')
        order = creator.process_parse_result(parse_result, email_log.id)
        self.assertEqual(
            order.sales_channel, 'etsy',
            "email-parser path must set sales_channel='etsy'.",
        )
        self.assertEqual(
            order.channel_order_ref, 'ETSY-CHN-001',
            "email-parser path must mirror etsy_order_id into channel_order_ref.",
        )
