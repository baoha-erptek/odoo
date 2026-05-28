"""product.product extension — variant-level SKU auto-derivation.

Spec 009 P-HUB-SKU-AUTODERIVE: onchange on attribute assignment to fill
variant default_code with full SKU (family-material-size-variant pattern).
"""

import logging

from odoo import api, models

from ..services import sku_grammar_v2

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.onchange('product_template_attribute_value_ids')
    def _onchange_auto_fill_variant_code(self):
        """Auto-fill variant default_code from categ_id + attributes.

        Per P-HUB-SKU-AUTODERIVE, when variant attribute values are assigned,
        auto-populate default_code with the full SKU (e.g., MUG-CR-F11).

        Respects dirty-flag and legacy product status (ba_approved_legacy).
        """
        for rec in self:
            # Never auto-update legacy products
            if rec.product_tmpl_id.x_sku_v2_status == 'ba_approved_legacy':
                continue

            # Skip if template has no category
            if not rec.product_tmpl_id.categ_id:
                continue

            cat_family = rec.product_tmpl_id.categ_id._get_sku_family_chain()
            if not cat_family:
                continue

            # Build attribute_values dict from variant's attributes
            attr_values = {}
            for ptav in rec.product_template_attribute_value_ids:
                if ptav.attribute_id and ptav.product_attribute_value_id:
                    attr_val = ptav.product_attribute_value_id
                    attr_values[ptav.attribute_id.name] = attr_val.x_code or attr_val.name

            # Evaluate with variant attributes
            suggested = sku_grammar_v2.evaluate(
                name=rec.product_tmpl_id.name or '',
                env=self.env,
                categ_id=rec.product_tmpl_id.categ_id.id,
                attribute_values=attr_values if attr_values else None,
            )

            # Ensure suggested is a string
            if isinstance(suggested, tuple):
                suggested = suggested[0]

            # Auto-fill if blank or looks auto-generated
            if not rec.default_code:
                rec.default_code = suggested
            elif rec.product_tmpl_id.x_sku_v2_status in ('matches', 'non_canonical'):
                # If template code looks auto-suggested, update variant too
                if rec.default_code == rec.product_tmpl_id.default_code:
                    rec.default_code = suggested
