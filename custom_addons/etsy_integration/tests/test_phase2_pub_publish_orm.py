"""Phase 2 ORM tests for P-PUB-PUBLISH (Spec 011 T028)."""

import base64
from unittest.mock import patch, MagicMock

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged

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
class TestPubPublishORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(eac_module, '_read_credentials', return_value=_FAKE)
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        cls.Wizard = cls.env['etsy.publish.wizard']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        cls.ba_user = new_test_user(
            cls.env, login='pub_publish_ba',
            groups='multichannel_hub_core.group_ba_user',
        )
        cls.plain_user = new_test_user(
            cls.env, login='pub_publish_plain',
            groups='base.group_user',
        )

    def _make_shop(self):
        return self.env['etsy.shop'].create({
            'name': 'PUBL TEST',
            'etsy_api_shop_id': '55555555',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
            'default_taxonomy_id': 1, 'default_shipping_profile_id': 2,
            'default_return_policy_id': 3, 'default_who_made': 'i_did',
            'default_when_made': 'made_to_order',
        })

    def _make_product(self, code='PUB-1'):
        return self.Template.create({
            'name': 'Custom Coffee Mug',
            'default_code': code,
            'list_price': 19.99,
            'image_1920': base64.b64encode(_PNG),
        })

    # ------------------------------------------------------------------
    # Wizard registration + FR-017
    # ------------------------------------------------------------------

    def test_wizard_is_transient(self):
        self.assertTrue(self.Wizard._transient)

    def test_wizard_non_ba_blocked(self):
        tmpl = self._make_product()
        shop = self._make_shop()
        w = self.Wizard.with_user(self.plain_user).create({
            'product_tmpl_id': tmpl.id, 'shop_id': shop.id,
        })
        with self.assertRaises(AccessError):
            w.with_user(self.plain_user).action_run_publish()

    # ------------------------------------------------------------------
    # Orchestrator happy path
    # ------------------------------------------------------------------

    def _mock_client(self):
        client = MagicMock()
        client.post.return_value = {'listing_id': 12345}
        client.post_multipart.return_value = {'listing_image_id': 9}
        client.put.return_value = {'products': []}
        client.patch.return_value = {'state': 'active'}
        return client

    def test_orchestrator_runs_full_chain(self):
        tmpl = self._make_product()
        shop = self._make_shop()
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = self._mock_client()
            ClientCls.return_value = client
            result = publisher.run(tmpl, shop)
        self.assertEqual(result.get('listing_id'), 12345)
        status = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ])
        self.assertEqual(status.state, 'published')
        self.assertEqual(status.external_ref, '12345')
        # MF-E2E-1: activation PATCH must hit the SHOP-SCOPED updateListing
        # path — the bare listings/{id} path 404s on the live API.
        patch_paths = [c[0][0] for c in client.patch.call_args_list]
        self.assertIn('shops/55555555/listings/12345', patch_paths)

    def test_orchestrator_skips_create_draft_when_external_ref_set(self):
        """Resume: status row exists with external_ref → skip create_draft."""
        tmpl = self._make_product(code='RESUME-1')
        shop = self._make_shop()
        # Pre-seed status as if a prior run created the listing
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy_channel.id,
            'state': 'error',
            'external_ref': '99999',
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = self._mock_client()
            ClientCls.return_value = client
            publisher.run(tmpl, shop)
        # client.post (create_draft) should NOT have been called for /shops/.../listings
        for c in client.post.call_args_list:
            args = c[0]
            self.assertNotIn('shops/55555555/listings', args[0],
                              "Resume should skip create_draft when external_ref present")

    def test_orchestrator_writes_published_status_on_success(self):
        tmpl = self._make_product(code='SUCC-1')
        shop = self._make_shop()
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            ClientCls.return_value = self._mock_client()
            publisher.run(tmpl, shop)
        status = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ])
        self.assertEqual(status.state, 'published')
        self.assertFalse(status.last_sync_error)

    # ------------------------------------------------------------------
    # Wizard action wrapper
    # ------------------------------------------------------------------

    def test_wizard_action_run_publish_calls_orchestrator(self):
        tmpl = self._make_product(code='WIZ-1')
        shop = self._make_shop()
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id, 'shop_id': shop.id,
        })
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            ClientCls.return_value = self._mock_client()
            w.with_user(self.ba_user).action_run_publish()
        status = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ])
        self.assertEqual(status.state, 'published')
