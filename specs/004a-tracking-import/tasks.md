# Tasks — Spec 004a Slice P2-01

**Slice**: P2-01 GKE Excel import wizard with schema fingerprinting (US1)
**Module**: `multichannel_hub_fulfillment`
**Branch**: `feature/006-master-plan-coding`

Sibling slices (P2-02..P2-06) own their own task IDs in this same file when dispatched.

Legend: `[ ]` open, `[X]` done, `[~]` partial.

---

## Phase 2 — RED (tdd-guide agent)

- [X] **T2-01-01** Create `tests/__init__.py` (if absent) registering `test_phase1_db` + `test_phase2_orm`.
- [X] **T2-01-02** Author `tests/fixtures/gke_known_schema.xlsx` (50 rows; ≥1 date with `day <= 12`; mix of carriers USPS/UniUni/YunExpress prefixes; ≥1 row matching existing test order).
- [X] **T2-01-03** Author `tests/fixtures/gke_unknown_schema.xlsx` (header order swapped to trigger new-hash branch).
- [X] **T2-01-04** Author `tests/fixtures/gke_oversized.xlsx` placeholder + assertion path (skip generating real >10MB; mock `file_size_bytes` instead).
- [X] **T2-01-05** Author `tests/fixtures/gke_partial_match.xlsx` (matched + unmatched + conflict rows).
- [X] **T2-01-06** `test_phase1_db.py::test_tracking_import_log_table_exists` — query `information_schema.tables`.
- [X] **T2-01-07** `test_phase1_db.py::test_tracking_import_log_columns` — assert all 18 fields exist with correct types.
- [X] **T2-01-08** `test_phase1_db.py::test_tracking_import_line_columns` — same for line model.
- [X] **T2-01-09** `test_phase1_db.py::test_tracking_import_log_composite_index` — query `pg_indexes` for `(state, create_date DESC)`.
- [X] **T2-01-10** `test_phase1_db.py::test_tracking_import_line_unique_constraint` — query `pg_constraint` for `tracking_import_line_idempotency_uniq`.
- [X] **T2-01-11** `test_phase1_db.py::test_acl_rows_exist` — query `ir.model.access` for 3 expected rows per model.
- [X] **T2-01-12** `test_phase2_orm.py::test_create_log_minimal` — basic ORM create.
- [X] **T2-01-13** `test_phase2_orm.py::test_log_state_machine_transitions` — pending → processing → ok.
- [X] **T2-01-14** `test_phase2_orm.py::test_constraint_file_size_cap` — exceeds ICP raises ValidationError.
- [X] **T2-01-15** `test_phase2_orm.py::test_constraint_terminal_finish_at` — ok without finish_at raises.
- [X] **T2-01-16** `test_phase2_orm.py::test_line_constraint_matched_requires_order` — matched without sale_order_id raises.
- [X] **T2-01-17** `test_phase2_orm.py::test_line_idempotency_unique_constraint` — duplicate `(log_id, source_row_hash)` raises IntegrityError.
- [X] **T2-01-18** `test_phase2_orm.py::test_schema_hash_stable_for_same_headers` — two parses of same fixture produce identical hash.
- [X] **T2-01-19** `test_phase2_orm.py::test_schema_hash_changes_on_column_reorder` — reordered headers → different hash.
- [X] **T2-01-20** `test_phase2_orm.py::test_schema_hash_normalizes_case_and_trim` — `" Order Number "` and `"order number"` collapse to same hash.
- [X] **T2-01-21** `test_phase2_orm.py::test_action_preview_creates_log_pending` — wizard action transitions to `previewed` state.
- [X] **T2-01-22** `test_phase2_orm.py::test_action_preview_unknown_schema_blocks_import` — `is_new_schema=True` and `action_import` refuses.
- [X] **T2-01-23** `test_phase2_orm.py::test_action_approve_schema_requires_ba_manager` — non-manager `has_group` raises AccessError.
- [X] **T2-01-24** `test_phase2_orm.py::test_action_approve_schema_appends_icp` — ICP `gke_schema_hashes` JSON list grows.
- [X] **T2-01-25** `test_phase2_orm.py::test_action_approve_schema_records_sync_health` — `etsy.sync.health` gets `gke_schema_approved` event.
- [X] **T2-01-26** `test_phase2_orm.py::test_action_import_writes_tracking_to_fulfillment` — matched row's fulfillment.tracking_number updated.
- [X] **T2-01-27** `test_phase2_orm.py::test_action_import_skips_carrier_when_already_set` — order with existing carrier keeps it; line records detected_carrier_id only.
- [X] **T2-01-28** `test_phase2_orm.py::test_action_import_per_row_savepoint` — one row error does not abort batch.
- [X] **T2-01-29** `test_phase2_orm.py::test_action_import_idempotent_on_rerun` — re-import same file results in 0 new writes; duplicate raises caught silently.
- [X] **T2-01-30** `test_phase2_orm.py::test_action_import_dayfirst_date_parsing` — fixture date `03/02/2026` parses to 3 Feb (not 2 Mar).
- [X] **T2-01-31** `test_phase2_orm.py::test_action_import_address_change_flag_passes_through` — order with `has_pending_address_change=True` gets tracking_number written + line flagged.
- [X] **T2-01-32** `test_phase2_orm.py::test_action_import_unmatched_state` — order_number with no match → line.state='unmatched'.
- [X] **T2-01-33** `test_phase2_orm.py::test_action_import_conflict_state` — duplicate channel_order_ref → line.state='conflict'.
- [X] **T2-01-34** `test_phase2_orm.py::test_action_import_records_sync_health` — `etsy.sync.health` gets `gke_tracking_import` event with counts.
- [X] **T2-01-35** `test_phase2_orm.py::test_action_import_blocks_oversize_file` — file_size > ICP threshold → ValidationError before parse.
- [X] **T2-01-36** `test_phase2_orm.py::test_order_resolution_fallback_to_etsy_order_id` — channel_order_ref miss + etsy_order_id hit → matched.

