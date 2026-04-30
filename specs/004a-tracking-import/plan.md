# Implementation Plan — Spec 004a (Slice P2-01: US1)

**Slice**: P2-01 — GKE Excel import wizard with schema fingerprinting
**Branch**: `feature/006-master-plan-coding`
**Module home**: `multichannel_hub_fulfillment` (per ADR-003)
**Authority**: spec.md §US1 + ADR-001/003/005/006§6/007 + tracker §"Active prioritization" 2026-04-27
**Authored**: 2026-04-30 (planner Opus, dispatched via /dispatch-slice next)

---

## Slice scope

US1 only. US2 (carrier auto-detect) → P2-02. US3 (stock-move hook) → P2-03. US4 (import-log replay) → P2-04. US5 (carrier admin UX) → P2-05. US6 (GDrive polling) → P2-06.

Out of scope but data model anticipates:
- `tracking.import.line.detected_carrier_id` Many2one — populated by P2-02 service, declared here.
- `tracking.import.line.state` enum — extends in P2-03 for stock-move hook.
- `tracking.import.log.source` Selection (`manual` / `gdrive`) + `source_gdrive_file_id` Char — populated by P2-06 poller, declared here so P2-06 needs no schema migration.

---

## Phased plan

### Phase 0 — Dispatch (done)

Owner DM `dispatch next` 2026-04-30 → /dispatch-slice escalated formal "Phase 1 exit" dep contradiction → owner picked option A (override dep, planner authors missing artifacts) → planner Opus produced this plan + data-model.md + tasks.md.

### Phase 1 — Plan (this document + data-model.md + tasks.md)

Locked decisions (see also `## Locked decisions` below). Tactical plan for downstream phases.

### Phase 2 — RED (tdd-guide agent, Sonnet)

Write failing tests in `custom_addons/multichannel_hub_fulfillment/tests/`:
- `test_phase1_db.py` — Phase 1 DB verification (table existence, columns, indexes, constraints, ACLs).
- `test_phase2_orm.py` — Phase 2 ORM (CRUD, wizard flow, schema-hash branches, idempotency, savepoint, conflict resolution, sync.health hook).

Test fixtures under `tests/fixtures/`:
- `gke_known_schema.xlsx` — golden file with 50 rows including DD/MM/YYYY date with `day <= 12`.
- `gke_unknown_schema.xlsx` — header order mutated to trigger new-hash branch.
- `gke_oversized.xlsx` — > 10 MB to trigger size cap.
- `gke_partial_match.xlsx` — mix of matched / unmatched / conflict rows.

Confirm fail-for-right-reason before GREEN.

### Phase 3 — GREEN (developer-session)

Implementation files (paths absolute from repo root):
- `custom_addons/multichannel_hub_fulfillment/models/__init__.py` — register new modules.
- `custom_addons/multichannel_hub_fulfillment/models/tracking_import_log.py` — persistent log Model.
- `custom_addons/multichannel_hub_fulfillment/models/tracking_import_line.py` — persistent per-row Model.
- `custom_addons/multichannel_hub_fulfillment/wizards/__init__.py` — wizard registration.
- `custom_addons/multichannel_hub_fulfillment/wizards/tracking_import_wizard.py` — TransientModel.
- `custom_addons/multichannel_hub_fulfillment/services/__init__.py` — service registration.
- `custom_addons/multichannel_hub_fulfillment/services/gke_excel_parser.py` — pure function `parse(file_bytes) -> (header_hash, rows)`; no ORM. Uses `openpyxl` (read-only mode, `data_only=True`).
- `custom_addons/multichannel_hub_fulfillment/services/tracking_importer.py` — orchestrator; resolves orders, applies savepoint per row, writes log/line/fulfillment, calls sync.health hook. Carrier detection stub (no-op until P2-02).
- `custom_addons/multichannel_hub_fulfillment/views/tracking_import_views.xml` — log + line list/form/search; wizard form; `Approve new schema` button gated by `groups`.
- `custom_addons/multichannel_hub_fulfillment/views/menu_views.xml` — Operations → Tracking Import menu.
- `custom_addons/multichannel_hub_fulfillment/security/ir.model.access.csv` — append rows for log + line + wizard.
- `custom_addons/multichannel_hub_fulfillment/security/tracking_import_security.xml` — declare `group_ba_shipping` + `group_ba_manager` (or reuse existing if found during Phase 3 audit).
- `custom_addons/multichannel_hub_fulfillment/__manifest__.py` — register new data files.

