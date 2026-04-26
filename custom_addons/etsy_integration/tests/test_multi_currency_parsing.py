"""Tests for multi-currency price parsing (T020 / US1).

Covers `services.order_creator._parse_price` and the wizard's `_parse_price`
wrapper. The TransactionCase base is used for Odoo's test-runner discovery;
the assertions themselves are ORM-free.
"""
from odoo.tests.common import TransactionCase

from odoo.addons.etsy_integration.services.order_creator import _parse_price
from odoo.addons.etsy_integration.wizards.import_orders_wizard import (
    _parse_price as wizard_parse_price,
)


class TestMultiCurrencyParsing(TransactionCase):
    """Direct call tests; the transaction is unused but required for discovery."""

    def test_usd_with_dollar_sign(self):
        self.assertEqual(_parse_price('$15.00'), (15.0, 'USD'))
        self.assertEqual(_parse_price('$ 7.50'), (7.5, 'USD'))

    def test_usd_with_iso_code(self):
        self.assertEqual(_parse_price('USD 15.00'), (15.0, 'USD'))
        self.assertEqual(_parse_price('15.00 USD'), (15.0, 'USD'))

    def test_eur_with_symbol(self):
        self.assertEqual(_parse_price('€9,99'), (9.99, 'EUR'))
        self.assertEqual(_parse_price('€ 12.50'), (12.5, 'EUR'))

    def test_eur_with_iso_code(self):
        self.assertEqual(_parse_price('15,00 EUR'), (15.0, 'EUR'))
        self.assertEqual(_parse_price('EUR 15.00'), (15.0, 'EUR'))

    def test_gbp_with_symbol(self):
        self.assertEqual(_parse_price('£12.50'), (12.5, 'GBP'))

    def test_gbp_with_iso_code(self):
        self.assertEqual(_parse_price('GBP 7.25'), (7.25, 'GBP'))

    def test_no_marker_defaults_to_eur(self):
        self.assertEqual(_parse_price('10.5'), (10.5, 'EUR'))
        self.assertEqual(_parse_price('25,75'), (25.75, 'EUR'))

    def test_empty_input(self):
        self.assertEqual(_parse_price(''), (0.0, 'EUR'))
        self.assertEqual(_parse_price(None), (0.0, 'EUR'))
        self.assertEqual(_parse_price('   '), (0.0, 'EUR'))

    def test_corrupted_input(self):
        self.assertEqual(_parse_price('garbage'), (0.0, 'EUR'))
        self.assertEqual(_parse_price('abc$def'), (0.0, 'USD'))

    def test_numeric_input_passes_through(self):
        self.assertEqual(_parse_price(15.0), (15.0, 'EUR'))
        self.assertEqual(_parse_price(7), (7.0, 'EUR'))

    def test_negative_price_treated_as_absolute(self):
        amount, code = _parse_price('-10.5 USD')
        self.assertEqual((amount, code), (10.5, 'USD'))

    def test_wizard_wrapper_matches_service(self):
        """The wizard delegate must produce identical results."""
        for sample in ('$15.00', '15,00 EUR', '£12.50', '', None, 'garbage'):
            self.assertEqual(
                wizard_parse_price(sample), _parse_price(sample),
                f'wizard wrapper diverged on {sample!r}')
