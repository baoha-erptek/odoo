"""sale.order extensions added by multichannel_hub_core.

P1-05 added the `_inherits` delegation to `sale.order.fulfillment`.
P1-01a adds the operator-dashboard fields:

- `sales_channel` / `channel_order_ref` — multi-channel foundation (FR-024).
- `qty_total` — stored compute summing order_line qty (decoration-info).
- `is_duplicate_buyer` — 7-day window detection on partner_id (T026).
- `is_overdue_approval` — open todo activity past 24h on Etsy orders (T027).
"""

from datetime import timedelta

from odoo import api, fields, models


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

    _sql_constraints = []  # Reserved for downstream slices.

    # NB: the composite (sales_channel, has_pending_address_change) index
    # required by data-model.md §1 lives in etsy_integration's sale_order
    # extension because `has_pending_address_change` is defined there
    # (mhc does not depend on etsy_integration).

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
