"""EtsyApiAdapter — fetches Etsy receipts and emits canonical payloads (P0-16b2).

Implements `EtsyChannelAdapter` Protocol against the Etsy v3
`/shops/{shop_id}/receipts` endpoint. Each receipt is converted to
`EtsyOrderPayload` via `_receipt_to_payload`. The orchestrator
(`EtsyOrderSyncer`, P0-16c) consumes the iterator one payload at a
time and only advances the shop's sync watermark on success.

Lifecycle: per-call. The orchestrator instantiates the adapter inside
the cron transaction, threads the `EtsyApiClient` it already built,
and discards the adapter when done. No long-lived state.

Pagination: Etsy v3 receipts list returns `{count, results, next_offset}`.
We page through with `limit=100` (Etsy's documented hard cap) and stop
when either `next_offset` is null/missing OR `len(results) < limit`
(belt-and-braces against APIs that omit `next_offset` on the final
page).

Money: Etsy returns money as `{amount, divisor, currency_code}`. We
convert to a `float` via `amount / divisor` so the canonical payload
can use `float`. Divisor is typically 100 for fiat currencies, but
Etsy reserves the right to vary; do NOT hardcode 100.
"""

import logging
from datetime import datetime, timezone
from typing import Iterator

from .etsy_api_client import RateLimitError
from .etsy_channel_adapter import HealthStatus
from .etsy_order_payload import (
    EtsyAddressPayload,
    EtsyLineItemPayload,
    EtsyOrderPayload,
)

_logger = logging.getLogger(__name__)

_RECEIPTS_PAGE_LIMIT = 100


