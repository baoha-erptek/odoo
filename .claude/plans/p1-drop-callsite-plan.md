# P1-DROP-CALLSITE — Tactical Implementation Plan

**Slice:** P1-DROP-CALLSITE (Master Plan 006, Wave: P1 Hybrid dropship + MTO)
**Branch:** `feature/006-master-plan-coding`
**Owner:** Dev (orchestrator inline)
**Authority:** ADR-010 Amendment 2026-05-03 + Clarifications 2026-05-04 (1A / 2A / 3B)
**Depends on:** P1-DROP-SEED (done)

## Goal

Relocate the Gearment-POD auto-push trigger from `sale.order._write_pipeline_state` (a private hook misused as an integration point) to `purchase.order.action_confirm` (the standard Odoo procurement boundary). Same commit removes all orphans. SO pipeline state transitions are now driven by the surrounding procurement / picking lifecycle, not by hand-rolled hooks.

---

## 1. File-by-file changes

### NEW — `custom_addons/multichannel_hub_fulfillment/models/purchase_order.py`
- `class PurchaseOrder(models.Model)` with `_inherit = 'purchase.order'`.
- Override `button_confirm()` (the public action that PO form's "Confirm Order" button calls; `action_confirm` is the alias on some Odoo versions — confirm with `git -C odoo grep` once during implementation; default to `button_confirm` since that is canonical in Odoo 19 CE).
- Logic:
  1. `result = super().button_confirm()` first — let standard PO confirmation set state, generate procurement, etc.
  2. For each `po` in `self.filtered(self._is_gearment_dropship_po)`:
     - Walk `po.order_line.sale_line_id.order_id` → unique `sale.order` set (`_get_source_sale_orders` helper).
     - For each SO: skip if `so.x_gearment_outbound_ref` (idempotency / migration safety).
     - Call `so.action_push_to_gearment()` — propagates exception on failure (after refactor in §3).
     - On success: `action_push_to_gearment` already stamps fields; advance the SO pipeline to `confirmed` via `super(SaleOrder, so)._write_pipeline_state(confirmed_state, change_type='automatic')` *from the PO model* — NO; instead the SO method should expose a public helper `_advance_pipeline_to(code)` (small refactor in `sale_order.py`); planner-leg defers the public-helper rename to a follow-up if mhc already provides one.
  3. Return `result`.
- Helpers (private):
  - `_is_gearment_dropship_po(self) -> bool` — true if `picking_type_id.code == 'dropship'` AND `partner_id == env.ref('multichannel_hub_fulfillment.partner_gearment_vendor')`. Use `env.ref(..., raise_if_not_found=False)` so absence of seed is a clean no-op (not an exception during install).
  - `_get_source_sale_orders(self) -> 'sale.order'` — returns the set of SOs feeding lines on this PO.
- Audit-on-rollback: when `action_push_to_gearment` raises, post a chatter line on the SO inside `with self.env.cr.savepoint(flush=False)` so the message survives the outer transaction rollback. Then `raise UserError(_("Gearment push failed for %s: %s. Confirm order to retry.", so.name, exc))`.

### NEW — `custom_addons/multichannel_hub_fulfillment/models/stock_picking.py`
- `class StockPicking(models.Model)` with `_inherit = 'stock.picking'`.
- Override `_action_done(self)` (post-validate hook; standard for all-line-done events).
  1. `result = super()._action_done()` first.
  2. For each `picking` where `picking_type_id.code == 'dropship'` AND `picking.sale_id`:
     - Call `picking.sale_id._advance_pipeline_to('shipped')` (helper added in §3).
     - Idempotent: helper short-circuits if the SO is already at `shipped` or beyond.
  3. Return `result`.

### MODIFIED — `custom_addons/multichannel_hub_fulfillment/models/sale_order.py`
**Resolution 3B legacy cleanup — same commit as relocation.**

Delete:
- Module docstring lines 1-21 (replace with a 3-line docstring describing the new shape).
- `_write_pipeline_state` override (lines ~63-77).
- `_gearment_push_should_fire` (lines ~79-93).
- `_enqueue_gearment_push` (lines ~95-115).
- The whole rollback branch in `action_push_to_gearment` (lines ~149-165) — outer-transaction rollback at the PO level now handles failure cleanup. The except branch becomes: log + re-raise as a more readable exception.
- `_cron_retry_stalled_gearment_pushes` (lines ~170-191) — cron is gone; retry semantics now = "operator re-clicks Confirm on the PO."
- `from datetime import timedelta` import (no longer needed once cron is gone).

Keep + refactor:
- `x_gearment_outbound_ref`, `x_gearment_pushed_at`, `x_gearment_status` fields — unchanged.
- `action_push_to_gearment` — strip the catch-and-rollback; leave the success branch intact (stamp fields, post chatter). Add a single `try/except` that wraps the adapter call, logs, then `raise UserError` so callers (PO override, manual button) get a clean exception. Manual-button UX: still works — the `UserError` will pop a dialog.
- ADD new public helper `_advance_pipeline_to(self, target_code: str) -> None`:
  - Find target state via `self.x_pipeline_id.state_ids.filtered(lambda s: s.code == target_code)[:1]`.
  - Skip if `self.x_pipeline_state_id.code == target_code` (idempotent).
  - TODO note: long-term this belongs on `sale.order` in `multichannel_hub_core` — file a follow-up. For now, mhf-local helper avoids cross-spec churn.
  - Call `super(SaleOrder, self)._write_pipeline_state(target, change_type='automatic')` — note we still call the private method, but only from inside *this module* with documented intent (not via `bypass_pipeline_state_guard` context).

### MODIFIED — `custom_addons/multichannel_hub_fulfillment/models/__init__.py`
Add (in dependency order — purchase_order after sale_order so the inherit Order is consistent):
```
from . import purchase_order
from . import stock_picking
```

### DELETED — `custom_addons/multichannel_hub_fulfillment/data/ir_cron_gearment_retry.xml`
Whole file deletes (only one cron, `ir_cron_gearment_retry_stalled`, which is gone).

### MODIFIED — `custom_addons/multichannel_hub_fulfillment/__manifest__.py`
- Bump `version` 19.0.1.0.11 → 19.0.1.0.12.
- Remove `'data/ir_cron_gearment_retry.xml'` from the `data` list (line 15).
- All other entries unchanged.

### NEW — `custom_addons/multichannel_hub_fulfillment/tests/test_p1_drop_callsite.py`
Phase 2 ORM tests. See §4.

### MODIFIED — `custom_addons/multichannel_hub_fulfillment/tests/test_phase1_install.py`
Add Phase 1 DB orphan-removal asserts. See §4.

### MODIFIED — `custom_addons/multichannel_hub_fulfillment/tests/test_gearment_auto_push_orm.py`
This existing test file references the deleted methods (line 179: `self.env['sale.order']._cron_retry_stalled_gearment_pushes()`). **Decision: delete the test file entirely** — its semantics are superseded by the new `test_p1_drop_callsite.py`. Do not try to migrate test-by-test; the hook surface is gone, so most assertions become meaningless. Removal is part of Resolution 3B cleanup.

### MODIFIED — `custom_addons/multichannel_hub_fulfillment/tests/__init__.py`
- Add `from . import test_p1_drop_callsite`.
- Remove `from . import test_gearment_auto_push_orm` if present.

---

## 2. PO `action_confirm` (`button_confirm`) override logic — detail

### Detection: is this a Gearment dropship PO?
```
picking_type_id.code == 'dropship'   AND
partner_id == env.ref('multichannel_hub_fulfillment.partner_gearment_vendor', raise_if_not_found=False)
```
- `picking_type_id.code == 'dropship'` is the standard Odoo dropshipping picking-type code (set by `stock_dropshipping` module).
- `partner_id` equality against the seeded partner — `env.ref` returns `False` when the seed hasn't loaded yet (e.g. during base install order), so the override silently no-ops, not crashes.

### PO → SO walk
- `po.order_line.sale_line_id.order_id` is canonical in Odoo (the line-level link installed by `sale_purchase`/`stock_dropshipping`).
- Use `mapped` to flatten and dedupe: `sos = po.order_line.sale_line_id.order_id`.
- For multi-SO POs (rare; possible if procurement consolidated), iterate.

### Idempotency — three layers
1. **PO-level** — if every linked SO has `x_gearment_outbound_ref`, the override is a no-op.
2. **Per-SO** — skip individual SO if `x_gearment_outbound_ref` already set.
3. **`action_push_to_gearment`** — keeps its existing per-record `if order.x_gearment_outbound_ref: continue` guard.

### Push-failure path (Resolution 2A)
```
try:
    so.action_push_to_gearment()
except (UserError, Exception) as exc:
    with self.env.cr.savepoint(flush=False):
        so.message_post(body=_(
            "Gearment push failed during PO %s confirm: %s",
            po.name, str(exc)[:512]))
    raise UserError(_(
        "Gearment push failed for SO %s: %s. PO not confirmed; "
        "fix the issue and re-click Confirm on the PO.",
        so.name, str(exc)[:240]))
```
- The `savepoint(flush=False)` pattern: chatter `mail.message` insert is committed at the savepoint level so the audit trail survives the outer `UserError` rollback. The `flush=False` matters — Odoo's default flush would re-trigger the failed operation; we want isolation.
- Stamp/advance happens INSIDE `action_push_to_gearment` on the success path; the PO override does not need to write `x_pipeline_state_id` itself if the SO method advances on success.

**Decision (lock this in implementation):** `action_push_to_gearment` will, on success, also call `self._advance_pipeline_to('confirmed')` so the pipeline transition is owned by one method. This collapses pipeline-state ownership for the push side into a single function, rather than scattering it.

---

## 3. Picking-done → pipeline `shipped` logic — detail

### Hook choice
- `_action_done` fires after a picking transitions to `done` state (whether by button_validate, immediate transfer, or backorder split). This is the standard Odoo extension point for "the picking just completed".
- DO NOT inherit `button_validate` — it's the UI button only; backorder/auto paths skip it.

### Detection
```
picking.picking_type_id.code == 'dropship'   AND
picking.sale_id  # standard m2o populated for procurement-driven pickings
```
- `picking.sale_id` is set by `stock_dropshipping` for dropship pickings linked to an SO via procurement.

### Idempotency
- The new `_advance_pipeline_to('shipped')` helper short-circuits if the SO is already at `shipped`. If a future state `delivered` exists in the pipeline that is downstream of `shipped`, the helper should also skip (don't move backwards). Implementation: compare `x_pipeline_state_id.sequence` to target-state `sequence` and only advance if target is strictly forward.

### What about the bypass-context?
- Demo runner uses `bypass_pipeline_state_guard` context for direct field writes. Per ADR/findings, this is a documented escape hatch for E2E scripts — internal modules MUST NOT use it. We call `_write_pipeline_state` (private, but in-module) with `change_type='automatic'`. This is the correct path.
- Follow-up (NOT in scope for this slice): mhc could expose `action_advance_pipeline(target_code)` as a public wrapper. File a tracker entry as `P1-PIPELINE-PUBLIC-ADVANCE` if the smell becomes worth fixing.

---

## 4. Test plan (RED)

### Phase 2 ORM — `tests/test_p1_drop_callsite.py`
All tests use `TransactionCase` and **mock `gearment_adapter.GearmentApiAdapter.push_order`** at the import path used by `sale_order.py` (likely `multichannel_hub_fulfillment.models.sale_order.gearment_adapter.GearmentApiAdapter` — verify exact patch target by reading the existing `test_gearment_auto_push_orm.py` mock pattern before deleting it).

Setup builds:
- A product with `x_gearment_sku='TEST_SKU_001'` so P1-DROP-SEED auto-routing kicks in.
- An SO on a `gearment_pod` pipeline state `quoted` with one line of that product.
- Helper to call `so.action_confirm()` and trace the procurement → PO chain.

Tests:

1. `test_po_confirm_pushes_to_gearment_and_advances_pipeline`
   - Setup: SO confirmed → PO auto-created against `partner_gearment_vendor`.
   - Mock `push_order` returns `{'id': 'GEAR_REF_42'}`.
   - Action: `po.button_confirm()`.
   - Assert: `so.x_gearment_outbound_ref == 'GEAR_REF_42'`, `so.x_gearment_pushed_at` set, `so.x_gearment_status == 'pending'`, `so.x_pipeline_state_id.code == 'confirmed'`, `po.state == 'purchase'`.
   - Assert: `push_order` called exactly once with the SO's payload.

2. `test_po_confirm_idempotent_when_so_already_pushed`
   - Setup: same as above but pre-stamp `so.x_gearment_outbound_ref = 'GEAR_REF_PRE'` before PO confirm.
   - Action: `po.button_confirm()`.
   - Assert: `push_order` was NOT called. `so.x_gearment_outbound_ref` unchanged. `po.state == 'purchase'` (PO still confirms — only the push is skipped).

3. `test_po_confirm_raises_userror_on_push_failure_and_rolls_back`
   - Setup: same as test 1.
   - Mock `push_order` raises `RuntimeError("HTTP 500")`.
   - Action: `with self.assertRaises(UserError): po.button_confirm()`.
   - Assert: `po.state == 'draft'` (rollback worked). `so.x_gearment_outbound_ref == False`. `so.x_pipeline_state_id.code == 'quoted'` (unchanged).
   - Assert: SO has a chatter row mentioning "Gearment push failed during PO" — this proves the `savepoint(flush=False)` audit pattern survived the rollback. Use `so.message_ids.filtered(lambda m: 'Gearment push failed' in (m.body or ''))`.

4. `test_dropship_picking_done_advances_pipeline_to_shipped`
   - Setup: SO+PO confirmed (test 1 path); dropship picking now exists in `assigned`/`done` state.
   - Action: validate picking via `picking._action_done()` (or use `button_validate` with `immediate_transfer` ctx).
   - Assert: `so.x_pipeline_state_id.code == 'shipped'`.

5. `test_picking_done_idempotent_when_so_already_shipped`
   - Setup: pre-stamp SO at `shipped`; second picking validate-equivalent fires `_action_done`.
   - Assert: state unchanged. No exception.

6. `test_non_gearment_dropship_po_does_not_trigger_push`
   - Setup: PO with `picking_type_id.code == 'dropship'` but `partner_id != partner_gearment_vendor` (some other dropship vendor).
   - Action: `po.button_confirm()`.
   - Assert: `push_order` not called.

7. `test_non_dropship_po_does_not_trigger_push`
   - Setup: PO with `picking_type_id.code == 'incoming'` (regular purchase) against the Gearment partner (edge: someone manually created an incoming PO).
   - Action: confirm.
   - Assert: `push_order` not called.

### Phase 1 DB — `tests/test_phase1_install.py` (extend) or new `test_p1_drop_callsite_phase1.py`

8. `test_orphan_methods_removed`
   - `self.assertFalse(hasattr(self.env['sale.order'], '_gearment_push_should_fire'))`
   - `self.assertFalse(hasattr(self.env['sale.order'], '_enqueue_gearment_push'))`
   - `self.assertFalse(hasattr(self.env['sale.order'], '_cron_retry_stalled_gearment_pushes'))`

9. `test_orphan_cron_xml_removed`
   - `self.assertFalse(self.env.ref('multichannel_hub_fulfillment.ir_cron_gearment_retry_stalled', raise_if_not_found=False))`

10. `test_purchase_order_action_confirm_overridden_by_mhf`
    - Inspect MRO: `mhf` appears in the `__module__` chain for `purchase.order.button_confirm`. Concretely:
      `self.assertIn('multichannel_hub_fulfillment', self.env['purchase.order'].button_confirm.__qualname__)` — or check the class registry's `_inherits_children` for `multichannel_hub_fulfillment.models.purchase_order.PurchaseOrder`.

11. `test_stock_picking_action_done_overridden_by_mhf`
    - Same pattern for `stock.picking._action_done`.

---

## 5. Risks + mitigations

| Risk | Mitigation |
|------|------------|
| In-flight Gearment-POD orders on staging without `x_gearment_outbound_ref` will try to push when their PO is re-confirmed | Document operator runbook in commit body and tracker. Pre-deploy: SQL-stamp them with a sentinel `'MIGRATION_SKIP'` ref OR confirm they're cleared before deploy. |
| `action_push_to_gearment` change from catch-and-log to raise breaks any callers expecting silent failure | Grep for callers: only the deleted hook, the deleted cron, and the manual button. The manual button raising `UserError` is correct UX (user gets a dialog). No other callers. |
| Test mock-target path mismatch | Read the existing `test_gearment_auto_push_orm.py` BEFORE deletion to copy the working mock pattern. |
| Picking `_action_done` super-class signature differs across Odoo versions | Lock in `def _action_done(self):` (no args in Odoo 19 CE base). Verify with `git grep '_action_done' addons/stock/models/stock_picking.py`. |
| Pipeline-state `code` mismatch — what if seed has `'pushed'` not `'confirmed'`? | Resolution 1A locks codes to `confirmed`/`shipped`. Implementation must NOT introduce new codes. If a future operator renames stage labels via UI, codes survive (per ADR-010 §5 auto-versioning). |
| `partner_gearment_vendor` ref unresolvable during fresh install (model load order) | `env.ref(..., raise_if_not_found=False)` returns falsy; override silently no-ops. Tests cover the seeded path; install ordering is verified by `-u multichannel_hub_fulfillment` exit 0. |
| Re-running the slice on staging where the old cron entry exists in the DB | XML record removal: `noupdate` was NOT set on `ir_cron_gearment_retry.xml`, so module upgrade will drop the cron via Odoo's standard data-record-removal logic (records with no module-data link survive; records linked to mhf get cleaned up on `-u`). |

---

## 6. Agent dispatch order (9-phase loop)

| Phase | Agent / Action | Inputs | Output |
|-------|----------------|--------|--------|
| 0 Dispatch | (done — this plan) | Tracker + ADR-010 + findings | TaskCreate ✓, this doc |
| 1 Plan | (done — this doc) | — | — |
| 2 RED | `tdd-guide` | This plan §4 + existing test patterns in mhf/tests/ | 7 Phase 2 + 4 Phase 1 failing tests |
| 3 GREEN | Developer (in-session) | This plan §1-3 + RED tests | All 11 tests pass |
| 4 Review | `code-reviewer` + `security-reviewer` (parallel, single message, 2 Agent calls) | Diff + `action_push_to_gearment` refactor + `savepoint(flush=False)` pattern | Block on CRITICAL/HIGH |
| 5 Verify | Bash | `-u multichannel_hub_fulfillment --stop-after-init`, `--test-tags /multichannel_hub_fulfillment`, `ruff check`, grep for `_logger.info` / `print(` | All green |
| 6 Commit | Bash | One conventional commit | sha-hash |
| 7 Document | Edit | tracker state→done, change-log entry, findings.md if new gotchas | Diff |
| 8 Learn | `/learn` | Surprises during implementation | Auto-memory entries |
| 9 Land | (deferred to W7 E2E sprint) | — | — |

---

## 7. Exit-criteria mapping

| Criterion | Artifact |
|-----------|----------|
| Every slice task `[X]` | TaskCreate IDs #1-9 all completed |
| Tests pass; coverage ≥80% on changed lines | `--test-tags /multichannel_hub_fulfillment` exit 0 + 11 new tests |
| Module installs cleanly | `-u multichannel_hub_fulfillment --stop-after-init` exit 0 |
| ACLs defined for new model | N/A — only `_inherit` of existing `purchase.order` and `stock.picking`; ACLs inherited |
| `sudo()` commented; raw SQL commented | No new sudo / raw SQL introduced; verify in code-reviewer pass |
| Tracker `state` updated; blockers documented | `.claude/plans/006-master-plan-tracking.md` P1-DROP-CALLSITE row → `done` + change-log entry 2026-05-05 |
| `/learn` insight captured | At least one auto-memory entry, or explicit "no new patterns" note in commit |
| `findings.md` updated if anything surprised | Append entry under `2026-05-05` if e.g. PO→SO walk surprises us, or note "implementation followed the plan exactly — no findings" |

---

## 8. Implementation guardrails (from playbook)

- **Surgical changes** — touch only the files in §1. Resist the urge to "fix" other Gearment code paths discovered in passing.
- **No bypass-context** in module code — only E2E scripts may use `bypass_pipeline_state_guard`.
- **No `_logger.info` for debug** — `_logger.warning` for the failed-push path; `_logger.debug` for "skipping non-Gearment PO" if useful at all.
- **Single commit** — Resolution 3B ties cleanup to relocation. Do not split into "remove orphans" + "add new code" commits; that creates a window where the surface is broken.
- **Migration runbook in commit body** — explicit instruction for the operator about in-flight Gearment-POD orders on staging.

---

## 9. Manifest version log

- mhf: 19.0.1.0.11 → 19.0.1.0.12 (this slice)
