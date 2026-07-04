"""Phase 2 ORM tests for P-LIST-SHIPPING (Wave 2 / Jira ESTY-191).

Covers:
- etsy.shipping.profile cache (UNIQUE (shop_id, etsy_profile_id)).
- sync_shipping_profiles upsert + soft-delete handling.
- EtsyListingPublisher._resolve_shipping_profile_id fallback chain.
"""

from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_shipping_profile_syncer import (
    sync_shipping_profiles,
)
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestShippingProfileCache(TransactionCase):

    def test_unique_composite_enforced(self):
        shop = self.env['etsy.shop'].create({
            'name': 'PLS A', 'etsy_api_shop_id': '9100001',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })
        Profile = self.env['etsy.shipping.profile']
        Profile.create({
            'shop_id': shop.id, 'etsy_profile_id': '111',
            'title': 'Standard US',
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Profile.create({
                    'shop_id': shop.id, 'etsy_profile_id': '111',
                    'title': 'dup',
                })


@tagged('post_install', '-at_install')
class TestShippingProfileSyncer(TransactionCase):

    def _shop(self, api_id='9100002'):
        return self.env['etsy.shop'].create({
            'name': 'PLS B', 'etsy_api_shop_id': api_id,
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def test_sync_creates_and_marks_deleted(self):
        shop = self._shop()
        fake_client = MagicMock()
        fake_client.get.return_value = {
            'results': [
                {'shipping_profile_id': 1001, 'title': 'Standard US',
                 'origin_country_iso': 'US', 'is_deleted': False},
                {'shipping_profile_id': 1002, 'title': 'Express',
                 'origin_country_iso': 'US', 'is_deleted': True},
            ]
        }
        created, updated = sync_shipping_profiles(
            self.env, shop, client=fake_client)
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        active = self.env['etsy.shipping.profile'].search([
            ('shop_id', '=', shop.id), ('etsy_profile_id', '=', '1001'),
        ])
        self.assertTrue(active.active)
        soft = self.env['etsy.shipping.profile'].with_context(
            active_test=False).search([
            ('shop_id', '=', shop.id), ('etsy_profile_id', '=', '1002'),
        ])
        self.assertFalse(soft.active)
        self.assertTrue(soft.is_deleted)


@tagged('post_install', '-at_install')
class TestResolveShippingProfile(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def _shop(self, default_profile=None):
        return self.env['etsy.shop'].create({
            'name': 'PLS C', 'etsy_api_shop_id': '9100003',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
            'default_shipping_profile_id': default_profile,
        })

    def test_listing_override_wins(self):
        shop = self._shop(default_profile='5000')
        tmpl = self.env['product.template'].create({
            'name': 'Ship', 'list_price': 1.0,
        })
        profile = self.env['etsy.shipping.profile'].create({
            'shop_id': shop.id, 'etsy_profile_id': '4242',
            'title': 'Override Profile',
        })
        self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
            'etsy_shipping_profile_id': profile.id,
        })
        publisher = EtsyListingPublisher(self.env)
        self.assertEqual(
            publisher._resolve_shipping_profile_id(tmpl, shop), 4242)

    def test_shop_default_fallback(self):
        shop = self._shop(default_profile='5000')
        tmpl = self.env['product.template'].create({
            'name': 'ShipDefault', 'list_price': 1.0,
        })
        publisher = EtsyListingPublisher(self.env)
        self.assertEqual(
            publisher._resolve_shipping_profile_id(tmpl, shop), 5000)

    def test_soft_zero_when_nothing_set(self):
        shop = self._shop(default_profile=False)
        tmpl = self.env['product.template'].create({
            'name': 'ShipEmpty', 'list_price': 1.0,
        })
        publisher = EtsyListingPublisher(self.env)
        self.assertEqual(
            publisher._resolve_shipping_profile_id(tmpl, shop), 0)
