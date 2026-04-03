"""Gmail API client using raw HTTP requests (no google-api-python-client).

Handles OAuth2 token refresh, message listing with pagination,
full message retrieval, MIME decoding, and label management.
"""
import base64
import logging

import requests

from .email_parser import RawEmail

_logger = logging.getLogger(__name__)

_TOKEN_URL = 'https://oauth2.googleapis.com/token'
_GMAIL_API = 'https://gmail.googleapis.com/gmail/v1/users/me'
_REQUEST_TIMEOUT = 15


class GmailClient:
    """Lightweight Gmail API client using OAuth2 refresh tokens."""

    def __init__(self, client_id, client_secret, refresh_token):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self):
        """Obtain an access token via the refresh_token grant.

        Returns True on success, False on failure.
        """
        try:
            response = requests.post(
                _TOKEN_URL,
                data={
                    'client_id': self._client_id,
                    'client_secret': self._client_secret,
                    'refresh_token': self._refresh_token,
                    'grant_type': 'refresh_token',
                },
                timeout=_REQUEST_TIMEOUT,
            )
            if not response.ok:
                _logger.error(
                    'Gmail auth failed (%s): %s',
                    response.status_code, response.text)
                return False
            data = response.json()
            self._access_token = data.get('access_token')
            return bool(self._access_token)
        except Exception:
            _logger.exception('Gmail auth request error')
            return False

    def test_connection(self):
        """Test the connection by fetching the user profile.

        Returns (success: bool, message: str).
        """
        if not self._access_token:
            ok = self.authenticate()
            if not ok:
                return False, 'Authentication failed. Check your credentials.'
        try:
            resp = requests.get(
                f'{_GMAIL_API}/profile',
                headers=self._auth_headers(),
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.ok:
                email = resp.json().get('emailAddress', 'unknown')
                return True, f'Connected as {email}'
            return False, f'API error {resp.status_code}: {resp.text[:200]}'
        except Exception as exc:
            _logger.exception('Gmail test_connection error')
            return False, f'Connection error: {exc}'

    # ------------------------------------------------------------------
    # Email fetching
    # ------------------------------------------------------------------

    def fetch_labeled_emails(self, label):
        """Fetch all emails with the given Gmail label.

        Returns a list of RawEmail instances. Returns an empty list on
        any error.
        """
        if not self._access_token:
            _logger.error('fetch_labeled_emails called without authentication')
            return []

        try:
            message_ids = self._list_message_ids(label)
            if not message_ids:
                return []

            raw_emails = []
            for msg_id in message_ids:
                raw_email = self._get_message(msg_id)
                if raw_email is not None:
                    raw_emails.append(raw_email)
            return raw_emails
        except Exception:
            _logger.exception('Error fetching labeled emails')
            return []

    def _list_message_ids(self, label):
        """Return all message IDs matching ``label:<label>``, handling pagination."""
        ids = []
        params = {'q': f'label:{label}', 'maxResults': 100}
        while True:
            resp = requests.get(
                f'{_GMAIL_API}/messages',
                headers=self._auth_headers(),
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
            if not resp.ok:
                _logger.error(
                    'Gmail list messages error (%s): %s',
                    resp.status_code, resp.text[:200])
                break
            data = resp.json()
            for msg in data.get('messages', []):
                ids.append(msg['id'])
            next_page = data.get('nextPageToken')
            if not next_page:
                break
            params['pageToken'] = next_page
        return ids

    def _get_message(self, message_id):
        """Fetch a single message in ``full`` format and return a RawEmail."""
        try:
            resp = requests.get(
                f'{_GMAIL_API}/messages/{message_id}',
                headers=self._auth_headers(),
                params={'format': 'full'},
                timeout=_REQUEST_TIMEOUT,
            )
            if not resp.ok:
                _logger.error(
                    'Gmail get message %s error (%s): %s',
                    message_id, resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            return self._decode_message(message_id, data)
        except Exception:
            _logger.exception('Error fetching message %s', message_id)
            return None

    # ------------------------------------------------------------------
    # MIME decoding
    # ------------------------------------------------------------------

    def _decode_message(self, message_id, data):
        """Decode a Gmail API message payload into a RawEmail."""
        payload = data.get('payload', {})
        headers = {
            h['name'].lower(): h['value']
            for h in payload.get('headers', [])
        }
        subject = headers.get('subject', '')
        date = headers.get('date', '')

        text_body = ''
        html_body = ''

        parts = payload.get('parts')
        if parts:
            text_body, html_body = self._extract_parts(parts)
        else:
            # Single-part message (no multipart wrapper)
            mime_type = payload.get('mimeType', '')
            body_data = payload.get('body', {}).get('data', '')
            decoded = self._b64url_decode(body_data)
            if mime_type == 'text/plain':
                text_body = decoded
            elif mime_type == 'text/html':
                html_body = decoded

        return RawEmail(
            message_id=message_id,
            subject=subject,
            date=date,
            text_body=text_body,
            html_body=html_body,
        )

    def _extract_parts(self, parts):
        """Recursively extract text/plain and text/html from MIME parts."""
        text_body = ''
        html_body = ''
        for part in parts:
            mime_type = part.get('mimeType', '')
            # Recurse into nested multipart
            nested = part.get('parts')
            if nested:
                t, h = self._extract_parts(nested)
                text_body = text_body or t
                html_body = html_body or h
                continue
            body_data = part.get('body', {}).get('data', '')
            if not body_data:
                continue
            decoded = self._b64url_decode(body_data)
            if mime_type == 'text/plain' and not text_body:
                text_body = decoded
            elif mime_type == 'text/html' and not html_body:
                html_body = decoded
        return text_body, html_body

    @staticmethod
    def _b64url_decode(data):
        """Decode a base64url-encoded string to UTF-8 text."""
        if not data:
            return ''
        try:
            padded = data + '=' * (4 - len(data) % 4)
            return base64.urlsafe_b64decode(padded).decode('utf-8', errors='replace')
        except Exception:
            _logger.debug('b64url decode failed', exc_info=True)
            return ''

    # ------------------------------------------------------------------
    # Label management
    # ------------------------------------------------------------------

    def remove_label(self, message_ids, label):
        """Remove the named label from a list of messages.

        Uses the batchModify endpoint. Resolves the label name to its ID
        first.
        """
        if not message_ids:
            return
        label_id = self._get_label_id(label)
        if not label_id:
            _logger.warning('Could not resolve label "%s" to an ID', label)
            return

        # batchModify supports up to 1000 IDs per request
        batch_size = 1000
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]
            try:
                resp = requests.post(
                    f'{_GMAIL_API}/messages/batchModify',
                    headers=self._auth_headers(),
                    json={
                        'ids': batch,
                        'removeLabelIds': [label_id],
                    },
                    timeout=_REQUEST_TIMEOUT,
                )
                if not resp.ok:
                    _logger.error(
                        'batchModify error (%s): %s',
                        resp.status_code, resp.text[:200])
            except Exception:
                _logger.exception('Error in batchModify for label removal')

    def _get_label_id(self, label_name):
        """Resolve a label name to its Gmail label ID."""
        try:
            resp = requests.get(
                f'{_GMAIL_API}/labels',
                headers=self._auth_headers(),
                timeout=_REQUEST_TIMEOUT,
            )
            if not resp.ok:
                return None
            for lbl in resp.json().get('labels', []):
                if lbl.get('name') == label_name:
                    return lbl['id']
        except Exception:
            _logger.exception('Error fetching labels')
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _auth_headers(self):
        return {'Authorization': f'Bearer {self._access_token}'}