## Phase 3 — GREEN

- [X] **T2-01-37** Add 6 ACL rows to `security/ir.model.access.csv` (3 models × 2 BA groups; system inherits from base).
- [X] **T2-01-38** Author `security/tracking_import_security.xml` — declare `group_ba_shipping` + `group_ba_manager` (or reuse `group_ba_lead` from P1-04 if semantically equivalent — decide during implementation; document in findings.md).
- [X] **T2-01-39** Implement `models/tracking_import_log.py` per data-model.md §1 — 18 fields, 2 `@api.constrains`, `_sql_constraints`, `init()` raw-SQL composite index per drift template.
- [X] **T2-01-40** Implement `models/tracking_import_line.py` per data-model.md §2 — 17 fields, 2 `@api.constrains`, `_sql_constraints` UNIQUE, `init()` raw SQL.
- [X] **T2-01-41** Implement `services/gke_excel_parser.py` — pure function `parse(file_bytes) -> ParseResult` namedtuple `(header_hash, headers, rows)`. Uses `openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True, keep_links=False)`.
- [X] **T2-01-42** Implement `services/tracking_importer.py` — orchestrator class `TrackingImporter`. Methods: `compute_source_row_hash`, `resolve_order` (bulk-fetch via `search([('channel_order_ref', 'in', refs)])`), `apply_to_fulfillment` (per-row savepoint).
- [X] **T2-01-43** Implement `wizards/tracking_import_wizard.py` — TransientModel + 4 actions. Each action method calls `_check_*_or_raise()` helper.
- [X] **T2-01-44** Author `views/tracking_import_views.xml` — log list + form (with chatter), line list (embedded in log form), wizard form (3 stages: upload → preview → import). Use `markupsafe.Markup`/`escape` for any operator-supplied text in chatter.
- [X] **T2-01-45** Author `views/menu_views.xml` — Operations → Tracking → Import GKE Excel menu item; group `group_ba_shipping`.
- [X] **T2-01-46** Add `ir.sequence` `tracking.import.log.seq` in `data/tracking_import_data.xml` (prefix `GKE-`, padding 6).
- [X] **T2-01-47** Update `__manifest__.py` — register new data files, bump version to `19.0.1.0.4`. Add `openpyxl` to `external_dependencies.python`.
- [X] **T2-01-48** Add migration `migrations/19.0.1.0.4/post-init-icps.py` — initialize `gke_schema_hashes` ICP to `'[]'` if not set.

## Phase 4 — Review (parallel: code-reviewer + security-reviewer)

- [X] **T2-01-49** Code-reviewer: scan for N+1 in `resolve_order` (must be bulk), savepoint scope, `_logger.info` violations, function length ≤50 LOC.
- [X] **T2-01-50** Security-reviewer: BA-manager RPC gate on `action_approve_schema`; file-upload size enforcement before parse; openpyxl `read_only`/`keep_links=False` flags; ICP writes scoped to action only; `sudo()` on `etsy.sync.health` write commented; `markupsafe.Markup` on operator strings in chatter.
- [X] **T2-01-51** Resolve all CRITICAL/HIGH inline; document acceptable trade-offs in commit body.

## Phase 5 — Verify

- [X] **T2-01-52** `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_fulfillment --stop-after-init` exit 0.
- [X] **T2-01-53** Test tags: `--test-tags /multichannel_hub_fulfillment` exit 0.
- [X] **T2-01-54** Full regression: `--test-tags /multichannel_hub_core,/multichannel_hub_fulfillment,/etsy_integration` exit 0.
- [X] **T2-01-55** `ruff check custom_addons/multichannel_hub_fulfillment/` exit 0.
- [X] **T2-01-56** `grep -rn "_logger.info\|print(" custom_addons/multichannel_hub_fulfillment/ models/ wizards/ services/` returns empty.

## Phase 6 — Commit

- [X] **T2-01-57** Commit RED phase: `[multichannel_hub_fulfillment] test(P2-01): RED tracking.import.log + line + wizard tests` citing T2-01-01..T2-01-36.
- [X] **T2-01-58** Commit GREEN phase: `[multichannel_hub_fulfillment] feat(P2-01): GREEN GKE Excel import wizard with schema fingerprint` citing T2-01-37..T2-01-48.
- [X] **T2-01-59** Commit security fixes (if any) inline before main commit per playbook.

