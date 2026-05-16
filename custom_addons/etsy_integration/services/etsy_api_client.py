"""Etsy API v3 client (P0-15).

Read-only sandbox client for the Etsy v3 API. Mirrors the shape of
`multichannel_hub_fulfillment.services.gearment_api_client.GearmentApiClient`
(P0-18a) but adds Etsy-specific token-refresh logic.

Auth (per Etsy v3 docs): two HTTP headers required on every request:
  - Authorization: Bearer <access_token>
  - x-api-key: <client_id>

Tokens come from the `etsy.shop` record (P0-14 fields with `groups='base.group_system'`);
`client_id` is read from `secrets/credentials.json` via `_read_credentials()`.

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


def _read_credentials() -> dict:
    """Load Etsy app credentials from the in-container secrets path.

    Matches the path used by `controllers/etsy_oauth._read_credentials`
    (`/opt/odoo/secrets/credentials.json` is the bind-mounted location in
    the namco_odoo19 docker compose). Tests patch this function so the
    credentials file does not need to exist inside the test container.
    """
    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as handle:
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
            credentials = _read_credentials()
        except FileNotFoundError as exc:
            raise ValueError(
                "EtsyApiClient: secrets/credentials.json not found"
            ) from exc
        if not credentials.get('client_id'):
            raise ValueError("EtsyApiClient: client_id missing from credentials")

        self.shop = shop
        self.client_id = credentials['client_id']
        self._rate_limiter = TokenBucket(_RATE_LIMIT_QPS, _RATE_LIMIT_PERIOD)

    def _session(self) -> requests.Session:
        session = requests.Session()
        # P1-10: pull plaintext through the Fernet helper. The raw
        # column holds ciphertext; reading it directly into the
        # Authorization header would 401 every request.
        session.headers = {
            'Authorization': f'Bearer {self.shop._get_access_token()}',
            'x-api-key': self.client_id,
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
            raise ValueError(
                "Etsy returned 403 Forbidden; check scope/permissions"
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
