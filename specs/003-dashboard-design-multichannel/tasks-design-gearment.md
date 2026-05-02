# Tasks — P1-DESIGN+GEARMENT

**Slice:** P1-DESIGN+GEARMENT (merged P1-DESIGN-PROOF + P4-01a)
**Date:** 2026-05-02
**Branch:** feature/006-master-plan-coding
**ETA:** ~400 LOC + 20 tests
**Closes:** Bug-2026-05-02-gearment-pod-design-flow-missing (spec_gap, MAJOR)

References: D2_production_flow.md §2.1 rows 3+5 + §3.2; findings.md Bug-2026-05-02 block; memory #64.

---

## Phase 2 — RED

- [X] **T-DG-01** `mhc/tests/test_design_proof_state_db.py` — DB schema (5 tests): proof_sent in Selection, proof_sent_at + proof_sent_by columns, sale.order x_gearment_outbound_ref/x_gearment_pushed_at/x_gearment_status fields, x_gearment_sku on product_template.
- [X] **T-DG-02** `mhc/tests/test_design_proof_workflow.py` — ORM (7 tests): pending→proof_sent, rejected→proof_sent (re-proof), BA-only on send_proof, XSS escape on buyer_message, MP-only approve, invalid-transition raises, kanban button visibility logic.
- [X] **T-DG-03** `mhc/tests/test_dashboard_buttons.py` — ORM (3 tests): action_dashboard_send_proof fans out, action_dashboard_approve_designs fans out, RPC gate blocks non-BA.
- [X] **T-DG-04** `mhf/tests/test_gearment_auto_push.py` — ORM (7 tests): push on confirm, idempotent on retry, failure→rollback to quoted, payload includes approved+proof_sent files, payload sanitization, cron retry finds stalled, savepoint fallback when queue_job absent.

## Phase 3 — GREEN

### multichannel_hub_core
- [X] **T-DG-05** `models/design_file.py`: add `proof_sent` to state Selection between pending+approved; readonly `proof_sent_at` + `proof_sent_by` fields; `action_send_proof_to_buyer(buyer_message=None)` method (BA-gate, Markup+escape chatter, state guard).
- [X] **T-DG-06** `models/design_file.py`: tighten `action_approve` + `action_reject` to group_production_team only (add `_check_production_or_raise`).
- [X] **T-DG-07** `models/design_file.py`: `@api.constrains('state')` enforces transitions {pending→proof_sent|rejected, proof_sent→approved|rejected, rejected→pending|proof_sent}.
- [X] **T-DG-08** `models/sale_order.py`: `action_dashboard_send_proof()` + `action_dashboard_approve_designs()` (fan out across order_line.design_file_ids; FR-017 gates).
- [X] **T-DG-09** `views/order_dashboard_views.xml`: kanban variant with two inline buttons + 4-bucket search filter (Chờ File / Chờ Duyệt / Đã Gửi Proof / Sẵn sàng sản xuất).

### multichannel_hub_fulfillment
- [X] **T-DG-10** `models/product_template.py` (NEW): `_inherit='product.template'` + `x_gearment_sku` Char (indexed, tracking, nullable).
- [X] **T-DG-11** `models/sale_order.py` (NEW): `_inherit='sale.order'` + 3 fields (`x_gearment_outbound_ref` Char readonly, `x_gearment_pushed_at` Datetime readonly, `x_gearment_status` Selection 5-state tracking).
- [X] **T-DG-12** `models/sale_order.py`: override `_write_pipeline_state()` — when transitioning to gearment_pod/confirmed AND outbound_ref empty AND ICP enabled → enqueue `_deferred_push_to_gearment` (queue_job if available, else savepoint).
- [X] **T-DG-13** `models/sale_order.py`: `_deferred_push_to_gearment()` builds payload + calls `gearment_adapter.push_order`; success→stamp ref + status='pending'; failure→rollback pipeline to quoted + chatter alert + status='failed'.
- [X] **T-DG-14** `services/gearment_payload_builder.py` (NEW): pure `build_payload(order)` returning `GearmentOrderPayload` (uses approved + proof_sent design files; Markup-safe buyer_note).
- [X] **T-DG-15** `data/ir_cron_gearment_retry.xml` (NEW): cron `_cron_retry_stalled_gearment_pushes` 1h interval; finds gearment_pod/confirmed/no-ref/>24h → re-enqueue.
- [X] **T-DG-16** `data/icp_gearment_auto_push.xml` (NEW): set `multichannel_hub_fulfillment.gearment_auto_push_enabled` Boolean default True (kill-switch).

### Security
- [X] **T-DG-17** `mhc/security/ir.model.access.csv`: design.file group_ba_shipping (R/W/C, no U) row.
- [X] **T-DG-18** `mhf/security/ir.model.access.csv`: product.template ACL with x_gearment_sku via system/manager write only (mostly inherited).

### Manifest
- [X] **T-DG-19** `mhc/__manifest__.py` bump 19.0.1.0.8 → 19.0.1.0.9; register new XML if added.
- [X] **T-DG-20** `mhf/__manifest__.py` bump 19.0.1.0.5 → 19.0.1.0.6; register cron + ICP data files; update models/__init__.py.

## Phase 4 — Review (parallel: code-reviewer + security-reviewer)
## Phase 5 — Verify (install + test-tags + ruff + log scan)
## Phase 6 — Commit (single conventional commit)
## Phase 7 — Document (mark T-DG-* [X], tracker → done, findings.md update)
## Phase 8 — Learn (memory entry capture)
