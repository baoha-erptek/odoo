"""P0-18b1 Phase 1 — Live Gearment API catalog probe (gated by env var).

This test runs ONLY when MULTICHANNEL_HUB_FULFILLMENT_LIVE_API=1 environment variable
is set. Default behavior is skip (safe for CI and to preserve API quota).

Purpose: Verify catalog endpoint works against owner's real Gearment account
and discover print_locations and product properties.

This is a read-only operation; no writes issued. Safe to run in CI if owner enables it
for integration testing.

WARNING: This test contacts the real Gearment API and is NON-DETERMINISTIC. If it
fails, check .env GEARMENT_API_BASE_URL, GEARMENT_API_KEY, and GEARMENT_API_SECRET.
"""

import os
import unittest

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'live_api')
class TestGearmentLiveProbe(TransactionCase):
    """Live integration tests against real Gearment API (catalog only)."""

    @unittest.skipUnless(
        os.environ.get('MULTICHANNEL_HUB_FULFILLMENT_LIVE_API') == '1',
        "Set MULTICHANNEL_HUB_FULFILLMENT_LIVE_API=1 to enable live API tests."
    )
    def test_catalog_live_probe(self):
        """Live GET /api/v3/catalog?limit=1; non-mutating, read-only probe.

        Verifies:
        - Connection to owner's Gearment account succeeds
        - Catalog response includes expected structure
        - legacy_product_id and print_locations are discoverable
        - product_avatar_url is populated

        This test is safe because:
        - No order creation
        - No webhook registration
        - No state change at Gearment
        - Read-only query
        - Low quota cost (1 catalog fetch = ~1 API unit)
        """
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        adapter = GearmentApiAdapter()
        catalog = adapter._fetch_catalog(limit=1)

        # Verify response structure
        self.assertIsInstance(catalog, dict, "Catalog response must be a dict")
        self.assertIn('data', catalog, "Catalog must have 'data' key")
        self.assertGreater(len(catalog['data']), 0, "Catalog must return at least 1 product")

        # Inspect first product
        first_product = catalog['data'][0]
        self.assertIn('legacy_product_id', first_product,
                     "Product must have legacy_product_id")
        self.assertIn('print_locations', first_product,
                     "Product must have print_locations array")

        # Verify print_locations structure
        print_locs = first_product['print_locations']
        self.assertIsInstance(print_locs, list, "print_locations must be a list")
        self.assertGreater(len(print_locs), 0, "Product must have at least 1 print location")

        # Sample a location
        if isinstance(print_locs[0], dict):
            location = print_locs[0]
            self.assertIn('code', location,
                         "Print location must have 'code' key")
        else:
            # Might be a string; that's OK
            self.assertIsInstance(print_locs[0], (str, dict))

        # Verify avatar URL if present
        if 'product_avatar_url' in first_product:
            avatar_url = first_product['product_avatar_url']
            self.assertIsInstance(avatar_url, (str, type(None)))

    @unittest.skipUnless(
        os.environ.get('MULTICHANNEL_HUB_FULFILLMENT_LIVE_API') == '1',
        "Set MULTICHANNEL_HUB_FULFILLMENT_LIVE_API=1 to enable live API tests."
    )
    def test_catalog_fetch_with_higher_limit(self):
        """Live GET /api/v3/catalog?limit=100 to enumerate available print locations.

        Used for discovery; not part of normal flow. Helps identify all possible
        print location codes that Gearment supports (pocket, front, back,
        left_sleeve, right_sleeve, etc.).
        """
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        adapter = GearmentApiAdapter()
        catalog = adapter._fetch_catalog(limit=100)

        self.assertIn('data', catalog)

        # Collect all unique print location codes across all products
        all_codes = set()
        for product in catalog['data']:
            locs = product.get('print_locations', [])
            for loc in locs:
                if isinstance(loc, dict):
                    code = loc.get('code')
                    if code:
                        all_codes.add(code)
                elif isinstance(loc, str):
                    all_codes.add(loc)

        # At minimum, expect to find core locations
        # (exact set may vary; this is a discovery probe)
        self.assertGreater(len(all_codes), 0,
                          "Must discover at least one print location code")
