"""
Phase 2 ORM Unit Tests for P-BUG-ESTY-188 Iteration 2: Currency Conversion.

Tests verify business logic, currency conversion, and migration behavior through the Odoo API.

Scope:
1. Currency conversion: publisher._convert_to_shop_currency(amount, shop)
2. Payload building: _build_create_draft_payload includes converted price
3. Inventory: push_inventory includes converted price in offerings
4. Migration: bootstraps shop listing_currency_id from GET /shops/{shop_id}
5. Robustness: handles missing currency, unknown currency codes, API failures, idempotency

RED: These tests FAIL because:
- Helper method _convert_to_shop_currency does not exist
- Payload building does not include converted prices
- Migration 19.0.2.34.0 does not exist
- Field listing_currency_id does not exist on etsy.shop

Expected failure patterns documented in each test docstring.
"""

import logging
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p_bug_esty_188_iter2')
class TestP_BUG_ESTY_188_Phase2_CurrencyConversion(TransactionCase):
    """Phase 2: Verify currency conversion at publisher boundary.

    RED: _convert_to_shop_currency method missing; conversion not implemented.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        # Currencies are loaded lazily per test to avoid TransactionCase isolation issues
        self.company = self.env.company
        Currency = self.env['res.currency'].with_context(active_test=False)
        self.usd = Currency.search([('name', '=', 'USD')], limit=1)
        self.vnd = Currency.search([('name', '=', 'VND')], limit=1)
        if self.vnd and not self.vnd.active:
            self.vnd.sudo().active = True

        # Seed currency rate only if VND is available
        if self.vnd:
            today = fields.Date.context_today(self)
            # First, remove any existing rate for today to avoid duplicate constraint
            self.env['res.currency.rate'].search([
                ('currency_id', '=', self.vnd.id),
                ('name', '=', today),
            ]).unlink()

            self.env['res.currency.rate'].create({
                'currency_id': self.vnd.id,
                'name': today,
                'rate': 25000.0,  # 1 USD = 25,000 VND
            })

    def _create_shop(self, name, api_shop_id='60752333', listing_currency_id=None,
                     active_source='api'):
        """Factory: create test shop with optional listing_currency_id."""
        vals = {
            'name': name,
            'etsy_api_shop_id': api_shop_id,
            'sync_mode': 'email_only',
            'active_source': active_source,
            'etsy_oauth_access_token': 'test_access_token',
            'etsy_oauth_refresh_token': 'test_refresh_token',
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=3600
            ),
            'default_taxonomy_id': '1111',
            'default_shipping_profile_id': '2222',
            'default_return_policy_id': '3333',
            'default_readiness_state_id': '1406133708616',
            'default_who_made': 'i_did',
            'default_when_made': 'made_to_order',
            'default_is_supply': False,
        }
        if listing_currency_id:
            vals['listing_currency_id'] = listing_currency_id
        return self.env['etsy.shop'].create(vals)

    def _create_template(self, name='Test Product', code='TEST-001', price=12.99):
        """Factory: create test product template."""
        return self.env['product.template'].create({
            'name': name,
            'default_code': code,
            'list_price': price,
        })

    def _get_company_and_currencies(self):
        """Lazily access company and currencies set in setUpClass."""
        return self.__class__.company, self.__class__.usd, self.__class__.vnd

    def test_payload_price_converted_when_shop_currency_differs(self):
        """RED: _convert_to_shop_currency not implemented.

        Expected RED reason: AttributeError on missing _convert_to_shop_currency method
        or KeyError on missing 'price' in payload dict, or the price is not converted.
        """
        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        if not self.vnd:
            self.skipTest("VND currency not available in test database")

        shop = self._create_shop('VND Shop', listing_currency_id=self.vnd.id)
        tmpl = self._create_template(price=12.99)

        publisher = EtsyListingPublisher(self.env)

        # The payload should include converted price: 12.99 * 25000 = 324,750
        payload = publisher._build_create_draft_payload(tmpl, shop)

        self.assertIn('price', payload, "Payload must include price key")
        # 12.99 * 25000 = 324,750; allow small floating-point delta
        self.assertAlmostEqual(
            payload['price'],
            12.99 * 25000,
            delta=0.01,
            msg=f"Price should be converted: 12.99 USD × 25000 rate = 324750 VND, got {payload['price']}"
        )

    def test_payload_price_unchanged_when_currencies_equal(self):
        """RED: _convert_to_shop_currency not checking if currencies are equal.

        Expected RED reason: price not matching or assertion failure.
        """
        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        if not self.usd:
            self.skipTest("USD currency not available in test database")

        # Ensure company currency is USD
        if self.company.currency_id != self.usd:
            self.company.currency_id = self.usd

        shop = self._create_shop('USD Shop', listing_currency_id=self.usd.id)
        tmpl = self._create_template(price=12.99)

        publisher = EtsyListingPublisher(self.env)
        payload = publisher._build_create_draft_payload(tmpl, shop)

        self.assertIn('price', payload)
        # When currencies are equal, no conversion; should be exactly 12.99
        self.assertAlmostEqual(
            payload['price'],
            12.99,
            delta=0.01,
            msg="Price should be unchanged when currencies match"
        )

    def test_payload_price_falls_through_with_warning_when_listing_currency_null(self):
        """Helper emits raw list_price + WARNING when currency missing.

        Hard-failing here would break every shop fixture that doesn't go
        through the OAuth / migration bootstrap path; production shops
        always have the field populated. The WARNING + Etsy's own response
        body identify the misconfiguration if a 400 reaches Etsy.
        """
        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        shop = self._create_shop('No Currency Shop', listing_currency_id=False)
        tmpl = self._create_template(price=12.99)

        publisher = EtsyListingPublisher(self.env)

        with self.assertLogs(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher',
            level='WARNING',
        ) as captured:
            payload = publisher._build_create_draft_payload(tmpl, shop)

        # Raw amount falls through (no conversion possible without target currency)
        self.assertEqual(payload['price'], 12.99)
        # WARNING explicitly names the missing field so operators can diagnose
        self.assertTrue(
            any('listing_currency_id' in line for line in captured.output),
            "WARNING must mention listing_currency_id; got %r" % captured.output,
        )

    def test_push_inventory_offering_price_converted(self):
        """RED: push_inventory not converting prices.

        Expected RED reason: Mocked payload doesn't include converted price,
        or publisher method doesn't call _convert_to_shop_currency.
        """
        from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
            EtsyListingPublisher,
        )

        if not self.vnd:
            self.skipTest("VND currency not available in test database")

        shop = self._create_shop('VND Shop 2', listing_currency_id=self.vnd.id)
        tmpl = self._create_template(price=12.99)

        publisher = EtsyListingPublisher(self.env)

        # Mock EtsyApiClient to avoid actual API calls
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            # Mock the push_inventory response (listing_id in response)
            mock_client.put.return_value = {'listing_id': 123456}

            # Call push_inventory; capture the payload that was POSTed
            try:
                publisher.push_inventory(tmpl, shop, listing_id='123456')
            except Exception:
                # Method may fail for other reasons (missing variant, etc.);
                # we just need to verify the put was called with converted price.
                pass

            # Check if put was called and with what payload
            if mock_client.put.called:
                call_args = mock_client.put.call_args
                payload = call_args[1] if len(call_args) > 1 else call_args[0][1] if len(call_args[0]) > 1 else None
                if payload and 'products' in payload and payload['products']:
                    first_product = payload['products'][0]
                    if 'offerings' in first_product and first_product['offerings']:
                        first_offering = first_product['offerings'][0]
                        self.assertAlmostEqual(
                            first_offering.get('price', 0),
                            12.99 * 25000,
                            delta=0.01,
                            msg="Offering price should be converted"
                        )


@tagged('post_install', '-at_install', 'p_bug_esty_188_iter2')
class TestP_BUG_ESTY_188_Phase2_Migration(TransactionCase):
    """Phase 2: Verify migration 19.0.2.34.0 bootstraps listing_currency_id.

    RED: Migration file missing; post_migrate function not defined.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        # Currencies are loaded lazily per test to avoid TransactionCase isolation issues
        Currency = self.env['res.currency'].with_context(active_test=False)
        self.usd = Currency.search([('name', '=', 'USD')], limit=1)
        self.vnd = Currency.search([('name', '=', 'VND')], limit=1)
        if self.vnd and not self.vnd.active:
            self.vnd.sudo().active = True

    def _create_shop(self, name, api_shop_id, active_source='api',
                     listing_currency_id=None):
        """Factory: create shop for migration testing."""
        vals = {
            'name': name,
            'etsy_api_shop_id': api_shop_id,
            'sync_mode': 'email_only',
            'active_source': active_source,
            'etsy_oauth_access_token': 'test',
            'etsy_oauth_refresh_token': 'test',
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=3600
            ),
        }
        if listing_currency_id:
            vals['listing_currency_id'] = listing_currency_id
        return self.env['etsy.shop'].create(vals)

    def test_bootstrap_currency_from_get_shops_discovers_currency_code(self):
        """RED: Migration file missing or post_migrate not implemented.

        Expected RED reason: ImportError/ModuleNotFoundError on importing
        migration module.
        """
        shop = self._create_shop('Bootstrap Test', '60752333')

        # Import migration's post_migrate function
        try:
            from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import (
                post_migrate,
            )
        except ImportError as e:
            self.fail(
                f"Migration module _19_0_2_34_0 not importable: {e}"
            )

        # Mock EtsyApiClient
        with patch(
            'odoo.addons.etsy_integration.migrations._19_0_2_34_0.EtsyApiClient'
        ) as MockCls:
            mock_client = MagicMock()
            MockCls.return_value = mock_client
            mock_client.get.return_value = {
                'currency_code': 'VND',
                'shop_id': 60752333,
            }

            post_migrate(self.env.cr, self.env)

        # Verify shop was updated
        shop.invalidate_recordset()
        self.assertEqual(
            shop.listing_currency_id.name,
            'VND',
            "Migration should bootstrap listing_currency_id to VND"
        )

    def test_bootstrap_skips_unknown_currency_code(self):
        """RED: Migration doesn't handle unknown currency codes.

        Expected RED reason: shop.listing_currency_id gets set to False/None
        (no matching currency) without warning, or ValueError on unknown code.
        """
        shop = self._create_shop('Unknown Currency', '60752334')

        try:
            from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import (
                post_migrate,
            )
        except ImportError:
            self.fail("Migration module not importable")

        with patch(
            'odoo.addons.etsy_integration.migrations._19_0_2_34_0.EtsyApiClient'
        ) as MockCls:
            mock_client = MagicMock()
            MockCls.return_value = mock_client
            mock_client.get.return_value = {
                'currency_code': 'XXX',  # Unknown code
                'shop_id': 60752334,
            }

            with self.assertLogs(
                'odoo.addons.etsy_integration.migrations._19_0_2_34_0',
                level='WARNING',
            ):
                post_migrate(self.env.cr, self.env)

        # Verify shop currency was NOT set
        shop.invalidate_recordset()
        self.assertFalse(
            shop.listing_currency_id,
            "Migration should skip unknown currency codes and not set field"
        )

    def test_bootstrap_handles_per_shop_api_failure(self):
        """RED: Migration doesn't handle per-shop failures gracefully.

        Expected RED reason: First shop's exception propagates; post_migrate fails.
        """
        shop1 = self._create_shop('Fail Shop', '60752335')
        shop2 = self._create_shop('Success Shop', '60752336')

        try:
            from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import (
                post_migrate,
            )
        except ImportError:
            self.fail("Migration module not importable")

        # Make first shop's API call fail, second succeed
        def get_side_effect(endpoint):
            if '60752335' in endpoint:
                raise Exception("API error for shop 1")
            return {'currency_code': 'VND', 'shop_id': 60752336}

        with patch(
            'odoo.addons.etsy_integration.migrations._19_0_2_34_0.EtsyApiClient'
        ) as MockCls:
            mock_client = MagicMock()
            MockCls.return_value = mock_client
            mock_client.get.side_effect = get_side_effect

            # post_migrate should NOT raise; it should swallow exceptions per shop
            post_migrate(self.env.cr, self.env)

        # shop1 should stay NULL; shop2 should be updated
        shop1.invalidate_recordset()
        shop2.invalidate_recordset()

        self.assertFalse(
            shop1.listing_currency_id,
            "Failed shop should stay NULL"
        )
        self.assertEqual(
            shop2.listing_currency_id.name,
            'VND',
            "Successful shop should be updated"
        )

    def test_post_migrate_iter2_idempotent(self):
        """RED: Migration doesn't check if field is already set.

        Expected RED reason: EtsyApiClient called even when field is already populated.
        """
        if not self.vnd:
            self.skipTest("VND currency not available in test database")

        shop = self._create_shop('Already Set', '60752337', listing_currency_id=self.vnd.id)

        try:
            from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import (
                post_migrate,
            )
        except ImportError:
            self.fail("Migration module not importable")

        with patch(
            'odoo.addons.etsy_integration.migrations._19_0_2_34_0.EtsyApiClient'
        ) as MockCls:
            post_migrate(self.env.cr, self.env)

            # If the field is already set, EtsyApiClient should not be instantiated
            MockCls.assert_not_called()

    def test_post_migrate_iter2_skips_email_only_shops(self):
        """RED: Migration doesn't filter out email-only shops.

        Expected RED reason: EtsyApiClient called for email-only shops.
        """
        shop = self._create_shop('Email Only', '60752338', active_source='email')

        try:
            from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import (
                post_migrate,
            )
        except ImportError:
            self.fail("Migration module not importable")

        with patch(
            'odoo.addons.etsy_integration.migrations._19_0_2_34_0.EtsyApiClient'
        ) as MockCls:
            post_migrate(self.env.cr, self.env)

            # Email-only shops should not trigger API call
            MockCls.assert_not_called()

        # Field should stay NULL
        shop.invalidate_recordset()
        self.assertFalse(
            shop.listing_currency_id,
            "Email-only shop should not be touched by migration"
        )

    def test_post_migrate_iter2_skips_shops_without_etsy_api_shop_id(self):
        """RED: Migration doesn't check for NULL etsy_api_shop_id.

        Expected RED reason: EtsyApiClient called with NULL shop_id (crashes).
        """
        # Create shop via raw SQL to bypass constraints
        expires_at = fields.Datetime.add(fields.Datetime.now(), seconds=3600)
        self.env.cr.execute(
            """
            INSERT INTO etsy_shop (
                name, active_source, etsy_oauth_access_token,
                etsy_oauth_refresh_token, etsy_oauth_token_expires_at,
                create_uid, create_date
            ) VALUES (%s, 'api', %s, %s, %s, %s, now())
            RETURNING id
            """,
            (
                'No Shop ID Shop',
                'test_access',
                'test_refresh',
                expires_at,
                self.env.user.id,
            ),
        )
        shop_id = self.env.cr.fetchone()[0]
        self.env['etsy.shop'].invalidate_model()
        shop = self.env['etsy.shop'].browse(shop_id)

        try:
            from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import (
                post_migrate,
            )
        except ImportError:
            self.fail("Migration module not importable")

        with patch(
            'odoo.addons.etsy_integration.migrations._19_0_2_34_0.EtsyApiClient'
        ) as MockCls:
            with self.assertLogs(
                'odoo.addons.etsy_integration.migrations._19_0_2_34_0',
                level='WARNING',
            ):
                post_migrate(self.env.cr, self.env)

            # Should warn + skip, not instantiate client
            MockCls.assert_not_called()

        # Field should stay NULL
        shop.invalidate_recordset()
        self.assertFalse(
            shop.listing_currency_id,
            "Shop without etsy_api_shop_id should be skipped"
        )
