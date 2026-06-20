"""Phase D #1 — buyer note auto-posted to sale.order chatter.

Flow 4 mockup screen 1 ("Chatter — buyer message auto-posted"): the Etsy
buyer note is stored in `etsy_note_from_buyer` but, before this slice, was
never surfaced as a chatter message — Marketing only saw it as a read-only
field. This asserts that creating an Etsy order with a buyer note posts that
note to the order's chatter, and that orders without a note post nothing.
"""

from odoo.tests.common import TransactionCase, tagged

_NOTE_SUBJECT = 'Note from buyer (Etsy)'


@tagged('post_install', '-at_install')
class TestBuyerNoteChatter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Sarah Miller'})

    def _buyer_note_messages(self, order):
        return order.message_ids.filtered(
            lambda m: m.subject == _NOTE_SUBJECT)

    def test_buyer_note_posted_to_chatter(self):
        note = 'Hi, I love the mug! Could you ship by Friday?'
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_order_id': 'ORD-CHAT-1',
            'etsy_note_from_buyer': note,
        })
        posted = self._buyer_note_messages(order)
        self.assertEqual(
            len(posted), 1,
            'Exactly one buyer-note chatter message should be posted.')
        self.assertIn(note, posted.body,
                      'The chatter message must contain the buyer note text.')

    def test_no_note_posts_nothing(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_order_id': 'ORD-CHAT-2',
            'etsy_note_from_buyer': '',
        })
        self.assertEqual(
            len(self._buyer_note_messages(order)), 0,
            'No buyer-note message should be posted when the note is empty.')

    def test_non_etsy_order_posts_nothing(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_note_from_buyer': 'stray note without an etsy order id',
        })
        self.assertEqual(
            len(self._buyer_note_messages(order)), 0,
            'Only Etsy orders (with etsy_order_id) post the buyer note.')
