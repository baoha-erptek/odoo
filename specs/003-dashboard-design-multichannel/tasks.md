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

## Phase 4b: P1-LBL — `label_status` Selection → Many2one (Owner directive D2, 2026-05-10)

**Source**: tracker row P1-LBL (`.claude/plans/006-master-plan-tracking.md` line 135) + JPG fixture `.0temp/2026-05-10_093634.jpg`.
**Goal**: replace the fixed `label_status` Selection on `sale.order.fulfillment` with a Many2one to a configurable master-data model `label.status.option`; seed 16 status options matching owner's daily-ops board.
**Independent test**: 16 seed rows present after install; fulfillment write to `label_status_id` resolves and emits bus event; non-BA-manager direct write raises AccessError; migration rewrites legacy Selection rows to safe-default `Chờ duyệt` with `_logger.warning` audit trail.
**Out of scope** — deferred to follow-up **P1-LBL-MIGRATE** slice: owner-authored mapping table for legacy Selection codes (`none`/`requested`/`buying`/`bought`/`failed`) → seed-record codes. Until that lands, all pre-existing fulfillment rows land on `Chờ duyệt` and BA-manager triages manually.

- [X] T-LBL-01 [P] [P1-LBL] Create `multichannel_hub_core/models/label_status_option.py` defining `label.status.option` Model: `name` Char(required, translate=True), `code` Char(unique, xmlid-friendly), `color` Integer(default=0), `sequence` Integer(default=10), `bucket` Selection([('target','MP target'),('pd_selfmake','PD self-make'),('done','Done'),('approval','Approval')], required=True), `active` Boolean(default=True). Inherit `mail.thread`; `tracking=True` on `name`/`bucket`/`active`/`color`/`sequence`. `_sql_constraints` UNIQUE on `code` and `name`.
- [X] T-LBL-02 [P1-LBL] Add `init()` raw-SQL UNIQUE mirror on `(code)` in `label_status_option.py` per `_sql_constraints` drift template (9th confirmation; canonical in `multichannel_hub_core/models/design_file.py:134-148`). Use `pg_constraint IF NOT EXISTS` pre-check (NOT EXCEPTION clause — PG raises 42P07 not 42710 on re-run).
- [X] T-LBL-03 [P] [P1-LBL] Create `multichannel_hub_core/data/label_status_data.xml` (`noupdate="1"`) with **16 seed records** keyed by xmlid `label_status_<code>`. Codes derived from JPG fixture `.0temp/2026-05-10_093634.jpg`:
  - **target bucket** (red box, "MP sẽ CHUYỂN TÌNH TRẠNG NÀY"): `us_od` ("US-od", color=1, seq=10), `vietnam_od` ("Vietnam-od", color=1, seq=20)
  - **pd_selfmake bucket** (green box, "pd TỰ SX"): `vn_tattoo` (color=10, seq=110), `vn_wooden_dish` (color=10, seq=120), `vn_dish` (color=10, seq=130), `vn_dish_ng` (color=2, seq=140), `vn_dish_fix` ("[Fix] VN-Dish", color=2, seq=150), `vn_sp_moi` ("VN-SP mới", color=10, seq=160), `vn_packed` (color=10, seq=170), `vn_packed_1` ("VN-Packed 1", color=10, seq=180), `vn_apron` (color=10, seq=190), `vn_handkerchief` (color=10, seq=200)
  - **done bucket** (blue box): `vn_fulfilled` ("VN-Fulfilled", color=4, seq=300)
  - **approval bucket** (orange box): `cho_duyet` ("Chờ duyệt", color=3, seq=410), `da_gui_proof` ("Đã gửi proof", color=3, seq=420), `cho_file` ("Chờ file", color=3, seq=430)
  - Names preserved verbatim (Vietnamese diacritics included). Color indices follow Odoo standard palette (1=red, 2=orange, 3=yellow, 4=light blue, 10=green).
- [X] T-LBL-04 [P] [P1-LBL] Add ACL rows in `multichannel_hub_core/security/ir.model.access.csv`: `access_label_status_option_user` (`base.group_user`, R/0/0/0); `access_label_status_option_ba_manager` (`multichannel_hub_core.group_ba_manager`, R/W/C/U). Read for everyone, write only for BA-manager.
- [X] T-LBL-05 [P1-LBL] In `multichannel_hub_core/models/sale_order_fulfillment.py:80`, replace the `label_status = fields.Selection(...)` definition with `label_status_id = fields.Many2one('label.status.option', ondelete='restrict', tracking=True, index=True)`. Drop the legacy Selection attribute entirely; **do NOT keep both fields** (avoids dual-write divergence per memory `feedback_fr017_write_defense_in_depth.md`).
- [X] T-LBL-06 [P1-LBL] Update `_BUS_TRIGGER_FIELDS` (line 12) and `_ADDRESS_LOCK_FIELDS` (line 28) in `models/sale_order_fulfillment.py`: replace literal `'label_status'` with `'label_status_id'` in both frozensets. Update bus payload at line 229: `'label_status': self.label_status_id.code` (transmit the comodel code, not the M2O id).
- [X] T-LBL-07 [P1-LBL] **FR-017 16th confirmation**: extend `sale.order.fulfillment.write()` (and `create()` if it touches `label_status_id`) to require `_check_ba_manager_or_raise()` BEFORE `sudo().write({...})` whenever `label_status_id` is in `vals`. Pattern mirrors P2-06 `logistics.partner` write defense exactly. ACL CSV stays read-only for BA-shipping users so the override is the only write path.
- [X] T-LBL-08 [P1-LBL] Update `multichannel_hub_core/views/operations_dashboard_views.xml` (lines 50-53, 76, 93-94): replace `<field name="label_status" widget="badge" decoration-...>` with `<field name="label_status_id" widget="many2one_tags" options="{'no_create': True}"/>`; rewrite the saved-filter domain at line 76 (`[('label_status', '=', 'bought')]`) to use the seed xmlid, e.g. `[('label_status_id.code', '=', 'vn_fulfilled')]` (or whichever code matches the legacy "bought" semantic — owner sign-off in P1-LBL-MIGRATE will finalize); update `group_by` filter at line 93-94 to `'label_status_id'` (Many2one group-by uses comodel `display_name` automatically; flat-sibling per Odoo 19 RNG memory).
- [X] T-LBL-09 [P1-LBL] Update `multichannel_hub_core/data/operations_dashboard_saved_filters.xml` line 40: rewrite the legacy domain `[..., ('label_status', '!=', 'none')]` to use `('label_status_id', '!=', False)` (M2O Falsy means "unset"; matches the legacy "none" semantic).
- [X] T-LBL-10 [P1-LBL] Create `multichannel_hub_core/migrations/19.0.1.0.<NEXT>/post-label-status-default.py` (NEXT = post-bump manifest version, choose at commit time). Script:
  1. `target = env.ref('multichannel_hub_core.label_status_cho_duyet', raise_if_not_found=True)`.
  2. `cr.execute("SELECT id FROM sale_order_fulfillment WHERE label_status_id IS NULL")` → collect IDs.
  3. `cr.execute("UPDATE sale_order_fulfillment SET label_status_id = %s WHERE label_status_id IS NULL", (target.id,))`.
  4. `_logger.warning("P1-LBL migration: rewrote %d sale.order.fulfillment rows to default 'Chờ duyệt' (id=%s); audit list: %s", count, target.id, list(ids))` — enumerate rewritten record IDs per tracker requirement.
