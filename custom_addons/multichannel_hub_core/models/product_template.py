"""Hub extensions on product.template.

Adds: channel applicability M2M, channel-status O2M back-ref, Excel
bookkeeping fields, SKU drift trio (v2 grammar suggested + status +
legacy archive), and unit margin compute.

Existing `product_template_pipeline.py` covers pipeline-state extensions;
this file is the central product hub surface (Spec 009).

Spec 009 — P-HUB-PROD-MODEL. Data model: specs/009-product-hub/data-model.md §3-4.
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..services import sku_grammar_v2

_logger = logging.getLogger(__name__)


_ETSY_TAG_CHARSET_RE = re.compile(r"^[A-Za-z0-9 \-']+$")
_ETSY_TAG_MAX_COUNT = 13
_ETSY_TAG_MAX_LEN = 20


SKU_V2_STATUS_VALUES = [
    ('matches', 'Matches v2 canonical'),
    ('non_canonical', 'Non-canonical (drift)'),
    ('msc_catchall', 'Misc catch-all'),
    ('ba_approved_legacy', 'BA-approved legacy SKU'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_channel_applicability_ids = fields.Many2many(
        'multichannel.sales.channel',
        'product_template_channel_applicability_rel',
        'product_tmpl_id',
        'channel_id',
        string='Applicable Channels',
        domain=[('active', '=', True)],
        help="Channels the product may be published to",
    )
    x_sales_channel_status_ids = fields.One2many(
        'product.channel.status',
        'product_tmpl_id',
        string='Channel Statuses',
    )
    x_listing_price = fields.Float(
        compute='_compute_x_listing_price',
        help="Deprecated: maps to list_price. Use list_price directly.",
    )
    x_shipping_price_internal = fields.Float(
        digits='Product Price',
        default=0.0,
        help="Excel 'Shipping Fees' bookkeeping",
    )
    x_additional_cost = fields.Float(
        digits='Product Price',
        default=0.0,
        help="Excel 'Other costs' bookkeeping",
    )
    x_unit_margin = fields.Float(
        digits='Product Price',
        compute='_compute_unit_margin',
        store=True,
        help="x_listing_price - standard_price - x_shipping_price_internal - x_additional_cost",
    )
    x_sku_v2_suggested = fields.Char(
        compute='_compute_x_sku_v2',
        store=True,
        index=True,
        help="Grammar v2 family code derived from name",
    )
    x_sku_v2_status = fields.Selection(
        SKU_V2_STATUS_VALUES,
        compute='_compute_x_sku_v2',
        store=True,
        readonly=False,
        index=True,
        help="Drift status; ba_approved_legacy is operator-pinned and never auto-overwritten",
    )
    x_sku_legacy = fields.Char(
        help="Archive of prior default_code after canonicalisation wizard run",
    )
    x_published_channel_count = fields.Integer(
        compute='_compute_x_published_channel_count',
        store=True,
        help="Number of channels where this product is currently published",
    )

    @api.depends('x_sales_channel_status_ids.state')
    def _compute_x_published_channel_count(self):
        for rec in self:
            rec.x_published_channel_count = sum(
                1 for s in rec.x_sales_channel_status_ids
                if s.state == 'published'
            )

    # ------------------------------------------------------------------
    # Extension point for per-channel SKU push (P-HUB-SKU-DRIFT mhc-half).
    # ------------------------------------------------------------------
    # Default no-op; etsy_integration overrides this to call the Etsy
    # publisher when channel_code == 'etsy' (lands with Spec 011 P-PUB-CLIENT).
    def action_open_channel_statuses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Channel Statuses',
            'res_model': 'product.channel.status',
            'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'target': 'current',
        }

    def _push_sku_to_channel(self, channel_code):
        """Push current `default_code` to the named channel.

        Default implementation is a no-op (returns True). Channel modules
        override per-channel as needed. Callers must wrap in a savepoint
        or accept full-transaction rollback on raise.
        """
        return True

    @api.depends('list_price')
    def _compute_x_listing_price(self):
        """Backward compatibility shim: x_listing_price now maps to list_price."""
        for rec in self:
            rec.x_listing_price = rec.list_price or 0.0

    @api.depends(
        'list_price',
        'standard_price',
        'x_shipping_price_internal',
        'x_additional_cost',
    )
    def _compute_unit_margin(self):
        for rec in self:
            rec.x_unit_margin = (
                (rec.list_price or 0.0)
                - (rec.standard_price or 0.0)
                - (rec.x_shipping_price_internal or 0.0)
                - (rec.x_additional_cost or 0.0)
            )

    @api.depends('name', 'default_code')
    def _compute_x_sku_v2(self):
        """Evaluate grammar v2 regex from frozen family rules.

        Status semantics (data-model.md §4):
          - matches: suggested == default_code AND family != MSC
          - non_canonical: suggested != default_code AND family != MSC
          - msc_catchall: family == MSC
          - ba_approved_legacy: operator-pinned by canonicalisation wizard;
            this compute does NOT overwrite that status.
        """
        for rec in self:
            if rec.x_sku_v2_status == 'ba_approved_legacy':
                continue  # operator-pinned; never auto-overwrite
            suggested, family_code = sku_grammar_v2.evaluate(rec.name or '', self.env)
            rec.x_sku_v2_suggested = suggested
            if family_code == 'MSC':
                rec.x_sku_v2_status = 'msc_catchall'
            elif suggested == (rec.default_code or ''):
                rec.x_sku_v2_status = 'matches'
            else:
                rec.x_sku_v2_status = 'non_canonical'

    @api.onchange('categ_id', 'attribute_line_ids')
    def _onchange_auto_fill_default_code(self):
        """Auto-derive default_code from categ_id + attribute_line_ids.

        Per P-HUB-SKU-AUTODERIVE (Spec 009):
        - If default_code is blank, populate via SKU grammar.
        - If default_code matches prior auto-suggestion (looks auto-generated),
          update to new suggestion when categ_id changes.
        - If default_code was manually edited (dirty-flag), preserve it.
        - Never auto-update legacy products (x_sku_v2_status='ba_approved_legacy').
        """
        for rec in self:
            # Never auto-update legacy products
            if rec.x_sku_v2_status == 'ba_approved_legacy':
                continue

            # Skip if category has no family (no suggestion available)
            if not rec.categ_id:
                continue

            cat_family = rec.categ_id._get_sku_family_chain()
            if not cat_family:
                continue

            # Build attribute_values dict from attribute_line_ids
            attr_values = {}
            for attr_line in rec.attribute_line_ids:
                if attr_line.attribute_id and attr_line.value_ids:
                    # For onchange, just take the first value (variants are created later)
                    first_value = attr_line.value_ids[0]
                    attr_values[attr_line.attribute_id.name] = first_value.x_code or first_value.name

            # Evaluate: categ_id + attributes → full SKU
            suggested = sku_grammar_v2.evaluate(
                name=rec.name or '',
                env=self.env,
                categ_id=rec.categ_id.id,
                attribute_values=attr_values if attr_values else None,
            )

            # Ensure suggested is a string (not tuple)
            if isinstance(suggested, tuple):
                suggested = suggested[0]

            # Auto-fill decision:
            # 1. If default_code is blank, populate
            # 2. If it matches the old suggestion (auto-generated), update
            # 3. If it's different (manual edit), preserve it
            if not rec.default_code:
                # Blank: always populate
                rec.default_code = suggested
            elif rec.x_sku_v2_status in ('matches', 'non_canonical'):
                # Was auto-suggested before; if user hasn't manually edited,
                # we can safely update to the new suggestion.
                # (In a full implementation, we'd track the prior suggested value,
                # but for onchange simplicity: update if the code starts with the old family code
                # and is changing families. For now: update unconditionally if it was suggested.)
                if rec.x_sku_v2_suggested and rec.default_code == rec.x_sku_v2_suggested:
                    rec.default_code = suggested

    @api.model_create_multi
    def create(self, vals_list):
        """Override to auto-fill default_code last-chance.

        After super().create(), if default_code is still blank and categ_id
        is set, populate via SKU grammar (Spec 009).
        """
        records = super().create(vals_list)

        for rec in records:
            # Skip if default_code is already set
            if rec.default_code:
                continue

            # Skip if legacy status
            if rec.x_sku_v2_status == 'ba_approved_legacy':
                continue

            # Skip if no category
            if not rec.categ_id:
                continue

            cat_family = rec.categ_id._get_sku_family_chain()
            if not cat_family:
                continue

            # Auto-fill from category
            suggested = sku_grammar_v2.evaluate(
                name=rec.name or '',
                env=self.env,
                categ_id=rec.categ_id.id,
                attribute_values=None,  # No variant attributes at create time
            )

            if isinstance(suggested, tuple):
                suggested = suggested[0]

            rec.default_code = suggested

        return records

    @api.constrains('product_tag_ids')
    def _check_etsy_tag_rules(self):
        """Enforce Etsy listing-tag rules on standard product.tag M2M.

        Rules: <=13 tags total, each tag <=20 chars, charset is
        [A-Za-z0-9 -'] only. Fires on create and write.
        """
        for rec in self:
            tag_names = rec.product_tag_ids.mapped('name')
            if len(tag_names) > _ETSY_TAG_MAX_COUNT:
                raise ValidationError(_(
                    "A product may carry at most %(max)d tags (got %(count)d).",
                ) % {'max': _ETSY_TAG_MAX_COUNT, 'count': len(tag_names)})
            for name in tag_names:
                if len(name) > _ETSY_TAG_MAX_LEN:
                    raise ValidationError(_(
                        "Tag %(tag)r exceeds %(max)d characters.",
                    ) % {'tag': name, 'max': _ETSY_TAG_MAX_LEN})
                if not _ETSY_TAG_CHARSET_RE.match(name):
                    raise ValidationError(_(
                        "Tag %(tag)r has invalid characters; allowed: "
                        "letters, digits, spaces, hyphens, apostrophes.",
                    ) % {'tag': name})
