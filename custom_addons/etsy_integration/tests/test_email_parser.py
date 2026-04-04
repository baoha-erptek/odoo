"""Unit tests for the Etsy email parser service.

These tests run without Odoo — they test pure Python parsing logic.
"""
import os
import unittest

from ..services.email_parser import (
    ParseError,
    ParseResult,
    RawEmail,
    parse_eur_amount,
    parse_etsy_email,
)


SAMPLE_TEXT_SINGLE = """Note from Andrea Flint:
Andrea Flint - The buyer did not leave a note.

Order details
Shop: Viktor
Transaction ID: 4623462013
Item: Never Forget The Difference You Have Made Retirement Ring Dish-Happy Retirement Gift For Women-Nurs
Size: Square
Personalization: June 2025
Quantity: 1
Item price: €19.70

Item total: €19.70
Applied discounts

Shipping: €3.96 (Standard)
Subtotal: €17.73

http://www.etsy.com/your/orders/3708041263
"""

SAMPLE_HTML_SINGLE = """<html>
<body>
<img src="https://i.etsystatic.com/28215280/r/il/a90239/6049408768/il_75x75.6049408768_n0ek.jpg"/>
<span class='notranslate name'>Andrea Flint</span>
<span class='notranslate first-line'>34 OWATONNA ST</span>
<span class='notranslate second-line'></span>
<span class='notranslate city'>AUBURNDALE</span>
<span class='notranslate state'>MA</span>
<span class='notranslate zip'>02466-1411</span>
<span class='notranslate country-name'>United States</span>
<span>Processing time: 9-10 business days</span>
</body>
</html>"""

SAMPLE_TEXT_MULTI = """Note from John Doe:
John Doe - Custom engraving requested.

Order details
Shop: Julien
Transaction ID: 4610399028
Item: Wildflower Temporary Tattoo-Flower Tattoo
Option: Pack of 10
Quantity: 1
Item price: €24.51

Transaction ID: 4610399029
Item: Rose Gold Ring Dish
Color: Rose Gold
Size: Small
Quantity: 2
Item price: €15.00

Item total: €54.51
Shipping: €4.64 (Standard)
Subtotal: €49.36

http://www.etsy.com/your/orders/3710632919
"""


