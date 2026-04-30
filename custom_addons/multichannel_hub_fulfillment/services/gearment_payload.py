"""GearmentOrderPayload dataclass for P0-18b1 order submission.

Encapsulates order details for submission to Gearment API v3.
Provides serialization, idempotency key generation, and PII scrubbing hooks.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GearmentOrderPayload:
    """Order payload for Gearment API v3 POST /api/v3/orders.

    Required fields:
    - external_order_id: source system order ID (e.g., 'SO001', used for idempotency)
    - platform: 'etsy' (or other source)
    - store_id: Gearment account store identifier
    - quantity: unit count (1+)
    - product_id: Gearment legacy_product_id
    - address: dict with at least {city, country}
    - shipping_method: 'standard' | 'express' | etc.
    - design_files: list of {role, url} dicts (may be empty)

    Optional:
    - notes: special instructions (PII-sensitive, will be scrubbed in logs)
    - custom_attributes: arbitrary JSON (preserved in logs)
    """

    external_order_id: str
    platform: str
    store_id: str
    quantity: int
    product_id: int
    address: dict
    shipping_method: str
    design_files: list = field(default_factory=list)
    notes: Optional[str] = None
    custom_attributes: Optional[dict] = None

    @property
    def idempotency_key(self) -> str:
        """SHA-256 hex digest of external_order_id for Idempotency-Key header.

        Ensures that replayed requests with the same order ID result in the
        same Gearment order (no duplicates).
        """
        return hashlib.sha256(self.external_order_id.encode()).hexdigest()

    def serialize(self) -> dict:
        """Serialize payload to dict for JSON submission to Gearment API.

        Includes reference_id (same as external_order_id) for audit trail.
        Optional fields are included only if non-None.
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
