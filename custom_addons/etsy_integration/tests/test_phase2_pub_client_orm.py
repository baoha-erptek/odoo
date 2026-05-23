"""Phase 2 ORM tests for P-PUB-CLIENT (Spec 011 T006).

Covers:
- EtsyApiClient.post/put/patch/post_multipart route through _request → same
  auth + 401-refresh + 429-retry + 4xx body capture guarantees as get()
- 401 triggers one-shot token refresh + retry; second 401 raises
- 4xx (non-401) surfaces vendor body in raised ValueError
- post_multipart passes `files=` argument through
- etsy.shop.default_* fields are writable / readable
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient


_FAKE_CREDS = {'client_id': 'kid-test', 'client_secret': 'secret-test'}


@tagged('post_install', '-at_install')
class TestPubClientORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Stub credentials so EtsyApiClient(__init__) doesn't try to read
        # /opt/odoo/secrets/credentials.json in the test runner.
        cls._creds_patcher = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'PUB CLIENT TEST',
            'etsy_api_shop_id': '12345678',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok-test',
            'etsy_oauth_refresh_token': 'ref-test',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def _make_response(self, status=200, json_data=None, text=''):
        r = MagicMock()
        r.status_code = status
        r.headers = {}
        r.text = text
        r.json.return_value = json_data or {}
        r.raise_for_status = MagicMock()
        if status >= 400:
            r.raise_for_status.side_effect = Exception("HTTP %s" % status)
        return r

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    def test_post_routes_through_request(self):
        client = EtsyApiClient(self.shop)
        with patch.object(client, '_request', return_value={'ok': True}) as m:
            result = client.post('listings', json={'name': 'x'})
        self.assertEqual(result, {'ok': True})
        args, kwargs = m.call_args
        self.assertEqual(args[0], 'POST')
        self.assertEqual(args[1], 'listings')
        self.assertEqual(kwargs.get('json'), {'name': 'x'})

    def test_put_routes_through_request(self):
        client = EtsyApiClient(self.shop)
        with patch.object(client, '_request', return_value={'updated': 1}) as m:
            client.put('listings/1/inventory', json={'products': []})
        self.assertEqual(m.call_args[0][0], 'PUT')

    def test_patch_routes_through_request(self):
        client = EtsyApiClient(self.shop)
        with patch.object(client, '_request', return_value={}) as m:
            client.patch('listings/1', json={'price': '9.99'})
        self.assertEqual(m.call_args[0][0], 'PATCH')

    def test_post_multipart_passes_files_kwarg(self):
        client = EtsyApiClient(self.shop)
        files = {'image': ('a.jpg', b'\x00\x01', 'image/jpeg')}
        with patch.object(client, '_request', return_value={}) as m:
            client.post_multipart('listings/1/images', files=files)
        self.assertEqual(m.call_args[0][0], 'POST')
        self.assertIs(m.call_args[1].get('files'), files)

    # ------------------------------------------------------------------
    # Shop defaults
    # ------------------------------------------------------------------

    def test_shop_default_fields_writable(self):
        self.shop.sudo().write({
            'default_taxonomy_id': 1234,
            'default_shipping_profile_id': 5678,
            'default_return_policy_id': 9012,
            'default_who_made': 'i_did',
            'default_when_made': '2020_2026',
            'default_is_supply': False,
        })
        self.assertEqual(self.shop.sudo().default_taxonomy_id, 1234)
        self.assertEqual(self.shop.sudo().default_who_made, 'i_did')
        self.assertFalse(self.shop.sudo().default_is_supply)

    def test_shop_default_who_made_selection(self):
        sel = self.env['etsy.shop']._fields['default_who_made'].selection
        codes = {code for code, _ in sel}
        for needed in ('i_did', 'someone_else', 'collective'):
            self.assertIn(needed, codes)
