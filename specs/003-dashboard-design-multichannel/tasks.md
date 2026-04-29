---
description: "Tasks for Spec 003 — Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation"
---

# Tasks: Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation

**Branch**: `003-dashboard-design-multichannel` | **Date**: 2026-04-27 (Stage 4.3 regen)
**Module**: `multichannel_hub_core` (per ADR-003 Phase 1 + ADR-001 §11)
**Input**: spec.md (Wave B 2026-04-13), plan.md (Stage 4.1 refresh), data-model.md (Stage 4.1 refresh), research.md, quickstart.md
**Tests**: REQUIRED per project's two-phase testing rule (Phase 1 DB + Phase 2 ORM unit, 80%+ coverage)
**Supersedes**: the prior frozen tasks.md (single-dashboard design, archived in git history at commit `f0a5be9`)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: User story label (US1–US7) for user-story-phase tasks; absent for Setup/Foundational/Polish phases

---

## Phase 1: Setup

- [ ] T001 Create new Odoo module skeleton at `custom_addons/multichannel_hub_core/` with `__manifest__.py` (version `19.0.1.0.0`, depends `['sale_management', 'stock', 'contacts', 'mail']`)
- [ ] T002 [P] Create top-level package `__init__.py` files in `multichannel_hub_core/{models,services,views,data,security,i18n,tests,migrations}`
- [ ] T003 Create `custom_addons/multichannel_hub_core/security/multichannel_hub_security.xml` declaring groups `group_production_team`, `group_pipeline_admin`, `group_ba_user`, `group_ba_lead`, `group_marketing_user`, `group_audit_reader`
- [ ] T004 [P] Create `custom_addons/multichannel_hub_core/data/ir_config_parameter.xml` with `multichannel_hub.large_file_threshold_bytes=10485760` and `multichannel_hub.default_pipeline_code=vn_internal_production`
- [ ] T005 [P] Add ruff config exception (or extend project `ruff.toml`) to cover `custom_addons/multichannel_hub_core/`

---

## Phase 2: Foundational (blocking prerequisites for all user stories)

- [ ] T006 [P] Implement `shipping.carrier` model in `models/shipping_carrier.py` (per data-model.md §4) with `code` UNIQUE constraint, `mail.thread` inheritance, `tracking=True` on user-visible fields
- [ ] T007 [P] Implement `pipeline.team` model in `models/pipeline_team.py` (per data-model.md §11) with `name` UNIQUE
- [ ] T008 Implement `order.pipeline` model in `models/order_pipeline.py` (per data-model.md §9) with auto-version-on-edit logic (`clone_for_edit`, `is_in_use`); `(code, version)` UNIQUE
- [ ] T009 Implement `order.pipeline.state` model in `models/order_pipeline_state.py` (per data-model.md §10) with `(pipeline_id, code)` UNIQUE; one-initial / at-least-one-terminal constraints; `next_stage_ids` Many2many self-relation
- [ ] T010 Implement `order.pipeline.transition.log` model in `models/order_pipeline_transition_log.py` (per data-model.md §12) — append-only audit table with `change_type` enum
- [ ] T011 Implement `sale.order.fulfillment` delegation sibling in `models/sale_order_fulfillment.py` (per data-model.md §2 + ADR-007) with `_inherits = {'sale.order': 'order_id'}`; auto-create on `sale.order.create`
- [ ] T012 [P] Add ACL entries to `security/ir.model.access.csv` for all foundational models (carrier, pipeline*, transition_log, fulfillment, team)
- [ ] T013 [P] Add record rules to `security/record_rules.xml` for pipeline-admin gating + production-team-edit-fulfillment
- [ ] T014 [P] Implement `services/pipeline_resolver.py` with `resolve(order_lines)` function per data-model.md §13 + ADR-010 §2 (product → category → system param fallback)
- [ ] T015 Create `data/order_pipeline_seed.xml` with 3 pipelines: `vn_internal_production` (17 stages per research.md R2), `gearment_pod` (4 stages), `multi_technique_hybrid` (3 stages — template)
- [ ] T016 [P] Create `data/shipping_carrier_seed.xml` with 7 carriers per data-model.md §4 (USPS, UniUni, YunExpress, 4PX, DHL eCommerce, FedEx SmartPost, GKE Local)
- [ ] T017 [P] Create `data/pipeline_team_seed.xml` with 4 teams: `team_vn_production_line_1`, `team_ba_approval`, `team_mp_marketing`, `team_gearment_liaison`
- [ ] T018 Implement `migrations/19.0.1.0.0_post.py` to insert ADR-003 Phase 1 module-move records and run `sales_channel='etsy'`/`channel_order_ref=etsy_order_id` backfill (FR-024/FR-025)
- [ ] T019 [P] Phase-1 (DB) test fixture in `tests/__init__.py` — common setUpClass loading seed pipelines + a sample sale.order
- [ ] T020 [P] Add `tests/test_seeds.py` verifying seed pipeline counts (1 vn pipeline with 17 states; 1 gearment with 4; 1 hybrid with 3) and carrier seed (7 rows with valid `etsy_carrier_name`)

