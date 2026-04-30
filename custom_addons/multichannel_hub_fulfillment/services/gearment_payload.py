"""GearmentOrderPayload — canonical order payload for Gearment API (P0-18b1).

Dataclass that encapsulates all fields required by Gearment's /api/v3/orders
POST endpoint. Includes serialization, PII scrubbing, and idempotency key
generation.

Idempotency: Gearment requires `Idempotency-Key` header (HMAC or hash-based
to prevent duplicate orders if the client retries). We use SHA-256 hex of
external_order_id — deterministic, cheap, and recoverable from any retry.

PII Scrubbing: Before storing in `gearment.api.log.request_payload_summary`,
the payload dict is filtered via `_scrub_pii()` to remove:
  - buyer_name, address_line_1, address_line_2
  - street_1, street_2 (legacy address aliases)
  - email, phone, notes
  - address (the entire dict, which may contain composite PII)
"""

import hashlib
from dataclasses import dataclass, field


@dataclass
class GearmentOrderPayload:
    """Canonical order payload for Gearment API /api/v3/orders."""

    external_order_id: str
    """Unique order ID from upstream (e.g., Etsy SO#, internal reference)."""

    platform: str
    """Origin platform (e.g., 'etsy', 'shopify', 'internal')."""

    store_id: str
    """Store/account ID at the origin platform."""

    quantity: int
    """Total item quantity (sum of all line items)."""

    product_id: int
    """Gearment product ID (legacy_product_id from catalog)."""

    address: dict
    """Shipping address {street_1, street_2, city, state, zip, country_code}."""

    shipping_method: str
    """Shipping speed ('standard', 'express', 'overnight', etc.)."""

    design_files: list[dict]
    """List of design file specs [{role, url, ...}, ...]."""

    notes: str | None = None
    """Optional order notes (e.g., gift wrapping, special instructions)."""

    custom_attributes: dict | None = None
    """Optional platform-specific metadata."""

    def serialize(self) -> dict:
        """Return serialized dict for API POST body.

        Includes all required fields plus reference_id (set to
        external_order_id). Optional fields (notes, custom_attributes) are
        included if non-None.
        """
        result = {
            'external_order_id': self.external_order_id,
            'reference_id': self.external_order_id,
            'platform': self.platform,
            'store_id': self.store_id,
            'quantity': self.quantity,
            'product_id': self.product_id,
            'address': self.address,
            'shipping_method': self.shipping_method,
            'design_files': self.design_files,
        }
        if self.notes is not None:
            result['notes'] = self.notes
        if self.custom_attributes is not None:
            result['custom_attributes'] = self.custom_attributes
        return result

    @property
    def idempotency_key(self) -> str:
        """SHA-256 hex of external_order_id for Idempotency-Key header."""
        return hashlib.sha256(self.external_order_id.encode()).hexdigest()


def _scrub_pii(payload: dict) -> dict:
    """Remove PII fields from payload dict for audit logging.

    Drops: buyer_name, address_line_1, address_line_2, street_1, street_2,
           email, phone, notes, address (the entire dict).

    Returns new dict (immutable input).
    """
    pii_keys = {
        'buyer_name', 'address_line_1', 'address_line_2',
        'street_1', 'street_2',
        'email', 'phone', 'notes', 'address',
    }
    return {k: v for k, v in payload.items() if k not in pii_keys}
