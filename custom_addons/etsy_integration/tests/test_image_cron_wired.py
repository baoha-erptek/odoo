"""P1-IMG-CRON-WIRE: Verify the orphan ImageDownloader.cron_download_pending_images
is reachable by an actual ir.cron record via a thin product.template wrapper.

Phase 1 (DB) checks the cron record landed by the data file; Phase 2 (ORM)
checks the wrapper method delegates to the existing service class.
"""
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install')
class TestImageCronWiredPhase1(TransactionCase):
    """DB-level introspection of the ir.cron seed."""

    def test_cron_xml_id_resolves(self):
        cron = self.env.ref(
            'etsy_integration.ir_cron_download_pending_etsy_images',
            raise_if_not_found=False,
        )
        self.assertTrue(cron, 'ir.cron seed must be loaded by the data file')

    def test_cron_points_at_product_template_model(self):
        cron = self.env.ref(
            'etsy_integration.ir_cron_download_pending_etsy_images')
        self.assertEqual(cron.model_id.model, 'product.template')

    def test_cron_state_is_code_calling_wrapper(self):
        cron = self.env.ref(
            'etsy_integration.ir_cron_download_pending_etsy_images')
        self.assertEqual(cron.state, 'code')
        self.assertIn('_cron_download_etsy_images', cron.code)

    def test_cron_active_by_default(self):
        cron = self.env.ref(
            'etsy_integration.ir_cron_download_pending_etsy_images')
        self.assertTrue(cron.active, 'Cron must ship active so backfill runs')


@tagged('at_install')
class TestImageCronWiredPhase2(TransactionCase):
    """ORM-level: wrapper method delegates to the ImageDownloader service."""

    def test_wrapper_invokes_image_downloader(self):
        """The cron wrapper must construct an ImageDownloader and call its
        cron_download_pending_images() method exactly once."""
        target = (
            'odoo.addons.etsy_integration.services.image_downloader'
            '.ImageDownloader.cron_download_pending_images'
        )
        with patch(target) as mock_cron:
            self.env['product.template']._cron_download_etsy_images()
            mock_cron.assert_called_once_with()

    def test_wrapper_no_op_when_no_pending_products(self):
        """With no Etsy products needing images the wrapper completes
        without raising; the underlying service handles the empty case."""
        # Sanity: nothing pending at this savepoint
        pending = self.env['product.template'].search([
            ('is_etsy_product', '=', True),
            ('image_1920', '=', False),
        ])
        self.assertFalse(pending, 'Test relies on no pending products')
        self.env['product.template']._cron_download_etsy_images()
