"""etsy.listing — Etsy shop listing metadata mirror (Spec 008 P-LIST-PULL).

Standalone Model per ADR-013 (NOT `_inherits('product.template')`).
Slice 1 scope is US1: listing *metadata* only. The variant-derived
computed fields described in data-model.md §1 (`variant_count`,
`unlinked_variant_count`, `drift_status`) and the `etsy.listing.product`
child depend on Slice 2 (P-LIST-INV-PULL) and are intentionally absent
here; `quantity` is the plain listing-level integer Etsy returns, not a
sum over children.

Soft delete only (ADR-013): a listing that disappears upstream is
flagged `is_active=False, state='deleted'` so the future drift report
and audit trail can still see it. No hard `unlink()` from sync.
"""

import logging
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Written on create; never overwritten on re-sync (ADR-013 immutability).
_IMMUTABLE_ON_RESYNC = ('url', 'created_at', 'shop_id', 'etsy_listing_id')


class EtsyListing(models.Model):
    _name = 'etsy.listing'
    _description = 'Etsy Listing'
    _order = 'last_modified desc, id desc'
    _rec_name = 'title'

    shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop',
        required=True, ondelete='cascade', index=True,
    )
    etsy_listing_id = fields.Char(
        string='Etsy Listing ID', required=True, index=True,
    )
    title = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    url = fields.Char(
        string='Etsy URL',
        help='Immutable after first ingest (ADR-013).',
    )
    price = fields.Float(string='Price')
    quantity = fields.Integer(
        string='Quantity',
        help='Listing-level quantity from the Etsy listings endpoint. '
             'Variant-level inventory is Slice 2 (P-LIST-INV-PULL).',
    )
    state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
            ('deleted', 'Deleted'),
        ],
        string='State', required=True,
    )
    created_at = fields.Datetime(
        string='Created At (Etsy)',
        help='Immutable after first ingest (ADR-013).',
    )
    last_modified = fields.Datetime(string='Last Modified (Etsy)', index=True)
    last_synced_at = fields.Datetime(
        string='Last Synced At', required=True, default=fields.Datetime.now,
    )
    is_active = fields.Boolean(string='Active', required=True, default=True)

    _sql_constraints = [
        (
            'etsy_listing_shop_listing_uniq',
            'UNIQUE(shop_id, etsy_listing_id)',
            'A listing with this Etsy ID already exists for this shop.',
        ),
    ]

    def init(self):
        """C-LIST-001 raw-SQL UNIQUE mirror — `_sql_constraints` is not
        reliably deployed across this codebase's addons (project drift
        invariant). pg_constraint IF NOT EXISTS pre-check (NOT an
        EXCEPTION clause — PG raises duplicate_table 42P07 on re-run,
        not duplicate_object)."""
        super().init()
        self.env.cr.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                     WHERE conname = 'etsy_listing_shop_listing_uniq'
                ) THEN
                    ALTER TABLE etsy_listing
                    ADD CONSTRAINT etsy_listing_shop_listing_uniq
                    UNIQUE (shop_id, etsy_listing_id);
                END IF;
            END $$;
            """
        )

    # ------------------------------------------------------------------
    # Sync orchestration
    # ------------------------------------------------------------------

    @api.model
    def _cron_sync_listings(self):
        """Scheduled: pull listing metadata for every `active_source='api'`
        shop. Per-shop isolation so one bad shop does not poison the rest.

        Privilege: the cron runner is `__system__`. The explicit
        `_is_system()` gate is defense-in-depth (FR-017) in case this is
        ever exposed via RPC/controller — a non-admin must never trigger
        a sync.
        """
        if not self.env.user._is_system():
            raise AccessError(
                'Etsy listing sync is restricted to system tasks; '
                'this method is only callable by the cron runner.'
            )
        shops = self.env['etsy.shop'].search([('active_source', '=', 'api')])
        if not shops:
            _logger.debug('Etsy listing sync: no api-source shops configured.')
            return
        for shop in shops:
            try:
                self._sync_shop_listings(shop)
            except Exception:
                _logger.exception(
                    'Etsy listing sync failed for shop %s (id=%s)',
                    shop.name, shop.id,
                )

    @api.model
    def _cron_topup_pod_quantities(self):
        """FLW-07 — re-push a target quantity to active listings running low.

        Etsy decrements listing quantity per sale and auto-deactivates at 0;
        POD products carry no Odoo stock, so the top-up target is the ICP
        `etsy_integration.pod_topup_quantity` (absent/0 = disabled — the
        cron ships OFF until the owner sets a target, e.g. 50). Any active
        `etsy.listing.product` mirror row below the target triggers one
        `push_inventory` for its listing with the target as quantity
        override. Per-listing isolation: one Etsy 4xx/5xx must not block
        the remaining top-ups.
        """
        if not self.env.user._is_system():
            raise AccessError(
                'Etsy quantity top-up is restricted to system tasks; '
                'this method is only callable by the cron runner.'
            )
        icp = self.env['ir.config_parameter'].sudo()
        try:
            target = int(icp.get_param(
                'etsy_integration.pod_topup_quantity', '0') or 0)
        except ValueError:
            _logger.warning(
                'FLW-07: non-numeric etsy_integration.pod_topup_quantity; '
                'top-up disabled.')
            return
        if target <= 0:
            return
        rows = self.env['etsy.listing.product'].search([
            ('is_active', '=', True),
            ('quantity', '<', target),
            ('product_id', '!=', False),
            ('listing_id.state', '=', 'active'),
        ])
        if not rows:
            return
        from ..services.etsy_listing_publisher import EtsyListingPublisher
        publisher = EtsyListingPublisher(
            self.with_context(etsy_qty_override=target).env)
        done_listing_ids = set()
        for row in rows:
            listing = row.listing_id
            if listing.id in done_listing_ids:
                continue
            done_listing_ids.add(listing.id)
            try:
                publisher.push_inventory(
                    row.product_id.product_tmpl_id,
                    listing.etsy_listing_id,
                    listing.shop_id,
                )
            except Exception:
                _logger.warning(
                    'FLW-07 quantity top-up failed for listing %s (shop %s)',
                    listing.etsy_listing_id, listing.shop_id.name,
                    exc_info=True,
                )

    @api.model
    def _sync_shop_listings(self, shop):
        """One read-only pull pass for `shop`: upsert fetched listings,
        soft-delete any active listing absent from the fetch, write one
        `etsy.api.log` audit row (`source='listing_pull'`)."""
        # See etsy_order_syncer.sync_shop_orders for the shared rationale
        # — Odoo PK != Etsy shop_id; refuse the API call without it.
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            _logger.warning(
                'Etsy listing sync: shop %s (id=%s) has no '
                'etsy_api_shop_id; skipping.',
                shop.name, shop.id,
            )
            return {'created': 0, 'updated': 0, 'soft_deleted': 0}

        adapter = self._build_adapter(shop)
        seen = set()
        created = updated = 0
        error_message = None
        try:
            for raw in adapter.fetch_listings(api_shop_id, since=None):
                listing_id = str(raw.get('listing_id'))
                seen.add(listing_id)
                vals = self._listing_vals_from_raw(raw, shop)
                existing = self.search([
                    ('shop_id', '=', shop.id),
                    ('etsy_listing_id', '=', listing_id),
                ], limit=1)
                if existing:
                    mutable = {
                        k: v for k, v in vals.items()
                        if k not in _IMMUTABLE_ON_RESYNC
                    }
                    existing.write(mutable)
                    updated += 1
                else:
                    self.create(vals)
                    created += 1
            soft_deleted = self._soft_delete_absent(shop, seen)
        except Exception as exc:  # noqa: BLE001 — recorded then re-raised
            error_message = str(exc)
            # P-UAT-FIX-API-LOG-HTTP-STATUS: surface the last HTTP status
            # the client saw (set even on HTTP-error before raise_for_status).
            self._write_audit(
                shop, created, updated, 0, error_message,
                http_status=getattr(adapter._client, 'last_http_status', 0),
            )
            raise
        self._write_audit(
            shop, created, updated, soft_deleted, None,
            http_status=getattr(adapter._client, 'last_http_status', 0),
        )
        return {
            'created': created, 'updated': updated,
            'soft_deleted': soft_deleted,
        }

    @api.model
    def _build_adapter(self, shop):
        """Factory hook — overridable by tests via mock.patch (mirrors
        EtsyOrderSyncer._build_adapter)."""
        from ..services.etsy_api_client import EtsyApiClient
        from ..services.etsy_listing_adapter import EtsyListingAdapter
        return EtsyListingAdapter(EtsyApiClient(shop))

    def _soft_delete_absent(self, shop, seen_listing_ids):
        """Listings present in Odoo + active but absent from this fetch
        are soft-deleted (never hard-unlinked) per ADR-013."""
        stale = self.search([
            ('shop_id', '=', shop.id),
            ('is_active', '=', True),
            ('etsy_listing_id', 'not in', list(seen_listing_ids) or [False]),
        ])
        if stale:
            stale.write({'is_active': False, 'state': 'deleted'})
        return len(stale)

    @api.model
    def _listing_vals_from_raw(self, raw, shop):
        """Map a raw Etsy v3 listing dict to `etsy.listing` vals.
        Money is `{amount, divisor, currency_code}`; timestamps are
        unix seconds (same shapes EtsyApiAdapter handles)."""
        return {
            'shop_id': shop.id,
            'etsy_listing_id': str(raw.get('listing_id')),
            'title': raw.get('title') or '',
            'description': raw.get('description') or False,
            'url': raw.get('url') or False,
            'price': self._money_amount(raw.get('price')),
            'quantity': int(raw.get('quantity') or 0),
            'state': raw.get('state') or 'active',
            'created_at': self._unix_to_datetime(
                raw.get('created_timestamp')),
            'last_modified': self._unix_to_datetime(
                raw.get('last_modified_tsz')
                or raw.get('updated_timestamp')),
            'last_synced_at': fields.Datetime.now(),
        }

    def _write_audit(self, shop, created, updated, soft_deleted, error,
                     http_status=0):
        """One `etsy.api.log` row per shop sync. sudo(): the log model
        is system-create-only; the cron is already `__system__` so this
        is defensive redundancy that also lets a manual admin trigger
        write the row without elevating their session.

        The error-path row is written on the same cursor: the cron
        (`_cron_sync_listings`) swallows the per-shop exception (no
        re-raise → no Odoo job-runner rollback), so the row persists on
        the cron's normal commit. (Defect-05's fresh-cursor durability
        applied to a controller that returns 400 and rolls back; this
        cron does not.)

        `http_status` is sourced from the adapter's client by the caller;
        per P-UAT-FIX-API-LOG-HTTP-STATUS it must be > 0 when the row
        carries no error_message, so Flow-2 TC-003 can converge."""
        self.env['etsy.api.log'].sudo().create({
            'shop_id': shop.id,
            'endpoint': 'GET /v3/application/shops/%s/listings' % (
                shop.sudo().etsy_api_shop_id or shop.id,
            ),
            'source': 'listing_pull',
            'http_status': http_status,
            'response_summary': (
                'listing_pull: created=%d updated=%d soft_deleted=%d'
                % (created, updated, soft_deleted)
            ),
            'error_message': error or False,
        })

    @staticmethod
    def _money_amount(money) -> float:
        if not money:
            return 0.0
        amount = money.get('amount') or 0
        divisor = money.get('divisor') or 1
        return amount / divisor

    @staticmethod
    def _unix_to_datetime(ts):
        if not ts:
            return False
        # tz-aware convert then strip tzinfo: Odoo Datetime fields are
        # naive UTC and reject tz-aware values. (datetime.utcfromtimestamp
        # is deprecated for removal in Python 3.13.)
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(
            tzinfo=None)
