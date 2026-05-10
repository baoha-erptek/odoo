"""Phase 2 (ORM) tests for P1-DESIGN-AUTO-CREATE-FROM-EMAIL.

Tests OrderCreator integration: verify that design.file rows are
auto-created when orders are ingested via both email and API paths
through OrderCreator.process_parse_result and process_etsy_payload.
"""

from datetime import datetime

from odoo.tests.common import TransactionCase, tagged


def _make_parse_result(order_id='SEED001', transaction_id='SEEDTXN001',
                       design_link_front='', design_link_back=''):
    """Factory: Create a ParseResult for testing."""
    from odoo.addons.etsy_integration.services.email_parser import (
        ParseResult, ShippingAddress, Transaction,
    )
    return ParseResult(
        order_id=order_id,
        shop='Viktor',
        date='Thu, 05 Jun 2025 16:14:27 +0000 (UTC)',
        note_from_buyer='',
        gift_message='',
        shipping_address=ShippingAddress(
            name='Seed Test', address1='1 Seed St', address2='',
            city='Seed City', state='CA', zipcode='90000',
            country='United States', country_code='US',
            phone='', email='seed@test.com',
        ),
        shipping_service='Standard',
        processing_time='5-7 days',
        shipping_cost=0.0,
        discount_code='',
        subtotal=10.0,
        transactions=[
            Transaction(
                transaction_id=transaction_id,
                product_name='Seed Product',
                sku='', quantity=1, price=10.0,
                personalisation='', option='', color='',
                size='', side='', face_mask_size='',
                image_url='', design_link_front=design_link_front,
                design_link_back=design_link_back,
            ),
        ],
    )


def _build_etsy_payload(etsy_order_id='ORD-SEED-001',
                        design_link_front='', design_link_back='', **overrides):
    """Factory: Create an EtsyOrderPayload for testing."""
    from odoo.addons.etsy_integration.services.etsy_order_payload import (
        EtsyAddressPayload,
        EtsyLineItemPayload,
        EtsyOrderPayload,
    )
    defaults = dict(
        etsy_shop_id=1,
        etsy_receipt_id="REC-SEED-001",
        etsy_order_id=etsy_order_id,
        buyer_name="Seed Buyer",
        buyer_country="US",
        order_date=datetime(2026, 5, 10, 10, 0, 0),
        currency="USD",
        amount_total=110.00,
        shipping_total=10.00,
        line_items=(
            EtsyLineItemPayload(
                listing_id="LSEED",
                transaction_id="TSEED",
                title="Seed Product",
                sku="SKU-SEED",
                quantity=1,
                unit_price=100.00,
                design_link_front=design_link_front,
                design_link_back=design_link_back,
            ),
        ),
        shipping_address=EtsyAddressPayload(
            name="Seed Buyer",
            street_1="123 Seed St",
            street_2=None,
            city="Seed City",
            state="CA",
            zip="90000",
            country_code="US",
        ),
        buyer_message=None,
        buyer_email="seed@example.com",
        listing_id="LSEED",
        payment_status="paid",
        is_gift=False,
        gift_message=None,
        source="api",
        fetched_at=datetime(2026, 5, 10, 10, 5, 0),
        raw_source_id="receipt:REC-SEED-001",
    )
    defaults.update(overrides)
    return EtsyOrderPayload(**defaults)


@tagged('post_install', '-at_install')
class TestEmailIngestDesignFileSeed(TransactionCase):
    """Email path: OrderCreator.process_parse_result triggers design.file seeding."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        self.creator = OrderCreator(self.env)

    def test_email_ingest_creates_design_files_via_process_parse_result(self):
        """Test that design.file rows are auto-created from email-parsed design links."""
        result = _make_parse_result(
            order_id='EMAIL_SEED_001',
            transaction_id='EMAIL_TXN_001',
            design_link_front='https://gdrive.example/email-front.jpg',
            design_link_back='https://gdrive.example/email-back.jpg',
        )
        log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'email_seed_msg_001',
            'parse_status': 'failed',
        })

        order = self.creator.process_parse_result(result, log.id)

        self.assertIsNotNone(order, "Order should be created from parse result")
        design_files = self.env['design.file'].search([
            ('order_line_id', 'in', order.order_line.ids),
        ])
        self.assertEqual(
            len(design_files), 2,
            "Two design.file rows should be auto-created (front + back)"
        )
        urls = set(df.file_url for df in design_files)
        self.assertEqual(
            urls,
            {'https://gdrive.example/email-front.jpg', 'https://gdrive.example/email-back.jpg'},
            "Both URLs should be present"
        )
        for design_file in design_files:
            self.assertEqual(design_file.state, 'pending')
            self.assertEqual(design_file.storage_mode, 'url')
            self.assertEqual(
                design_file.created_via, 'email_ingest',
                "Design files from email path should have created_via='email_ingest'"
            )

    def test_email_ingest_no_design_files_when_links_absent(self):
        """Test that no design.file rows are created when design links are absent."""
        result = _make_parse_result(
            order_id='EMAIL_NODESIGN_001',
            transaction_id='EMAIL_NOTXN_001',
            design_link_front='',
            design_link_back='',
        )
        log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'email_nodesign_msg_001',
            'parse_status': 'failed',
        })

        order = self.creator.process_parse_result(result, log.id)

        self.assertIsNotNone(order)
        design_files = self.env['design.file'].search([
            ('order_line_id', 'in', order.order_line.ids),
        ])
        self.assertEqual(len(design_files), 0, "No design.file rows should be created")


@tagged('post_install', '-at_install')
class TestApiIngestDesignFileSeed(TransactionCase):
    """API path: OrderCreator.process_etsy_payload triggers design.file seeding."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        self.creator = OrderCreator(self.env)
        self.shop = self.env['etsy.shop'].create({'name': 'SeedShop'})

    def test_api_ingest_creates_design_files_via_process_etsy_payload(self):
        """Test that design.file rows are auto-created from API-fetched design links."""
        payload = _build_etsy_payload(
            etsy_order_id='ORD-API-SEED-001',
            design_link_front='https://gdrive.example/api-front.jpg',
            design_link_back='https://gdrive.example/api-back.jpg',
        )

        order = self.creator.process_etsy_payload(payload, self.shop)

        self.assertIsNotNone(order, "Order should be created from API payload")
        design_files = self.env['design.file'].search([
            ('order_line_id', 'in', order.order_line.ids),
        ])
        self.assertEqual(
            len(design_files), 2,
            "Two design.file rows should be auto-created (front + back)"
        )
        urls = set(df.file_url for df in design_files)
        self.assertEqual(
            urls,
            {'https://gdrive.example/api-front.jpg', 'https://gdrive.example/api-back.jpg'},
            "Both URLs should be present"
        )
        for design_file in design_files:
            self.assertEqual(design_file.state, 'pending')
            self.assertEqual(design_file.storage_mode, 'url')
            self.assertEqual(
                design_file.created_via, 'api_ingest',
                "Design files from API path should have created_via='api_ingest'"
            )

    def test_api_ingest_no_design_files_when_payload_has_no_links(self):
        """Test that no design.file rows are created when payload has no design links."""
        payload = _build_etsy_payload(
            etsy_order_id='ORD-API-NODESIGN-001',
            design_link_front='',
            design_link_back='',
        )

        order = self.creator.process_etsy_payload(payload, self.shop)

        self.assertIsNotNone(order)
        design_files = self.env['design.file'].search([
            ('order_line_id', 'in', order.order_line.ids),
        ])
        self.assertEqual(len(design_files), 0, "No design.file rows should be created")