---

## Phase 3: US1 — Order Dashboard for BA daily triage (P1)

**Goal**: BA sees commercial-state list view with thumbnails, decorations, inline edit, audit trail.
**Independent test**: 17K rows render <3s; decorations + inline edit + chatter audit verified.

- [~] T021 [P] [US1] Extend `sale.order` in `models/sale_order.py` adding `sales_channel`, `channel_order_ref`, `x_pipeline_id`, `x_pipeline_state_id`, `has_pending_address_change` (computed, store=True per research.md R5) per data-model.md §1 — **landed in P1-04 + P1-01a**: `has_pending_address_change` (P1-04), `sales_channel` + `channel_order_ref` + idempotent backfill (P1-01a). `x_pipeline_id` / `x_pipeline_state_id` defer to P1-08 (after order.pipeline lands).
- [~] T022 [US1] Add `sale.order` `@api.constrains` C-SO-001 (address-change lock) and C-SO-002 (pipeline policy) per data-model.md §1 — **partial**: C-SO-001 in P1-04; C-SO-002 (pipeline policy) defers to P1-08.
- [X] T023 [P] [US1] Extend `sale.order.line` in `models/sale_order_line.py` with rolled-up `design_status` (computed, store=True; lowest-of-children from `design_file_ids.state`) per data-model.md §3 — **landed in P1-02a (2026-04-29)** in `multichannel_hub_core/models/sale_order_line.py`.
- [X] T024 [US1] Create `views/order_dashboard_views.xml` with `ir.actions.act_window` "Order Dashboard" + `ir.ui.view` (list) — 14 columns per spec.md FR-001 — **landed in P1-01a** with 10 cols (image, channel, date, buyer, country, amount, MP note, PIC, priority, tracking_state, overdue marker). 14-col version deferred (image, design_status, has_pending_address_change column require P1-02 + cross-module fix).
- [X] T025 [US1] Add row decorations to the Order Dashboard list view: `decoration-info` (qty≥2), `decoration-bf` (duplicate buyer 7-day window), `decoration-danger` (priority=push), `decoration-warning` (sales_channel=amazon) — **landed in P1-01a**.
- [X] T026 [US1] Implement compute method `_compute_is_duplicate_buyer` on `sale.order` (7-day window on partner_id + shipping address hash, excludes legitimate repeat customers per spec.md edge cases) — **landed in P1-01a**. Note: direction-only @api.depends; daily cron sweeps the trailing 7-day window for retroactive recompute (avoids O(N²) on bulk migrations).
- [X] T027 [P] [US1] Add overdue-approval marker computed field on `sale.order` (excludes final-state orders + non-etsy channels per FR-009 + spec.md edge cases) — **landed in P1-01a**. Daily cron picks up calendar-only transitions.
- [X] T028 [P] [US1] Add ACL entries for inline-edit fields (MP note, PIC, priority) — Marketing group write-allowed; BA group write-allowed — **landed in P1-01a**: P1-05's `sale.order.fulfillment` ACL already grants write to `sales_team.group_sale_salesman` for these fields; P1-01a added `tracking=True` to mp_note + pd_note (P1-05 oversight).
- [X] T029 [US1] Add menu entry `Operations → Order Dashboard` in `views/menu.xml` — **landed in P1-01a** (lives in mhc).
- [~] T030 [P] [US1] Phase-2 test `tests/test_order_dashboard.py`: render-perf assertion (≤3s for 17K rows fixture), decoration logic per row type, inline-edit chatter audit — **partial in P1-01a**: decoration logic + compute-correctness + delegation-reach tests. 17K-row perf assertion deferred to E2E sprint. Chatter-audit assertion replaced with delegation-reach assertion (mail.thread tracking semantics in TransactionCase are unreliable for the @api.depends path).
- [X] T031 [US1] Phase-1 DB test in `tests/test_dashboards_db.py` verifying composite index `(sales_channel, has_pending_address_change)` exists post-install — **landed in P1-01a**.

