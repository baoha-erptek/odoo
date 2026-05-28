# P1-02b Tactical Implementation Plan: Design-File Routing

**Slice**: P1-02b — Spec 003 US5 routing
**Tasks covered**: T066, T068, T073, T074, T075
**Depends on**: P1-02a (done — `design.file` model + URL-mode + 3-state kanban + 10MB cap + historical seed shipped)
**Generated**: 2026-04-29 (planner agent, Phase 1 of 9-phase loop)
**Branch**: `feature/006-master-plan-coding`
**Module**: `multichannel_hub_core` (mhc)

This file is the Phase 1 deliverable. Phase 2 (RED) reads it as input. Stale once P1-02b lands — superseded by tracker `done` + commit body.

---

## Overview

P1-02b layers the file-delivery mechanism on top of P1-02a's `design.file` model. Adds the route-dispatch pattern, queued-job orchestration, and stuck-route detection per ADR-009 §4 and ADR-012. Scope: manual delivery methods only (`gdrive_share`, `discord_manual`); Gearment API defers to P4-01. Five tasks (T066, T068, T073, T074, T075) delivering the route model, router service, stuck-route badge, design-status route-awareness, and on-confirm auto-route.

---

## File List (Create/Modify)

| File Path | Type | Reason |
|-----------|------|--------|
| `custom_addons/multichannel_hub_core/models/design_file_route.py` | NEW | T066 — `design.file.route` model with `idempotency_key` UNIQUE |
| `custom_addons/multichannel_hub_core/models/__init__.py` | MODIFY | Register `design_file_route` import |
| `custom_addons/multichannel_hub_core/services/design_file_router.py` | NEW | T068 — queued-job dispatcher (5 retries, exponential backoff) |
| `custom_addons/multichannel_hub_core/services/__init__.py` | MODIFY | Register `design_file_router` import if needed |
| `custom_addons/multichannel_hub_core/models/sale_order.py` | MODIFY | T073 — `stuck_route_badge` computed field; T075 — `action_confirm()` hook |
| `custom_addons/multichannel_hub_core/models/sale_order_line.py` | MODIFY | T074 — update `_compute_design_status` to be route-state aware |
| `custom_addons/multichannel_hub_core/security/ir.model.access.csv` | MODIFY | ACL rows for `design.file.route` |
| `custom_addons/multichannel_hub_core/security/record_rules.xml` | MODIFY | Record rules for route visibility (optional, depends on granularity) |
| `custom_addons/multichannel_hub_core/migrations/19.0.1.0.5/__init__.py` | NEW (maybe) | Empty migration init if schema-snapshot needed for idempotency rollout |
| `custom_addons/multichannel_hub_core/tests/test_design_file_lifecycle_p1_02b.py` | NEW | Phase 1 + Phase 2 tests for routing |

**Cross-module touches**: None. P1-02b is isolated within `multichannel_hub_core`. P1-02c (GDrive upload wizard) and P4-01 (Gearment API) are separate slices.

---

## Agent Dispatch Order (Remaining Phases)

### Phase 2: RED Tests — `tdd-guide` agent

Write failing tests **first**. Two-phase structure in `tests/test_design_file_lifecycle_p1_02b.py`:

**Phase 1 DB tests** (`TestPhase1DB`):
- `test_idempotency_key_unique_constraint_exists` — assert UNIQUE constraint on `idempotency_key` (SHA-256 hash of route identity tuple)
- `test_route_table_columns_exist` — verify all fields from `data-model.md` §7 present and typed correctly
- `test_foreign_key_design_file_cascade` — verify FK `design_file_id` has `ondelete='cascade'`

**Phase 2 ORM tests** (`TestPhase2ORM`):
- `test_route_auto_create_on_file_approve_internal_production` — `design.file.state='pending'→'approved'` triggers auto-create of 3 routes (`mp`, `ba`, `pd`) for internal-production orders
- `test_route_state_machine_pending_to_sent_to_acknowledged` — transitions via `action_dispatch()` (mocked GDrive success), `action_acknowledge()` (manual UI button)
- `test_route_idempotency_key_dedup` — re-calling `dispatch` with same idempotency_key is no-op (no duplicate enqueue)
- `test_stuck_route_badge_computation_after_2h` — `order.stuck_route_badge` reads `route_ids` with `state IN ('pending','failed') AND create_date < now()-2h`, returns True
- `test_design_status_route_aware_approved_pending_route` — `design_status` reads approved file with pending/failed routes as `'approved-pending-route'`
- `test_action_confirm_enqueues_routing_job` — on `sale.order.action_confirm()`, `design_file_router.dispatch` is called for all approved files
- `test_delivery_method_constraints_gdrive_vs_discord` — C-DR-004: `delivery_method='gdrive_share'` requires `recipient_user_id` OR `recipient_partner_id`
- `test_route_failure_reason_required_when_failed` — C-DR-003