@tagged('post_install', '-at_install')
class TestDesignSeedIdempotency(TransactionCase):
    """Idempotency: Re-ingesting the same email doesn't duplicate design.file rows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        self.creator = OrderCreator(self.env)

    def test_re_ingest_same_email_does_not_duplicate_design_files(self):
        """Test that re-ingesting same email doesn't duplicate design.file rows."""
        result = _make_parse_result(
            order_id='IDEMPOTENT_001',
            transaction_id='IDEMPOTENT_TXN_001',
            design_link_front='https://gdrive.example/idempotent-front.jpg',
            design_link_back='https://gdrive.example/idempotent-back.jpg',
        )

        # First ingest
        log1 = self.env['etsy.email.log'].create({
            'gmail_message_id': 'idempotent_msg_001',
            'parse_status': 'failed',
        })
        order1 = self.creator.process_parse_result(result, log1.id)
        self.assertIsNotNone(order1)
        design_files_1 = self.env['design.file'].search([
            ('order_line_id', 'in', order1.order_line.ids),
        ])
        count_1 = len(design_files_1)
        self.assertEqual(count_1, 2, "First ingest should create 2 design.file rows")

        # Second ingest (duplicate order)
        log2 = self.env['etsy.email.log'].create({
            'gmail_message_id': 'idempotent_msg_002',
            'parse_status': 'failed',
        })
        order2 = self.creator.process_parse_result(result, log2.id)
        # Note: depending on dedup logic, order2 might be None or a different order
        # Either way, the design.file count should not double

        # Check total design.file count
        all_design_files = self.env['design.file'].search([
            ('file_url', 'in', [
                'https://gdrive.example/idempotent-front.jpg',
                'https://gdrive.example/idempotent-back.jpg'
            ]),
        ])
        self.assertEqual(
            len(all_design_files), 2,
            "Total design.file count should be 2 (not duplicated)"
        )


@tagged('post_install', '-at_install')
class TestDesignFileRelationship(TransactionCase):
    """Verify design.file relationship to sale.order and order_line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        self.creator = OrderCreator(self.env)

    def test_email_seeded_files_accessible_via_order_line_relation(self):
        """Test that seeded design.file rows are accessible from order_line."""
        result = _make_parse_result(
            order_id='RELATION_001',
            transaction_id='RELATION_TXN_001',
            design_link_front='https://gdrive.example/relation-front.jpg',
            design_link_back='https://gdrive.example/relation-back.jpg',
        )
        log = self.env['etsy.email.log'].create({
            'gmail_message_id': 'relation_msg_001',
            'parse_status': 'failed',
        })

        order = self.creator.process_parse_result(result, log.id)

        # Verify design.file rows are linked to the product line
        product_lines = order.order_line.filtered(
            lambda l: l.product_id.name == 'Seed Product'
        )
        self.assertEqual(len(product_lines), 1, "Should have one product line")
        product_line = product_lines[0]

        # Check the design.file relationship
        design_files = self.env['design.file'].search([
            ('order_line_id', '=', product_line.id),
        ])
        self.assertEqual(
            len(design_files), 2,
            "Product line should have 2 related design.file records"
        )
        urls = sorted([df.file_url for df in design_files])
        expected_urls = sorted([
            'https://gdrive.example/relation-front.jpg',
            'https://gdrive.example/relation-back.jpg'
        ])
        self.assertEqual(urls, expected_urls, "Design file URLs should match")