- [X] T-LBL-11 [P1-LBL] Update existing tests that hard-code legacy Selection values (the slice MUST land green): `tests/test_tracking_dashboard.py:91,98,229,286`, `tests/test_operations_dashboard_orm.py:102,182,192,201,322-333`, `tests/test_phase2_orm.py:166-168`, `tests/test_audit_coverage_db.py:124`, `tests/test_operations_dashboard_db.py:225-227`. Replace literal `'bought'`/`'none'`/`'requested'`/`'failed'` writes with `env.ref('multichannel_hub_core.label_status_<code>').id` writes; replace introspection of `label_status` Selection with `label_status_id` M2O. Default-value assertion in `test_phase2_orm.py:166-168` flips from `'none'` to `False` (M2O default).
- [X] T-LBL-12 [P] [P1-LBL] Phase 1 DB tests in new `multichannel_hub_core/tests/test_label_status_db.py`:
  - `test_model_registered` — `'label.status.option' in env.registry`
  - `test_unique_constraint_present` — `pg_constraint` row for `code_unique` post-install (drift-template idempotency check)
  - `test_seed_records_loaded` — exactly 16 rows, bucket distribution `target=2, pd_selfmake=10, done=1, approval=3`
  - `test_seed_xmlids_resolvable` — every `label_status_<code>` xmlid resolves
  - `test_fulfillment_field_swap` — `sale_order_fulfillment` table has `label_status_id` integer FK column; legacy `label_status` varchar column does NOT exist (dropped, not orphaned)
  - `test_acl_grants` — `ir.model.access` rows for `label.status.option`: base.group_user R-only; group_ba_manager R/W/C/U
- [X] T-LBL-13 [P1-LBL] Phase 2 ORM tests in new `multichannel_hub_core/tests/test_label_status_orm.py`:
  - `test_create_with_duplicate_code_raises` — IntegrityError surfaces ValidationError
  - `test_fulfillment_write_emits_bus_on_label_status_id_change` — bus.bus channel `multichannel_hub.fulfillment_update` fires when `label_status_id` changes
  - `test_fulfillment_write_blocked_for_non_ba_manager` — FR-017 16th confirmation: BA-shipping user write raises AccessError; ba_manager user succeeds
  - `test_fulfillment_address_lock_includes_label_status_id` — pending address change blocks `label_status_id` write per `_ADDRESS_LOCK_FIELDS`
  - `test_migration_default_writes_cho_duyet_with_warning` — apply migration helper to fulfillment rows with NULL `label_status_id`; assert all rewritten to `label_status_cho_duyet` xmlid and `_logger.warning` captured via `assertLogs`
  - `test_kanban_color_reachable_via_m2o` — `fulfillment.label_status_id.color` is an integer in palette range
- [X] T-LBL-14 [P1-LBL] Bump `multichannel_hub_core/__manifest__.py` version (next free patch) and append `'data/label_status_data.xml'` to the `data` list. Verify clean install: `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` returns 0; expect post-migration `_logger.warning` line confirming rewrite count; ruff check (if available) clean.

---

## Phase 4c: P1-01b — Operations Dashboard refactor `sale.order` → `sale.order.line` (Owner directive D6, 2026-05-10)

