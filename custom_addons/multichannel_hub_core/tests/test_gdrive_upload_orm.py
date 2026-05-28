"""
Phase 2 (ORM Unit Tests): GDrive upload service + wizard + constraints.

Tests verify business logic through Odoo ORM:
- GdriveUploader service (mocked Google Drive API): file upload, folder caching, error handling
- ThumbnailGenerator service: JPEG generation, corruption handling, size caps
- design.file model: GDrive fields, computed field, constraint C-DF-006
- design.file.upload.wizard: creation flow, validation, chatter posting
- RPC gate (FR-017): non-production user cannot call action_upload

Uses unittest.mock to avoid real Google Drive API calls.
"""

import base64
import logging
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestGdriveUploaderService(TransactionCase):
    """Test GdriveUploader service with mocked Google Drive API."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a test shop (from etsy_integration fixtures)
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop',
            'shop_id': 'test_shop_123',
            'api_key': 'test_key',
            'api_secret': 'test_secret',
        })

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_upload_file_success(self, mock_creds, mock_build):
        """Test successful GDrive file upload."""
        # Mock credentials and Drive service
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock Drive files().create() response
        mock_file_response = {
            'id': 'fake_file_id_123',
            'webViewLink': 'https://drive.google.com/file/d/fake_file_id_123/view',
        }
        mock_service.files.return_value.create.return_value.execute.return_value = mock_file_response

        # Import and test uploader (must import after mock patches are active)
        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader

        uploader = GdriveUploader()
        result = uploader.upload_file(
            file_blob=b'test_file_content',
            file_name='design.pdf',
            folder_id='folder_123'
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.get('file_id'), 'fake_file_id_123')
        self.assertEqual(
            result.get('web_view_link'),
            'https://drive.google.com/file/d/fake_file_id_123/view'
        )
        self.assertIsNone(result.get('error'))

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_upload_file_auth_failure(self, mock_creds, mock_build):
        """Test GDrive upload with auth failure."""
        import google.auth.exceptions

        # Mock credentials to raise auth error
        mock_creds.side_effect = google.auth.exceptions.DefaultCredentialsError(
            'Service account JSON not found'
        )

        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader

        uploader = GdriveUploader()
        result = uploader.upload_file(
            file_blob=b'test_file_content',
            file_name='design.pdf',
            folder_id='folder_123'
        )

        self.assertIsNotNone(result)
        self.assertIsNone(result.get('file_id'))
        self.assertIsNotNone(result.get('error'))
        self.assertIn('credentials', result.get('error', '').lower())

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_upload_file_quota_exceeded(self, mock_creds, mock_build):
        """Test GDrive upload with quota exceeded (403)."""
        from googleapiclient.errors import HttpError

        # Mock credentials and service
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock quota exceeded error
        http_error = HttpError(
            resp=MagicMock(status=403),
            content=b'Quota exceeded'
        )
        mock_service.files.return_value.create.return_value.execute.side_effect = http_error

        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader

        uploader = GdriveUploader()
        result = uploader.upload_file(
            file_blob=b'test_file_content',
            file_name='design.pdf',
            folder_id='folder_123'
        )

        self.assertIsNotNone(result)
        self.assertIsNone(result.get('file_id'))
        self.assertIsNotNone(result.get('error'))

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_ensure_shop_folder_creates_when_missing(self, mock_creds, mock_build):
        """Test folder creation when not found in Drive."""
        # Mock credentials and service
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock files.list() returns empty (folder not found)
        mock_service.files.return_value.list.return_value.execute.return_value = {
            'files': []
        }

        # Mock files.create() for folder creation
        mock_service.files.return_value.create.return_value.execute.return_value = {
            'id': 'new_folder_id_456'
        }

        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader

        uploader = GdriveUploader()
        folder_id = uploader.ensure_shop_folder(self.shop)

        self.assertEqual(folder_id, 'new_folder_id_456')

        # Verify cache field was set on shop
        self.shop.refresh()
        self.assertEqual(self.shop.x_gdrive_design_folder_id, 'new_folder_id_456')

    @patch('googleapiclient.discovery.build')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_ensure_shop_folder_cache_hit_skips_drive_call(self, mock_creds, mock_build):
        """Test that second call to ensure_shop_folder uses cache."""
        # Mock credentials and service
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Pre-populate cache on shop
        self.shop.x_gdrive_design_folder_id = 'cached_folder_id_789'

        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader

        uploader = GdriveUploader()
        folder_id = uploader.ensure_shop_folder(self.shop)

        self.assertEqual(folder_id, 'cached_folder_id_789')

        # Verify Drive API was NOT called (mock_service.files not invoked)
        mock_service.files.assert_not_called()


@tagged('post_install', '-at_install')
class TestThumbnailGenerator(TransactionCase):
    """Test ThumbnailGenerator service."""

    def test_generate_thumbnail_jpeg_input(self):
        """Test thumbnail generation from JPEG input."""
        from multichannel_hub_core.services.design_thumbnail_generator import (
            ThumbnailGenerator,
        )

        # Create a minimal valid JPEG (1x1 pixel)
        jpeg_blob = base64.b64decode(
            b'/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8VAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k='
        )

        generator = ThumbnailGenerator()
        thumbnail = generator.generate_thumbnail(jpeg_blob)

        self.assertIsNotNone(thumbnail)
        self.assertIsInstance(thumbnail, bytes)
        self.assertLess(len(thumbnail), 256 * 1024)  # Should be <= 256 KB

    def test_generate_thumbnail_corrupt_blob_returns_none(self):
        """Test that corrupt image blob returns None (non-fatal)."""
        from multichannel_hub_core.services.design_thumbnail_generator import (
            ThumbnailGenerator,
        )

        generator = ThumbnailGenerator()
        # Pass invalid image data
        corrupt_blob = b'\x00\x01\x02\x03invalid_image_data'
        thumbnail = generator.generate_thumbnail(corrupt_blob)

        self.assertIsNone(thumbnail)

    def test_generate_thumbnail_respects_size_cap(self):
        """Test that thumbnail respects max_size_kb parameter."""
        from multichannel_hub_core.services.design_thumbnail_generator import (
            ThumbnailGenerator,
        )

        # Create a minimal JPEG
        jpeg_blob = base64.b64decode(
            b'/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8VAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k='
        )

        generator = ThumbnailGenerator()
        thumbnail = generator.generate_thumbnail(jpeg_blob, max_size_kb=50)

        self.assertIsNotNone(thumbnail)
        # Size should be <= 50 KB
        self.assertLessEqual(len(thumbnail), 50 * 1024)


@tagged('post_install', '-at_install')
class TestDesignFileGdriveFields(TransactionCase):
    """Test design.file model with GDrive fields and C-DF-006 constraint."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create partner, product, order
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        cls.order_line = cls.order.order_line[0]

    def _create_design_file(self, **kwargs):
        """Factory for design.file records."""
        defaults = {
            'name': 'Test Design',
            'order_id': self.order.id,
        }
        defaults.update(kwargs)
        return self.env['design.file'].create(defaults)

    def test_create_with_gdrive_mode_persists_fields(self):
        """Test gdrive mode creation persists all fields."""
        df = self._create_design_file(
            storage_mode='gdrive',
            gdrive_file_id='file_abc_123',
            gdrive_folder_id='folder_xyz_789',
            name='GDrive Design'
        )

        self.assertTrue(df.id)
        self.assertEqual(df.storage_mode, 'gdrive')
        self.assertEqual(df.gdrive_file_id, 'file_abc_123')
        self.assertEqual(df.gdrive_folder_id, 'folder_xyz_789')

    def test_gdrive_preview_url_computed(self):
        """Test gdrive_preview_url computed field."""
        df = self._create_design_file(
            storage_mode='gdrive',
            gdrive_file_id='file_abc_123',
            gdrive_folder_id='folder_xyz_789',
        )

        self.assertTrue(
            df.gdrive_preview_url.startswith('https://drive.google.com/file/d/')
        )
        self.assertIn('file_abc_123', df.gdrive_preview_url)

    def test_c_df_006_gdrive_requires_file_id(self):
        """Test C-DF-006 constraint: storage_mode='gdrive' requires gdrive_file_id."""
        with self.assertRaises(ValidationError):
            self._create_design_file(
                storage_mode='gdrive',
                gdrive_file_id='',  # Empty
                gdrive_folder_id='folder_xyz_789',
            )

    def test_c_df_006_gdrive_requires_folder_id(self):
        """Test C-DF-006 constraint: storage_mode='gdrive' requires gdrive_folder_id."""
        with self.assertRaises(ValidationError):
            self._create_design_file(
                storage_mode='gdrive',
                gdrive_file_id='file_abc_123',
                gdrive_folder_id='',  # Empty
            )

    def test_gdrive_thumbnail_optional(self):
        """Test that gdrive_thumbnail field is optional (non-fatal on generation failure)."""
        df = self._create_design_file(
            storage_mode='gdrive',
            gdrive_file_id='file_abc_123',
            gdrive_folder_id='folder_xyz_789',
            gdrive_thumbnail=False,  # Empty/None is OK
        )

        self.assertTrue(df.id)
        self.assertEqual(df.gdrive_thumbnail, False)


