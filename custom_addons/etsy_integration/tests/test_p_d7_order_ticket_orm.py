"""Phase D#7 — after-sales ticket model (Story 4.8 / Flow 4 #4)."""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEtsyOrderTicket(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Ticket Buyer'})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'etsy_order_id': 'ORD-TICKET-1',
        })
        cls.ba_lead = cls.env.ref('multichannel_hub_core.group_ba_lead')

    def _ticket(self, **kw):
        vals = {'order_id': self.order.id, 'ticket_type': 'refund'}
        vals.update(kw)
        return self.env['etsy.order.ticket'].create(vals)

    def test_create_assigns_reference_and_draft(self):
        ticket = self._ticket()
        self.assertTrue(ticket.name.startswith('RT'))
        self.assertEqual(ticket.state, 'draft')

    def test_negative_refund_rejected(self):
        with self.assertRaises(ValidationError):
            self._ticket(refund_amount=-1.0)

    def test_approve_requires_ba_lead(self):
        ticket = self._ticket()
        self.env.user.group_ids = [(3, self.ba_lead.id)]
        with self.assertRaises(AccessError):
            ticket.action_approve()

    def test_full_flow_with_ba_lead(self):
        ticket = self._ticket(refund_amount=25.0)
        self.env.user.group_ids = [(4, self.ba_lead.id)]
        ticket.action_approve()
        self.assertEqual(ticket.state, 'approved')
        self.assertEqual(ticket.approved_by, self.env.user)
        ticket.action_mark_refunded()
        self.assertEqual(ticket.state, 'refunded')
