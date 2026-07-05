"""GearmentOrderPayload — canonical payload for /api/v3/orders/draft (P4-01).

Schema regenerated 2026-05-10 from the readiness probe in
`specs/004-fulfillment-routing/findings.md` 2026-05-09 (G2 contract gap).
The legacy schema (external_order_id / address dict / quantity / product_id)
is fully replaced.

Wire shape (`/api/v3/orders/draft` POST body — schema-corrected 2026-05-10):

    {"data": {
        "reference_id": "SO-2026-00123",
        "addresses": [{
            "first_name": "Alice", "last_name": "Buyer",
            "street_1": "123 Main St", "zip_code": "02108", "country_code": "US",
            ...
        }],
        "line_items": [{
            "legacy_id": 1234, "quantity": 1, "sku": "MUG-001",
            "printing_options": [
                {"location_code": "PRINT_LOCATION_CODE_FRONT", "url": "https://drive.../front.png"},
                {"location_code": "PRINT_LOCATION_CODE_BACK", "url": "https://drive.../back.png"},
            ],
            ...
        }],
        ...
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
    """Buyer's address per /orders/draft schema."""

    first_name: str
    last_name: str
    street_1: str
    street_2: str | None
    city: str
    state: str | None
    zip_code: str
    country_code: str
    phone: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class GearmentLineItem:
    """One line item on a Gearment order draft.

    Schema corrected by P4-01-FIX-PAYLOAD-SCHEMA after live `/api/v3/orders/draft`
    rejected the previous (`product_id` + flat `design_url_front/back`) shape.
    Real schema per `specs/004-fulfillment-routing/research.md:43-44`:
      - `legacy_id` (Gearment catalog int; alternatively `variant_id`)
      - `printing_options[]` with `{location_code, url}` per design placement.

    `printing_options` is a tuple (not list) so the dataclass remains
    structurally immutable — same pattern as `GearmentOrderPayload.line_items`.
    """

    legacy_id: int
    quantity: int
    sku: str | None = None
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

        Probe S3 finding: `/orders/draft` rejects `data: []` array envelope
        with `unmarshal proto: unexpected token [`. Single-object envelope
        `{"data": {...}}` is the working shape.
        """
        return {
            'data': {
                'reference_id': self.reference_id,
                'store_id': self.store_id,
                'addresses': [
                    _without_none(asdict(addr)) for addr in self.addresses
                ],
                'line_items': [
                    _without_none(asdict(item)) for item in self.line_items
                ],
                'shipping_method': self.shipping_method,
                'notes': self.notes,
                'custom_attributes': self.custom_attributes,
            },
        }


def _without_none(d: dict) -> dict:
    """Drop None-valued keys so optional fields don't pollute the wire body."""
    return {k: v for k, v in d.items() if v is not None}