## Phase 7 — Document

- [X] **T2-01-60** Mark all T2-01-* `[X]` in this file.
- [X] **T2-01-61** Tracker change-log row: `2026-04-XX: P2-01 GREEN landed on feature/006-master-plan-coding ...`.
- [X] **T2-01-62** Tracker P2-01 row → `state=done` with commit hash + counts.
- [X] **T2-01-63** Author `specs/004a-tracking-import/findings.md` capturing: Odoo 19 surprises, openpyxl gotchas, BA-group decision (new vs reuse `group_ba_lead`).

## Phase 8 — Learn

- [X] **T2-01-64** `/learn` to capture: openpyxl read-only patterns, dayfirst gotcha, schema-fingerprint pattern (reusable for any Excel import), composite-hash idempotency template, file-upload size cap reuse pattern.

---

## Deferred to sibling slices (NOT P2-01 scope)

| Task | Slice |
|---|---|
| Carrier auto-detection service | P2-02 |
| Stock-move hook on transition to "Đã sản xuất" | P2-03 |
| Import-log replay UI + bulk re-detect | P2-04 |
| `shipping.carrier` admin UX + extended seed | P2-05 |
| GDrive polling cron + `logistics.partner` model | P2-06 |
| Excel export from Tracking Dashboard (T036 from P1-03) | P2-01 explicitly OWNS export-import schema symmetry; export logic itself stays deferred |
| Vietnamese `.po` translation | P1-07 |
| `tracking.import.log` audit-tab AC across changes | P1-08 |

---

# Tasks — Spec 004a Slice P2-02

**Slice**: P2-02 Carrier auto-detection (US2)
**Module**: `multichannel_hub_fulfillment` (+ shipping.carrier seed extension in mhc)
**Branch**: `feature/006-master-plan-coding`

## Phase 2 — RED

- [X] **T2-02-01** Test fixture: tracking-number samples per carrier (USPS 22-digit, UniUni `UUS...`, YunExpress `YT...`, unknown).
- [X] **T2-02-02** `test_phase1_db.py::test_shipping_carrier_other_seed_exists` — assert carrier with `code='other'` is seeded.
- [X] **T2-02-03** `test_phase1_db.py::test_tracking_import_line_needs_review_column` — column exists.
- [X] **T2-02-04** `test_phase2_orm.py::test_detector_matches_usps_prefix`.
- [X] **T2-02-05** `test_phase2_orm.py::test_detector_matches_uniuni_prefix`.
- [X] **T2-02-06** `test_phase2_orm.py::test_detector_matches_yunexpress_prefix`.
- [X] **T2-02-07** `test_phase2_orm.py::test_detector_falls_back_to_other_on_unknown` — unknown → carrier `other` + `needs_review=True`.
- [X] **T2-02-08** `test_phase2_orm.py::test_detector_handles_empty_tracking_number` — None/empty → False + needs_review.
- [X] **T2-02-09** `test_phase2_orm.py::test_detector_skips_inactive_carriers`.
- [X] **T2-02-10** `test_phase2_orm.py::test_detector_sequence_priority_on_overlap` — multiple matches → highest-priority (lowest sequence) wins.
- [X] **T2-02-11** `test_phase2_orm.py::test_wizard_preview_populates_detected_carrier_id` — preview hook fills field.
- [X] **T2-02-12** `test_phase2_orm.py::test_bulk_redetect_action_updates_lines` — re-detect action updates line carriers.
- [X] **T2-02-13** `test_phase2_orm.py::test_bulk_redetect_gated_to_ba_shipping` — non-BA → AccessError.
- [X] **T2-02-14** `test_phase2_orm.py::test_bulk_redetect_does_not_overwrite_order_carrier` — order's existing carrier untouched.
- [X] **T2-02-15** `test_phase2_orm.py::test_carrier_regex_constraint_rejects_dangerous_pattern` — regex matching empty string raises ValidationError.

## Phase 3 — GREEN

- [X] **T2-02-16** Add `code='other'` carrier seed in `shipping_carrier_data.xml` (sequence=999, low priority fallback).
- [X] **T2-02-17** `services/carrier_detector.py` — pure-function `detect_carrier(env, tracking_number)`; cached compiled regexes via lru_cache; `re.match()` (anchored).
- [X] **T2-02-18** Add `needs_review` Boolean field on `tracking.import.line` (default False).
- [X] **T2-02-19** `@api.constrains('tracking_prefix_regex')` on `shipping.carrier` — reject patterns that match empty string.
- [X] **T2-02-20** Wire detector into `tracking_import_wizard.action_preview()` after `resolve_orders()`.
- [X] **T2-02-21** Add `action_re_detect_carriers()` on `tracking.import.line` with `_check_ba_shipping_or_raise()` gate.
- [X] **T2-02-22** Server action + button in views: list-view bulk action calls `action_re_detect_carriers()`.

## Phase 4-8 — Review/Verify/Commit/Document/Learn (orchestrator inline; no separate task IDs).

---

