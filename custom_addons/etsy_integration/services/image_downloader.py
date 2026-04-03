"""Download Etsy product images and store them in Odoo product records.

Images are fetched from etsystatic.com URLs, base64-encoded, and written
to the product.template ``image_1920`` field.
"""
import base64
import logging
import time

import requests

_logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 20
_DELAY_BETWEEN_DOWNLOADS = 1  # seconds


class ImageDownloader:
    """Service for downloading and storing Etsy product images."""

    def __init__(self, env):
        self._env = env

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_and_store(self, product_tmpl, image_url):
        """Download an image and store it on the product template.

        Args:
            product_tmpl: A product.template recordset (single record).
            image_url: URL to the image (typically etsystatic.com).

        Returns:
            True if the image was successfully downloaded and stored,
            False otherwise.
        """
        if not image_url:
            return False

        if product_tmpl.image_1920:
            _logger.debug(
                'Product %s already has an image; skipping download.',
                product_tmpl.display_name)
            return False

        try:
            response = requests.get(image_url, timeout=_DOWNLOAD_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            _logger.warning(
                'Failed to download image for product %s from %s: %s',
                product_tmpl.display_name, image_url, exc)
            return False

        if not response.content:
            _logger.warning(
                'Empty response body for image URL %s', image_url)
            return False

        try:
            image_b64 = base64.b64encode(response.content)
            product_tmpl.write({'image_1920': image_b64})
            _logger.info(
                'Stored image for product %s (%d bytes)',
                product_tmpl.display_name, len(response.content))
            return True
        except Exception:
            _logger.exception(
                'Error storing image for product %s',
                product_tmpl.display_name)
            return False

    def cron_download_pending_images(self):
        """Cron job: download images for Etsy products missing images.

        Finds product.template records where:
        - is_etsy_product = True
        - etsy_image_url is set (not False/empty)
        - image_1920 is not set

        Downloads each image with a 1-second delay between requests to
        avoid hammering the server.
        """
        ProductTemplate = self._env['product.template']
        pending = ProductTemplate.search([
            ('is_etsy_product', '=', True),
            ('etsy_image_url', '!=', False),
            ('image_1920', '=', False),
        ])

        if not pending:
            _logger.info('Image downloader: no pending images to download.')
            return

        _logger.info(
            'Image downloader: %d products need images.', len(pending))

        success_count = 0
        fail_count = 0

        for product_tmpl in pending:
            ok = self.download_and_store(
                product_tmpl, product_tmpl.etsy_image_url)
            if ok:
                success_count += 1
            else:
                fail_count += 1
            # Delay between downloads to be a good citizen
            time.sleep(_DELAY_BETWEEN_DOWNLOADS)

        _logger.info(
            'Image downloader complete: %d downloaded, %d failed.',
            success_count, fail_count)
