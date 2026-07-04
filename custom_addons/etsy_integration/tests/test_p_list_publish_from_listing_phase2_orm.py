"""Phase 2 (ORM) tests for P-LIST-PUBLISH-FROM-LISTING.

Verifies multichannel.listing.action_open_etsy_publish_wizard():
  - happy path returns the wizard act_window with both context defaults
  - guards: non-Etsy channel, unresolved etsy_shop_id, multi-record call
  - FR-017 layer-2 (wizard method gate) still fires for non-BA users
    even when the bridge action would have succeeded
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPListPublishFromListingPhase2ORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.etsy_channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.amazon_channel = cls.env.ref('multichannel_hub_core.channel_amazon')
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'PListBridgeShop',
        })
        cls.tmpl = cls.env['product.template'].create({
            'name': 'PListBridge Mug',
            'default_code': 'PLBR-MUG-1',
            'list_price': 19.99,
        })

    def _make_listing(self, **overrides):
        vals = {
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.etsy_channel.id,
            'shop_ref': 'plistbridgeshop',
            'etsy_shop_id': self.shop.id,
            'state': 'draft',
        }
        vals.update(overrides)
        return self.Listing.create(vals)

    def test_happy_path_returns_wizard_action(self):
        listing = self._make_listing()
        result = listing.action_open_etsy_publish_wizard()
        self.assertEqual(result.get('type'), 'ir.actions.act_window')
        self.assertEqual(result.get('res_model'), 'etsy.publish.wizard')
        self.assertEqual(result.get('target'), 'new')
        ctx = result.get('context') or {}
        self.assertEqual(ctx.get('default_product_tmpl_id'), self.tmpl.id)
        self.assertEqual(ctx.get('default_shop_id'), self.shop.id)

    def test_error_non_etsy_channel(self):
        listing = self._make_listing(channel_id=self.amazon_channel.id)
        with self.assertRaises(UserError) as cm:
            listing.action_open_etsy_publish_wizard()
        self.assertIn('Etsy channel', str(cm.exception))

    def test_error_no_etsy_shop_resolved(self):
        listing = self._make_listing(etsy_shop_id=False)
        with self.assertRaises(UserError) as cm:
            listing.action_open_etsy_publish_wizard()
        self.assertIn('Etsy Shop', str(cm.exception))

    def test_error_multi_record_recordset(self):
        listing_a = self._make_listing(shop_ref='plistbridgeshop_a')
        listing_b = self._make_listing(shop_ref='plistbridgeshop_b')
        with self.assertRaises(ValueError):
            (listing_a + listing_b).action_open_etsy_publish_wizard()

    def test_fr017_wizard_gate_blocks_non_ba_user(self):
        """Bridge action is unguarded by design (view + wizard both gate).

        Confirm that even if a non-BA user got past the view hide and
        called the bridge, the wizard's _check_ba_or_raise() fires
        the moment they try to actually publish.
        """
        non_ba = self.env['res.users'].create({
            'name': 'Non BA',
            'login': 'p_list_publish_non_ba@test.local',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        listing = self._make_listing()
        # Bridge action itself does NOT gate (defense layer = view + wizard).
        result = listing.with_user(non_ba).action_open_etsy_publish_wizard()
        wizard = self.env['etsy.publish.wizard'].with_user(non_ba).create({
            'product_tmpl_id': result['context']['default_product_tmpl_id'],
            'shop_id': result['context']['default_shop_id'],
        })
        with self.assertRaises(AccessError):
            wizard.action_run_publish_draft_only()
