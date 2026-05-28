"""Phase 2 ORM tests for P-HUB-XLS-GDRIVE-FETCHER cron branch."""

import base64
import io
from unittest.mock import patch

import openpyxl

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_core.services.excel_catalog_parser import (
    _fingerprint_headers,
)


def _make_xlsx(headers, rows):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet('GDriveSheet')
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestCatalogGdriveFetcherORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['product.catalog.import.run']
        cls.Fingerprint = cls.env['product.catalog.sheet.fingerprint']
        cls.ICP = cls.env['ir.config_parameter'].sudo()

    def setUp(self):
        super().setUp()
        self.ICP.set_param('multichannel_hub.catalog_cron_gdrive_file_id', '')
        self.ICP.set_param('multichannel_hub.catalog_cron_source_path', '')

    def test_no_icp_configured_returns_false(self):
        result = self.Run._cron_run_catalog_sync()
        self.assertFalse(result)

    def test_gdrive_branch_takes_precedence(self):
        headers = ['SKU', 'Product Name']
        self.Fingerprint.create({
            'sheet_name': 'GDriveSheet',
            'column_headers_sha256': _fingerprint_headers(headers),
            'column_headers_preview': 'sku | product name',
            'approved': True,
        })
        self.ICP.set_param(
            'multichannel_hub.catalog_cron_gdrive_file_id', 'gd-test-1',
        )
        self.ICP.set_param(
            'multichannel_hub.catalog_cron_source_path', '/tmp/should-not-be-used.xlsx',
        )
        xlsx_bytes = _make_xlsx(headers, [['GD-1', 'GDrive Product']])
        with patch(
            'odoo.addons.multichannel_hub_core.services.gdrive_uploader_helper.'
            'fetch_gdrive_bytes',
            return_value=xlsx_bytes,
        ) as fetch_mock:
            result = self.Run._cron_run_catalog_sync()
        self.assertTrue(result)
        fetch_mock.assert_called_once()
        # A run row was created with source_kind=gdrive
        run = self.Run.search([
            ('source_kind', '=', 'gdrive'),
            ('source_path', '=', 'gd-test-1'),
        ], limit=1)
        self.assertTrue(run)

    def test_gdrive_fetch_failure_returns_false(self):
        self.ICP.set_param(
            'multichannel_hub.catalog_cron_gdrive_file_id', 'gd-bad',
        )
        with patch(
            'odoo.addons.multichannel_hub_core.services.gdrive_uploader_helper.'
            'fetch_gdrive_bytes',
            side_effect=RuntimeError('boom'),
        ):
            result = self.Run._cron_run_catalog_sync()
        self.assertFalse(result)