class TestParseEurAmount(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(parse_eur_amount('€19.70'), 19.70)

    def test_with_spaces(self):
        self.assertAlmostEqual(parse_eur_amount('€3.96  '), 3.96)

    def test_no_symbol(self):
        self.assertAlmostEqual(parse_eur_amount('19.70'), 19.70)

    def test_empty(self):
        self.assertAlmostEqual(parse_eur_amount(''), 0.0)

    def test_none_like(self):
        self.assertAlmostEqual(parse_eur_amount('N/A'), 0.0)

    def test_with_dash(self):
        self.assertAlmostEqual(parse_eur_amount('-€5.00'), 5.00)


class TestParseSingleOrder(unittest.TestCase):
    def setUp(self):
        self.raw = RawEmail(
            message_id='msg_001',
            subject='New order [3708041263]',
            date='Thu, 05 Jun 2025 16:14:27 +0000 (UTC)',
            text_body=SAMPLE_TEXT_SINGLE,
            html_body=SAMPLE_HTML_SINGLE,
        )

    def test_returns_parse_result(self):
        result = parse_etsy_email(self.raw)
        self.assertIsInstance(result, ParseResult)

    def test_order_id(self):
        result = parse_etsy_email(self.raw)
        self.assertEqual(result.order_id, '3708041263')

    def test_shop(self):
        result = parse_etsy_email(self.raw)
        self.assertEqual(result.shop, 'Viktor')

    def test_transaction_count(self):
        result = parse_etsy_email(self.raw)
        self.assertEqual(len(result.transactions), 1)

    def test_transaction_fields(self):
        result = parse_etsy_email(self.raw)
        txn = result.transactions[0]
        self.assertIn('4623462013', txn.transaction_id)
        self.assertIn('Ring Dish', txn.product_name)
        self.assertEqual(txn.size, 'Square')
        self.assertEqual(txn.personalisation, 'June 2025')
        self.assertEqual(txn.quantity, 1)
        self.assertAlmostEqual(txn.price, 19.70)

    def test_shipping_address(self):
        result = parse_etsy_email(self.raw)
        addr = result.shipping_address
        self.assertEqual(addr.name, 'Andrea Flint')
        self.assertEqual(addr.address1, '34 OWATONNA ST')
        self.assertEqual(addr.city, 'AUBURNDALE')
        self.assertEqual(addr.state, 'MA')
        self.assertEqual(addr.zipcode, '02466-1411')
        self.assertIn(addr.country_code, ('US', ''))

    def test_shipping_service(self):
        result = parse_etsy_email(self.raw)
        self.assertEqual(result.shipping_service, 'Standard')

    def test_image_url_300(self):
        result = parse_etsy_email(self.raw)
        txn = result.transactions[0]
        if txn.image_url:
            self.assertIn('300x300', txn.image_url)
            self.assertNotIn('75x75', txn.image_url)

    def test_note_from_buyer_empty_when_no_note(self):
        result = parse_etsy_email(self.raw)
        self.assertEqual(result.note_from_buyer, '')

    def test_pricing(self):
        result = parse_etsy_email(self.raw)
        self.assertAlmostEqual(result.shipping_cost, 3.96)
        self.assertAlmostEqual(result.subtotal, 17.73)


class TestParseMultiOrder(unittest.TestCase):
    def setUp(self):
        self.raw = RawEmail(
            message_id='msg_002',
            subject='New order [3710632919]',
            date='Sun, 08 Jun 2025 10:37:25 +0000 (UTC)',
            text_body=SAMPLE_TEXT_MULTI,
            html_body='<html><body></body></html>',
        )

    def test_two_transactions(self):
        result = parse_etsy_email(self.raw)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(len(result.transactions), 2)

    def test_second_transaction(self):
        result = parse_etsy_email(self.raw)
        txn2 = result.transactions[1]
        self.assertIn('4610399029', txn2.transaction_id)
        self.assertEqual(txn2.color, 'Rose Gold')
        self.assertEqual(txn2.size, 'Small')
        self.assertEqual(txn2.quantity, 2)
        self.assertAlmostEqual(txn2.price, 15.00)

    def test_note_from_buyer(self):
        result = parse_etsy_email(self.raw)
        self.assertIn('Custom engraving', result.note_from_buyer)


class TestParseError(unittest.TestCase):
    def test_empty_email(self):
        raw = RawEmail('msg_003', '', '', '', '')
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseError)

    def test_no_order_details(self):
        raw = RawEmail('msg_004', 'Some subject', '', 'Random text', '<html></html>')
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseError)


# ---------------------------------------------------------------------------
# German-labeled email samples
# ---------------------------------------------------------------------------

SAMPLE_TEXT_GERMAN_PERSONALISIERUNG = """Note from Klara Meier:
Klara Meier - The buyer did not leave a note.

Order details
Shop: Viktor
Transaction ID: 4630001001
Item: Engraved Silver Bracelet Custom Name Gift
Size: Medium
Personalisierung: Frohe Weihnachten 2025
Quantity: 1
Item price: €22.50

Item total: €22.50
Shipping: €4.10 (Standard)
Subtotal: €20.35

http://www.etsy.com/your/orders/3720001001
"""

SAMPLE_TEXT_GERMAN_PERSONALISIERUN = """Note from Hans Weber:
Hans Weber - Bitte mit Geschenkverpackung.

Order details
Shop: Julien
Transaction ID: 4630002001
Item: Personalized Wooden Music Box Melody Engraving
Option: Walnut
Personalisierun: Alles Gute zum Geburtstag, Oma
Quantity: 1
Item price: €35.80

Item total: €35.80
Shipping: €5.20 (Express)
Subtotal: €32.40

http://www.etsy.com/your/orders/3720002001
"""


