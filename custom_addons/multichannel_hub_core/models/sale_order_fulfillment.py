from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


# Fields whose changes trigger a bus.bus push to the tracking dashboard.
# Writes touching only fields outside this set are silent (operator notes,
# routine edits) — keeps the channel signal-to-noise ratio high.
_BUS_TRIGGER_FIELDS = frozenset({
    'tracking_number',
    'tracking_state',
    'label_status',
    'shipping_date',
    'production_blocked',
    'block_reason',
})

# FR-017 — fields that move an order toward shipped state. Writes to any
# of these while the parent order has a pending address-change request
# are blocked at the write() boundary, defending against direct-RPC
# bypass of action_bulk_mark_shipped(). Override via context flag
# `bypass_address_change_check=True` (intended for system tooling /
# explicit operator override, not normal flows).
_ADDRESS_LOCK_FIELDS = frozenset({
    'tracking_number',
    'tracking_state',
    'shipping_date',
    'label_status',
})


class SaleOrderFulfillment(models.Model):
    _name = 'sale.order.fulfillment'
    _description = 'Fulfillment lifecycle for a sale order'
    _inherit = ['mail.thread']
    _order = 'id desc'

    # Reverse pointer for the dashboard view + bulk-action parent lookup.
    # Stamped at sale.order.create() time and backfilled by migration
    # 19.0.1.0.4 for existing rows. Not declared via _inherits because
    # P1-05 chose Direction A (sale.order → fulfillment); we need the
    # reverse for read paths (dashboard columns, address-change check).
    order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        index=True,
        ondelete='cascade',
        copy=False,
    )

    # Mirror of `sale.order.has_pending_address_change` (declared by
    # etsy_integration). Computed via getattr so that mhc remains
    # architecturally independent of etsy_integration — when that
    # module is absent, the column stays False and the Tracking
    # Dashboard's `decoration-warning` simply never fires.
    order_address_change_pending = fields.Boolean(
        string='Order Address Change Pending',
        compute='_compute_order_address_change_pending',
        store=False,
        help='Mirror of order_id.has_pending_address_change for the '
             "Tracking Dashboard list-view decoration. False when the "
             'etsy_integration module is not installed.',
    )

    tracking_number = fields.Char(string='Tracking Number', index=True, tracking=True)
    shipping_date = fields.Date(string='Shipping Date', tracking=True)
    shipping_carrier_id = fields.Many2one(
        'shipping.carrier',
        string='Shipping Carrier',
        ondelete='set null',
        index=True,
        tracking=True,
    )
    label_status = fields.Selection(
        [
            ('none', 'None'),
            ('requested', 'Requested'),
            ('buying', 'Buying'),
            ('bought', 'Bought'),
            ('failed', 'Failed'),
        ],
        string='Label Status',
        default='none',
        required=True,
        tracking=True,
    )
    tracking_state = fields.Selection(
        [
            ('none', 'None'),
            ('label_requested', 'Label Requested'),
            ('label_ready', 'Label Ready'),
            ('shipped', 'Shipped'),
            ('in_transit', 'In Transit'),
            ('delivered', 'Delivered'),
            ('returned', 'Returned'),
        ],
        string='Tracking State',
        default='none',
        required=True,
        tracking=True,
    )
    mp_note = fields.Text(string='Marketing Note', tracking=True)
    pd_note = fields.Text(string='Production Note', tracking=True)
    pic_user_id = fields.Many2one(
        'res.users',
        string='Person In Charge',
        ondelete='set null',
        index=True,
        tracking=True,
    )
    pd_pic_user_id = fields.Many2one(
        'res.users',
        string='Production PIC',
        ondelete='set null',
        index=True,
        tracking=True,
        help="Production team's person in charge (distinct from BA's pic_user_id).",
    )
    order_priority = fields.Selection(
        [
            ('normal', 'Normal'),
            ('push', 'Push'),
            ('urgent', 'Urgent'),
        ],
        string='Order Priority',
        default='normal',
        required=True,
        tracking=True,
    )
    production_blocked = fields.Boolean(string='Production Blocked', default=False, tracking=True)
    block_reason = fields.Text(string='Block Reason', tracking=True)
    warehouse_zone = fields.Selection(
        [
            ('vn', 'Vietnam'),
            ('us', 'United States'),
        ],
        string='Warehouse Zone',
        index=True,
        tracking=True,
        help="Logical warehouse selector (not stock.location). VN or US.",
    )
    fulfillment_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('produced', 'Produced'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
        ],
        string='Fulfillment Status',
        default='pending',
        required=True,
        tracking=True,
    )

    @api.constrains('production_blocked', 'block_reason')
    def _check_block_reason_when_blocked(self):
        for record in self:
            if record.production_blocked and not (record.block_reason and record.block_reason.strip()):
                raise ValidationError(_(
                    "A block reason is required when production is blocked."
                ))

    # ---------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._bus_push_fulfillment_update()
        return records

    def write(self, vals):
        # FR-017 defense-in-depth — block ship-progress writes when the
        # parent order has a pending address-change request. The bulk
        # action filters first; this guard catches direct-RPC writes that
        # would otherwise bypass FR-017. Context flag exists for system
        # tooling / explicit operator override.
        if (
            _ADDRESS_LOCK_FIELDS.intersection(vals.keys())
            and not self.env.context.get('bypass_address_change_check')
        ):
            # sudo() — read-only check on parent order state; production
            # users may not hold direct sale.order read ACL.
            blocked = self.sudo().filtered(
                lambda r: r.order_id and r.order_id.has_pending_address_change
            )
            if blocked:
                raise UserError(_(
                    "Cannot update shipping fields while an address-change "
                    "approval is pending on order(s): %s",
                    ', '.join(blocked.order_id.mapped('name')),
                ))

        # Push only when a tracked-on-dashboard field actually changes.
        # Filter early — avoid spam from routine note edits or audit writes.
        relevant = _BUS_TRIGGER_FIELDS.intersection(vals.keys())
        result = super().write(vals)
        if relevant:
            # Prefetch parent orders once — avoids N+1 traversal inside the
            # per-record bus emit loop on bulk writes.
            self.sudo().mapped('order_id')
            for record in self:
                record._bus_push_fulfillment_update()
        return result

    # ---------------------------------------------------------------- helpers
    def _bus_push_fulfillment_update(self):
        """Emit one notification per record on the tracking-dashboard channel.

        sudo() rationale: production-team users may not hold direct read
        ACL on sale.order, but the bus payload includes the order name as
        a row identifier for the dashboard. Read-only.
        """
        self.ensure_one()
        order = self.sudo().order_id
        payload = {
            'fulfillment_id': self.id,
            'order_id': order.id if order else False,
            'order_name': order.name if order else '',
            'tracking_number': self.tracking_number or '',
            'tracking_state': self.tracking_state or '',
            'label_status': self.label_status or '',
            'updated_by': self.env.user.id,
            'updated_at': fields.Datetime.now().isoformat(),
        }
        self.env['bus.bus']._sendone(
            'multichannel_hub.fulfillment_update',
            'fulfillment_update',
            payload,
        )

    # ---------------------------------------------------------------- actions
    def action_bulk_mark_shipped(self):
        """T035 + T061 — silent-skip rows with pending address-change + warn.

        RPC gate: only production_team or system. Salesman-tier users hit
        AccessError. Address-change-pending rows are filtered before write
        and listed in a sticky warning notification per FR-017.
        """
        if not (
            self.env.user.has_group('multichannel_hub_core.group_production_team')
            or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(_(
                "Only production-team or system users may bulk-mark orders shipped."
            ))

        # sudo() rationale: production-team users may not hold direct read
        # ACL on sale.order, but the bulk action MUST consult the parent
        # order's has_pending_address_change flag to honour FR-017.
        # Read-only check; the actual fulfillment write below runs in the
        # caller's context so write ACLs still apply.
        sudoed = self.sudo()
        excluded_ids = {
            r.id for r in sudoed
            if r.order_id and r.order_id.has_pending_address_change
        }
        excluded = self.filtered(lambda r: r.id in excluded_ids)
        to_process = self - excluded
        to_process.write({
            'shipping_date': fields.Date.context_today(self),
            'tracking_state': 'shipped',
        })

        if not excluded:
            return True

        # Reuse the sudoed read for the order names — same justification.
        excluded_refs = ', '.join(excluded.sudo().order_id.mapped('name'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(
                    'Shipped %(processed)d order(s); skipped %(skipped)d',
                    processed=len(to_process),
                    skipped=len(excluded),
                ),
                'message': _(
                    'Skipped (pending address-change approval): %s',
                    excluded_refs,
                ),
                'type': 'warning',
                'sticky': True,
            },
        }

    @api.depends('order_id')
    def _compute_order_address_change_pending(self):
        """Mirror order.has_pending_address_change without a hard
        dependency on etsy_integration.

        Uses getattr() so installations without etsy_integration still
        render the Tracking Dashboard list view (the field returns False
        and the decoration-warning never fires).
        """
        for rec in self:
            order = rec.order_id
            rec.order_address_change_pending = bool(
                getattr(order, 'has_pending_address_change', False))
