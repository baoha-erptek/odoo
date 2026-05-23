"""Phase 1 DB tests — Spec 010 catalog-sync ICP defaults loaded."""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1CatalogICPDB(TransactionCase):

    def test_catalog_excel_max_mb_default(self):
        v = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.catalog_excel_max_mb',
        )
        self.assertEqual(v, '200')

    def test_catalog_max_images_per_run_default(self):
        v = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.catalog_max_images_per_run',
        )
        self.assertEqual(v, '500')

    def test_large_file_threshold_bytes_default(self):
        v = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.large_file_threshold_bytes',
        )
        self.assertEqual(v, '10485760')
