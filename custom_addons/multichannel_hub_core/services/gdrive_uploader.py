"""GDrive upload service — Google Drive API wrapper for design files."""
import io
import logging
import os

try:
    import google.auth.exceptions
    from google.oauth2 import service_account
    from googleapiclient import discovery
    from googleapiclient.http import MediaIoBaseUpload
except ImportError:
    google = None

_logger = logging.getLogger(__name__)


class GdriveUploader:
    """Upload files to Google Drive and manage folder structure."""

    def __init__(self, credentials_path: str | None = None):
        """Initialize uploader with optional credential path override.

        Args:
            credentials_path: Path to service account JSON (default from env)
        """
        self.credentials_path = credentials_path or self._credentials_path()

    @staticmethod
    def _credentials_path() -> str:
        """Return path to service account JSON from env or default location."""
        from_env = os.environ.get('GDRIVE_SERVICE_ACCOUNT_JSON')
        if from_env:
            return from_env
        # Default: look for secrets/ relative to project root (via Docker)
        return '/app/secrets/gdrive-service-account.json'

    def _build_service(self):
        """Build Google Drive service with credentials.

        Raises:
            FileNotFoundError: If credential file missing
            google.auth.exceptions.DefaultCredentialsError: If cred loading fails
        """
        if not os.path.exists(self.credentials_path):
            _logger.warning(
                "GDrive credential file missing at %s", self.credentials_path
            )
            raise FileNotFoundError(
                "GDrive service account not configured. Contact administrator."
            )
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/drive'],
        )
        return discovery.build('drive', 'v3', credentials=creds)

    def upload_file(
        self,
        file_blob: bytes,
        file_name: str,
        folder_id: str,
    ) -> dict:
        """Upload file to GDrive folder.

        Args:
            file_blob: File content bytes
            file_name: Filename for Drive (sanitized in caller)
            folder_id: GDrive folder ID to upload into

        Returns:
            {'file_id': str, 'web_view_link': str, 'error': None} on success
            {'file_id': None, 'error': str} on failure
        """
        try:
            service = self._build_service()
        except Exception as e:
            msg = f"GDrive authentication failed: {e}"
            _logger.warning(msg)
            return {'file_id': None, 'web_view_link': None, 'error': msg}

        try:
            file_metadata = {
                'name': file_name,
                'parents': [folder_id],
            }
            media_body = MediaIoBaseUpload(
                io.BytesIO(file_blob), mimetype='application/octet-stream'
            )
            file_obj = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media_body,
                    fields='id,webViewLink',
                    supportsAllDrives=True,
                )
                .execute()
            )
            return {
                'file_id': file_obj.get('id'),
                'web_view_link': file_obj.get('webViewLink'),
                'error': None,
            }
        except Exception as e:
            msg = f"GDrive upload failed: {e}"
            _logger.warning(msg)
            return {'file_id': None, 'web_view_link': None, 'error': msg}

    def ensure_shop_folder(self, shop) -> str:
        """Ensure GDrive folder exists for shop; return folder_id (cached or created).

        Caches folder ID in shop.x_gdrive_design_folder_id to avoid repeated
        Drive queries.

        Args:
            shop: etsy.shop record

        Returns:
            GDrive folder ID (str)
        """
        if shop.x_gdrive_design_folder_id:
            return shop.x_gdrive_design_folder_id

        try:
            service = self._build_service()
        except Exception as e:
            _logger.error(
                "Cannot ensure shop folder for shop %s: %s", shop.name, e
            )
            raise

        # Sanitize folder name: escape single quotes and backslashes for Drive query syntax.
        # Drive's q= uses single-quoted strings; unescaped quotes break parsing and enable
        # enumeration attacks.
        folder_name = shop.name or f'Shop_{shop.id}'
        safe_name = folder_name.replace('\\', '\\\\').replace("'", "\\'")

        try:
            # Query for existing folder
            q = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name='{safe_name}' and trashed=false"
            )
            results = service.files().list(
                q=q,
                spaces='drive',
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            files = results.get('files', [])

            if files:
                folder_id = files[0]['id']
            else:
                # Create new folder
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                }
                folder_obj = (
                    service.files()
                    .create(
                        body=folder_metadata,
                        fields='id',
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                folder_id = folder_obj.get('id')

            # Cache in shop record
            # sudo: x_gdrive_design_folder_id is a system-internal cache field;
            # any user who can call ensure_shop_folder (gated to production_team via
            # action_upload) must be able to populate this cache regardless of write ACL
            # on etsy.shop record. Bypass is intentional and bounded.
            shop.sudo().x_gdrive_design_folder_id = folder_id
            return folder_id

        except Exception as e:
            _logger.error(
                "Failed to ensure shop folder for %s: %s", shop.name, e
            )
            raise
