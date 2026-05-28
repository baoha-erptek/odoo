# Phase 1 Plan — Slice P1-LBL: `label_status` Selection → Many2one

**Slice**: P1-LBL — owner directive D2 (2026-05-10)
**Branch**: `feature/006-master-plan-coding` (clean at commit `d7eda792b60`)
**Planner agent**: Sonnet (in-spec, no new ADR)
**Saved by**: orchestrator inline (memory `feedback_planner_agent_no_write.md` — planner toolkit is Read/Grep/Glob only)

---

## Operative decisions (orchestrator)

These resolve the planner's open questions per memory `feedback_dispatch_run_to_completion.md` (pick recommended option, run end-to-end, log surprises in findings.md):

| Q | Decision | Rationale |
|---|---|---|
| Q1 (BLOCKING) seed codes match JPG | **CONFIRMED** — codes from `.0temp/2026-05-10_093634.jpg` are transcribed verbatim in T-LBL-03; tasks.md is the source of truth | Tracker row + JPG + tasks.md align |
| Q2 (BLOCKING) saved-filter rewrite at line 76 | **DEFER explicit code mapping** — rewrite to `('label_status_id', '!=', False)` (M2O Falsy = "unset", semantic match for legacy `'none'`) | Owner has not authored legacy→code mapping; P1-LBL-MIGRATE owns that |
| Q3 (NON-BLOCKING) BA-shipping read access | **YES, R-only for `base.group_user`** | Shipping ops needs visibility on dashboard |
| Q4 (NON-BLOCKING) `translate=True` on `name` | **YES** | Future-proofs for English rendering; no .po work this slice |

**Manifest version target**: `19.0.1.0.28` → **`19.0.1.0.29`** (current verified). Migration dir `19.0.1.0.29/` is clear.

**Xmlid collision check**: grep confirmed no existing `label_status_<code>` xmlids in any custom_addons module — clean to use `multichannel_hub_core.label_status_<code>` namespace for all 16 seed records.

---

## 1. Spec-drift check

**Current `label_status` Selection** (`multichannel_hub_core/models/sale_order_fulfillment.py:80-92`):

```python
label_status = fields.Selection(
    [('none','None'), ('requested','Requested'), ('buying','Buying'),
     ('bought','Bought'), ('failed','Failed')],
    string='Label Status', default='none', required=True, tracking=True,
)
```

**Tracker spec (P1-LBL row line 135) vs `tasks.md` Phase 4b**: aligned, all 14 tasks T-LBL-01 through T-LBL-14 specified.

**Affected files** confirmed by grep:
- Frozensets at `sale_order_fulfillment.py:12, 28` — both contain literal `'label_status'`
- Bus payload at line 229 — `'label_status': self.label_status or ''`
- Selection field at line 80
- Write defense at line 186 (`_ADDRESS_LOCK_FIELDS.intersection`)
- 5 test files with hardcoded literals (4 lit values: `none`, `requested`, `bought`, `failed`)
- 1 view file (`operations_dashboard_views.xml` lines 50-53, 76, 93-94)
- 1 saved-filter file (`operations_dashboard_saved_filters.xml:40`)

**No mismatch found.**

---

## 2. File list

### Models (NEW)
- `custom_addons/multichannel_hub_core/models/label_status_option.py` — full model file (~80 LOC). Inherit `mail.thread`. `init()` raw-SQL UNIQUE(code) drift mirror with `pg_constraint IF NOT EXISTS` pre-check (canonical: `design_file.py:134-148` — 9th confirmation).

### Models (MODIFIED in-place)
- `custom_addons/multichannel_hub_core/models/sale_order_fulfillment.py`:
  - Line 12: `'label_status'` → `'label_status_id'` in `_BUS_TRIGGER_FIELDS`
  - Line 28: `'label_status'` → `'label_status_id'` in `_ADDRESS_LOCK_FIELDS`
  - Lines 80-92: drop Selection field; add `label_status_id = fields.Many2one('label.status.option', ondelete='restrict', tracking=True, index=True)`
  - Line 186 region (`write()` override): add `_check_ba_manager_or_raise()` guard when `'label_status_id' in vals` BEFORE `sudo().write(...)` — FR-017 16th confirmation
  - Line 229 (bus payload): `'label_status': self.label_status or ''` → `'label_status': self.label_status_id.code or ''`
  - `create()` override (if it touches the field): mirror FR-017 guard

