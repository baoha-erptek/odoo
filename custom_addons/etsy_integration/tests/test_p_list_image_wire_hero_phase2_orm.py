"""Phase 2 ORM tests for P-LIST-IMAGE-WIRE-HERO (spec slice).

Tests the listing-tier image selection in upload_images(). Current code
checks template main + gallery + shop default, but SKIPS the listing tier
(multichannel.listing.image_1920).

The fix inserts listing-tier check at the TOP of candidates list, before
template main.

Candidate selection order (FIXED):
  1. listing.image_1920 (marketing override)
  2. template.image_1920 (product main)
  3. template.x_extra_image_ids (gallery rows)
  4. shop.default_image_1920 (brand-voice rescue)

Tests use small PNG bytes to distinguish tiers by their binary content.
"""

import base64
from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}

# Tiny 1x1 PNG bytes for distinguishing tiers in assertions.
# Each is a valid minimal PNG with different content for identity checks.
_PNG_RED = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\r\xb5P\x00\x00\x00\x00IEND\xaeB`\x82'
)
_PNG_BLUE = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\xf8\x0f'
    b'\x00\x00\x01\x01\x00\x05\x18\r\xb5Q\x00\x00\x00\x00IEND\xaeB`\x82'
)
_PNG_GREEN = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x0f\xf8'
    b'\x00\x00\x01\x01\x00\x05\x18\r\xb5R\x00\x00\x00\x00IEND\xaeB`\x82'
)
_PNG_YELLOW = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xf8\x0f'
    b'\x00\x00\x01\x01\x00\x05\x18\r\xb5S\x00\x00\x00\x00IEND\xaeB`\x82'
)