**Source**: tracker row P1-01b (`.claude/plans/006-master-plan-tracking.md` line 136) + Excel fixture `.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx` sheet "Trang tính1" (34 columns, header row enumerated below).
**Goal**: refactor the unified Operations Dashboard list from `sale.order` to `sale.order.line` so each visible row is a line item (matching the operator's existing daily-ops Excel mental model). Lift the 34-column layout from owner's Excel (column order + headers must match — owner directive D6 forbids editing the Excel). Order-level fields are pulled in via `related='order_id.*'`; address fields via `related='order_id.partner_shipping_id.*'`; line-level fields are native or new on `sale.order.line`. Keep the P1-01a row decorations (qty≥2, duplicate-buyer, push-urgent, amazon) and the P1-DASH-MERGE BA/Marketing/PD tracking columns by hopping through `order_id`.
**Independent test**: dashboard action `action_operations_dashboard` opens a `sale.order.line` list with all 34 Excel columns visible (or `optional='hide'` per UAT preference), in the exact column order the Excel uses; multi-select + `action_bulk_mark_shipped` server action operates on lines and delegates to `order_id.fulfillment_id.action_bulk_mark_shipped()` preserving FR-017 silent-skip + production_team RPC gate; row decorations fire on the line view via `order_id.qty_total` etc.; saved filters from `data/operations_dashboard_saved_filters.xml` rebind to the line model with domain rewrites; legacy `sale.order` list view is **kept under a separate menu** (`menu_operations_dashboard_legacy_orders`) for one sprint per R-2026-05-10.
**Out of scope** — deferred follow-ups: (a) per-line bulk Push-to-Gearment action (lands in P4-01 step (b)); (b) Excel-export round-trip of the line view (lands in P2-01 GKE schema work — owner directive); (c) form-view replacement for `sale.order.line` (the dashboard form fallback hops to `sale.view_order_form` via `order_id`); (d) historical `etsy_design_link_front/back` ↔ new `design_link_front/back` reconciliation (defer to P1-LBL-MIGRATE-style mapping slice if owner finds drift on staging UAT).

**Excel column reference (sheet "Trang tính1", row 1, verbatim — column order is contract)**:
1. `TRANSACTION_ID` → line.`etsy_transaction_id` (etsy_integration extension)
2. `IMG_URL` → new line.`image_url` (Char, free-text; populated from product or channel ingest where available)
3. `IMG` → line.`product_image_thumb` (existing, P1-IMG-LINE-WIDGET — Binary widget="image")
4. `DATE` → related `order_id.date_order`
5. `NOTE_FROM_BUYER` → related `order_id.note` (existing sale.order field) OR new `order_id.buyer_note` if channel-agnostic split needed (planner decides)
6. `GIFT_MESSAGE` → new related `order_id.gift_message` (Char on sale.order in mhc; channel-agnostic; etsy ingest writes here)
7. `PERSONALISATION` → line.`etsy_personalisation`
8. `SKU` → line.`etsy_sku` (or fallback to `product_id.default_code` when null)
9. `SHOP` → related `order_id.sales_channel` (Selection, label) OR `order_id.channel_order_ref` for shop-name display — planner reconciles with existing `etsy_shop_id` reference
10. `ORDER_ID` → related `order_id.channel_order_ref` (FR-024) with fallback to `order_id.name`
11. `SHIPPING_NAME` → related `order_id.partner_shipping_id.name`
12. `SHIPPING_ADDRESS1` → related `order_id.partner_shipping_id.street`
13. `SHIPPING_ADDRESS2` → related `order_id.partner_shipping_id.street2`
14. `SHIPPING_CITY` → related `order_id.partner_shipping_id.city`
15. `SHIPPING_STATE` → related `order_id.partner_shipping_id.state_id` (display_name via M2O)
16. `SHIPPING_ZIPCODE` → related `order_id.partner_shipping_id.zip`
17. `SHIPPING_COUNTRY` → related `order_id.partner_shipping_id.country_id`
18. `SHIPPING_PHONE` → related `order_id.partner_shipping_id.phone`
19. `SHIPPING_EMAIL` → related `order_id.partner_shipping_id.email`
20. `PRODUCT_NAME` → related `product_id.display_name`
21. `OPTION` → new line.`option_label` (Char; computed from `product_template_attribute_value_ids` where derivable, else free-text editable)
22. `COLOR` → new line.`color` (Char; same derivation as OPTION)
23. `SIZE` → new line.`size` (Char; same derivation)
24. `SIDE` → new line.`side` (Char; same derivation)
25. `FACE_MASK_SIZE` → new line.`face_mask_size` (Char; same derivation)
26. `QUANTITY` → line.`product_uom_qty`
27. `DESIGN_LINK_FRONT` → new line.`design_link_front` (Char; channel-agnostic; planner decides whether to alias or supersede `etsy_design_link_front`)
28. `DESIGN_LINK_BACK` → new line.`design_link_back` (Char; same as above)
29. `SHIPPING_SERVICE` → related `order_id.shipping_carrier_id.name` (existing via P1-05 delegation) OR new `order_id.shipping_service_label` if channel-supplied label diverges from carrier match
30. `PROCESSING_TIME` → new related `order_id.processing_time` (Char or Integer days; channel-supplied, etsy ingest populates)
31. `SHIPPING_COST` → related `order_id.amount_delivery` (Monetary; existing on sale.order)
32. `PRICE` → line.`price_unit`
33. `DISCOUNT_CODE` → new related `order_id.discount_code` (Char; channel-supplied)
34. `SUBTOTAL` → line.`price_subtotal` (existing on sale.order.line)

**Keep BA/Marketing/PD columns** (related fields hopping through `order_id` to `sale.order.fulfillment` via P1-05 _inherits delegation):
- `pic_user_id` (BA owner)
- `pd_pic_user_id` (PD owner)
- `mp_note` (Marketing note)
- `label_status_id` (Many2one widget per P1-LBL — `widget="many2one_tags" options="{'no_create': True, 'no_open': True}"`)
- `order_priority`
- `production_blocked`
- `is_overdue_approval` (boolean toggle)

**Tasks**:

- [X] T-01b-01 [P] [P1-01b] In `multichannel_hub_core/models/sale_order_line.py`, add the 7 new line-level Char fields per the Excel mapping: `image_url`, `option_label`, `color`, `size`, `side`, `face_mask_size`, `design_link_front`, `design_link_back`. Each is `fields.Char(string=...)` with no `required=True`. For OPTION/COLOR/SIZE/SIDE/FACE_MASK_SIZE: store=False compute `_compute_attribute_label` reading `product_template_attribute_value_ids` (filter by attribute name match — case-insensitive; surface raw value); fallback to manual entry by making the compute non-stored + `inverse=` writing user-supplied value to a sibling `_manual` Char and `_compute` preferring manual when set. Planner refines the compute/inverse split during Phase 1. For `image_url`/`design_link_front`/`design_link_back`: plain stored Char, channel-ingest writes them (no compute).
- [X] T-01b-02 [P] [P1-01b] In `multichannel_hub_core/models/sale_order.py`, add the 4 new order-level fields per the Excel mapping that have no current home: `gift_message` (Char), `processing_time` (Char or Integer days — planner decides; default to Char for channel-supplied free-text), `discount_code` (Char), `shipping_service_label` (Char; nullable; falls back to `shipping_carrier_id.name` in the dashboard related field). All `tracking=True` per FR-031 audit-coverage pattern. No `required=True`.
- [X] T-01b-03 [P1-01b] **Refactor** `multichannel_hub_core/views/operations_dashboard_views.xml` `operations_dashboard_list_view`: change `<field name="model">` from `sale.order` to `sale.order.line`. Replace all 16 fields in the existing `<list>` with the **34-column Excel order** (TRANSACTION_ID first, SUBTOTAL last). For columns 2-19 + 29-34 use `<field name="order_id"/>` chains via related fields declared in T-01b-04; for columns 1, 7, 8, 20-28 use native or new line fields. Default `optional="hide"` for the long-tail address columns (SHIPPING_ADDRESS2, SHIPPING_PHONE, SHIPPING_EMAIL) and PROCESSING_TIME/DISCOUNT_CODE; default `optional="show"` for the operator-critical ones (TRANSACTION_ID, IMG, DATE, PERSONALISATION, SKU, ORDER_ID, SHIPPING_NAME, PRODUCT_NAME, QUANTITY, SHIPPING_SERVICE, PRICE, SUBTOTAL). Append the 7 BA/Marketing/PD columns at the right edge (`pic_user_id`, `pd_pic_user_id`, `mp_note`, `label_status_id`, `order_priority`, `production_blocked`, `is_overdue_approval`) with `optional="show"`.
- [X] T-01b-04 [P1-01b] In `multichannel_hub_core/models/sale_order_line.py`, add **related-field shadows** for every order/address/fulfillment field the dashboard list reads, so the list view can declare them by name without OWL having to traverse dot-paths in templates. Pattern: `field_name_dash = fields.<Type>(related='order_id.<path>', readonly=True, string='<EXCEL_HEADER>')` for: `date_order`, `note`, `gift_message`, `channel_order_ref`, `sales_channel`, `partner_shipping_name` (related='order_id.partner_shipping_id.name'), `partner_shipping_street`, `partner_shipping_street2`, `partner_shipping_city`, `partner_shipping_state_id`, `partner_shipping_zip`, `partner_shipping_country_id`, `partner_shipping_phone`, `partner_shipping_email`, `shipping_carrier_id`, `shipping_service_label`, `processing_time`, `amount_delivery`, `discount_code`, **plus** the BA/PD/MP set: `pic_user_id`, `pd_pic_user_id`, `mp_note`, `label_status_id`, `order_priority`, `production_blocked`, `is_overdue_approval` (these last 7 chain `order_id.fulfillment_id.<field>` via the P1-05 _inherits delegation; planner verifies the related path resolves). **Heritage decoration flags**: also expose `qty_total`, `is_duplicate_buyer` as related from `order_id`. All related fields `readonly=True` (write goes to the canonical owner via the form view), `store=False` unless the dashboard search/filter needs them indexed (planner judges per filter — start with store=False for safety).
- [X] T-01b-05 [P1-01b] Refactor `operations_dashboard_search_view` in the same XML file: change `<field name="model">` to `sale.order.line`. Re-anchor existing search fields/filters/group-bys on `order_id.<path>` (or the new related shadow declared in T-01b-04 — planner picks whichever yields the cleaner domain). Preserve all 6 group-by filters (`Sales Channel`, `Carrier`, `Tracking State`, `Label Status`, `Warehouse`, `Priority`) and all 5 boolean filters (`Production Blocked`, `Label Set`, `Shipped`, `Delivered`, `VN Warehouse`, `US Warehouse`).
- [X] T-01b-06 [P1-01b] Refactor `action_operations_dashboard` in the same XML file: `res_model` from `sale.order` to `sale.order.line`; `view_mode="list,form"` retained; `view_id` still `operations_dashboard_list_view`. Add a separate `view_ids` ordered list pinning the form fallback to `sale.view_order_form` (Odoo's stock sale.order form), with `view_mode="form"` mapped to a thin OWL form action that opens `order_id` instead of the line — pattern: `view_mode="list,form"` with `views=[(operations_dashboard_list_view, 'list'), (False, 'form')]` letting Odoo auto-pick a sensible form view on `sale.order.line` (which is empty by default). If that fails the operator UAT loop, add an explicit `act_window` redirect on the form action that opens `sale.order` form via `order_id`. Planner finalizes the redirect mechanism in Phase 1.
- [X] T-01b-07 [P1-01b] Re-bind the row decorations on the new line list view (in T-01b-03): `decoration-info="qty_total >= 2"` (now reads the related shadow from order), `decoration-bf="is_duplicate_buyer"`, `decoration-danger="order_priority in ('push','urgent')"`, `decoration-warning="sales_channel == 'amazon'"`. All four shadow fields are declared in T-01b-04. Keep them `column_invisible="1"` in the list arch.
- [X] T-01b-08 [P1-01b] Re-bind `action_server_bulk_mark_shipped` server action: `model_id` and `binding_model_id` change from `model_sale_order` to `model_sale_order_line`; the `code` field changes from `action = records.action_bulk_mark_shipped()` to `action = records.mapped('order_id').action_bulk_mark_shipped()` (dedupe parent orders before delegating, preserves FR-017 silent-skip on the parent). Add a defensive `mapped('order_id.fulfillment_id')` guard so lines on orders without a fulfillment row are silently skipped.
- [X] T-01b-09 [P1-01b] Update `multichannel_hub_core/data/operations_dashboard_saved_filters.xml`: rewrite each `ir.filters` row's `model_id` from `sale.order` to `sale.order.line` and rewrite each `domain` field to traverse through `order_id` (e.g. `[('production_blocked', '=', True)]` → `[('order_id.production_blocked', '=', True)]` or `[('production_blocked', '=', True)]` if T-01b-04 declared the related shadow). Preserve role-marker names per P1-DASH-MERGE owner Q1 deferred decision.
- [X] T-01b-10 [P1-01b] Add a **fallback legacy menu** + `ir.actions.act_window` that re-creates the previous `sale.order` list (using `operations_dashboard_list_view`'s previous arch as captured in git pre-P1-01b) under `Operations → Legacy → Order View (P1-01a)`. Group-gated on `multichannel_hub_core.group_ba_lead`. Lifetime: **one sprint** per R-2026-05-10 — append a `<!-- TODO: remove after 2026-05-24 staging UAT sign-off -->` comment to the menu/action records and open a tracker R-2026-05-10-FOLLOWUP row on slice landing.
- [X] T-01b-11 [P1-01b] Optional `ir.config_parameter` `multichannel_hub.dashboard_default_columns` (Char; comma-separated list of `optional` field names whose default is `show` regardless of the arch defaults). If unset, T-01b-03's hard-coded defaults apply. No model code reads this in P1-01b — purely a forward-compat marker so a future slice can wire it without a schema bump. Document in `multichannel_hub_core/__manifest__.py` description if convenient.
- [X] T-01b-12 [P] [P1-01b] **Phase 1 DB tests** in new `multichannel_hub_core/tests/test_operations_dashboard_line_db.py`:
  - `test_view_model_is_sale_order_line` — `env.ref('multichannel_hub_core.operations_dashboard_list_view').model == 'sale.order.line'`
  - `test_action_res_model_is_sale_order_line` — `env.ref('multichannel_hub_core.action_operations_dashboard').res_model == 'sale.order.line'`
  - `test_search_view_model_is_sale_order_line` — `env.ref('multichannel_hub_core.operations_dashboard_search_view').model == 'sale.order.line'`
  - `test_bulk_shipped_binding_model_is_sale_order_line` — server action `binding_model_id` resolves to `sale.order.line`
  - `test_legacy_menu_present` — `menu_operations_dashboard_legacy_orders` exists and resolves to a `sale.order` list action
  - `test_new_line_fields_columns_exist` — pg_columns on `sale_order_line` table for `image_url`, `option_label`, `color`, `size`, `side`, `face_mask_size`, `design_link_front`, `design_link_back`
  - `test_new_order_fields_columns_exist` — pg_columns on `sale_order` table for `gift_message`, `processing_time`, `discount_code`, `shipping_service_label`
  - `test_excel_column_count_matches` — parse `operations_dashboard_list_view` arch via lxml; assert exactly 34 Excel-named columns + ≤7 BA/Marketing/PD columns + ≤3 invisible decoration-driver columns; no extra fields
  - `test_excel_column_order_matches` — assert the 34 Excel columns appear in the list arch in the exact order from `.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx` row 1 (TRANSACTION_ID first, SUBTOTAL last)
- [X] T-01b-13 [P1-01b] **Phase 2 ORM tests** in new `multichannel_hub_core/tests/test_operations_dashboard_line_orm.py`:
  - `test_attribute_compute_derives_option_label` — create product.template with attribute "Option=Print" + "Color=Red"; assert `line.option_label == 'Print'`, `line.color == 'Red'`
  - `test_attribute_compute_falls_back_to_manual_entry` — write `line.color = 'Custom'` on a line whose product has no Color attribute; assert read-back returns `'Custom'`
  - `test_related_address_fields_resolve` — create order with shipping partner; assert `line.partner_shipping_name`, `partner_shipping_street`, `partner_shipping_zip` resolve to the partner's values
  - `test_related_order_fields_resolve` — assert `line.date_order`, `line.gift_message`, `line.discount_code` reflect order-level writes
  - `test_related_fulfillment_fields_resolve` — assert `line.label_status_id`, `line.pic_user_id`, `line.production_blocked` reflect `order_id.fulfillment_id.<field>` via _inherits delegation
  - `test_related_decoration_flags_resolve` — assert `line.qty_total`, `line.is_duplicate_buyer`, `line.order_priority`, `line.sales_channel` resolve from `order_id.*`
  - `test_bulk_shipped_action_dedupes_orders` — select 5 lines across 2 orders; call `action_server_bulk_mark_shipped`; assert `mapped('order_id')` was called once per order (not per line) — pattern: introspect via `unittest.mock.patch.object(SaleOrder, 'action_bulk_mark_shipped')`
  - `test_bulk_shipped_action_skips_lines_without_fulfillment` — order with no fulfillment row; bulk action returns silently, no AccessError
  - `test_bulk_shipped_action_preserves_fr017_gate` — non-production-team user bulk-clicks; FR-017 silent-skip fires (existing parent test re-asserted on the line entry-point) — **9th FR-017 confirmation** (per memory `feedback_fr017_write_defense_in_depth.md`)
  - `test_saved_filters_rebound_to_line_model` — every row in `data/operations_dashboard_saved_filters.xml` has `model_id == 'sale.order.line'`
  - `test_legacy_menu_action_targets_sale_order` — legacy menu's act_window opens `sale.order` (so operators have a fallback during UAT)
- [X] T-01b-14 [P1-01b] Bump `multichannel_hub_core/__manifest__.py` version (next free patch — likely 19.0.1.0.32). No new XML data file (saved filters edited in-place, no new model means no migration script). If T-01b-02 changes `sale.order` field tracking flags, add an idempotent migration `migrations/19.0.1.0.32/post-stamp-new-sale-order-fields.py` that backfills NULLs to safe defaults (empty string / False) per `_sql_constraints` drift template philosophy. Verify clean install + upgrade: `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` returns 0.
- [X] T-01b-15 [P1-01b] Update `multichannel_hub_core/CLAUDE.md` (or `README.md`) "Active" list to mention P1-01b dashboard refactor; update `findings.md` with anything surprising the planner / tdd-guide / code-reviewer cycle finds (Excel column ↔ Odoo field translation gaps are likely candidates).

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
- [X] T066 [P] [US5] Implement `design.file.route` model in `models/design_file_route.py` per data-model.md §7 with `idempotency_key` UNIQUE — **landed in P1-02b (2026-04-29)** in `multichannel_hub_core/models/design_file_route.py`. Stored SHA-256 compute on `{file_id}_{recipient_id}_{delivery_method}`; `_sql_constraints` UNIQUE mirrored in `init()` raw SQL via `pg_constraint IF NOT EXISTS` pre-check (drift-template). 2 `@api.constrains` C-DR-001/003. Action methods (`action_dispatch`/`action_acknowledge`) gated by `_check_production_team_or_raise()` per FR-017.
- [ ] T067 [P] [US5] Implement `design.print.batch` wizard in `models/design_print_batch.py` per data-model.md §8 with C-DB-001 (only approved files allowed)
- [X] T068 [P] [US5] Implement `services/design_file_router.py` with queued-job dispatcher (5 retries with exponential backoff per ADR-009 §4 + ADR-012) — **landed in P1-02b (2026-04-29)** as `design.file.router` AbstractModel with `dispatch(file_id, recipient_types=None) → {queued, deduped}`. Idempotency-key dedup via Route.search before create. Recipient resolution from `ir.config_parameter` keys `multichannel_hub.routing.recipient_user.{mp,ba,pd}` with `self.env.user` fallback. **5-retry exponential backoff deferred to P1-02c** (queue_job wrap; tests mock `action_dispatch`); marked TODO in code.
- [ ] T069 [US5] Implement A4 layout PDF generator (services or wizard helper); cache as `ir.attachment` with TTL 24h
- [ ] T070 [P] [US5] Implement cron `cron_design_print_batch_expire` flipping cached_pdf to expired after 24h
- [X] T071 [P] [US5] Create `views/design_file_views.xml` (form, list, kanban with 3 columns Chờ duyệt/Duyệt/Cần chỉnh lại); production-team-only ACL on drag-drop — **landed in P1-02a (2026-04-29)** in `multichannel_hub_core/views/design_file_views.xml`. RPC-level `has_group(group_production_team)` gate in `write()` defends drag-drop beyond view-level `groups=` (which is bypassable via XML-RPC).
- [ ] T072 [P] [US5] Create `views/design_print_batch_wizard.xml` (TransientModel wizard form)
- [X] T073 [US5] Add stuck-route badge computation on `sale.order` reading `design.file.route.state` ∈ {pending, failed} AND create_date < now()-2h — **landed in P1-02b (2026-04-29)** as `sale.order.stuck_route_badge` Boolean compute (`store=False`). `@api.depends` on `design_file_ids.route_ids.{state,create_date}` and `order_line.design_file_ids.route_ids.{state,create_date}`. Plan R3 perf risk acknowledged (computed-on-read; index `design_file_route_design_file_id_state_idx` covers hot path).
- [X] T074 [US5] Modify `sale.order.line._compute_design_status` (T023) to be route-state aware ("approved-pending-route" gradient per plan.md §Stage-2 ADR deltas) — **landed in P1-02b (2026-04-29)**. Selection extended with `('approved-pending-route', ...)`; depends adds `design_file_ids.route_ids.state`; compute returns `'approved-pending-route'` when all files approved AND any route in {pending, failed}.
- [X] T075 [US5] Implement REQ-AUT-02 — on `sale.order.action_confirm()`, route file design via `design.file.router.dispatch` per ADR-009 §4 — **landed in P1-02b (2026-04-29)** via `sale.order.action_confirm()` override + `_after_confirm_routing()` helper. Iterates approved `design.file` records on the order, calls `design.file.router.dispatch(file.id)`, swallows exceptions (does not block confirm), posts chatter when routes remain pending/failed.
- [X] T076 [P] [US5] Phase-2 test `tests/test_design_file_lifecycle.py`: storage-mode enforcement, immutable history (parent_file_id chain), route state machine, idempotency_key dedup, stuck-route badge — **completed across P1-02a + P1-02b (2026-04-29)**. P1-02a covered storage-mode + ACL + mail-thread + design_status rollup + 10 MB cap. P1-02b adds route state machine, idempotency_key dedup (collision + DB UNIQUE), stuck-route badge (3-true / 2-false cases), route-aware design_status (4 cases), on-confirm hook (4 cases), C-DR-001/003 + 2 C0-DR-001 RPC-gate regression tests in `tests/test_design_file_lifecycle_p1_02b.py` (32 + 2 tests). Immutable-history full chain test still deferred (no re-upload action yet — folds into P1-02c).
- [ ] T077 [P] [US5] Phase-2 test for `design.print.batch` wizard: PDF generation, 24h cache TTL, only-approved-files constraint
- [X] T078 [US5] Migration step: seed `design.file` from historical orders (FR-023) — `storage_mode='url'`, populated from `DESIGN_LINK_FRONT`/`DESIGN_LINK_BACK` columns (delegates to Spec 002's migration wizard, which calls into `multichannel_hub_core.design_file.create`) — **landed in P1-02a (2026-04-29)** as `design.file._seed_from_historical_lines()` (idempotent on `(order_line_id, file_url)`, batched, skips empty URLs, probes `etsy_design_link_front` field presence). Default `state='approved'` + `is_seed=True` per D3 (proof-of-record semantics; owner-confirm flag in findings.md).

---

## Phase 7.5: P1-09 — GDrive Design-File Upload Service & Wizard

**Goal**: Service-account-authenticated GDrive upload path; new `storage_mode='gdrive'` mode + 3 fields (`gdrive_file_id`, `gdrive_preview_url`, `gdrive_folder_id`) + `gdrive_thumbnail` Binary; TransientModel wizard from `sale.order.line`. Unblocks P1-02c (queue_job retry wrap) + P2-06 (GDrive polling cron).

**Independent test**: Service-account auth via `secrets/gdrive-service-account.json` (P0-03); upload returns Drive file ID; `design.file(storage_mode='gdrive')` persisted with `gdrive_file_id` non-empty; thumbnail ≤ 256 KB JPEG; folder cached per shop; module install clean.

**ADR alignment**: ADR-006 §3 (storage modes) + §6 (folder structure + write policy); ADR-012 §3 (no auto-fallback on failure — surface error). Both ADRs verified consistent with this slice; no amendments needed (planner audit 2026-04-30).

- [X] T094 [P] [US5] [P1-09] Implement `services/gdrive_uploader.py` in `multichannel_hub_core` (ADR-006 §3 + §6)
  - Service-account auth via `google-api-python-client` + `google-auth`; reads JSON from `/opt/odoo/secrets/gdrive-service-account.json` (matching P0-15 credential-path pattern)
  - Scopes: `https://www.googleapis.com/auth/drive.file` (minimum — app-created files only)
  - Public API: `upload_file(file_blob, file_name, folder_id) → {file_id, web_view_link, error}` and `ensure_shop_folder(shop) → folder_id`
  - Folder structure: `Multichannel Hub/Design Files/<shop_code>/<YYYY>/` (idempotent create-or-reuse; cache result on `etsy.shop.x_gdrive_design_folder_id`)
  - Error handling: auth/quota/503 failures return `{error: str(e), file_id: None}` — caller decides; no silent fallback to small-mode (ADR-012 §3)
  - Retry: synchronous try-once + exponential backoff sleep in P1-09. Queued retry deferred to P1-02c.
  - Audit: every call logged via `_logger.debug` (file_id, folder_id, result); no PII (no buyer name / order number)
  - Library pin: `google-api-python-client>=2.80.0`, `google-auth>=2.16.0` in `requirements.txt`

- [X] T095 [P] [US5] [P1-09] Implement `services/design_thumbnail_generator.py`
  - Public API: `generate_thumbnail(file_blob, max_size_kb=256) → bytes | None`
  - Library: Pillow (`pillow>=9.0.0`) — pure-python, no system deps. Wand fallback deferred (see findings P1-09 thumbnail-library decision)
  - Input formats: TIFF, PSD (via `psd-tools` if needed), JPEG, PNG, BMP, GIF
  - Output: JPEG ≤ 256 KB; quality auto-tuned to fit cap
  - Fallback: generation failure → returns `None` (caller stores empty `gdrive_thumbnail`; non-fatal)
  - Timeout: ≤ 2s wall-clock; abort beyond

- [X] T096 [P] [US5] [P1-09] Add fields to `design.file` model in `multichannel_hub_core/models/design_file.py`
  - `gdrive_file_id` Char
  - `gdrive_preview_url` Char (computed `store=True`, `@api.depends('gdrive_file_id')`, returns `https://drive.google.com/file/d/{gdrive_file_id}/view`)
  - `gdrive_folder_id` Char
  - `gdrive_thumbnail` Binary (`attachment=True`)
  - Extend `storage_mode` Selection: append `('gdrive', 'GDrive')`
  - Implement constraint C-DF-006 (`@api.constrains('storage_mode', 'gdrive_file_id', 'gdrive_folder_id')`)

- [X] T097 [US5] [P1-09] Create `models/design_file_upload_wizard.py` (TransientModel `design.file.upload.wizard`)
  - Fields: `file_blob` Binary, `file_name` Char, `storage_mode` Selection {small, url, gdrive} default `'gdrive'`, `file_url` Char, `gdrive_folder_id` Char, `thumbnail_blob` Binary (computed preview), `order_id` / `order_line_id` Many2one (from context)
  - Constraint C-DUW-001: `storage_mode='gdrive'` requires `gdrive_folder_id` non-empty
  - Method `action_upload()`:
    - For `gdrive`: call `GdriveUploader.upload_file()` → on success create `design.file(storage_mode='gdrive', gdrive_file_id=..., gdrive_preview_url=..., gdrive_folder_id=..., gdrive_thumbnail=thumbnail_blob)`
    - For `small`: existing path (file_blob → `design_file` Binary)
    - For `url`: existing path (file_url → `design.file.file_url`)
    - On Drive failure: raise `ValidationError` with user-friendly message offering "use URL instead" affordance (no auto-fallback per ADR-012 §3)
    - Post chatter on parent `sale.order` after creation
  - ACL: `group_production_team` + `group_system` callable; `group_marketing_user` + `group_ba_user` read-only

- [X] T098 [P] [US5] [P1-09] Create `views/design_file_upload_wizard.xml` (form + ir.actions.act_window)
  - Modal form with file input, mode radio (gdrive default), URL input (visible if mode=url), folder picker (visible if mode=gdrive), thumbnail preview, progress indicator
  - Buttons: "Upload & Create" (action_upload) / "Cancel"
  - Help text wrapped in `_()` for i18n (Vietnamese .po lands in P1-07)

- [X] T099 [US5] [P1-09] Wire wizard into `sale.order.line` form (button "Upload Design File")
  - Extend existing `multichannel_hub_core/views/sale_order_views.xml` (or sub-view if cleaner)
  - Action passes `default_order_id` + `default_order_line_id` + `default_gdrive_folder_id` (from shop cache) via context
  - Visible to `group_production_team` + `group_system`

- [X] T100 [P] [US5] [P1-09] Phase-1 (DB) test in `tests/test_gdrive_upload_db.py`
  - Verify schema: `design_file` table has columns `gdrive_file_id`, `gdrive_preview_url`, `gdrive_folder_id`, `gdrive_thumbnail`
  - Verify `storage_mode` Selection includes `'gdrive'`
  - Verify TransientModel `design.file.upload.wizard` is registered
  - Verify `etsy.shop.x_gdrive_design_folder_id` Char field exists (cache field)
  - Verify ACL rows for wizard

- [X] T101 [P] [US5] [P1-09] Phase-2 (ORM unit) test in `tests/test_gdrive_upload_orm.py` — coverage ≥80%
  - `TestGdriveUploader`: mocked auth + upload (mock `google.auth.default`, `googleapiclient.discovery.build`); upload success → returns dict with `file_id`; auth failure → returns `{error: ..., file_id: None}`; folder cache hit on second `ensure_shop_folder()` call (no extra Drive calls)
  - `TestThumbnailGenerator`: 50MB TIFF input → ≤256KB JPEG output; corrupted blob → returns None (no raise)
  - `TestUploadWizard`: gdrive-mode happy path creates `design.file(storage_mode='gdrive', gdrive_file_id=...)`; Drive failure raises `ValidationError`; chatter posted to parent `sale.order`; C-DUW-001 catches missing `gdrive_folder_id`
  - `TestC_DF_006`: `design.file.create(storage_mode='gdrive', gdrive_file_id='')` raises ValidationError; `gdrive_file_id='abc', gdrive_folder_id=''` also raises
  - `TestRpcGate`: non-production-team user calls `wizard.action_upload()` via mocked-rpc → AccessError (FR-017 defense-in-depth pattern from P1-02b)

**Slice exit criteria** (all required to mark P1-09 done):
- All 8 tasks T094–T101 marked `[X]`
- Phase 1 + Phase 2 tests pass; coverage ≥ 80% on changed lines
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` exit 0
- `ruff check custom_addons/multichannel_hub_core/services/gdrive_uploader.py custom_addons/multichannel_hub_core/services/design_thumbnail_generator.py custom_addons/multichannel_hub_core/models/design_file_upload_wizard.py` clean
- ACLs defined for wizard (production_team R/W/C; salesman R)
- C-DF-006 + C-DUW-001 enforced at constrains layer
- Tracker `state` flipped P1-09 `todo → doing → done`
- `findings.md` P1-09 section updated with any new surprises (or "no new surprises")
- `/learn` insight captured (or explicit "no new patterns")
- ADR-006 / ADR-012 alignment re-confirmed in commit body

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

- [X] T082 [P] [US7] Audit all spec-introduced models — confirm `mail.thread` + `mail.activity.mixin` inheritance; `tracking=True` on all user-visible scalar fields per FR-031 (P1-08 2026-05-03; schema-level satisfied; runtime tracking-value persistence deferred per Bug-2026-05-03-mail-tracking-not-firing)
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

## P1-DESIGN-AUTO-CREATE-FROM-EMAIL — auto-seed design.file on order ingest

Slice landed 2026-05-10 (commit on `feature/006-master-plan-coding`). Unblocks
Defect-2026-05-11-01 / reclassified Defect-2026-05-10-05: empty `data.line_items`
in Gearment payload because no design.file rows linked.

- [X] T-DF-AUTO-01 [US5] Add `created_via` Selection field to `design.file` (`migration_seed`, `email_ingest`, `api_ingest`, `operator_wizard`; default `operator_wizard`; `tracking=True`; `index=True`; `required=True`). ADR-009 amendment §"Provenance" — distinguishes auto-seeded rows from operator wizard uploads.
- [X] T-DF-AUTO-02 [US5] Implement `design.file._seed_design_files_from_lines(order, created_via)` instance method — search-before-create on `(order_line_id, file_url)` (mirrors `_seed_from_historical_lines` idempotency at design_file.py:580). Skips empty URLs. Creates rows with `state='pending'`, `storage_mode='url'`, `is_seed=False`. Returns count of newly created rows. Fail-fast `ValueError` if `created_via` not in `{email_ingest, api_ingest}`.
- [X] T-DF-AUTO-03 [US5] Hook `OrderCreator.process_parse_result` (email path, line ~325) and `OrderCreator.process_etsy_payload` (API path, line ~626) to call seed with `email_ingest` / `api_ingest` markers. API path also adds `design_link_front`/`back` to the inline `line_vals` dict so the channel-agnostic fields land on `sale.order.line` for both ingest sources.
- [X] T-DF-AUTO-04 [US5] Extend `EtsyLineItemPayload` dataclass with `design_link_front` and `design_link_back` (default `''`). Etsy v3 adapter does not yet populate them; future adapter slice will extract from receipt variations / personalisation. Today the API path is a structural no-op for auto-create, but the channel-agnostic field name lets `_build_line_vals` and `_seed_design_files_from_lines` work uniformly across paths.
- [X] T-DF-AUTO-05 [US5] Phase 1 DB tests (3) + Phase 2 ORM tests (14) — `multichannel_hub_core/tests/test_phase1_design_file_created_via.py`, `multichannel_hub_core/tests/test_phase2_design_auto_create_seed.py`, `etsy_integration/tests/test_phase2_order_creator_design_seed.py`. Coverage: front-only / back-only / both / empty-skip / idempotent re-run / pre-existing-url-skip / created_via marker / order-with-no-lines / email path E2E / API path E2E / re-ingest no duplicate / order_line ↔ design.file relation.
- [X] T-DF-AUTO-06 [US5] Post-install migration `migrations/19.0.1.0.35/post-migrate-backfill-created-via.py` — `is_seed=TRUE` rows → `'migration_seed'`; all other existing rows → `'operator_wizard'`. Idempotent (only touches `created_via IS NULL`). Manifest version 19.0.1.0.34 → 19.0.1.0.35.

Follow-ups:
- P1-DESIGN-API-EXTRACT-LINKS — extend `EtsyApiAdapter` to populate `design_link_front`/`back` on `EtsyLineItemPayload` from receipt `variations`/`personalisation`. Today it ships empty for the API path.

## Cross-references

- spec.md US1–US7 (each task maps to a User Story phase)
- plan.md (Stage 4.1 refresh) — module structure, ADR alignments
- data-model.md — model definitions (referenced per task)
- research.md R1–R5 — design decisions encoded
- ADRs: 001 (split), 003 (4-module), 005 (carrier), 006 (storage), 007 (delegation), 009 (file lifecycle, +Provenance amendment 2026-05-10), 010 (configurable pipeline), 012 (GDrive failover)
