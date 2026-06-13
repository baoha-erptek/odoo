"""Phase 2 ORM tests for P-LIST-SHIP-CREATE (Jira ESTY-201).

Covers the creator service + the create wizard:

- ``create_profile`` POSTs the form payload, upserts the cache row with
  ``source='odoo_create'`` (etsy_profile_id stored as str), and writes a
  ``shipping_profile_create`` audit row on success.
- A 4xx from Etsy raises and leaves no cache row behind.
- The wizard validates required fields, destination XOR, and the
  delivery-days pair BEFORE any network call.
- ``action_create_profile`` is FR-017 gated to BA users and can set the
  shop default / listing override.
"""

from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import (
    etsy_shipping_profile_creator as creator_module,
)
from odoo.addons.etsy_integration.services.etsy_shipping_profile_creator import (
    create_profile,
)

_CREATOR = (
    'odoo.addons.etsy_integration.wizards.'
    'etsy_shipping_profile_create_wizard.create_profile'
)


def _shop(env, api_id='9200001', default_profile=None):
    return env['etsy.shop'].create({
        'name': 'SHIP-CREATE %s' % api_id,
        'etsy_api_shop_id': api_id,
        'sync_mode': 'email_only',
        'etsy_oauth_access_token': 'tok',
        'etsy_oauth_refresh_token': 'ref',
        'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        'default_shipping_profile_id': default_profile,
    })


@tagged('post_install', '-at_install')
class TestShippingProfileCreator(TransactionCase):

    def test_create_profile_happy_path(self):
        shop = _shop(self.env)
        client = MagicMock()
        client.post.return_value = {
            'shipping_profile_id': 778899,
            'title': 'Standard US',
            'origin_country_iso': 'US',
            'is_deleted': False,
        }
        payload = {
            'title': 'Standard US',
            'origin_country_iso': 'US',
            'primary_cost': '5.00',
            'secondary_cost': '2.00',
            'min_delivery_days': 3,
            'max_delivery_days': 7,
            'destination_country_iso': 'US',
        }
        profile = create_profile(self.env, shop, payload, client=client)

        # POST routed to the per-shop shipping-profiles collection as form data.
        client.post.assert_called_once()
        args, kwargs = client.post.call_args
        self.assertEqual(args[0], 'shops/9200001/shipping-profiles')
        self.assertEqual(kwargs.get('data'), payload)

        self.assertEqual(profile.etsy_profile_id, '778899')
        self.assertEqual(profile.source, 'odoo_create')
        self.assertEqual(profile.shop_id, shop)
        self.assertTrue(profile.created_at)

    def test_create_profile_writes_audit_row(self):
        shop = _shop(self.env, api_id='9200002')
        client = MagicMock()
        client.post.return_value = {'shipping_profile_id': 11, 'title': 'A'}
        create_profile(self.env, shop, {'title': 'A'}, client=client)
        log = self.env['etsy.api.log'].search([
            ('shop_id', '=', shop.id),
            ('source', '=', 'shipping_profile_create'),
        ])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.http_status, 200)

    def test_create_profile_4xx_leaves_no_row(self):
        shop = _shop(self.env, api_id='9200003')
        client = MagicMock()
        client.post.side_effect = ValueError("Etsy returned 400 (bad title)")
        try:
            create_profile(self.env, shop, {'title': 'X'}, client=client)
        except UserError:
            pass
        else:
            self.fail("create_profile must raise UserError on a 4xx")
        rows = self.env['etsy.shipping.profile'].with_context(
            active_test=False).search([('shop_id', '=', shop.id)])
        self.assertFalse(rows, "no cache row should be written on failure")

    def test_create_profile_missing_id_in_response_raises(self):
        shop = _shop(self.env, api_id='9200004')
        client = MagicMock()
        client.post.return_value = {'title': 'no id here'}
        with self.assertRaises(UserError):
            create_profile(self.env, shop, {'title': 'Z'}, client=client)


