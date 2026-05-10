"""Canonical in-memory payload for Etsy receipts (P0-16a).

Frozen dataclasses that every channel-source adapter (`EtsyApiAdapter`,
future `EtsyEmailAdapter`) emits and `EtsyOrderIngestor` consumes.
Immutability prevents adapters from mutating each other's data and
ensures the ingestion path is single-writer per receipt.

Module placement: this file lives in `etsy_integration/services/`,
not `multichannel_hub_core/services/` as `data-model.md` originally
suggested — see `specs/005-etsy-api-channel/findings.md` 2026-04-28
for the rationale (module CLAUDE.md prohibits Etsy-named code in
core; future channels will host their own canonical payload).

Reference: `specs/005-etsy-api-channel/data-model.md` lines 215-258.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class EtsyAddressPayload:
    """Buyer's shipping address. All fields are str|None — hashable."""

    name: str
    street_1: str
    street_2: str | None
    city: str
    state: str | None
    zip: str
    country_code: str


@dataclass(frozen=True)
class EtsyLineItemPayload:
    """One line item on a receipt.

    Note: `variations` and `personalisation` carry buyer-supplied data
    that the operator pipeline shows on the production dashboard.

    Mutability contract for `variations`: the dict is a per-receipt
    snapshot that an adapter builds fresh for each construction call
    (no shared references). Downstream consumers MUST treat it as
    read-only — `.update()` / `.pop()` / item assignment break the
    single-writer invariant. A `MappingProxyType` would enforce this
    at runtime but interacts poorly with `field(default_factory=...)`;
    the contract is documented instead. P0-16c ingestor review must
    re-confirm no consumer mutates `variations` in place.
    """

    listing_id: str | None
    transaction_id: str
    title: str
    sku: str | None
    quantity: int
    unit_price: float
    variations: dict[str, str] = field(default_factory=dict)
    personalisation: str | None = None
    # P0-22 — when the source channel supplies a custom display name for the
    # line (e.g. email parser's product_name string after personalisation
    # rendering) the ingestor copies it onto `sale.order.line.name`. None
    # means "use product.display_name" (current behaviour).
    name_override: str | None = None


@dataclass(frozen=True)
class EtsyOrderPayload:
    """Canonical payload emitted by adapters and consumed by the ingestor.

    `source` discriminates 'api' vs 'email' so the ingestor can write
    `sale.order.sync_source` and `raw_source_id` (e.g. `receipt:1234` or
    `email_log:567`) provides a back-pointer to the originating record
    for audit and re-processing.
    """

    etsy_shop_id: int
    etsy_receipt_id: str
    etsy_order_id: str
    buyer_name: str
    buyer_country: str
    order_date: datetime
    currency: str
    amount_total: float
    shipping_total: float
    # tuple, not list, so the payload is structurally immutable —
    # `.append()` against a list-typed field would bypass `frozen=True`
    # and break single-writer semantics (security-reviewer P0-16a, HIGH).
    line_items: tuple[EtsyLineItemPayload, ...]
    shipping_address: EtsyAddressPayload
    buyer_message: str | None
    buyer_email: str | None
    listing_id: str | None
    payment_status: str | None
    is_gift: bool | None
    gift_message: str | None
    source: Literal['api', 'email']
    fetched_at: datetime
    raw_source_id: str
    # P0-16c — last-modified timestamp from the source. For API
    # receipts this is `last_modified_tsz`; the syncer uses the max
    # over a batch as the new watermark and FR-009 status-only re-sync
    # uses it to distinguish stale fetches from genuine updates.
    last_modified: datetime | None = None
    # P0-22 — channel-agnostic shipping/discount metadata. Email receipts
    # always carry these; API receipts populate them when the v3 endpoint
    # exposes the fields (`shipping_method`, `min/max_processing_days`,
    # `coupon_code`). When unavailable, adapters set None and the ingestor
    # writes a falsy value to `sale.order.etsy_*`. Optional with `None`
    # default so existing call-sites (P0-16b2) don't break.
    shipping_service: str | None = None
    processing_time: str | None = None
    discount_code: str | None = None
    subtotal: float | None = None
