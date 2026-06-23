from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # P-LIST-INV-PULL (ADR-013 §2): dual-index link to the Etsy variant
    # snapshot. Set by SKU discovery or operator override; ondelete
    # set null so deleting the snapshot never cascades to the product.
    etsy_listing_variant_id = fields.Many2one(
        'etsy.listing.product', string='Etsy Listing Variant',
        ondelete='set null', index=True,
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    etsy_image_url = fields.Char(string='Etsy Image URL')
    is_etsy_product = fields.Boolean(
        string='Is Etsy Product', default=False, index=True)
    etsy_needs_product_review = fields.Boolean(
        string='Needs Etsy Product Review',
        default=False,
        index=True,
        help='Set when Etsy order ingest had to auto-create this product.',
    )

    def _push_sku_to_channel(self, channel_code):
        """Spec 009 P-HUB-SKU-DRIFT checkpoint b — Etsy override.

        Routes through EtsyInventoryPusher to PUT the new SKU to the
        product's Etsy listing. The shop is derived from the listing row
        that backs the product.channel.status.external_ref.
        """
        if channel_code != 'etsy':
            return super()._push_sku_to_channel(channel_code)
        # Resolve listing → shop
        Channel = self.env.ref('multichannel_hub_core.channel_etsy')
        status = self.env['product.channel.status'].sudo().search([
            ('product_tmpl_id', '=', self.id),
            ('channel_id', '=', Channel.id),
        ], limit=1)
        if not status or not status.external_ref:
            return super()._push_sku_to_channel(channel_code)
        listing = self.env['etsy.listing'].sudo().search([
            ('etsy_listing_id', '=', status.external_ref),
        ], limit=1)
        if not listing:
            return super()._push_sku_to_channel(channel_code)
        from ..services.etsy_inventory_pusher import EtsyInventoryPusher
        EtsyInventoryPusher(self.env).push(self, listing.shop_id)
        return True

    def action_open_etsy_publish_wizard(self):
        """Spec 011 P-PUB-PUBLISH T027 — open the publish wizard for this product.

        The wizard itself carries the FR-017 method-top gate; this action is
        only a UI entry point. View binds `groups=` for defense-in-depth visibility.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Publish to Etsy',
            'res_model': 'etsy.publish.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_tmpl_id': self.id},
        }

    @api.model
    def _cron_download_etsy_images(self):
        """ir.cron entry point — delegates to the existing service class.

        Service lives at ``services.image_downloader.ImageDownloader`` and
        cannot be referenced directly by ir.cron.model_id (services aren't
        Odoo Models). This thin wrapper restores the missing schedule.

        Runs as ``base.user_root`` (set on the ir.cron record) so the
        ``image_1920`` writes inside ``cron_download_pending_images`` always
        have product.template write rights regardless of caller ACL.
        SSRF allowlist (i.etsystatic.com / img.etsystatic.com / www.etsy.com)
        is enforced inside ``download_and_store``.
        """
        from ..services.image_downloader import ImageDownloader
        ImageDownloader(self.env).cron_download_pending_images()
