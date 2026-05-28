# Implementation Plan: P1-12 — EtsyTrackingPusher (Spec 005 US3)

> Authored by orchestrator from `planner` agent output (planner has no Write tool).
> Slice dispatched 2026-05-16 via `/dispatch-slice P1-12`.

## Overview

Implement `EtsyTrackingPusher` service to push fulfillment tracking numbers back to
Etsy via `POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking`,
closing the full-cycle order loop (US3). Trigger is the Gearment
`tracking_order_updated` webhook handler (decision **D-A**); reads
`shipping.carrier.etsy_carrier_name` per ADR-005 & FR-014/015; writes audit row
source=`tracking_push` to `etsy.api.log`; sets
`sale.order.fulfillment.etsy_ship_notified_at` on success.

**Dependencies (all satisfied):**
- P1-10 (prod OAuth + Fernet token encryption) — LANDED 2026-05-16
- P1-06 (carrier mapping with `etsy_carrier_name`) — LANDED 2026-04-28
- P0-18b2c (Gearment webhook handler) — LANDED 2026-04-28
- E1 Etsy scope approval — APPROVED 2026-05-12 (`transactions_r/w` etc.)

---

## Slice tasks

- **T026** (finish): add `etsy_tracking_push_status`, `etsy_tracking_push_at`,
  `etsy_tracking_push_error` to `models/sale_order.py` per data-model.md §6
  (sync_source/etsy_last_modified parts landed in P0-16c).
- **T034**: implement `services/etsy_tracking_pusher.py`.
- **T035**: ir.cron `cron_etsy_tracking_push` default 5min (fallback path).
- **T036**: on-demand push button on `sale.order` form → synchronous push.
- **T037**: unmapped carrier (etsy_carrier_name NULL) → push `other` + warn-log.
- **T038**: Phase-1 DB + Phase-2 ORM tests.
- **T039**: wire from Gearment webhook per D-A.

---

## Field spec for T026 (verbatim, data-model.md §6)

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `etsy_tracking_push_status` | Selection: `none`/`pending`/`pushed`/`failed` | No | `none` | FR-016 — set by `EtsyTrackingPusher` |
| `etsy_tracking_push_at` | Datetime | No | — | Timestamp of successful push |
| `etsy_tracking_push_error` | Text | No | — | Error message if push failed |

Written by service layer only — no constraints/computed/CRUD overrides.

---

## EtsyTrackingPusher API surface

`custom_addons/etsy_integration/services/etsy_tracking_pusher.py` (NEW, ~150 LOC).
Per ORM-free-services constraint, the class takes `env` explicitly (no implicit
`Environment.envs`).

```python
class EtsyTrackingPusher:
    def __init__(self, env): ...
    def push(self, order) -> bool: ...          # sync entry: webhook + button + cron
    def _validate_order(self, order) -> tuple[bool, str]: ...
    def _get_carrier_name(self, fulfillment) -> str | None: ...
    def _push_to_api(self, order, fulfillment, carrier_name) -> tuple[bool, str]: ...
    def _audit_log(self, order, endpoint, status, summary, error_msg): ...
```

- Etsy v3 endpoint: `POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking`
  body `tracking_code` (carrier enum), `tracking_number`.
- Client construction reuses P1-10 pattern: `EtsyApiClient(order.etsy_shop_id)`;
  client internally calls `shop.sudo()._get_access_token()` (Fernet-decrypted).
- Retry-on-5xx delegated to `EtsyApiClient` (`_MAX_RETRIES=3` + backoff).
- On success: `etsy_tracking_push_status='pushed'`, `etsy_tracking_push_at=now`,
  set fulfillment `etsy_ship_notified_at`; audit `http_status=201`.
- On failure: `etsy_tracking_push_status='failed'`, `etsy_tracking_push_error`,
  audit with actual status + truncated body.

---

## Webhook wiring (decision D-A — binding)

**File**: `custom_addons/multichannel_hub_fulfillment/services/gearment_webhook_dispatcher.py`,
handler `_handle_tracking_order_updated(body)` (~line 226). After the existing
`self._write_fulfillment(fulfillment, vals)` call succeeds, add a soft-fail
synchronous `EtsyTrackingPusher(self.env).push(order)`:

