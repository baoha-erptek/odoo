"""Phase 2 ORM tests for P-ENH-ESTY-190 / ADR-017 — 3-tier brand-voice fallback.

Verifies the publisher helpers ``_resolve_title_with_fallback``,
``_resolve_description_with_fallback``, ``_resolve_image_with_fallback``
across the listing → product → shop default tier chain. Also asserts
``upload_images`` consults the shop default when neither template main
nor gallery has any image bytes.
"""

import base64
from types import SimpleNamespace

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)

_GIF_BYTES = base64.b64decode(
    b'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
)


@tagged('post_install', '-at_install')
class TestPEnhEsty190Phase2ORM(TransactionCase):
    """3-tier fallback chain for title/description/image."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'BrandVoiceShop',
        })
        cls.product_with_name = cls.env['product.template'].create({
            'name': 'Product Canonical Name',
            'description_sale': 'Product Canonical Description',
            'list_price': 10.0,
            'type': 'consu',
        })
        cls.publisher = EtsyListingPublisher(cls.env)

    def _make_listing(self, title='', description='', image_bytes=False):
        channel = self.env.ref('multichannel_hub_core.channel_etsy')
        vals = {
            'product_tmpl_id': self.product_with_name.id,
            'title': title,
            'description': description,
            'channel_id': channel.id,
        }
        if image_bytes:
            vals['image_1920'] = base64.b64encode(image_bytes)
        return self.env['multichannel.listing'].create(vals)

    # ------------------------------------------------------------------
    # Title fallback
    # ------------------------------------------------------------------
    def test_title_listing_present(self):
        intent = self._make_listing(title='Listing-level Override')
        result = self.publisher._resolve_title_with_fallback(
            intent, self.product_with_name, self.shop.sudo(),
        )
        self.assertEqual(result, 'Listing-level Override')

    def test_title_falls_back_to_product(self):
        intent = self._make_listing(title='')
        self.shop.default_title = 'Shop Default Title'
        result = self.publisher._resolve_title_with_fallback(
            intent, self.product_with_name, self.shop.sudo(),
        )
        self.assertEqual(result, 'Product Canonical Name')

    def test_title_falls_back_to_shop_default(self):
        # product.template.name is NOT NULL in Odoo, so the "product name
        # absent" branch is exercised via a duck-typed namespace rather
        # than an empty-name ORM row.
        intent = self.env['multichannel.listing']
        bare_tmpl = SimpleNamespace(id=0, name='')
        self.shop.default_title = 'Shop Brand Voice'
        with self.assertLogs(level='DEBUG'):
            result = self.publisher._resolve_title_with_fallback(
                intent, bare_tmpl, self.shop.sudo(),
            )
        self.assertEqual(result, 'Shop Brand Voice')

    def test_title_all_empty_returns_empty_string(self):
        intent = self.env['multichannel.listing']
        bare_tmpl = SimpleNamespace(id=0, name='')
        # shop with no default_title set
        empty_shop = self.env['etsy.shop'].create({
            'name': 'EmptyDefaultsShop',
        }).sudo()
        result = self.publisher._resolve_title_with_fallback(
            intent, bare_tmpl, empty_shop,
        )
        self.assertEqual(result, '')

    # ------------------------------------------------------------------
    # Description fallback
    # ------------------------------------------------------------------
    def test_description_listing_present(self):
        intent = self._make_listing(description='Listing-level desc')
        result = self.publisher._resolve_description_with_fallback(
            intent, self.product_with_name, self.shop.sudo(),
        )
        self.assertEqual(result, 'Listing-level desc')

    def test_description_falls_back_to_product(self):
        intent = self._make_listing(description='')
        self.shop.default_description = 'Shop Default Desc'
        result = self.publisher._resolve_description_with_fallback(
            intent, self.product_with_name, self.shop.sudo(),
        )
        self.assertEqual(result, 'Product Canonical Description')

    def test_description_falls_back_to_shop_default(self):
        bare_product = self.env['product.template'].create({
            'name': 'Bare Product',
            'list_price': 0.0,
            'type': 'consu',
        })
        intent = self._make_listing(description='')
        self.shop.default_description = 'Shop Default Description'
        with self.assertLogs(level='DEBUG'):
            result = self.publisher._resolve_description_with_fallback(
                intent, bare_product, self.shop.sudo(),
            )
        self.assertEqual(result, 'Shop Default Description')

    # ------------------------------------------------------------------
    # Image fallback (used by upload_images)
    # ------------------------------------------------------------------
    def test_image_falls_back_to_shop_default(self):
        bare_product = self.env['product.template'].create({
            'name': 'Bare Product Image Test',
            'list_price': 0.0,
            'type': 'consu',
        })
        self.shop.default_image_1920 = base64.b64encode(_GIF_BYTES)
        with self.assertLogs(level='DEBUG'):
            result = self.publisher._resolve_image_with_fallback(
                bare_product, self.shop.sudo(),
            )
        self.assertTrue(result)

    def test_image_listing_present_uses_product(self):
        product_with_image = self.env['product.template'].create({
            'name': 'Imaged Product',
            'list_price': 0.0,
            'type': 'consu',
            'image_1920': base64.b64encode(_GIF_BYTES),
        })
        result = self.publisher._resolve_image_with_fallback(
            product_with_image, self.shop.sudo(),
        )
        # Helper returns the template image; shop default is not consulted.
        self.assertEqual(result, product_with_image.image_1920)