# Tasks — Spec 004a Slice P2-03

**Slice**: P2-03 Process Dashboard "Đã sản xuất" stock-move hook (US3, FR-016..FR-020)
**Module**: `multichannel_hub_fulfillment` (extension of `sale.order.fulfillment` mixin from `multichannel_hub_core`; new `stock.move` field in mhf)
**Branch**: `feature/006-master-plan-coding`
**Spec drift note**: see `findings.md` P2-03 entry — code uses `fulfillment_status='produced'` (not `production_stage='da_san_xuat'`), `warehouse_zone` Selection (not `warehouse_id` M2O), final states `shipped`/`delivered`/`cancelled` (not `shipped`/`done`/`cancel`).

## Phase 2 — RED (tdd-guide agent)

### Phase 1 — DB schema tests
- [X] **T2-03-01** `test_phase1_db.py::test_stock_move_purpose_column_exists` — query `information_schema.columns` for `stock_move.purpose` (Char/Varchar).
- [X] **T2-03-02** `test_phase1_db.py::test_stock_move_purpose_unique_constraint` — query `pg_constraint` for `stock_move_order_purpose_uniq` UNIQUE on `(sale_order_id_or_origin_ref, purpose)` (exact column name TBD by Phase 3 design — confirm during GREEN; test asserts the constraint exists by name).
- [X] **T2-03-03** `test_phase1_db.py::test_production_locations_icp_optional` — ICP `multichannel_hub_fulfillment.production_locations` may be empty after install (fail-open path); presence is not required.

### Phase 2 — ORM behavior tests
- [X] **T2-03-04** `test_phase2_orm.py::test_hook_fires_on_transition_to_produced` — write `fulfillment_status='produced'` from `'in_progress'`; assert exactly one `stock.move` exists with `purpose='production_completion'` linked to the order.
- [X] **T2-03-05** `test_phase2_orm.py::test_hook_idempotent_on_repeat_write` — call `write({'fulfillment_status': 'produced'})` a second time on a record already at `'produced'`; assert no duplicate move (still exactly one).
- [X] **T2-03-06** `test_phase2_orm.py::test_hook_idempotent_via_savepoint_rollback` — simulate concurrent transition (two records, manual `psycopg2.IntegrityError` re-raise path); assert second create is caught, no UserError leaks.
- [X] **T2-03-07** `test_phase2_orm.py::test_hook_resolves_locations_from_warehouse_zone_vn` — set ICP map for `vn` zone; assert move's `location_id` + `location_dest_id` resolve to mapped xmlids.
- [X] **T2-03-08** `test_phase2_orm.py::test_hook_resolves_locations_from_warehouse_zone_us` — same for `us` zone.
- [X] **T2-03-09** `test_phase2_orm.py::test_hook_fail_open_on_missing_icp` — empty ICP; transition succeeds (no UserError); `fulfillment_status` does become `'produced'`; sync.health record `name='production_completion'`, `kind='warning'`, message names the missing zone; **no** stock.move created.
- [X] **T2-03-10** `test_phase2_orm.py::test_hook_fail_open_on_unresolved_xmlid` — ICP has zone but xmlid points at deleted/missing record; same fail-open behavior as T2-03-09.
- [X] **T2-03-11** `test_phase2_orm.py::test_hook_qty_from_storable_lines` — order with 3 storable lines (qty 2, 5, 1) and 1 service line; assert move quantity = 8 (sum of storable only).
- [X] **T2-03-12** `test_phase2_orm.py::test_hook_skips_zero_storable_lines` — order with all-service lines; transition succeeds; sync.health logs info `'No stock move: no storable products on order X'`; no move created; `fulfillment_status` does become `'produced'`.
- [X] **T2-03-13** `test_phase2_orm.py::test_hook_blocks_final_state_transition` — order at `'shipped'`; attempt `write({'fulfillment_status': 'produced'})`; raises `UserError` per FR-020.
- [X] **T2-03-14** `test_phase2_orm.py::test_hook_blocks_delivered_state` — same for `'delivered'`.
- [X] **T2-03-15** `test_phase2_orm.py::test_hook_blocks_cancelled_state` — same for `'cancelled'`.
- [X] **T2-03-16** `test_phase2_orm.py::test_hook_no_move_on_non_produced_transition` — `pending → in_progress`; assert zero stock.moves with `purpose='production_completion'` for the order.
- [X] **T2-03-17** `test_phase2_orm.py::test_hook_records_sync_health_on_success` — successful transition → `etsy.sync.health` event `kind='production_completion'` with `ok=1`.
- [X] **T2-03-18** `test_phase2_orm.py::test_hook_respects_address_change_lock` — order with `has_pending_address_change=True`; `fulfillment_status` is NOT in `_ADDRESS_LOCK_FIELDS` (verify); transition still works (FR-017 governs ship-fields, not production stage). If verification reveals `fulfillment_status` IS in lock-fields, then test the inverse: transition is blocked. Document outcome in findings.md.

## Phase 3 — GREEN

