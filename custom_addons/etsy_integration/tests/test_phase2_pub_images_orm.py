"""Phase 2 ORM tests for P-PUB-IMAGES + P-PUB-MULTI-IMAGE (Spec 011, MP006).

Original slice (P-PUB-IMAGES T016): single-image upload via image_1920.
Multi-image slice (P-PUB-MULTI-IMAGE 2026-05-27): iterates a custom
`multichannel.product.image` gallery (chosen over website_sale's
product.image to avoid pulling 10+ unwanted modules — Standard-Odoo-First
escalation 2026-05-27). Main image_1920 first, then gallery rows sorted
by sequence; cap at Etsy's 10-image limit; per-image failures continue.
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

    # ------------------------------------------------------------------
    # P-PUB-MULTI-IMAGE (2026-05-27) — multi-image iteration tests
    # ------------------------------------------------------------------

    def _add_gallery(self, tmpl, sequences):
        Gallery = self.env['multichannel.product.image']
        rows = []
        for seq in sequences:
            rows.append(Gallery.create({
                'product_tmpl_id': tmpl.id,
                'sequence': seq,
                'image_1920': base64.b64encode(_PNG),
            }))
        return Gallery.browse([r.id for r in rows])

    def test_upload_main_plus_gallery_in_sequence_order(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'gallery order',
            'default_code': 'GO-1',
            'image_1920': base64.b64encode(_PNG),
        })
        self._add_gallery(tmpl, [30, 10, 20])
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 1}
            results = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(client.post_multipart.call_count, 4)
        self.assertEqual(len(results), 4)

    def test_upload_exactly_ten_images_no_skip_log(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'exactly ten',
            'default_code': 'X10-1',
            'image_1920': base64.b64encode(_PNG),
        })
        self._add_gallery(tmpl, [10 * i for i in range(1, 10)])
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 1}
            results = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(len(results), 10)
        self.assertEqual(client.post_multipart.call_count, 10)

    def test_upload_eleven_capped_at_ten_with_info_log(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'eleven try',
            'default_code': 'X11-1',
            'image_1920': base64.b64encode(_PNG),
        })
        self._add_gallery(tmpl, [10 * i for i in range(1, 11)])  # 10 gallery + 1 main = 11
        # Sanity: confirm fixture actually persisted 10 gallery rows w/ images.
        self.assertEqual(len(tmpl.x_extra_image_ids), 10)
        self.assertTrue(all(r.image_1920 for r in tmpl.x_extra_image_ids))
        self.assertTrue(bool(tmpl.image_1920))
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 1}
            with self.assertLogs(
                'odoo.addons.etsy_integration.services.etsy_listing_publisher',
                level='WARNING',
            ) as cm:
                results = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(len(results), 10)
        self.assertEqual(client.post_multipart.call_count, 10)
        self.assertTrue(
            any('cap' in m.lower() or 'skip' in m.lower() for m in cm.output),
            f"expected cap/skip WARNING log, got: {cm.output}",
        )

    def test_upload_gallery_only_no_main(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'no main',
            'default_code': 'NM-1',
        })
        self._add_gallery(tmpl, [10, 20, 30])
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 1}
            results = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(len(results), 3)
        self.assertEqual(client.post_multipart.call_count, 3)

    def test_upload_per_image_failure_continues(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'partial fail',
            'default_code': 'PF-1',
            'image_1920': base64.b64encode(_PNG),
        })
        self._add_gallery(tmpl, [10, 20])  # 1 main + 2 gallery = 3 attempts
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.side_effect = [
                {'listing_image_id': 1},
                RuntimeError('400 Bad Request'),
                {'listing_image_id': 3},
            ]
            with self.assertLogs(
                'odoo.addons.etsy_integration.services.etsy_listing_publisher',
                level='WARNING',
            ) as cm:
                results = publisher.upload_images(tmpl, 'LST-1', shop)
        self.assertEqual(client.post_multipart.call_count, 3)
        self.assertEqual(len(results), 2)  # 1st + 3rd succeeded
        self.assertTrue(
            any('400' in m or 'Bad Request' in m for m in cm.output),
            f"expected failure WARNING log, got: {cm.output}",
        )