class EtsyApiAdapter:
    """Etsy v3 receipts adapter. One instance per orchestrator pass."""

    def __init__(self, client):
        """`client` is an `EtsyApiClient` (P0-15) already authenticated
        for the shop being synced. The adapter does not own auth — that's
        the orchestrator's responsibility."""
        self._client = client

    def fetch_new_orders(
        self, shop_id: int, since: datetime | None,
    ) -> Iterator[EtsyOrderPayload]:
        """Yield `EtsyOrderPayload` for every receipt modified after
        `since`. `since=None` triggers a full backfill (no
        `min_last_modified` filter sent — caller must ensure that's
        what they want; the syncer will pass NULL only on the very
        first sync of a shop).

        Iteration is lazy: each `next()` may issue a new HTTP page
        fetch. Callers that bail mid-iterator avoid downloading
        pages they will not consume.
        """
        offset = 0
        # Coerce defensively — service-layer contract says callers pass
        # `shop.id` (int), but `f'shops/{...}/receipts'` would happily
        # interpolate a malicious string like `42/orders/secret`. Cheap
        # belt for negligible cost.
        shop_path_id = int(shop_id)
        while True:
            params = {
                'limit': _RECEIPTS_PAGE_LIMIT,
                'offset': offset,
            }
            if since is not None:
                params['min_last_modified'] = self._datetime_to_unix(since)

            response = self._client.get(
                f'shops/{shop_path_id}/receipts',
                params=params,
            )
            results = response.get('results') or []
            for receipt in results:
                yield self._receipt_to_payload(receipt, shop_id=shop_id)

            # Etsy v3 returns next_offset = None (or missing) on the
            # final page. We trust that signal alone; the result-length
            # heuristic was over-eager and stopped before consuming
            # legitimately-paginated short pages.
            next_offset = response.get('next_offset')
            if not next_offset:
                return
            offset = next_offset

    def health_check(self, shop_id: int) -> HealthStatus:
        """Cheap liveness probe — does NOT fetch orders. Calls the
        client's `ping()` (which hits `/users/me`)."""
        try:
            self._client.ping()
        except RateLimitError:
            return HealthStatus.DEGRADED
        except Exception:  # pylint: disable=broad-except
            # Any auth / network / 5xx error means the syncer cannot
            # safely progress; mark DOWN and let the recovery cron
            # re-probe later.
            return HealthStatus.DOWN
        return HealthStatus.OK

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _receipt_to_payload(
        self, receipt: dict, shop_id: int,
    ) -> EtsyOrderPayload:
        """Map an Etsy v3 receipt JSON to canonical `EtsyOrderPayload`."""
        receipt_id = str(receipt['receipt_id'])
        message = receipt.get('message_from_buyer') or None  # '' → None

        return EtsyOrderPayload(
            etsy_shop_id=shop_id,
            etsy_receipt_id=receipt_id,
            # Etsy uses receipt_id as the canonical order identifier in
            # v3 (the legacy `order_id` field is the same value); keep
            # them aligned in our payload so downstream callers don't
            # have to reason about the difference.
            etsy_order_id=receipt_id,
            buyer_name=receipt.get('name') or '',
            buyer_country=receipt.get('country_iso') or '',
            order_date=self._unix_to_datetime(receipt.get('created_timestamp')),
            currency=self._money_currency(receipt.get('grandtotal')),
            amount_total=self._money_amount(receipt.get('grandtotal')),
            shipping_total=self._money_amount(receipt.get('total_shipping_cost')),
            line_items=tuple(
                self._transaction_to_line_item(txn)
                for txn in receipt.get('transactions') or ()
            ),
            shipping_address=EtsyAddressPayload(
                name=receipt.get('name') or '',
                street_1=receipt.get('first_line') or '',
                street_2=receipt.get('second_line'),
                city=receipt.get('city') or '',
                state=receipt.get('state') or None,
                zip=receipt.get('zip') or '',
                country_code=receipt.get('country_iso') or '',
            ),
            buyer_message=message,
            buyer_email=receipt.get('buyer_email'),
            listing_id=self._first_listing_id(receipt),
            payment_status='paid' if receipt.get('is_paid') else 'unpaid',
            is_gift=bool(receipt.get('is_gift')),
            gift_message=receipt.get('gift_message') or None,
            source='api',
            fetched_at=datetime.utcnow(),
            raw_source_id=f'receipt:{receipt_id}',
            last_modified=self._unix_to_datetime(
                receipt.get('last_modified_tsz') or receipt.get('updated_timestamp'),
            ),
            # P0-22 — channel-agnostic fields. The Etsy v3 receipts endpoint
            # returns these inconsistently (some shops/listings populate
            # `shipping_method` + `coupon_code`, others don't). When absent
            # we emit None so the ingestor writes a falsy value to keep the
            # symmetric write contract with the email path. `subtotal` is
            # always derivable from grandtotal - shipping_cost.
            shipping_service=receipt.get('shipping_method') or None,
            processing_time=self._processing_time(receipt),
            discount_code=receipt.get('coupon_code') or None,
            subtotal=self._money_amount(receipt.get('subtotal'))
            or (
                self._money_amount(receipt.get('grandtotal'))
                - self._money_amount(receipt.get('total_shipping_cost'))
            ),
        )

    @staticmethod
    def _processing_time(receipt: dict) -> str | None:
        """Render `min/max_processing_days` as the same human string format
        the email parser emits ("1-2 business days").
        """
        lo = receipt.get('min_processing_days')
        hi = receipt.get('max_processing_days')
        if lo is None and hi is None:
            return None
        if lo is None:
            return f'up to {hi} business days'
        if hi is None or lo == hi:
            return f'{lo} business days'
        return f'{lo}-{hi} business days'

    def _transaction_to_line_item(self, txn: dict) -> EtsyLineItemPayload:
        return EtsyLineItemPayload(
            listing_id=self._opt_str(txn.get('listing_id')),
            transaction_id=str(txn['transaction_id']),
            title=txn.get('title') or '',
            sku=txn.get('sku') or None,
            quantity=int(txn.get('quantity') or 1),
            unit_price=self._money_amount(txn.get('price')),
            variations=self._variations_to_dict(txn.get('variations')),
            personalisation=txn.get('personalization') or None,
        )

    @staticmethod
    def _money_amount(money: dict | None) -> float:
        if not money:
            return 0.0
        amount = money.get('amount') or 0
        divisor = money.get('divisor') or 1
        return amount / divisor

    @staticmethod
    def _money_currency(money: dict | None) -> str:
        if not money:
            return ''
        return money.get('currency_code') or ''

    @staticmethod
    def _datetime_to_unix(dt: datetime) -> int:
        # `since` may arrive naive (Odoo Datetime fields are stored as
        # naive UTC). Normalize to UTC explicitly before converting so
        # the request floor isn't skewed by the host's local timezone.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    @staticmethod
    def _unix_to_datetime(ts: int | None) -> datetime:
        if not ts:
            return datetime.utcnow()
        return datetime.utcfromtimestamp(int(ts))

    @staticmethod
    def _variations_to_dict(variations: list | None) -> dict[str, str]:
        """Etsy returns variations as `[{property_id, formatted_name,
        formatted_value}, ...]`. Flatten to `{name: value}` dropping
        property_id (not useful downstream)."""
        result = {}
        for v in variations or ():
            name = v.get('formatted_name')
            value = v.get('formatted_value')
            if name and value:
                result[name] = value
        return result

    @staticmethod
    def _first_listing_id(receipt: dict) -> str | None:
        """Convenience field — many UIs key off the first listing's id
        for thumbnail rendering."""
        for txn in receipt.get('transactions') or ():
            listing_id = txn.get('listing_id')
            if listing_id:
                return str(listing_id)
        return None

    @staticmethod
    def _opt_str(value) -> str | None:
        return str(value) if value is not None else None
