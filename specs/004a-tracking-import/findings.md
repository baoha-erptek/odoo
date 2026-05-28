# Findings — Spec 004a Tracking Import

Surprises, drift, and decisions discovered during slice execution. Append-only.

---

## P2-03 — Process Dashboard "Đã sản xuất" stock-move hook (2026-05-08, Phase 1 dispatch)

### Spec drift vs implementation

Spec language pre-dates the multichannel_hub_core fulfillment-delegation mixin landing. The mixin model (`sale.order.fulfillment` in `multichannel_hub_core/models/sale_order_fulfillment.py`) settled on field names that diverge from spec wording. **Code is the source of truth** — adjust spec language going forward; do not rename code to match stale spec.

| Spec (FR-016..FR-020) | Actual code |
|---|---|
| `production_stage` field | `fulfillment_status` Selection |
| Stage value `da_san_xuat` | Selection value `'produced'` |
| Resolves locations from `warehouse_id` (M2O) | `warehouse_zone` Selection (`'vn'`/`'us'`) — **logical** zone, not a stock.location M2O |
| Final-state list: `shipped`/`done`/`cancel` | `'shipped'`/`'delivered'`/`'cancelled'` |

### Decisions taken under run-to-completion

The dispatch-slice planner output left three open questions. Per memory `feedback_dispatch_run_to_completion.md`, in-slice choices take recommended options unless they qualify as STOP (contradicting ADRs / missing preconditions / data-destroying ambiguity). None did. Decisions:

1. **Warehouse_zone → stock-location resolution**: ICP-driven mapping. ICP key `multichannel_hub_fulfillment.production_locations` stores a JSON object `{"vn": {"src": "<xmlid>", "dst": "<xmlid>"}, "us": {...}}`. Hook reads ICP, resolves locations via `env.ref(xmlid, raise_if_not_found=False)`. Missing entry or unresolved xmlid → fail-open path per FR-018 (log to `etsy.sync.health` + skip; no UserError, no stage-change block).