- [X] **T2-03-19** Add `purpose` Char field to `stock.move` via new file `models/stock_move.py` in `multichannel_hub_fulfillment`. Field is indexed; `_sql_constraints` declares `(stock_move_order_purpose_uniq, UNIQUE(<order-link-column>, purpose))`. Use the actual stock.move column that links to the order — `sale_line_id` chains to `sale.order.line.order_id`; OR add a direct `sale_order_id` Many2one on stock.move (cleaner — recommend this). Document choice in commit body.
- [X] **T2-03-20** Mirror the UNIQUE constraint via `init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check (drift template per memory `project_sql_constraints_drift.md` — 7th use). Add inline comment citing why (sql_constraints not deployed across multi-addon installs).
- [X] **T2-03-21** Implement hook method `_action_complete_production()` on `sale.order.fulfillment` (extension file in `multichannel_hub_fulfillment/models/sale_order_fulfillment.py` — new file or extend if exists). Method: resolves `(src, dst)` xmlids from ICP `multichannel_hub_fulfillment.production_locations` keyed by `self.warehouse_zone`; computes qty from `self.order_id.order_line.filtered(lambda l: l.product_id.type in ('product', 'consu'))`; creates one `stock.move` with `purpose='production_completion'` and `sale_order_id=self.order_id.id`; catches `psycopg2.IntegrityError` for race-idempotency; catches `ValueError`/missing-xmlid for fail-open; writes to `etsy.sync.health` via the optional-discovery pattern (mirror `services/tracking_importer.py:198 record_sync_health`).
- [X] **T2-03-22** Override `write()` on the fulfillment extension to detect `fulfillment_status` transition from non-final state to `'produced'` and call `_action_complete_production()`. Block writes from final states (`'shipped'`/`'delivered'`/`'cancelled'`) → `'produced'` with `UserError`. Detection must batch-aware (handle `len(self) > 1` correctly).
- [X] **T2-03-23** Add ICP default in `data/production_locations_data.xml` (or migration script) — set `multichannel_hub_fulfillment.production_locations` to `'{}'` on install. Operator populates per warehouse via Settings.
- [X] **T2-03-24** Add migration `migrations/19.0.1.0.X/post-init-production-icp.py` initializing the ICP if not set.
- [X] **T2-03-25** Update `__manifest__.py` — register `models/stock_move.py` import + new data file; bump version. Add `stock` to `depends` if not already present.
- [X] **T2-03-26** Add `etsy.sync.health` `kind='production_completion'` to the value list (if model uses Selection on `kind`) — coordinate with etsy_integration. If `kind` is free-text Char, no change needed.
- [X] **T2-03-27** Vietnamese strings: any new user-visible message (UserError, sync.health labels) declared in `_(…)` for i18n.

## Phase 4 — Review (parallel: code-reviewer + security-reviewer)

- [X] **T2-03-28** Code-reviewer focus: N+1 in qty calc loop, idempotency race-condition correctness (`IntegrityError` catch scope), savepoint discipline around the `create()`, no `_logger.info` for routine events, function length ≤50 LOC, batch-aware `write()` override.
- [X] **T2-03-29** Security-reviewer focus: fail-open path doesn't swallow real DB errors (only `IntegrityError` on the unique constraint + missing-xmlid `ValueError`); `sudo()` on cross-module sync.health write is commented; `UserError` message doesn't leak internal record IDs; no raw SQL in hook (only in `init()` mirror with rationale).
- [X] **T2-03-30** Resolve all CRITICAL/HIGH inline; document trade-offs in commit body.

## Phase 5 — Verify

- [X] **T2-03-31** `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_fulfillment --stop-after-init` exit 0.
- [X] **T2-03-32** `--test-tags /multichannel_hub_fulfillment` exit 0.
- [X] **T2-03-33** Full regression: `--test-tags /multichannel_hub_core,/multichannel_hub_fulfillment,/etsy_integration` exit 0.
- [X] **T2-03-34** `ruff check custom_addons/multichannel_hub_fulfillment/` exit 0.
- [X] **T2-03-35** `grep -rn "_logger.info\|print(" custom_addons/multichannel_hub_fulfillment/models/ custom_addons/multichannel_hub_fulfillment/services/` returns empty.

## Phase 6 — Commit

- [X] **T2-03-36** RED commit: `[multichannel_hub_fulfillment] test(P2-03): RED stock-move hook on production transition` citing T2-03-01..T2-03-18.
- [X] **T2-03-37** GREEN commit: `[multichannel_hub_fulfillment] feat(P2-03): GREEN production stock-move hook with idempotency + fail-open` citing T2-03-19..T2-03-27.

## Phase 7 — Document

- [X] **T2-03-38** Mark all T2-03-* `[X]` in this file.
- [X] **T2-03-39** Tracker change-log: `2026-05-XX: P2-03 GREEN landed on feature/006-master-plan-coding ...`.
- [X] **T2-03-40** Tracker P2-03 row → `state=done` with commit hashes + counts.
- [X] **T2-03-41** Update `findings.md` with: Odoo 19 stock.move auto-confirm behavior outcome, address-change-lock interaction with `fulfillment_status`, any race-condition surprises observed during tests.

## Phase 8 — Learn

- [X] **T2-03-42** `/learn` to capture: stock.move purpose-based idempotency template, fail-open ICP-resolution pattern, race-condition handling via `IntegrityError` catch, batch-aware `write()` override for stage transitions.

---

# Tasks — Spec 004a Slice P2-04

**Slice**: P2-04 Tracking import log visibility + replay (US4)
**Module**: `multichannel_hub_fulfillment`
**Branch**: `feature/006-master-plan-coding`
**Plan archive**: [_archive/p2-04-plan.md](_archive/p2-04-plan.md)

Depends on: P2-01 ✓, P2-02 ✓

## Phase 2 — RED (tdd-guide agent)

### Phase 1 — DB schema/view tests (`tests/test_phase1_db.py` — append)

- [X] **T2-04-01** `test_tracking_import_log_schema_hash_visible` — assert list view XML has no `optional="hide"` on `schema_hash`.
- [X] **T2-04-02** `test_smart_button_action_exists` — assert today-filter `ir.actions.act_window` registered for `tracking.import.log`.
- [X] **T2-04-03** `test_tracking_import_line_action_replay_line_exists` — assert `action_replay_line` method on `tracking.import.line`.
- [X] **T2-04-04** `test_tracking_import_line_action_resolve_conflict_exists` — assert `action_resolve_conflict` method on `tracking.import.line`.
- [X] **T2-04-05** `test_tracking_import_log_recount_summary_exists` — assert `_recount_summary` method on `tracking.import.log`.

### Phase 2 — ORM behavior tests (`tests/test_phase2_orm_p2_04.py` — new file)

- [X] **T2-04-06** `test_action_replay_line_reruns_resolve_orders` — error line for an order_number that becomes valid after fix; replay; assert state transitions to `matched` with `sale_order_id` set.
- [X] **T2-04-07** `test_action_replay_line_reruns_carrier_detection` — matched line; replay; assert `applied_carrier_id` populated via P2-02 detector.
- [X] **T2-04-08** `test_action_replay_line_reruns_fulfillment_write` — error line; underlying issue resolved; replay; assert `tracking_number` written on fulfillment + line state `imported`.
- [X] **T2-04-09** `test_action_replay_line_savepoint_rollback_on_error` — replay where fulfillment write raises `ValidationError`; assert state remains `error`, no partial writes.
- [X] **T2-04-10** `test_action_replay_line_updates_parent_summary` — log with 3 lines (1 matched, 1 unmatched, 1 error); replay error line successfully; assert parent counts recomputed (`error_count -1`, `imported_count +1`).
- [X] **T2-04-11** `test_conflict_line_operator_selects_candidate_order` — conflict line with 2 candidates; call `action_resolve_conflict(selected_order_id)`; assert `sale_order_id` set, state `matched`, parent log chatter has audit message.
- [X] **T2-04-12** `test_action_replay_line_gated_to_ba_shipping` — non-BA user calls; assert `AccessError` raised (FR-017 13th confirmation).
- [X] **T2-04-13** `test_action_resolve_conflict_gated_to_ba_shipping` — non-BA user calls; assert `AccessError`.
- [X] **T2-04-14** `test_action_resolve_conflict_rejects_non_conflict_state` — line with `state='matched'`; call resolve; assert `ValidationError`.
- [X] **T2-04-15** `test_smart_button_action_filters_by_today` — call `action_view_today_imports` from log; assert returned domain includes `('create_date', '>=', today)`.
- [X] **T2-04-16** `test_replay_idempotent_on_duplicate_call` — replay imported line twice; assert no duplicate stock.move (UNIQUE purpose marker holds from P2-03).

## Phase 3 — GREEN

- [X] **T2-04-17** `views/tracking_import_views.xml` — remove `optional="hide"` on `schema_hash` field in list view.
- [X] **T2-04-18** `views/tracking_import_views.xml` — add inline `Re-process` button on `line_ids` one2many embedded list, invisible when `state == 'imported'`.
- [X] **T2-04-19** `views/tracking_import_views.xml` — add candidate-domain on `sale_order_id` widget for conflict lines: `domain="[('channel_order_ref', '=', raw_order_number)]"` when `state == 'conflict'`.
- [X] **T2-04-20** `views/tracking_import_views.xml` — add `oe_stat_button` linking to `action_view_today_imports` on log form.
- [X] **T2-04-21** `models/tracking_import_line.py` — implement `action_replay_line()` (FR-017 gate, savepoint per record, calls `tracking_importer.resolve_orders` → `carrier_detector.detect_carrier` → `apply_to_fulfillment`, on success calls `log._recount_summary()`).
- [X] **T2-04-22** `models/tracking_import_line.py` — implement `action_resolve_conflict(selected_order_id)` (FR-017 gate, ensure_one, candidate validation, write `sale_order_id` + state, post audit message to parent log chatter).
- [X] **T2-04-23** `models/tracking_import_log.py` — implement `_recount_summary()` using `read_group` on child line states.
- [X] **T2-04-24** `models/tracking_import_log.py` — implement `action_view_today_imports()` returning `ir.actions.act_window` with Python-computed today domain (avoids XML `timedelta` serialization).
- [X] **T2-04-25** `views/etsy_sync_health_smartbutton.xml` — new file extending `etsy.sync.health` form with conditional smart-button (`invisible="name != 'gke_tracking_import'"`).
- [X] **T2-04-26** Add Python helper `etsy.sync.health.action_view_gke_today` (in mhf `models/etsy_sync_health.py` extension or as `_inherit`) returning the same `act_window`. Verify dependency chain (mhf → etsy_integration must be transitive via mhc; if not, use `getattr` probe per `feedback_odoo19_test_gotchas.md`).
- [X] **T2-04-27** `__manifest__.py` — bump version `19.0.1.0.14` → `19.0.1.0.15`; register `views/etsy_sync_health_smartbutton.xml`.

## Phase 4 — Review (parallel: code-reviewer + security-reviewer)

- [X] **T2-04-28** Code-reviewer: function length ≤50 LOC, savepoint scope correctness, `read_group` perf, no N+1 in bulk replay loop, no premature abstractions.
- [X] **T2-04-29** Security-reviewer: FR-017 gate present on both action methods, chatter message escaped/safe (use `markupsafe.escape` if injecting raw user input), no `sudo()` without inline rationale, no raw SQL.
- [X] **T2-04-30** Resolve all CRITICAL/HIGH inline; document trade-offs in commit body.

## Phase 5 — Verify

- [X] **T2-04-31** `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_fulfillment --stop-after-init` exit 0.
- [X] **T2-04-32** `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_fulfillment --stop-after-init` exit 0.
- [X] **T2-04-33** Cross-module regression: `--test-tags /multichannel_hub_core,/multichannel_hub_fulfillment,/etsy_integration` exit 0.
- [X] **T2-04-34** `ruff check custom_addons/multichannel_hub_fulfillment/` exit 0 (if available).
- [X] **T2-04-35** `grep -rn "_logger.info\|print(" custom_addons/multichannel_hub_fulfillment/{models,views,services} ` returns no debugging artifacts.

## Phase 6 — Commit

- [X] **T2-04-36** RED commit: `[multichannel_hub_fulfillment] test(P2-04): RED replay + conflict resolver tests` citing T2-04-01..T2-04-16.
- [X] **T2-04-37** GREEN commit: `[multichannel_hub_fulfillment] feat(P2-04): GREEN tracking-import log visibility + per-line replay + conflict resolver` citing T2-04-17..T2-04-27.

## Phase 7 — Document

- [X] **T2-04-38** Mark all T2-04-* `[X]` in this file.
- [X] **T2-04-39** Tracker change-log entry for 2026-05-XX P2-04 landing.
- [X] **T2-04-40** Tracker P2-04 row → `state=done` with commit hashes.
- [X] **T2-04-41** Update `findings.md` with: conflict-chatter location decision (parent log), replay idempotency notes, FR-017 13th confirmation, smart-button layering decision.

## Phase 8 — Learn

- [X] **T2-04-42** `/learn` to capture: per-line replay savepoint pattern (reusable for other row-level undo flows), `_recount_summary` via `read_group`, smart-button Python-domain pattern (avoids XML timedelta), chatter audit on parent when child has no `mail.thread`.

---

# Tasks — Spec 004a Slice P2-05

**Slice**: P2-05 Spec 004a US5 `shipping.carrier` admin UX + extended seed
**Module**: `multichannel_hub_core` (model + ACL + view + seed XML); `multichannel_hub_fulfillment` only for detector regression coverage
**Branch**: `feature/006-master-plan-coding`
**Plan**: `specs/004a-tracking-import/_archive/p2-05-plan.md`

## Phase 2 — RED (tdd-guide agent)

### Phase 1 — DB / static-asset checks (`tests/test_phase1_shipping_carrier_p2_05.py`)
- [ ] **T2-05-01** `test_seed_xml_is_noupdate_one` — read `multichannel_hub_core/data/shipping_carrier_data.xml` (raw file via `tools` import), assert root `<odoo>` element has `noupdate="1"`.
- [ ] **T2-05-02** `test_acl_csv_has_system_row_for_shipping_carrier` — read `security/ir.model.access.csv`, assert a row matches `(model_id=model_shipping_carrier, group_id=base.group_system, perm_read=1, perm_write=1, perm_create=1, perm_unlink=1)`.
- [ ] **T2-05-03** `test_acl_csv_manager_row_is_read_only` — same file: assert the `sales_team.group_sale_manager` row for `model_shipping_carrier` has `perm_read=1, perm_write=0, perm_create=0, perm_unlink=0`.

### Phase 2 — ORM behavior (`tests/test_phase2_shipping_carrier_p2_05.py`)
- [ ] **T2-05-04** `test_create_requires_at_least_regex_or_etsy` — create with both `tracking_prefix_regex=False` and `etsy_carrier_name=False` raises `ValidationError` mentioning "at least one".
- [ ] **T2-05-05** `test_create_accepts_regex_only` — create with regex set + `etsy_carrier_name=False` succeeds.
- [ ] **T2-05-06** `test_create_accepts_etsy_only` — create with `etsy_carrier_name='other'` + no regex succeeds.
- [ ] **T2-05-07** `test_write_to_clear_both_mappings_raises` — existing carrier; `write({'tracking_prefix_regex': False, 'etsy_carrier_name': False})` raises `ValidationError`.
- [ ] **T2-05-08** `test_create_blocked_for_non_system_user` — sales-manager user (no `group_system`) attempting `create({...})` raises `AccessError` (canonical `assertRaises(AccessError)` per memory).
- [ ] **T2-05-09** `test_write_blocked_for_non_system_user` — sales-manager user `write({'name': 'X'})` raises `AccessError`.
- [ ] **T2-05-10** `test_unlink_blocked_for_non_system_user` — sales-manager user `unlink()` raises `AccessError`.
- [ ] **T2-05-11** `test_create_succeeds_for_system_user` — admin user (default `group_system`) creates carrier with regex, succeeds.
- [ ] **T2-05-12** `test_write_succeeds_for_system_user` — admin user `write({'name': 'USPS Priority'})` on existing seed row succeeds.
- [ ] **T2-05-13** `test_inactive_carrier_skipped_by_detector` — create carrier with prefix `^ZZZ`, set `is_active=False`, call `carrier_detector.detect_carrier(env, 'ZZZ123456')` → returns fallback `'other'` not the inactive row. (mhf test file).
- [ ] **T2-05-14** `test_inactive_carrier_name_still_renders` — fulfillment record references inactive carrier; `fulfillment.shipping_carrier_id.name` reads correctly (no blanking on `is_active=False`).
- [ ] **T2-05-15** `test_at_least_one_constraint_runs_after_regex_safe` — empty regex `''` + no etsy_name should surface AS1 error (not regex-safe error). Establishes constraint-ordering contract for review.

## Phase 3 — GREEN

- [ ] **T2-05-16** Add `_check_at_least_one_mapping()` `@api.constrains('tracking_prefix_regex', 'etsy_carrier_name')` to `models/shipping_carrier.py` (per plan §"Phase 3 GREEN Skeleton").
- [ ] **T2-05-17** Add `_check_group_system_or_raise()` helper + `create()` (model_create_multi) / `write()` / `unlink()` overrides on `models/shipping_carrier.py`. Inline docstring cites FR-017 14th confirmation.
- [ ] **T2-05-18** Update `security/ir.model.access.csv`: downgrade `access_shipping_carrier_manager` to `1,0,0,0`; add `access_shipping_carrier_system` row for `base.group_system` `1,1,1,1`.
- [ ] **T2-05-19** Flip `data/shipping_carrier_data.xml` line 2: `noupdate="0"` → `noupdate="1"`.
- [ ] **T2-05-20** Bump `__manifest__.py` version (e.g., `19.0.1.0.16` → `19.0.1.0.17`).

## Phase 4 — Review (parallel)

- [ ] **T2-05-21** `code-reviewer` agent: constraint ordering, naming, helper-function placement, defense-in-depth justification, no `_logger.info`, function length ≤50 LOC.
- [ ] **T2-05-22** `security-reviewer` agent: ACL tightening blast radius (existing tests / runtime users), `sudo()` not used in P2-05 path (gate must run in user context), `AccessError` wording (no internal-id leakage), confirms CSV diff is correct.

## Phase 5 — Verify

- [ ] **T2-05-23** `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` exit 0.
- [ ] **T2-05-24** `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core,/multichannel_hub_fulfillment --stop-after-init` exit 0 (P2-05 + cross-module regression).
- [ ] **T2-05-25** `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init` exit 0 (no etsy regression).
- [ ] **T2-05-26** `ruff check custom_addons/multichannel_hub_core/` exit 0 (if available).
- [ ] **T2-05-27** `grep -rn "_logger.info\|print(" custom_addons/multichannel_hub_core/{models,views,services}` returns no debugging artifacts.

## Phase 6 — Commit

- [ ] **T2-05-28** RED commit: `[multichannel_hub_core] test(P2-05): RED carrier admin UX + ACL + seed-noupdate tests` citing T2-05-01..T2-05-15.
- [ ] **T2-05-29** GREEN commit: `[multichannel_hub_core] feat(P2-05): GREEN carrier at-least-one constraint + system-only write gate + noupdate seed` citing T2-05-16..T2-05-20.

## Phase 7 — Document

- [ ] **T2-05-30** Mark all T2-05-* `[X]` in this file.
- [ ] **T2-05-31** Tracker change-log entry for 2026-05-09 P2-05 landing.
- [ ] **T2-05-32** Tracker P2-05 row → `state=done` with commit hashes + test counts.
- [ ] **T2-05-33** Update `findings.md`: noupdate flip rationale (one-way migration), constraint-ordering finding, FR-017 14th confirmation, ACL-tightening blast radius (which tests touched).

## Phase 8 — Learn

- [ ] **T2-05-34** `/learn` to capture: at-least-one-of constrains template (reusable for any "at least one mapping required" model), system-only write/create/unlink gate as canonical pattern for master-data models, `noupdate` flip semantics + when admin-edit-preservation matters.

