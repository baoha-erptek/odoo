import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError

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

    # Spec 005 P0-16c — channel-source selector per ADR-002. Two values
    # only; new shops default to 'email_only' until E1 scope review +
    # per-shop cutover (P1-11). The syncer cron only fires for
    # 'api_only' shops; 'email_only' shops continue using the Gmail
    # cron (`_cron_fetch_etsy_emails`).
    sync_mode = fields.Selection(
        selection=[
            ('email_only', 'Email Only'),
            ('api_only', 'API Only'),
        ],
        string='Sync Mode',
        default='email_only',
        required=True,
        groups='base.group_system',
        help='Email Only: legacy Gmail-cron ingest. API Only: Etsy v3 '
             'receipts cron ingest. Switch via P1-11 cutover only.',
    )
    # Spec 005 P0-16c (architect Q4) — when True the API syncer runs
    # read-only: fetch receipts, log via _logger.warning, write zero
    # sale.orders. Used during the 1-2 week pilot-shop cutover window
    # for BA validation (ADR-002 §3). Soft-warn (no constraint) if both
    # this and `sync_mode='api_only'` are True at sync time — see OQ4.
    sync_audit_mode = fields.Boolean(
        string='Audit Mode (read-only sync)',
        default=False,
        groups='base.group_system',
        help='Read-only API sync: fetch receipts, compare, log diffs; '
             'no sale.order writes. Use during cutover validation.',
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

    # ------------------------------------------------------------------
    # P1-10: Fernet-at-rest token helpers.
    #
    # Decision D-P1-10-01 (helper-method indirection over raw Char
    # columns): callers route through these four helpers; the columns
    # store Fernet ciphertext, the helpers handle encrypt/decrypt at
    # the boundary. Production callers: `controllers/etsy_oauth.py` on
    # token persistence; `services/etsy_api_client.py` on refresh +
    # session-header reads. Direct `.etsy_oauth_access_token` reads
    # outside these call sites are a regression (see findings.md
    # §P1-10 for the grep-CI gate).
    #
    # sudo() rationale: the three token columns carry
    # `groups='base.group_system'` (P0-14) so non-system writes/reads
    # raise AccessError. The cron + controller paths run under the
    # cron actor (system) or under the OAuth callback (system after
    # check_access_rule on the shop); calling user may not be system,
    # so we sudo at the boundary inside each helper.
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Decrypt and return the Etsy access token; '' if unset.

        Lazy-migration fallback (D-P1-10-03): if the column holds a
        non-Fernet value (P0-14 plaintext from before this slice),
        return it as-is and log once. Next refresh writes ciphertext
        via `_set_access_token`.
        """
        self.ensure_one()
        ciphertext = self.sudo().etsy_oauth_access_token or ''
        if not ciphertext:
            return ''
        if not ciphertext.startswith('gAAAAA'):
            _logger.warning(
                "etsy.shop[id=%s] token column holds non-Fernet content "
                "(P0-14 plaintext); returning as-is. Re-encrypt by "
                "running a token refresh.", self.id,
            )
            return ciphertext
        from ..services.fernet_crypto import decrypt
        return decrypt(ciphertext, self.env)

    def _set_access_token(self, plaintext: str) -> None:
        """Encrypt and persist the Etsy access token. '' clears the column."""
        self.ensure_one()
        from ..services.fernet_crypto import encrypt
        ciphertext = encrypt(plaintext, self.env) if plaintext else False
        self.sudo().write({'etsy_oauth_access_token': ciphertext})
        # Flush so callers reading the raw column via SQL (audit
        # tooling, drift checks) see the ciphertext immediately.
        self.sudo().flush_recordset(['etsy_oauth_access_token'])

    def _get_refresh_token(self) -> str:
        """Decrypt and return the Etsy refresh token; '' if unset.

        Same lazy-migration fallback as `_get_access_token` —
        non-Fernet values are returned as-is for the one-call
        migration window.
        """
        self.ensure_one()
        ciphertext = self.sudo().etsy_oauth_refresh_token or ''
        if not ciphertext:
            return ''
        if not ciphertext.startswith('gAAAAA'):
            _logger.warning(
                "etsy.shop[id=%s] refresh-token column holds non-Fernet "
                "content (P0-14 plaintext); returning as-is.", self.id,
            )
            return ciphertext
        from ..services.fernet_crypto import decrypt
        return decrypt(ciphertext, self.env)

    def _set_refresh_token(self, plaintext: str) -> None:
        """Encrypt and persist the Etsy refresh token. '' clears the column."""
        self.ensure_one()
        from ..services.fernet_crypto import encrypt
        ciphertext = encrypt(plaintext, self.env) if plaintext else False
        self.sudo().write({'etsy_oauth_refresh_token': ciphertext})
        self.sudo().flush_recordset(['etsy_oauth_refresh_token'])

    @api.model
    def _cron_sync_orders(self):
        """Scheduled action: incremental Etsy receipts sync per shop.

        OQ5: Cron filters to shops with `sync_mode='api_only'` only.
        Audit-mode flag is honored by the syncer but does NOT trigger
        the cron; audit runs are typically manual during cutover.

        Privilege: cron runner sets the user to `__system__`. The
        explicit `_is_system()` gate is defense-in-depth in case this
        ever gets exposed via RPC or a controller route — we never
        want a non-admin caller to trigger sync (security-reviewer
        P0-16c HIGH, mitigated).
        """
        if not self.env.user._is_system():
            raise AccessError(
                'Etsy order sync is restricted to system tasks; '
                'this method is only callable by the cron runner.'
            )

        from ..services.etsy_order_syncer import EtsyOrderSyncer

        shops = self.search([('sync_mode', '=', 'api_only')])
        if not shops:
            _logger.debug('Etsy API sync cron: no api_only shops configured.')
            return

        syncer = EtsyOrderSyncer(self.env)
        for shop in shops:
            try:
                syncer.sync_shop_orders(shop)
            except Exception:
                # Per-shop isolation: one shop's failure must not stop
                # others. The syncer logs internally; log here too with
                # shop context for cron-level diagnostics.
                _logger.exception(
                    'Etsy API sync failed for shop %s (id=%s)',
                    shop.name, shop.id,
                )
