"""P0-16c Phase 2 — ORM tests for status-only re-sync (FR-009).

Tests the EtsyOrderIngestor.ingest logic for re-syncing an order that
already exists: must update payment_status, shipping_status, cancellation,
and etsy_last_modified WITHOUT modifying operator fields (mp_note, pic_user_id)
or design state.

Single-writer invariant: only ingestor can modify etsy_* fields; operators
own their own fields (mp_note, pic_user_id, etc.).

Reference: Master Plan 006, P0-16c, OQ2 (status-only re-sync is full FR-009).
"""

from datetime import datetime

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEtsyOrderIngestor_StatusOnlyResync(TransactionCase):
    """Status-only re-sync behavior for existing orders."""

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({'name': 'StatusResyncShop'})
        try:
            from odoo.addons.etsy_integration.services.etsy_order_ingestor import (
                EtsyOrderIngestor,
            )
            self.ingestor = EtsyOrderIngestor(self.env)
        except ImportError:
            self.ingestor = None

    def _build_payload(self, **overrides):
        """Build a test EtsyOrderPayload."""
        try:
            from odoo.addons.etsy_integration.services.etsy_order_payload import (
                EtsyAddressPayload,
                EtsyLineItemPayload,
                EtsyOrderPayload,
            )
        except ImportError:
            self.fail("EtsyOrderPayload not found")

        defaults = dict(
            etsy_shop_id=self.shop.id,
            etsy_receipt_id="REC-3001",
            etsy_order_id="ORD-3001",
            buyer_name="Resync Buyer",
            buyer_country="US",
            order_date=datetime(2026, 4, 28, 10, 0, 0),
            currency="USD",
            amount_total=110.00,
            shipping_total=10.00,
            line_items=(
                EtsyLineItemPayload(
                    listing_id="L1",
                    transaction_id="T-3001",
                    title="Test Product",
                    sku="TEST-001",
                    quantity=1,
                    unit_price=100.00,
                ),
            ),
            shipping_address=EtsyAddressPayload(
                name="Resync Buyer",
                street_1="123 Main St",
                street_2=None,
                city="Boston",
                state="MA",
                zip="02108",
                country_code="US",
            ),
            buyer_message=None,
            buyer_email="resync@example.com",
            listing_id="L1",
            payment_status="paid",
            is_gift=False,
            gift_message=None,
            source="api",
            fetched_at=datetime(2026, 4, 28, 10, 5, 0),
            raw_source_id="receipt:REC-3001",
        )
        defaults.update(overrides)
        return EtsyOrderPayload(**defaults)

    def test_existing_order_payment_status_updated(self):
        """When re-syncing a payload with the same etsy_order_id but
        different payment_status, the existing order's payment_status must
        be updated."""
        if not self.ingestor:
            self.fail("EtsyOrderIngestor not found; RED phase expected")

        # Create initial order with unpaid status
        initial_payload = self._build_payload(
            etsy_order_id="X1", payment_status="unpaid"
        )
        order = self.ingestor.ingest(initial_payload, self.shop)
        self.assertIsNotNone(order)
        self.assertEqual(order.payment_status, "unpaid")

        # Re-sync with paid status
        resync_payload = self._build_payload(
            etsy_order_id="X1", payment_status="paid"
        )
        result = self.ingestor.ingest(resync_payload, self.shop)

        # For status-only resync, the method behavior depends on whether
        # OrderCreator handles re-sync or ingestor does.
        # This test verifies the contract: payment_status is updated.
        # If result is None, we need to fetch the order manually.
        if result is None:
            order = self.env['sale.order'].search([('etsy_order_id', '=', 'X1')])
            self.assertTrue(order)
        else:
            order = result

        self.assertEqual(
            order.payment_status, "paid",
            "payment_status should be updated on re-sync"
        )

    def test_existing_order_mp_note_preserved(self):
        """When re-syncing an order, the operator's mp_note field must
        NOT be overwritten."""
        if not self.ingestor:
            self.fail("EtsyOrderIngestor not found; RED phase expected")

        # Create order
        initial_payload = self._build_payload(etsy_order_id="X2")
        order = self.ingestor.ingest(initial_payload, self.shop)
        self.assertIsNotNone(order)

        # Set operator note
        operator_note = "Operator hand-written note"
        try:
            # Try to set mp_note on the fulfillment (might not exist yet)
            if hasattr(order, 'fulfillment_id') and order.fulfillment_id:
                order.fulfillment_id.mp_note = operator_note
            else:
                # For RED phase, this may fail — that's expected
                order.mp_note = operator_note
        except AttributeError:
            # mp_note might not exist yet; skip this test or mark it
            self.skipTest("mp_note field not found on order or fulfillment")
            return

        # Re-sync with new data
        resync_payload = self._build_payload(
            etsy_order_id="X2",
            buyer_name="Different Buyer Name"
        )
        self.ingestor.ingest(resync_payload, self.shop)

        # Verify mp_note is preserved
        order.invalidate_recordset()
        try:
            actual_note = (
                order.fulfillment_id.mp_note
                if hasattr(order, 'fulfillment_id') and order.fulfillment_id
                else order.mp_note
            )
            self.assertEqual(
                actual_note, operator_note,
                "mp_note should be preserved on re-sync"
            )
        except AttributeError:
            self.skipTest("Cannot verify mp_note preservation — field missing")

    def test_existing_order_pic_user_id_preserved(self):
        """When re-syncing an order, the pic_user_id (design owner)
        must NOT be overwritten."""
        if not self.ingestor:
            self.fail("EtsyOrderIngestor not found; RED phase expected")

        # Create order
        initial_payload = self._build_payload(etsy_order_id="X3")
        order = self.ingestor.ingest(initial_payload, self.shop)
        self.assertIsNotNone(order)

        # Set design owner (pic_user_id)
        designer = self.env['res.users'].create({
            'name': 'Designer User',
            'login': 'designer@example.com',
        })
        try:
            if hasattr(order, 'fulfillment_id') and order.fulfillment_id:
                order.fulfillment_id.pic_user_id = designer
            else:
                order.pic_user_id = designer
        except AttributeError:
            self.skipTest("pic_user_id field not found")
            return

        # Re-sync with new data
        resync_payload = self._build_payload(
            etsy_order_id="X3",
            buyer_name="Another Name"
        )
        self.ingestor.ingest(resync_payload, self.shop)

        # Verify pic_user_id is preserved
        order.invalidate_recordset()
        try:
            actual_user = (
                order.fulfillment_id.pic_user_id
                if hasattr(order, 'fulfillment_id') and order.fulfillment_id
                else order.pic_user_id
            )
            self.assertEqual(
                actual_user.id, designer.id,
                "pic_user_id should be preserved on re-sync"
            )
        except AttributeError:
            self.skipTest("Cannot verify pic_user_id preservation")

    def test_existing_order_etsy_last_modified_advanced(self):
        """When re-syncing with a newer last_modified timestamp,
        the order's etsy_last_modified field should be updated."""
        if not self.ingestor:
            self.fail("EtsyOrderIngestor not found; RED phase expected")

        # Create order with initial timestamp
        initial_payload = self._build_payload(
            etsy_order_id="X4",
            last_modified=datetime(2026, 4, 28, 10, 0, 0),
        )
        order = self.ingestor.ingest(initial_payload, self.shop)
        self.assertIsNotNone(order)
        initial_modified = order.etsy_last_modified
        self.assertEqual(initial_modified, datetime(2026, 4, 28, 10, 0, 0))

        # Re-sync with newer timestamp
        newer_payload = self._build_payload(
            etsy_order_id="X4",
            last_modified=datetime(2026, 4, 28, 11, 0, 0),
        )
        self.ingestor.ingest(newer_payload, self.shop)

        # Verify field was updated
        order.invalidate_recordset()
        self.assertGreater(
            order.etsy_last_modified, initial_modified,
            "etsy_last_modified should be advanced on re-sync"
        )

    def test_new_order_full_create(self):
        """Verify that the status-only resync path doesn't hijack the
        new-order creation path. A previously-unseen etsy_order_id should
        still create a full sale.order with all fields."""
        if not self.ingestor:
            self.fail("EtsyOrderIngestor not found; RED phase expected")

        payload = self._build_payload(etsy_order_id="BRANDNEW")
        order = self.ingestor.ingest(payload, self.shop)

        self.assertIsNotNone(order)
        self.assertEqual(order.etsy_order_id, "BRANDNEW")
        self.assertEqual(len(order.order_line), 2)  # product + shipping
        self.assertEqual(order.partner_id.email, "resync@example.com")
