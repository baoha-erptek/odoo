"""Phase 2 ORM tests for P-LIST-PUBLISH-STATE-SYNC.

Tests the synchronization of multichannel.listing.state during the
EtsyListingPublisher.run() success and error paths. Currently MUST FAIL
because the publisher writes only to product.channel.status, not to
multichannel.listing.state.

Covers:
- publish_success_flips_listing_state_to_published: single shop, single listing
- publish_error_flips_listing_state_to_error: error path capture
- publish_does_not_touch_other_shop_rows: only shop-specific row updated
- publish_does_not_touch_null_shop_row: shop-specific precedence
- publish_idempotent_on_already_published: state stays consistent
- publish_no_listing_row_does_not_raise: graceful when no listing row exists
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPListPublishStateSyncPhase2Orm(TransactionCase):
    """Phase 2 ORM tests for listing.state synchronization during publish."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)

        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        cls.Listing = cls.env['multichannel.listing']
        cls.Shop = cls.env['etsy.shop']

        ChannelAll = cls.env['multichannel.sales.channel'].with_context(
            active_test=False
        )
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)

    def _make_shop(self, name='TestShop', shop_id='99999999'):
        """Factory method to create an etsy.shop with required defaults."""
        return self.Shop.create({
            'name': name,
            'etsy_api_shop_id': shop_id,
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
            'default_taxonomy_id': 1111,
            'default_shipping_profile_id': 2222,
            'default_return_policy_id': 3333,
            'default_who_made': 'i_did',
            'default_when_made': 'made_to_order',
            'default_is_supply': False,
        })

    def _make_product(self, name='Test Product', code='TST-001'):
        """Factory method to create a product.template."""
        return self.Template.create({
            'name': name,
            'default_code': code,
            'list_price': 49.99,
            'description_sale': 'Test product for publisher.',
            'type': 'consu',
            'is_storable': True,
        })

    def _make_listing(self, tmpl, shop_ref=None, state='draft'):
        """Factory method to create a multichannel.listing.

        Args:
            tmpl: product.template instance
            shop_ref: shop identifier (e.g. 'testshop'), or None for template-wide
            state: initial state ('draft', 'ready', 'published', 'error')
        """
        return self.Listing.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy_channel.id,
            'shop_ref': shop_ref,
            'state': state,
        })

    def _mock_publisher_run(self, shop, tmpl, raise_exception=None):
        """Run publisher.run() with mocked HTTP layer.

        Mocks EtsyApiClient methods to bypass real network calls.
        All steps (create_draft, upload_images, push_inventory, etc.) are
        mocked to succeed unless raise_exception is provided.

        Exception is propagated to the caller (do NOT wrap with
        ``self.assertRaises`` — Odoo's ``_assertRaises`` opens a savepoint
        that rolls back any DB writes performed inside the publisher's
        ``except`` block, which is exactly what this slice asserts on).
        Callers expecting an exception should use a plain ``try``/``except``.
        """
        publisher = EtsyListingPublisher(self.env)

        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value

            # Mock successful responses for all steps
            client.post.return_value = {'listing_id': 12345, 'state': 'draft'}
            client.put.return_value = {'listing_id': 12345}
            client.patch.return_value = {'listing_id': 12345, 'state': 'active'}

            # If raise_exception is specified, make one of the calls raise it
            if raise_exception:
                client.post.side_effect = raise_exception

            return publisher.run(tmpl, shop)

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_publish_success_flips_listing_state_to_published(self):
        """Test that publish success updates multichannel.listing.state to 'published'."""
        shop = self._make_shop(name='SingleShop', shop_id='11111111')
        tmpl = self._make_product(name='Test Product A')
        listing = self._make_listing(tmpl, shop_ref='singleshop', state='draft')

        # Verify initial state
        self.assertEqual(listing.state, 'draft',
                        "Listing should start in draft")

        # Run publisher
        self._mock_publisher_run(shop, tmpl)

        # Reload listing from DB
        listing = self.Listing.browse(listing.id)

        # ASSERTION: listing.state must be 'published' after successful publish
        self.assertEqual(listing.state, 'published',
                        "listing.state should be updated to 'published' "
                        "after publisher.run() succeeds")

    def test_publish_error_flips_listing_state_to_error(self):
        """Test that publish error updates multichannel.listing.state to 'error'."""
        shop = self._make_shop(name='ErrorShop', shop_id='22222222')
        tmpl = self._make_product(name='Test Product B')
        listing = self._make_listing(tmpl, shop_ref='errorshop', state='draft')

        # Verify initial state
        self.assertEqual(listing.state, 'draft',
                        "Listing should start in draft")

        # Run publisher with a failing step. Use try/except (NOT assertRaises)
        # so the savepoint that wraps assertRaises does not roll back the
        # writeback we are asserting on.
        error = UserError("Simulated publish failure")
        with self.assertLogs(level='WARNING'):  # silence the publisher's warn
            try:
                self._mock_publisher_run(shop, tmpl, raise_exception=error)
            except UserError:
                pass
            else:
                self.fail("publisher.run() should have raised UserError")

        # Reload listing from DB
        listing = self.Listing.browse(listing.id)

        # ASSERTION: listing.state must be 'error' after publisher fails
        self.assertEqual(listing.state, 'error',
                        "listing.state should be updated to 'error' "
                        "when publisher.run() raises an exception")

    def test_publish_does_not_touch_other_shop_rows(self):
        """Test that publishing to one shop does not modify listings for other shops."""
        # Create two shops
        shop1 = self._make_shop(name='Shop1', shop_id='33333333')
        shop2 = self._make_shop(name='Shop2', shop_id='44444444')

        # Create one product
        tmpl = self._make_product(name='Test Product C')

        # Create listings for both shops
        listing1 = self._make_listing(tmpl, shop_ref='shop1', state='draft')
        listing2 = self._make_listing(tmpl, shop_ref='shop2', state='draft')

        # Verify both start in draft
        self.assertEqual(listing1.state, 'draft')
        self.assertEqual(listing2.state, 'draft')

        # Publish to shop1 only
        self._mock_publisher_run(shop1, tmpl)

        # Reload both from DB
        listing1 = self.Listing.browse(listing1.id)
        listing2 = self.Listing.browse(listing2.id)

        # ASSERTION: only listing1 should change
        self.assertEqual(listing1.state, 'published',
                        "Shop1 listing should be 'published' after publish to shop1")
        self.assertEqual(listing2.state, 'draft',
                        "Shop2 listing should remain 'draft' — not touched by "
                        "publishing to shop1")

    def test_publish_does_not_touch_null_shop_row(self):
        """Test that shop-specific listing is updated, not template-wide (NULL shop) row.

        This is the critical test for the correct resolution logic:
        when both a shop-specific row (shop_ref='shop3') and a template-wide
        row (shop_ref=NULL) exist, publishing updates ONLY the specific one.
        """
        shop3 = self._make_shop(name='Shop3', shop_id='55555555')
        tmpl = self._make_product(name='Test Product D')

        # Create shop-specific listing
        specific = self._make_listing(tmpl, shop_ref='shop3', state='draft')

        # Create template-wide (NULL shop_ref) listing
        template_wide = self._make_listing(tmpl, shop_ref=None, state='draft')

        # Verify both start in draft
        self.assertEqual(specific.state, 'draft')
        self.assertEqual(template_wide.state, 'draft')

        # Publish to shop3
        self._mock_publisher_run(shop3, tmpl)

        # Reload both from DB
        specific = self.Listing.browse(specific.id)
        template_wide = self.Listing.browse(template_wide.id)

        # ASSERTION: only shop-specific row updated
        self.assertEqual(specific.state, 'published',
                        "Shop3-specific listing should be 'published'")
        self.assertEqual(template_wide.state, 'draft',
                        "Template-wide (NULL shop_ref) listing should remain "
                        "'draft' — the publisher must use the shop-specific row only")

    def test_publish_idempotent_on_already_published(self):
        """Test that republishing an already-published listing keeps it published."""
        shop4 = self._make_shop(name='Shop4', shop_id='66666666')
        tmpl = self._make_product(name='Test Product E')

        # Create listing already in 'published' state
        listing = self._make_listing(tmpl, shop_ref='shop4', state='published')

        # Verify initial state
        self.assertEqual(listing.state, 'published')

        # Run publisher again (simulating a re-publish)
        self._mock_publisher_run(shop4, tmpl)

        # Reload from DB
        listing = self.Listing.browse(listing.id)

        # ASSERTION: state should remain 'published'
        self.assertEqual(listing.state, 'published',
                        "Republishing an already-published listing should "
                        "keep state='published'")

    def test_publish_no_listing_row_does_not_raise(self):
        """Test that publisher succeeds gracefully when no multichannel.listing row exists.

        The product.channel.status write still happens; the missing
        multichannel.listing writeback should not cause an exception.
        """
        shop5 = self._make_shop(name='Shop5', shop_id='77777777')
        tmpl = self._make_product(name='Test Product F')

        # Do NOT create any multichannel.listing row for this product

        # Run publisher — should not raise
        try:
            self._mock_publisher_run(shop5, tmpl)
        except Exception as exc:
            self.fail(f"publisher.run() raised {type(exc).__name__}: {exc} "
                     "when no multichannel.listing row exists; should complete "
                     "gracefully")

        # ASSERTION: product.channel.status row exists and is 'published'
        status = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ], limit=1)
        self.assertTrue(status, "status row should exist after publish")
        self.assertEqual(status.state, 'published',
                        "status.state should be 'published' even when no "
                        "multichannel.listing row exists")