@tagged('post_install', '-at_install')
class TestPListImageWireHeroPhase2Orm(TransactionCase):
    """Phase 2 ORM tests for listing-tier image selection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Listing = cls.env['multichannel.listing']
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def _make_shop(self, name='IMAGE-WIRE-SHOP', api_id='8888001',
                   default_image=None):
        """Factory: create an etsy.shop."""
        vals = {
            'name': name,
            'etsy_api_shop_id': api_id,
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        }
        if default_image is not None:
            vals['default_image_1920'] = base64.b64encode(default_image).decode()
        return self.env['etsy.shop'].create(vals)

    def _make_tmpl(self, name='Test Product', code='TST-1',
                   main_image=None):
        """Factory: create a product.template with optional main image."""
        vals = {
            'name': name,
            'default_code': code,
            'list_price': 50.0,
        }
        if main_image is not None:
            vals['image_1920'] = base64.b64encode(main_image).decode()
        return self.Template.create(vals)

    def _make_listing_intent(self, tmpl, shop, shop_ref=None, image=None):
        """Factory: create a multichannel.listing intent for (tmpl, shop).

        If shop_ref is None, creates a template-wide stub (shop_ref='').
        If shop_ref is a string, uses shop name for case-insensitive matching.
        If image is binary, stores it in the listing row.
        """
        vals = {
            'product_tmpl_id': tmpl.id,
            'channel_id': self.channel.id,
        }
        if shop_ref is not None:
            vals['shop_ref'] = shop_ref
        else:
            # Template-wide stub: shop_ref='' (NULL-shop fallback)
            vals['shop_ref'] = ''
        if image is not None:
            vals['image_1920'] = base64.b64encode(image).decode()
        return self.Listing.sudo().create(vals)

    # --------------------------------------------------------------------
    # Test 1: Listing image wins when set (regression from current code)
    # --------------------------------------------------------------------

    def test_upload_images_uses_listing_image_when_set(self):
        """Listing.image_1920 set + tmpl.image_1920 set + shop default set.

        FIRST upload call must use LISTING image bytes (not template).
        Tests the NEW listing-tier candidate selection.
        """
        shop = self._make_shop(name='LISTEDBRAND', api_id='8888001',
                               default_image=_PNG_YELLOW)
        tmpl = self._make_tmpl(name='Test Product', code='TST-1',
                               main_image=_PNG_RED)
        # Create listing intent with own image (listing tier)
        self._make_listing_intent(tmpl, shop, shop_ref='listedbrand',
                                  image=_PNG_BLUE)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 111}
            publisher.upload_images(tmpl, listing_id=12345, shop=shop)
            # Inspect FIRST call
            self.assertTrue(client.post_multipart.called)
            calls = client.post_multipart.call_args_list
            first_call_args, first_call_kwargs = calls[0]
            files = first_call_kwargs['files']
            filename, payload_bytes, mimetype = files['image']
            # ASSERTION: FIRST call bytes should be LISTING image (BLUE),
            # NOT template image (RED).
            self.assertEqual(payload_bytes, _PNG_BLUE,
                             "FIRST upload should use listing.image_1920, not tmpl.image_1920")

    # --------------------------------------------------------------------
    # Test 2: Template main wins when listing empty (regression guard)
    # --------------------------------------------------------------------

    def test_upload_images_falls_through_to_template_when_listing_empty(self):
        """Listing.image_1920 NOT set, tmpl.image_1920 set.

        FIRST call must use TEMPLATE image bytes.
        Regression guard: current code should already pass this.
        """
        shop = self._make_shop(name='FALLTHROUGH', api_id='8888002')
        tmpl = self._make_tmpl(name='Product With Main', code='TST-2',
                               main_image=_PNG_RED)
        # Create listing intent WITHOUT image (empty listing tier)
        self._make_listing_intent(tmpl, shop, shop_ref='fallthrough',
                                  image=None)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 222}
            publisher.upload_images(tmpl, listing_id=23456, shop=shop)
            self.assertTrue(client.post_multipart.called)
            calls = client.post_multipart.call_args_list
            first_call_args, first_call_kwargs = calls[0]
            files = first_call_kwargs['files']
            filename, payload_bytes, mimetype = files['image']
            self.assertEqual(payload_bytes, _PNG_RED,
                             "When listing.image empty, should use tmpl.image_1920")

    # --------------------------------------------------------------------
    # Test 3: Shop default wins when template AND listing empty (regression guard)
    # --------------------------------------------------------------------

    def test_upload_images_falls_through_to_shop_default_when_both_empty(self):
        """Listing empty, tmpl.image_1920 empty, shop default set.

        ONE call with SHOP DEFAULT bytes.
        Regression guard: current code should already pass this.
        """
        shop = self._make_shop(name='SHOPDEFAULT', api_id='8888003',
                               default_image=_PNG_GREEN)
        tmpl = self._make_tmpl(name='Product No Main', code='TST-3',
                               main_image=None)
        # Create listing intent without image
        self._make_listing_intent(tmpl, shop, shop_ref='shopdefault',
                                  image=None)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 333}
            publisher.upload_images(tmpl, listing_id=34567, shop=shop)
            self.assertTrue(client.post_multipart.called)
            calls = client.post_multipart.call_args_list
            first_call_args, first_call_kwargs = calls[0]
            files = first_call_kwargs['files']
            filename, payload_bytes, mimetype = files['image']
            self.assertEqual(payload_bytes, _PNG_GREEN,
                             "When tmpl and listing empty, should use shop.default_image_1920")

    # --------------------------------------------------------------------
    # Test 4: No image anywhere = no calls (regression guard)
    # --------------------------------------------------------------------

    def test_upload_images_no_image_anywhere_makes_no_calls(self):
        """All tiers empty: listing, tmpl, shop default.

        ZERO upload calls. returns [].
        """
        shop = self._make_shop(name='NOIMAGES', api_id='8888004',
                               default_image=None)
        tmpl = self._make_tmpl(name='Product Bare', code='TST-4',
                               main_image=None)
        # Create listing intent without image
        self._make_listing_intent(tmpl, shop, shop_ref='noimages',
                                  image=None)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            result = publisher.upload_images(tmpl, listing_id=45678, shop=shop)
            # Should return empty list, no calls
            self.assertEqual(result, [])
            client.post_multipart.assert_not_called()

    # --------------------------------------------------------------------
    # Test 5: Template-wide stub (NULL-shop listing) with image
    # --------------------------------------------------------------------

    def test_upload_images_listing_null_shop_stub_used_as_fallback(self):
        """Listing row with shop_ref='' (template-wide stub) has image.

        Tmpl.image_1920 is empty. FIRST call should use listing-stub image.
        Tests the NULL-shop fallback in _resolve_listing_intent for reads.
        """
        shop = self._make_shop(name='STUBSHOP', api_id='8888005',
                               default_image=None)
        tmpl = self._make_tmpl(name='Product Stub Test', code='TST-5',
                               main_image=None)
        # Create template-wide stub (shop_ref='') with image
        self._make_listing_intent(tmpl, shop, shop_ref='',  # NULL-shop fallback
                                  image=_PNG_GREEN)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {'listing_image_id': 555}
            publisher.upload_images(tmpl, listing_id=56789, shop=shop)
            self.assertTrue(client.post_multipart.called)
            calls = client.post_multipart.call_args_list
            first_call_args, first_call_kwargs = calls[0]
            files = first_call_kwargs['files']
            filename, payload_bytes, mimetype = files['image']
            self.assertEqual(payload_bytes, _PNG_GREEN,
                             "Template-wide listing stub image should be used "
                             "when no shop-specific intent exists")