---

## Phase 4: US2 — Tracking Dashboard for shipping ops (P1)

**Goal**: Dedicated tracking view with bulk actions, search, GKE export.
**Independent test**: 13 columns; tracking search; bulk mark-shipped excludes pending-address rows; export round-trips.

- [X] T032 [P] [US2] Add fields to `sale.order.fulfillment` per data-model.md §2 — **landed in P1-03**: `tracking_number/shipping_carrier_id/shipping_date/label_status/tracking_state/mp_note/pd_note/pic_user_id/order_priority/production_blocked/block_reason` already on disk from P1-05/P1-06; P1-03 adds `pd_pic_user_id`, `warehouse_zone`, `order_id` back-ref (mhc) and `etsy_ship_notified_at` (etsy_integration `_inherit` extension, `groups='base.group_system'` per security review).
- [X] T033 [US2] Add C-SOF-001 constraint (block_reason required when production_blocked) per data-model.md §2 — already landed in P1-05 (`_check_block_reason_when_blocked`); P1-03 added regression-guard test.
- [X] T034 [P] [US2] Create `views/tracking_dashboard_views.xml` with list view + 13 columns per spec.md US2 acceptance — **landed in P1-03** (list + search + 5 group-by filters; flat group-by per Odoo 19 RNG).
- [X] T035 [US2] Implement bulk action "Mark Shipped" via `model.action_bulk_mark_shipped` — **landed in P1-03**. Silent-skip + sticky warning notification (FR-017). RPC `has_group(group_production_team OR base.group_system)` gate at method entry; write-level `_ADDRESS_LOCK_FIELDS` defense-in-depth blocks direct-RPC bypass (security-review CRITICAL fix).
- [~] T036 [US2] Implement Excel export action with column order matching GKE import format (FR-006 round-trip) — **deferred to P2-01** (Spec 004a US1 owns canonical GKE schema fingerprint; designing export here risks divergence — owner-acked deferral 2026-04-29).
- [X] T037 [P] [US2] Add bus.bus push hook on `sale.order.fulfillment.write` — **landed in P1-03**: channel `multichannel_hub.fulfillment_update`, gate set `{tracking_number, tracking_state, label_status, shipping_date, production_blocked, block_reason}`, emit on write+create, web-client subscription deferred.
- [X] T038 [P] [US2] Phase-2 test `tests/test_tracking_dashboard.py`: bulk action exclusion + search-by-tracking_number + warehouse_zone filter + bus.bus emit gate + RPC gate + write-level FR-017 — **landed in P1-03**. Export round-trip test deferred with T036.
- [X] T039 [US2] Add menu entry `Operations → Tracking Dashboard` — **landed in P1-03**.

---

## Phase 5: US3 — Process Dashboard for Production VN+US (P1, configurable pipeline)

**Goal**: PD's 18 columns, pipeline-state column with colour chips, warehouse-zone filter.
**Independent test**: Stage transition writes `order.pipeline.transition.log`; Vietnamese diacritics preserved; transition policy enforced.

- [ ] T040 [P] [US3] Implement `_write_pipeline_state` helper on `sale.order` enforcing `transition_policy` per data-model.md §1 C-SO-002 (dag_strict, dag_with_admin_override, free_form)
- [ ] T041 [US3] Hook the pipeline-state write to emit `order.pipeline.transition.log` row with `change_type='order_transition'`, `from_state_id`, `to_state_id`, `actor_user_id` per ADR-010 §1
- [ ] T042 [P] [US3] Create `views/process_dashboard_views.xml` with list view + 18 columns per spec.md US3 acceptance (order_date, shop, image, product_name, variant_attrs, qty, personalisation, pd_note, design_status, x_pipeline_state_id (chip with color), production_blocked, block_reason, pd_pic_user_id, priority, decorations, warehouse_zone)
- [ ] T043 [US3] Render pipeline-state column with `widget="badge"` and `decoration-*` reading the state's `color` field
- [ ] T044 [P] [US3] Add admin-confirmation popup for non-DAG transitions when `transition_policy='dag_with_admin_override'`
- [ ] T045 [P] [US3] Add Process Dashboard filters: `warehouse_zone='vn'/'us'`, group-by team, group-by stage
- [ ] T046 [P] [US3] Add inline edit on Process Dashboard: x_pipeline_state_id, pd_note, production_blocked, block_reason, pd_pic_user_id (subject to ACL)
- [ ] T047 [P] [US3] Phase-2 test `tests/test_order_pipeline.py`: pipeline auto-version-on-first-use-edit (REQ-PIP-07), DAG transition validation, transition log write atomicity, snapshot on entry per ADR-010 §6
- [ ] T048 [US3] Phase-1 DB test verifying `(order_id, actor_at DESC)` composite index on `order_pipeline_transition_log` per data-model.md §12
- [ ] T049 [US3] Add menu entry `Operations → Process Dashboard`
- [ ] T050 [P] [US3] Add `data/order_pipeline_views_seed.xml` configuring kanban view of `order.pipeline` for admin pipeline editing

