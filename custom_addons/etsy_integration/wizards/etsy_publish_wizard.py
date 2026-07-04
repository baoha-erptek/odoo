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

    def action_run_publish_draft_only(self):
        # Smoke-test entrypoint for scripts/e2e_product_listing.py (P-PUB-E2E).
        # Runs create_draft + upload_images + push_inventory, then stops —
        # listing stays in Etsy 'draft' state (no listing fee, not buyer-visible).
        self._check_ba_or_raise()  # FR-017
        self.ensure_one()
        publisher = EtsyListingPublisher(self.env)
        publisher._check_shop_defaults(self.shop_id)
        draft = publisher.create_draft(self.product_tmpl_id, self.shop_id)
        listing_id = draft.get('listing_id')
        publisher.upload_images(self.product_tmpl_id, listing_id, self.shop_id)
        publisher.push_inventory(self.product_tmpl_id, listing_id, self.shop_id)
        # Video parity with upload_images: a draft preview should include the
        # listing's video too. Best-effort + non-fatal, mirroring run()
        # (etsy_listing_publisher.py). No-op when the resolved listing intent
        # carries no video_attachment_id. NOTE: push_personalization and
        # push_variation_images remain intentionally skipped on the draft-only
        # path (out of scope for P-LIST-VIDEO-DRAFT-PARITY).
        try:
            publisher.push_video(self.product_tmpl_id, listing_id, self.shop_id)
        except Exception as exc:  # noqa: BLE001 — non-fatal, mirrors run()
            _logger.warning(
                "Draft-only publish: push_video failed for listing %s: %s; "
                "continuing.", listing_id, exc,
            )
        # Cast listing_id to str: Etsy listing ids overflow XML-RPC int32 limit
        # (max 2,147,483,647). Callers parse back to int as needed.
        return {
            'type': 'ir.actions.act_window_close',
            'listing_id': str(listing_id) if listing_id else False,
        }

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
