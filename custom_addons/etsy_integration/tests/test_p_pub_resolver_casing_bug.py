"""
Phase 2 ORM Unit Tests for P-PUB-RESOLVER-CASING-BUG: shop_name casing mismatch.

Tests verify the _resolve_listing_intent method correctly matches shop names
across casing boundaries (e.g., CamelCase etsy.shop.name to lowercase
multichannel.listing.shop_ref).

Scope:
1. CamelCase shop.name resolves to lowercase shop_ref (headline assertion)
2. Exact match still works (regression guard for existing happy path)
3. Literal underscore in shop.name is not treated as SQL wildcard
4. Literal percent in shop.name is not treated as SQL wildcard
5. Empty shop.name falls through to NULL shop_ref tier
6. No match falls through to template-level defaults (empty recordset)

RED: These tests FAIL because the production code uses exact '='
match on line 515 of etsy_listing_publisher.py instead of '=ilike'
with proper escape of % and _ literals.

Expected failure pattern:
  AssertionError: false != true
  (resolver returns empty recordset when CamelCase ≠ lowercase)
"""

import logging

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPPubResolverCasingBug(TransactionCase):
    """Phase 2 ORM: Verify _resolve_listing_intent handles casing correctly.

    RED reason: _resolve_listing_intent uses exact '=' match on shop_ref,
    which fails to match CamelCase etsy.shop.name to lowercase shop_ref.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        """Set up fixtures for each test."""
        super().setUp()

        # Get or create the Etsy channel
        self.channel = self.env.ref(
            'multichannel_hub_core.channel_etsy',
            raise_if_not_found=False,
        )
        if not self.channel:
            self.channel = self.env['multichannel.sales.channel'].create({
                'name': 'Etsy',
                'code': 'etsy',
            })

        # Create a product template for testing
        self.template = self.env['product.template'].create({
            'name': 'Test Product',
            'type': 'consu',
            'is_storable': True,
        })

    def _create_shop(self, name):
        """Factory: create an etsy.shop with given name."""
        return self.env['etsy.shop'].create({
            'name': name,
        })

    def _create_listing(self, template, channel, shop_ref):
        """Factory: create a multichannel.listing with given scope.

        shop_ref can be a string or False/None.
        """
        return self.env['multichannel.listing'].create({
            'product_tmpl_id': template.id,
            'channel_id': channel.id,
            'shop_ref': shop_ref,
            'title': 'Test Listing',
        })

    def test_camelcase_shop_name_resolves_lowercase_shop_ref(self):
        """Test that CamelCase shop.name matches lowercase shop_ref.

        This is the headline assertion. Etsy's shop name is 'JaHandmadeArt'
        (CamelCase); the listing intent row has shop_ref='jahandmadeart'
        (lowercase URL slug). The resolver must match them.

        FAILS with current code: exact '=' match fails because
        'JaHandmadeArt' != 'jahandmadeart'.
        """
        shop = self._create_shop('JaHandmadeArt')
        listing = self._create_listing(
            self.template,
            self.channel,
            'jahandmadeart'
        )

        # Import the publisher here to avoid import-time side effects
        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        publisher = EtsyListingPublisher(self.env)
        result = publisher._resolve_listing_intent(self.template, shop)

        self.assertTrue(
            result,
            msg='Resolver should find listing with lowercase shop_ref '
                'when shop.name is CamelCase'
        )
        self.assertEqual(
            result.id,
            listing.id,
            msg='Resolver should return the specific listing that matches '
                'shop_ref, not fall through to template tier'
        )

    def test_exact_match_still_resolves(self):
        """Test that exact shop_ref match still works (regression guard).

        Both shop.name and shop_ref are identical lowercase strings.
        The resolver must return this listing.

        This ensures the fix doesn't break the existing happy path.
        """
        shop = self._create_shop('alreadylower')
        listing = self._create_listing(
            self.template,
            self.channel,
            'alreadylower'
        )

        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        publisher = EtsyListingPublisher(self.env)
        result = publisher._resolve_listing_intent(self.template, shop)

        self.assertTrue(
            result,
            msg='Exact match should still resolve'
        )
        self.assertEqual(
            result.id,
            listing.id,
            msg='Resolver should return the exact-match listing'
        )

    def test_literal_underscore_in_shop_name_does_not_wildcard(self):
        """Test that literal underscore in shop_ref is not treated as wildcard.

        Shop.name='ab_cd' (literal underscore). A listing with shop_ref='abXcd'
        (where X is any single char) exists. The resolver must NOT match it.

        If the fix uses '=ilike' without proper escape, the underscore becomes
        a wildcard and matches incorrectly. With proper escape, it treats '_'
        as a literal character.

        Expected: no match, falls through to NULL shop_ref tier (which doesn't
        exist in this test → empty recordset).
        """
        shop = self._create_shop('ab_cd')

        # Create two listings: one with matching shop_ref, one with wildcard pattern
        listing_null = self._create_listing(
            self.template,
            self.channel,
            False  # NULL shop_ref tier
        )
        listing_x = self._create_listing(
            self.template,
            self.channel,
            'abXcd'  # Would match if _ is wildcard
        )

        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        publisher = EtsyListingPublisher(self.env)
        result = publisher._resolve_listing_intent(self.template, shop)

        # The resolver should return the NULL-shop_ref listing, not the 'abXcd' one
        self.assertTrue(
            result,
            msg='Resolver should fall through to NULL shop_ref tier'
        )
        self.assertEqual(
            result.id,
            listing_null.id,
            msg='Resolver must NOT match underscore as wildcard; '
                'must skip the abXcd listing and return NULL-fallback'
        )

    def test_literal_percent_in_shop_name_does_not_wildcard(self):
        """Test that literal percent in shop_ref is not treated as wildcard.

        Shop.name='ab%cd' (literal percent). A listing with shop_ref='abZZZZcd'
        exists. The resolver must NOT match it.

        If the fix uses '=ilike' without proper escape, % becomes a wildcard
        (match zero or more of any char) and matches incorrectly. With proper
        escape, % is literal.

        Expected: no match, falls through to NULL tier.
        """
        shop = self._create_shop('ab%cd')

        # Create NULL-fallback and a "would match if % is wildcard" listing
        listing_null = self._create_listing(
            self.template,
            self.channel,
            False  # NULL shop_ref tier
        )
        listing_z = self._create_listing(
            self.template,
            self.channel,
            'abZZZZcd'  # Would match if % is wildcard
        )

        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        publisher = EtsyListingPublisher(self.env)
        result = publisher._resolve_listing_intent(self.template, shop)

        self.assertTrue(
            result,
            msg='Resolver should fall through to NULL shop_ref tier'
        )
        self.assertEqual(
            result.id,
            listing_null.id,
            msg='Resolver must NOT match percent as wildcard; '
                'must skip the abZZZZcd listing and return NULL-fallback'
        )

    def test_empty_shop_name_falls_through_to_null_shop_ref(self):
        """Test that empty shop.name falls through to NULL shop_ref tier.

        When shop.name is empty (or whitespace-only), the resolver should
        skip the per-shop tier and return a listing with shop_ref=FALSE
        or shop_ref=''.

        This preserves the existing behavior on lines 519-523 of the method.
        """
        shop = self._create_shop('')

        # Create a NULL-fallback listing
        listing_null = self._create_listing(
            self.template,
            self.channel,
            False
        )

        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        publisher = EtsyListingPublisher(self.env)
        result = publisher._resolve_listing_intent(self.template, shop)

        self.assertTrue(
            result,
            msg='Empty shop.name should fall through to NULL shop_ref tier'
        )
        self.assertEqual(
            result.id,
            listing_null.id,
            msg='Resolver should return the NULL-fallback listing'
        )

    def test_no_match_falls_through_to_template_tier(self):
        """Test that no per-shop match and no NULL-fallback returns empty.

        When:
        1. shop.name doesn't match any listing.shop_ref
        2. No listing with shop_ref=NULL or shop_ref=''

        The resolver returns an empty recordset. The caller then uses
        product.template fields as defaults.

        This verifies that the resolver doesn't create a false match when
        data doesn't exist.
        """
        shop = self._create_shop('someshop')

        # Do NOT create any listings for this template/channel combo.
        # This forces the resolver to return empty.

        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        publisher = EtsyListingPublisher(self.env)
        result = publisher._resolve_listing_intent(self.template, shop)

        self.assertFalse(
            result,
            msg='Resolver should return empty recordset when no '
                'listing matches the template/channel/shop scope'
        )
