"""Gearment API v3 client.

Read-only auth probe scaffolding for P0-18a. Full POC (live order submission,
webhook signature discovery) is deferred to P0-18b.

Auth: two HTTP headers are required on every request:
  - X-Gearment-Client-Key: <api_key>
  - X-Gearment-Client-Secret: <api_secret>

Both come from environment variables (`GEARMENT_API_KEY`,
`GEARMENT_API_SECRET`) injected via docker-compose `.env`. Base URL also from
env: `GEARMENT_API_BASE_URL` (e.g., sandbox
`https://api.gearmentinc.com/integration-handler` or production
`https://apiv2.gearment.com/integration-handler`).

Per Gearment docs (developers.gearment.com/api.md, 2026-04-27): rate limit is
100 requests / 10 seconds, then 1-minute block. 429 responses carry a
`Retry-After` header which we honor; otherwise we fall back to (1, 2, 4)
exponential backoff. After three retries we raise `RateLimitError`.
"""

import logging
import os
import time

import requests

_logger = logging.getLogger(__name__)

_DEFAULT_RATE_LIMIT = 100
_DEFAULT_RATE_PERIOD = 10.0
_BACKOFF_SECONDS = (1, 2, 4)
_MAX_RETRIES = 3
_MAX_RETRY_AFTER_SECONDS = 60
_AUTH_STATUS_CODES = (401, 403)


class RateLimitError(Exception):
    """Raised when Gearment 429s exceed the retry budget."""

    def __init__(self, message: str, retry_after: float = None):
        super().__init__(message)
        self.retry_after = retry_after


class GearmentApiClient:
    """Read-only Gearment API v3 client (P0-18a).

    Reads credentials from environment at construction time and fails fast if
    any are missing. Subsequent calls go through `_request`, which applies the
    rate limiter (advisory) and the 429-retry policy.
    """

    _REQUIRED_ENV = ('GEARMENT_API_KEY', 'GEARMENT_API_SECRET', 'GEARMENT_API_BASE_URL')

    def __init__(self, env=None):
        # Lazy import to avoid a circular dep when the core module isn't loaded
        # yet (e.g., during Odoo registry build before fulfillment installs).
        from odoo.addons.multichannel_hub_core.utils.rate_limiter import TokenBucket

        self.env = env
        missing = [name for name in self._REQUIRED_ENV if not os.environ.get(name)]
        if missing:
            raise ValueError(
                f"GearmentApiClient missing required env vars: {', '.join(missing)}"
            )
        self.api_key = os.environ['GEARMENT_API_KEY']
        self.api_secret = os.environ['GEARMENT_API_SECRET']
        self.base_url = os.environ['GEARMENT_API_BASE_URL'].rstrip('/')
        self._rate_limiter = TokenBucket(_DEFAULT_RATE_LIMIT, _DEFAULT_RATE_PERIOD)

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers = {
            'X-Gearment-Client-Key': self.api_key,
            'X-Gearment-Client-Secret': self.api_secret,
            'Accept': 'application/json',
        }
        return session

    def _request(self, method: str, path: str, **kwargs) -> dict:
        session = self._session()
        url = f"{self.base_url}/{path.lstrip('/')}"

        if not self._rate_limiter.acquire():
            _logger.warning(
                "Gearment local rate limiter exhausted; sending anyway (advisory)"
            )

        last_retry_after = None
        response = None
        for attempt in range(_MAX_RETRIES + 1):
            response = session.request(method, url, **kwargs)
            if response.status_code != 429:
                break

            header_value = response.headers.get('Retry-After')
            if header_value is not None:
                try:
                    last_retry_after = int(header_value)
                except (TypeError, ValueError):
                    last_retry_after = None

            if last_retry_after is not None:
                # Cap so a malformed/hostile upstream cannot pin us for hours.
                wait = min(last_retry_after, _MAX_RETRY_AFTER_SECONDS)
            else:
                wait = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
            time.sleep(wait)
        else:
            raise RateLimitError(
                "Gearment rate limit retries exhausted",
                retry_after=last_retry_after,
            )

        if response.status_code in _AUTH_STATUS_CODES:
            raise ValueError(
                f"Gearment auth failed (HTTP {response.status_code}); "
                "check GEARMENT_API_KEY / GEARMENT_API_SECRET"
            )
        response.raise_for_status()
        return response.json()

    def ping(self) -> dict:
        """Cheapest auth-validation call; returns parsed JSON on success."""
        return self._request('GET', 'api/v3/catalog', params={'limit': 1})
