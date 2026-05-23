"""Operator-facing wizard for Spec 011 P-PUB-PUBLISH.

Wraps `EtsyListingPublisher.run()` (full create→images→inventory→publish
chain) and `push_inventory()` (inventory-only re-push). FR-017 method-top
gate on both actions before any side effect.
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import AccessError

from ..services.etsy_listing_publisher import EtsyListingPublisher

_logger = logging.getLogger(__name__)

_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'


class EtsyPublishWizard(models.TransientModel):
    _name = 'etsy.publish.wizard'
    _description = 'Etsy Publish Wizard'

    product_tmpl_id = fields.Many2one(
        'product.template', required=True, ondelete='cascade',
    )
    shop_id = fields.Many2one(
        'etsy.shop', required=True, ondelete='cascade',
    )

    def _check_ba_or_raise(self):
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_(
                "Only BA users can publish products to Etsy."
            ))

    def action_run_publish(self):
        self._check_ba_or_raise()  # FR-017 24th confirmation
        self.ensure_one()
        publisher = EtsyListingPublisher(self.env)
        publisher.run(self.product_tmpl_id, self.shop_id)
        return {'type': 'ir.actions.act_window_close'}

    def action_run_inventory_only(self):
        self._check_ba_or_raise()  # FR-017
        self.ensure_one()
        Channel = self.env.ref('multichannel_hub_core.channel_etsy')
        Status = self.env['product.channel.status'].sudo()
        status = Status.search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            ('channel_id', '=', Channel.id),
        ], limit=1)
        if not status or not status.external_ref:
            raise AccessError(_(
                "Cannot re-push inventory: product has no Etsy listing yet."
            ))
        publisher = EtsyListingPublisher(self.env)
        publisher.push_inventory(
            self.product_tmpl_id, status.external_ref, self.shop_id,
        )
        return {'type': 'ir.actions.act_window_close'}