Implementation rules (from CLAUDE.md + memory):
- All `_sql_constraints` UNIQUE mirrored in `init()` raw SQL via `pg_constraint IF NOT EXISTS` pre-check (drift template — 4th confirmation, canonical sample `multichannel_hub_core/models/design_file.py`).
- Action methods (`action_approve_schema`, `action_import`) gated by `_check_ba_manager_or_raise()` per FR-017 / `feedback_fr017_write_defense_in_depth`. RPC bypass is the default attack surface.
- `write()` override on `state` to mirror action gates (defense-in-depth).
- File-upload size cap: read `multichannel_hub.large_file_threshold_bytes` ICP (default 10 MB). Reject before openpyxl load.
- Date parsing: `dayfirst=True` via `dateutil.parser.parse(..., dayfirst=True)`. Test fixture must include date with `day <= 12`.
- `sudo()` on `etsy.sync.health` write — commented inline (cross-module, hub model owns audit).
- All user-visible strings wrapped in `_()`. Vietnamese translation in P1-07 polish slice.
- No `_logger.info`. Use `_logger.debug` or `_logger.warning`.

### Phase 4 — Review (parallel: code-reviewer + security-reviewer)

Single message, two `Agent` calls. Block on CRITICAL/HIGH.

Security focus areas:
- BA-manager group gate on `action_approve_schema` (RPC bypass).
- File-upload size cap enforced before openpyxl parse (DoS via zip-bomb XLSX).
- openpyxl `read_only=True` + `keep_links=False` (prevent external-link DoS).
- Schema-hash collision resistance — SHA-256 sufficient; document why MD5 rejected.
- `sale.order.fulfillment` write through delegation — no direct write on `sale.order`; respects `_ADDRESS_LOCK_FIELDS` (P1-03 defense-in-depth).
- `has_pending_address_change` flag respected — line marked but tracking still writes per spec §US1 AC5; documented exception to `_ADDRESS_LOCK_FIELDS`.
- ICP `gke_schema_hashes` write — only via `action_approve_schema`; never user-controllable.

Code-review focus:
- N+1 queries on order resolution (use `read_group` or `search([('channel_order_ref', 'in', refs)])`).
- Savepoint scope (per-row inside per-batch — playbook gotcha; verify).
- Idempotency hash collision handling (composite UNIQUE on `(log_id, source_row_hash)`).

### Phase 5 — Verify

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_fulfillment --stop-after-init
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_fulfillment --stop-after-init
ruff check custom_addons/multichannel_hub_fulfillment/
grep -rn "_logger.info\|print(" custom_addons/multichannel_hub_fulfillment/ | grep -v "_logger.info(_(" || echo OK
```

Exit code 0 on all four. Coverage ≥80% on changed lines.

### Phase 6 — Commit

One conventional commit citing T2-01-* IDs in body. Format:
```
[multichannel_hub_fulfillment] feat(P2-01): GREEN GKE Excel import wizard with schema fingerprint

