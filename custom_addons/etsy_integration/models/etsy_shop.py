import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

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

    # Real Etsy API shop_id (e.g. 60752333 for JaHandmadeArt), distinct
    # from the Odoo PK `id`. The sandbox-era convention
    # `etsy.shop.id == Etsy shop_id` (memory item #132) does not survive
    # real shop creation: Etsy assigns its own large numeric ids. All
    # /v3/application/shops/{shop_id}/... URLs must use this field.
    # NULL is legal on email-only shops (they never hit the API);
    # required (by convention, not constraint) before `active_source`
    # flips to 'api'. Auto-bootstrap from /users/me on OAuth callback
    # is deferred to follow-up slice P1-11-SHOPID-BOOTSTRAP.
    etsy_api_shop_id = fields.Char(
        string='Etsy Shop ID',
        index=True,
        groups='base.group_system',
        help='Numeric shop_id assigned by Etsy (visible in seller '
             'dashboard URL). Used in /v3/application/shops/{shop_id}/* '
             'URLs. Must be set before flipping Active Source to '
             '"Etsy API".',
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

    # Spec 011 P-PUB-CLIENT T003 — Etsy publisher defaults per shop. The
    # three Integer IDs are sensitive (Etsy account-side identifiers) and
    # gated to base.group_system. The three enums are operator-editable
    # within BA group via standard form-view ACL.
    default_taxonomy_id = fields.Integer(
        string='Default Etsy Taxonomy ID',
        groups='base.group_system',
        help='Etsy taxonomy node id used as the default for createDraftListing.',
    )
    default_shipping_profile_id = fields.Integer(
        string='Default Etsy Shipping Profile ID',
        groups='base.group_system',
        help='Etsy shipping profile id used as the default for createDraftListing.',
    )
    default_return_policy_id = fields.Integer(
        string='Default Etsy Return Policy ID',
        groups='base.group_system',
        help='Etsy return policy id used as the default for createDraftListing.',
    )
    default_who_made = fields.Selection(
        selection=[
            ('i_did', 'I did'),
            ('someone_else', 'Someone else'),
            ('collective', 'A member of my shop'),
        ],
        string='Default "Who made it"',
        default='i_did',
    )
    default_when_made = fields.Char(
        string='Default "When was it made"',
        default='made_to_order',
        help='Etsy when_made enum value (e.g. made_to_order, 2020_2026).',
    )
    default_is_supply = fields.Boolean(
        string='Default "Is Supply"',
        default=False,
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

    # Spec 005 P1-11a — ADR-008a §2 source-switching architecture.
    # `active_source` supersedes `sync_mode` (ADR-002) as the canonical
    # adapter selector; `sync_mode` is kept (not dropped) for the dual-
    # column transition window and is mapped by the post-migration.
    # `tracking=True` from data-model.md §1 is intentionally omitted:
    # `etsy.shop` does not inherit `mail.thread`; adding the mixin is
    # out of P1-11a surgical scope (see findings.md).
    active_source = fields.Selection(
        selection=[('api', 'Etsy API'), ('email', 'Email')],
        string='Active Source',
        default='email',
        required=True,
        help='Which upstream adapter feeds the single ingestion '
             'pipeline for this shop (ADR-008a). Toggling is restricted '
             'to system administrators (C-ESY-002).',
    )
    active_source_changed_at = fields.Datetime(
        string='Active Source Changed At',
        help='Set automatically on every active_source transition.',
    )
    auto_recovery = fields.Boolean(
        string='Auto Recovery',
        default=True,
        required=True,
        help='When False, the recovery probe never auto-switches the '
             'shop back to its primary source (ADR-008a §3).',
    )
    health_check_consecutive_failures = fields.Integer(
        string='Health-Check Consecutive Failures',
        default=0,
        help='Counter for the 3-failure auto-failover threshold. '
             'Reset to 0 on a successful probe.',
    )
    recovery_probe_consecutive_successes = fields.Integer(
        string='Recovery-Probe Consecutive Successes',
        default=0,
        help='Counter for the 6-success recovery threshold. '
             'Reset to 0 on a failed probe.',
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Shop name must be unique!'),
    ]

    def init(self):
        """Install a BEFORE INSERT trigger so rows created outside the
        ORM (raw-SQL inserts, the dual-column transition window) still
        get a deterministic `active_source` mapped from the legacy
        `sync_mode`, plus non-null `auto_recovery` / counter defaults.

        Raw SQL justification: ORM field defaults are applied in
        `create()` only; rows inserted directly into `etsy_shop`
        (migrations, data-fix scripts, tests) would otherwise leave
        `active_source` NULL and violate the `required=True` invariant.
        The trigger mirrors the post-migration CASE mapping exactly.

        Idempotent: `CREATE OR REPLACE FUNCTION` plus a `pg_trigger`
        existence pre-check (NOT an EXCEPTION clause — PG raises on
        duplicate trigger), per the project _sql_constraints-drift
        house pattern.
        """
        self.env.cr.execute("""
            CREATE OR REPLACE FUNCTION etsy_shop_active_source_default_fn()
            RETURNS trigger AS $fn$
            BEGIN
                IF NEW.sync_mode IS NULL THEN
                    NEW.sync_mode := 'email_only';
                END IF;
                IF NEW.active_source IS NULL THEN
                    NEW.active_source := CASE NEW.sync_mode
                        WHEN 'api_only' THEN 'api'
                        WHEN 'email_only' THEN 'email'
                        ELSE 'email' END;
                END IF;
                IF NEW.auto_recovery IS NULL THEN
                    NEW.auto_recovery := TRUE;
                END IF;
                IF NEW.health_check_consecutive_failures IS NULL THEN
                    NEW.health_check_consecutive_failures := 0;
                END IF;
                IF NEW.recovery_probe_consecutive_successes IS NULL THEN
                    NEW.recovery_probe_consecutive_successes := 0;
                END IF;
                RETURN NEW;
            END;
            $fn$ LANGUAGE plpgsql;
        """)
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgname = 'etsy_shop_active_source_default'
                ) THEN
                    CREATE TRIGGER etsy_shop_active_source_default
                        BEFORE INSERT ON etsy_shop
                        FOR EACH ROW
                        EXECUTE FUNCTION etsy_shop_active_source_default_fn();
                END IF;
            END $$;
        """)

    @api.constrains('active_source', 'etsy_oauth_access_token',
                    'etsy_oauth_refresh_token')
    def _check_api_source_has_tokens(self):
        """C-ESY-001: `active_source='api'` requires both OAuth tokens.

        sudo() rationale: the two token columns carry
        `groups='base.group_system'`; the constraint must read them
        regardless of which (system) user triggered the write.
        """
        for shop in self:
            if shop.active_source != 'api':
                continue
            shop_su = shop.sudo()
            if not shop_su.etsy_oauth_access_token:
                raise ValidationError(
                    "Etsy OAuth access token is required when "
                    "active_source is 'api' (C-ESY-001)."
                )
            if not shop_su.etsy_oauth_refresh_token:
                raise ValidationError(
                    "Etsy OAuth refresh token is required when "
                    "active_source is 'api' (C-ESY-001)."
                )

    def write(self, vals):
        """FR-017 write-level mirror of the C-ESY-002 UI gate, plus
        append-only source-change audit logging.

        The form field is system-group-gated in the view; this method
        gate is the security boundary (RPC-bypassable otherwise — 18
        prior FR-017 confirmations). `env.su` is allowed so internal
        sudo paths (token setters, migration backfills) are unaffected;
        those never write `active_source` anyway.
        """
        if ('active_source' in vals
                and not self.env.su
                and not self.env.user._is_system()):
            raise AccessError(
                "The 'active_source' field on Etsy Shop is restricted "
                "to system administrators (C-ESY-002 / FR-017)."
            )

        track = 'active_source' in vals
        if track and 'active_source_changed_at' not in vals:
            vals = dict(vals, active_source_changed_at=fields.Datetime.now())
        old_source = {s.id: s.active_source for s in self} if track else {}

        result = super().write(vals)

        if track:
            actor_id = self.env.user.id
            now = fields.Datetime.now()
            # sudo(): the audit model is create-only for base.group_system;
            # the change itself is already authorised by the gate above.
            log_model = self.env['etsy.shop.source.change.log'].sudo()
            for shop in self:
                previous = old_source.get(shop.id)
                if previous == shop.active_source:
                    continue
                log_model.create({
                    'shop_id': shop.id,
                    'from_source': previous or False,
                    'to_source': shop.active_source,
                    'reason': 'manual',
                    'actor_user_id': actor_id,
                    'changed_at': now,
                    'health_check_failures_at_change':
                        shop.health_check_consecutive_failures,
                })
        return result

    def _probe_api(self):
        """T050 — health probe for the API adapter: lightweight read
        against the Etsy ping endpoint. Returns True on HTTP 2xx.

        Used by the health-check cron and by `action_test_connection`
        (P1-11-RUNBOOK) to drive the 3-failure auto-failover counter
        and the operator UI toast.
        """
        self.ensure_one()
        from ..services.etsy_api_client import EtsyApiClient
        try:
            EtsyApiClient(self).get('openapi-ping')
            return True
        except Exception as exc:
            # Bumped from debug→warning 2026-05-22 after the operator
            # toast surfaced "probe failed" with no log evidence on
            # log_level=info. We still don't include the exception
            # message in the audit channel (may carry token fragments
            # via session headers in trace contexts) — just the type +
            # shop identity for triage.
            _logger.warning(
                'Etsy API probe failed for shop %s (id=%s): %s',
                self.name, self.id, type(exc).__name__,
            )
            return False

    def _probe_email(self, fresh_hours=24):
        """T050 — health probe for the email adapter: the Gmail-sourced
        ingest is healthy if any receipt email was processed within
        `fresh_hours`. `etsy.email.log` is shop-agnostic (one Gmail
        inbox feeds all shops), so this is a global freshness check.
        Returns bool; no caller in P1-11a.
        """
        self.ensure_one()
        threshold = fields.Datetime.now() - timedelta(hours=fresh_hours)
        recent = self.env['etsy.email.log'].sudo().search_count([
            ('date_received', '>=', threshold),
        ])
        return recent > 0

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

    def action_authorize_etsy(self):
        """T017 — open the OAuth2 PKCE authorize flow for this shop.

        Hands the browser to the `/etsy/api/oauth/authorize` controller
        route (auth='user'), which generates the PKCE verifier and
        redirects to Etsy's consent screen; on callback it persists
        Fernet-encrypted tokens for this shop.

        System-only (FR-017 defense-in-depth): the route writes
        privileged OAuth credentials for this shop, so the gate is
        enforced here at the method — the view `groups=` only hides
        the button and is RPC-bypassable on its own.
        """
        self.ensure_one()
        if not self.env.user._is_system():
            raise AccessError(
                'Authorizing an Etsy shop is restricted to system '
                'administrators.'
            )
        return {
            'type': 'ir.actions.act_url',
            'url': '/etsy/api/oauth/authorize?shop_id=%s' % self.id,
            'target': 'self',
        }

    def action_test_connection(self):
        """T017 — operator connectivity check before an `active_source`
        cutover. Probes the Etsy API with this shop's stored OAuth
        tokens (wraps `_probe_api()` → GET /v3/application/openapi-ping)
        and surfaces the result as a UI notification.

        System-only (FR-017 defense-in-depth): this triggers an
        outbound Etsy API call with the shop's system OAuth
        credentials, so the gate is enforced at the method — the view
        `groups=` only hides the button.
        """
        self.ensure_one()
        if not self.env.user._is_system():
            raise AccessError(
                'Testing the Etsy connection is restricted to system '
                'administrators.'
            )
        reachable = self._probe_api()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Etsy Connection',
                'message': (
                    'Etsy API is reachable.' if reachable
                    else 'Etsy API probe failed — check the server logs.'
                ),
                'type': 'success' if reachable else 'warning',
                'sticky': False,
            },
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

        OQ5: Cron filters to shops with `active_source='api'` only
        (ADR-008a §2 — supersedes the legacy `sync_mode='api_only'`
        filter; mapped 1:1 by the P1-11a post-migration).
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

        shops = self.search([('active_source', '=', 'api')])
        if not shops:
            _logger.debug('Etsy API sync cron: no api-source shops configured.')
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
