"""Hub extensions on product.template.

Adds: channel applicability M2M, channel-status O2M back-ref, Excel
bookkeeping fields, SKU drift trio (v2 grammar suggested + status +
legacy archive), and unit margin compute.

Existing `product_template_pipeline.py` covers pipeline-state extensions;
this file is the central product hub surface (Spec 009).

Spec 009 — P-HUB-PROD-MODEL. Data model: specs/009-product-hub/data-model.md §3-4.
"""

import logging

from odoo import api, fields, models

from ..services import sku_grammar_v2

_logger = logging.getLogger(__name__)


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
        digits='Product Price',
        default=0.0,
        help="Excel 'Price USD' bookkeeping — NOT the sale-order pricing source",
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

    @api.depends(
        'x_listing_price',
        'standard_price',
        'x_shipping_price_internal',
        'x_additional_cost',
    )
    def _compute_unit_margin(self):
        for rec in self:
            rec.x_unit_margin = (
                (rec.x_listing_price or 0.0)
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
            suggested, family_code = sku_grammar_v2.evaluate(rec.name or '')
            rec.x_sku_v2_suggested = suggested
            if family_code == 'MSC':
                rec.x_sku_v2_status = 'msc_catchall'
            elif suggested == (rec.default_code or ''):
                rec.x_sku_v2_status = 'matches'
            else:
                rec.x_sku_v2_status = 'non_canonical'
