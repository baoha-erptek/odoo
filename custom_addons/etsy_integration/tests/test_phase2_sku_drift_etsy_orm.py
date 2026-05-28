"""Phase 2 ORM tests for P-HUB-SKU-DRIFT checkpoint b (Spec 009 T024).

The etsy_integration override of `product.template._push_sku_to_channel('etsy')`
routes through `EtsyInventoryPusher.push()` to PUT the new SKU to Etsy.
"""

from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestSkuDriftEtsyOverride(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(eac_module, '_read_credentials', return_value=_FAKE)
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)

    def _setup(self):
        shop = self.env['etsy.shop'].create({
            'name': 'DRIFT TEST SHOP',
            'etsy_api_shop_id': '44444444',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })
        tmpl = self.Template.create({
            'name': 'Custom Coffee Mug',
            'default_code': 'LEGACY-MUG',
            'list_price': 19.99,
        })
        self.env['etsy.listing'].create({
            'shop_id': shop.id,
            'etsy_listing_id': 'LST-DRIFT',
            'title': 'L', 'url': 'https://etsy/x',
            'state': 'active',
            'last_modified': '2026-05-23 00:00:00',
        })
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy_channel.id,
            'state': 'published',
            'external_ref': 'LST-DRIFT',
        })
        return shop, tmpl

    def test_etsy_push_override_calls_inventory_pusher(self):
        shop, tmpl = self._setup()
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = MagicMock()
            client.put.return_value = {'products': []}
            ClientCls.return_value = client
            result = tmpl.sudo()._push_sku_to_channel('etsy')
        self.assertTrue(result)
        self.assertEqual(client.put.call_count, 1)
        path = client.put.call_args[0][0]
        self.assertEqual(path, 'listings/LST-DRIFT/inventory')

    def test_non_etsy_channel_is_noop(self):
        """Hub default returns True without side effect; override delegates only for 'etsy'."""
        shop, tmpl = self._setup()
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = MagicMock()
            ClientCls.return_value = client
            result = tmpl.sudo()._push_sku_to_channel('amazon')
        self.assertTrue(result)
        self.assertEqual(client.put.call_count, 0)
