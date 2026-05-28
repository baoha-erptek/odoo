"""EtsyInventoryAdapter — fetches a listing's variant matrix (P-LIST-INV-PULL).

`GET /v3/application/listings/{listing_id}/inventory` returns a single
object `{products: [...]}` (NOT paginated — the whole variant array comes
back in one call; this is also why the future writeback must re-submit
the entire array, ADR-013). Per-call lifecycle, ORM-free, mirrors
`EtsyListingAdapter`; the orchestrator threads an authenticated
`EtsyApiClient`.
"""

import logging

_logger = logging.getLogger(__name__)


class EtsyInventoryAdapter:
    """Etsy v3 listing-inventory adapter. One instance per pass."""

    def __init__(self, client):
        self._client = client

    def fetch_variants(self, listing_id) -> list:
        """Return the raw `products[]` array for `listing_id` (one GET,
        no pagination). `int()` coercion mirrors the EtsyApiAdapter path
        belt."""
        response = self._client.get(
            f'listings/{int(listing_id)}/inventory')
        return response.get('products') or []
