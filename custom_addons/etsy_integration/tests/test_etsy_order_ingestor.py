"""P0-16b1 — RED-phase tests for EtsyOrderIngestor + OrderCreator.process_etsy_payload.

Verifies the canonical ingest path: hand-crafted `EtsyOrderPayload` →
`EtsyOrderIngestor.ingest(payload, shop)` → `sale.order` row written via
the new `OrderCreator.process_etsy_payload` helper.

P0-16b1 covers the new-order happy path, dedup by `etsy_order_id`, and
the shop cursor field. Status-only re-sync (FR-009) and audit-mode
(architect Q4) are deferred to P0-16c.

Reference: spec 005 T008, T022, T026 (subset), T029 (deferred to P0-16c).
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
        etsy_receipt_id="REC-2001",
        etsy_order_id="ORD-2001",
        buyer_name="Alice Buyer",
        buyer_country="US",
        order_date=datetime(2026, 4, 28, 10, 0, 0),
        currency="USD",
        amount_total=110.00,
        shipping_total=10.00,
        line_items=(
            EtsyLineItemPayload(
                listing_id="L1",
                transaction_id="T-2001",
                title="Custom Mug",
                sku="MUG-001",
                quantity=1,
                unit_price=100.00,
            ),
        ),
        shipping_address=EtsyAddressPayload(
            name="Alice Buyer",
            street_1="123 Main St",
            street_2=None,
            city="Boston",
            state="MA",
            zip="02108",
            country_code="US",
        ),
        buyer_message=None,
        buyer_email="alice2001@example.com",
        listing_id="L1",
        payment_status="paid",
        is_gift=False,
        gift_message=None,
        source="api",
        fetched_at=datetime(2026, 4, 28, 10, 5, 0),
        raw_source_id="receipt:REC-2001",
    )
    defaults.update(overrides)
    return EtsyOrderPayload(**defaults)


@tagged('post_install', '-at_install')
class TestEtsyShopCursorField(TransactionCase):
    """`etsy.shop.etsy_last_receipt_sync_at` Datetime field."""

    def test_cursor_field_exists(self):
        """The cursor field must be declared on `etsy.shop`."""
        self.assertIn(
            'etsy_last_receipt_sync_at',
            self.env['etsy.shop']._fields,
        )

    def test_cursor_field_is_datetime(self):
        from odoo import fields as odoo_fields
        field = self.env['etsy.shop']._fields['etsy_last_receipt_sync_at']
        self.assertIsInstance(field, odoo_fields.Datetime)

    def test_cursor_field_default_is_null(self):
        """A newly created shop has no sync watermark — first sync fetches
        everything from the configured floor."""
        shop = self.env['etsy.shop'].create({'name': 'CursorShop'})
        self.assertFalse(shop.etsy_last_receipt_sync_at)


@tagged('post_install', '-at_install')
class TestOrderCreatorProcessEtsyPayload(TransactionCase):
    """`OrderCreator.process_etsy_payload(payload, shop)` happy-path tests.

    Reuses the existing partner-dedup, product creation, and xmlid
    resolution from the email path. Distinct from `process_parse_result`
    only in the input shape (`EtsyOrderPayload`) and `sync_source='api'`.
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator
        self.creator = OrderCreator(self.env)
        self.shop = self.env['etsy.shop'].create({'name': 'PayloadShop'})

    def test_creates_sale_order_from_payload(self):
        payload = _build_payload()
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertTrue(order)
        self.assertEqual(order.etsy_order_id, "ORD-2001")
        self.assertEqual(order.etsy_shop_id.id, self.shop.id)

    def test_creates_partner_with_buyer_email(self):
        payload = _build_payload(buyer_email="newbuyer@example.com")
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertEqual(order.partner_id.email, "newbuyer@example.com")

    def test_reuses_existing_partner_by_email(self):
        existing = self.env['res.partner'].create({
            'name': 'Existing Buyer',
            'email': 'existing@example.com',
            'is_etsy_customer': True,
        })
        payload = _build_payload(buyer_email="existing@example.com")
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertEqual(order.partner_id.id, existing.id)

    def test_creates_product_for_first_listing(self):
        payload = _build_payload()
        order = self.creator.process_etsy_payload(payload, self.shop)
        line = order.order_line.filtered(lambda l: l.product_id.name == "Custom Mug")
        self.assertTrue(line)
        self.assertEqual(line.product_uom_qty, 1)
        self.assertEqual(line.price_unit, 100.00)

    def test_appends_shipping_line_when_shipping_total_positive(self):
        payload = _build_payload(shipping_total=15.00)
        order = self.creator.process_etsy_payload(payload, self.shop)
        # Shipping line uses the configured shipping product; identifies
        # it by price_unit since name varies by config.
        shipping_lines = order.order_line.filtered(
            lambda l: l.price_unit == 15.00 and l.product_id != order.order_line[0].product_id
        )
        self.assertTrue(shipping_lines)

    def test_skips_shipping_line_when_zero(self):
        payload = _build_payload(shipping_total=0.0)
        order = self.creator.process_etsy_payload(payload, self.shop)
        # All lines should be product lines, none for shipping.
        # Easier assertion: only one line (the single line_items entry).
        self.assertEqual(len(order.order_line), 1)

    def test_writes_etsy_personalisation_from_payload(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
            EtsyLineItemPayload,
        )
        payload = _build_payload(line_items=(
            EtsyLineItemPayload(
                listing_id="L1",
                transaction_id="T-perso",
                title="Personalised Mug",
                sku="MUG-PERSO",
                quantity=2,
                unit_price=50.00,
                personalisation="Happy Birthday Bao",
            ),
        ))
        order = self.creator.process_etsy_payload(payload, self.shop)
        line = order.order_line.filtered(lambda l: l.etsy_transaction_id == "T-perso")
        self.assertEqual(line.etsy_personalisation, "Happy Birthday Bao")
        self.assertEqual(line.etsy_sku, "MUG-PERSO")
        self.assertEqual(line.product_uom_qty, 2)

    def test_dedup_by_etsy_order_id_returns_none(self):
        """Re-ingesting an already-imported receipt is a no-op and
        returns None — single-writer invariant."""
        payload = _build_payload(etsy_order_id="ORD-DEDUP")
        first = self.creator.process_etsy_payload(payload, self.shop)
        self.assertTrue(first)
        # Second call with same etsy_order_id must not create a new order.
        second = self.creator.process_etsy_payload(payload, self.shop)
        self.assertIsNone(second)

    def test_records_api_source_provenance(self):
        """sync_source='api' must be written so the operator can tell at a
        glance which adapter created the order. Field is added in this
        slice (P0-16b1) on sale.order; until P0-16c uses it, the value
        is purely diagnostic."""
        payload = _build_payload(etsy_order_id="ORD-PROV", source="api")
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertEqual(order.sync_source, "api")

    def test_api_path_stamps_sales_channel_etsy(self):
        """Regression: API ingest path must also stamp sales_channel='etsy'
        + channel_order_ref. Same reason as the email-path regression — the
        Operations Dashboard, Gearment auto-push gate, and tracking import
        wizard all filter / match on these fields.
        """
        payload = _build_payload(etsy_order_id="ORD-CHANNEL-API")
        order = self.creator.process_etsy_payload(payload, self.shop)
        self.assertEqual(
            order.sales_channel, 'etsy',
            "API ingest path must set sales_channel='etsy'.",
        )
        self.assertEqual(
            order.channel_order_ref, 'ORD-CHANNEL-API',
            "API ingest path must mirror etsy_order_id into channel_order_ref.",
        )


