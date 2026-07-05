"""sale.order extensions added by multichannel_hub_core.

P1-05 added the `_inherits` delegation to `sale.order.fulfillment`.
P1-01a adds the operator-dashboard fields:

- `sales_channel` / `channel_order_ref` — multi-channel foundation (FR-024).
- `qty_total` — stored compute summing order_line qty (decoration-info).
- `is_duplicate_buyer` — 7-day window detection on partner_id (T026).
- `is_overdue_approval` — open todo activity past 24h on Etsy orders (T027).

P1-02b adds the design routing fields:

- `stuck_route_badge` — computed badge showing if any design.file.route is
  pending/failed and >2h old (T073).
- `action_confirm()` hook — enqueues routing dispatch for approved files (T075).
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _inherits = {'sale.order.fulfillment': 'fulfillment_id'}

    fulfillment_id = fields.Many2one(
        'sale.order.fulfillment',
        string='Fulfillment',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # P1-01a — multi-channel foundation (FR-024).
    sales_channel = fields.Selection(
        selection=[
            ('etsy', 'Etsy'),
            ('amazon', 'Amazon'),
            ('website', 'Website'),
            ('other', 'Other'),
        ],
        string='Sales Channel',
        required=True, default='other', index=True, tracking=True,
        help='Source channel of the order. Backfilled to "etsy" for '
             'existing Etsy orders by FR-025 migration.')
    channel_order_ref = fields.Char(
        string='Channel Order Reference',
        index=True, copy=False, tracking=True,
        help='External order reference within the source channel '
             '(e.g., Etsy receipt id, Amazon order id).')

    # P1-01a — Order Dashboard support fields.
    qty_total = fields.Float(
        string='Total Quantity',
        compute='_compute_qty_total', store=True,
        help='Sum of order line quantities. Drives the qty>=2 row '
             'decoration on the Order Dashboard (FR-003).')
    is_duplicate_buyer = fields.Boolean(
        string='Duplicate Buyer',
        compute='_compute_is_duplicate_buyer', store=True, index=True,
        help='True if this partner placed another non-cancel order in '
             'the previous 7 days. Drives the duplicate-buyer row '
             'decoration on the Order Dashboard (FR-003).')
    is_overdue_approval = fields.Boolean(
        string='Overdue Approval',
        compute='_compute_is_overdue_approval', store=True, index=True,
        help='True when an open To Do mail.activity on this order has '
             'date_deadline >24h ago. Etsy orders only, excludes '
             'cancelled. Recomputed daily by '
             'cron_recompute_overdue_approval (FR-009).')

    # P1-02b — Design file routing
    design_file_ids = fields.One2many(
        'design.file',
        'order_id',
        string='Design Files',
        help='Order-level design files (mockups, etc.). Line-level files are accessed via order_line.design_file_ids.',
    )

    stuck_route_badge = fields.Boolean(
        string='Stuck Route Badge',
        compute='_compute_stuck_route_badge',
        store=False,
        help='True if any design.file.route on this order is pending/failed '
             'and >2h old. Shows the stuck-route alert badge on Order Dashboard.')

    # P1-OPS-DESIGN-LINK — smart-button count for header + line design files.
    design_files_count = fields.Integer(
        string='Design Files Count',
        compute='_compute_design_files_count',
        help='Total number of design.file records attached to this order '
             '(header + line). Drives the smart button on the order form.')

    # P1-IMG-DASH-COL — product image aggregate for dashboard rendering.
    order_image_128 = fields.Binary(
        string='Product Image',
        compute='_compute_order_image_128',
        store=False,
        attachment=False,
        readonly=True,
        help='First non-empty product_image_thumb from order_line_ids. '
             'Fallback to subsequent lines if earlier are empty. '
             'P1-IMG-DASH-COL; depends on P1-IMG-LINE-WIDGET.')

    # P1-PIPELINE-MIN — fulfillment route resolved from product/category master data.
    x_pipeline_id = fields.Many2one(
        'order.pipeline',
        string='Fulfillment Pipeline',
        compute='_compute_x_pipeline_id',
        store=True,
        index=True,
        help='Resolved per ADR-010 §2: order line product.template '
             '→ product.category → ICP fallback. Recomputed when order_line / '
             'product changes.',
    )
    x_pipeline_channel_hint = fields.Selection(
        related='x_pipeline_id.channel_hint',
        string='Pipeline Channel',
        store=True,
        readonly=True,
    )

    # P1-PIPELINE-FULL — current stage on the resolved pipeline.
    x_pipeline_state_id = fields.Many2one(
        'order.pipeline.state',
        string='Pipeline State',
        ondelete='set null',
        index=True,
        tracking=True,
        domain="[('pipeline_id', '=', x_pipeline_id)]",
        help="Current stage on the order's pipeline. Auto-assigned to "
             "x_pipeline_id.initial_state_id on first resolve. Mutate via "
             "_write_pipeline_state(new_state, note) to persist a "
             "transition.log row in the same transaction.",
    )

    # P-D3-PIPELINE-UI — read-only transition history surfaced on the form's
    # Pipeline tab. Inverse of order.pipeline.transition.log.sale_order_id.
    pipeline_transition_log_ids = fields.One2many(
        'order.pipeline.transition.log',
        'sale_order_id',
        string='Pipeline History',
        readonly=True,
    )

    # P1-01b — channel-agnostic order-level fields lifted from owner's daily-ops
    # Excel (.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx). Coexist with the
    # etsy_* equivalents in etsy_integration during operator UAT (DECISION 1
    # in p1-01b-plan.md); cleanup deferred to follow-up slice.
    gift_message = fields.Char(
        string='Gift Message',
        tracking=True,
        help='Channel-agnostic gift message lifted from buyer-supplied data.')
    processing_time = fields.Char(
        string='Processing Time',
        tracking=True,
        help='Channel-supplied processing time label (e.g. "1-3 days"). '
             'Free-text to accommodate channels that ship various encodings.')
    discount_code = fields.Char(
        string='Discount Code',
        tracking=True,
        help='Channel-supplied discount/promo code applied at checkout.')
    shipping_service_label = fields.Char(
        string='Shipping Service Label',
        tracking=True,
        help='Operator/channel-supplied shipping service label. Falls back '
             'to shipping_carrier_id.name in the Operations Dashboard when '
             'unset.')
    shipping_cost = fields.Char(
        string='Shipping Cost (Display)',
        tracking=True,
        help='Free-text shipping cost as supplied by the channel; placeholder '
             'until the delivery module dependency is added per follow-up. '
             'Channel ingest populates with the raw cost label (e.g. "$4.50").')

    _sql_constraints = []  # Reserved for downstream slices.

    # NB: the composite (sales_channel, has_pending_address_change) index
    # required by data-model.md §1 lives in etsy_integration's sale_order
    # extension because `has_pending_address_change` is defined there
    # (mhc does not depend on etsy_integration).

    @api.model_create_multi
    def create(self, vals_list):
        # Stamp the reverse pointer on the auto-created fulfillment sibling
        # so the Tracking Dashboard + bulk action can traverse from
        # fulfillment → order without an extra search. Idempotent.
        orders = super().create(vals_list)
        Log = self.env['order.pipeline.transition.log']
        for order in orders:
            if order.fulfillment_id and not order.fulfillment_id.order_id:
                order.fulfillment_id.order_id = order.id
            # P1-PIPELINE-FULL: stamp initial pipeline state + audit log.
            pipeline = order.x_pipeline_id
            if (pipeline and pipeline.initial_state_id
                    and not order.x_pipeline_state_id):
                # Bypass write() defense (below) for the system-driven initial
                # stamp — guarded by `bypass_pipeline_state_guard` context.
                order.with_context(
                    bypass_pipeline_state_guard=True,
                ).x_pipeline_state_id = pipeline.initial_state_id
                # sudo: transition log is system-of-record; initial state
                # assignment is automatic and audited. Bypass bounded to log
                # row creation here — the order field write above runs under
                # the user's ACL.
                Log.sudo().create({
                    'sale_order_id': order.id,
                    'pipeline_id': pipeline.id,
                    'from_state_id': False,
                    'to_state_id': pipeline.initial_state_id.id,
                    'change_type': 'initial',
                    'note': _('Initial state on order create'),
                })
        return orders

    def write(self, vals):
        """FR-017 defense-in-depth: reject direct x_pipeline_state_id writes.

        State transitions must go through `_write_pipeline_state(...)` so an
        audit row lands in `order.pipeline.transition.log` in the same
        transaction. The helper sets `bypass_pipeline_state_guard` in context
        before its own field write to opt out of this check.
        """
        if (
            'x_pipeline_state_id' in vals
            and not self.env.context.get('bypass_pipeline_state_guard')
        ):
            raise ValidationError(_(
                "Direct writes to 'Pipeline State' are not allowed. "
                "Use sale.order._write_pipeline_state(new_state, note) so "
                "the transition is recorded in the audit log."
            ))
        return super().write(vals)

    def _write_pipeline_state(self, new_state, note=None,
                              change_type='manual'):
        """Transition this order to a new pipeline state; persist audit log.

        Validates new_state belongs to the order's pipeline, writes the log
        row + the field in the same transaction. Caller may wrap in their
        own try/except to handle ValidationError.

        :param new_state: order.pipeline.state recordset (1 record)
        :param note: optional human-readable transition reason
        :param change_type: enum value from order.pipeline.transition.log.change_type
        """
        self.ensure_one()
        if not new_state:
            raise ValidationError(_("Cannot transition to an empty state."))
        new_state.ensure_one()
        if self.x_pipeline_id and new_state.pipeline_id != self.x_pipeline_id:
            raise ValidationError(_(
                "State '%(state)s' belongs to pipeline '%(other)s', not the "
                "order's pipeline '%(own)s'.",
                state=new_state.name,
                other=new_state.pipeline_id.name,
                own=self.x_pipeline_id.name,
            ))
        if new_state.next_state_ids:
            # Enforcement deferred — pipelines without next_state_ids set are
            # treated as "any forward move allowed". Strict enforcement lands
            # in P1-PIPELINE-FULL+ once the seed graph is complete.
            pass
        # P1-MTO-SYNC: terminal-stage guard. Manual writes to a terminal
        # pipeline state require all linked mrp.production records to be in
        # a terminal MO state ('done' or 'cancel'). Automatic writes (sync
        # hooks, ADR-007 callsites) bypass this guard. Non-MTO orders (no
        # MOs) skip naturally because the search returns empty.
        # Note: callers passing change_type='automatic' bypass the guard by
        # design — this is the FR-017 9th-confirmation dismissable flavor
        # (composing already-writable fields via documented internal callers,
        # audited via the transition log's change_type column).
        if change_type == 'manual' and new_state.is_terminal:
            productions = self.env['mrp.production'].search(
                [('origin', '=', self.name)])
            unfinished = productions.filtered(
                lambda mo: mo.state not in ('done', 'cancel'))
            if unfinished:
                raise ValidationError(_(
                    "Cannot move order '%(order)s' to terminal stage "
                    "'%(state)s' while linked manufacturing order(s) "
                    "%(mos)s are not yet done. Mark the MO(s) as done first.",
                    order=self.name,
                    state=new_state.name,
                    mos=', '.join(unfinished.mapped('name')),
                ))
        from_state = self.x_pipeline_state_id
        # Bypass the write() guard — this helper IS the audited path.
        self.with_context(
            bypass_pipeline_state_guard=True,
        ).x_pipeline_state_id = new_state.id
        # sudo: transition log is system-of-record; salesman may transition
        # their own orders but should not write log rows directly. Bypass is
        # bounded to this helper.
        self.env['order.pipeline.transition.log'].sudo().create({
            'sale_order_id': self.id,
            'pipeline_id': new_state.pipeline_id.id,
            'from_state_id': from_state.id if from_state else False,
            'to_state_id': new_state.id,
            'change_type': change_type,
            'note': note,
        })

    def action_open_pipeline_transition_wizard(self):
        """P-D3 — open the transition wizard for the Pipeline tab button."""
        self.ensure_one()
        if not self.x_pipeline_id:
            raise UserError(_(
                "This order has no fulfillment pipeline resolved yet. Add a "
                "product whose category or template maps to a pipeline first."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Change Pipeline State'),
            'res_model': 'order.pipeline.transition.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    @api.depends(
        'order_line',
        'order_line.product_id',
        'order_line.product_id.product_tmpl_id.x_default_pipeline_id',
        'order_line.product_id.product_tmpl_id.categ_id',
        'order_line.product_id.product_tmpl_id.categ_id.x_default_pipeline_id',
        'order_line.product_id.product_tmpl_id.categ_id.parent_id',
    )
    def _compute_x_pipeline_id(self):
        from ..services.pipeline_resolver import resolve_pipeline_for_order
        for order in self:
            order.x_pipeline_id = resolve_pipeline_for_order(order)

    @api.depends('order_line', 'order_line.product_uom_qty')
    def _compute_qty_total(self):
        for order in self:
            order.qty_total = sum(order.order_line.mapped('product_uom_qty'))

    @api.depends('partner_id', 'date_order', 'state')
    def _compute_is_duplicate_buyer(self):
        """Stored compute. NOTE: directionally only the *new* sibling
        flips True automatically; the *earlier* order stays stale until
        `_cron_recompute_duplicate_buyer` runs (daily). The migration
        wizard creates 1000s of orders per cohort — doing per-record
        retroactive recompute in `create()` is O(N²) and locks up the
        wizard. Plan R2 trade-off: dashboard correctness within ≤24h.
        """
        for order in self:
            if not order.partner_id or order.state == 'cancel':
                order.is_duplicate_buyer = False
                continue
            window_start = (order.date_order or fields.Datetime.now()) - timedelta(days=7)
            window_end = (order.date_order or fields.Datetime.now()) + timedelta(days=7)
            siblings = self.search_count([
                ('id', '!=', order.id),
                ('partner_id', '=', order.partner_id.id),
                ('state', '!=', 'cancel'),
                ('date_order', '>=', window_start),
                ('date_order', '<=', window_end),
            ])
            order.is_duplicate_buyer = bool(siblings)

    def _cron_recompute_duplicate_buyer(self):
        """Daily cron — sweep all non-cancel orders in the trailing
        7-day window so retroactive duplicates flip True without
        per-create work."""
        cutoff = fields.Datetime.now() - timedelta(days=8)
        candidates = self.search([
            ('state', '!=', 'cancel'),
            ('date_order', '>=', cutoff),
        ])
        candidates.invalidate_recordset(['is_duplicate_buyer'])
        candidates._compute_is_duplicate_buyer()

    @api.depends('sales_channel', 'state', 'activity_ids',
                 'activity_ids.date_deadline', 'activity_ids.activity_type_id')
    def _compute_is_overdue_approval(self):
        """Recomputed on activity-related changes; daily cron picks up
        cases where merely the calendar advanced past a deadline (no
        write triggered the depends).
        """
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        cutoff = fields.Date.today() - timedelta(days=1)
        for order in self:
            if order.sales_channel != 'etsy' or order.state == 'cancel':
                order.is_overdue_approval = False
                continue
            overdue = order.activity_ids.filtered(
                lambda a: (
                    (not todo or a.activity_type_id == todo)
                    and a.date_deadline
                    and a.date_deadline < cutoff
                )
            )
            order.is_overdue_approval = bool(overdue)

    def _cron_recompute_overdue_approval(self):
        """Daily cron — invalidates the compute on every non-cancel
        Etsy order so the dashboard reflects deadlines that tipped over
        purely from the calendar advancing (no DB write triggers the
        depends chain).
        """
        candidates = self.search([
            ('sales_channel', '=', 'etsy'),
            ('state', '!=', 'cancel'),
        ])
        candidates.invalidate_recordset(['is_overdue_approval'])
        candidates._compute_is_overdue_approval()

    @api.depends('design_file_ids.route_ids.state',
                 'design_file_ids.route_ids.create_date',
                 'order_line.design_file_ids.route_ids.state',
                 'order_line.design_file_ids.route_ids.create_date')
    def _compute_stuck_route_badge(self):
        """Compute stuck_route_badge: True if any route pending/failed >2h old.

        Checks all design.file.route records attached to design_file rows
        on the order (order-level files) and the order's lines (line-level files).
        A route is "stuck" if:
        - state IN ('pending', 'failed')
        - create_date < now() - 2 hours (Odoo auto-timestamp; matches data-model
          §7 created_at semantics — both are set on insert)

        Used to show a warning badge on the Order Dashboard when file routing
        is delayed or has errored.
        """
        cutoff = fields.Datetime.now() - timedelta(hours=2)
        for order in self:
            # Collect routes from both order-level and line-level design files
            order_routes = order.design_file_ids.route_ids
            line_routes = order.order_line.design_file_ids.route_ids
            all_routes = order_routes | line_routes
            stuck = any(
                r.state in ('pending', 'failed') and r.create_date and r.create_date < cutoff
                for r in all_routes
            )
            order.stuck_route_badge = stuck

    def action_confirm(self):
        """Override order confirmation to enqueue design file routing.

        After calling super().action_confirm(), for each design.file on the
        order with state='approved', call design_file_router.dispatch() to
        enqueue routes to the internal production team.

        Dispatch failures are caught and logged (do not block confirm).
        If routes exist in pending/failed state after dispatch, post a chatter
        message to alert the operator.
        """
        res = super().action_confirm()
        self._after_confirm_routing()
        return res

    def _after_confirm_routing(self):
        """Helper: route approved design files on order confirmation.

        Enqueues routes for all approved design files and posts chatter alert
        if any routes are outstanding (pending/failed).
        """
        Router = self.env['design.file.router']
        for order in self:
            # Find approved design files on this order's lines
            approved_files = order.order_line.design_file_ids.filtered(
                lambda f: f.state == 'approved'
            )

            # Dispatch each approved file
            for design_file in approved_files:
                try:
                    Router.dispatch(design_file.id)
                except Exception as exc:
                    _logger.warning(
                        "design routing dispatch failed for design.file %s "
                        "on order %s: %s",
                        design_file.id, order.id, exc,
                    )

            # Post chatter if routes are outstanding
            outstanding = approved_files.route_ids.filtered(
                lambda r: r.state in ('pending', 'failed')
            )
            if outstanding:
                order.message_post(
                    body=_(
                        'Design routing in progress — monitor the '
                        'stuck-route badge.'
                    )
                )

    def unlink(self):
        # `_inherits` makes sale.order a variant of sale.order.fulfillment;
        # the fulfillment record is the "parent" and is not auto-deleted when
        # the variant is deleted (same semantics as product.product /
        # product.template). ADR-007's contract is that the sibling row is
        # 1:1 with the order — when the order is gone, its fulfillment row
        # has no reason to exist. Cascade explicitly here.
        #
        # sudo() rationale: the cascade is system-enforced data integrity,
        # not a user-initiated operation on the fulfillment row. The user's
        # permission to delete the *order* is what gates this code path
        # (super().unlink() above runs the ACL check on sale.order). Once
        # the order is gone, the orphaned 1:1 sibling must follow regardless
        # of whether the user holds perm_unlink on sale.order.fulfillment.
        # Without sudo, sales-users with order-unlink rights but no
        # fulfillment-unlink rights would hit a confusing AccessError after
        # the order had already been deleted (rolled back by the transaction).
        fulfillments = self.fulfillment_id
        result = super().unlink()
        fulfillments.sudo().exists().unlink()
        return result

    # ------------------------------------------------------------------
    # P1-DASH-MERGE — bulk Mark Shipped on the unified Operations list
    # ------------------------------------------------------------------
    def action_bulk_mark_shipped(self):
        """Wrapper for bulk Mark Shipped on the unified Operations Dashboard.

        The server action ``action_server_bulk_mark_shipped`` is bound to
        ``sale.order`` (P1-DASH-MERGE) so its ``records`` recordset is
        sale.order. Delegate to ``sale.order.fulfillment.action_bulk_mark_shipped``
        which holds the canonical FR-017 silent-skip on
        has_pending_address_change + production_team RPC gate.
        """
        return self.fulfillment_id.action_bulk_mark_shipped()

    # ------------------------------------------------------------------
    # P1-DESIGN+GEARMENT — Order Dashboard kanban actions
    # ------------------------------------------------------------------
    def _all_design_files(self):
        """Return all design.file records on this order (header + line)."""
        return self.design_file_ids | self.order_line.design_file_ids

    def action_dashboard_send_proof(self):
        """Send a proof for every pending/rejected design file on the order.

        FR-017 RPC gate. Used by Order Dashboard kanban "Gửi Proof" button.
        """
        # Cross-module check via has_group; group_ba_shipping declared by
        # multichannel_hub_fulfillment, group_production_team by mhc.
        u = self.env.user
        if not (u.has_group('multichannel_hub_fulfillment.group_ba_shipping')
                or u.has_group('multichannel_hub_core.group_production_team')
                or u.has_group('base.group_system')):
            raise AccessError(_(
                "Only BA Shipping or Production Team members may send "
                "design proofs."))
        sent = 0
        for order in self:
            files = order._all_design_files().filtered(
                lambda f: f.state in ('pending', 'rejected'))
            if files:
                files.action_send_proof_to_buyer()
                sent += len(files)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _("Design proofs sent"),
                'message': _("%s design file(s) flipped to 'proof_sent'.", sent),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_dashboard_approve_designs(self):
        """Approve every proof_sent design file on the order.

        FR-017 RPC gate — production team only (MP role).
        """
        u = self.env.user
        if not (u.has_group('multichannel_hub_core.group_production_team')
                or u.has_group('base.group_system')):
            raise AccessError(_(
                "Only Production Team members may approve design files."))
        approved = 0
        for order in self:
            files = order._all_design_files().filtered(
                lambda f: f.state == 'proof_sent')
            if files:
                files.action_approve()
                approved += len(files)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _("Designs approved"),
                'message': _("%s design file(s) flipped to 'approved'.", approved),
                'type': 'success',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # P1-OPS-DESIGN-LINK — sale.order form hooks (smart button + tab)
    # ------------------------------------------------------------------
    @api.depends('design_file_ids', 'order_line.design_file_ids')
    def _compute_design_files_count(self):
        for order in self:
            order.design_files_count = len(order._all_design_files())

    @api.depends('order_line.product_image_thumb')
    def _compute_order_image_128(self):
        for order in self:
            thumb = False
            for line in order.order_line:
                if line.product_image_thumb:
                    thumb = line.product_image_thumb
                    break
            order.order_image_128 = thumb

    def action_open_design_files(self):
        """Open the design.file list scoped to this order's files.

        Used by the smart button on the sale.order form (Slice 1).
        """
        self.ensure_one()
        files = self._all_design_files()
        return {
            'name': _("Design Files"),
            'type': 'ir.actions.act_window',
            'res_model': 'design.file',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', files.ids)],
            'context': {'default_order_id': self.id},
        }

    def action_open_design_file_upload_wizard(self):
        """Open the design-file upload wizard pre-bound to this order.

        FR-017 RPC gate (10th confirmation): only Production Team or
        system may trigger uploads. The wizard itself enforces the same
        gate, but defending here surfaces AccessError before the wizard
        view loads — better UX than a half-rendered modal.
        """
        self.ensure_one()
        u = self.env.user
        if not (u.has_group('multichannel_hub_core.group_production_team')
                or u.has_group('base.group_system')):
            raise AccessError(_(
                "Only Production Team members may upload design files."))
        action = self.env['ir.actions.act_window']._for_xml_id(
            'multichannel_hub_core.design_file_upload_wizard_action')
        action['context'] = {
            'default_order_id': self.id,
        }
        return action

    # ------------------------------------------------------------------
    # P-KPI-01 — Operations Dashboard KPI band (mockup-v3 plan)
    # ------------------------------------------------------------------

    @api.model
    def get_operations_dashboard_kpis(self):
        """Counts for the KPI band above the Operations Dashboard list.

        Called by the `operations_dashboard_list` js_class renderer. Uses
        search_count as the current user, so ACLs and record rules apply —
        each user sees counts over the records they can read.
        """
        today_start = fields.Datetime.to_datetime(fields.Date.context_today(self))
        return [
            {
                'key': 'orders_today',
                'label': _('New Orders Today'),
                'value': self.search_count([
                    ('date_order', '>=', today_start),
                    ('state', '!=', 'cancel'),
                ]),
            },
            {
                'key': 'to_fulfill',
                'label': _('To Fulfill'),
                'value': self.search_count([
                    ('state', '=', 'sale'),
                    ('delivery_status', 'in', ('pending', 'started', 'partial')),
                ]),
            },
            {
                'key': 'designs_pending',
                'label': _('Designs Awaiting Approval'),
                'value': self._kpi_safe_count('design.file', [
                    ('state', '=', 'pending'),
                ]),
            },
            {
                'key': 'channel_errors',
                'label': _('Channel Errors'),
                'value': self._kpi_safe_count('product.channel.status', [
                    ('state', '=', 'error'),
                ]),
            },
        ]

    @api.model
    def _kpi_safe_count(self, model_name, domain):
        """search_count that degrades to 0 when the user lacks read access.

        The KPI band must never crash the dashboard view for a user whose
        groups can open the list but cannot read a side model (e.g.
        design.file is production/sales gated).
        """
        try:
            return self.env[model_name].search_count(domain)
        except AccessError:
            return 0
