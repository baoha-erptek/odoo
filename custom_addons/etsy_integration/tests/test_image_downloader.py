"""Tests for the image downloader service.

Verifies image URL transformation, skip-when-image-exists logic,
and graceful handling of download failures.
"""
import base64

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..services.email_parser import RawEmail
from ..services.image_downloader import ImageDownloader


@tagged('at_install')
class TestImageDownloader(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _create_etsy_product(self, name='Test Etsy Product', image_url='',
                              image_data=False):
        """Helper to create a product.template with Etsy fields."""
        vals = {
            'name': name,
            'is_etsy_product': True,
            'etsy_image_url': image_url,
        }
        if image_data:
            vals['image_1920'] = image_data
        return self.env['product.template'].create(vals)

    # ------------------------------------------------------------------
    # T044c-1: URL transform in email parser
    # ------------------------------------------------------------------

    def test_url_transform_in_parser(self):
        """Verify that the email parser replaces '75x75' with '300x300'
        in image URLs extracted from HTML."""
        raw = RawEmail(
            message_id='<test-img-transform@etsy.com>',
            subject='New order from Etsy',
            date='Mon, 01 Jan 2024 00:00:00 +0000',
            text_body='',
            html_body=(
                '<html><body>'
                '<img src="https://i.etsystatic.com/28215280/r/il/abc123/'
                '6049408768/il_75x75.6049408768_n0ek.jpg"/>'
                '</body></html>'
            ),
        )
        # We call the internal _extract_image_urls helper via import
        from ..services.email_parser import _extract_image_urls
        urls = _extract_image_urls(raw.html_body)

        self.assertTrue(len(urls) >= 1, 'Expected at least one image URL')
        for url in urls:
            self.assertNotIn(
                '75x75', url,
                'Image URL should have 75x75 replaced with 300x300')
            self.assertIn(
                '300x300', url,
                'Image URL should contain 300x300 after transformation')

    # ------------------------------------------------------------------
    # T044c-2: Skip download when product already has an image
    # ------------------------------------------------------------------

    def test_skip_when_already_has_image(self):
        """When a product already has image_1920 set, download_and_store
        should return False without making any HTTP request."""
        # 1x1 transparent PNG as base64
        existing_image = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4'
            b'\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05'
            b'\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        product = self._create_etsy_product(
            name='Product With Image',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
            image_data=existing_image,
        )

        downloader = ImageDownloader(self.env)

        with patch('odoo.addons.etsy_integration.services.image_downloader.requests.get') as mock_get:
            result = downloader.download_and_store(
                product, 'https://i.etsystatic.com/test/300x300.jpg')

            self.assertFalse(result, 'Should return False when image already exists')
            mock_get.assert_not_called()

    # ------------------------------------------------------------------
    # T044c-3: Graceful handling of download failure
    # ------------------------------------------------------------------

    def test_download_failure_graceful(self):
        """When the HTTP request fails, download_and_store should return
        False and leave the product image unchanged."""
        product = self._create_etsy_product(
            name='Product Without Image',
            image_url='https://i.etsystatic.com/invalid/does-not-exist.jpg',
        )
        self.assertFalse(product.image_1920, 'Product should start with no image')

        downloader = ImageDownloader(self.env)

        import requests as req_lib
        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get',
            side_effect=req_lib.exceptions.ConnectionError('Simulated failure'),
        ):
            result = downloader.download_and_store(
                product, 'https://i.etsystatic.com/invalid/does-not-exist.jpg')

        self.assertFalse(result, 'Should return False on download failure')
        self.assertFalse(
            product.image_1920,
            'Product image should remain unset after download failure')
