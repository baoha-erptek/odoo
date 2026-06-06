"""
Phase 2 ORM Unit Tests for P-ENH-ESTY-195: Listing Currency Display.

These tests verify business logic through the Odoo API:
- Computed field display_price_in_shop_currency with currency conversion math
- Soft-fail semantics: 0.0 + WARNING when shop/currency/rate is missing
- Computed field display_currency_id mirrors shop's listing currency
- Cron method _cron_refresh_currency_rates() skeleton with provider switching
- Migration backfill of etsy_shop_id from shop_ref name-lookup

RED: These tests FAIL when Phase 3 has not:
- Declared etsy_shop_id M2O field on multichannel.listing
- Declared display_price_in_shop_currency computed field with SOFT-FAIL logic
- Declared display_currency_id computed field
- Implemented _cron_refresh_currency_rates() method on etsy.shop
- Created migration _19_0_3_8_0/post_migrate.py with backfill logic

Test fixture gotchas (from memory feedback_odoo19_test_gotchas):
- Odoo 19 assertLogs requires level='WARNING' not 'INFO' (item 148)
- Pre-existing res.currency.rate rows may bleed across tests; explicit delete per test
- assertRaises((E1, E2)) tuple breaks — use single exception (item 140)
- Don't depend on demo data — build minimal fresh fixtures in setUp
"""

