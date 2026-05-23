"""Phase 2 ORM tests for P-PUB-IMAGES (Spec 011 T016) — option B (MVP).

Scoped down per finding 2026-05-23: Odoo 19 CE has no `product.image`
model. This slice uploads the template's `image_1920` (single image) per
publish; no manifest diff, no DELETE path. Multi-image-per-listing + diff
deferred to a follow-up slice when business value surfaces.
"""

import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}
_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx'
    b'\x9cc\xfc\xcf\xc0\x00\x00\x00\x03\x00\x01a\xc2C\x8f\x00\x00\x00\x00IEND\xaeB`\x82'
)


@tagged('post_install', '-at_install')
class TestPubImagesORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(eac_module, '_read_credentials', return_value=_FAKE)
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']

    def _make_shop(self):
        return self.env['etsy.shop'].create({
            'name': 'IMG TEST',
            'etsy_api_shop_id': '66666666',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def test_upload_images_skips_when_no_image(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'No image product',
            'default_code': 'NOIMG-1',
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            result = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(client.post_multipart.call_count, 0)
        self.assertEqual(result, [])

    def test_upload_images_posts_multipart_with_image_bytes(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'With image product',
            'default_code': 'IMG-1',
            'image_1920': base64.b64encode(_PNG),
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 9001}
            publisher.upload_images(tmpl, 'LST-IMG', shop)
        self.assertEqual(client.post_multipart.call_count, 1)
        args, kwargs = client.post_multipart.call_args
        self.assertEqual(args[0], 'listings/LST-IMG/images')
        files = kwargs.get('files') or {}
        self.assertIn('image', files)
        # files['image'] is (filename, bytes, mime)
        filename, payload, mime = files['image']
        self.assertEqual(mime, 'image/jpeg')
        self.assertTrue(payload)  # non-empty bytes

    def test_upload_images_returns_response_list(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'Return test',
            'default_code': 'RTN-1',
            'image_1920': base64.b64encode(_PNG),
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 42}
            results = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].get('listing_image_id'), 42)
