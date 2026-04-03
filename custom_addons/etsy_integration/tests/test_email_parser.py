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


if __name__ == '__main__':
    unittest.main()