### Models registration
- `custom_addons/multichannel_hub_core/models/__init__.py` — append `from . import label_status_option`

### Data (NEW)
- `custom_addons/multichannel_hub_core/data/label_status_data.xml` — 16 records, `noupdate="1"`, xmlids `label_status_<code>` per T-LBL-03 transcription:
  - **target** (red): `us_od` color=1 seq=10; `vietnam_od` color=1 seq=20
  - **pd_selfmake** (green): `vn_tattoo` (10/110), `vn_wooden_dish` (10/120), `vn_dish` (10/130), `vn_dish_ng` (2/140), `vn_dish_fix` (2/150), `vn_sp_moi` (10/160), `vn_packed` (10/170), `vn_packed_1` (10/180), `vn_apron` (10/190), `vn_handkerchief` (10/200)
  - **done** (blue): `vn_fulfilled` color=4 seq=300
  - **approval** (orange): `cho_duyet` color=3 seq=410; `da_gui_proof` color=3 seq=420; `cho_file` color=3 seq=430

### Data (MODIFIED)
- `custom_addons/multichannel_hub_core/data/operations_dashboard_saved_filters.xml:40` — domain swap to `('label_status_id', '!=', False)` per Q2 decision

### Security (MODIFIED)
- `custom_addons/multichannel_hub_core/security/ir.model.access.csv` — append 2 rows:
  - `access_label_status_option_user,label.status.option.user,model_label_status_option,base.group_user,1,0,0,0`
  - `access_label_status_option_ba_manager,label.status.option.ba_manager,model_label_status_option,multichannel_hub_core.group_ba_manager,1,1,1,1`

### Views (MODIFIED)
- `custom_addons/multichannel_hub_core/views/operations_dashboard_views.xml`:
  - Lines 50-53: replace `<field name="label_status" widget="badge" decoration-...>` with `<field name="label_status_id" widget="many2one_tags" options="{'no_create': True}"/>`
  - Line 76: `[('label_status', '=', 'bought')]` → `[('label_status_id', '!=', False)]` (planner Q2 decision)
  - Lines 93-94: group-by context `'group_by': 'label_status'` → `'group_by': 'label_status_id'` (M2O group-by uses comodel display_name; flat-sibling per Odoo 19 RNG memory)

### Migrations (NEW)
- `custom_addons/multichannel_hub_core/migrations/19.0.1.0.29/__init__.py` — empty
- `custom_addons/multichannel_hub_core/migrations/19.0.1.0.29/post-label-status-default.py` — `migrate(cr, version)` body:
  1. `env = api.Environment(cr, SUPERUSER_ID, {})`
  2. `target = env.ref('multichannel_hub_core.label_status_cho_duyet', raise_if_not_found=True)`
  3. `cr.execute("SELECT id FROM sale_order_fulfillment WHERE label_status_id IS NULL")` — collect IDs
  4. `cr.execute("UPDATE sale_order_fulfillment SET label_status_id = %s WHERE label_status_id IS NULL", (target.id,))`
  5. `_logger.warning("P1-LBL migration: rewrote %d sale.order.fulfillment rows to default 'Chờ duyệt' (id=%s); audit list: %s", count, target.id, list(ids))`

### Tests (NEW)
- `custom_addons/multichannel_hub_core/tests/test_label_status_db.py` — Phase 1 DB (6 methods, see §7)
- `custom_addons/multichannel_hub_core/tests/test_label_status_orm.py` — Phase 2 ORM (6 methods, see §7)

### Tests (MODIFIED — migrate off legacy literals)
- `tests/test_tracking_dashboard.py:91, 98, 229, 286` — replace literal `'bought'`/`'none'` writes with `self.env.ref('multichannel_hub_core.label_status_<code>').id`
- `tests/test_operations_dashboard_orm.py:102, 182, 192, 201` — same pattern; lines 322-333 (the delegation test): keep but rename to `test_related_label_status_id_readable_via_sale_order` and assert M2O traversal
- `tests/test_phase2_orm.py:166-168` — flip default-value assertion: `'none'` → `False` (M2O default)
- `tests/test_audit_coverage_db.py:124` — introspection list update: `'label_status'` → `'label_status_id'`
- `tests/test_operations_dashboard_db.py:225-227` — view-arch field-name check update

