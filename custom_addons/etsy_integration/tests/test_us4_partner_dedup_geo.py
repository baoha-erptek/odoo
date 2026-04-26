"""Tests for improved partner deduplication and geo resolution (T028-T030 / US4).

Covers find_or_create_partner() with 3-tier matching strategy:
  1. Email match (exact)
  2. Normalized name+address+city+zip match (accents stripped, lowercase)
  3. Name+zip fallback

Also tests _resolve_state() with code-first lookup and _resolve_country() with
extended name overrides.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPartnerDedup(TransactionCase):
    """Test improved customer deduplication logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _make_shipping_address(self, **kwargs):
        """Helper to create a ShippingAddress-like object."""
        from ..services.email_parser import ShippingAddress
        defaults = {
            'name': 'Test Customer',
            'address1': '123 Main St',
            'address2': '',
            'city': 'Portland',
            'state': 'OR',
            'zipcode': '97201',
            'country': 'United States',
            'country_code': 'US',
            'phone': '',
            'email': '',
        }
        defaults.update(kwargs)
        return ShippingAddress(**defaults)

    def test_partner_dedup_by_email_first(self):
        """T028 tier 1: Same email → same partner, even with different name/address."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # Create first partner with email
        shipping1 = self._make_shipping_address(
            name='John Smith',
            email='john@example.com',
            address1='123 Main St',
            city='Portland',
            zipcode='97201',
        )
        partner1 = creator.find_or_create_partner(shipping1, 'JohnS')
        self.assertTrue(partner1.id, "Partner 1 should be created")

        # Create second address with same email, different name and street
        shipping2 = self._make_shipping_address(
            name='Jon Smith',  # Different name
            email='john@example.com',  # Same email
            address1='456 Oak Ave',  # Different address
            city='Salem',  # Different city
            zipcode='97301',  # Different zip
        )
        partner2 = creator.find_or_create_partner(shipping2, 'JonS')
        self.assertEqual(
            partner1.id, partner2.id,
            "Same email should match to existing partner, ignoring name/address differences",
        )

    def test_partner_dedup_normalized_name_address(self):
        """T028 tier 2: Normalized name+address+city+zip match (accents, case-insensitive)."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # Create first partner with accented name, no email
        shipping1 = self._make_shipping_address(
            name='Françoise Müller',
            email='',
            address1='123 Rue Principale',
            city='Lyon',
            zipcode='69001',
        )
        partner1 = creator.find_or_create_partner(shipping1, 'FrancoisM')
        self.assertTrue(partner1.id, "Partner 1 should be created")

        # Create second with normalized name (no accents), case-insensitive, same address
        shipping2 = self._make_shipping_address(
            name='Francoise Mueller',  # Normalized accents
            email='',  # No email to skip tier 1
            address1='123 rue principale',  # Different case
            city='LYON',  # Different case
            zipcode='69001',  # Same zip
        )
        partner2 = creator.find_or_create_partner(shipping2, 'FM')

        # EXPECTED: Should match because normalized address matches
        # NOTE: This test will FAIL in RED phase because T028 is not yet implemented
        self.assertEqual(
            partner1.id, partner2.id,
            "Normalized name+address+city+zip should match to existing partner",
        )

    def test_partner_dedup_by_name_and_zip_fallback(self):
        """T028 tier 3: Name+zip fallback when email and full address unavailable."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # Create first partner
        shipping1 = self._make_shipping_address(
            name='Maria Garcia',
            email='',  # No email
            address1='999 Unknown',
            city='Barcelona',
            zipcode='08001',
        )
        partner1 = creator.find_or_create_partner(shipping1, 'MG')
        self.assertTrue(partner1.id, "Partner 1 should be created")

        # Create second with same name+zip, different street/city
        shipping2 = self._make_shipping_address(
            name='Maria Garcia',  # Same name
            email='',  # No email
            address1='Carrer Diferent',  # Different street
            city='Another City',  # Different city
            zipcode='08001',  # Same zip
        )
        partner2 = creator.find_or_create_partner(shipping2, 'MG')

        # EXPECTED: Should match because name+zip matches
        # NOTE: This test will FAIL in RED phase because T028 is not yet implemented
        self.assertEqual(
            partner1.id, partner2.id,
            "Name+zip fallback should match to existing partner",
        )

    def test_partner_no_false_match_when_zip_differs(self):
        """T028 negative test: Same name, different zip → different partners."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # Create first partner
        shipping1 = self._make_shipping_address(
            name='John Brown',
            email='',
            zipcode='12345',
        )
        partner1 = creator.find_or_create_partner(shipping1, 'JB1')
        self.assertTrue(partner1.id, "Partner 1 should be created")

        # Create second with same name, different zip (and no email)
        shipping2 = self._make_shipping_address(
            name='John Brown',
            email='',
            zipcode='54321',  # Different zip
        )
        partner2 = creator.find_or_create_partner(shipping2, 'JB2')

        self.assertNotEqual(
            partner1.id, partner2.id,
            "Different zip should prevent false match even with same name",
        )

    def test_partner_email_still_preferred_over_name_zip(self):
        """Verify email tier still takes precedence over name+zip matching."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # Create first partner with email
        shipping1 = self._make_shipping_address(
            name='Alice',
            email='alice@example.com',
            zipcode='10001',
        )
        partner1 = creator.find_or_create_partner(shipping1, 'A1')
        self.assertTrue(partner1.id, "Partner 1 created")

        # Create second with same name+zip but DIFFERENT email
        shipping2 = self._make_shipping_address(
            name='Alice',  # Same name
            email='different@example.com',  # Different email
            zipcode='10001',  # Same zip
        )
        partner2 = creator.find_or_create_partner(shipping2, 'A2')

        self.assertNotEqual(
            partner1.id, partner2.id,
            "Different email should prevent match, even if name+zip are the same",
        )


@tagged('post_install', '-at_install')
class TestStateResolution(TransactionCase):
    """Test state/province code and name resolution (T029)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_resolve_state_by_code_first(self):
        """T029: State code (e.g., 'CA') should be resolved by code, not name."""
        from ..services.order_creator import OrderCreator

        # Get or create US country
        us_country = self.env['res.country'].search([('code', '=', 'US')], limit=1)
        self.assertTrue(us_country, "US country should exist")

        creator = OrderCreator(self.env)
        state = creator._resolve_state('CA', us_country)
        self.assertTrue(state, "State 'CA' should resolve")
        self.assertEqual(state.code, 'CA', "Should resolve to California (code CA)")
        self.assertEqual(state.name, 'California', "State name should be California")

    def test_resolve_state_by_name_when_code_unknown(self):
        """T029: State name fallback when code doesn't match."""
        from ..services.order_creator import OrderCreator

        # Get US country
        us_country = self.env['res.country'].search([('code', '=', 'US')], limit=1)
        self.assertTrue(us_country, "US country should exist")

        creator = OrderCreator(self.env)
        state = creator._resolve_state('California', us_country)
        self.assertTrue(state, "State 'California' should resolve by name")
        self.assertEqual(state.code, 'CA', "Should resolve to CA")

    def test_resolve_state_none_when_not_found(self):
        """T029: Non-existent state returns None."""
        from ..services.order_creator import OrderCreator

        us_country = self.env['res.country'].search([('code', '=', 'US')], limit=1)
        self.assertTrue(us_country, "US country should exist")

        creator = OrderCreator(self.env)
        state = creator._resolve_state('XYZState', us_country)
        self.assertIsNone(state, "Non-existent state should return None")

    def test_resolve_state_with_none_country(self):
        """T029: State resolution with None country should return None."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        state = creator._resolve_state('CA', None)
        self.assertIsNone(state, "Should return None when country is None")


@tagged('post_install', '-at_install')
class TestCountryResolution(TransactionCase):
    """Test country code and name resolution with extended overrides (T030)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_resolve_country_overrides_united_states(self):
        """T030: Country override mapping should work for United States → US."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        country = creator._resolve_country('', 'United States')
        self.assertTrue(country, "United States should resolve via override")
        self.assertEqual(country.code, 'US', "Should resolve to US")

    def test_resolve_country_overrides_united_kingdom(self):
        """T030: Country override mapping for United Kingdom → GB."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        country = creator._resolve_country('', 'United Kingdom')
        self.assertTrue(country, "United Kingdom should resolve via override")
        self.assertEqual(country.code, 'GB', "Should resolve to GB")

    def test_resolve_country_by_code_first(self):
        """T030: Country resolution by ISO code takes precedence."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        country = creator._resolve_country('FR', '')
        self.assertTrue(country, "France (FR) should resolve by code")
        self.assertEqual(country.code, 'FR', "Should resolve to FR")

    def test_resolve_country_by_name_fallback(self):
        """T030: Country name fallback when code is unknown."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        country = creator._resolve_country('', 'France')
        self.assertTrue(country, "France should resolve by name")
        self.assertEqual(country.code, 'FR', "Should resolve to FR")

    def test_resolve_country_czechia_override(self):
        """T030: Extended override for Czechia mapping.

        NOTE: This test expects an override entry for 'Czechia' to be added
        to _COUNTRY_NAME_OVERRIDES in order_creator.py as part of T030.
        """
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        # T030 should add 'Czechia' → 'CZ' mapping
        country = creator._resolve_country('', 'Czechia')
        # This will FAIL in RED if the override is not yet added
        self.assertTrue(country, "Czechia should resolve via override")
        self.assertEqual(country.code, 'CZ', "Should resolve to CZ (Czech Republic)")

    def test_resolve_country_republic_of_korea_override(self):
        """T030: Extended override for Republic of Korea mapping.

        NOTE: This test expects an override entry for 'Republic of Korea' to be added
        to _COUNTRY_NAME_OVERRIDES in order_creator.py as part of T030.
        """
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        # T030 should add 'Republic of Korea' → 'KR' mapping
        country = creator._resolve_country('', 'Republic of Korea')
        # This will FAIL in RED if the override is not yet added
        self.assertTrue(country, "Republic of Korea should resolve via override")
        self.assertEqual(country.code, 'KR', "Should resolve to KR (South Korea)")

    def test_resolve_country_none_when_not_found(self):
        """T030: Non-existent country returns None."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        country = creator._resolve_country('ZZ', '')
        self.assertIsNone(country, "Non-existent country should return None")

    def test_resolve_country_empty_inputs(self):
        """T030: Empty code and name should return None."""
        from ..services.order_creator import OrderCreator

        creator = OrderCreator(self.env)
        country = creator._resolve_country('', '')
        self.assertIsNone(country, "Empty code and name should return None")