class TestMultiLanguageLabels(unittest.TestCase):
    """Verify the parser extracts personalisation from German-labeled emails."""

    def test_personalisierung_label(self):
        """Parse email using 'Personalisierung:' (full German label)."""
        raw = RawEmail(
            message_id='msg_de_001',
            subject='New order [3720001001]',
            date='Mon, 15 Dec 2025 09:00:00 +0000 (UTC)',
            text_body=SAMPLE_TEXT_GERMAN_PERSONALISIERUNG,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(len(result.transactions), 1)
        txn = result.transactions[0]
        self.assertEqual(txn.personalisation, 'Frohe Weihnachten 2025')

    def test_personalisierun_label(self):
        """Parse email using 'Personalisierun:' (truncated German label)."""
        raw = RawEmail(
            message_id='msg_de_002',
            subject='New order [3720002001]',
            date='Tue, 16 Dec 2025 14:30:00 +0000 (UTC)',
            text_body=SAMPLE_TEXT_GERMAN_PERSONALISIERUN,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(len(result.transactions), 1)
        txn = result.transactions[0]
        self.assertEqual(txn.personalisation, 'Alles Gute zum Geburtstag, Oma')

    def test_personalisierung_order_fields(self):
        """Verify order-level fields are correct for a German-labeled email."""
        raw = RawEmail(
            message_id='msg_de_003',
            subject='New order [3720001001]',
            date='Mon, 15 Dec 2025 09:00:00 +0000 (UTC)',
            text_body=SAMPLE_TEXT_GERMAN_PERSONALISIERUNG,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.order_id, '3720001001')
        self.assertEqual(result.shop, 'Viktor')
        self.assertAlmostEqual(result.shipping_cost, 4.10)
        self.assertEqual(result.shipping_service, 'Standard')

    def test_personalisierun_transaction_fields(self):
        """Verify transaction fields are correct for the truncated German label."""
        raw = RawEmail(
            message_id='msg_de_004',
            subject='New order [3720002001]',
            date='Tue, 16 Dec 2025 14:30:00 +0000 (UTC)',
            text_body=SAMPLE_TEXT_GERMAN_PERSONALISIERUN,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        txn = result.transactions[0]
        self.assertIn('4630002001', txn.transaction_id)
        self.assertIn('Music Box', txn.product_name)
        self.assertEqual(txn.option, 'Walnut')
        self.assertEqual(txn.quantity, 1)
        self.assertAlmostEqual(txn.price, 35.80)

    def test_personalisierun_note_from_buyer(self):
        """German note is extracted when buyer leaves a message."""
        raw = RawEmail(
            message_id='msg_de_005',
            subject='New order [3720002001]',
            date='Tue, 16 Dec 2025 14:30:00 +0000 (UTC)',
            text_body=SAMPLE_TEXT_GERMAN_PERSONALISIERUN,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        self.assertIn('Geschenkverpackung', result.note_from_buyer)


class TestSampleDataFiles(unittest.TestCase):
    """Verify that the sample data files parse correctly through the parser."""

    _DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

    def _read_sample(self, filename):
        path = os.path.join(self._DATA_DIR, filename)
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_sample_single_order_parses(self):
        text = self._read_sample('sample_single_order.txt')
        raw = RawEmail(
            message_id='msg_file_001',
            subject='New order [3708050001]',
            date='Wed, 10 Jun 2025 08:00:00 +0000 (UTC)',
            text_body=text,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(len(result.transactions), 1)

    def test_sample_multi_order_parses(self):
        text = self._read_sample('sample_multi_order.txt')
        raw = RawEmail(
            message_id='msg_file_002',
            subject='New order [3710050002]',
            date='Thu, 11 Jun 2025 12:00:00 +0000 (UTC)',
            text_body=text,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseResult)
        self.assertGreaterEqual(len(result.transactions), 2)

    def test_sample_malformed_fails(self):
        text = self._read_sample('sample_malformed.txt')
        raw = RawEmail(
            message_id='msg_file_003',
            subject='Some notification',
            date='Fri, 12 Jun 2025 15:00:00 +0000 (UTC)',
            text_body=text,
            html_body='<html><body></body></html>',
        )
        result = parse_etsy_email(raw)
        self.assertIsInstance(result, ParseError)


if __name__ == '__main__':
    unittest.main()