---

## Phase 6: US4 — Address-Change Approval Workflow (P1, safety-critical)

**Goal**: MP cannot edit destination directly; BA approves; bulk actions skip pending; ORM enforcement.
**Independent test**: Request → activity to BA → approve atomic → label-buy blocked while pending.

- [X] T051 [US4] Implement `etsy.address.change.request` model in `models/etsy_address_change_request.py` per data-model.md §5 with `mail.thread` + `mail.activity.mixin` inheritance
- [X] T052 [US4] Implement constraints C-AC-001 (no requests on shipped/done/cancel orders), C-AC-002 (one outstanding per order), C-AC-003 (rejection_reason required when state=rejected)
- [X] T053 [US4] Implement `action_approve` method (atomic: writes new_values to `sale.order` with `context={'approve_address_change': True}`, sets state=approved, closes activity, posts chatter delta)
- [X] T054 [US4] Implement `action_reject` method (requires rejection_reason, posts chatter @mention to requester)
- [X] T055 [US4] Add auto-activity on create: `mail.activity.create` to `group_ba_lead` with summary "Approve address change for order <ref>", deadline +24h
- [X] T056 [P] [US4] Update `sale.order` C-SO-001 to recognise `context.get('approve_address_change')` bypass (data-model.md §1) — partial-write disabled when has_pending_address_change=True (P1-04: folded into T022 — same constraint, with bypass-context detection)
- [X] T057 [P] [US4] Create `views/etsy_address_change_request_views.xml` with form, list, and Activity inbox visibility
- [X] T058 [US4] Add ACL: create allowed for marketing+ba; write (state) restricted to ba_lead; delete restricted to system
- [X] T059 [P] [US4] Modify `sale.order` form view to render destination fields readonly when has_pending_address_change=True with banner instructing user to file request — **partial in P1-04**: banner + `partner_shipping_id` readonly attrs landed; full destination-field set lands when P1-01 wires the dashboard's expanded shipping-fields layout.
- [~] T060 [US4] Add "Request address change" button on `sale.order` form (visible only to MP when no pending request) — **deferred to P1-01**: requires the wizard/quick-create UX co-designed with the Order Dashboard.
- [~] T061 [P] [US4] Modify Tracking Dashboard's bulk-shipped action (T035) to surface address-change skip warning explicitly (FR-017) — **deferred to P1-03** (Tracking Dashboard slice owns T035).
- [X] T062 [P] [US4] Phase-2 test `tests/test_address_change_workflow.py`: full lifecycle (request→approve, request→reject, server-side write blocked, bulk-action exclusion, atomic apply) — bulk-action exclusion test deferred to P1-03 caller integration.

---

## Phase 7: US5 — Design Files + 3-State Approval (P1, ADR-009 lifecycle)

**Goal**: Immutable file history, route delivery via queued jobs, A4 bulk-print wizard.
**Independent test**: 10 MB cap; rejected→re-upload creates new row with parent_file_id; PDF cache 24h; route stuck-badge after 2h.

