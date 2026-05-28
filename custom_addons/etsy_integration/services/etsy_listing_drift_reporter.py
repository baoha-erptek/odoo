"""EtsyListingDriftReporter — Etsy↔Odoo catalog drift (Spec 008 US4).

Stateless service (build with `EtsyListingDriftReporter(env)`); read-only
indexed ORM queries. Three drift categories per ADR-013 / spec.md US4:
- unlinked  : active variant with no `product_id`
- qty_drift : linked variant whose Etsy qty != Odoo qty
- orphan    : Odoo product whose SKU has no active Etsy variant
"""

import logging

_logger = logging.getLogger(__name__)


class EtsyListingDriftReporter:

    def __init__(self, env):
        self._env = env

    def _shop_variants(self, shop):
        return self._env['etsy.listing.product'].search([
            ('listing_id.shop_id', '=', shop.id),
            ('is_active', '=', True),
        ])

    def get_unlinked_variants(self, shop) -> list:
        """Active variants with no Odoo product linked."""
        return [
            {'variant_id': v.id, 'sku': v.sku,
             'listing_id': v.listing_id.etsy_listing_id,
             'drift_type': 'unlinked'}
            for v in self._shop_variants(shop) if not v.product_id
        ]

    def get_qty_drifts(self, shop, threshold=0) -> list:
        """Linked variants whose |Etsy qty - Odoo qty| > threshold."""
        out = []
        for v in self._shop_variants(shop):
            if v.product_id and abs(v.qty_drift) > threshold:
                out.append({
                    'variant_id': v.id, 'sku': v.sku,
                    'etsy_qty': v.quantity, 'odoo_qty': v.odoo_qty,
                    'qty_drift': v.qty_drift, 'drift_type': 'qty_drift'})
        return out

    def get_orphan_products(self, shop) -> list:
        """Odoo products whose default_code matches no active Etsy
        variant for this shop (potential un-listed products).

        NOTE: scans all coded products in memory — fine within the
        ADR-013 ~5k-variant retention bound; promote to a single
        LEFT JOIN if a large multi-catalog deployment appears
        (deferred per plan.md R-L2)."""
        linked_skus = {
            v.sku for v in self._shop_variants(shop) if v.sku
        }
        orphans = []
        products = self._env['product.product'].search(
            [('default_code', '!=', False)])
        for p in products:
            if p.default_code not in linked_skus:
                orphans.append({
                    'product_id': p.id, 'sku': p.default_code,
                    'drift_type': 'orphan_product'})
        return orphans
