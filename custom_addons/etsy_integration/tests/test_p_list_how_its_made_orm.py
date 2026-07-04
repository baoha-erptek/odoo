"""Phase 2 ORM tests for P-LIST-HOW-ITS-MADE (Wave 2 / Jira ESTY-193).

3-tier fallback for who_made / when_made; 2-tier for is_supply
(no per-product surface).
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestResolveHowItsMade(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def _shop(self, **defaults):
        vals = {
            'name': 'PLH', 'etsy_api_shop_id': '9200001',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        }
        vals.update(defaults)
        return self.env['etsy.shop'].create(vals)

    def test_listing_override_wins_who_made(self):
        shop = self._shop(default_who_made='someone_else')
        tmpl = self.env['product.template'].create({
            'name': 'PLH-A', 'list_price': 1.0, 'x_who_made': 'collective',
        })
        self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
            'etsy_who_made': 'i_did',
        })
        intent = EtsyListingPublisher(self.env)._resolve_listing_intent(
            tmpl, shop)
        self.assertEqual(
            EtsyListingPublisher._resolve_who_made(tmpl, shop, intent),
            'i_did',
        )

    def test_product_fallback_who_made(self):
        shop = self._shop(default_who_made='someone_else')
        tmpl = self.env['product.template'].create({
            'name': 'PLH-B', 'list_price': 1.0, 'x_who_made': 'collective',
        })
        # listing without override → product fallback
        intent = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
        })
        self.assertEqual(
            EtsyListingPublisher._resolve_who_made(tmpl, shop, intent),
            'collective',
        )

    def test_shop_fallback_who_made(self):
        shop = self._shop(default_who_made='someone_else')
        tmpl = self.env['product.template'].create({
            'name': 'PLH-C', 'list_price': 1.0,
        })
        self.assertEqual(
            EtsyListingPublisher._resolve_who_made(tmpl, shop, None),
            'someone_else',
        )

    def test_when_made_3tier_chain(self):
        shop = self._shop(default_when_made='2010_2019')
        tmpl = self.env['product.template'].create({
            'name': 'PLH-D', 'list_price': 1.0, 'x_when_made': '1990s',
        })
        intent = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
            'etsy_when_made': '1980s',
        })
        # listing wins
        self.assertEqual(
            EtsyListingPublisher._resolve_when_made(tmpl, shop, intent),
            '1980s',
        )
        # clear listing → product fallback
        intent.etsy_when_made = False
        self.assertEqual(
            EtsyListingPublisher._resolve_when_made(tmpl, shop, intent),
            '1990s',
        )
        # clear product → shop default
        tmpl.x_when_made = False
        self.assertEqual(
            EtsyListingPublisher._resolve_when_made(tmpl, shop, intent),
            '2010_2019',
        )

    def test_is_supply_listing_or_shop_only(self):
        shop = self._shop(default_is_supply=True)
        tmpl = self.env['product.template'].create({
            'name': 'PLH-E', 'list_price': 1.0,
        })
        # No intent → shop default
        self.assertTrue(
            EtsyListingPublisher._resolve_is_supply(tmpl, shop, None))
        # Intent with etsy_is_supply=True
        intent = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
            'etsy_is_supply': True,
        })
        self.assertTrue(
            EtsyListingPublisher._resolve_is_supply(tmpl, shop, intent))
        # Intent with etsy_is_supply=False but shop default True → still True
        # (intent False is the model default; doesn't disable the shop flag.
        # Pre-hardening behavior — explicit override fields land in a future
        # slice if/when operators ask for it.)
        intent.etsy_is_supply = False
        self.assertTrue(
            EtsyListingPublisher._resolve_is_supply(tmpl, shop, intent))
