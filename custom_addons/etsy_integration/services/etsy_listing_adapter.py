"""EtsyListingAdapter — pages the Etsy v3 shop listings endpoint (P-LIST-PULL).

Read-only metadata ingest (Spec 008 US1). Mirrors `EtsyApiAdapter`:
per-call lifecycle, the orchestrator threads an already-authenticated
`EtsyApiClient`, the adapter owns no auth and no ORM. Variant inventory
(`GET /v3/application/listings/{id}/inventory`) is Slice 2
(P-LIST-INV-PULL) and is intentionally NOT fetched here.

Pagination: Etsy v3 returns `{count, results, next_offset}`. We page
with `limit=100` (Etsy's documented hard cap) and stop when
`next_offset` is null/missing — the same signal `EtsyApiAdapter`
trusts (the result-length heuristic was over-eager there and is not
reproduced).
"""

import logging
from datetime import datetime, timezone
from typing import Iterator

_logger = logging.getLogger(__name__)

_LISTINGS_PAGE_LIMIT = 100


class EtsyListingAdapter:
    """Etsy v3 shop-listings adapter. One instance per orchestrator pass."""

    def __init__(self, client):
        """`client` is an `EtsyApiClient` (P0-15) already authenticated
        for the shop being synced. The adapter does not own auth."""
        self._client = client

    def fetch_listings(
        self, shop_id: int, since: datetime | None = None,
    ) -> Iterator[dict]:
        """Yield raw Etsy listing dicts for `shop_id`.

        `since=None` fetches all listings (no `min_last_modified`
        filter). Iteration is lazy: each `next()` may issue a new HTTP
        page fetch, so a caller that bails mid-iterator avoids
        downloading pages it will not consume.
        """
        offset = 0
        # Coerce defensively — the path is interpolated, mirror the
        # EtsyApiAdapter belt against `42/listings/secret`-style input.
        shop_path_id = int(shop_id)
        while True:
            params = {
                'limit': _LISTINGS_PAGE_LIMIT,
                'offset': offset,
            }
            if since is not None:
                params['min_last_modified'] = self._datetime_to_unix(since)

            response = self._client.get(
                f'shops/{shop_path_id}/listings',
                params=params,
            )
            for listing in response.get('results') or []:
                yield listing

            next_offset = response.get('next_offset')
            if not next_offset:
                return
            offset = next_offset

    @staticmethod
    def _datetime_to_unix(dt: datetime) -> int:
        # Odoo Datetime fields are naive UTC; normalize before convert.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