```python
# P1-12: push tracking to Etsy after Gearment webhook writes it (D-A).
# Soft-fail: tracking already local; webhook still returns 200; cron retries.
try:
    from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
        EtsyTrackingPusher,
    )
    EtsyTrackingPusher(self.env).push(order)
except Exception as exc:  # noqa: BLE001
    _logger.warning("P1-12: etsy tracking push soft-failed for %s: %s",
                     order.name, exc, exc_info=True)
```

Rationale (owner directive 2026-05-10 D4): Etsy tab is a read-only mirror; the
trigger must come from upstream (Gearment), NOT `sale.order.fulfillment.write`.
5-min cron (T035) handles webhook-time network failures.

---

## State machine

`none` → (`pending` reserved for future async) → `pushed` | `failed`.
Sync push skips `pending`, goes directly to `pushed`/`failed`. `failed` is
retriable by cron (T035) or button (T036). Retry-on-5xx is internal to
`EtsyApiClient`; exhausted retries → `failed`.

---

## Open questions / risks — RESOLVED at dispatch (2026-05-16)

1. **`etsy_ship_notified_at`** — RESOLVED: already exists on
   `sale.order.fulfillment` (added P1-03 T038, base in
   `multichannel_hub_core/models/sale_order_fulfillment.py`). No new field.
2. **`receipt_id` sourcing** — RESOLVED: `sale.order.etsy_order_id` IS the Etsy
   receipt_id. `etsy_api_adapter.py:122-127` sets both `etsy_receipt_id` and
   `etsy_order_id` to `receipt_id` ("Etsy uses receipt_id as the canonical order
   identifier"). Etsy v3 is 1:1 order↔receipt — no multi-receipt handling needed,
   no STOP.
3. Webhook immediate-sync vs async-queue → sync chosen (no queue model);
   fallback cron covers failures.

### Spec drift to honor (planner assumptions corrected)

- Fulfillment carrier field is **`shipping_carrier_id`** (M2o), NOT `carrier_id`.
  Base model: `multichannel_hub_core/models/sale_order_fulfillment.py`
  (`order_id`, `tracking_number`, `shipping_carrier_id`).
- `_get_carrier_name` reads `fulfillment.shipping_carrier_id.etsy_carrier_name`.
- shop_id for the Etsy endpoint: resolve via `order.etsy_shop_id` (M2o
  `etsy.shop`) → numeric shop id field (confirm exact field name during RED;
  P0-FIX-DEMO-NUMERIC-SKU referenced `etsy_numeric_shop_id`).

---

## Agent dispatch order (9-phase loop)

1. **RED** (`tdd-guide`): `tests/test_phase1_tracking_push_db.py` (column
   existence, Selection enforcement, cron record) + `tests/test_phase2_tracking_pusher_orm.py`
   (happy path, missing carrier, 5xx retry, missing fulfillment, audit row,
   button action, cron). **Verify tests registered in `tests/__init__.py`** and
   actually execute (count assertions, not just exit code).
2. **GREEN**: service + `sale_order.py` fields/cron/button + views + cron XML +
   webhook wiring + manifest.
3. **Review**: `code-reviewer` + `security-reviewer` in parallel (single message,
   two Agent calls). Block on CRITICAL/HIGH. Verify reviewer diff claims with
   `git diff --stat HEAD` before applying any fix.
4. **Verify**: `-u etsy_integration --stop-after-init` exit 0; run both test
   tags; `ruff check custom_addons/etsy_integration/`; grep `_logger.info`/`print(`.
5. **Commit**: one conventional commit `[etsy_integration] feat(P1-12): ...`
   citing T026/T034-T039.
6. **Document**: tasks.md `[X]`; tracker P1-12 `state=done` + last reviewed;
   findings.md P1-12 section.
7. **Learn**: `/learn` or explicit no-new-patterns note.

---

## Exit-criteria mapping (12 tasks created in Phase 0)

| Task # | Criterion | Source |
|--------|-----------|--------|
| 1 | T026 fields added | tasks.md |
| 2 | T034 service | tasks.md |
| 3 | T035 cron | tasks.md |
| 4 | T036 button | tasks.md |
| 5 | T037 unmapped carrier | tasks.md |
| 6 | T038 tests | tasks.md |
| 7 | T039 webhook wiring (D-A) | tasks.md |
| 8 | all tasks `[X]` in tasks.md | playbook |
| 9 | tests pass ≥80% changed lines | playbook |
| 10 | module installs clean | playbook |
| 11 | ACL/sudo/raw-SQL hygiene | playbook |
| 12 | tracker + findings + /learn | playbook |
