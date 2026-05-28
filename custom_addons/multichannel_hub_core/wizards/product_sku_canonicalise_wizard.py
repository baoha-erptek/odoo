"""SKU drift canonicalisation wizard (per-product).

Spec 009 US4 / P-HUB-SKU-DRIFT — mhc-half (checkpoint a). Operator chooses
**Keep legacy** (pins `x_sku_v2_status='ba_approved_legacy'`) or **Accept
canonical** (moves `default_code` → `x_sku_legacy`, writes v2 suggested →
`default_code`, then fires `_push_sku_to_channel` for each applicable
channel; rolls back on failure).

The Etsy implementation of `_push_sku_to_channel` lands in checkpoint (b)
after Spec 011 P-PUB-CLIENT — at this checkpoint the hook is a no-op
defined on `product.template` and tests use `mock.patch.object` to inject
behaviour.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'


class ProductSkuCanonicaliseWizard(models.TransientModel):
    _name = 'product.sku.canonicalise.wizard'
    _description = 'SKU Canonicalisation Wizard'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
    )
    current_default_code = fields.Char(
        related='product_tmpl_id.default_code',
        readonly=True,
        string='Current SKU',
    )
    suggested_default_code = fields.Char(
        related='product_tmpl_id.x_sku_v2_suggested',
        readonly=True,
        string='Suggested SKU (v2)',
    )
    current_status = fields.Selection(
        related='product_tmpl_id.x_sku_v2_status',
        readonly=True,
        string='Current Status',
    )

    def _check_ba_or_raise(self):
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_(
                "Only BA users can canonicalise SKUs."
            ))

    # ------------------------------------------------------------------

    def action_keep_legacy(self):
        self._check_ba_or_raise()  # FR-017
        for rec in self:
            rec.product_tmpl_id.sudo().write({
                'x_sku_v2_status': 'ba_approved_legacy',
            })
        return {'type': 'ir.actions.act_window_close'}

    def action_accept_canonical(self):
        self._check_ba_or_raise()  # FR-017
        for rec in self:
            tmpl = rec.product_tmpl_id
            new_code = tmpl.x_sku_v2_suggested or ''
            if not new_code:
                # Nothing to do; defensive.
                continue
            old_code = tmpl.default_code or ''
            # Swap before push so push sees the new SKU.
            tmpl.sudo().write({
                'default_code': new_code,
                'x_sku_legacy': old_code,
            })
            # Fire push hook per applicable channel. Any failure propagates
            # and rolls back the transaction.
            channels = tmpl.with_context(active_test=False).x_channel_applicability_ids
            for channel in channels:
                tmpl.sudo()._push_sku_to_channel(channel.code)
        return {'type': 'ir.actions.act_window_close'}