### Manifest (MODIFIED)
- `custom_addons/multichannel_hub_core/__manifest__.py`:
  - `'version': '19.0.1.0.28'` → `'19.0.1.0.29'`
  - Append `'data/label_status_data.xml'` to `data` list (place after `shipping_carrier_data.xml`, before pipeline seed)

---

## 3. Agent dispatch order

| Phase | Agent | Inputs | Output |
|---|---|---|---|
| 1 — Phase 1 plan (this doc) | planner (Sonnet) | tracker row + tasks.md + this plan | DONE |
| 2 — RED | tdd-guide | this plan §7 | 12 new failing tests in `test_label_status_db.py` + `test_label_status_orm.py`; 5 existing test files NOT yet updated (TODO comments only) |
| 3 — GREEN (orchestrator inline; no sub-agent — recent self-deception captures #5/#6 in memory recommend inline GREEN for slices touching cross-test surface) | orchestrator | RED commit | model + seed + view + ACL + migration + sale_order_fulfillment surgery + manifest bump; 5 existing test files migrated last |
| 4 — Review (PARALLEL, single message, 2 Agent calls) | code-reviewer + security-reviewer | GREEN commit | block on CRITICAL/HIGH; advisory MEDIUMs accepted with inline notes |
| 5 — Verify | orchestrator | reviewed code | `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` exit 0; test-tag run green; ruff if available |
| 6 — Commit | orchestrator | verified | one conventional commit `feat(mhc): P1-LBL label_status M2O swap` (or split RED/GREEN if reviewer requests) |
| 7 — Document | orchestrator | committed | tasks.md `[X]` for T-LBL-01..14 + tracker P1-LBL `state→done` + findings.md surprises |
| 8 — Learn | orchestrator | findings | `/learn` invoke |

---

## 4. Risks + mitigations

1. **Seed xmlid collision** (LOW after grep) — mitigation: orchestrator pre-grep confirmed no `label_status_<code>` xmlids exist; we own the namespace.
2. **Test-migration scope creep** (MEDIUM) — 5 test files, 14 specific lines/ranges. Mitigation: edit ALL 5 in one batch AFTER GREEN model+migration land; do not interleave.
3. **Migration ordering** (LOW) — Odoo loads `data/` XML before `migrations/<version>/post_*.py`. Mitigation: `env.ref('multichannel_hub_core.label_status_cho_duyet', raise_if_not_found=True)` will surface an explicit error if data didn't load. Test T-LBL-13 `test_migration_default_writes_cho_duyet_with_warning` covers the happy path.
4. **Bus payload type regression** (MEDIUM) — listeners may expect a string code, not an ID. Mitigation: payload uses `self.label_status_id.code` (string), not `.id`. Test T-LBL-13 #2 verifies payload structure.
5. **Backward-compat for in-flight orders** (LOW) — existing fulfillment rows have NULL `label_status_id` after column add. Mitigation: post-migration script defaults all NULLs to `cho_duyet`; logs row count + IDs via `_logger.warning`.
6. **`required=True` on legacy Selection — does new M2O preserve required-ness?** (MEDIUM, new gotcha) — original Selection had `required=True, default='none'`. M2O equivalent would be `required=True` + `default=lambda self: self.env.ref('multichannel_hub_core.label_status_cho_duyet').id`. **Decision**: leave M2O as nullable (no `required=True`) and rely on post-migration defaulting + view UX. Otherwise creating a fulfillment without explicitly setting `label_status_id` raises; would break the `_inherits` auto-create on `sale.order.create`. Document in findings.md.

---

## 5. Open questions for owner

All BLOCKING resolved by orchestrator decisions in header (`Q1` confirmed; `Q2` defer to P1-LBL-MIGRATE). Slice can proceed.

NON-BLOCKING (no need to wait):
- Q3 BA-shipping read: keep R-only for `base.group_user`.
- Q4 `translate=True` on `name`: yes.
- Q5 (orchestrator-added) `required=True` on Many2one: NO; nullable + post-migration default. See risk #6.

---

## 6. Exit-criteria pre-check

| ID | Criterion | Verification |
|---|---|---|
| EXIT-1 | T-LBL-01..14 marked `[X]` in tasks.md | grep `[X] T-LBL-` count == 14 |
| EXIT-2 | Tests pass | `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core --stop-after-init`; new tests pass; pre-existing `TestHistoricalSeedT078.test_seed_skips_empty_urls` baseline failure unchanged |
| EXIT-3 | Module installs cleanly | `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` exit 0; expect post-migration `_logger.warning` on existing rows |
| EXIT-4 | ACLs + sudo + raw SQL commented | `grep label_status_option` in `ir.model.access.csv` returns 2 rows; security-reviewer APPROVE; `init()` raw SQL has `# Drift mirror per project_sql_constraints_drift memory (9th confirmation)` comment |
| EXIT-5 | Tracker P1-LBL `state→done`; last reviewed 2026-05-10 | `grep "P1-LBL" .claude/plans/006-master-plan-tracking.md` shows `done` |
| EXIT-6 | `/learn` insight | new memory entry OR explicit "no new patterns — drift template 9th confirmation only" note in commit body |
| EXIT-7 | findings.md updated | `specs/003-dashboard-design-multichannel/findings.md` has P1-LBL section (M2O nullable decision, bus-payload string-code choice, legacy-test-migration scope) |

---

## 7. Two-Phase Testing layout

### Phase 1 DB — `tests/test_label_status_db.py` (6 methods)

1. `test_model_registered` — `'label.status.option' in self.env.registry`
2. `test_unique_constraint_present` — raw SQL `SELECT 1 FROM pg_constraint WHERE conname LIKE '%label_status_option_code%'` returns ≥1
3. `test_seed_records_loaded` — `len(env['label.status.option'].search([]))` == 16; bucket distribution `target=2, pd_selfmake=10, done=1, approval=3` via read_group
4. `test_seed_xmlids_resolvable` — loop 16 codes, assert `env.ref(f'multichannel_hub_core.label_status_{code}')` returns recordset
5. `test_fulfillment_field_swap` — `information_schema.columns` has `label_status_id` int FK; legacy `label_status` varchar column DOES NOT exist (drop verification)
6. `test_acl_grants` — `ir.model.access` rows: base.group_user R/0/0/0; group_ba_manager R/W/C/U; no other groups

### Phase 2 ORM — `tests/test_label_status_orm.py` (6 methods)

1. `test_create_with_duplicate_code_raises` — savepoint + IntegrityError on duplicate `code='vn_fulfilled'`
2. `test_fulfillment_write_emits_bus_on_label_status_id_change` — patch `bus.bus._sendone`; write `label_status_id` change; assert call_args has channel `'multichannel_hub.fulfillment_update'` and payload `'label_status': '<code-string>'` (NOT id)
3. `test_fulfillment_write_blocked_for_non_ba_manager` — non-ba-manager user `with_user(...).write({'label_status_id': seed.id})` raises AccessError; ba_manager user write succeeds (FR-017 16th confirmation)
4. `test_fulfillment_address_lock_includes_label_status_id` — order with `has_pending_address_change=True`; write `label_status_id` raises UserError; same write with `context={'bypass_address_change_check': True}` succeeds
5. `test_migration_default_writes_cho_duyet_with_warning` — set fulfillment `label_status_id=False`; call migration helper directly; assert post-write `label_status_id == env.ref(...cho_duyet).id`; `assertLogs('odoo.addons.multichannel_hub_core', level='WARNING')` captures the audit-list warning
6. `test_kanban_color_reachable_via_m2o` — `fulfillment.label_status_id.color` is integer 0..15

---

## 8. Summary

- **14 slice tasks** + **7 exit-criterion tasks** registered in `TaskCreate`
- **~80 LOC new model** + **~40 LOC migration** + **16-record seed XML** + **12 new tests** + **5 existing test files migrated** + **1 view file + 1 saved-filter file + 1 ACL CSV + 1 manifest update**
- **Manifest version**: `19.0.1.0.28` → `19.0.1.0.29`
- **Migration dir**: new `19.0.1.0.29/`
- **FR-017 16th confirmation**, **drift template 9th confirmation**
- **No new ADR needed** — Selection→M2O is data-shape change within existing data-model.md §2 footprint
- **No external blockers**; ready for tdd-guide RED phase
