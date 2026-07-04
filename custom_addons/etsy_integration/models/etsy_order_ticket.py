"""Phase D#7 — after-sales return/refund/reship ticket (Story 4.8).

Flow 4 mockup screen 4 ("Refund"). Etsy has no usable refund-create API for our
flow, so the actual refund stays a manual action on the Etsy site (per the
mockup). This model TRACKS the decision: Marketing/BA raises a ticket, BA Lead
approves or rejects (FR-017 gated), and marks it refunded once done on Etsy —
giving an auditable record + chatter trail instead of a loose note.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

_BA_LEAD_GROUP = 'multichannel_hub_core.group_ba_lead'


class EtsyOrderTicket(models.Model):
    _name = 'etsy.order.ticket'
    _description = 'Etsy After-Sales Ticket (return / refund / reship)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', default='New', copy=False, readonly=True)
    order_id = fields.Many2one(
        'sale.order', string='Order', required=True,
        ondelete='cascade', index=True, tracking=True)
    ticket_type = fields.Selection(
        [('return', 'Return'), ('refund', 'Refund'), ('reship', 'Reship')],
        string='Type', required=True, default='refund', tracking=True)
    reason = fields.Text(string='Reason', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved'),
         ('rejected', 'Rejected'), ('refunded', 'Refunded / Done')],
        string='Status', default='draft', required=True, tracking=True)
    refund_amount = fields.Monetary(
        string='Refund Amount', currency_field='currency_id')
    currency_id = fields.Many2one(
        related='order_id.currency_id', string='Currency', readonly=True)
    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, ondelete='restrict', tracking=True)
    approved_by = fields.Many2one(
        'res.users', string='Decided By', ondelete='restrict',
        readonly=True, tracking=True)
    note = fields.Text(string='Internal Note')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.name or rec.name == 'New':
                rec.name = 'RT%05d' % rec.id
        return records

    @api.constrains('refund_amount')
    def _check_refund_amount(self):
        for rec in self:
            if rec.refund_amount < 0:
                raise ValidationError(_("Refund amount cannot be negative."))

    def _check_ba_lead_or_raise(self):
        # RPC-level FR-017 gate: form buttons use groups= but RPC bypasses
        # view-level checks, so the privileged transition is gated here too.
        if not self.env.user.has_group(_BA_LEAD_GROUP):
            raise AccessError(_(
                "Only a BA Lead can approve, reject, or close after-sales "
                "tickets."))

    def action_approve(self):
        self._check_ba_lead_or_raise()
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.write({'state': 'approved', 'approved_by': self.env.user.id})
            rec.message_post(body=_("Ticket approved by %s.") % self.env.user.display_name)

    def action_reject(self):
        self._check_ba_lead_or_raise()
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.write({'state': 'rejected', 'approved_by': self.env.user.id})
            rec.message_post(body=_("Ticket rejected by %s.") % self.env.user.display_name)

    def action_mark_refunded(self):
        self._check_ba_lead_or_raise()
        for rec in self.filtered(lambda r: r.state == 'approved'):
            rec.write({'state': 'refunded'})
            rec.message_post(body=_(
                "Marked refunded/done by %s (refund executed manually on "
                "Etsy).") % self.env.user.display_name)
