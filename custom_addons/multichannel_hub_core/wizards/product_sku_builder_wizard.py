"""4-step BA-facing SKU builder wizard (Spec 009 §2.5 P-HUB-SKU-BUILDER T045).

Composes a v2.1 SKU `<FAM3>-<MAT2>-<SIZE>[-<VAR2>]` from operator picks
and creates a `product.template` with the resulting `default_code`.

Coexists with `product.creation.wizard` for one sprint per D-V2-3 (the
legacy wizard handles the "free-form SKU + full pricing" path; this
wizard handles the "guided assembly from taxonomy" path). FR-017 24th
confirmation: method-top group gate before any side effect.
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import sku_grammar_v2

_logger = logging.getLogger(__name__)


_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'
_RECT_PATTERN = re.compile(r'^[1-9]\d{0,2}$')  # 1-999 inches

# Per SKU_GRAMMAR.md §4 family-gated rules. Maps family code → set of
# allowed size namespaces. Families not listed allow the dish-family
# defaults (shape + dim).
_FAMILY_NAMESPACE_MAP = {
    'MUG': {'fluid_oz'},
    'TUM': {'fluid_oz'},
    'APP': {'apparel'},
    'APR': {'apparel'},
    'DMT': {'rect'},
    'RUG': {'rect'},
}
_DEFAULT_NAMESPACES = {'shape', 'dim', 'rect'}


class ProductSkuBuilderWizard(models.TransientModel):
    _name = 'product.sku.builder.wizard'
    _description = 'SKU Builder Wizard (4-step, BA-gated)'

    step = fields.Selection(
        [
            ('1', '1. Family'),
            ('2', '2. Material'),
            ('3', '3. Size'),
            ('4', '4. Preview & Create'),
        ],
        default='1',
        required=True,
    )

    # --- Step 1
    product_name = fields.Char(
        required=True,
        help="Product display name. Drives auto-family-classification.",
    )
    family_id_auto = fields.Many2one(
        'mhc.sku.family',
        compute='_compute_family_id_auto',
        store=False,
        help="Auto-classified family suggestion from product_name. "
             "BA can override via family_id (D-V2-4).",
    )
    family_id = fields.Many2one(
        'mhc.sku.family',
        string='Family',
        domain=[('active', '=', True)],
        help="22-family dropdown (D-V2-4). Defaults to family_id_auto on open; "
             "BA can pick a different family.",
    )

    # --- Step 2
    material_id = fields.Many2one(
        'product.attribute.value',
        string='Material',
        domain="[('attribute_id.name', '=', 'Material')]",
    )

    # --- Step 3
    size_id = fields.Many2one(
        'product.attribute.value',
        string='Size',
        help="Family-gated. For rectangular doormats use rect_w/rect_h instead.",
    )
    rect_w = fields.Integer(
        string='Width (inches)',
        default=0,
        help="Rectangular size width. Used when family route requires R-codes "
             "(e.g. doormat). Leave 0 if using size_id.",
    )
    rect_h = fields.Integer(
        string='Height (inches)',
        default=0,
        help="Rectangular size height. See rect_w.",
    )

    # --- Step 4
    var2_color_id = fields.Many2one(
        'product.attribute.value',
        string='Color (optional)',
        domain="[('attribute_id.name', '=', 'Color')]",
    )
    preview_sku = fields.Char(
        compute='_compute_preview_sku',
        store=False,
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('product_name')
    def _compute_family_id_auto(self):
        Family = self.env['mhc.sku.family']
        for rec in self:
            _suggested, code = sku_grammar_v2.evaluate(rec.product_name or '', self.env)
            rec.family_id_auto = Family.search([('code', '=', code)], limit=1)

    @api.depends('family_id', 'material_id', 'size_id', 'rect_w', 'rect_h', 'var2_color_id')
    def _compute_preview_sku(self):
        for rec in self:
            rec.preview_sku = rec._build_sku_or_blank()

    @api.onchange('product_name')
    def _onchange_product_name_default_family(self):
        for rec in self:
            if not rec.family_id and rec.family_id_auto:
                rec.family_id = rec.family_id_auto

    @api.onchange('family_id')
    def _onchange_family_default_material(self):
        for rec in self:
            if rec.family_id and not rec.material_id and rec.family_id.default_material_id:
                rec.material_id = rec.family_id.default_material_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_sku_or_blank(self) -> str:
        """Return assembled SKU when fields are sufficient, else empty string."""
        self.ensure_one()
        if not (self.family_id and self.material_id):
            return ''
        fam = self.family_id.code or ''
        mat = self.material_id.x_code or ''
        size = self._size_segment_or_blank()
        if not size:
            return ''
        parts = [fam, mat, size]
        if self.var2_color_id and self.var2_color_id.x_code:
            parts.append(self.var2_color_id.x_code)
        return '-'.join(parts)

    def _size_segment_or_blank(self) -> str:
        """Resolve the SIZE segment from size_id or rect_w/rect_h."""
        self.ensure_one()
        if self.size_id and self.size_id.x_code:
            return self.size_id.x_code
        if self.rect_w > 0 and self.rect_h > 0:
            if not (_RECT_PATTERN.match(str(self.rect_w)) and _RECT_PATTERN.match(str(self.rect_h))):
                return ''
            return 'R%dX%d' % (self.rect_w, self.rect_h)
        return ''

    def _check_size_namespace_matches_family(self):
        """Family-gated size validation per SKU_GRAMMAR §4.

        Two layers of guard:
        1. Explicit `x_applicable_family_ids` on the size value (e.g. F11
           is only applicable to MUG and TUM). If non-empty, the chosen
           family must be in the set.
        2. Family-to-namespace map. MUG/TUM expect `fluid_oz`; APP/APR
           expect `apparel`; DMT/RUG expect `rect`; other families allow
           the default {shape, dim, rect} set.

        Empty `x_applicable_family_ids` is "applies to all" UNLESS the
        size carries a namespace AND the family has a restricted namespace
        set that excludes it.
        """
        self.ensure_one()
        if not self.size_id or not self.family_id:
            return
        # Layer 1: explicit per-value family allowlist
        allowed = self.size_id.x_applicable_family_ids
        if allowed and self.family_id not in allowed:
            raise UserError(_(
                "Size '%(size)s' is not valid for family '%(family)s'. "
                "Pick a size from a compatible namespace.",
                size=self.size_id.name,
                family=self.family_id.code,
            ))
        # Layer 2: namespace ↔ family map (SKU_GRAMMAR §4)
        if self.size_id.x_namespace:
            allowed_ns = _FAMILY_NAMESPACE_MAP.get(
                self.family_id.code,
                _DEFAULT_NAMESPACES,
            )
            if self.size_id.x_namespace not in allowed_ns:
                raise UserError(_(
                    "Size '%(size)s' uses namespace '%(ns)s', which is "
                    "not valid for family '%(family)s'. Allowed: %(ok)s.",
                    size=self.size_id.name,
                    ns=self.size_id.x_namespace,
                    family=self.family_id.code,
                    ok=', '.join(sorted(allowed_ns)),
                ))

    # ------------------------------------------------------------------
    # Gate + validation + action
    # ------------------------------------------------------------------

    def _check_ba_or_raise(self):
        """FR-017 method-top gate (24th confirmation).

        Must fire BEFORE any side effect. Memory
        `feedback_fr017_write_defense_in_depth` (22 prior confirmations).
        """
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_(
                "Only BA users can create products via this wizard."
            ))

    def _validate(self):
        for rec in self:
            if not (rec.product_name or '').strip():
                raise UserError(_("Product name is required."))
            if not rec.family_id:
                raise UserError(_("Pick a family in step 1."))
            if not rec.material_id:
                raise UserError(_("Pick a material in step 2."))
            size = rec._size_segment_or_blank()
            if not size:
                raise UserError(_(
                    "Pick a size (or rectangular dimensions) in step 3."
                ))
            rec._check_size_namespace_matches_family()

    def action_next(self):
        self.ensure_one()
        order = ['1', '2', '3', '4']
        idx = order.index(self.step)
        if idx < len(order) - 1:
            self.step = order[idx + 1]
        return {'type': 'ir.actions.act_window', 'res_id': self.id,
                'res_model': self._name, 'view_mode': 'form', 'target': 'new',
                'context': self.env.context}

    def action_prev(self):
        self.ensure_one()
        order = ['1', '2', '3', '4']
        idx = order.index(self.step)
        if idx > 0:
            self.step = order[idx - 1]
        return {'type': 'ir.actions.act_window', 'res_id': self.id,
                'res_model': self._name, 'view_mode': 'form', 'target': 'new',
                'context': self.env.context}

    def action_create(self):
        # FR-017 24th — must fire BEFORE any side effect / write / search.
        self._check_ba_or_raise()
        self._validate()
        self.ensure_one()
        sku = self._build_sku_or_blank()
        if not sku:
            raise UserError(_("SKU assembly failed — check all required steps."))
        # sudo() is intentional and bounded: the FR-017 gate above proved BA
        # membership; BA group does not include product.group_product_manager
        # but ADR-014 §6 grants BA the product-creation responsibility. The
        # write surface is exactly the assembled SKU + name — no smuggling.
        Template = self.env['product.template'].sudo()
        tmpl = Template.create({
            'name': self.product_name,
            'default_code': sku,
        })
        _logger.debug(
            "SKU builder wizard created product.template id=%s default_code=%s",
            tmpl.id, sku,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product Created'),
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': tmpl.id,
            'target': 'current',
        }
