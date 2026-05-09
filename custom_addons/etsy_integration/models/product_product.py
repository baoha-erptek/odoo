from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    etsy_image_url = fields.Char(string='Etsy Image URL')
    is_etsy_product = fields.Boolean(
        string='Is Etsy Product', default=False, index=True)

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