@tagged('post_install', '-at_install')
class TestUploadWizard(TransactionCase):
    """Test design.file.upload.wizard model and action_upload."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        cls.order_line = cls.order.order_line[0]

        # Create test shop
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop',
            'shop_id': 'test_shop_123',
            'api_key': 'test_key',
            'api_secret': 'test_secret',
        })

    def _create_wizard(self, **kwargs):
        """Factory for wizard creation."""
        defaults = {
            'file_blob': b'test_file_content',
            'file_name': 'design.pdf',
            'storage_mode': 'gdrive',
            'gdrive_folder_id': 'folder_123',
        }
        defaults.update(kwargs)
        return self.env['design.file.upload.wizard'].create(defaults)

    @patch('multichannel_hub_core.services.gdrive_uploader.GdriveUploader.upload_file')
    def test_action_upload_gdrive_happy_path(self, mock_upload):
        """Test wizard happy path: GDrive upload succeeds, design.file created."""
        # Mock upload success
        mock_upload.return_value = {
            'file_id': 'uploaded_file_id',
            'web_view_link': 'https://drive.google.com/file/d/uploaded_file_id/view',
            'error': None,
        }

        wizard = self._create_wizard(
            order_id=self.order.id,
            storage_mode='gdrive',
            gdrive_folder_id='folder_123',
        )

        # Call action_upload
        wizard.action_upload()

        # Verify design.file was created with gdrive mode
        design_files = self.env['design.file'].search([('order_id', '=', self.order.id)])
        self.assertEqual(len(design_files), 1)

        df = design_files[0]
        self.assertEqual(df.storage_mode, 'gdrive')
        self.assertEqual(df.gdrive_file_id, 'uploaded_file_id')
        self.assertEqual(df.gdrive_folder_id, 'folder_123')

    @patch('multichannel_hub_core.services.gdrive_uploader.GdriveUploader.upload_file')
    def test_action_upload_gdrive_drive_failure_raises_validationerror(self, mock_upload):
        """Test wizard raises ValidationError on Drive failure."""
        # Mock upload failure
        mock_upload.return_value = {
            'file_id': None,
            'error': 'Authentication failed',
        }

        wizard = self._create_wizard(
            order_id=self.order.id,
            storage_mode='gdrive',
        )

        # Should raise ValidationError (no fallback, per ADR-012 §3)
        with self.assertRaises(ValidationError):
            wizard.action_upload()

        # No design.file should be created on failure
        design_files = self.env['design.file'].search([('order_id', '=', self.order.id)])
        self.assertEqual(len(design_files), 0)

    def test_action_upload_url_mode_skips_drive(self):
        """Test URL mode bypasses GDrive upload."""
        wizard = self._create_wizard(
            order_id=self.order.id,
            storage_mode='url',
            file_url='https://example.com/design.pdf',
        )

        wizard.action_upload()

        # Verify design.file with url mode was created
        design_files = self.env['design.file'].search([('order_id', '=', self.order.id)])
        self.assertEqual(len(design_files), 1)
        self.assertEqual(design_files[0].storage_mode, 'url')
        self.assertEqual(design_files[0].file_url, 'https://example.com/design.pdf')

    def test_action_upload_small_mode_skips_drive(self):
        """Test small mode (filestore) bypasses GDrive upload."""
        small_blob = b'x' * 1000  # 1 KB

        wizard = self._create_wizard(
            order_id=self.order.id,
            storage_mode='small',
            file_blob=small_blob,
        )

        wizard.action_upload()

        # Verify design.file with small mode was created
        design_files = self.env['design.file'].search([('order_id', '=', self.order.id)])
        self.assertEqual(len(design_files), 1)
        self.assertEqual(design_files[0].storage_mode, 'small')

    def test_c_duw_001_gdrive_requires_folder_id(self):
        """Test C-DUW-001 constraint: gdrive mode requires gdrive_folder_id."""
        # Create wizard with empty folder ID
        wizard_vals = {
            'file_blob': b'test',
            'file_name': 'test.pdf',
            'storage_mode': 'gdrive',
            'gdrive_folder_id': '',  # Empty
        }

        # Should raise ValidationError on create or action_upload
        try:
            wizard = self.env['design.file.upload.wizard'].create(wizard_vals)
            with self.assertRaises(ValidationError):
                wizard.action_upload()
        except ValidationError:
            # Constraint may trigger on create or on action_upload
            pass


@tagged('post_install', '-at_install')
class TestRpcGateFR017(TransactionCase):
    """Test RPC gate (FR-017) for wizard action_upload."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create production team group
        cls.prod_group = cls.env.ref('multichannel_hub_core.group_production_team')

        # Create non-production user (marketing group only)
        marketing_group = cls.env.ref('base.group_user')
        cls.non_prod_user = cls.env['res.users'].create({
            'name': 'Marketing User',
            'login': 'marketing@example.com',
            'password': 'password',
            'groups_id': [(6, 0, [marketing_group.id])],
        })

        # Create production user
        cls.prod_user = cls.env['res.users'].create({
            'name': 'Production User',
            'login': 'production@example.com',
            'password': 'password',
            'groups_id': [(6, 0, [cls.prod_group.id])],
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

    @patch('multichannel_hub_core.services.gdrive_uploader.GdriveUploader.upload_file')
    def test_non_production_team_user_cannot_call_action_upload(self, mock_upload):
        """Test that non-production user gets AccessError on action_upload RPC."""
        # Mock successful upload
        mock_upload.return_value = {
            'file_id': 'file_id',
            'web_view_link': 'https://drive.google.com/file/d/file_id/view',
            'error': None,
        }

        wizard = self.env['design.file.upload.wizard'].create({
            'file_blob': b'test',
            'file_name': 'test.pdf',
            'storage_mode': 'gdrive',
            'gdrive_folder_id': 'folder_123',
            'order_id': self.order.id,
        })

        # Try to call action_upload with non-production user
        with self.assertRaises(AccessError):
            wizard.with_user(self.non_prod_user).action_upload()
