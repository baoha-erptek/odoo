"""Etsy API v3 client (P0-15).

Read-only sandbox client for the Etsy v3 API. Mirrors the shape of
`multichannel_hub_fulfillment.services.gearment_api_client.GearmentApiClient`
(P0-18a) but adds Etsy-specific token-refresh logic.

Auth (per Etsy v3 docs): two HTTP headers required on every request:
  - Authorization: Bearer <access_token>
  - x-api-key: <client_id>:<client_secret>     (since 2026-02-09 enforcement;
    etsy/open-api Discussion #1521 — keystring-only form is rejected)

Tokens come from the `etsy.shop` record (P0-14 fields with `groups='base.group_system'`);
`client_id` and `client_secret` are read from `secrets/credentials.json` via
`_read_credentials()`.

Rate limiter: per-instance `TokenBucket(rate=8, period=1.0)` (per architect Q3 in
`specs/005-etsy-api-channel/findings.md`). Lives in `multichannel_hub_core.utils`
since P0-18a — the shared-bucket Phase 1 refactor (Q3 long-term home) is already
in place. Advisory only on send.

429 retry: honor `Retry-After` capped at 60 seconds (defense-in-depth from
P0-18a security review), fall back to (1, 2, 4) exponential backoff, raise
`RateLimitError` after 3 retries.

401 handling: refresh the access token via `etsy_oauth.refresh_access_token`,
write new tokens to the shop record using `sudo()` (group_system fields), retry
the original request once. If the second attempt also returns 401, give up.
If the refresh itself fails, raise `ValueError`.

Proactive refresh: if `shop.etsy_oauth_token_expires_at` is within the next
60 seconds, refresh BEFORE sending — avoids burning a request on a known-soon-
to-expire token.
"""

import json
import logging
import time
from datetime import datetime, timedelta

import requests

from . import etsy_oauth

_logger = logging.getLogger(__name__)

ETSY_API_BASE_URL = 'https://openapi.etsy.com/v3/application'
_RATE_LIMIT_QPS = 8
_RATE_LIMIT_PERIOD = 1.0
_BACKOFF_SECONDS = (1, 2, 4)
_MAX_RETRIES = 3
_MAX_RETRY_AFTER_SECONDS = 60
_PROACTIVE_REFRESH_WINDOW_SECONDS = 60
_AUTH_NEEDS_REFRESH = 401
_AUTH_FORBIDDEN = 403


CREDENTIALS_PATH = '/opt/odoo/secrets/credentials.json'
_CREDENTIALS_PATH_PARAM = 'etsy.oauth.credentials_path'


def _read_credentials(env=None) -> dict:
    """Load Etsy app credentials from the in-container secrets path.

    Single source of truth with `controllers/etsy_oauth._read_credentials`:
    when an Odoo `env` is supplied, the path is read from the
    `etsy.oauth.credentials_path` system parameter so dev / staging / prod
    can keep distinct filenames (staging uses `etsy_credentials.json` per
    `reference_staging_ssh_deploy.md`). When env is None (test isolation,
    pure-Python callers), fall back to the historical hardcoded default —
    tests patch this function so the file does not need to exist.
    """
    path = CREDENTIALS_PATH
    if env is not None:
        param = env['ir.config_parameter'].sudo().get_param(
            _CREDENTIALS_PATH_PARAM,
        )
        if param:
            path = param
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