@tagged('post_install', '-at_install')
class TestEtsyOrderIngestor(TransactionCase):
    """`EtsyOrderIngestor.ingest(payload, shop)` thin wrapper around
    OrderCreator.process_etsy_payload — adds idempotency hooks and the
    audit-mode short-circuit (deferred to P0-16c)."""

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_order_ingestor import (
            EtsyOrderIngestor,
        )
        self.ingestor = EtsyOrderIngestor(self.env)
        self.shop = self.env['etsy.shop'].create({'name': 'IngestorShop'})

    def test_ingest_returns_sale_order_on_new_payload(self):
        payload = _build_payload(etsy_order_id="ORD-INGEST-NEW")
        result = self.ingestor.ingest(payload, self.shop)
        self.assertTrue(result)
        self.assertEqual(result.etsy_order_id, "ORD-INGEST-NEW")

    def test_ingest_returns_existing_order_on_duplicate(self):
        """P0-16c FR-009: duplicate ingest no longer returns None — it
        returns the existing order after a status-only re-sync (idempotent
        when payload fields match what's already stored)."""
        payload = _build_payload(etsy_order_id="ORD-INGEST-DUP")
        first = self.ingestor.ingest(payload, self.shop)
        self.assertTrue(first)
        second = self.ingestor.ingest(payload, self.shop)
        self.assertEqual(second.id, first.id)

    def test_ingest_writes_raw_source_id_to_order(self):
        """Audit hook: raw_source_id ('receipt:1234' or 'email_log:567')
        must be back-pointered on the created sale.order so we can find
        the originating record."""
        payload = _build_payload(
            etsy_order_id="ORD-RAWREF",
            raw_source_id="receipt:RAWREF",
        )
        order = self.ingestor.ingest(payload, self.shop)
        self.assertEqual(order.etsy_raw_source_id, "receipt:RAWREF")
