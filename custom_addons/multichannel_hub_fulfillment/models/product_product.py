"""product.product extension — per-variant Gearment mapping (FLW-01).

Gearment's `variant_id` encodes color+size, so a multi-variant template
cannot be keyed by the template-level ``x_gearment_sku`` alone. The GM
variant_id for a specific variant lives in the standard
``product.supplierinfo.product_code`` on the Gearment vendor's pricelist
row pinned to that variant (``product_id`` set) — no custom field needed
(Standard-Odoo-First). ``x_gearment_sku`` stays the route/vendor marker
(P1-DROP-SEED) and the fallback for single-variant products.
"""
from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _gearment_variant_code(self):
        """GM variant_id pinned to THIS variant via the Gearment vendor's
        supplierinfo row, or '' when no variant-specific row exists."""
        self.ensure_one()
        partner = self.product_tmpl_id._get_gearment_partner()
        if not partner:
            return ''
        rows = self.product_tmpl_id.seller_ids.filtered(
            lambda s: s.partner_id == partner
            and s.product_id == self
            and (s.product_code or '').strip()
        )
        return rows[0].product_code.strip() if rows else ''

    def _gearment_resolved_sku(self):
        """Variant-specific GM id first, template ``x_gearment_sku`` fallback."""
        self.ensure_one()
        return (
            self._gearment_variant_code()
            or (self.product_tmpl_id.x_gearment_sku or '').strip()
        )
