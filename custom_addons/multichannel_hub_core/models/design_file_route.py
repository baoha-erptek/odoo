"""design.file.route — file delivery routing and state machine.

P1-02b routing layer — manages file delivery methods (GDrive share, Discord,
Gearment API, email link) and routes files to internal production teams and
external partners. Integrates with queued-job dispatcher for async delivery.

State machine: pending → sent → acknowledged (or pending → failed).

References: ADR-009 §4, ADR-012, data-model.md §7, p1-02b-plan.md.
"""
import hashlib
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class DesignFileRoute(models.Model):
    _name = 'design.file.route'
    _description = 'Design File Route'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC, id DESC'

    # Relationships
    design_file_id = fields.Many2one(
        'design.file',
        string='Design File',
        ondelete='cascade',
        required=True,
        index=True,
    )

    # Recipient routing
    recipient_type = fields.Selection(
        [
            ('mp', 'Manufacturing/Production'),
            ('ba', 'Business Admin'),
            ('pd', 'Product Design'),
            ('partner_gearment', 'Partner: Gearment'),
            ('partner_other', 'Partner: Other'),
        ],
        string='Recipient Type',
        required=True,
        tracking=True,
    )

    recipient_partner_id = fields.Many2one(
        'res.partner',
        string='Recipient Partner',
        ondelete='set null',
    )

    recipient_user_id = fields.Many2one(
        'res.users',
        string='Recipient User',
        ondelete='set null',
    )

    # Delivery method
    delivery_method = fields.Selection(
        [
            ('gdrive_share', 'GDrive Share'),
            ('gearment_api', 'Gearment API'),
            ('email_link', 'Email Link'),
            ('discord_manual', 'Discord (Manual)'),
        ],
        string='Delivery Method',
        required=True,
        tracking=True,
    )

    # State machine
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('acknowledged', 'Acknowledged'),
            ('failed', 'Failed'),
        ],
        string='State',
        required=True,
        default='pending',
        tracking=True,
        index=True,
    )

    # Timestamps
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        required=True,
        store=True,
    )

    sent_at = fields.Datetime(
        string='Sent At',
    )

    acknowledged_at = fields.Datetime(
        string='Acknowledged At',
    )

    # Failure tracking
    failure_reason = fields.Text(
        string='Failure Reason',
    )

    # Idempotency
    idempotency_key = fields.Char(
        string='Idempotency Key',
        compute='_compute_idempotency_key',
        store=True,
        index=True,
    )

    # Queued job reference
    job_uuid = fields.Char(
        string='Job UUID',
    )

    _sql_constraints = [
        (
            'uniq_design_file_route_idempotency_key',
            'UNIQUE(idempotency_key)',
            'A design.file.route with this idempotency_key already exists.',
        ),
    ]

    def init(self):
        """Create DB-level objects that Odoo's declarative path may miss.

        - UNIQUE(idempotency_key) constraint as a belt-and-braces mirror of
          _sql_constraints (see memory project_sql_constraints_drift.md).
        - Indexes for hot-path lookups: (design_file_id, state, create_date)
          for the stuck-route badge computation.
        """
        cr = self.env.cr

        # Index for stuck-route badge and route lookups
        cr.execute("""
            CREATE INDEX IF NOT EXISTS design_file_route_design_file_id_state_idx
                ON design_file_route (design_file_id, state, create_date DESC)
        """)

        # Index on design_file_id for FK traversal
        cr.execute("""
            CREATE INDEX IF NOT EXISTS design_file_route_design_file_id_idx
                ON design_file_route (design_file_id)
        """)

        # Index on idempotency_key (from UNIQUE constraint)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS design_file_route_idempotency_key_idx
                ON design_file_route (idempotency_key)
        """)

        # Belt-and-braces: ensure UNIQUE constraint exists at DB level.
        # Use pg_constraint IF NOT EXISTS check (NOT EXCEPTION clause) to
        # ensure idempotency on re-run (-u); PG raises duplicate_table (42P07)
        # on CONSTRAINT re-create, not duplicate_object (42710).
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_design_file_route_idempotency_key'
                ) THEN
                    ALTER TABLE design_file_route
                        ADD CONSTRAINT uniq_design_file_route_idempotency_key
                        UNIQUE (idempotency_key);
                END IF;
            END $$
        """)

    # --------------------------------------------------------------- Constraints

    @api.constrains('recipient_partner_id', 'recipient_user_id', 'recipient_type')
    def _check_recipient_xor(self):
        """C-DR-001: Exactly one of recipient_partner_id or recipient_user_id
        must be set, matching the recipient_type.

        Internal recipients (mp, ba, pd) require recipient_user_id.
        Partner recipients (partner_gearment, partner_other) require
        recipient_partner_id.
        """
        for route in self:
            has_partner = bool(route.recipient_partner_id)
            has_user = bool(route.recipient_user_id)

            # Exactly one must be set
            if not (has_partner or has_user):
                raise ValidationError(
                    _('Either "Recipient Partner" or "Recipient User" must be set.')
                )

            if has_partner and has_user:
                raise ValidationError(
                    _('Only one of "Recipient Partner" or "Recipient User" can be set.')
                )

            # Type must match recipient type
            is_internal = route.recipient_type in ('mp', 'ba', 'pd')
            is_partner = route.recipient_type in ('partner_gearment', 'partner_other')

            if is_internal and has_partner:
                raise ValidationError(
                    _(
                        'Recipient type "%(type)s" is internal — '
                        'set "Recipient User", not "Recipient Partner".',
                        type=dict(route._fields['recipient_type'].selection).get(route.recipient_type, route.recipient_type),
                    )
                )

            if is_partner and has_user:
                raise ValidationError(
                    _(
                        'Recipient type "%(type)s" is a partner — '
                        'set "Recipient Partner", not "Recipient User".',
                        type=dict(route._fields['recipient_type'].selection).get(route.recipient_type, route.recipient_type),
                    )
                )

    @api.constrains('state', 'failure_reason')
    def _check_failure_reason_required_when_failed(self):
        """C-DR-003: failure_reason required when state='failed'."""
        for route in self:
            if route.state == 'failed' and not route.failure_reason:
                raise ValidationError(
                    _('Failure reason is required when route state is "Failed".')
                )

    # --------------------------------------------------------------- Computations

    @api.depends(
        'design_file_id',
        'recipient_user_id',
        'recipient_partner_id',
        'delivery_method',
    )
    def _compute_idempotency_key(self):
        """Compute SHA-256 idempotency_key from identity tuple.

        Format: {design_file_id}_{recipient_id}_{delivery_method}

        recipient_id = recipient_user_id if set, else recipient_partner_id,
        else empty string (edge case, should be caught by constraint).

        This ensures that re-dispatching the same file to the same recipient
        via the same method is idempotent (no duplicate enqueue).
        """
        for route in self:
            recipient_id = ''
            if route.recipient_user_id:
                recipient_id = str(route.recipient_user_id.id)
            elif route.recipient_partner_id:
                recipient_id = str(route.recipient_partner_id.id)

            identity_tuple = (
                f"{route.design_file_id.id}"
                f"_{recipient_id}"
                f"_{route.delivery_method}"
            )

            route.idempotency_key = hashlib.sha256(
                identity_tuple.encode()
            ).hexdigest()

    # --------------------------------------------------------------- Helpers

    def _check_production_team_or_raise(self):
        """RPC-level gate per FR-017 / feedback_fr017_write_defense_in_depth.

        Action methods must check `has_group()` explicitly: the
        `ir.model.access.csv` ACL guards CRUD but not arbitrary action-method
        calls via XML-RPC. Without this gate, a salesman with read-only ACL
        could call route.action_dispatch() and mutate state.
        """
        if self.env.user.has_group('multichannel_hub_core.group_production_team'):
            return
        if self.env.user.has_group('base.group_system'):
            return
        raise AccessError(_(
            "Only members of the Production Team may change the delivery "
            "state of a design.file.route."
        ))

    # --------------------------------------------------------------- Actions

    def action_dispatch(self):
        """Initiate delivery of this route.

        Sets state='sent' and sent_at=now(). Actual GDrive/Gearment API
        calls are mocked in tests and deferred to P1-02c (GDrive upload
        wizard integration).

        In production, this is called by design_file_router.dispatch() after
        queuing the route via queue_job (P1-02c with 5-retry backoff).
        """
        self._check_production_team_or_raise()
        for route in self:
            route.write({
                'state': 'sent',
                'sent_at': fields.Datetime.now(),
            })
        _logger.debug(
            "Dispatched %d design.file.route(s); state set to 'sent'",
            len(self),
        )

    def action_acknowledge(self):
        """Mark this route as acknowledged by the recipient.

        Sets state='acknowledged' and acknowledged_at=now(). Called when
        the recipient confirms receipt (e.g., via manual UI button or
        webhook from GDrive sharing API).
        """
        self._check_production_team_or_raise()
        for route in self:
            route.write({
                'state': 'acknowledged',
                'acknowledged_at': fields.Datetime.now(),
            })
        _logger.debug(
            "Acknowledged %d design.file.route(s); state set to 'acknowledged'",
            len(self),
        )
