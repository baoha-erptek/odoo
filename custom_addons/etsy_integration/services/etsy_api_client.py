"""Etsy API v3 client — RED stub. Will be implemented in GREEN phase.

Auth: two HTTP headers are required on every request:
  - Authorization: Bearer <access_token>
  - x-api-key: <client_id>

Both tokens come from etsy.shop record fields (P0-14). client_id is read from
secrets/credentials.json (same file etsy_oauth.py reads from).

Rate limit: per-instance TokenBucket(rate=8, period=1.0) from
multichannel_hub_core.utils.rate_limiter. Advisory only on send.

429 handling: honor Retry-After capped at 60s, fall back to (1, 2, 4)
exponential backoff, raise RateLimitError after 3 retries.

401 handling: refresh access token via etsy_oauth.refresh_access_token(),
write new tokens to shop record via sudo() (fields have group_system ACL),
retry original request once. If refresh fails, raise ValueError.

Proactive refresh: if shop.etsy_oauth_token_expires_at is within next 60
seconds, refresh BEFORE sending.
"""


def _read_credentials():
    """Stub: read client_id and client_secret from secrets/credentials.json.

    This will be implemented in GREEN phase. Tests mock this function.
    """
    raise NotImplementedError("Will be implemented in GREEN phase")


class RateLimitError(Exception):
    """Raised when Etsy 429s exceed the retry budget."""

    def __init__(self, message: str, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class EtsyApiClient:
    """Etsy API v3 client (P0-15).

    Reads access/refresh tokens from etsy.shop record and client_id from
    secrets/credentials.json. Applies rate limiting (advisory), 429-retry
    policy, and 401-refresh policy.
    """

    pass
