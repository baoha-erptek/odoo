"""P1-DESIGN-AUTO-GDRIVE — cron-driven approved → GDrive promotion (Slice 2).

Phase 1 (DB) + Phase 2 (ORM) tests pinning the contract:
  - cron `cron_design_file_gdrive_sync` registered, calls
    `design.file._cron_sync_approved_to_gdrive`, runs as base.user_root.
  - ICP `multichannel_hub.design_gdrive_auto_sync_enabled` defaults True.
  - ICP `multichannel_hub.design_file_default_gdrive_folder_id` may be unset
    (cron skips silently when missing).
  - `synced_to_gdrive_at` Datetime field exists, stamped on promotion.
  - Cron picks state='approved' AND storage_mode='small' AND design_file IS
    NOT NULL AND gdrive_file_id IS NULL; uploads via gdrive_uploader; flips
    storage_mode→'gdrive', stamps gdrive_file_id + gdrive_folder_id.
  - Killswitch off → cron is a no-op.
  - Idempotent: re-running after promotion is a no-op (gdrive_file_id set).
  - approved-but-no-blob → skipped (storage_mode='url' has no blob to upload).
"""
import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesignAutoGdrivePhase1DB(TransactionCase):
    """Phase 1 — cron + ICP + schema sanity."""

    def test_cron_registered(self):
        cron = self.env.ref(
            'multichannel_hub_core.cron_design_file_gdrive_sync',
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "Auto-GDrive sync cron not registered.")
        self.assertEqual(cron.model_id.model, 'design.file')
        self.assertIn('_cron_sync_approved_to_gdrive', cron.code)
        # System-maintenance job: must run as root, not a salesman whose
        # record rules might silently filter approved files.
        self.assertEqual(cron.user_id, self.env.ref('base.user_root'))

    def test_synced_to_gdrive_at_field_exists(self):
        df = self.env['design.file']
        self.assertIn('synced_to_gdrive_at', df._fields)
        self.assertEqual(df._fields['synced_to_gdrive_at'].type, 'datetime')


@tagged('post_install', '-at_install')
class TestDesignAutoGdrivePhase2ORM(TransactionCase):
    """Phase 2 — cron behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({'name': 'AGD Buyer'})
        cls.product = cls.env['product.product'].create({
            'name': 'AGD Product', 'list_price': 1.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id, 'product_uom_qty': 1,
            })],
        })
        # Provide a default folder so the cron can target somewhere.
        cls.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.design_file_default_gdrive_folder_id',
            '1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789Folder',
        )

    def _make_approved_small_file(self, name='approved-small'):
        """Create an approved design.file in storage_mode='small' with blob."""
        # ~64 bytes — well under the 10 MB cap.
        blob = base64.b64encode(b"x" * 64)
        df = self.env['design.file'].with_context(
            bypass_design_state_guard=True,
        ).create({
            'name': name,
            'order_id': self.order.id,
            'storage_mode': 'small',
            'design_file': blob,
            'file_name': f'{name}.png',
            'file_size': 64,
            'state': 'approved',
        })
        return df.with_env(df.env(context={}))

    def test_cron_promotes_approved_small_to_gdrive(self):
        df = self._make_approved_small_file()
        with patch(
            'odoo.addons.multichannel_hub_core.services.gdrive_uploader'
            '.GdriveUploader.upload_file',
            return_value={
                'file_id': 'GDRIVE_ID_123',
                'web_view_link': 'https://drive.google.com/file/d/GDRIVE_ID_123/view',
                'error': None,
            },
        ) as mock_upload:
            self.env['design.file']._cron_sync_approved_to_gdrive()
        df.invalidate_recordset()
        self.assertEqual(df.storage_mode, 'gdrive')
        self.assertEqual(df.gdrive_file_id, 'GDRIVE_ID_123')
        self.assertEqual(df.gdrive_folder_id, '1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789Folder')
        self.assertTrue(df.synced_to_gdrive_at)
        mock_upload.assert_called_once()

    def test_cron_killswitch_disables_promotion(self):
        df = self._make_approved_small_file()
        self.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.design_gdrive_auto_sync_enabled', 'False',
        )
        try:
            with patch(
                'odoo.addons.multichannel_hub_core.services.gdrive_uploader'
                '.GdriveUploader.upload_file',
            ) as mock_upload:
                self.env['design.file']._cron_sync_approved_to_gdrive()
            mock_upload.assert_not_called()
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'multichannel_hub.design_gdrive_auto_sync_enabled', 'True',
            )
        df.invalidate_recordset()
        self.assertEqual(df.storage_mode, 'small')
        self.assertFalse(df.gdrive_file_id)

    def test_cron_idempotent_after_promotion(self):
        df = self._make_approved_small_file()
        with patch(
            'odoo.addons.multichannel_hub_core.services.gdrive_uploader'
            '.GdriveUploader.upload_file',
            return_value={
                'file_id': 'GDRIVE_ID_FIRST',
                'web_view_link': 'https://drive.google.com/file/d/GDRIVE_ID_FIRST/view',
                'error': None,
            },
        ) as mock_upload:
            self.env['design.file']._cron_sync_approved_to_gdrive()
            self.assertEqual(mock_upload.call_count, 1)
            # Re-run: should not re-upload the same file.
            self.env['design.file']._cron_sync_approved_to_gdrive()
            self.assertEqual(
                mock_upload.call_count, 1,
                "Cron must not re-upload files already promoted to gdrive.",
            )

    def test_cron_skips_approved_url_mode(self):
        """URL-mode files (no local blob) must be skipped."""
        df = self.env['design.file'].with_context(
            bypass_design_state_guard=True,
        ).create({
            'name': 'url-only',
            'order_id': self.order.id,
            'storage_mode': 'url',
            'file_url': 'https://drive.example/d/foo',
            'state': 'approved',
        })
        with patch(
            'odoo.addons.multichannel_hub_core.services.gdrive_uploader'
            '.GdriveUploader.upload_file',
        ) as mock_upload:
            self.env['design.file']._cron_sync_approved_to_gdrive()
        mock_upload.assert_not_called()
        df.invalidate_recordset()
        self.assertEqual(df.storage_mode, 'url')

    def test_cron_rejects_malformed_folder_id(self):
        """Defense-in-depth: ICP with bogus characters must not flow to Drive."""
        df = self._make_approved_small_file('bad-folder')
        self.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.design_file_default_gdrive_folder_id',
            "bogus' OR 1=1; DROP TABLE",
        )
        try:
            with patch(
                'odoo.addons.multichannel_hub_core.services.gdrive_uploader'
                '.GdriveUploader.upload_file',
            ) as mock_upload:
                self.env['design.file']._cron_sync_approved_to_gdrive()
            mock_upload.assert_not_called()
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'multichannel_hub.design_file_default_gdrive_folder_id',
                '1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789Folder',
            )
        df.invalidate_recordset()
        self.assertEqual(df.storage_mode, 'small')

    def test_cron_skips_when_default_folder_unset(self):
        """If no default folder configured, cron must no-op (do not crash)."""
        self.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.design_file_default_gdrive_folder_id', '',
        )
        df = self._make_approved_small_file('no-folder')
        try:
            with patch(
                'odoo.addons.multichannel_hub_core.services.gdrive_uploader'
                '.GdriveUploader.upload_file',
            ) as mock_upload:
                self.env['design.file']._cron_sync_approved_to_gdrive()
            mock_upload.assert_not_called()
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'multichannel_hub.design_file_default_gdrive_folder_id',
                '1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789Folder',
            )
        df.invalidate_recordset()
        self.assertEqual(df.storage_mode, 'small')
