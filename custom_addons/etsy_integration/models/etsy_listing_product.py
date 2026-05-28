"""etsy.listing.product — Etsy listing variant snapshot (Spec 008
P-LIST-INV-PULL, US2/US3/US4).

One2many child of `etsy.listing` (P-LIST-PULL). A timestamped mirror of
the Etsy variant matrix + the dual-index link to `product.product`
(ADR-013 §2): SKU-based discovery sets `product_id`; an operator may
override it (preserved on resync — R-L6). Soft delete only.

SKU-match domain note: ADR-013 §2 assumed `(company_id, default_code)`,
but `etsy.shop` has no `company_id` field in this single-company
codebase, so matching is by `default_code` alone; duplicate
`default_code` is warn-logged and resolved first-by-id (deterministic).
Recorded in specs/008 findings.md.
"""

import json
import logging
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class EtsyListingProduct(models.Model):
    _name = 'etsy.listing.product'
    _description = 'Etsy Listing Variant'
    _order = 'id desc'

    listing_id = fields.Many2one(
        'etsy.listing', string='Listing',
        required=True, ondelete='cascade', index=True,
    )
    etsy_product_id = fields.Char(
        string='Etsy Product ID', required=True, index=True,
    )
    sku = fields.Char(string='SKU', index=True)
    property_values = fields.Text(string='Property Values (JSON)')
    quantity = fields.Integer(string='Etsy Quantity')
    price = fields.Float(string='Etsy Price')
    product_id = fields.Many2one(
        'product.product', string='Odoo Product',
        ondelete='set null', index=True,
    )
    is_active = fields.Boolean(string='Active', required=True, default=True)
    last_synced_at = fields.Datetime(
        string='Last Synced At', required=True, default=fields.Datetime.now,
    )
    odoo_qty = fields.Integer(
        string='Odoo Quantity', compute='_compute_odoo_qty')
    qty_drift = fields.Integer(
        string='Qty Drift', compute='_compute_qty_drift')

    # NOTE: inert in Odoo 19 (memory #135) — kept for documentation/intent
    # only. Actual enforcement is the init() raw-SQL mirror below.
    _sql_constraints = [
        (
            'etsy_listing_product_listing_prod_uniq',
            'UNIQUE(listing_id, etsy_product_id)',
            'This Etsy variant already exists for this listing.',
        ),
    ]

    def init(self):
        """C-LPROD-001 raw-SQL UNIQUE mirror. Odoo 19 makes
        `_sql_constraints` inert (memory #135) — this mirror is the
        sole enforcement. pg_constraint IF NOT EXISTS pre-check
        (project drift template)."""
        super().init()
        self.env.cr.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                     WHERE conname =
                       'etsy_listing_product_listing_prod_uniq'
                ) THEN
                    ALTER TABLE etsy_listing_product
                    ADD CONSTRAINT
                      etsy_listing_product_listing_prod_uniq
                    UNIQUE (listing_id, etsy_product_id);
                END IF;
            END $$;
            """
        )

    @api.depends('product_id')
    def _compute_odoo_qty(self):
        for rec in self:
            rec.odoo_qty = (
                rec.product_id.qty_available if rec.product_id else 0)

    @api.depends('quantity', 'odoo_qty')
    def _compute_qty_drift(self):
        for rec in self:
            rec.qty_drift = rec.quantity - rec.odoo_qty

    @api.constrains('product_id', 'sku')
    def _check_c_lprod_002(self):
        """C-LPROD-002: a linked product's default_code must equal the
        variant SKU (data-integrity guard)."""
        for rec in self:
            if rec.product_id and rec.product_id.default_code != rec.sku:
                raise ValidationError(
                    "Linked product SKU '%s' does not match the Etsy "
                    "variant SKU '%s' (C-LPROD-002)."
                    % (rec.product_id.default_code, rec.sku)
                )

    # ------------------------------------------------------------------
    # Sync orchestration (mirrors etsy.listing P-LIST-PULL)
    # ------------------------------------------------------------------

    @api.model
    def _cron_sync_variants(self):
        """Scheduled: pull the variant matrix for every active listing of
        each `active_source='api'` shop. FR-017 system gate before any
        side effect; per-shop isolation."""
        if not self.env.user._is_system():
            raise AccessError(
                'Etsy variant sync is restricted to system tasks; '
                'this method is only callable by the cron runner.'
            )
        shops = self.env['etsy.shop'].search([('active_source', '=', 'api')])
        for shop in shops:
            try:
                self._sync_shop_variants(shop)
            except Exception:
                _logger.exception(
                    'Etsy variant sync failed for shop %s (id=%s)',
                    shop.name, shop.id,
                )

    @api.model
    def _sync_shop_variants(self, shop):
        """One read-only pass: for each active listing of `shop`, fetch
        the variant matrix, upsert, soft-delete absent variants, run
        SKU matching, write one `etsy.api.log` audit row."""
        adapter = self._build_adapter(shop)
        listings = self.env['etsy.listing'].search([
            ('shop_id', '=', shop.id), ('is_active', '=', True)])
        created = updated = soft_deleted = 0
        for listing in listings:
            seen = set()
            for raw in adapter.fetch_variants(listing.etsy_listing_id):
                pid = str(raw.get('product_id'))
                seen.add(pid)
                vals = self._variant_vals_from_raw(raw, listing)
                existing = self.search([
                    ('listing_id', '=', listing.id),
                    ('etsy_product_id', '=', pid),
                ], limit=1)
                if existing:
                    existing.write(vals)
                    rec = existing
                    updated += 1
                else:
                    rec = self.create(dict(
                        vals, listing_id=listing.id, etsy_product_id=pid))
                    created += 1
                self._match_variant(rec)
            soft_deleted += self._soft_delete_absent(listing, seen)
        self._write_audit(shop, created, updated, soft_deleted)
        return {'created': created, 'updated': updated,
                'soft_deleted': soft_deleted}

    @api.model
    def _build_adapter(self, shop):
        """Factory hook — overridable by tests via mock.patch."""
        from ..services.etsy_api_client import EtsyApiClient
        from ..services.etsy_inventory_adapter import EtsyInventoryAdapter
        return EtsyInventoryAdapter(EtsyApiClient(shop))

    def _soft_delete_absent(self, listing, seen_product_ids):
        stale = self.search([
            ('listing_id', '=', listing.id),
            ('is_active', '=', True),
            ('etsy_product_id', 'not in',
             list(seen_product_ids) or [False]),
        ])
        if stale:
            stale.write({'is_active': False})
        return len(stale)

    def _match_variant(self, rec):
        """SKU → product.product link (ADR-013 §2 / Q-a / Q-c, R-L1/R-L6).

        - manual/existing FK is never overwritten (R-L6)
        - empty SKU → skip (leave NULL)
        - no match → leave NULL, NO auto-create (Q-a)
        - duplicate default_code → warn, link first-by-id deterministic
          (Q-c closest-match-only: every candidate has default_code==sku
          by domain, so first is the canonical pick)
        """
        if rec.product_id:
            return
        sku = (rec.sku or '').strip()
        if not sku:
            return
        candidates = self.env['product.product'].search(
            [('default_code', '=', sku)], order='id')
        if not candidates:
            return
        if len(candidates) > 1:
            _logger.warning(
                'SKU %s matches %d products; linking first (id=%s) '
                'for listing %s variant %s.',
                sku, len(candidates), candidates[0].id,
                rec.listing_id.etsy_listing_id, rec.etsy_product_id,
            )
        rec.product_id = candidates[0]

    @api.model
    def _variant_vals_from_raw(self, raw, listing):
        offering = (raw.get('offerings') or [{}])[0]
        return {
            'sku': raw.get('sku') or False,
            'property_values': json.dumps(raw.get('property_values') or []),
            'quantity': int(offering.get('quantity') or 0),
            'price': self._money_amount(offering.get('price')),
            'is_active': True,
            'last_synced_at': fields.Datetime.now(),
        }

    def _write_audit(self, shop, created, updated, soft_deleted):
        """One `etsy.api.log` row per shop variant sync. sudo(): log
        model is system-create-only; cron is already `__system__`."""
        # Path note: variants are fetched per-listing at
        # /listings/{listing_id}/inventory (no shop prefix); the audit
        # string mentions the shop_id for operator readability only.
        self.env['etsy.api.log'].sudo().create({
            'shop_id': shop.id,
            'endpoint':
                'GET /v3/application/listings/{listing_id}/inventory '
                '[shop %s]' % (shop.sudo().etsy_api_shop_id or shop.id),
            'source': 'listing_pull',
            'response_summary': (
                'variant_pull: created=%d updated=%d soft_deleted=%d'
                % (created, updated, soft_deleted)
            ),
        })

    @staticmethod
    def _money_amount(money) -> float:
        if not money:
            return 0.0
        return (money.get('amount') or 0) / (money.get('divisor') or 1)

    @staticmethod
    def _unix_to_datetime(ts):
        if not ts:
            return False
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(
            tzinfo=None)
