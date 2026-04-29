"""Address-change approval workflow (Spec 003 US4 / P1-04).

Marketing/BA-user files a request when a buyer asks for a shipping-address
change after the order is placed. The request locks the destination fields
on `sale.order` (C-SO-001) until a BA Lead approves or rejects. Approval
applies the new values atomically with `approve_address_change=True` in
context to bypass the lock.

Constraints:
    C-AC-001 — order must not be shipped/done/cancel at create time
    C-AC-002 — at most one outstanding (`state='requested'`) request per order
    C-AC-003 — `rejection_reason` required when `state='rejected'`
"""

import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EtsyAddressChangeRequest(models.Model):
    _name = 'etsy.address.change.request'
    _description = 'Etsy Address-Change Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    order_id = fields.Many2one(
        'sale.order', string='Order', required=True,
        ondelete='cascade', index=True)
    requested_fields = fields.Json(
        string='Requested Fields', required=True,
        help='List of field names (sale.order destination fields) being changed.')
    new_values = fields.Json(
        string='New Values', required=True,
        help="Map of field_name -> value. Many2one fields stored as "
             "{'id': <int>, 'display_name': <str>}.")
    state = fields.Selection(
        selection=[
            ('requested', 'Requested'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='State', required=True, default='requested',
        copy=False, tracking=True, index=True)
    reason = fields.Text(
        string='Reason', required=True,
        help="Buyer's reason for the change — required at request time.")
    rejection_reason = fields.Text(
        string='Rejection Reason', tracking=True,
        help='Required when state is rejected.')
    requested_by = fields.Many2one(
        'res.users', string='Requested By', required=True,
        default=lambda self: self.env.user, ondelete='restrict')
    approved_by = fields.Many2one(
        'res.users', string='Approved By', ondelete='restrict', tracking=True)
    approved_at = fields.Datetime(string='Approved At')
    rejected_at = fields.Datetime(string='Rejected At')

    # Constraints --------------------------------------------------------

    @api.constrains('order_id', 'state')
    def _check_order_not_final(self):
        """C-AC-001: order must not be in shipped/done/cancel at create time."""
        for rec in self:
            if rec.state == 'requested' and rec.order_id.state in ('done', 'cancel'):
                raise ValidationError(_(
                    "Order already shipped — create a return/ticket instead "
                    "(see Spec 004c)."))

    @api.constrains('state', 'order_id')
    def _check_outstanding_unique(self):
        """C-AC-002: only one outstanding request per order."""
        for rec in self:
            if rec.state != 'requested':
                continue
            siblings = self.search([
                ('order_id', '=', rec.order_id.id),
                ('state', '=', 'requested'),
                ('id', '!=', rec.id),
            ], limit=1)
            if siblings:
                raise ValidationError(_(
                    "An outstanding address-change request already exists "
                    "for order %s. Resolve it before filing a new one."
                ) % rec.order_id.name)

    @api.constrains('state', 'rejection_reason')
    def _check_rejection_reason(self):
        """C-AC-003: rejection_reason required when state='rejected'."""
        for rec in self:
            if rec.state == 'rejected' and not (rec.rejection_reason or '').strip():
                raise ValidationError(_(
                    "rejection_reason is required when rejecting an "
                    "address-change request."))

    # Lifecycle ----------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for request in requests:
            request._post_ba_activity()
        return requests

    # Actions ------------------------------------------------------------

    def _check_ba_lead_or_raise(self):
        """RPC-level gate. Form buttons use ``groups=`` but RPC bypasses
        view-level checks, so action methods must enforce the group too.
        """
        if not self.env.user.has_group('etsy_integration.group_ba_lead'):
            raise UserError(_(
                "Only BA Leads may approve or reject address-change requests."))

    def action_approve(self):
        """Apply new_values to sale.order atomically; mark approved.

        Idempotent: re-invoking on a non-'requested' state raises
        ValidationError (the state guard is the idempotency mechanism).
        """
        self.ensure_one()
        self._check_ba_lead_or_raise()
        if self.state != 'requested':
            raise ValidationError(_(
                "Only requests in 'requested' state can be approved."))

        write_vals = self._build_order_write_vals()
        # Bypass C-SO-001 — this is the documented unlock path.
        self.order_id.with_context(approve_address_change=True).write(write_vals)

        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_at': fields.Datetime.now(),
        })
        self._close_ba_activity()
        # Markup % auto-escapes the substituted strings — defends chatter
        # rendering against malicious user/field strings.
        body = Markup(_(
            "Address change approved by %(user)s. Updated fields: %(fields)s."
        )) % {
            'user': self.env.user.display_name,
            'fields': ', '.join(self.requested_fields or []),
        }
        self.order_id.message_post(body=body)
        return True

    def action_reject(self):
        """Mark rejected; require rejection_reason; @mention requester.

        Idempotent: re-invoking on a non-'requested' state raises
        ValidationError (the state guard is the idempotency mechanism).
        """
        self.ensure_one()
        self._check_ba_lead_or_raise()
        if self.state != 'requested':
            raise ValidationError(_(
                "Only requests in 'requested' state can be rejected."))
        if not (self.rejection_reason or '').strip():
            raise ValidationError(_(
                "rejection_reason is required when rejecting an "
                "address-change request."))

        self.write({
            'state': 'rejected',
            'rejected_at': fields.Datetime.now(),
        })
        self._close_ba_activity()
        partner_ids = self.requested_by.partner_id.ids if self.requested_by else []
        # escape() guarantees user-supplied rejection_reason renders as text,
        # not HTML, in the chatter — defends against stored XSS.
        body = Markup(_("Address change rejected. Reason: %s")) % escape(
            self.rejection_reason or '')
        self.order_id.message_post(body=body, partner_ids=partner_ids)
        return True

    # Helpers ------------------------------------------------------------

    def _build_order_write_vals(self):
        """Translate new_values JSON into a sale.order.write() dict."""
        self.ensure_one()
        write_vals = {}
        for field, value in (self.new_values or {}).items():
            if isinstance(value, dict) and 'id' in value:
                write_vals[field] = value['id']
            else:
                write_vals[field] = value
        return write_vals

    def _post_ba_activity(self):
        """Post a 'To Do' mail.activity to a BA Lead member, deadline +24h."""
        self.ensure_one()
        # Odoo 19 renamed res.groups.users -> user_ids.
        ba_lead = self.env.ref(
            'etsy_integration.group_ba_lead', raise_if_not_found=False)
        user_id = self.env.user.id
        if ba_lead and ba_lead.user_ids:
            user_id = ba_lead.user_ids[0].id
        try:
            self.order_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Approve address change for order %s")
                        % self.order_id.name,
                date_deadline=fields.Date.today() + timedelta(days=1),
                user_id=user_id,
            )
        except Exception:
            _logger.exception(
                "Failed to schedule BA activity for address-change request %s",
                self.id)

    def _close_ba_activity(self):
        """Mark the open BA activity for this order's address-change as done."""
        self.ensure_one()
        summary = _("Approve address change for order %s") % self.order_id.name
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.order_id.id),
            ('summary', '=', summary),
        ])
        if activities:
            activities.action_feedback(feedback=_("Resolved by request %s.") % self.id)