- [X] T063 [US5] Implement `design.file` model in `models/design_file.py` per data-model.md §6 with mail.thread + mail.activity.mixin — **landed in P1-02a (2026-04-29)** in `multichannel_hub_core/models/design_file.py`.
- [~] T064 [US5] Implement constraints C-DF-001 through C-DF-005 (single-of order_id/order_line_id; storage_mode=small ⇒ size ≤ threshold; storage_mode=url ⇒ file_url non-empty; immutable history; re-upload pattern) — **partial in P1-02a**: C-DF-001 (`_check_xor_order_link`), C-DF-002 (`_check_storage_mode_small_size_cap`), C-DF-003 (`_check_storage_mode_url_requires_file_url`), C-DF-004 (immutable-history via ACL `perm_unlink=0` for production_team) all in. Re-upload pattern (C-DF-005) deferred to P1-02b (parent_file_id chain wizard / re-upload action).
- [X] T065 [US5] Override `ir.attachment.create` to enforce 10 MB ceiling on attachments linked to `design.file`/`sale.order`/`tracking.import.line` (FR-019) — **landed in P1-02a (2026-04-29)** via `multichannel_hub_core/models/ir_attachment.py` `@api.model_create_multi` override gated by `_RESTRICTED_RES_MODELS`; threshold configurable via `multichannel_hub.large_file_threshold_bytes` ICP.
- [ ] T066 [P] [US5] Implement `design.file.route` model in `models/design_file_route.py` per data-model.md §7 with `idempotency_key` UNIQUE
- [ ] T067 [P] [US5] Implement `design.print.batch` wizard in `models/design_print_batch.py` per data-model.md §8 with C-DB-001 (only approved files allowed)
- [ ] T068 [P] [US5] Implement `services/design_file_router.py` with queued-job dispatcher (5 retries with exponential backoff per ADR-009 §4 + ADR-012)
- [ ] T069 [US5] Implement A4 layout PDF generator (services or wizard helper); cache as `ir.attachment` with TTL 24h
- [ ] T070 [P] [US5] Implement cron `cron_design_print_batch_expire` flipping cached_pdf to expired after 24h
- [X] T071 [P] [US5] Create `views/design_file_views.xml` (form, list, kanban with 3 columns Chờ duyệt/Duyệt/Cần chỉnh lại); production-team-only ACL on drag-drop — **landed in P1-02a (2026-04-29)** in `multichannel_hub_core/views/design_file_views.xml`. RPC-level `has_group(group_production_team)` gate in `write()` defends drag-drop beyond view-level `groups=` (which is bypassable via XML-RPC).
- [ ] T072 [P] [US5] Create `views/design_print_batch_wizard.xml` (TransientModel wizard form)
- [ ] T073 [US5] Add stuck-route badge computation on `sale.order` reading `design.file.route.state` ∈ {pending, failed} AND create_date < now()-2h
- [ ] T074 [US5] Modify `sale.order.line._compute_design_status` (T023) to be route-state aware ("approved-pending-route" gradient per plan.md §Stage-2 ADR deltas)
- [ ] T075 [US5] Implement REQ-AUT-02 — on `sale.order.action_confirm()`, route file design via `design.file.router.dispatch` per ADR-009 §4
- [~] T076 [P] [US5] Phase-2 test `tests/test_design_file_lifecycle.py`: storage-mode enforcement, immutable history (parent_file_id chain), route state machine, idempotency_key dedup, stuck-route badge — **partial in P1-02a (2026-04-29)**: storage-mode enforcement + ACL kanban + mail-thread + design_status rollup + 10 MB cap boundary + T078 seed all in. Immutable history full chain test, route state machine, idempotency_key dedup, stuck-route badge all deferred to P1-02b (require `design.file.route` model).
- [ ] T077 [P] [US5] Phase-2 test for `design.print.batch` wizard: PDF generation, 24h cache TTL, only-approved-files constraint
- [X] T078 [US5] Migration step: seed `design.file` from historical orders (FR-023) — `storage_mode='url'`, populated from `DESIGN_LINK_FRONT`/`DESIGN_LINK_BACK` columns (delegates to Spec 002's migration wizard, which calls into `multichannel_hub_core.design_file.create`) — **landed in P1-02a (2026-04-29)** as `design.file._seed_from_historical_lines()` (idempotent on `(order_line_id, file_url)`, batched, skips empty URLs, probes `etsy_design_link_front` field presence). Default `state='approved'` + `is_seed=True` per D3 (proof-of-record semantics; owner-confirm flag in findings.md).

---

## Phase 8: US6 — Multi-Channel Foundation (P2)

**Goal**: `sales_channel` + `channel_order_ref` indexed and backfilled; channel decoration.
**Independent test**: Backfill idempotent; Amazon decoration distinct from Push.

- [ ] T079 [P] [US6] Verify migration script (T018) sets `sales_channel='etsy'` + `channel_order_ref=etsy_order_id` for all existing orders, idempotent on re-run
- [ ] T080 [P] [US6] Add Channel filter + group-by to all 3 dashboards (Order, Tracking, Process)
- [ ] T081 [P] [US6] Phase-2 test `tests/test_channel_backfill.py`: backfill correctness, idempotency, decoration logic for amazon channel

---

## Phase 9: US7 — Audit + Vietnamese UI (P2 cross-cutting)

**Goal**: Every tracked field produces chatter; 100% i18n coverage; UTF-8 round-trip.
**Independent test**: 5 tracked-field edits → 5 chatter rows; Vietnamese language renders all labels with diacritics; CI enforces 100%.

- [ ] T082 [P] [US7] Audit all spec-introduced models — confirm `mail.thread` + `mail.activity.mixin` inheritance; `tracking=True` on all user-visible scalar fields per FR-031
- [ ] T083 [US7] Create `i18n/vi_VN.po` skeleton with translations for all string literals introduced by this spec (labels, help, errors, kanban column titles, selection values)
- [ ] T084 [P] [US7] Implement `tests/test_i18n_coverage.py` parsing `.py` and `.xml` for `_()` calls, parsing `.po` for translations, asserting equality (FR-032 CI gate)
- [ ] T085 [P] [US7] Implement `tests/test_utf8_roundtrip.py` with diacritic fixture ("Đĩa tim mới") for Excel import → product creation → Excel export round-trip (FR-033)

---

## Phase 10: Polish & Cross-Cutting

- [ ] T086 [P] Add doc string headers to all new models referencing the relevant ADRs and spec.md FRs
- [ ] T087 [P] Update `CLAUDE.md` (project root) with `multichannel_hub_core` section + module entry-point note
- [ ] T088 [P] Add `README.md` to `multichannel_hub_core/` with quickstart pointer
- [ ] T089 Run `ruff check custom_addons/multichannel_hub_core/` and fix any violations
- [ ] T090 Run module update on staging (`docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init`) and verify clean install (no warnings/errors)
- [ ] T091 Run full test suite (`docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core --stop-after-init`); target ≥80% coverage
- [ ] T092 Run quickstart.md walkthrough end-to-end on staging; check off all 8 sections
- [ ] T093 Document the migration plan for the existing `etsy_integration` to declare `multichannel_hub_core` dependency (write `etsy_integration/migrations/19.0.1.0.X/post-migrate.py` if needed; otherwise declare in `__manifest__.py.depends`)

---

## Dependencies (story completion order)

```
Setup (T001–T005) → Foundational (T006–T020)
  ↓
US1 (T021–T031) ─┬─→ US4 (T051–T062)        ─┐
                 ├─→ US6 (T079–T081)         │
                 ├─→ US7 (T082–T085)         │── parallel after US1
US2 (T032–T039) ─┘                           │
                                              │
US3 (T040–T050) ←(depends on US1's x_pipeline_id field at T021)
                                              │
US5 (T063–T078) ←(depends on US1's design_status at T023)
                                              │
                                              ↓
                                       Polish (T086–T093)
```

**MVP** = Setup + Foundational + US1 + US4 (the order-dashboard + safety-critical address-change workflow). US2/US3/US5 layer in for full Phase 1; US6/US7 are cross-cutting and can land alongside.

## Parallel execution examples

Within Phase 2 (Foundational), the [P]-marked tasks can run in parallel:
- T006, T007, T012, T013, T014, T016, T017, T019, T020 can all proceed concurrently after T001-T005 complete.

Within Phase 3 (US1), parallelisable: T021, T023, T027, T028, T030.

Within Phase 7 (US5), parallelisable: T066, T067, T068, T070, T071, T072, T076, T077.

## Test coverage targets

- Phase-2 ORM unit: 80%+ across all introduced services + models
- Phase-1 DB: row-count and index assertions on every migration + seed
- E2E: deferred to Spec 003 cluster (not in this tasks list — per playbook E2E happens after all spec coding completes)

## Cross-references

- spec.md US1–US7 (each task maps to a User Story phase)
- plan.md (Stage 4.1 refresh) — module structure, ADR alignments
- data-model.md — model definitions (referenced per task)
- research.md R1–R5 — design decisions encoded
- ADRs: 001 (split), 003 (4-module), 005 (carrier), 006 (storage), 007 (delegation), 009 (file lifecycle), 010 (configurable pipeline), 012 (GDrive failover)
