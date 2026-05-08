"""Regression: GdriveUploader must pass supportsAllDrives=True so that target
folders living inside a Google Workspace Shared Drive are visible.

Without the flag, the Drive API returns HTTP 404 "File not found" even when
the service account is granted Editor on the folder. The 2026-05-08 staging
probe found folder 1AZRhXHHt... (driveId 0ABK9vk_...) lives in a Shared
Drive and was 404'ing every upload attempt.

These tests use unittest.mock to assert the kwarg is passed; no live network
or shop fixtures (which would pull in the broken setUpClass chain in the
sibling test_gdrive_upload_orm.py).

Skipped on environments without google-api-python-client installed (e.g.
the local dev container; staging has the libs and runs them as part of the
deploy verify).
"""
import unittest
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

try:
    import googleapiclient  # noqa: F401
    import google.oauth2  # noqa: F401
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False


@tagged('post_install', '-at_install')
@unittest.skipUnless(
    _GOOGLE_AVAILABLE,
    "google-api-python-client not installed in this environment; run on staging.",
)
class TestGdriveSharedDriveSupport(TransactionCase):
    """Assert GdriveUploader passes supportsAllDrives=True on Drive API calls."""

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_upload_file_passes_supports_all_drives(self, mock_creds, mock_build):
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files.return_value.create.return_value.execute.return_value = {
            'id': 'sd_file_id',
            'webViewLink': 'https://drive.google.com/file/d/sd_file_id/view',
        }

        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import (
            GdriveUploader,
        )
        GdriveUploader().upload_file(
            file_blob=b'shared-drive-payload',
            file_name='design.pdf',
            folder_id='shared_drive_folder_id',
        )

        create_kwargs = mock_service.files.return_value.create.call_args.kwargs
        self.assertTrue(
            create_kwargs.get('supportsAllDrives'),
            "files().create() must pass supportsAllDrives=True for Shared Drive support.",
        )

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_ensure_shop_folder_passes_supports_all_drives(self, mock_creds, mock_build):
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        # Simulate "folder not found" path so we exercise both list and create.
        mock_service.files.return_value.list.return_value.execute.return_value = {'files': []}
        mock_service.files.return_value.create.return_value.execute.return_value = {'id': 'new_folder_id'}

        # Lightweight stub mimicking the etsy.shop interface ensure_shop_folder
        # depends on (read x_gdrive_design_folder_id, write via .sudo()).
        class _StubShop:
            id = 1
            name = 'TestShop'
            x_gdrive_design_folder_id = False
            def sudo(self):
                return self

        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import (
            GdriveUploader,
        )
        GdriveUploader().ensure_shop_folder(_StubShop())

        list_kwargs = mock_service.files.return_value.list.call_args.kwargs
        self.assertTrue(
            list_kwargs.get('supportsAllDrives'),
            "files().list() must pass supportsAllDrives=True.",
        )
        self.assertTrue(
            list_kwargs.get('includeItemsFromAllDrives'),
            "files().list() must pass includeItemsFromAllDrives=True.",
        )
        create_kwargs = mock_service.files.return_value.create.call_args.kwargs
        self.assertTrue(
            create_kwargs.get('supportsAllDrives'),
            "folder-create files().create() must pass supportsAllDrives=True.",
        )
