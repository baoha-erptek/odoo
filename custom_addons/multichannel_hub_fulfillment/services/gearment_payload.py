"""GearmentOrderPayload — canonical payload for /api/v3/orders/draft (P4-01).

Schema regenerated 2026-05-10 from the readiness probe in
`specs/004-fulfillment-routing/findings.md` 2026-05-09 (G2 contract gap).
The legacy schema (external_order_id / address dict / quantity / product_id)
is fully replaced.

Wire shape (`/api/v3/orders/draft` POST body — proven live 200 on 2026-07-05):

    {"data": {
        "reference_id": "SO-2026-00123",
        "store_id": "JaHandmadeArt",
        "platform": "MARKETPLACE_PLATFORM_ETSY",
        "address": {
            "first_name": "Alice", "last_name": "Buyer",
            "street_1": "123 Main St", "city": "Boston",
            "state_code": "MA", "zip_code": "02108", "country_code": "US",
            "phone_no": "+1 555 0100", "email": "a@b.com",
        },
        "shipping_method": "METHOD_STANDARD",
        "line_items": [{
            "variant_id": "GM0249020374", "quantity": 1,
            "printing_options": [
                {"location_code": "PRINT_LOCATION_CODE_FRONT", "url": "https://drive.../front.png"},
                {"location_code": "PRINT_LOCATION_CODE_BACK", "url": "https://drive.../back.png"},
            ],
        }],
    }}

Idempotency belt-and-braces:
- HTTP `Idempotency-Key` header = sha256(reference_id) (set by adapter)
- body field `reference_id` mirrors the SO name (Gearment dedupe hint)

Both adapter writes; whichever Gearment honors wins. P0-18b1 captured both.
"""

import hashlib
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GearmentAddress:
    """Buyer's address per /orders/draft schema.

    Field names ARE the wire keys (via `asdict`). Corrected 2026-07-05 from the
    live `/orders/draft` 400 body + doc crawl: the validator wants `state_code`
    and `phone_no` (not `state`/`phone`); unknown keys are silently dropped, so
    the mismatch surfaced as "value length must be at least 1" on every field.
    """

    first_name: str
    last_name: str
    street_1: str
    street_2: str | None
    city: str
    state_code: str | None
    zip_code: str
    country_code: str
    phone_no: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class GearmentLineItem:
    """One line item on a Gearment order draft.

    Schema corrected 2026-07-05 after the enum fix unblocked the draft and the
    400 moved to `some gm product variants not found` (Defect-2026-05-10-02):
    draft line items are keyed by the GM-prefixed catalog `variant_id`
    (e.g. `GM0249020374`), NOT the `legacy_id` product int. The variant_id is
    the merchant's `x_gearment_sku` on product.template.

    `printing_options` is a tuple (not list) so the dataclass remains
    structurally immutable — same pattern as `GearmentOrderPayload.line_items`.
    """

    variant_id: str
    quantity: int
    printing_options: tuple[dict, ...] = ()
    personalisation: str | None = None
    custom_attributes: dict | None = None


@dataclass(frozen=True)
class GearmentOrderPayload:
    """Canonical payload sent to `POST /api/v3/orders/draft`.

    `addresses` and `line_items` are tuples (not lists) so the dataclass is
    structurally immutable — `.append()` on a list-typed field would bypass
    `frozen=True`. Pattern carried forward from `EtsyOrderPayload`.
    """

    reference_id: str
    store_id: str
    platform: str
    addresses: tuple[GearmentAddress, ...]
    line_items: tuple[GearmentLineItem, ...]
    shipping_method: str | None = None
    notes: str | None = None
    custom_attributes: dict | None = None

    @property
    def idempotency_key(self) -> str:
        """SHA-256 hex of reference_id for HTTP `Idempotency-Key` header."""
        return hashlib.sha256(self.reference_id.encode()).hexdigest()

    def serialize(self) -> dict:
        """Return wire-format dict for the POST body.

        Shape proven with a live 200 on 2026-07-05 (draft order_id
        260705P-GM3MUJU-Y20XJXY6). `data` is a bare object (array envelope 400s
        with `unexpected token [`); the buyer address is the SINGULAR `address`
        key (the `addresses` array is response-only); `platform` is required
        (`MARKETPLACE_PLATFORM_ETSY`) else the API 404s "marketplace not found".
        `notes`/`custom_attributes` are NOT sent — they are unknown to the draft
        schema; keeping them off the wire keeps the proven-200 body exact.
        """
        return {
            'data': _without_none({
                'reference_id': self.reference_id,
                'store_id': self.store_id,
                'platform': self.platform,
                # SINGULAR `address` — the draft request takes one buyer address.
                'address': (
                    _without_none(asdict(self.addresses[0]))
                    if self.addresses else None
                ),
                'line_items': [
                    _without_none(asdict(item)) for item in self.line_items
                ],
                'shipping_method': self.shipping_method,
            }),
        }


def _without_none(d: dict) -> dict:
    """Drop None-valued keys so optional fields don't pollute the wire body."""
    return {k: v for k, v in d.items() if v is not None}