Closes T2-01-01..T2-01-47 except deferred (T2-01-XX → P2-02).
...
```

### Phase 7 — Document

- `tracker.md` change-log row (this slice).
- `tracker.md` P2-01 row → `done` with commit hash.
- `tasks.md` mark all `[X]`.
- `findings.md` capture surprises (new file: `specs/004a-tracking-import/findings.md`).

### Phase 8 — Learn

`/learn` to capture: openpyxl read-only mode patterns, dayfirst parsing gotcha, schema fingerprint pattern (reusable for future Excel imports), composite-hash idempotency.

### Phase 9 — Land

No merge to `main` per memory `feedback_use_worktree_for_new_work.md` — accumulates on `feature/006-master-plan-coding` until W7 E2E sprint.

---

## Top risks

1. **openpyxl DoS via malformed XLSX (zip-bomb / nested formulas)** — Mitigation: 10 MB size cap pre-parse; `read_only=True`; `data_only=True`; `keep_links=False`; wrap parse in `try/except` returning `state='error'` with sanitized message.

2. **Schema-hash silent drift** — fixture mismatch in production after GKE supplier renames a column. Mitigation: hard-fail with diff display; BA-manager-only approval; persist all known headers with hashes in a sidecar field for forensic comparison.

3. **DD/MM/YYYY locale inversion** — `dateutil` default falls back to MM/DD when `day <= 12`. Mitigation: `dayfirst=True` explicit; fixture with `03/02/2026` → assert parses to 3 Feb.

4. **Order resolution N+1** — 500-row file × 1 query each = 500 queries. Mitigation: bulk `search([('channel_order_ref', 'in', list_of_refs)])` upfront, build dict, iterate in memory.

5. **Idempotency vs partial-update race** — re-run mid-import while previous run still active. Mitigation: composite UNIQUE on `(log_id, source_row_hash)` (PG-level); per-row savepoint catches `IntegrityError`; `state='conflict'` semantics.

6. **`has_pending_address_change` write gate** — P1-03's `_ADDRESS_LOCK_FIELDS` blocks tracking_number writes. Spec §US1 AC5 says tracking still writes but flagged in log. Mitigation: pass `approve_address_change=True` context only for the `tracking_number`/`shipping_date` write; do NOT bypass for `partner_shipping_id` (lock stays).

---

## Exit-criteria mapping

| Playbook exit criterion | Closing task |
|---|---|
| Every slice task `[X]` in tasks.md | T2-01-46 |
| Tests pass; coverage ≥80% | T2-01-41 + T2-01-42 |
| Module installs cleanly | T2-01-42 |
| ACLs defined | T2-01-37 |
| `sudo()` commented | T2-01-43 |
| Raw SQL commented | T2-01-44 |
| Tracker `state` updated | T2-01-46 |
| `/learn` captured | T2-01-47 |
| `findings.md` updated | T2-01-47 |

---

## Locked decisions

1. **Module home**: `multichannel_hub_fulfillment` (ADR-003).
2. **Schema fingerprint**: SHA-256 of `|`-joined normalized headers (uppercase + trim + case-fold). Persisted as JSON array in `ir.config_parameter` `multichannel_hub_fulfillment.gke_schema_hashes`.
3. **Idempotency**: composite UNIQUE `(log_id, source_row_hash)` where `source_row_hash = SHA-256("|".join(raw_cell_values_as_str))`.
4. **File-upload cap**: reuse `multichannel_hub.large_file_threshold_bytes` ICP (10 MB default). No new ICP key.
5. **Date parsing**: `dayfirst=True`. Fixture must include `day <= 12` ambiguous case.
6. **Order resolution**: primary `channel_order_ref` → fallback `etsy_order_id` → `state='unmatched'` if both miss.
7. **Carrier detection**: OUT OF SCOPE; `tracking.import.line.detected_carrier_id` field declared, populated as `False`. P2-02 service writes it.
8. **Stock-move hook**: OUT OF SCOPE; `tracking.import.line.state` enum includes `matched` / `unmatched` / `conflict` / `error` / `imported`. P2-03 extends.
9. **GDrive polling**: OUT OF SCOPE; `tracking.import.log.source` Selection (`manual`/`gdrive`) + `source_gdrive_file_id` declared, populated `manual` for now.
10. **Wizard model**: `TransientModel` (auto-vacuumed). Log + Line are persistent.
11. **mail.thread**: `tracking.import.log` inherits `mail.thread` (audit chatter). `tracking.import.line` does NOT (volume — could be 500+/import).
12. **Composite indexes**:
    - `tracking.import.log`: `(state, create_date DESC)` — Tracking Dashboard recent-imports query.
    - `tracking.import.line`: `(log_id, state)` — log-detail view; UNIQUE `(log_id, source_row_hash)` — idempotency.

---

## Deferred to developer-session

1. Existence audit of `group_ba_shipping` / `group_ba_manager` — search for existing groups before declaring new ones. If found, reuse XMLIDs in security.xml.
2. Vietnamese error-message wording — operator-supplied Markup-escaped (per P1-04 XSS lesson).
3. Whether to expose `Re-run` button on log form (T2-01-45 placeholder); decide based on tdd-guide test ergonomics.
4. Final list of GKE columns to capture verbatim on `tracking.import.line` — owner says ~10 cols; full list to be enumerated when fixture is built.

---

## Files modified outside this module

None expected. `sale.order.fulfillment` is consumed via existing fields (P1-05 + P1-03). `etsy.sync.health` is consumed via existing `_record_event` helper (W3.1).

If a write to `sale.order.fulfillment` reveals a missing field (e.g., `import_log_id` back-ref), declare it in this slice's data-model.md and add to `multichannel_hub_core` via a small extension commit.