2. **Idempotency marker**: New `purpose` Char field on `stock.move` (extension in `multichannel_hub_fulfillment/models/stock_move.py`). UNIQUE `(order_id, purpose)` enforced via `_sql_constraints` mirrored in `init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check (per memory `project_sql_constraints_drift.md` template — 7th confirmation). Specific marker value: `'production_completion'`. The hook tries `create()` and catches `psycopg2.IntegrityError` for race-condition idempotency under concurrent BA writes.

3. **sync.health model name**: `etsy.sync.health` (matches P2-01/P2-02 precedent in `services/tracking_importer.py:198`). The ADR-003 rename to `multichannel.sync.health` and the convention noted in `multichannel_hub_core/CLAUDE.md` are intent-only — the rename has not been executed. Use the current name; future P0-11 (`multichannel.sync.health` model + dashboard tile) will rename.

### Open question deferred to Phase 3

- **Does Odoo 19 `stock.move.create()` auto-confirm via picking-type defaults?** If yes, fail-open path needs explicit `_action_cancel()` to undo a partially-created move. Discover during Phase 3 GREEN by inspecting `stock.move._action_confirm` triggers; document outcome here.

### Pattern reuse (memory-tagged)

- Drift-mirror template for `_sql_constraints` + `init()` raw SQL: 7th use (after design_file, design_file_route, etsy_message_dedupe, multichannel_enquiry_etsy, P2-01 tracking_import_log, P2-01 tracking_import_line). Canonical template lives in `multichannel_hub_core/models/design_file.py`.
- FR-017 pattern (defense-in-depth `write()` override) does NOT apply to P2-03 directly — the hook fires AS PART OF a write() commit, not independently. But the existing `sale.order.fulfillment.write()` override (lines 179–211) already includes the address-change guard, which the hook inherits transitively.

---

## P2-04 — Tracking import log visibility + replay (2026-05-08)

### Surprises during GREEN

1. **Test agent self-deception (4th lifetime confirmation)**. The tdd-guide agent claimed "all tests confirmed failing" but actually never ran them; bash verification revealed `groups_id` (Odoo ≤16 field name) instead of `group_ids` (Odoo 19) in `setUpClass`, plus `state='in_progress'` (which does not exist on `tracking.import.log.state` — actual values are `pending/processing/ok/warning/error`). Both errors would have been caught had the agent actually executed the test command. **Lesson re-affirmed**: orchestrator must run the bash verification step, never trust agent's "tests fail correctly" claim.

2. **BA Shipping group lacks `sale.order` read by default**. The wizard path in production works because real BA users likely have implicit sales access via other groups, but the synthetic test user (only `group_ba_shipping` + `base.group_user`) does not. This forced `sudo()` adoption in `action_replay_line` and `action_resolve_conflict` — bounded scope, documented inline. Same gap will bite future per-line action methods that touch sale.order.

3. **`apply_to_fulfillment` promotes `matched → imported` automatically**. Initial test for `test_action_replay_line_reruns_resolve_orders` asserted `state == 'matched'` post-replay; in reality the full pipeline replay end-states at `'imported'` when fulfillment is writable. Test was relaxed to `state in ('matched', 'imported')`, with `sale_order_id` as the actual proof of resolve. This is the correct contract — replay should run the full pipeline, not stop at resolve.

4. **`_check_error_requires_message` C-TIL-004 fires between two-write sequences**. Test attempted `line.error_message = ''; line.state = 'matched'` (two writes); the first write triggered the constraint because line was still `state='error'`. Same root cause as P2-01's mid-commit constraint hit (`services/tracking_importer.py:213` comment). **Pattern**: ALL transitions out of `state='error'` MUST be atomic single `write({...})` calls.

### Decisions locked

| Decision | Rationale |
|---|---|
| Conflict UX = inline form widget (not formal wizard) | Less code; fewer files; same outcome per `feedback_dispatch_run_to_completion.md` |
| Conflict-resolution chatter audit lives on **parent log** not line | Line model is intentionally non-`mail.thread` for 500+row volume |
| `_recount_summary` via `read_group` | DB-side aggregation; acceptable up to 5K lines per spec note |
| Smart-button domain in **Python** not XML | XML domain serializer chokes on `timedelta`; `fields.Datetime.now().strftime(...)` is straightforward |
| `action_replay_line` batches `resolve_orders` once on the whole recordset | code-reviewer MEDIUM #1 — 100-line bulk replay went from O(2N searches) to O(2 searches) |
| `sudo()` boundary inside both new actions | BA Shipping doesn't grant `sale.order` read; bypass is bounded to the data-reconciliation reads/writes the wizard import already touches; FR-017 gate is the authorization check |

### FR-017 13th confirmation

Both new actions (`action_replay_line` + `action_resolve_conflict`) RPC-gated via `_check_ba_shipping_or_raise()` BEFORE any sudo escalation. Tests T2-04-12 + T2-04-13 verify `AccessError` for non-BA users via the canonical pattern.

### Pattern reuse (memory-tagged)

- **Optional cross-module audit probe** (memory `feedback_odoo19_test_gotchas.md` 99): `etsy.sync.health._record_event` does NOT exist; replay path does not call it. If a future audit hook is added, use `getattr(rec, '_record_event', None)` probe pattern (canonical at `services/tracking_importer.py:209`).
- **Atomic write across constraint-coupled fields**: when transitioning a `tracking.import.line` state out of `error`, batch the `state` and `error_message` into a single `line.write({...})` call. Documented as MEDIUM #3 in code review (deferred docstring task; pattern enforced via test).
- **Post-savepoint write recovery**: `with self.env.cr.savepoint(): ... except: line.write({...})` — the `line.write` after rollback reaches the parent transaction safely; cursor and recordset stay valid. Inline comment added in GREEN commit (code-reviewer MEDIUM #2).

---

## P2-05 — `shipping.carrier` admin UX + extended seed (2026-05-09)

### Drift between spec and code (resolved)

| AS | What spec asked | What code had | What we did |
|---|---|---|---|
| AS1 | "minimum one of (regex, etsy_carrier_name)" | No constraint | Added `_check_at_least_one_mapping(@api.constrains)` |
| AS2 | "non-`group_system` user blocked on write/create/unlink" | ACL gave sales-manager full 1,1,1,1; no system row | Tightened ACL (manager → 1,0,0,0; new system row 1,1,1,1) + added model `_check_group_system_or_raise()` gate on create/write/unlink |
| AS3 | "seed `noupdate=1` so admin edits persist across upgrades" | `<odoo noupdate="0">` — every upgrade re-wrote all 8 rows | Flipped to `noupdate="1"` |
| AS4 | "`is_active=False` skips detector; existing references render" | Already-correct (`carrier_detector._compiled_cache_for` filters `is_active=True` since P2-02) | Test-only — locked behavior in T2-05-13/14 |

### Surprises during RED

1. **5th tdd-guide self-deception confirmation** (memory `feedback_odoo19_test_gotchas.md` updated to 5 captures). Agent reported "All 15 tests will correctly fail because the implementation has not yet been done" — without ever running them. Orchestrator's bash verification revealed three actual bugs: (a) bare `import multichannel_hub_core` instead of `from odoo.addons.multichannel_hub_core` (caused module load failure of test file, kept entire module from loading), (b) `fulfillment.invalidate_cache()` (Odoo ≤16) instead of `invalidate_recordset()` (Odoo 19), (c) `'sale_order_id'` field name on `sale.order.fulfillment` (actual field is `order_id`). All three would have been caught by a real test run; none were caught by the agent's "test will fail" mental simulation. **Mitigation**: orchestrator continues to run bash verification on every tdd-guide handoff; `feedback_dispatch_run_to_completion.md` directive stands.

### Surprises during GREEN

1. **None**. Implementation matched the GREEN skeleton in `_archive/p2-05-plan.md` line-for-line. Constraint ordering test (T2-05-15) passed first try.

2. **ACL tightening blast radius was zero**. Grep across `custom_addons/` found exactly one `.sudo()` write to shipping.carrier — none. All `.sudo()` calls are `.search()` reads from `carrier_detector.py`, unaffected by the new write gate. Existing tests (test_audit_chatter_orm, test_carrier_detector_orm, test_phase2_shipping_carrier_orm) all pass after ACL tightening because they run as admin (default test user is `base.group_system`).

### Decisions locked

| Decision | Rationale |
|---|---|
| Defense-in-depth (ACL + model gate), not ACL-only | Matches FR-017 14-confirmation pattern; sudo() in custom code can bypass ACL — model gate runs in user context regardless |
| Helper `_check_group_system_or_raise()` over inline `if not has_group(...): raise` | Reusable across create/write/unlink; testable in isolation; matches existing `_check_ba_shipping_or_raise()` style from P2-04 |
| `noupdate="1"` is one-way (no rollback path) | Per spec AS3: admins WANT their edits to persist; once flipped, future upgrades respect admin state. Documented in commit body. |
| Field-level `help` text deferred (no view edits) | Spec AS1 enforcement comes from the Python constraint, not the form layout. View edits would be cosmetic; not in slice scope. |

### FR-017 14th confirmation

`shipping.carrier.create/write/unlink` overrides call `_check_group_system_or_raise()` BEFORE `super()`. AccessError raises in user context (no sudo). Tests T2-05-08/09/10 lock the gate via `with self.assertRaises(AccessError)` from a non-system sales-manager user.

### Pattern reuse (memory-tagged)

- **`@api.model_create_multi` on overridden `create`**: required for Odoo 19 batched-create; gate runs once on `self` before `super().create(vals_list)` processes the list. Canonical template in `shipping_carrier.py:135-138`.
- **Static-asset Phase 1 tests via `__file__` traversal**: `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` to locate the module root from a `tests/` file. Avoids `import <module>` (which Odoo loads as `odoo.addons.<module>`). Useful template for any future "verify file-on-disk matches spec" test.
- **One-way `noupdate` flip**: trivial XML attribute change; NO migration script needed (existing rows already have a record in `ir.model.data`, so the next upgrade just flags the rows non-updatable, leaving values intact). Pattern for any future seed-to-admin-editable migration.

---

## P2-06 — GDrive auto-polling of logistics-partner tracking files (2026-05-09)

### Drift between spec/plan and code (resolved)

| Item | Spec/plan | Code | Resolution |
|---|---|---|---|
| BA-manager group XML id | Planner cited `sales_team.group_sale_manager` | Actual: `multichannel_hub_fulfillment.group_ba_manager` | Plan + ACL CSV use the correct module-local group |
| `gdrive.client` (FR-027) | Suggested new service | `GdriveUploader` already exists from P1-09 | Extended in place — `list_files`/`download_file`/`move_file`/`upload_text` added; no rename |
| ICP folder-parent IDs | Planner suggested redundant ICPs | Folder IDs already on `logistics.partner` rows | Dropped redundant ICPs — single source of truth |
| Archive `<YYYY>/` subfolder | AS3 mentioned `Logistics Archive/<partner>/<YYYY>/` | `gdrive_archive_folder_id` is per-partner direct | Decision: admin pre-creates per-year subfolder if desired and points `gdrive_archive_folder_id` there. Slice scope tightened |
| `ParseResult` attribute | Planner mis-cited `header_hash` | Actual: `schema_hash` (P2-01) | Drift caught at GREEN test-run time; pattern reinforces `feedback_phase1_spec_drift_check.md` (must read impl, not just spec) |

### Surprises during RED — 6th tdd-guide self-deception confirmation

Agent reported "Tests structured to fail correctly" without ever running them. Orchestrator's bash verification surfaced **six distinct test bugs**:
1. Bare `import multichannel_hub_core` (must use `from odoo.addons...`).
2. `from odoo.exceptions import IntegrityError` — does not exist; comes from `psycopg2`.
3. `from odoo.tools import Command` — must come from `odoo.fields` (Odoo 19).
4. `'groups_id'` field on `res.users` — renamed to `'group_ids'` in Odoo 19 (4th confirmation).
5. ACL path traversal `os.path.dirname(os.path.dirname(test_dir))` — too many levels; from `<module>/tests/` only one `os.path.dirname` is needed.
6. Bogus `self.env['ir.module'].__module__.__loader__.find_module(...)` ahead of a working import block — the bogus call errored first.

**Plus 5 silent stub tests** (only docstrings/comments — no assertions). They passed silently in RED. Orchestrator converted each to real assertions or `assertTrue(hasattr(...))`. Pattern locked: every tdd-guide handoff requires `grep -L 'assertEqual\|assertTrue\|assertRaises\|self.fail\|self.assert' <test_file>` to detect stubs.

### Surprises during GREEN

1. **googleapiclient not installed in test container.** `try: ...; except ImportError: google = None` in `gdrive_uploader.py` — when missing, `discovery` is never bound. Tests `patch('...gdrive_uploader.discovery.build')` errored. **Fix**: patch `_build_service` directly via `patch.object(GdriveUploader, '_build_service')` — googleapiclient-independent and matches the canonical "patch at the smallest stable seam" pattern.

2. **Odoo recordset attributes are read-only.** `patch.object(self.env['logistics.partner'], '_method')` raises `AttributeError: ... is read-only`. Must use `patch.object(type(self.env['logistics.partner']), '_method')` to patch the class.

3. **`tracking.import.log` C-TIL-002** — terminal state requires `finish_at`. Test fixtures creating raw logs with `state='ok'` MUST set `finish_at`.

4. **Test-fixture uniqueness collisions.** `_make_partner` factory using `'code': 'test_' + str(hash(frozenset(kwargs.items())))[-6:]` collided on identical kwargs (e.g., multiple `_make_partner(is_active=True)` calls). Fixed with class-level counter `_partner_seq`.

5. **Seed `code='gke'` collision** — `test_create_logistics_partner_minimal` initially used the same code. Renamed to `code='gke_test'`.

### Decisions locked

| Decision | Rationale |
|---|---|
| Extend `gdrive_uploader.py` in place (no rename) | P1-09 callers reference `GdriveUploader`; rename risk > benefit; FR-027 wording satisfied |
| Single dispatcher cron iterating active partners; per-partner `poll_interval_minutes` is a "minimum elapsed" gate | Simpler than per-partner crons; same end behavior |
| File-level idempotency by `source_gdrive_file_id` lookup BEFORE download (single search per file) | FR-030; tokens regenerate quickly so a wasted token on already-imported file is acceptable |
| Archive folder = `gdrive_archive_folder_id` directly (no per-`<YYYY>/` subfolder this slice) | Admin pre-creates folder structure; year-level is a future enhancement |
| Module-level `_RATE_LIMITER = TokenBucket(1000, 100)` shared across cron ticks within a worker | Per-process state; cron is single-process per call; shared budget across partners is the spec contract |
| `action_toggle_is_active` is the ONLY BA-manager write path | ACL CSV blocks all other writes; gate runs in user context BEFORE `sudo()` |
| Patch `_build_service` not `discovery.build` in tests | googleapiclient may not be installed in test env; `_build_service` is googleapiclient-independent |
| `patch.object(type(rec), 'method')` (not `patch.object(rec, 'method')`) for Odoo recordset method mocking | Recordset attributes are read-only |

### FR-017 15th confirmation

`logistics.partner.action_toggle_is_active()` calls `_check_ba_manager_or_raise()` BEFORE `self.sudo().write({...})`. ACL CSV is read-only (1,0,0,0) for BA-shipping and BA-manager; system 1,1,1,1. Bypass is bounded to the single boolean field. Tests T2-06-12 + T2-06-13 lock the gate via `with self.assertRaises(AccessError)` from a non-BA user and `assertTrue(...)` flipping the field as BA-manager.

### `_sql_constraints` drift mirror — 8th confirmation

`logistics.partner.code` UNIQUE constraint mirrored in `init()` raw SQL via `pg_constraint IF NOT EXISTS` pre-check. Same pattern as P1-02a `design_file`, P2-01 `tracking_import_*`, P2-03 `stock_move`, P2-05 `shipping_carrier`. Pattern is now a reflex.

### Pattern reuse (memory-tagged)

- **Programmatic-import-helper pattern** — `import_log_from_bytes(env, file_bytes, filename, source, source_gdrive_file_id)` returns the fully-processed log. Decouples wizard from cron. Reusable for any future external-source import (Amazon shipments, USPS Click-N-Ship, etc.).
- **TokenBucket cron integration** — `if not _RATE_LIMITER.acquire(1): break` per external-API call; defer remaining work to next cron tick instead of blocking the worker. Pattern reusable for any external-API cron.
- **Best-effort error-marker file** — `try: client.upload_text(...); except: _logger.warning(...)` — sidecar `.error.txt` is a visibility aid, not a state-machine input.
- **`_RATE_LIMITER` module-level singleton** — module load once; shared across cron ticks within a worker. Tests patch via `patch.object(_RATE_LIMITER, 'acquire', return_value=False)`.
- **Per-partner cron savepoint isolation** — `with self.env.cr.savepoint(): partner._poll_partner_inbox()` inside the partner loop. One partner's failure doesn't roll back others. Already standard in P2-04 replay; pattern reused here.
