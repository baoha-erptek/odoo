"""Tests for header-based column mapping in the Etsy import wizard.

Spec 002 US5 T031–T034. These tests verify the wizard's ability to handle
dynamic header mapping, missing headers, and case-insensitive normalization.

Currently blocks 4 inherited failing tests from 002 MVP:
  - test_import_creates_order_with_auto_confirm
  - test_import_multiple_lines_same_order
  - test_import_skips_duplicate
  - test_import_reordered_columns
"""
import base64
import io

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from ..wizards.import_orders_wizard import (
    _cell_str,
    _parse_eur_price,
    _parse_quantity,
)


class TestImportWizardHeaderMapping(TransactionCase):
    """RED phase tests for header-based column mapping (T031–T034)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    # =====================================================================
    # Helper methods (factory pattern)
    # =====================================================================

    def _build_xlsx_bytes(self, rows):
        """Create a minimal .xlsx file in memory from a list of row tuples.

        Each row is a tuple of cell values. Returns raw bytes
        (not base64-encoded).
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
                  date='2025-06-05', column_order=None):
        """Build a row tuple with values positioned per column_order.

        Args:
            order_id, transaction_id, etc.: Values to populate
            column_order: Optional list of column names in desired order.
                         If None, uses default 34-column layout.

        Returns:
            A tuple of 34 elements in the order specified by column_order
            or the default positional layout.
        """
        default_order = [
            'TRANSACTION_ID', 'IMG_URL', 'IMG', 'DATE', 'NOTE_FROM_BUYER',
            'GIFT_MESSAGE', 'PERSONALISATION', 'SKU', 'SHOP', 'ORDER_ID',
            'SHIPPING_NAME', 'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2',
            'SHIPPING_CITY', 'SHIPPING_STATE', 'SHIPPING_ZIPCODE',
            'SHIPPING_COUNTRY', 'SHIPPING_PHONE', 'SHIPPING_EMAIL',
            'PRODUCT_NAME', 'OPTION', 'COLOR', 'SIZE', 'SIDE',
            'FACE_MASK_SIZE', 'QUANTITY', 'DESIGN_LINK_FRONT',
            'DESIGN_LINK_BACK', 'SHIPPING_SERVICE', 'PROCESSING_TIME',
            'SHIPPING_COST', 'PRICE', 'DISCOUNT_CODE', 'SUBTOTAL',
        ]

        if column_order is None:
            column_order = default_order

        # Build value map for easy lookup
        value_map = {
            'TRANSACTION_ID': transaction_id,
            'IMG_URL': '',
            'IMG': '',
            'DATE': date,
            'NOTE_FROM_BUYER': 'Test note',
            'GIFT_MESSAGE': '',
            'PERSONALISATION': 'Custom engraving',
            'SKU': 'SKU001',
            'SHOP': shop,
            'ORDER_ID': order_id,
            'SHIPPING_NAME': shipping_name,
            'SHIPPING_ADDRESS1': '123 Test St',
            'SHIPPING_ADDRESS2': '',
            'SHIPPING_CITY': 'Test City',
            'SHIPPING_STATE': 'CA',
            'SHIPPING_ZIPCODE': '90210',
            'SHIPPING_COUNTRY': 'US',
            'SHIPPING_PHONE': '555-1234',
            'SHIPPING_EMAIL': shipping_email,
            'PRODUCT_NAME': product_name,
            'OPTION': '',
            'COLOR': 'Gold',
            'SIZE': 'Small',
            'SIDE': '',
            'FACE_MASK_SIZE': '',
            'QUANTITY': quantity,
            'DESIGN_LINK_FRONT': '',
            'DESIGN_LINK_BACK': '',
            'SHIPPING_SERVICE': 'Standard',
            'PROCESSING_TIME': '5-7 days',
            'SHIPPING_COST': '3.96',
            'PRICE': price,
            'DISCOUNT_CODE': '',
            'SUBTOTAL': '19.70',
        }

        # Build row in column_order sequence. Normalize the column name
        # the same way the wizard does, so mixed-case test headers still
        # resolve to the right value_map entry.
        def _norm(col):
            return col.strip().upper().replace(' ', '_') if col else ''
        row = [value_map.get(_norm(col), '') for col in column_order]
        # Pad to 34 if needed
        while len(row) < 34:
            row.append('')
        return tuple(row[:34])

    def _create_wizard(self, xlsx_bytes):
        """Create the wizard record with a base64-encoded xlsx attachment."""
        encoded = base64.b64encode(xlsx_bytes).decode('ascii')
        return self.env['etsy.import.orders.wizard'].create({
            'excel_file': encoded,
            'excel_filename': 'test_orders.xlsx',
        })

    # =====================================================================
    # T034: Header reordering test
    # =====================================================================

    def test_header_reordering_columns_mapped_correctly(self):
        """Columns in non-default order map to correct values.

        RED: This test will FAIL because the wizard uses fixed _COL_*
        constants instead of reading header row to build a mapping dict.

        Reorder columns: put PRODUCT_NAME first, PRICE before QUANTITY,
        swap other positions. Verify the import still succeeds and
        extracted values match the reordered layout.
        """
        # Reordered header: PRODUCT_NAME, TRANSACTION_ID, ORDER_ID, PRICE,
        # QUANTITY, plus all others in original order
        reordered_header = (
            'PRODUCT_NAME',          # col 0 (was 19)
            'TRANSACTION_ID',        # col 1 (was 0)
            'ORDER_ID',              # col 2 (was 9)
            'PRICE',                 # col 3 (was 31)
            'QUANTITY',              # col 4 (was 25)
            'IMG_URL', 'IMG', 'DATE', 'NOTE_FROM_BUYER', 'GIFT_MESSAGE',
            'PERSONALISATION', 'SKU', 'SHOP', 'SHIPPING_NAME',
            'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2', 'SHIPPING_CITY',
            'SHIPPING_STATE', 'SHIPPING_ZIPCODE', 'SHIPPING_COUNTRY',
            'SHIPPING_PHONE', 'SHIPPING_EMAIL', 'OPTION', 'COLOR', 'SIZE',
            'SIDE', 'FACE_MASK_SIZE', 'DESIGN_LINK_FRONT',
            'DESIGN_LINK_BACK', 'SHIPPING_SERVICE', 'PROCESSING_TIME',
            'SHIPPING_COST', 'DISCOUNT_CODE', 'SUBTOTAL',
        )

        # Build data row in reordered layout
        data_row = self._make_row(
            order_id='REORD_001',
            transaction_id='REORD_TXN_001',
            product_name='Reordered Product',
            price='49.99',
            quantity='3',
            column_order=list(reordered_header),
        )

        xlsx_bytes = self._build_xlsx_bytes([reordered_header, data_row])
        wizard = self._create_wizard(xlsx_bytes)
        wizard.action_import()

        # Verify order was created
        order = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'REORD_001')], limit=1)
        self.assertTrue(order, 'Order should be created with reordered columns')

        # Verify line item has correct values from reordered positions
        line = order.order_line[0]
        self.assertEqual(
            line.product_id.name, 'Reordered Product',
            'Product name should match data from reordered col 0')
        self.assertAlmostEqual(
            line.price_unit, 49.99,
            msg='Price should match data from reordered col 3')
        self.assertEqual(
            line.product_uom_qty, 3,
            msg='Quantity should match data from reordered col 4')
        self.assertEqual(
            line.etsy_transaction_id, 'REORD_TXN_001',
            msg='Transaction ID should match data from reordered col 1')

    # =====================================================================
    # Missing required header test
    # =====================================================================

    def test_missing_required_header_raises_user_error(self):
        """Missing required header (e.g., PRODUCT_NAME) raises UserError.

        RED: This test will FAIL because the wizard does not validate
        required headers. No exception is currently raised.

        Build xlsx with PRODUCT_NAME omitted from header. Call
        wizard.action_import(). Expect UserError.

        Required headers per spec: TRANSACTION_ID, ORDER_ID, PRODUCT_NAME,
        PRICE, QUANTITY.
        """
        # Header missing PRODUCT_NAME
        incomplete_header = (
            'TRANSACTION_ID', 'IMG_URL', 'IMG', 'DATE', 'NOTE_FROM_BUYER',
            'GIFT_MESSAGE', 'PERSONALISATION', 'SKU', 'SHOP', 'ORDER_ID',
            'SHIPPING_NAME', 'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2',
            'SHIPPING_CITY', 'SHIPPING_STATE', 'SHIPPING_ZIPCODE',
            'SHIPPING_COUNTRY', 'SHIPPING_PHONE', 'SHIPPING_EMAIL',
            # PRODUCT_NAME OMITTED
            'OPTION', 'COLOR', 'SIZE', 'SIDE', 'FACE_MASK_SIZE',
            'QUANTITY', 'DESIGN_LINK_FRONT', 'DESIGN_LINK_BACK',
            'SHIPPING_SERVICE', 'PROCESSING_TIME', 'SHIPPING_COST',
            'PRICE', 'DISCOUNT_CODE', 'SUBTOTAL',
        )

        data_row = self._make_row()
        # Adjust to 33-element tuple (missing one column)
        data_row_short = data_row[:19] + data_row[20:]
        xlsx_bytes = self._build_xlsx_bytes([incomplete_header, data_row_short])
        wizard = self._create_wizard(xlsx_bytes)

        with self.assertRaises(UserError):
            wizard.action_import()

    # =====================================================================
    # Missing optional header test (T033 prerequisite)
    # =====================================================================

    def test_missing_optional_header_imports_with_warning(self):
        """Missing optional header (e.g., DESIGN_LINK_FRONT) warns.

        RED: This test will FAIL because warning_count and
        validation_notes fields do not yet exist on the wizard model
        (see T033).

        Build xlsx without DESIGN_LINK_FRONT (optional). Import.
        Verify order created AND warning_count >= 1 OR validation_notes
        is truthy.
        """
        # Header missing DESIGN_LINK_FRONT (optional)
        optional_missing_header = (
            'TRANSACTION_ID', 'IMG_URL', 'IMG', 'DATE', 'NOTE_FROM_BUYER',
            'GIFT_MESSAGE', 'PERSONALISATION', 'SKU', 'SHOP', 'ORDER_ID',
            'SHIPPING_NAME', 'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2',
            'SHIPPING_CITY', 'SHIPPING_STATE', 'SHIPPING_ZIPCODE',
            'SHIPPING_COUNTRY', 'SHIPPING_PHONE', 'SHIPPING_EMAIL',
            'PRODUCT_NAME', 'OPTION', 'COLOR', 'SIZE', 'SIDE',
            'FACE_MASK_SIZE', 'QUANTITY',
            # DESIGN_LINK_FRONT OMITTED (optional)
            'DESIGN_LINK_BACK', 'SHIPPING_SERVICE', 'PROCESSING_TIME',
            'SHIPPING_COST', 'PRICE', 'DISCOUNT_CODE', 'SUBTOTAL',
        )

        data_row = self._make_row(order_id='OPT_001', transaction_id='OPT_TXN')
        # Adjust to 33-element tuple
        data_row_short = data_row[:26] + data_row[27:]
        xlsx_bytes = self._build_xlsx_bytes([optional_missing_header, data_row_short])
        wizard = self._create_wizard(xlsx_bytes)
        wizard.action_import()

        # Order should be created
        order = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'OPT_001')], limit=1)
        self.assertTrue(order, 'Order created despite optional header missing')

        # Check for warning field (will exist after T033 implementation)
        has_warning = (
            hasattr(wizard, 'warning_count') and wizard.warning_count >= 1
        ) or (
            hasattr(wizard, 'validation_notes')
            and bool(wizard.validation_notes)
        )
        self.assertTrue(
            has_warning,
            'Wizard should track missing optional header as warning')

    # =====================================================================
    # Header normalization (case-insensitive, underscore/space handling)
    # =====================================================================

    def test_header_normalization_case_insensitive(self):
        """Headers with mixed case, spaces, and underscores normalize.

        RED: This test will FAIL because the wizard only checks if
        first_row[0].upper() is 'TRANSACTION_ID' or 'ID', and uses
        positional indexing for all other columns. No normalization
        logic exists.

        Build xlsx with headers like:
          - Transaction_Id (underscore, mixed case)
          - Order Id (space, mixed case)
          - product_name (lowercase)
          - PRICE (uppercase)
          - Quantity (title case)

        Import. Verify order created with correct values extracted.
        """
        mixed_case_header = (
            'Transaction_Id',        # Mixed: underscore + mixed case
            'IMG_URL', 'IMG', 'DATE', 'NOTE_FROM_BUYER', 'GIFT_MESSAGE',
            'PERSONALISATION', 'SKU', 'SHOP',
            'Order Id',              # Mixed: space + mixed case
            'SHIPPING_NAME', 'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2',
            'SHIPPING_CITY', 'SHIPPING_STATE', 'SHIPPING_ZIPCODE',
            'SHIPPING_COUNTRY', 'SHIPPING_PHONE', 'SHIPPING_EMAIL',
            'product_name',          # Lowercase
            'OPTION', 'COLOR', 'SIZE', 'SIDE', 'FACE_MASK_SIZE',
            'Quantity',              # Title case
            'DESIGN_LINK_FRONT', 'DESIGN_LINK_BACK', 'SHIPPING_SERVICE',
            'PROCESSING_TIME', 'SHIPPING_COST',
            'PRICE',                 # Uppercase
            'DISCOUNT_CODE', 'SUBTOTAL',
        )

        data_row = self._make_row(
            order_id='NORMCASE_001',
            transaction_id='NORMCASE_TXN',
            product_name='Normalized Test',
            price='29.99',
            quantity='2',
            column_order=list(mixed_case_header),
        )

        xlsx_bytes = self._build_xlsx_bytes([mixed_case_header, data_row])
        wizard = self._create_wizard(xlsx_bytes)
        wizard.action_import()

        # Verify order created
        order = self.env['sale.order'].search(
            [('etsy_order_id', '=', 'NORMCASE_001')], limit=1)
        self.assertTrue(
            order,
            'Order created despite mixed-case and space-formatted headers')

        # Verify line has correct data
        line = order.order_line[0]
        self.assertEqual(
            line.product_id.name, 'Normalized Test',
            'Product name extracted despite lowercase header')
        self.assertEqual(
            line.etsy_transaction_id, 'NORMCASE_TXN',
            'Transaction ID extracted despite underscore/mixed-case header')

    # =====================================================================
    # Sanity check: warning_count field exists (Phase 1 DB test, T033)
    # =====================================================================

    def test_warning_count_field_exists_and_defaults_zero(self):
        """warning_count and validation_notes fields exist with defaults.

        RED/Phase-1 sanity check: Verify the fields added in T033 exist
        on the wizard model, with correct defaults (0 and empty string).

        This test will PASS once T033 adds the fields, even if T031-T032
        implementation is incomplete.
        """
        wizard = self.env['etsy.import.orders.wizard'].create({
            'excel_file': base64.b64encode(
                self._build_xlsx_bytes([('TRANSACTION_ID',)])
            ).decode('ascii'),
            'excel_filename': 'check.xlsx',
        })

        # Check field existence and defaults
        self.assertTrue(
            hasattr(wizard, 'warning_count'),
            'warning_count field should exist (T033)')
        self.assertEqual(
            wizard.warning_count, 0,
            'warning_count should default to 0')

        self.assertTrue(
            hasattr(wizard, 'validation_notes'),
            'validation_notes field should exist (T033)')
        self.assertFalse(
            bool(wizard.validation_notes),
            'validation_notes should default to empty/falsy')
