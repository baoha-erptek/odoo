"""Phase 2 ORM tests for P-HUB-IMAGES Excel image downloader."""

import base64
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_core.services.excel_catalog_image_downloader import (
    download_images_for_run,
)


_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx'
    b'\x9cc\xfc\xcf\xc0\x00\x00\x00\x03\x00\x01a\xc2C\x8f\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _mock_response(content=_PNG, status=200):
    r = MagicMock()
    r.status_code = status
    r.content = content
    r.raise_for_status = MagicMock()
    return r


@tagged('post_install', '-at_install')
class TestExcelCatalogImageDownloaderORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['product.catalog.import.run']
        cls.Line = cls.env['product.catalog.import.line']
        cls.Template = cls.env['product.template']

    def _setup(self, image_url='https://example.com/a.png'):
        run = self.Run.create({
            'mode': 'commit', 'source_kind': 'manual_upload',
            'source_path': '/tmp/x.xlsx',
        })
        tmpl = self.Template.create({
            'name': 'Image Test', 'default_code': 'IMG-DL-1',
        })
        line = self.Line.create({
            'run_id': run.id, 'sheet_name': 'S', 'row_number': 1,
            'sku': 'IMG-DL-1', 'state': 'upserted',
            'target_product_id': tmpl.id,
            'image_1_ref': image_url,
        })
        return run, tmpl, line

    def test_downloads_https_image(self):
        run, tmpl, line = self._setup()
        with patch(
            'odoo.addons.multichannel_hub_core.services.'
            'excel_catalog_image_downloader.requests.get',
            return_value=_mock_response(),
        ):
            counters = download_images_for_run(self.env, run)
        self.assertEqual(counters['downloaded'], 1)
        tmpl.invalidate_recordset()
        self.assertTrue(tmpl.image_1920)

    def test_skipped_when_same_hash(self):
        run, tmpl, line = self._setup()
        tmpl.write({'image_1920': base64.b64encode(_PNG)})
        with patch(
            'odoo.addons.multichannel_hub_core.services.'
            'excel_catalog_image_downloader.requests.get',
            return_value=_mock_response(),
        ):
            counters = download_images_for_run(self.env, run)
        self.assertEqual(counters['skipped_unchanged'], 1)
        self.assertEqual(counters['downloaded'], 0)

    def test_non_https_url_rejected(self):
        run, tmpl, line = self._setup(image_url='http://example.com/insecure.png')
        with patch(
            'odoo.addons.multichannel_hub_core.services.'
            'excel_catalog_image_downloader.requests.get',
        ) as mock_get:
            counters = download_images_for_run(self.env, run)
        self.assertEqual(counters['failed'], 1)
        self.assertEqual(mock_get.call_count, 0)

    def test_http_failure_doesnt_break_run(self):
        run, tmpl, line = self._setup()
        import requests as real_requests
        with patch(
            'odoo.addons.multichannel_hub_core.services.'
            'excel_catalog_image_downloader.requests.get',
            side_effect=real_requests.exceptions.ConnectionError('boom'),
        ):
            counters = download_images_for_run(self.env, run)
        self.assertEqual(counters['failed'], 1)
        self.assertEqual(counters['downloaded'], 0)

    def test_cap_respected(self):
        run = self.Run.create({
            'mode': 'commit', 'source_kind': 'manual_upload',
            'source_path': '/tmp/x.xlsx',
        })
        # Create 3 lines + cap=2
        self.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.catalog_max_images_per_run', '2',
        )
        for i in range(3):
            tmpl = self.Template.create({
                'name': 'CapTest %s' % i, 'default_code': 'CAP-%s' % i,
            })
            self.Line.create({
                'run_id': run.id, 'sheet_name': 'S', 'row_number': i + 1,
                'sku': tmpl.default_code, 'state': 'upserted',
                'target_product_id': tmpl.id,
                'image_1_ref': 'https://example.com/%s.png' % i,
            })
        with patch(
            'odoo.addons.multichannel_hub_core.services.'
            'excel_catalog_image_downloader.requests.get',
            return_value=_mock_response(),
        ):
            counters = download_images_for_run(self.env, run)
        # Restore default
        self.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.catalog_max_images_per_run', '500',
        )
        self.assertEqual(counters['downloaded'], 2,
                          "cap=2 should stop after 2 downloads")
