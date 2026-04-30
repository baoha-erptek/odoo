"""GearmentOrderPayload — canonical order payload + idempotency key.

Domain-level structure independent of Gearment wire format.
Adapter calls payload.serialize() to obtain the dict POSTed to /api/v3/orders.
"""
import hashlib
from dataclasses import dataclass, field


@dataclass
class GearmentOrderPayload:
    """Canonical order payload sent to Gearment API.

    Idempotency belt-and-braces (P0-18b1):
    - HTTP header `Idempotency-Key: sha256(external_order_id)` (set by adapter)
    - body field `reference_id == external_order_id` (set by serialize())

    P0-18b2 will confirm which approach Gearment honors.
    """

    external_order_id: str
    platform: str
    store_id: str
    quantity: int
    product_id: int
    address: dict
    shipping_method: str
    design_files: list = field(default_factory=list)
    notes: str | None = None
    custom_attributes: dict | None = None

    @property
    def idempotency_key(self) -> str:
        """SHA-256 hex of external_order_id for HTTP `Idempotency-Key` header."""
        return hashlib.sha256(self.external_order_id.encode()).hexdigest()

    def serialize(self) -> dict:
        """Return wire-format dict for Gearment POST body.

        `reference_id` mirrors `external_order_id` (idempotency dedup hint).
        Keeps `notes` / `custom_attributes` even when None for stable schema.
        """
        return {
            'external_order_id': self.external_order_id,
            'reference_id': self.external_order_id,
            'platform': self.platform,
            'store_id': self.store_id,
            'quantity': self.quantity,
            'product_id': self.product_id,
            'address': self.address,
            'shipping_method': self.shipping_method,
            'design_files': self.design_files,
            'notes': self.notes,
            'custom_attributes': self.custom_attributes,
        }
