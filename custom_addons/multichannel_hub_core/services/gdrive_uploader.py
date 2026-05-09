"""GDrive upload service — Google Drive API wrapper for design files."""
import io
import logging
import os

try:
    import google.auth.exceptions
    from google.oauth2 import service_account
    from googleapiclient import discovery
    from googleapiclient.http import MediaInMemoryUpload, MediaIoBaseDownload, MediaIoBaseUpload
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

    # ------------------------------------------------------------------
    # P2-06 — logistics inbox polling surface
    # ------------------------------------------------------------------

    def list_files(self, folder_id: str, modified_after=None) -> list[dict]:
        """List non-trashed files in a Drive folder, optionally newer than a timestamp.

        Args:
            folder_id: GDrive folder ID to list.
            modified_after: datetime (or RFC3339 string) — only files with
                modifiedTime > this value are returned. None = no filter.

        Returns:
            list of {'id', 'name', 'mimeType', 'modifiedTime'} dicts.
            Returns [] on auth/IO errors (caller handles via sync.health).

        Drive query escaping: folder_id is supplied by trusted admin via
        logistics.partner record (FR-035 system-only); no untrusted input
        reaches the q= clause.
        """
        service = self._build_service()
        # Escape single quotes in folder_id defensively even though source is admin-only.
        # Order matters: backslash first (to avoid re-escaping the escapes we add),
        # then single quote. Drive query syntax: single-quoted strings need \' for literals.
        safe_folder = folder_id.replace('\\', '\\\\').replace("'", "\\'")
        q_parts = [f"'{safe_folder}' in parents", "trashed=false"]
        if modified_after is not None:
            if hasattr(modified_after, 'isoformat'):
                ts = modified_after.isoformat()
                if not ts.endswith('Z') and '+' not in ts:
                    ts += 'Z'
            else:
                ts = str(modified_after)
            ts_escaped = ts.replace("'", "\\'")
            q_parts.append(f"modifiedTime > '{ts_escaped}'")
        q = ' and '.join(q_parts)

        results = service.files().list(
            q=q,
            spaces='drive',
            fields='files(id,name,mimeType,modifiedTime)',
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        return list(results.get('files', []))

    def download_file(self, file_id: str) -> bytes:
        """Download file content from Drive.

        Args:
            file_id: GDrive file ID.

        Returns:
            File bytes.

        Raises:
            googleapiclient.errors.HttpError on API failure (caller handles).
        """
        service = self._build_service()
        request = service.files().get_media(
            fileId=file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        return buffer.getvalue()

    def move_file(self, file_id: str, new_parent_folder_id: str) -> dict:
        """Move file to a different parent folder (archive flow).

        Args:
            file_id: GDrive file ID to move.
            new_parent_folder_id: target parent folder ID.

        Returns:
            updated file metadata dict.
        """
        service = self._build_service()
        # Read current parents to remove them
        current = service.files().get(
            fileId=file_id, fields='parents', supportsAllDrives=True).execute()
        previous_parents = ','.join(current.get('parents', []))
        return service.files().update(
            fileId=file_id,
            addParents=new_parent_folder_id,
            removeParents=previous_parents,
            fields='id,parents',
            supportsAllDrives=True,
        ).execute()

    def upload_text(self, folder_id: str, filename: str, body: str) -> dict:
        """Upload a small text/plain blob (used for .error.txt sidecar markers).

        Args:
            folder_id: GDrive parent folder ID.
            filename: name (e.g., 'tracking.xlsx.error.txt').
            body: text content.

        Returns:
            file metadata dict.
        """
        service = self._build_service()
        media = MediaInMemoryUpload(
            body.encode('utf-8'), mimetype='text/plain')
        return service.files().create(
            body={'name': filename, 'parents': [folder_id]},
            media_body=media,
            fields='id',
            supportsAllDrives=True,
        ).execute()
