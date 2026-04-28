"""EtsyOrderIngestor — single-writer ingestion service (P0-16b1).

Thin wrapper around `OrderCreator.process_etsy_payload`. The wrapper
exists so that future cross-cutting concerns — audit-mode
short-circuit (P0-16c, architect Q4), status-only re-sync (FR-009),
buyer-message persistence (REQ-MSG-01) — can land here without
touching `OrderCreator` (which still serves the email path).

Single-writer invariant: only this service writes API-sourced
`sale.order` records. The orchestrator (`EtsyOrderSyncer`, P0-16c)
calls `ingest()` once per payload as it consumes adapter output.
Direct callers (e.g. webhook handler in P1) MUST go through this
class, not through `OrderCreator.process_etsy_payload` directly,
so the audit hooks remain in one place.
"""

import logging

from .order_creator import OrderCreator

_logger = logging.getLogger(__name__)


class EtsyOrderIngestor:
    """Apply a canonical `EtsyOrderPayload` to Odoo state.

    Stateless aside from a per-instance `OrderCreator` (which is itself
    stateless aside from xmlid lookup memoization). Safe to instantiate
    per-call inside cron handlers; the underlying `_env` keeps record
    cache scoped to the calling transaction.
    """

    def __init__(self, env):
        self._env = env
        self._creator = OrderCreator(env)

    def ingest(self, payload, shop):
        """Apply `payload` to the database. Returns the created
        `sale.order` recordset, or `None` if the payload was a
        duplicate of an already-imported receipt."""
        return self._creator.process_etsy_payload(payload, shop)