**Minimum DB assertions**:
- `idempotency_key` UNIQUE exists (idempotent `pg_constraint` check)
- `(design_file_id, recipient_*_id, delivery_method)` index for hot-path lookups exists

### Phase 3: GREEN Implementation — order T066 → T068 → T073 → T074 → T075

1. **T066** — `design_file_route.py` model
   - Fields per `data-model.md` §7
   - Constraints C-DR-001, C-DR-002, C-DR-003, C-DR-004
   - `idempotency_key` computed as SHA-256 hash, stored, indexed, UNIQUE (`_sql_constraints` + `init()` raw SQL belt-and-braces per `_sql_constraints` drift memory; use `pg_constraint IF NOT EXISTS` pre-check, NOT EXCEPTION clause)
   - `mail.thread` inheritance (audit trail on state changes)
   - `_order = 'create_date DESC'`

2. **T068** — `design_file_router.py` service
   - Class `DesignFileRouter`
   - Method:
     ```python
     def dispatch(self, design_file_id: int, recipient_types: list[str] | None = None) -> dict:
         """Queued-job wrapper for design.file.route dispatch.

         Returns {'queued': int, 'deduped': int}
         """
     ```
   - Retry: 5 attempts, exponential backoff (1m, 5m, 15m, 1h, 4h capped)
   - Per route: idempotency_key dedup before enqueue
   - Failure: `route.state='failed'`, `route.failure_reason` set (per ADR-012 §3 no auto-fallback; manual Discord only)
   - Logging: DEBUG on start/success, WARNING on retry, ERROR on final failure (NEVER `_logger.info`)
   - Entry: `design.file.route.action_dispatch()` (mocked in P1-02b tests; actual GDrive client defers to P1-02c)

3. **T073** — `sale.order` extension: stuck-route badge
   - New computed field `stuck_route_badge` (Boolean, `store=False`)
   - `@api.depends('design_file_ids.route_ids.state', 'design_file_ids.route_ids.create_date')`
   - Logic: `any(route.state IN ('pending','failed') AND route.create_date < now()-2h for route in self.design_file_ids.route_ids)`
   - Used on Order Dashboard as conditional badge decoration

4. **T074** — `sale.order.line` extension: route-aware design_status
   - Modify existing `_compute_design_status` from T023 (P1-02a)
   - Current: rollup of `design_file.state` only
   - New: rollup of `design_file.state` AND `design_file.route_ids.state`
   - If file is `approved` but all its routes are `pending`/`failed` → return `'approved-pending-route'`
   - Update Selection: `none`, `pending`, `approved`, `rejected`, `approved-pending-route`

5. **T075** — `sale.order.action_confirm()` hook: on-confirm routing
   - Extend or wrap via `_after_confirm_routing()` helper
   - For each `design.file` on the order with `state='approved'`: call `self.env['design.file.router'].dispatch(design_file.id)`
   - Catch exceptions: log WARNING, do NOT block confirm (routing async)
   - If routes exist with `state IN ('pending','failed')`, post chatter: "Design routing in progress — monitor stuck-route badge"

### Phase 4: Review — `code-reviewer` + `security-reviewer` (parallel)

**code-reviewer focuses on**:
- `design_file_router.py`: idempotency-key dedup, retry, error handling
- Constraint implementations: logic correctness, error messages
- Computes (`stuck_route_badge`, `design_status`): no N+1, depends correctness
- No mutation of input recordsets

**security-reviewer focuses on**:
- ACL on `design.file.route`: production_team write, read per visibility rules
- `action_dispatch` RPC gate: must check `has_group(group_production_team OR base.group_system)`
- Raw SQL in `init()`: `pg_constraint` idempotency check is correct
- No secrets in code (GDrive auth defers to P1-02c)
- Sudo: none required for P1-02b (P1-02c GDrive client may need sudo)

