"""multichannel.enquiry — pre-sale customer enquiry record.

Per spec 007 data-model.md §1 and ADR-011 (lightweight model on
multichannel_hub_core, no `crm` dep). Extended from the P3-LEAD-DEDUPE stub
(2026-05-07) which created the table so `etsy.message.dedupe.target_enquiry_id`
could declare its FK.

Behavior:
- 4-state machine: new -> qualified -> converted (terminal); new/qualified -> closed (terminal).
- Backwards transitions disallowed (mirrored in @api.constrains AND write()
  per FR-017 write-level defense in depth, 11th confirmation).
- Action methods (action_qualify / action_close / action_convert_to_quote)
  carry RPC gates beyond ACL: _check_sale_user_or_raise() runs has_group()
  and raises UserError on fail.
- Partial UNIQUE on (etsy_shop_id, etsy_conversation_id) WHERE
  etsy_conversation_id IS NOT NULL — declared in init() raw SQL via
  drift-template pattern (project_sql_constraints_drift.md 6th confirmation).
- Composite index on (partner_email, state) for inbox lookups.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

_SOURCE_SELECTION = [
    ('etsy_api', 'Etsy Conversations API'),
    ('email_alias', 'Email Alias'),
    ('manual', 'Manual'),
]

_STATE_SELECTION = [
    ('new', 'New'),
    ('qualified', 'Qualified'),
    ('converted', 'Converted'),
    ('closed', 'Closed'),
]

_CLOSED_REASON_SELECTION = [
    ('no_response', 'No Response'),
    ('not_interested', 'Not Interested'),
    ('spam', 'Spam'),
    ('duplicate', 'Duplicate'),
    ('other', 'Other'),
]

# Forward transition matrix: from -> set of allowed to-states.
# Backwards / cross-terminal moves are forbidden.
_ALLOWED_TRANSITIONS = {
    'new': {'qualified', 'converted', 'closed'},
    'qualified': {'converted', 'closed'},
    'converted': set(),  # terminal
    'closed': set(),     # terminal
}


class MultichannelEnquiry(models.Model):
    _name = 'multichannel.enquiry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Customer enquiry — pre-sale conversation not yet tied to an order'
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Name', compute='_compute_name', store=True, readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Partner', ondelete='restrict', tracking=True,
        help='Resolved buyer; created on demand by _match_or_create_partner().',
    )
    partner_email = fields.Char(
        string='Partner Email', index=True, tracking=True,
        help='Authoritative when partner_id is null.',
    )
    subject = fields.Char(string='Subject', tracking=True)
    source = fields.Selection(
        _SOURCE_SELECTION, string='Source', required=True,
        index=True, tracking=True, default='manual',
    )
    # Etsy-specific FKs (etsy_shop_id, etsy_conversation_id) live on the
    # etsy_integration extension per ADR-003 — mhc cannot reference channel
    # models. The partial UNIQUE on (etsy_shop_id, etsy_conversation_id)
    # likewise mirrors there.
    state = fields.Selection(
        _STATE_SELECTION, string='State', required=True,
        default='new', tracking=True, copy=False,
    )
    assigned_user_id = fields.Many2one(
        'res.users', string='Assigned To', ondelete='set null', tracking=True,
    )
    converted_order_id = fields.Many2one(
        'sale.order', string='Converted Quote', ondelete='set null',
        readonly=True, tracking=True, copy=False,
    )
    converted_at = fields.Datetime(
        string='Converted At', readonly=True, tracking=True, copy=False,
    )
    closed_reason = fields.Selection(
        _CLOSED_REASON_SELECTION, string='Closed Reason',
        tracking=True, copy=False,
    )
    notes = fields.Text(string='Internal Notes')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # init() — drift-template raw SQL mirror per project_sql_constraints_drift.md
    # ------------------------------------------------------------------
    def init(self):
        """Mirror composite index in raw SQL.

        The partial UNIQUE on (etsy_shop_id, etsy_conversation_id) lives in
        the etsy_integration extension because mhc cannot reference Etsy
        columns at all (ADR-003).
        """
        super().init()
        # idx_mhe_partner_email_state: non-unique composite.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_mhe_partner_email_state
            ON multichannel_enquiry (partner_email, state);
        """)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('state', 'closed_reason')
    def _check_state_transition(self):
        for record in self:
            if record.state == 'closed' and not record.closed_reason:
                raise ValidationError(_(
                    "Cannot close enquiry %s: closed_reason is required."
                ) % (record.display_name or record.id))

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('partner_email', 'create_date')
    def _compute_name(self):
        for record in self:
            email_part = record.partner_email or _('unknown')
            if record.create_date:
                date_part = fields.Date.to_string(record.create_date)
                record.name = f"Enquiry from {email_part} · {date_part}"
            else:
                record.name = f"Enquiry from {email_part}"

    # ------------------------------------------------------------------
    # CRUD overrides — FR-017 write-level defense in depth (11th confirmation)
    # ------------------------------------------------------------------
    def write(self, vals):
        """Enforce state-machine forward-only progression on direct writes.

        @api.constrains fires post-write so the row mutates before raising;
        the write() override rejects pre-mutation for friendlier UX and
        defense in depth against direct RPC writes that bypass action methods.
        Pattern: feedback_fr017_write_defense_in_depth.md (11+ confirmations).
        """
        if 'state' in vals:
            new_state = vals['state']
            for record in self:
                old_state = record.state
                if old_state == new_state:
                    continue
                allowed = _ALLOWED_TRANSITIONS.get(old_state, set())
                if new_state not in allowed:
                    raise ValidationError(_(
                        "Invalid state transition for enquiry %(name)s: "
                        "%(old)s -> %(new)s is not allowed. "
                        "Allowed transitions from %(old)s: %(allowed)s."
                    ) % {
                        'name': record.display_name or record.id,
                        'old': old_state,
                        'new': new_state,
                        'allowed': ', '.join(sorted(allowed)) or _('(terminal)'),
                    })
        return super().write(vals)

    # ------------------------------------------------------------------
    # Action methods — RPC-gated per FR-017 (gates beyond CRUD ACL)
    # ------------------------------------------------------------------
    def _check_sale_user_or_raise(self):
        """Raise UserError unless current user has the sale-user group.

        ACL guards CRUD; action methods need an explicit RPC gate so users
        with read-only access cannot trigger state machine transitions.
        Pattern from design_file_route._check_production_team_or_raise().
        """
        if not (
            self.env.user.has_group('sales_team.group_sale_salesman')
            or self.env.user.has_group('sales_team.group_sale_manager')
            or self.env.user.has_group('multichannel_hub_core.group_ba_lead')
        ):
            raise UserError(_(
                "You need Sales User, BA Lead, or Sales Manager rights "
                "to perform this action on enquiries."
            ))

    def action_qualify(self):
        """Flip state from new to qualified."""
        self._check_sale_user_or_raise()
        for record in self:
            if record.state != 'new':
                raise UserError(_(
                    "Cannot qualify enquiry %(name)s: only enquiries in 'new' "
                    "state can be qualified, current state is %(state)s."
                ) % {
                    'name': record.display_name or record.id,
                    'state': record.state,
                })
            record.state = 'qualified'
            record.message_post(body=_(
                "Qualified by %s"
            ) % (self.env.user.display_name or self.env.user.login))

    def action_close(self, reason=None):
        """Terminal close transition; reason is required."""
        self._check_sale_user_or_raise()
        if not reason:
            raise UserError(_(
                "Cannot close enquiry: a reason is required."
            ))
        valid_reasons = {key for key, _label in _CLOSED_REASON_SELECTION}
        if reason not in valid_reasons:
            raise UserError(_(
                "Invalid close reason: %s. Allowed: %s."
            ) % (reason, ', '.join(sorted(valid_reasons))))
        for record in self:
            if record.state in ('converted', 'closed'):
                raise UserError(_(
                    "Cannot close enquiry %(name)s from terminal state %(state)s."
                ) % {
                    'name': record.display_name or record.id,
                    'state': record.state,
                })
            record.write({'state': 'closed', 'closed_reason': reason})
            record.message_post(body=_(
                "Closed by %(user)s — reason: %(reason)s"
            ) % {
                'user': self.env.user.display_name or self.env.user.login,
                'reason': dict(_CLOSED_REASON_SELECTION).get(reason, reason),
            })

    def action_convert_to_quote(self):
        """Create a draft sale.order linked to this enquiry."""
        self._check_sale_user_or_raise()
        self.ensure_one()
        if self.state == 'converted' and self.converted_order_id:
            return self._action_open_converted_order()
        if self.state not in ('new', 'qualified'):
            raise UserError(_(
                "Cannot convert enquiry from state %s."
            ) % self.state)
        partner = self._match_or_create_partner()
        if not partner:
            raise UserError(_(
                "Cannot convert: enquiry has no partner and no email "
                "to create one from."
            ))
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'origin': self.name,
        })
        # Defensive: persist partner_id explicitly even though
        # _match_or_create_partner already wrote it via single-field
        # assignment. Reviewer-requested for audit-trail clarity.
        self.write({
            'state': 'converted',
            'partner_id': partner.id,
            'converted_order_id': order.id,
            'converted_at': fields.Datetime.now(),
        })
        self.message_post(body=_("Converted to %s") % order.name)
        order.message_post(body=_("Created from enquiry %s") % self.name)
        return self._action_open_converted_order()

    def _action_open_converted_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.converted_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _match_or_create_partner(self):
        """Match existing res.partner by normalized email, or create one.

        Mirrors Spec 002 US4 partner-dedup pattern: search by
        email_normalized; create with is_etsy_customer=True (channel-agnostic
        flag, despite the name) when no match. Returns the partner record or
        an empty recordset when partner_email is blank.
        """
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        if not self.partner_email:
            return self.env['res.partner']
        normalized = email_normalize(self.partner_email)
        if not normalized:
            return self.env['res.partner']
        Partner = self.env['res.partner']
        # Use email_normalized field if present (Spec 002 US4 added it);
        # fall back to email comparison otherwise.
        if 'email_normalized' in Partner._fields:
            existing = Partner.search([('email_normalized', '=', normalized)], limit=1)
        else:
            existing = Partner.search([('email', '=ilike', normalized)], limit=1)
        if existing:
            self.partner_id = existing.id
            return existing
        # Derive a name from the email local-part if no other source.
        local_part = normalized.split('@', 1)[0] if '@' in normalized else normalized
        partner_vals = {
            'name': local_part or normalized,
            'email': self.partner_email,
        }
        if 'is_etsy_customer' in Partner._fields:
            partner_vals['is_etsy_customer'] = True
        new_partner = Partner.create(partner_vals)
        self.partner_id = new_partner.id
        return new_partner
