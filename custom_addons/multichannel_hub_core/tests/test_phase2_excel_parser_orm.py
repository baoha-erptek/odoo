"""Phase 2 ORM tests for P-HUB-XLS-PARSE-SERVICE.

Uses in-memory xlsx (openpyxl.Workbook → BytesIO) — no fixture file needed.
"""

import io

import openpyxl

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_core.services.excel_catalog_parser import (
    parse, _fingerprint_headers,
)


def _make_xlsx(sheet_specs):
    """Build an xlsx in memory.

    Args:
        sheet_specs: dict[str, list[list]] — sheet_name → list of rows
            (first row is headers).

    Returns:
        bytes of the xlsx.
    """
    wb = openpyxl.Workbook()
    default_ws = wb.active
    wb.remove(default_ws)
    for sheet_name, rows in sheet_specs.items():
        ws = wb.create_sheet(sheet_name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestExcelCatalogParserORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['product.catalog.import.run']
        cls.Line = cls.env['product.catalog.import.line']
        cls.Fingerprint = cls.env['product.catalog.sheet.fingerprint']

    def _make_run(self):
        return self.Run.create({
            'mode': 'dry_run', 'source_kind': 'manual_upload',
            'source_path': '/tmp/test.xlsx',
        })

    def _approve_fingerprint(self, sheet_name, headers):
        fp_sha = _fingerprint_headers(headers)
        fp = self.Fingerprint.create({
            'sheet_name': sheet_name,
            'column_headers_sha256': fp_sha,
            'column_headers_preview': ' | '.join(h.lower() for h in headers),
            'approved': True,
        })
        return fp

    # ------------------------------------------------------------------
    # Unknown-fingerprint sheet → quarantined for admin approval
    # ------------------------------------------------------------------

    def test_unknown_fingerprint_quarantines_sheet(self):
        run = self._make_run()
        xlsx = _make_xlsx({
            'Accessories': [
                ['SKU', 'Product Name', 'Price USD'],
                ['NEW-1', 'New Thing', 19.99],
            ],
        })
        summary = parse(self.env, run, xlsx)
        self.assertEqual(summary['unknown_fingerprint_sheets'], 1)
        self.assertEqual(summary['rows_emitted'], 0)
        # Fingerprint row was created for admin approval
        fp = self.Fingerprint.search([('sheet_name', '=', 'Accessories')], limit=1)
        self.assertTrue(fp)
        self.assertFalse(fp.approved)
        # An error line marker was written
        err_line = self.Line.search([
            ('run_id', '=', run.id),
            ('sheet_name', '=', 'Accessories'),
            ('row_number', '=', 0),
        ], limit=1)
        self.assertEqual(err_line.state, 'error')
        self.assertEqual(err_line.error_kind, 'parse')

    # ------------------------------------------------------------------
    # Approved fingerprint → rows emitted
    # ------------------------------------------------------------------

    def test_approved_fingerprint_emits_rows(self):
        run = self._make_run()
        headers = ['SKU', 'Product Name', 'Price USD', 'Shipping Fee']
        self._approve_fingerprint('Accessories', headers)
        xlsx = _make_xlsx({
            'Accessories': [
                headers,
                ['MUG-1', 'Coffee Mug', 19.99, 2.5],
                ['RDS-1', 'Ring Dish', 29.99, 3.0],
            ],
        })
        summary = parse(self.env, run, xlsx)
        self.assertEqual(summary['sheets_parsed'], 1)
        self.assertEqual(summary['rows_emitted'], 2)
        self.assertEqual(summary['rows_error'], 0)
        lines = self.Line.search([
            ('run_id', '=', run.id),
            ('sheet_name', '=', 'Accessories'),
            ('row_number', '>', 0),
        ])
        self.assertEqual(len(lines), 2)
        mug = lines.filtered(lambda l: l.sku == 'MUG-1')
        self.assertEqual(mug.name, 'Coffee Mug')
        self.assertAlmostEqual(mug.price_usd, 19.99, places=2)
        self.assertAlmostEqual(mug.shipping_fee, 2.5, places=2)

    # ------------------------------------------------------------------
    # Existing-but-unapproved fingerprint → reject
    # ------------------------------------------------------------------

    def test_existing_unapproved_fingerprint_rejects(self):
        run = self._make_run()
        headers = ['SKU', 'Product Name']
        # Create UNapproved fingerprint up-front
        self.Fingerprint.create({
            'sheet_name': 'Accessories',
            'column_headers_sha256': _fingerprint_headers(headers),
            'column_headers_preview': 'sku | product name',
            'approved': False,
        })
        xlsx = _make_xlsx({
            'Accessories': [headers, ['X-1', 'name']],
        })
        summary = parse(self.env, run, xlsx)
        self.assertEqual(summary['rows_emitted'], 0)
        self.assertEqual(summary['rows_error'], 1)
        err = self.Line.search([
            ('run_id', '=', run.id), ('state', '=', 'error'),
        ], limit=1)
        self.assertIn('not approved', err.error_message)

    # ------------------------------------------------------------------
    # Multiple sheets — one approved, one not
    # ------------------------------------------------------------------

    def test_multi_sheet_partial_approval(self):
        run = self._make_run()
        approved_hdr = ['SKU', 'Product Name', 'Price USD']
        self._approve_fingerprint('Mugs', approved_hdr)
        xlsx = _make_xlsx({
            'Mugs': [approved_hdr, ['MUG-A', 'Mug A', 9.99]],
            'NewSheet': [['Foo', 'Bar'], ['x', 'y']],
        })
        summary = parse(self.env, run, xlsx)
        self.assertEqual(summary['sheets_parsed'], 1, "only Mugs parsed")
        self.assertEqual(summary['rows_emitted'], 1)
        self.assertEqual(summary['unknown_fingerprint_sheets'], 1,
                          "NewSheet quarantined for approval")

    # ------------------------------------------------------------------
    # Blank rows skipped
    # ------------------------------------------------------------------

    def test_blank_rows_skipped(self):
        run = self._make_run()
        headers = ['SKU', 'Product Name']
        self._approve_fingerprint('Accessories', headers)
        xlsx = _make_xlsx({
            'Accessories': [
                headers,
                ['A-1', 'first'],
                [None, None],  # blank
                ['A-2', 'second'],
            ],
        })
        summary = parse(self.env, run, xlsx)
        self.assertEqual(summary['rows_emitted'], 2)

    # ------------------------------------------------------------------
    # Type errors on non-required fields (parse hardens)
    # ------------------------------------------------------------------

    def test_invalid_price_defaults_to_zero(self):
        run = self._make_run()
        headers = ['SKU', 'Price USD']
        self._approve_fingerprint('Accessories', headers)
        xlsx = _make_xlsx({
            'Accessories': [headers, ['BAD-1', 'not-a-number']],
        })
        summary = parse(self.env, run, xlsx)
        self.assertEqual(summary['rows_emitted'], 1)
        line = self.Line.search([
            ('run_id', '=', run.id), ('sku', '=', 'BAD-1'),
        ], limit=1)
        self.assertEqual(line.price_usd, 0.0)