class RateLimitError(Exception):
    """Raised when Etsy 429 retries are exhausted."""

    def __init__(self, message: str, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class EtsyApiClient:
    """Etsy API v3 client. Per-shop instance.

    Constructor reads tokens from the supplied `etsy.shop` record and
    `client_id` from `secrets/credentials.json`. Fail-fast if any required
    credential is missing.

    Access-control note: this client uses `sudo()` to refresh OAuth tokens
    because the relevant shop fields carry `groups='base.group_system'`. The
    caller is the access-control gate — only authorized service code (cron
    jobs, sync orchestrators, system-controller routes) should instantiate
    this client. Do NOT expose `EtsyApiClient` to interactive end-user code
    paths without first checking the user's access against the shop record.
    """

    def __init__(self, shop):
        # Lazy import keeps registry-build order deterministic.
        from odoo.addons.multichannel_hub_core.utils.rate_limiter import TokenBucket

        if not shop:
            raise ValueError("EtsyApiClient requires an etsy.shop record")
        if not shop.sudo().etsy_oauth_access_token:
            raise ValueError(
                "EtsyApiClient: etsy_oauth_access_token is missing on shop"
            )
        if not shop.sudo().etsy_oauth_refresh_token:
            raise ValueError(
                "EtsyApiClient: etsy_oauth_refresh_token is missing on shop"
            )
        try:
            credentials = _read_credentials(env=shop.env)
        except FileNotFoundError as exc:
            raise ValueError(
                f"EtsyApiClient: credentials file not found ({exc.filename})"
            ) from exc
        if not credentials.get('client_id'):
            raise ValueError("EtsyApiClient: client_id missing from credentials")
        if not credentials.get('client_secret'):
            raise ValueError("EtsyApiClient: client_secret missing from credentials")

        self.shop = shop
        self.client_id = credentials['client_id']
        self.client_secret = credentials['client_secret']
        self._rate_limiter = TokenBucket(_RATE_LIMIT_QPS, _RATE_LIMIT_PERIOD)

    def _session(self) -> requests.Session:
        session = requests.Session()
        # P1-10: pull plaintext through the Fernet helper. The raw
        # column holds ciphertext; reading it directly into the
        # Authorization header would 401 every request.
        session.headers = {
            'Authorization': f'Bearer {self.shop._get_access_token()}',
            'x-api-key': f'{self.client_id}:{self.client_secret}',
            'Accept': 'application/json',
        }
        return session

    def _token_expires_soon(self) -> bool:
        # Compare in UTC. Odoo Datetime fields read as naive UTC; pair with
        # `datetime.utcnow()` so the threshold is not timezone-skewed in
        # non-UTC deployments.
        expires_at = self.shop.sudo().etsy_oauth_token_expires_at
        if not expires_at:
            return False
        threshold = datetime.utcnow() + timedelta(seconds=_PROACTIVE_REFRESH_WINDOW_SECONDS)
        return expires_at < threshold

    def _refresh_token(self) -> None:
        """Refresh access token via etsy_oauth and persist on the shop.

        sudo() is required because the OAuth fields carry
        `groups='base.group_system'` ACL (P0-14); this method represents
        a system-level token-rotation event triggered by Etsy's auth flow,
        not a user write — calling user may legitimately lack system rights.
        Raises ValueError if the refresh call itself fails.
        """
        try:
            payload = etsy_oauth.refresh_access_token(
                self.client_id,
                self.shop._get_refresh_token(),
            )
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise ValueError(f"Etsy token refresh failed: {exc}") from exc

        access_token = payload.get('access_token')
        refresh_token = payload.get('refresh_token')
        expires_in = payload.get('expires_in')
        if not access_token or not refresh_token:
            raise ValueError(
                "Etsy token refresh failed: missing access/refresh in response"
            )
        # P1-10: route through Fernet-encrypting helpers; raw columns
        # hold ciphertext.
        self.shop._set_access_token(access_token)
        self.shop._set_refresh_token(refresh_token)
        if expires_in:
            # Store as naive UTC to match the convention used elsewhere.
            self.shop.sudo().write({
                'etsy_oauth_token_expires_at': (
                    datetime.utcnow() + timedelta(seconds=int(expires_in))
                ),
            })

    def _send_with_429_retry(self, session, method, url, **kwargs):
        """Single 429-retry loop. Returns the final response (any status)
        or raises `RateLimitError` after `_MAX_RETRIES` retries.
        """
        last_retry_after = None
        response = None
        for attempt in range(_MAX_RETRIES + 1):
            response = session.request(method, url, **kwargs)
            if response.status_code != 429:
                return response

            header_value = response.headers.get('Retry-After')
            if header_value is not None:
                try:
                    last_retry_after = int(header_value)
                except (TypeError, ValueError):
                    last_retry_after = None

            if last_retry_after is not None:
                wait = min(last_retry_after, _MAX_RETRY_AFTER_SECONDS)
            else:
                wait = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
            time.sleep(wait)

        raise RateLimitError(
            "Etsy rate limit retries exhausted",
            retry_after=last_retry_after,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if self._token_expires_soon():
            self._refresh_token()

        if not self._rate_limiter.acquire():
            _logger.warning(
                "Etsy local rate limiter exhausted; sending anyway (advisory)"
            )

        url = f"{ETSY_API_BASE_URL}/{path.lstrip('/')}"

        session = self._session()
        response = self._send_with_429_retry(session, method, url, **kwargs)

        if response.status_code == _AUTH_NEEDS_REFRESH:
            # One-shot refresh + retry. If the post-refresh request also 401s,
            # do not loop — the refresh token may itself be revoked.
            self._refresh_token()
            session = self._session()
            response = self._send_with_429_retry(session, method, url, **kwargs)
            if response.status_code == _AUTH_NEEDS_REFRESH:
                raise ValueError(
                    "Etsy auth still failing after token refresh; "
                    "refresh_token may be revoked"
                )

        if response.status_code == _AUTH_FORBIDDEN:
            # Per memory feedback_capture_response_body_before_blackbox_probe.md:
            # surface vendor error body so 403s are diagnosable without
            # a special diagnostic deploy. Body is typically a small JSON
            # like {"error": "...", "error_description": "..."}; truncate
            # to 500 chars to keep the log line bounded and avoid token
            # leakage in any pathological response.
            body = (response.text or '')[:500]
            _logger.warning(
                "Etsy 403 Forbidden url=%s body=%r", url, body,
            )
            raise ValueError(
                f"Etsy returned 403 Forbidden ({body}); check scope/permissions"
            )

        response.raise_for_status()
        return response.json()

    def ping(self) -> dict:
        """Cheapest auth-validation call. Returns the user/me payload."""
        return self._request('GET', 'users/me')

    def get(self, path: str, params: dict | None = None) -> dict:
        """Authenticated GET against the Etsy v3 application surface.

        Public wrapper around `_request('GET', ...)` for callers that
        do not need the full request method/body machinery — the
        `EtsyApiAdapter` (P0-16b2) is the only intended caller. Same
        rate-limit + 401-refresh + 429-retry guarantees as `_request`.
        """
        kwargs = {'params': params} if params else {}
        return self._request('GET', path, **kwargs)

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-CLIENT — write methods. Each thin wrapper routes
    # through `_request` so the auth + rate-limit + 401-refresh + 429-retry
    # + 4xx-body-capture behaviour is shared with `get()`. Multipart upload
    # has its own helper to make `files=` plumbing explicit at the call site.
    # ------------------------------------------------------------------

    def post(self, path: str, json: dict | None = None,
             data: dict | None = None) -> dict:
        kwargs: dict = {}
        if json is not None:
            kwargs['json'] = json
        if data is not None:
            kwargs['data'] = data
        return self._request('POST', path, **kwargs)

    def put(self, path: str, json: dict | None = None,
            data: dict | None = None) -> dict:
        kwargs: dict = {}
        if json is not None:
            kwargs['json'] = json
        if data is not None:
            kwargs['data'] = data
        return self._request('PUT', path, **kwargs)

    def patch(self, path: str, json: dict | None = None,
              data: dict | None = None) -> dict:
        kwargs: dict = {}
        if json is not None:
            kwargs['json'] = json
        if data is not None:
            kwargs['data'] = data
        return self._request('PATCH', path, **kwargs)

    def post_multipart(self, path: str, files: dict,
                        data: dict | None = None) -> dict:
        """POST a multipart/form-data body (image upload).

        `files` is the standard `requests` files dict —
        e.g. `{'image': ('a.jpg', bytes, 'image/jpeg')}`.
        """
        kwargs: dict = {'files': files}
        if data is not None:
            kwargs['data'] = data
        return self._request('POST', path, **kwargs)

    def push_tracking(self, shop_path_id, receipt_id, carrier_name,
                      tracking_number):
        """P1-12: create a receipt shipment (tracking pushback).

        ``POST shops/{shop_id}/receipts/{receipt_id}/tracking`` with the
        Etsy v3 form fields ``tracking_code`` + ``carrier_name``. Returns
        ``(ok, http_status, error_message)``. Same rate-limit / 401-refresh
        / 429-retry guarantees as ``_request``; raises on hard transport or
        auth failure so the caller (EtsyTrackingPusher) can mark the push
        failed and audit it.
        """
        # receipt_id originates from order.etsy_order_id (Etsy API receipt
        # id, but the legacy email path can set arbitrary values) — URL-
        # encode it so a crafted value cannot traverse to another API path.
        from urllib.parse import quote
        safe_receipt = quote(str(receipt_id), safe='')
        path = f'shops/{int(shop_path_id)}/receipts/{safe_receipt}/tracking'
        self._request('POST', path, data={
            'tracking_code': tracking_number,
            'carrier_name': carrier_name,
        })
        # `_request` raises for any non-2xx; reaching here is success. Etsy
        # returns 200 with the updated receipt body on this endpoint.
        return (True, 200, '')