---

## Risks & Mitigations

| Risk | P | Impact | Mitigation |
|------|---|--------|------------|
| Concurrent route enqueue (two users confirm orders sharing a `design.file`) | M | M | Idempotency-key dedup + queue-job's own dedup. Test: `test_route_idempotency_key_dedup`. |
| Stuck-route badge O(N) on dashboard render (17K orders × 200 routes each) | H | H | `store=False` (computed-on-read, Odoo cache); index on `(design_file_id, state, create_date)` from migration. Re-evaluate in W7 E2E if perf regresses; gate via `search_read` if needed. |
| Design-status compute path explosion (3 sources: file.state, route.state, route.create_date) | M | M | Phase 2 test pins logic before impl. Compute order matters; document. |
| Route-aware status cascades to order level (future P1-03 may need order-level status) | L | H | Document dependency in code comments; flag tech-debt if needed. |
| Idempotency-key hash collision | VL | H | SHA-256 — collision risk negligible at 50k routes. Add deterministic test `test_idempotency_key_does_not_collide`. |
| GDrive upload wizard (P1-02c) slip leaves routes in `pending` forever | M | M | Not on critical path for P1-02b landing. Routes default `state='pending'`; wizard `action_dispatch` on file upload. Order-confirm just enqueues. |

---

## Exit Criteria Checklist

**5 task `[X]` markers**:
- [ ] T066 — `design.file.route` model exists; `idempotency_key` UNIQUE mirrored in `_sql_constraints` + `init()` raw SQL
- [ ] T068 — `services/design_file_router.py` implemented; 5-retry backoff; `dispatch()` returns `{'queued', 'deduped'}`
- [ ] T073 — `sale.order.stuck_route_badge` Boolean compute with correct logic (pending/failed + >2h)
- [ ] T074 — `sale.order.line._compute_design_status` updated; Selection includes `'approved-pending-route'`
- [ ] T075 — `sale.order.action_confirm()` hooks routing; on-confirm chatter if routes exist

**7 machine-checkable**:
1. Module installs cleanly — `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` exit 0
2. Phase 1 DB tests pass — `--test-tags /multichannel_hub_core/test_design_file_lifecycle_p1_02b::TestPhase1DB`
3. Phase 2 ORM tests pass (≥80% coverage on changed lines) — `--test-tags ::TestPhase2ORM`
4. ACL defined — `security/ir.model.access.csv` has `design.file.route` rows (production_team, system)
5. No `_logger.info(` / `print(` in new code — grep sweep
6. Idempotency-key UNIQUE at DB — both `_sql_constraints` AND `init()` `pg_constraint` check
7. Stuck-route badge index — reuse `design_file_order_line_id_state_idx` from P1-02a; add `(design_file_id, create_date)` if needed

---

## Mode 2 Parallelism Candidate?

**Question**: Pair P1-02b with P0-18b (Gearment webhook in `multichannel_hub_fulfillment`)?

**Assessment**: **NO, not without risk.**

- Shared dependency: both touch `design.file` indirectly (Gearment webhook may cascade to route acknowledgment)
- P0-18b file overlap: unknown until module exists
- Sequencing: P1-02b is pure mechanics; P0-18b is external integration. Land P1-02b first, then assess P0-18b's actual file touches.
- **Verdict**: sequential. Re-evaluate Mode 2 after P1-02b lands.

---

## Summary

| Phase | Agent | Input | Output | Files | LOC |
|-------|-------|-------|--------|-------|-----|
| RED | tdd-guide | Tasks 066–075 | 8+ failing tests | `test_design_file_lifecycle_p1_02b.py` | ~400 |
| GREEN | tdd-guide | Test specs | Model + service + extends passing | 5 new/modified | ~800 |
| Review | code-reviewer + security-reviewer (parallel) | Green code | CRITICAL/HIGH fixed | — | — |
| Verify | manual | Module update + tests | Exit criteria green | — | — |
| Commit | manual | Verified code | 1–2 conventional commits | — | — |
| Document | manual | Code + findings | tasks.md `[X]`, tracker, MASTER_PLAN snapshot | — | — |

P1-02b is **surgical** — routing layer only. P1-02c (GDrive upload + wizard) and P4-01 (Gearment API) are separate slices. Idempotency-key + queue-job are decoupled from delivery method, so adding `gearment_api` later is a 1-line Selection enum addition.
