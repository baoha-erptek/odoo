"""Phase 2 ORM tests for P-PUB-PER-PRODUCT-DEFAULTS publisher payload (MP006, Spec 011).

Verifies EtsyListingPublisher._build_create_draft_payload uses per-product
overrides (x_taxonomy_id, x_who_made, x_when_made) when set, and falls back
to shop defaults when product values are blank.
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubPerProductDefaultsPayload(TransactionCase):
    """ORM tests for per-product-defaults payload builder."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Shop = cls.env['etsy.shop']

    def _shop(self, **kwargs):
        """Factory to create test etsy.shop."""
        defaults = {
            'name': 'PER-PRODUCT DEFAULTS TEST SHOP',
            'etsy_api_shop_id': '99999999',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        }
        defaults.update(kwargs)
        return self.Shop.create(defaults)

    def _tmpl(self, name='Test Product', list_price=10.0, **defaults_kwargs):
        """Factory to create product.template with per-product defaults."""
        vals = {
            'name': name,
            'default_code': name.upper().replace(' ', '-'),
            'list_price': list_price,
        }
        vals.update(defaults_kwargs)
        return self.Template.create(vals)

    def test_taxonomy_id_uses_product_value_when_set(self):
        """When x_taxonomy_id is set, payload uses product value not shop default."""
        shop = self._shop(default_taxonomy_id='99999')
        tmpl = self._tmpl('Taxonomy Override', x_taxonomy_id='12345')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['taxonomy_id'], 12345)

    def test_taxonomy_id_falls_back_to_shop_default_when_product_blank(self):
        """When x_taxonomy_id is blank, payload uses shop default."""
        shop = self._shop(default_taxonomy_id='99999')
        tmpl = self._tmpl('No Taxonomy Override')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['taxonomy_id'], 99999)

    def test_taxonomy_id_int4_overflow_preserved(self):
        """Large taxonomy IDs (> int4 max) stored as Char survive int() coercion."""
        shop = self._shop(default_taxonomy_id='99999')
        tmpl = self._tmpl(
            'Large Taxonomy ID',
            x_taxonomy_id='285149016922',  # > 2147483647 (int4 max)
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['taxonomy_id'], 285149016922)

    def test_who_made_uses_product_value_when_set(self):
        """When x_who_made is set, payload uses product value not shop default."""
        shop = self._shop(default_who_made='i_did')
        tmpl = self._tmpl('Who Made Override', x_who_made='someone_else')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['who_made'], 'someone_else')

    def test_who_made_falls_back_to_shop_default(self):
        """When x_who_made is blank, payload uses shop default."""
        shop = self._shop(default_who_made='collective')
        tmpl = self._tmpl('No Who Made Override')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['who_made'], 'collective')

    def test_who_made_falls_back_to_hardcoded_default_when_both_blank(self):
        """When both product and shop are blank, payload defaults to 'i_did'."""
        shop = self._shop()  # default_who_made left blank
        tmpl = self._tmpl('No Who Made Anywhere')  # x_who_made blank
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['who_made'], 'i_did')

    def test_when_made_uses_product_value_when_set(self):
        """When x_when_made is set, payload uses product value not shop default."""
        shop = self._shop(default_when_made='made_to_order')
        tmpl = self._tmpl('When Made Override', x_when_made='1980s')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['when_made'], '1980s')

    def test_when_made_falls_back_to_shop_default(self):
        """When x_when_made is blank, payload uses shop default."""
        shop = self._shop(default_when_made='2020_2026')
        tmpl = self._tmpl('No When Made Override')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['when_made'], '2020_2026')

    def test_when_made_falls_back_to_hardcoded_when_both_blank(self):
        """When both product and shop are blank, payload defaults to 'made_to_order'."""
        shop = self._shop()  # default_when_made left blank
        tmpl = self._tmpl('No When Made Anywhere')  # x_when_made blank
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        self.assertEqual(payload['when_made'], 'made_to_order')
