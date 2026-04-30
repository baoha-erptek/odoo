"""Google Drive file upload service with service-account authentication.

Handles:
- Service-account auth via google-auth library
- File upload to Drive folders
- Shop folder creation/caching (per etsy.shop.x_gdrive_design_folder_id)
- Error handling (auth, quota, network) returning structured dict response

ADR-006 §3 + §6 alignment: service-account-only, minimum scopes, app-created
files only, folder structure idempotent, no silent fallback on error.
"""
import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

GDRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
GDRIVE_DEFAULT_PATH = '/opt/odoo/secrets/gdrive-service-account.json'
GDRIVE_SECRET_PATH_ICP = 'multichannel_hub.gdrive_service_account_path'


class GdriveUploader:
    """Service-account-authenticated Google Drive upload client.

    Public API:
        upload_file(file_blob: bytes, file_name: str, folder_id: str,
                    mime_type: str = 'application/octet-stream') -> dict
            Returns {'file_id': str | None, 'web_view_link': str | None,
                     'error': str | None}.
            Never raises on Drive failure; caller inspects 'error' key.

        ensure_shop_folder(shop_record) -> str | None
            Returns Drive folder_id (cached on shop.x_gdrive_design_folder_id
            after first call). Returns None on persistent failure (caller
            should ValidationError).
    """

    def __init__(self, env=None):
        """Initialize with optional Odoo env (for ICP + shop access)."""
        self.env = env

    def _credentials_path(self):
        """Return path to service account JSON file.

        Prefers ICP override (multichannel_hub.gdrive_service_account_path);
        falls back to default. Kept as separate method so missing google-auth
        doesn't break services/__init__.py import.
        """
        if self.env:
            return self.env['ir.config_parameter'].sudo().get_param(
                GDRIVE_SECRET_PATH_ICP, GDRIVE_DEFAULT_PATH
            )
        return GDRIVE_DEFAULT_PATH

    def _build_service(self):
        """Lazy-import + build Google Drive v3 service.

        Keeps google-auth/googleapiclient imports out of module level so
        their absence doesn't break services/ import when GDrive features
        are not in use.
        """
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ImportError(
                "google-auth and google-api-python-client are required for "
                "GDrive uploads. Install: pip install 'google-auth>=2.16.0' "
                "'google-api-python-client>=2.80.0'"
            ) from exc

        cred_path = self._credentials_path()
        try:
            with open(cred_path, 'r', encoding='utf-8') as f:
                creds = service_account.Credentials.from_service_account_info(
                    json.load(f), scopes=[GDRIVE_SCOPE]
                )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Service account JSON not found at {cred_path}. "
                f"Set multichannel_hub.gdrive_service_account_path ICP or "
                f"place file at {GDRIVE_DEFAULT_PATH}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Service account JSON at {cred_path} is invalid"
            ) from exc

        return build('drive', 'v3', credentials=creds, cache_discovery=False)

    def upload_file(self, file_blob, file_name, folder_id,
                    mime_type='application/octet-stream'):
        """Upload file blob to Drive folder.

        Args:
            file_blob (bytes): Raw file content
            file_name (str): Display name for file on Drive
            folder_id (str): Drive folder ID (parent)
            mime_type (str): MIME type (default octet-stream)

        Returns:
            dict: {'file_id': str|None, 'web_view_link': str|None,
                   'error': str|None}
                   On success: file_id + web_view_link set, error=None
                   On failure: file_id=None, error=str(exception)
        """
        try:
            from googleapiclient.http import MediaInMemoryUpload

            service = self._build_service()
            metadata = {'name': file_name, 'parents': [folder_id]}
            media = MediaInMemoryUpload(file_blob, mimetype=mime_type)
            result = service.files().create(
                body=metadata,
                media_body=media,
                fields='id, webViewLink',
            ).execute()

            file_id = result.get('id')
            web_view_link = result.get('webViewLink')
            _logger.debug(
                "GDrive upload OK file_id=%s folder_id=%s",
                file_id, folder_id,
            )
            return {
                'file_id': file_id,
                'web_view_link': web_view_link,
                'error': None,
            }
        except Exception as exc:  # noqa: BLE001 — caller inspects error str
            err_str = str(exc)
            _logger.warning(
                "GDrive upload failed folder_id=%s err=%s",
                folder_id, err_str,
            )
            return {
                'file_id': None,
                'web_view_link': None,
                'error': err_str,
            }

    def ensure_shop_folder(self, shop):
        """Get or create Drive folder for shop; cache on shop record.

        Lookup/create is idempotent — reuses existing folder if present
        with matching name. Caches result on shop.x_gdrive_design_folder_id
        to avoid repeated Drive calls.

        Args:
            shop (etsy.shop record): Shop record with name field

        Returns:
            str | None: Drive folder_id on success, None on persistent failure
        """
        # Cache hit: avoid Drive call
        cached = getattr(shop, 'x_gdrive_design_folder_id', False)
        if cached:
            _logger.debug(
                "GDrive folder cache hit shop_id=%s folder_id=%s",
                shop.id, cached,
            )
            return cached

        try:
            from datetime import datetime

            service = self._build_service()
            year = datetime.utcnow().strftime('%Y')
            folder_name = f"{shop.name}_{year}"

            # Search for existing folder
            q = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name='{folder_name}' and trashed=false"
            )
            resp = service.files().list(q=q, fields='files(id)').execute()
            files = resp.get('files', [])

            if files:
                folder_id = files[0]['id']
                _logger.debug(
                    "GDrive folder found existing shop_id=%s folder_id=%s",
                    shop.id, folder_id,
                )
            else:
                # Create new folder
                meta = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                }
                created = service.files().create(
                    body=meta, fields='id',
                ).execute()
                folder_id = created['id']
                _logger.debug(
                    "GDrive folder created shop_id=%s folder_id=%s",
                    shop.id, folder_id,
                )

            # Cache on shop record (sudo to bypass potential read-only ACL)
            shop.sudo().x_gdrive_design_folder_id = folder_id
            return folder_id

        except Exception as exc:  # noqa: BLE001
            err_str = str(exc)
            _logger.warning(
                "GDrive ensure_shop_folder failed shop_id=%s err=%s",
                shop.id, err_str,
            )
            return None
