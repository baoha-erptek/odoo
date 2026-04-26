"""Tests for the Etsy import orders wizard.

Covers utility functions (_parse_eur_price, _parse_quantity, _cell_str),
date parsing, full order import via Excel upload, and deduplication.
"""
import base64
import io

from odoo.tests.common import TransactionCase

from ..wizards.import_orders_wizard import (
    _cell_str,
    _parse_eur_price,
    _parse_quantity,
)


class TestImportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    # ------------------------------------------------------------------
    # _parse_eur_price
    # ------------------------------------------------------------------

    def test_parse_eur_price_basic(self):
        """EUR prices with euro sign, comma separator, and EUR prefix."""
        self.assertAlmostEqual(_parse_eur_price('\u20ac19.70'), 19.70)
        self.assertAlmostEqual(_parse_eur_price('19,70'), 19.70)
        self.assertAlmostEqual(_parse_eur_price('EUR 5.00'), 5.00)

    def test_parse_eur_price_empty_and_none(self):
        """Empty string and None return 0.0."""
        self.assertAlmostEqual(_parse_eur_price(''), 0.0)
        self.assertAlmostEqual(_parse_eur_price(None), 0.0)

    def test_parse_eur_price_negative_stripped(self):
        """Leading dash is stripped (absolute value)."""
        self.assertAlmostEqual(_parse_eur_price('-12.50'), 12.50)
        self.assertAlmostEqual(_parse_eur_price('\u20ac-8,30'), 8.30)

    def test_parse_eur_price_whitespace(self):
        """Surrounding whitespace is handled."""
        self.assertAlmostEqual(_parse_eur_price('  3.50  '), 3.50)

    def test_parse_eur_price_invalid(self):
        """Non-numeric text returns 0.0."""
        self.assertAlmostEqual(_parse_eur_price('abc'), 0.0)

    def test_parse_eur_price_numeric_passthrough(self):
        """Numeric values passed directly (int, float) are handled."""
        self.assertAlmostEqual(_parse_eur_price(19.70), 19.70)
        self.assertAlmostEqual(_parse_eur_price(0), 0.0)

    # ------------------------------------------------------------------
    # _parse_quantity
    # ------------------------------------------------------------------

    def test_parse_quantity_integer_string(self):
        self.assertEqual(_parse_quantity('1'), 1)
        self.assertEqual(_parse_quantity('5'), 5)

    def test_parse_quantity_float_string(self):
        """Float strings are truncated to int."""
        self.assertEqual(_parse_quantity('2.0'), 2)
        self.assertEqual(_parse_quantity('3.9'), 3)

    def test_parse_quantity_empty_returns_one(self):
        """Empty or missing values default to 1."""
        self.assertEqual(_parse_quantity(''), 1)
        self.assertEqual(_parse_quantity(None), 1)

    def test_parse_quantity_invalid_returns_one(self):
        """Non-numeric text defaults to 1."""
        self.assertEqual(_parse_quantity('abc'), 1)

    def test_parse_quantity_zero_becomes_one(self):
        """Zero is clamped to 1 (minimum quantity)."""
        self.assertEqual(_parse_quantity('0'), 1)

    # ------------------------------------------------------------------
    # _cell_str
    # ------------------------------------------------------------------

    def test_cell_str_none(self):
        self.assertEqual(_cell_str(None), '')

    def test_cell_str_number(self):
        """Numeric values are converted to strings."""
        self.assertEqual(_cell_str(42), '42')
        self.assertEqual(_cell_str(3.14), '3.14')

    def test_cell_str_whitespace(self):
        """Surrounding whitespace is stripped."""
        self.assertEqual(_cell_str('  hello  '), 'hello')
        self.assertEqual(_cell_str('\tworld\n'), 'world')

    def test_cell_str_passthrough(self):
        """Normal strings pass through unchanged."""
        self.assertEqual(_cell_str('test'), 'test')

    # ------------------------------------------------------------------
    # _parse_date (static method on ImportOrdersWizard)
    # ------------------------------------------------------------------

    def test_date_parsing_email_format(self):
        """RFC 2822 date with parenthesized timezone."""
        Wizard = self.env['etsy.import.orders.wizard']
        result = Wizard._parse_date(
            'Thu, 05 Jun 2025 16:14:27 +0000 (UTC)')
        self.assertEqual(result, '2025-06-05 16:14:27')

    def test_date_parsing_iso_format(self):
        """ISO 8601 date string."""
        Wizard = self.env['etsy.import.orders.wizard']
        result = Wizard._parse_date('2025-06-05')
        self.assertIn('2025-06-05', result)

    def test_date_parsing_us_format(self):
        """US date format MM/DD/YYYY."""
        Wizard = self.env['etsy.import.orders.wizard']
        result = Wizard._parse_date('06/05/2025')
        # Could be parsed as MM/DD/YYYY or DD/MM/YYYY depending on format
        # order; just verify it returns a truthy string.
        self.assertTrue(result)

    def test_date_parsing_empty(self):
        """Empty and falsy values return False."""
        Wizard = self.env['etsy.import.orders.wizard']
        self.assertFalse(Wizard._parse_date(''))
        self.assertFalse(Wizard._parse_date(None))

    def test_date_parsing_invalid(self):
        """Completely invalid date returns False."""
        Wizard = self.env['etsy.import.orders.wizard']
        self.assertFalse(Wizard._parse_date('not-a-date'))

    def test_date_parsing_datetime_format(self):
        """Full datetime string YYYY-MM-DD HH:MM:SS."""
        Wizard = self.env['etsy.import.orders.wizard']
        result = Wizard._parse_date('2025-01-15 10:30:00')
        self.assertEqual(result, '2025-01-15 10:30:00')

    # ------------------------------------------------------------------
    # Full import flow helpers
    # ------------------------------------------------------------------

    def _build_xlsx_bytes(self, rows):
        """Create a minimal .xlsx file in memory from a list of row tuples.

        Each row is a tuple of 34 cell values matching the wizard's
        column layout.  Returns raw bytes (not base64-encoded).
        """
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(list(row))
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _make_row(self, order_id='XLSORD001', transaction_id='XLSTXN001',
                  product_name='Test Mug', price='19.70', quantity='1',
                  shop='Viktor', shipping_name='Test Customer',
                  shipping_email='test@example.com',
                  date='2025-06-05'):
        """Build a 34-element tuple matching the wizard column layout."""
        row = [None] * 34
        row[0] = transaction_id       # TRANSACTION_ID
        row[1] = ''                   # IMG_URL
        row[2] = ''                   # IMG
        row[3] = date                 # DATE
        row[4] = 'Test note'          # NOTE_FROM_BUYER
        row[5] = ''                   # GIFT_MESSAGE
        row[6] = 'Custom engraving'   # PERSONALISATION
        row[7] = 'SKU001'             # SKU
        row[8] = shop                 # SHOP
        row[9] = order_id             # ORDER_ID
        row[10] = shipping_name       # SHIPPING_NAME
        row[11] = '123 Test St'       # SHIPPING_ADDRESS1
        row[12] = ''                  # SHIPPING_ADDRESS2
        row[13] = 'Test City'         # SHIPPING_CITY
        row[14] = 'CA'                # SHIPPING_STATE
        row[15] = '90210'             # SHIPPING_ZIPCODE
        row[16] = 'US'                # SHIPPING_COUNTRY
        row[17] = '555-1234'          # SHIPPING_PHONE
        row[18] = shipping_email      # SHIPPING_EMAIL
        row[19] = product_name        # PRODUCT_NAME
        row[20] = ''                  # OPTION
        row[21] = 'Gold'              # COLOR
        row[22] = 'Small'             # SIZE
        row[23] = ''                  # SIDE
        row[24] = ''                  # FACE_MASK_SIZE
        row[25] = quantity            # QUANTITY
        row[26] = ''                  # DESIGN_LINK_FRONT
        row[27] = ''                  # DESIGN_LINK_BACK
        row[28] = 'Standard'          # SHIPPING_SERVICE
        row[29] = '5-7 days'          # PROCESSING_TIME
        row[30] = '3.96'              # SHIPPING_COST
        row[31] = price               # PRICE
        row[32] = ''                  # DISCOUNT_CODE
        row[33] = '19.70'             # SUBTOTAL
        return tuple(row)

    def _create_wizard(self, xlsx_bytes):
        """Create the wizard record with a base64-encoded xlsx attachment."""
        encoded = base64.b64encode(xlsx_bytes).decode('ascii')
        return self.env['etsy.import.orders.wizard'].create({
            'excel_file': encoded,
            'excel_filename': 'test_orders.xlsx',
        })

    # ------------------------------------------------------------------
    # Full import tests
    # ------------------------------------------------------------------

    def test_import_creates_order(self):
        """Upload a minimal xlsx and verify a sale.order is created."""
        header = tuple(
            ['TRANSACTION_ID', 'IMG_URL', 'IMG', 'DATE',
             'NOTE_FROM_BUYER', 'GIFT_MESSAGE', 'PERSONALISATION',
             'SKU', 'SHOP', 'ORDER_ID', 'SHIPPING_NAME',
             'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2', 'SHIPPING_CITY',
             'SHIPPING_STATE', 'SHIPPING_ZIPCODE', 'SHIPPING_COUNTRY',
             'SHIPPING_PHONE', 'SHIPPING_EMAIL', 'PRODUCT_NAME',
             'OPTION', 'COLOR', 'SIZE', 'SIDE', 'FACE_MASK_SIZE',
             'QUANTITY', 'DESIGN_LINK_FRONT', 'DESIGN_LINK_BACK',
             'SHIPPING_SERVICE', 'PROCESSING_TIME', 'SHIPPING_COST',
             'PRICE', 'DISCOUNT_CODE', 'SUBTOTAL']
        )
        data_row = self._make_row(
            order_id='IMP_ORD_001',
            transaction_id='IMP_TXN_001',
            product_name='Wizard Test Ring',
            price='25.50',
            quantity='2',
        )
        xlsx_bytes = self._build_xlsx_bytes([header, data_row])
        wizard = self._create_wizard(xlsx_bytes)
        wizard.action_import()

        order = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'IMP_ORD_001')], limit=1)
        self.assertTrue(order, 'Expected sale.order to be created')
        self.assertEqual(order.etsy_order_id, 'IMP_ORD_001')
        self.assertTrue(len(order.order_line) >= 1)

        line = order.order_line[0]
        self.assertEqual(line.etsy_transaction_id, 'IMP_TXN_001')
        self.assertAlmostEqual(line.price_unit, 25.50)
        self.assertEqual(line.product_uom_qty, 2)
        self.assertEqual(line.etsy_personalisation, 'Custom engraving')
        self.assertEqual(line.etsy_color, 'Gold')
        self.assertEqual(line.etsy_size, 'Small')

        # Verify status message reports success
        self.assertIn('1 orders imported', wizard.status_message)

    def test_import_skips_duplicate(self):
        """Importing the same order_id twice creates only one sale.order."""
        data_row = self._make_row(
            order_id='DUP_IMP_001',
            transaction_id='DUP_TXN_001',
            product_name='Duplicate Test',
        )
        xlsx_bytes = self._build_xlsx_bytes([data_row])

        # First import
        wizard1 = self._create_wizard(xlsx_bytes)
        wizard1.action_import()

        orders_after_first = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'DUP_IMP_001')])
        self.assertEqual(len(orders_after_first), 1)

        # Second import with same order_id
        wizard2 = self._create_wizard(xlsx_bytes)
        wizard2.action_import()

        orders_after_second = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'DUP_IMP_001')])
        self.assertEqual(
            len(orders_after_second), 1,
            'Duplicate order should not be created')
        self.assertIn('1 skipped', wizard2.status_message)

    def test_import_multiple_lines_same_order(self):
        """Multiple rows with the same ORDER_ID create one order with
        multiple lines."""
        row1 = self._make_row(
            order_id='MULTI_001',
            transaction_id='MULTI_TXN_A',
            product_name='Product A',
            price='10.00',
        )
        row2 = self._make_row(
            order_id='MULTI_001',
            transaction_id='MULTI_TXN_B',
            product_name='Product B',
            price='15.00',
        )
        xlsx_bytes = self._build_xlsx_bytes([row1, row2])
        wizard = self._create_wizard(xlsx_bytes)
        wizard.action_import()

        orders = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'MULTI_001')])
        self.assertEqual(len(orders), 1, 'Should create exactly one order')
        # Two product lines + one Etsy Shipping line (shipping_cost=3.96 from
        # _make_row); the shipping line is added once per order, not per row.
        self.assertEqual(
            len(orders.order_line), 3,
            'Order should have two product lines plus one shipping line')

    def test_import_empty_file(self):
        """An empty xlsx produces a status message, no orders."""
        import openpyxl
        wb = openpyxl.Workbook()
        # Leave the sheet completely empty
        buf = io.BytesIO()
        wb.save(buf)
        wizard = self._create_wizard(buf.getvalue())
        wizard.action_import()
        self.assertIn('empty', (wizard.status_message or '').lower())

    def test_import_no_file(self):
        """Wizard with no file upload reports the issue."""
        wizard = self.env['etsy.import.orders.wizard'].create({
            'excel_file': False,
            'excel_filename': '',
        })
        # The field is required, so we bypass by writing directly
        wizard.write({'excel_file': False})
        wizard.action_import()
        self.assertIn('No file', wizard.status_message or '')
