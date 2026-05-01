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
