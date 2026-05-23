"""Standalone entry point for inventory-only push (Spec 011 T019).

Thin alias around `EtsyListingPublisher.push_inventory` for callers that
have only a `product.template` + `etsy.shop` and need to resolve the
listing_id from `product.channel.status.external_ref`.

Primary user: Spec 009 P-HUB-SKU-DRIFT checkpoint b — the canonicalisation
wizard's `_push_sku_to_channel` override needs to push the new SKU to Etsy
without knowing the listing_id directly.
"""

from .etsy_listing_publisher import EtsyListingPublisher


class EtsyInventoryPusher:

    def __init__(self, env):
        self.env = env

    def push(self, tmpl, shop):
        """Resolve listing_id from product.channel.status and push inventory.

        Raises ValueError if no status row exists for (tmpl, etsy channel)
        or if external_ref is empty.
        """
        channel = self.env.ref('multichannel_hub_core.channel_etsy')
        status = self.env['product.channel.status'].sudo().search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', channel.id),
        ], limit=1)
        if not status or not status.external_ref:
            raise ValueError(
                "No Etsy listing_id found for product %r on shop %r — "
                "publish first via P-PUB-DRAFT." % (tmpl.name, shop.name)
            )
        publisher = EtsyListingPublisher(self.env)
        return publisher.push_inventory(tmpl, status.external_ref, shop)