@tagged('post_install', '-at_install')
class TestShippingProfileCreateWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        # The wizard actions are FR-017 gated to BA users; grant the test
        # user the BA group so the happy-path actions are reachable.
        self.env.user.group_ids = [
            (4, self.env.ref('multichannel_hub_core.group_ba_user').id)]

    def _valid_vals(self, shop):
        country_us = self.env.ref('base.us')
        return {
            'shop_id': shop.id,
            'title': 'Standard US',
            'origin_country_id': country_us.id,
            'origin_postal_code': '10001',
            'primary_cost': 5.0,
            'secondary_cost': 2.0,
            'min_delivery_days': 3,
            'max_delivery_days': 7,
            'destination_kind': 'country',
            'destination_country_id': country_us.id,
        }

    def test_action_builds_payload_and_calls_creator(self):
        shop = _shop(self.env, api_id='9300001')
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(
            self._valid_vals(shop))
        with patch(_CREATOR) as mock_create:
            mock_create.return_value = self.env['etsy.shipping.profile'].create({
                'shop_id': shop.id, 'etsy_profile_id': '42', 'title': 'x',
            })
            wiz.action_create_profile()
        mock_create.assert_called_once()
        call_args = mock_create.call_args[0]
        self.assertEqual(call_args[1], shop)
        vals = call_args[2]
        self.assertEqual(vals['title'], 'Standard US')
        self.assertEqual(vals['origin_country_iso'], 'US')
        self.assertEqual(vals['destination_country_iso'], 'US')
        self.assertNotIn('destination_region', vals)

    def test_destination_country_without_country_raises(self):
        # destination_country_id is only conditionally required in the view,
        # so the method-level guard is the real enforcement.
        shop = _shop(self.env, api_id='9300002')
        vals = self._valid_vals(shop)
        vals['destination_country_id'] = False
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(vals)
        with patch(_CREATOR) as mock_create:
            with self.assertRaises(UserError):
                wiz.action_create_profile()
            mock_create.assert_not_called()

    def test_destination_country_and_region_both_set_raises(self):
        shop = _shop(self.env, api_id='9300003')
        vals = self._valid_vals(shop)
        # 'region' kind but a country is also populated → ambiguous.
        vals['destination_kind'] = 'region'
        vals['destination_region'] = 'eu'
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(vals)
        # country still set from _valid_vals; region kind must clear it or raise.
        with patch(_CREATOR) as mock_create:
            wiz.action_create_profile()
            built = mock_create.call_args[0][2]
            self.assertIn('destination_region', built)
            self.assertNotIn('destination_country_iso', built)

    def test_delivery_days_half_pair_raises(self):
        shop = _shop(self.env, api_id='9300004')
        vals = self._valid_vals(shop)
        vals['max_delivery_days'] = 0
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(vals)
        with patch(_CREATOR) as mock_create:
            with self.assertRaises(UserError):
                wiz.action_create_profile()
            mock_create.assert_not_called()

    def test_non_ba_user_blocked(self):
        shop = _shop(self.env, api_id='9300005')
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(
            self._valid_vals(shop))
        plain = self.env['res.users'].create({
            'name': 'Plain', 'login': 'plain_ship_create',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with patch(_CREATOR):
            with self.assertRaises(AccessError):
                wiz.with_user(plain).action_create_profile()

    def test_set_as_shop_default_writes_shop(self):
        shop = _shop(self.env, api_id='9300006')
        vals = self._valid_vals(shop)
        vals['set_as_shop_default'] = True
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(vals)
        created = self.env['etsy.shipping.profile'].create({
            'shop_id': shop.id, 'etsy_profile_id': '5151', 'title': 'def',
        })
        with patch(_CREATOR, return_value=created):
            wiz.action_create_profile()
        self.assertEqual(shop.default_shipping_profile_id, '5151')

    def test_set_on_listing_writes_override(self):
        shop = _shop(self.env, api_id='9300007')
        channel = self.env.ref('multichannel_hub_core.channel_etsy')
        tmpl = self.env['product.template'].create({
            'name': 'ShipWire', 'list_price': 1.0,
        })
        listing = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': channel.id,
            'etsy_shop_id': shop.id,
        })
        vals = self._valid_vals(shop)
        vals['set_on_listing_id'] = listing.id
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(vals)
        created = self.env['etsy.shipping.profile'].create({
            'shop_id': shop.id, 'etsy_profile_id': '6262', 'title': 'ov',
        })
        with patch(_CREATOR, return_value=created):
            wiz.action_create_profile()
        self.assertEqual(listing.etsy_shipping_profile_id, created)

    def test_negative_cost_raises(self):
        shop = _shop(self.env, api_id='9300008')
        vals = self._valid_vals(shop)
        vals['primary_cost'] = -1.0
        wiz = self.env['etsy.shipping.profile.create.wizard'].create(vals)
        with patch(_CREATOR) as mock_create:
            with self.assertRaises(UserError):
                wiz.action_create_profile()
            mock_create.assert_not_called()


@tagged('post_install', '-at_install')
class TestCreatorModuleSurface(TransactionCase):
    """Guards the module-level symbol the wizard imports."""

    def test_create_profile_is_callable(self):
        self.assertTrue(callable(creator_module.create_profile))
