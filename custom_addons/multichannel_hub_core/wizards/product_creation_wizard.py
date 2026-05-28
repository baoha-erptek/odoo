"""BA-gated product creation wizard.

Spec 009 US3 / P-HUB-WIZARD. Validates name + SKU + category + prices +
at least one channel before creating `product.template` and the matching
`product.channel.status` rows.

FR-017 21st confirmation: method-top group gate before any side effect.
ADR-010 reuse: production mode preview reads `x_gearment_sku` to surface
the inferred dropship vs MTO route.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import sku_grammar_v2

_logger = logging.getLogger(__name__)


_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'


class ProductCreationWizard(models.TransientModel):
    _name = 'product.creation.wizard'
    _description = 'Product Creation Wizard (BA-gated)'

    name = fields.Char(required=True)
    default_code = fields.Char(string='Internal Reference (SKU)', required=True)
    categ_id = fields.Many2one(
        'product.category',
        string='Category',
        required=True,
        ondelete='restrict',
    )
    x_listing_price = fields.Float(
        string='Listing Price (USD)',
        digits='Product Price',
        default=0.0,
    )
    x_shipping_price_internal = fields.Float(
        string='Shipping Fees',
        digits='Product Price',
        default=0.0,
    )
    x_additional_cost = fields.Float(
        string='Other Costs',
        digits='Product Price',
        default=0.0,
    )
    standard_price = fields.Float(
        string='Cost (Standard Price)',
        digits='Product Price',
        default=0.0,
    )
    x_gearment_sku = fields.Char(
        string='Gearment SKU',
        help="If set, the new product auto-applies the Dropship route (ADR-010).",
    )
    x_channel_applicability_ids = fields.Many2many(
        'multichannel.sales.channel',
        'product_creation_wizard_channel_rel',
        'wizard_id',
        'channel_id',
        string='Channels',
        domain=[('active', '=', True)],
    )

    # ---- previews (non-stored, surfaced in form view)
    sku_v2_suggested_preview = fields.Char(
        string='SKU Grammar v2 — Suggested',
        compute='_compute_sku_v2_preview',
    )
    sku_v2_status_preview = fields.Char(
        string='SKU Grammar v2 — Status',
        compute='_compute_sku_v2_preview',
    )
    production_mode_preview = fields.Char(
        string='Production Mode (inferred)',
        compute='_compute_production_mode_preview',
    )

    @api.depends('name', 'default_code')
    def _compute_sku_v2_preview(self):
        for rec in self:
            suggested, family_code = sku_grammar_v2.evaluate(rec.name or '', self.env)
            rec.sku_v2_suggested_preview = suggested
            if family_code == 'MSC':
                rec.sku_v2_status_preview = 'msc_catchall'
            elif suggested == (rec.default_code or ''):
                rec.sku_v2_status_preview = 'matches'
            else:
                rec.sku_v2_status_preview = 'non_canonical'

    @api.depends('x_gearment_sku')
    def _compute_production_mode_preview(self):
        for rec in self:
            rec.production_mode_preview = (
                _('Dropship via Gearment') if rec.x_gearment_sku
                else _('In-house (MTO)')
            )

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def _check_ba_or_raise(self):
        """FR-017 method-top gate. Must fire BEFORE any side effect.

        Memory `feedback_fr017_write_defense_in_depth` (21st confirmation).
        """
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_(
                "Only BA users can create products via this wizard."
            ))

    def _validate(self):
        """Validate wizard inputs.

        Runs the v2.1 grammar check on ``default_code`` BEFORE existing field
        checks. Soft mode logs a WARNING and signals the caller (via the
        returned flag) to auto-mark the new template ``x_sku_v2_status``
        as ``ba_approved_legacy``; hard mode raises UserError before any
        side effect (FR-017 defense-in-depth pattern, 25th confirmation).

        Returns:
            bool: True iff at least one record failed v2.1 validation in
            soft mode (caller should set ``x_sku_v2_status='ba_approved_legacy'``
            on the created template).
        """
        soft_warn = False
        for rec in self:
            if not sku_grammar_v2.validate_v2_sku(rec.default_code or ''):
                mode = self.env['ir.config_parameter'].sudo().get_param(
                    sku_grammar_v2.ICP_ENFORCE_MODE_KEY, 'soft',
                )
                if mode == 'hard':
                    raise UserError(_(
                        "SKU does not match v2.1 grammar "
                        "(<FAM3>-<MAT2>-<SIZE>[-<VAR2>], 8-14 chars). "
                        "See SKU_GRAMMAR.md §7.1."
                    ))
                _logger.warning(
                    "v2.1 grammar soft-warn: default_code=%r does not match; "
                    "auto-marking new template as ba_approved_legacy.",
                    rec.default_code or '',
                )
                soft_warn = True
            if not (rec.name or '').strip():
                raise UserError(_("Product name is required."))
            if not (rec.default_code or '').strip():
                raise UserError(_("Internal Reference (SKU) is required."))
            if not rec.categ_id:
                raise UserError(_("Category is required."))
            if rec.x_listing_price <= 0:
                raise UserError(_("Listing Price must be greater than 0."))
            if rec.x_shipping_price_internal < 0:
                raise UserError(_("Shipping Fees cannot be negative."))
            if not rec.x_channel_applicability_ids:
                raise UserError(_("Select at least one channel."))
        return soft_warn

    def action_create(self):
        self._check_ba_or_raise()  # FR-017 — before any write
        soft_warn = self._validate()
        # sudo() is intentional and bounded: the FR-017 gate above proved BA
        # membership; BA group does not include the platform-level
        # `product.group_product_manager`, but ADR-014 §6 says product creation
        # via this wizard is part of the BA tier's responsibility. The write
        # surface is exactly what the validated wizard collected — no smuggling.
        Template = self.env['product.template'].sudo()
        Status = self.env['product.channel.status'].sudo()
        self.ensure_one()
        # Bypass active_test so inactive channels selected via direct write
        # (e.g. test contexts) still land in the M2M; the form picker's domain
        # is the operator-side guard and remains effective.
        channel_ids = self.with_context(active_test=False).x_channel_applicability_ids.ids
        tmpl_vals = {
            'name': self.name,
            'default_code': self.default_code,
            'categ_id': self.categ_id.id,
            'list_price': self.x_listing_price,
            'x_shipping_price_internal': self.x_shipping_price_internal,
            'x_additional_cost': self.x_additional_cost,
            'standard_price': self.standard_price,
            'x_gearment_sku': self.x_gearment_sku or False,
            'x_channel_applicability_ids': [(6, 0, channel_ids)],
        }
        if soft_warn:
            # v2.1 soft mode: pin the template so the compute bypass at
            # product_template._compute_x_sku_v2 line 151 leaves it alone.
            tmpl_vals['x_sku_v2_status'] = 'ba_approved_legacy'
        tmpl = Template.create(tmpl_vals)
        Status.create([
            {'product_tmpl_id': tmpl.id, 'channel_id': ch_id, 'state': 'draft'}
            for ch_id in channel_ids
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product Created'),
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': tmpl.id,
            'target': 'current',
        }
