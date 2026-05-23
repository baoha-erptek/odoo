"""Phase 2 ORM tests for P1-MSG-EMAIL-FALLBACK scaffold."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.etsy_buyer_message import (
    is_buyer_message_email,
    parse_buyer_message_email,
    ingest_buyer_message_email,
)


@tagged('post_install', '-at_install')
class TestBuyerMessageORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'BUYER MSG SHOP', 'sync_mode': 'email_only',
        })
        cls.partner = cls.env.ref('base.partner_admin')
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'etsy_shop_id': cls.shop.id,
            'etsy_order_id': '3818231452',
        })
        cls.Dedupe = cls.env['etsy.message.dedupe'].sudo()

    # ------------------------------------------------------------------
    # Subject detection
    # ------------------------------------------------------------------

    def test_subject_new_message_from_buyer(self):
        self.assertTrue(is_buyer_message_email(
            "MyShop — New message from john_doe",
        ))

    def test_subject_sent_you_a_message(self):
        self.assertTrue(is_buyer_message_email(
            "JaneDoe sent you a message about Ring Dish",
        ))

    def test_subject_buyer_messaged_you(self):
        self.assertTrue(is_buyer_message_email(
            "A buyer messaged you about your order",
        ))

    def test_subject_order_receipt_NOT_buyer_message(self):
        self.assertFalse(is_buyer_message_email(
            "New order from your Etsy shop",
        ))

    def test_subject_empty_returns_false(self):
        self.assertFalse(is_buyer_message_email(''))
        self.assertFalse(is_buyer_message_email(None))

    # ------------------------------------------------------------------
    # Parse output shape
    # ------------------------------------------------------------------

    def test_parse_buyer_message_returns_message_id(self):
        result = parse_buyer_message_email(
            subject="New message from buyer",
            body="Hi, I'd like to ask about my order #3818231452 please. Receipt ID: 3818231452",
        )
        self.assertTrue(result['is_buyer_message'])
        self.assertTrue(result['message_id'].startswith('email-'))
        self.assertEqual(result['etsy_order_id'], '3818231452')

    def test_parse_non_buyer_message_returns_skip_marker(self):
        result = parse_buyer_message_email(
            subject="New order from your Etsy shop",
            body="...",
        )
        self.assertFalse(result['is_buyer_message'])

    def test_parse_message_id_is_deterministic(self):
        a = parse_buyer_message_email("New message from x", "Body content here")
        b = parse_buyer_message_email("New message from x", "Body content here")
        self.assertEqual(a['message_id'], b['message_id'])

    # ------------------------------------------------------------------
    # Ingest happy path
    # ------------------------------------------------------------------

    def test_ingest_posts_to_matched_order(self):
        parsed = parse_buyer_message_email(
            subject="New message from buyer",
            body="Receipt ID: 3818231452 — question about engraving",
        )
        msg_count_before = len(self.order.message_ids)
        result = ingest_buyer_message_email(self.env, self.shop, parsed)
        self.assertEqual(result, 'posted')
        self.order.invalidate_recordset()
        self.assertGreater(len(self.order.message_ids), msg_count_before)
        dedupe_row = self.Dedupe.search([
            ('etsy_message_id', '=', parsed['message_id']),
        ], limit=1)
        self.assertEqual(dedupe_row.target_sale_order_id, self.order)
        self.assertEqual(dedupe_row.state, 'posted')

    def test_ingest_dedupes_on_second_call(self):
        parsed = parse_buyer_message_email(
            subject="messaged you",
            body="Receipt ID: 3818231452 hello",
        )
        first = ingest_buyer_message_email(self.env, self.shop, parsed)
        second = ingest_buyer_message_email(self.env, self.shop, parsed)
        self.assertEqual(first, 'posted')
        self.assertEqual(second, 'duplicate')

    def test_ingest_unmatched_receipt_buffers(self):
        parsed = parse_buyer_message_email(
            subject="New message from buyer",
            body="Receipt ID: 9999999999 — question",
        )
        result = ingest_buyer_message_email(self.env, self.shop, parsed)
        self.assertEqual(result, 'no_order')
        dedupe_row = self.Dedupe.search([
            ('etsy_message_id', '=', parsed['message_id']),
        ], limit=1)
        self.assertEqual(dedupe_row.state, 'buffered')

    def test_ingest_non_buyer_message_skipped(self):
        parsed = parse_buyer_message_email(
            subject="New order from your Etsy shop",
            body="...",
        )
        result = ingest_buyer_message_email(self.env, self.shop, parsed)
        self.assertEqual(result, 'skipped')
