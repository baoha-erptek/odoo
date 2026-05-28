"""Phase 2 ORM tests for P-HUB-XLS-CRON orchestrator
(product.catalog.import.run.run_parse_and_ingest).
"""

import io

import openpyxl

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_core.services.excel_catalog_parser import (
    _fingerprint_headers,
)


def _make_xlsx(sheet_name, rows):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(sheet_name)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestCatalogOrchestratorORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['product.catalog.import.run']
        cls.Template = cls.env['product.template']
        cls.Fingerprint = cls.env['product.catalog.sheet.fingerprint']

    def _approve_fingerprint(self, sheet_name, headers):
        return self.Fingerprint.create({
            'sheet_name': sheet_name,
            'column_headers_sha256': _fingerprint_headers(headers),
            'column_headers_preview': ' | '.join(h.lower() for h in headers),
            'approved': True,
        })

    def test_orchestrator_parses_then_upserts(self):
        headers = ['SKU', 'Product Name', 'Price USD']
        self._approve_fingerprint('Accessories', headers)
        xlsx = _make_xlsx('Accessories', [
            headers,
            ['ORCH-1', 'Coffee Mug', 19.99],
            ['ORCH-2', 'Ring Dish', 29.99],
        ])
        run = self.Run.create({
            'mode': 'commit', 'source_kind': 'manual_upload',
            'source_path': '/tmp/orch.xlsx',
        })
        result = run.run_parse_and_ingest(xlsx)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'imported')
        self.assertEqual(run.sheets_parsed, 1)
        self.assertGreaterEqual(run.rows_upserted, 2)
        # Templates were created
        self.assertTrue(self.Template.search([('default_code', '=', 'ORCH-1')]))
        self.assertTrue(self.Template.search([('default_code', '=', 'ORCH-2')]))

    def test_orchestrator_dry_run_marks_previewed(self):
        headers = ['SKU', 'Product Name']
        self._approve_fingerprint('DryRun', headers)
        xlsx = _make_xlsx('DryRun', [headers, ['DRY-1', 'Test']])
        run = self.Run.create({
            'mode': 'dry_run', 'source_kind': 'manual_upload',
            'source_path': '/tmp/dry.xlsx',
        })
        run.run_parse_and_ingest(xlsx)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'previewed')

    def test_orchestrator_records_file_size(self):
        headers = ['SKU']
        self._approve_fingerprint('S', headers)
        xlsx = _make_xlsx('S', [headers, ['S-1']])
        run = self.Run.create({
            'mode': 'commit', 'source_kind': 'manual_upload',
            'source_path': '/tmp/s.xlsx',
        })
        run.run_parse_and_ingest(xlsx)
        run.invalidate_recordset()
        self.assertGreater(run.file_size_bytes, 0)

    def test_orchestrator_corrupt_file_flips_to_error(self):
        run = self.Run.create({
            'mode': 'commit', 'source_kind': 'manual_upload',
            'source_path': '/tmp/bad.xlsx',
        })
        raised = False
        try:
            run.run_parse_and_ingest(b'not-an-xlsx')
        except Exception:
            raised = True
        self.assertTrue(raised)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'error')
