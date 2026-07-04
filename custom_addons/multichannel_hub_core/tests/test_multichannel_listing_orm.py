"""Phase 2 ORM tests for `multichannel.listing` (P-LIST-MODEL).

Exercises create/read/write, the UNIQUE composite, the resolver helpers
(title / description / image fallback chain), and the backfill migration
helper. ACL fences are covered by Phase 1 (CSV truth) — runtime user-
context tests in another slice if the team wants explicit isolation.
"""

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestMultichannelListingCRUD(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.tmpl = cls.env['product.template'].create({
            'name': 'P-LIST-MODEL Test Tray',
            'list_price': 12.99,
        })
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def test_create_sets_default_state_draft(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'shop_ref': 'unit-test',
        })
        self.assertEqual(listing.state, 'draft')
        self.assertEqual(listing.display_name,
                         'P-LIST-MODEL Test Tray @ etsy/unit-test')

    def test_unique_composite_enforced(self):
        self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'shop_ref': 'unique-shop',
        })
        with self.assertRaises(IntegrityError), \
             mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Listing.create({
                    'product_tmpl_id': self.tmpl.id,
                    'channel_id': self.channel.id,
                    'shop_ref': 'unique-shop',
                })

    def test_null_shop_ref_still_unique_per_pair(self):
        self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
        })
        with self.assertRaises(IntegrityError), \
             mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Listing.create({
                    'product_tmpl_id': self.tmpl.id,
                    'channel_id': self.channel.id,
                })


@tagged('post_install', '-at_install')
class TestMultichannelListingResolvers(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.tmpl = cls.env['product.template'].create({
            'name': 'P-LIST-MODEL Resolver Tmpl',
            'description_sale': 'Template description',
            'list_price': 5.0,
        })
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def test_resolve_title_override(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'title': 'Marketing override',
        })
        self.assertEqual(listing.resolve_title(), 'Marketing override')

    def test_resolve_title_fallback(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
        })
        self.assertEqual(listing.resolve_title(),
                         'P-LIST-MODEL Resolver Tmpl')

    def test_resolve_description_override(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'description': 'Marketing copy',
        })
        self.assertEqual(listing.resolve_description(), 'Marketing copy')

    def test_resolve_description_fallback_to_template(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
        })
        self.assertEqual(listing.resolve_description(),
                         'Template description')

    def test_resolve_image_override(self):
        import base64
        # Minimal 1×1 PNG (red pixel) — valid PIL input.
        png = base64.b64encode(bytes.fromhex(
            '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
            '890000000d49444154789c63f8cfc0f01f00050501020df5d3e3'
            '0000000049454e44ae426082'
        ))
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'image_1920': png,
        })
        self.assertTrue(listing.resolve_image_1920())


@tagged('post_install', '-at_install')
class TestMultichannelListingBackfill(TransactionCase):

    def test_backfill_creates_one_row_per_status_pair(self):
        from odoo.addons.multichannel_hub_core.migrations._19_0_1_0_65 import (
            backfill_listings,
        )
        tmpl = self.env['product.template'].create({
            'name': 'Backfill Tmpl 1',
            'list_price': 1.0,
        })
        channel = self.env.ref('multichannel_hub_core.channel_etsy')
        self.env['product.channel.status'].sudo().create({
            'product_tmpl_id': tmpl.id,
            'channel_id': channel.id,
            'state': 'draft',
        })
        # Clear any pre-existing listing rows the test DB might carry.
        baseline = self.env['multichannel.listing'].sudo().search_count([
            ('product_tmpl_id', '=', tmpl.id),
        ])
        self.assertEqual(baseline, 0)

        created, skipped = backfill_listings(self.env)
        self.assertGreaterEqual(created, 1)

        stub = self.env['multichannel.listing'].sudo().search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', channel.id),
        ], limit=1)
        self.assertTrue(stub)
        self.assertEqual(stub.state, 'draft')
        self.assertFalse(stub.title, 'backfill leaves overrides null')
        self.assertFalse(stub.description)

    def test_backfill_idempotent(self):
        """Second invocation must not create duplicates."""
        from odoo.addons.multichannel_hub_core.migrations._19_0_1_0_65 import (
            backfill_listings,
        )
        tmpl = self.env['product.template'].create({
            'name': 'Backfill Idempotent Tmpl',
            'list_price': 1.0,
        })
        channel = self.env.ref('multichannel_hub_core.channel_etsy')
        self.env['product.channel.status'].sudo().create({
            'product_tmpl_id': tmpl.id,
            'channel_id': channel.id,
            'state': 'draft',
        })
        backfill_listings(self.env)
        before = self.env['multichannel.listing'].sudo().search_count([
            ('product_tmpl_id', '=', tmpl.id),
        ])
        backfill_listings(self.env)
        after = self.env['multichannel.listing'].sudo().search_count([
            ('product_tmpl_id', '=', tmpl.id),
        ])
        self.assertEqual(before, after,
            'backfill must be idempotent — second run = same count')