import logging

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.migrations._19_0_3_8_0.post_migrate import (
    post_migrate as _backfill_etsy_shop_id,
)

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPEnhEsty195Phase2ORM(TransactionCase):
    """Phase 2: ORM behavioral tests for currency display and conversion."""

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Activate or create VND currency (ISO 4217 always ships in base)
        vnd = cls.env.ref('base.VND')
        if not vnd.active:
            vnd.write({'active': True})
        cls.vnd = vnd

        # Get USD (already active in base)
        cls.usd = cls.env.ref('base.USD')

        # Get the company
        cls.company = cls.env.company

    def setUp(self):
        """Per-test setup: clean currency rates before each test."""
        super().setUp()
        # Delete any stale VND→USD rates from prior tests to avoid bleed
        self.env['res.currency.rate'].search([
            ('currency_id', '=', self.vnd.id),
            ('company_id', '=', self.company.id),
        ]).unlink()

    def _create_etsy_shop(self, name='Test Shop', listing_currency_id=None, **kwargs):
        """Factory: create a minimal etsy.shop."""
        vals = {
            'name': name,
        }
        if listing_currency_id:
            vals['listing_currency_id'] = listing_currency_id
        vals.update(kwargs)
        return self.env['etsy.shop'].create(vals)

    def _create_multichannel_listing(self, product_tmpl=None, etsy_shop_id=None, shop_ref=None, **kwargs):
        """Factory: create a minimal multichannel.listing."""
        if not product_tmpl:
            # Create a minimal product template with list_price
            product_tmpl = self.env['product.template'].create({
                'name': 'Test Product',
                'list_price': 19.99,
                'type': 'consu',
            })
        vals = {
            'product_tmpl_id': product_tmpl.id,
            'title': product_tmpl.name,
            'channel_id': self._get_or_create_test_channel().id,
        }
        if etsy_shop_id:
            vals['etsy_shop_id'] = etsy_shop_id
        if shop_ref:
            vals['shop_ref'] = shop_ref
        vals.update(kwargs)
        return self.env['multichannel.listing'].create(vals)

    def _get_or_create_test_channel(self):
        """Factory: return the seeded Etsy sales-channel from mhc data."""
        return self.env.ref('multichannel_hub_core.channel_etsy')

    def test_display_price_computes_for_vnd_shop(self):
        """Test conversion: USD 19.99 @ rate 25400 → VND 507,746.

        Spec US1: Create a shop with listing_currency_id=VND, a product with
        list_price USD 19.99, and a listing linked to that shop. The
        display_price_in_shop_currency must return the converted amount.

        RED: Fails when display_price_in_shop_currency is not declared or
        conversion logic is not implemented.
        """
        # Seed currency rate USD→VND = 25400 at today's date
        today = fields.Date.context_today(self.env.user)
        self.env['res.currency.rate'].create({
            'name': today,
            'rate': 25400.0,  # 1 USD = 25400 VND
            'currency_id': self.vnd.id,
            'company_id': self.company.id,
        })

        # Create shop with VND listing currency
        shop = self._create_etsy_shop('VND Shop', listing_currency_id=self.vnd.id)

        # Create product with list_price 19.99 USD
        product = self.env['product.template'].create({
            'name': 'USD Product',
            'list_price': 19.99,
            'type': 'consu',
        })

        # Create listing linked to shop
        listing = self._create_multichannel_listing(
            product_tmpl=product,
            etsy_shop_id=shop.id,
        )

        # Expected: 19.99 USD * 25400 VND/USD = 507,746.00 VND
        expected = 19.99 * 25400.0  # = 507,746.0
        actual = listing.display_price_in_shop_currency

        self.assertAlmostEqual(
            actual, expected, delta=1.0,
            msg=f"display_price_in_shop_currency should be {expected}, got {actual}",
        )

    def test_display_price_zero_when_no_shop(self):
        """Test SOFT-FAIL: etsy_shop_id=False → 0.0 + WARNING.

        Spec US3: When listing.etsy_shop_id is NULL, the computed field
        returns 0.0 and logs WARNING exactly once per (listing, transaction).
        The form must load gracefully, not crash.

        RED: Fails when computed field not declared or SOFT-FAIL logic absent.
        """
        # Create listing with no shop
        product = self.env['product.template'].create({
            'name': 'Product No Shop',
            'list_price': 100.0,
            'type': 'consu',
        })
        listing = self._create_multichannel_listing(
            product_tmpl=product,
            etsy_shop_id=False,
        )

        # Assert WARNING logged and price is 0.0
        with self.assertLogs(level='WARNING') as cm:
            price = listing.display_price_in_shop_currency

        self.assertEqual(price, 0.0)
        self.assertTrue(
            any('shop' in m.lower() or 'etsy_shop_id' in m.lower() for m in cm.output),
            f"WARNING must mention shop or etsy_shop_id. Got: {cm.output}",
        )

    def test_display_price_zero_when_currency_unset(self):
        """Test SOFT-FAIL: shop exists but listing_currency_id=False → 0.0 + WARNING.

        Spec US3: Shop is configured but its listing_currency_id is NULL.
        Computed field returns 0.0 and logs WARNING.

        RED: Fails when SOFT-FAIL logic doesn't check currency_id.
        """
        # Create shop WITHOUT listing currency
        shop = self._create_etsy_shop('No Currency Shop', listing_currency_id=False)

        product = self.env['product.template'].create({
            'name': 'Product Currency Test',
            'list_price': 100.0,
            'type': 'consu',
        })
        listing = self._create_multichannel_listing(
            product_tmpl=product,
            etsy_shop_id=shop.id,
        )

        # Assert WARNING and 0.0
        with self.assertLogs(level='WARNING') as cm:
            price = listing.display_price_in_shop_currency

        self.assertEqual(price, 0.0)
        self.assertTrue(
            any('currency' in m.lower() or 'shop' in m.lower() for m in cm.output),
            f"WARNING must mention currency or shop. Got: {cm.output}",
        )

    def test_display_price_handles_missing_rate(self):
        """Test SOFT-FAIL: shop + currency set but res.currency.rate missing → 0.0 + WARNING.

        Spec US3: When the conversion rate for today does not exist, the field
        returns 0.0 and logs WARNING. No crash on missing rate (different from
        publisher's hard-fail behavior).

        RED: Fails when SOFT-FAIL logic doesn't catch missing rate exception.
        """
        # Create shop with VND currency but NO rate seeded
        shop = self._create_etsy_shop('VND Shop No Rate', listing_currency_id=self.vnd.id)

        # Verify no rate exists
        self.env['res.currency.rate'].search([
            ('currency_id', '=', self.vnd.id),
            ('company_id', '=', self.company.id),
        ]).unlink()

        product = self.env['product.template'].create({
            'name': 'Product Rate Test',
            'list_price': 100.0,
            'type': 'consu',
        })
        listing = self._create_multichannel_listing(
            product_tmpl=product,
            etsy_shop_id=shop.id,
        )

        # Assert WARNING and 0.0
        with self.assertLogs(level='WARNING') as cm:
            price = listing.display_price_in_shop_currency

        self.assertEqual(price, 0.0)
        self.assertTrue(
            any('rate' in m.lower() or 'currency' in m.lower() for m in cm.output),
            f"WARNING must mention rate or currency. Got: {cm.output}",
        )

    def test_display_currency_id_matches_shop(self):
        """Test computed field display_currency_id returns shop's listing_currency_id.

        Spec US1 §5: display_currency_id is a sibling non-stored computed field
        that returns etsy_shop_id.listing_currency_id or False. This drives the
        Monetary widget's currency display.

        RED: Fails when display_currency_id is not declared.
        """
        # Shop with VND
        shop = self._create_etsy_shop('Currency Match Shop', listing_currency_id=self.vnd.id)

        product = self.env['product.template'].create({
            'name': 'Currency Match',
            'list_price': 100.0,
            'type': 'consu',
        })
        listing = self._create_multichannel_listing(
            product_tmpl=product,
            etsy_shop_id=shop.id,
        )

        # Assert display_currency_id == shop's currency
        self.assertEqual(listing.display_currency_id, self.vnd)

        # When shop is unset, display_currency_id is False
        listing.write({'etsy_shop_id': False})
        self.assertFalse(listing.display_currency_id)

    def test_cron_skeleton_manual_provider_logs_warning(self):
        """Test cron method logs WARNING for manual provider (default).

        Spec US2: _cron_refresh_currency_rates() checks ir.config_parameter
        'etsy_integration.currency_rate_provider'. When 'manual' (the default),
        logs WARNING and returns without writing any rates.

        RED: Fails when the cron method is not declared or doesn't log WARNING.
        """
        # Verify default is 'manual'
        val = self.env['ir.config_parameter'].sudo().get_param(
            'etsy_integration.currency_rate_provider', default='manual',
        )
        self.assertEqual(val, 'manual')

        # Count rates before cron
        rate_count_before = self.env['res.currency.rate'].search_count([])

        # Call cron, assert WARNING
        with self.assertLogs(level='WARNING') as cm:
            self.env['etsy.shop']._cron_refresh_currency_rates()

        # Check WARNING mentions manual provider
        self.assertTrue(
            any('manual' in m.lower() for m in cm.output),
            f"WARNING must mention 'manual'. Got: {cm.output}",
        )

        # Verify no rates were written
        rate_count_after = self.env['res.currency.rate'].search_count([])
        self.assertEqual(rate_count_before, rate_count_after, "Cron must not write rates for manual provider")

    def test_cron_skeleton_unknown_provider_warns(self):
        """Test cron with unknown provider logs WARNING and doesn't crash.

        Spec US2: When ir.config_parameter is set to a value like 'ecb' (not yet
        implemented), cron logs WARNING and returns. Must not raise or crash.

        RED: Fails when cron doesn't gracefully handle unknown providers.
        """
        # Set provider to 'ecb' (not implemented)
        self.env['ir.config_parameter'].sudo().set_param(
            'etsy_integration.currency_rate_provider', 'ecb',
        )

        try:
            # Cron must not raise
            with self.assertLogs(level='WARNING') as cm:
                self.env['etsy.shop']._cron_refresh_currency_rates()

            # Check WARNING logged (placeholder message about not implemented)
            self.assertTrue(
                any('provider' in m.lower() or 'not' in m.lower() for m in cm.output),
                f"WARNING must mention provider or implementation status. Got: {cm.output}",
            )
        finally:
            # Reset to default
            self.env['ir.config_parameter'].sudo().set_param(
                'etsy_integration.currency_rate_provider', 'manual',
            )

    def test_etsy_shop_id_backfilled_from_shop_ref(self):
        """Test migration backfill of etsy_shop_id from shop_ref name-lookup.

        Spec §7 Migration: When a listing has shop_ref='SomeShopName' but
        etsy_shop_id=NULL, the migration creates the FK by looking up the shop
        by name. After migration, listing.etsy_shop_id points to that shop.

        RED: Fails when the migration module/function doesn't exist or import fails.
        This is expected RED — the migration package is not yet created in Phase 3.
        Document this in the test so Phase 3 doesn't treat the ImportError as a
        test bug.

        Test strategy: Attempt to import the migration; if ImportError, that's
        the expected RED signal. In Phase 3 GREEN, the import will succeed and
        the migration logic will execute.
        """
        # Create a shop with a known name
        shop = self._create_etsy_shop('JaHandmadeArt')

        # Create a listing with shop_ref but no etsy_shop_id
        product = self.env['product.template'].create({
            'name': 'Backfill Test',
            'list_price': 100.0,
            'type': 'consu',
        })
        listing = self._create_multichannel_listing(
            product_tmpl=product,
            etsy_shop_id=False,
            shop_ref='JaHandmadeArt',
        )

        # Before migration, etsy_shop_id should be NULL
        self.assertFalse(listing.etsy_shop_id)

        # Run the testable backfill entry point directly (the dotted-dir
        # shim is just an Odoo-discovery wrapper around this function).
        _backfill_etsy_shop_id(self.env.cr, self.env)

        # Reload listing from DB
        listing.invalidate_recordset()

        # After migration, etsy_shop_id should match the shop
        self.assertEqual(listing.etsy_shop_id, shop)
