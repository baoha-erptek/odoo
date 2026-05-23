"""Phase 2 ORM tests for P-HUB-BACKFILL (Spec 009 US6).

Verifies:
- Backfill creates product.channel.status for each (template, etsy) pair
  inferred from etsy.listing → etsy.listing.product.product_id chain
- Idempotent (second run is a no-op on existing rows)
- Unmatched variants (product_id NULL) are surfaced separately, NOT silently
  auto-created
- Does NOT overwrite BA-edited x_channel_applicability_ids (only adds if missing)
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestHubBackfillORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['etsy.listing.backfill.wizard']
        cls.Listing = cls.env['etsy.listing']
        cls.ListingProduct = cls.env['etsy.listing.product']
        cls.Template = cls.env['product.template']
        cls.Product = cls.env['product.product']
        cls.Status = cls.env['product.channel.status']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        cls.ba_user = new_test_user(
            cls.env,
            login='hub_backfill_ba',
            groups='multichannel_hub_core.group_ba_user',
        )
        cls.plain_user = new_test_user(
            cls.env,
            login='hub_backfill_plain',
            groups='base.group_user',
        )
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Backfill Test Shop',
            'etsy_api_shop_id': '99999999',
            'sync_mode': 'email_only',
        })

    def _make_matched_listing(self, listing_id='L1', sku='BACKFILL-SKU-1'):
        """Create listing + variant linked to a real product.product."""
        tmpl = self.Template.create({
            'name': 'Backfill Product %s' % sku,
            'default_code': sku,
        })
        # product.product is auto-created for the template; reuse it
        variant = tmpl.product_variant_ids[:1]
        listing = self.Listing.create({
            'shop_id': self.shop.id,
            'etsy_listing_id': listing_id,
            'title': 'L %s' % listing_id,
            'url': 'https://etsy/x/%s' % listing_id,
            'state': 'active',
            'last_modified': '2026-05-23 00:00:00',
        })
        self.ListingProduct.create({
            'listing_id': listing.id,
            'etsy_product_id': '%s-V1' % listing_id,
            'sku': sku,
            'product_id': variant.id,
            'quantity': 10,
        })
        return listing, tmpl

    def _make_unmatched_listing(self, listing_id='L2', sku='UNMATCHED-1'):
        listing = self.Listing.create({
            'shop_id': self.shop.id,
            'etsy_listing_id': listing_id,
            'title': 'L %s' % listing_id,
            'url': 'https://etsy/x/%s' % listing_id,
            'state': 'active',
            'last_modified': '2026-05-23 00:00:00',
        })
        self.ListingProduct.create({
            'listing_id': listing.id,
            'etsy_product_id': '%s-V1' % listing_id,
            'sku': sku,
            'product_id': False,  # unmatched
            'quantity': 10,
        })
        return listing

    # ------------------------------------------------------------------

    def test_backfill_creates_channel_status_for_matched(self):
        listing, tmpl = self._make_matched_listing()
        w = self.Wizard.with_user(self.ba_user).create({'shop_id': self.shop.id})
        w.with_user(self.ba_user).action_backfill()
        statuses = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ])
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses.state, 'published')
        self.assertEqual(statuses.external_ref, listing.etsy_listing_id)

    def test_backfill_adds_etsy_applicability(self):
        listing, tmpl = self._make_matched_listing(sku='APPLI-1')
        w = self.Wizard.with_user(self.ba_user).create({'shop_id': self.shop.id})
        w.with_user(self.ba_user).action_backfill()
        tmpl.invalidate_recordset()
        self.assertIn(self.etsy_channel, tmpl.x_channel_applicability_ids)

    def test_backfill_idempotent(self):
        listing, tmpl = self._make_matched_listing(sku='IDEMPOTENT-1')
        w = self.Wizard.with_user(self.ba_user).create({'shop_id': self.shop.id})
        w.with_user(self.ba_user).action_backfill()
        w2 = self.Wizard.with_user(self.ba_user).create({'shop_id': self.shop.id})
        w2.with_user(self.ba_user).action_backfill()
        statuses = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ])
        self.assertEqual(len(statuses), 1, "second backfill must not duplicate status")

    def test_backfill_does_not_overwrite_ba_edited_applicability(self):
        """If template already has etsy in M2M (manual), keep it; don't clear."""
        listing, tmpl = self._make_matched_listing(sku='BA-EDIT-1')
        tmpl.x_channel_applicability_ids = [(4, self.etsy_channel.id)]
        existing_count = len(tmpl.x_channel_applicability_ids)
        w = self.Wizard.with_user(self.ba_user).create({'shop_id': self.shop.id})
        w.with_user(self.ba_user).action_backfill()
        tmpl.invalidate_recordset()
        self.assertEqual(len(tmpl.x_channel_applicability_ids), existing_count)

    def test_non_ba_user_blocked_by_fr017_gate(self):
        """FR-017 23rd confirmation: non-BA user → AccessError BEFORE any write."""
        listing, tmpl = self._make_matched_listing(sku='FR017-1')
        status_before = self.Status.search_count([])
        w = self.Wizard.with_user(self.plain_user).create({'shop_id': self.shop.id})
        with self.assertRaises(AccessError):
            w.with_user(self.plain_user).action_backfill()
        status_after = self.Status.search_count([])
        self.assertEqual(
            status_before, status_after,
            "non-BA action_backfill must not create any product.channel.status",
        )

    def test_unmatched_variants_reported_not_auto_created(self):
        self._make_unmatched_listing(sku='UNMATCH-X')
        w = self.Wizard.with_user(self.ba_user).create({'shop_id': self.shop.id})
        w.with_user(self.ba_user).action_backfill()
        # No template auto-created for unmatched SKU
        unmatched_tmpl = self.Template.search([('default_code', '=', 'UNMATCH-X')])
        self.assertFalse(unmatched_tmpl, "unmatched SKU must NOT auto-create template")
        # But surfaced in unmatched_count
        self.assertEqual(w.unmatched_count, 1)
        self.assertEqual(w.matched_count, 0)
