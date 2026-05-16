"""EtsyOrderIngestor — single-writer ingestion service.

Routes a canonical `EtsyOrderPayload` to the right write path:

- New receipt (no matching `etsy_order_id`): delegate to
  `OrderCreator.process_etsy_payload` for full create.
- Existing receipt (matching `etsy_order_id`): apply FR-009 status-only
  re-sync — update `payment_status` + `etsy_last_modified` only,
  preserving operator fields (`mp_note`, `pic_user_id`, design state).

P0-16b1 introduced the wrapper. P0-16c (this revision) hosts the
status-only re-sync logic here, NOT inside `OrderCreator`, to keep
single-writer semantics: only this service writes API-sourced re-syncs.
The syncer (P0-16c orchestrator) calls `ingest()` once per payload as
it consumes adapter output.
"""

import logging

from .order_creator import OrderCreator

_logger = logging.getLogger(__name__)

# FR-009 — fields written on status-only re-sync. Operator-owned
# fields (mp_note, pic_user_id, design state) are intentionally
# absent. Add to this list ONLY when a new field is provably
# adapter-sourced and never operator-edited.
_STATUS_ONLY_FIELDS = ('payment_status', 'etsy_last_modified')


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
        """Apply `payload` to the database.

        T058 / ADR-008a §2 — the ingestor is source-aware: a shop runs
        exactly one active adapter at a time, recorded on
        `shop.active_source` ('api' or 'email'). The adapter that built
        this payload is `payload.source`. A mismatch (e.g. a late
        email-sourced payload arriving for a shop already cut over to
        the API adapter, or vice versa) is an invariant violation worth
        flagging — but we still ingest: the syncer cursor is the
        authoritative stale-fetch gate, and dropping a real receipt
        would lose order data. Soft-warn only, no behaviour change.

        Returns the `sale.order` record (created or re-synced). Returns
        `None` if the payload had no usable line items (delegated to
        `OrderCreator` which already handles that edge case).
        """
        active = shop.active_source
        if payload.source != active:
            expected = 'api' if active == 'api' else 'email'
            _logger.warning(
                'Etsy ingest source mismatch: shop %s (id=%s) '
                'active_source=%s but payload.source=%s (expected %s); '
                'ingesting anyway (syncer cursor is authoritative).',
                shop.name, shop.id, active, payload.source, expected,
            )
        existing = self._env['sale.order'].search(
            [('etsy_order_id', '=', payload.etsy_order_id)], limit=1,
        )
        if existing:
            return self._status_only_resync(existing, payload)
        return self._creator.process_etsy_payload(payload, shop)

    def _status_only_resync(self, order, payload):
        """FR-009 — refresh adapter-owned fields without disturbing
        operator-owned fields. Idempotent: writing the same values is
        a no-op as far as the operator is concerned.

        We update `etsy_last_modified` regardless of monotonicity —
        the syncer's cursor is the authoritative gate against stale
        re-fetches; if the syncer hands us an older payload, that's
        a bug in the syncer, not the ingestor. Letting the field
        reflect the most recent fetch keeps it useful for diagnostics.
        """
        vals = {
            'payment_status': payload.payment_status or False,
            'etsy_last_modified': payload.last_modified or False,
        }
        # Filter out no-op writes so we don't churn `write_date` on
        # orders whose payment status is unchanged.
        vals = {
            k: v for k, v in vals.items()
            if order[k] != v
        }
        if vals:
            order.write(vals)
            _logger.debug(
                'Etsy re-sync: order %s (#%s) updated %s',
                order.name, payload.etsy_order_id, list(vals),
            )
        return order
