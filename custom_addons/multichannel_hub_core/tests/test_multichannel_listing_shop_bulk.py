"""Phase 2 ORM tests for P-LIST-SHOP-BULK (Wave 2 / Jira ESTY-197).

Server actions on the Listings list view:
  action_bulk_mark_ready   — Draft → Ready (state-locked).
  action_bulk_reset_to_draft — Ready/Error → Draft (Published skipped).

Both refuse rows in the wrong state and report a notification with the
skipped count (FR-017 write-defense pattern).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBulkMarkReady(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.tmpl = cls.env['product.template'].create({
            'name': 'BULK Tmpl', 'list_price': 1.0,
        })

    def _make(self, state, shop='shop1'):
        return self.Listing.sudo().create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'shop_ref': shop,
            'state': state,
        })

    def test_mark_ready_flips_draft_only(self):
        a = self._make('draft', 'a')
        b = self._make('draft', 'b')
        c = self._make('ready', 'c')
        d = self._make('published', 'd')
        recs = a | b | c | d
        action = recs.action_bulk_mark_ready()
        self.assertEqual(a.state, 'ready')
        self.assertEqual(b.state, 'ready')
        self.assertEqual(c.state, 'ready',
            'already-ready row must not change')
        self.assertEqual(d.state, 'published',
            'published row must be untouched')
        self.assertEqual(action['type'], 'ir.actions.client')
        # 2 flipped, 2 skipped
        self.assertIn('2 marked ready', action['params']['message'])
        self.assertIn('2 skipped', action['params']['message'])
        self.assertEqual(action['params']['type'], 'warning',
            'skipped count > 0 → warning notification')

    def test_mark_ready_all_draft_returns_success(self):
        a = self._make('draft', 'a')
        b = self._make('draft', 'b')
        action = (a | b).action_bulk_mark_ready()
        self.assertEqual(action['params']['type'], 'success')


@tagged('post_install', '-at_install')
class TestBulkResetToDraft(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.tmpl = cls.env['product.template'].create({
            'name': 'RESET Tmpl', 'list_price': 1.0,
        })

    def _make(self, state, shop='shop1'):
        return self.Listing.sudo().create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'shop_ref': shop,
            'state': state,
        })

    def test_reset_to_draft_flips_ready_and_error_only(self):
        a = self._make('ready', 'a')
        b = self._make('error', 'b')
        c = self._make('draft', 'c')
        d = self._make('published', 'd')
        action = (a | b | c | d).action_bulk_reset_to_draft()
        self.assertEqual(a.state, 'draft')
        self.assertEqual(b.state, 'draft')
        self.assertEqual(c.state, 'draft', 'already-draft unchanged')
        self.assertEqual(d.state, 'published',
            'published row must NOT be reset by Marketing bulk-action')
        self.assertIn('2 reset', action['params']['message'])
        self.assertIn('2 skipped', action['params']['message'])
