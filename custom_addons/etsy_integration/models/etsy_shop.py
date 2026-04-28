import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EtsyShop(models.Model):
    _name = 'etsy.shop'
    _description = 'Etsy Shop'
    _order = 'name'

    name = fields.Char(string='Shop Name', required=True, index=True)
    active = fields.Boolean(default=True)
    order_ids = fields.One2many('sale.order', 'etsy_shop_id', string='Orders')
    order_count = fields.Integer(
        string='Order Count', compute='_compute_order_count')
    revenue_total = fields.Float(
        string='Total Revenue', compute='_compute_order_count')

    # Etsy OAuth2 PKCE token storage (P0-14, sandbox-mode 2026-04-27).
    # Plaintext for Phase 0 with system-only field-level read ACL; Fernet
    # encryption deferred to Phase 1 (P1-10) per Spec 005 findings Q2.
    etsy_oauth_access_token = fields.Char(
        string='Etsy OAuth Access Token',
        groups='base.group_system',
    )
    etsy_oauth_refresh_token = fields.Char(
        string='Etsy OAuth Refresh Token',
        groups='base.group_system',
    )
    etsy_oauth_token_expires_at = fields.Datetime(
        string='Etsy OAuth Token Expires At',
    )

    # Spec 005 P0-16b1 — incremental-sync watermark. The `EtsyOrderSyncer`
    # (P0-16c) reads this when calling the adapter's `fetch_new_orders`
    # and writes a fresh value once the batch ingests cleanly. NULL on
    # newly created shops; the syncer treats NULL as "fetch from the
    # configured floor" (a quarter-day lookback or shop creation date,
    # decision deferred to P0-16c).
    # System-only ACL parity with the OAuth token fields above —
    # operators have no business reading or writing the sync watermark
    # directly; only the syncer cron (running as system) needs access.
    # P0-16b1 security review HIGH: tighten before P0-16c orchestrator.
    etsy_last_receipt_sync_at = fields.Datetime(
        string='Etsy Last Receipt Sync At',
        groups='base.group_system',
        help='Watermark for incremental Etsy receipt sync. The syncer '
             'fetches receipts modified after this timestamp.',
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Shop name must be unique!'),
    ]

    @api.depends('order_ids')
    def _compute_order_count(self):
        for shop in self:
            orders = shop.order_ids
            shop.order_count = len(orders)
            shop.revenue_total = sum(orders.mapped('amount_total'))

    def action_view_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Orders - {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('etsy_shop_id', '=', self.id)],
            'context': {'default_etsy_shop_id': self.id},
        }
