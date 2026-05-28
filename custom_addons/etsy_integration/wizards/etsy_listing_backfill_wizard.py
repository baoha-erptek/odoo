"""Backfill existing Etsy listings into the multichannel hub.

Spec 009 US6 / P-HUB-BACKFILL. Read-only against Etsy (no outbound calls).
For each `etsy.listing.product` with a matched `product_id`, ensure the
parent `product.template` has `x_channel_applicability_ids` containing
the etsy channel and a `product.channel.status` row for (template, etsy).

Idempotent — second run is a no-op on existing rows. Unmatched variants
(product_id NULL) are surfaced via `unmatched_count` for operator
follow-up; this slice does NOT auto-create products for unmatched SKUs
(owner directive 2026-05-23: backfill, not replace).

ADR-014 §6: backfill wizard lives in etsy_integration (Etsy-specific
data path); the channel-agnostic surfaces it writes (product.template,
product.channel.status) live in multichannel_hub_core.
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'
_ETSY_CHANNEL_XMLID = 'multichannel_hub_core.channel_etsy'


class EtsyListingBackfillWizard(models.TransientModel):
    _name = 'etsy.listing.backfill.wizard'
    _description = 'Etsy Listing → Product Hub Backfill Wizard'

    shop_id = fields.Many2one(
        'etsy.shop',
        string='Etsy Shop',
        required=True,
        ondelete='cascade',
    )
    matched_count = fields.Integer(readonly=True)
    unmatched_count = fields.Integer(readonly=True)
    unmatched_skus = fields.Text(readonly=True)

    def _check_ba_or_raise(self):
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_("Only BA users can run the backfill wizard."))

    def action_backfill(self):
        self._check_ba_or_raise()
        self.ensure_one()
        channel = self.env.ref(_ETSY_CHANNEL_XMLID)
        if not channel:
            raise UserError(_("Etsy channel reference is missing."))
        Listing = self.env['etsy.listing']
        ListingProduct = self.env['etsy.listing.product']
        # sudo() bounded: FR-017 gate above proves BA membership; BA group does
        # not include product.channel.status write rights (group_system-write
        # per data-model.md §2). We write only (template, channel) tuples
        # derived from already-matched local data — no smuggling.
        Status = self.env['product.channel.status'].sudo()
        matched = 0
        unmatched_skus = []
        listings = Listing.search([
            ('shop_id', '=', self.shop_id.id),
            ('state', '=', 'active'),
        ])
        seen_templates = set()
        for listing in listings:
            variants = ListingProduct.search([('listing_id', '=', listing.id)])
            for variant in variants:
                if not variant.product_id:
                    unmatched_skus.append(variant.sku or '(no sku)')
                    continue
                tmpl = variant.product_id.product_tmpl_id
                if tmpl.id not in seen_templates:
                    seen_templates.add(tmpl.id)
                    # Add etsy channel to applicability if missing — idempotent.
                    # sudo() bounded: BA may lack product.template write; we
                    # add a single channel id, never clear/replace existing.
                    if channel not in tmpl.x_channel_applicability_ids:
                        tmpl.sudo().x_channel_applicability_ids = [(4, channel.id)]
                    # Ensure status row exists — idempotent
                    existing = Status.search([
                        ('product_tmpl_id', '=', tmpl.id),
                        ('channel_id', '=', channel.id),
                    ], limit=1)
                    if not existing:
                        Status.create({
                            'product_tmpl_id': tmpl.id,
                            'channel_id': channel.id,
                            'state': 'published',
                            'external_ref': listing.etsy_listing_id,
                        })
                    elif not existing.external_ref:
                        existing.write({'external_ref': listing.etsy_listing_id})
                    matched += 1
        self.write({
            'matched_count': matched,
            'unmatched_count': len(unmatched_skus),
            'unmatched_skus': '\n'.join(unmatched_skus),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Backfill Result'),
        }
