# P2-06 Phase-1 Tactical Plan — Google Drive auto-polling of logistics-partner tracking files (US6)

**Slice**: P2-06 (Spec 004a US6)
**Branch**: `feature/006-master-plan-coding`
**Module**: `multichannel_hub_fulfillment` (`logistics.partner` + cron); `multichannel_hub_core` (gdrive client extension)
**Dependencies**: P1-09 (done), P2-01..P2-05 (done)
**Authored**: 2026-05-09 (planner agent + orchestrator drift correction)

---

## Spec-Drift Check

Verified against actual files (orchestrator override after planner mis-cited BA-manager group):

| Item | Spec | Code | Verdict |
|---|---|---|---|
| `tracking.import.log.source` Selection (`manual`/`gdrive`) | FR-029 | Present in `models/tracking_import_log.py` | MATCH |
| `tracking.import.log.source_gdrive_file_id` Char | FR-029 | Present, `copy=False` | MATCH |
| `GdriveUploader.upload_file()` + `ensure_shop_folder()` | FR-027 | Present in `multichannel_hub_core/services/gdrive_uploader.py` | PARTIAL — needs `list_files`, `download_file`, `move_file` |
| `TokenBucket(rate, period).acquire(count=1) -> bool` + `time_until_refill()` | FR-034 | Present in `multichannel_hub_core/utils/rate_limiter.py` | MATCH (use as-is) |
| Shared-Drive flags `supportsAllDrives=True` + `includeItemsFromAllDrives=True` | per `feedback_staging_gdrive_provisioning.md` | Already used in `gdrive_uploader.py:144-150` | MATCH (reuse pattern) |
| BA-manager group XML id | FR-035 ("BA-manager read + toggle is_active") | `multichannel_hub_fulfillment.group_ba_manager` (NOT stock `sales_team.group_sale_manager`) | DRIFT — planner cited stock group; corrected here |
| BA-shipping group XML id | FR-022 chain | `multichannel_hub_fulfillment.group_ba_shipping` | MATCH |
| `etsy.sync.health` model | FR-033 (`gdrive_integration` row) | Cross-module; access via `getattr(env, 'etsy.sync.health', None)` probe (memory feedback_odoo19_test_gotchas.md #99) | IMPLICIT (probe pattern) |
| `logistics.partner` model | FR-026 — 8 fields | Does NOT exist | NEW |
| `logistics.inbox.poller` cron | FR-028 | Does NOT exist | NEW |

---

## Decisions Locked

| # | Decision | Rationale |
|---|---|---|
| 1 | Extend `multichannel_hub_core/services/gdrive_uploader.py` in place — add `list_files()`, `download_file()`, `move_file()` to existing `GdriveUploader` class. Do NOT rename file. | Renaming risks breaking P1-09 imports; the class is already named `GdriveUploader`; FR-027 wording ("`gdrive.client` service") is satisfied by extending existing service file |
| 2 | `logistics.partner` model lives in `multichannel_hub_fulfillment`; `gdrive_uploader.py` extension stays in `multichannel_hub_core`; cron lives in `multichannel_hub_fulfillment` | Logistics is a fulfillment concern (ADR-003 module decomposition); GDrive client is shared infra (ADR-006 §6) |
| 3 | Single dispatcher cron iterating active `logistics.partner` rows; NOT one cron per partner | Simpler admin UX; rate-limiter ensures quota compliance; `poll_interval_minutes` per partner becomes a "minimum elapsed since last_poll_at" gate inside the dispatcher loop |
| 4 | ACL: `group_system` 1,1,1,1; `group_ba_manager` 1,0,0,0 read-only via CSV; `is_active` toggle exposed via `action_toggle_is_active()` RPC + model gate (no inline write override needed because BA-manager has no write perm to bypass) | FR-035 word-literal "read + toggle is_active"; defense-in-depth via custom action that calls `_check_ba_manager_or_raise()` then `sudo()` flips field — sudo() inline-commented per security.md |
| 5 | File-level idempotency by `source_gdrive_file_id` lookup BEFORE download (single search query); row-level idempotency by P2-01's `(log_id, source_row_hash)` UNIQUE | FR-030 + reuses P2-01 invariant; no double-download even on cron re-entry |
| 6 | Archive folder path = `gdrive_archive_folder_id` directly (per-partner already specifies the archive root — no per-year subfolder this slice). Spec AS3 mentions `<YYYY>/` but ADR-006 §6 leaves the depth to admin folder pre-creation. | Keep slice scope tight; admin pre-creates `<YYYY>/` if desired and updates `gdrive_archive_folder_id` annually. Documented as Decision in findings.md |
| 7 | Rate-limiter consumption — module-level singleton `TokenBucket(1000, 100)`; cron checks `acquire(1)` BEFORE each gdrive API call; if False, defer that partner to next tick (no in-tick sleep) | Cron is short-lived; sleeping inside cron blocks the worker. Skipping to next partner respects worker time |
| 8 | NO redundant ICPs for parent folder IDs — folder IDs live ONLY on `logistics.partner.gdrive_inbox_folder_id` and `gdrive_archive_folder_id`. Drop the planner's suggested `multichannel_hub_fulfillment.gdrive_inbox_parent_folder_id` ICP (overengineering). | Single source of truth; admin sees folder IDs on partner form |
| 9 | Programmatic convergence: poller calls `services/tracking_importer.import_log_from_bytes(env, file_bytes, filename, source='gdrive', source_gdrive_file_id=file_id) -> tracking.import.log` — new helper. Wizard `action_import` is refactored minimally to delegate to this helper for code reuse. | FR-032 convergence; avoids constructing TransientModel + invoking action steps from non-UI context |
| 10 | Error marker `<filename>.error.txt` written via `gdrive_client` upload (small text body); failure to write marker is NOT fatal — caught and logged | FR-031; marker is a visibility aid for operators, not a state machine input |
| 11 | GKE seed in `data/logistics_partner_data.xml` with `noupdate="1"`; folder IDs left as empty strings — admin populates via UI on first install (memory `feedback_staging_gdrive_provisioning.md`: real folder IDs depend on tenant) | Avoid hardcoding tenant-specific IDs; install does not crash on empty IDs (cron skips partners with empty `gdrive_inbox_folder_id`) |

---

## Phase 3 GREEN Skeleton

### Files to create

1. **`custom_addons/multichannel_hub_fulfillment/models/logistics_partner.py`** — Model with 8 fields per FR-026, `_check_poll_interval_positive()` constrains, `action_toggle_is_active()` RPC, `_cron_poll_inbox()` (@api.model entry), `_poll_partner_inbox()` (private per-partner). UNIQUE(code) `_sql_constraints` + mirror in `init()` raw SQL per drift template (8th use).
2. **`custom_addons/multichannel_hub_fulfillment/data/logistics_partner_data.xml`** — `noupdate="1"`. GKE seed (folder IDs empty); cron `ir.cron` row pointing to `model._cron_poll_inbox()`, interval=15 min.
3. **`custom_addons/multichannel_hub_fulfillment/views/logistics_partner_views.xml`** — tree + form + search + menu under Operations → Tracking → Logistics Partners.
4. **`custom_addons/multichannel_hub_fulfillment/migrations/19.0.1.0.16/post-init-noop.py`** — placeholder if needed for ACL refresh; delete if not. (Probably not needed — ACL CSV reload handles it.)

### Files to modify

5. **`custom_addons/multichannel_hub_core/services/gdrive_uploader.py`** — append three methods to `GdriveUploader` class:
   - `list_files(folder_id, modified_after=None) -> list[dict]` — returns `[{'id', 'name', 'modifiedTime', 'mimeType'}, ...]`; uses `q="'<folder>' in parents and trashed=false"` + optional `modifiedTime > '<rfc3339>'`; both Shared-Drive flags ON.
   - `download_file(file_id) -> bytes` — uses `MediaIoBaseDownload`; returns content.
   - `move_file(file_id, new_parent_folder_id) -> dict` — `files().update(fileId=..., addParents=..., removeParents=<old>, supportsAllDrives=True)`; returns updated file metadata.
   - `upload_text(folder_id, filename, body) -> dict` — small helper for the `.error.txt` marker (uses `MediaInMemoryUpload` text/plain).
6. **`custom_addons/multichannel_hub_fulfillment/services/tracking_importer.py`** — add module-level helper `import_log_from_bytes(env, file_bytes, filename, source='manual', source_gdrive_file_id=None) -> tracking.import.log`. Wraps existing parse + processing chain. Returns the fully-processed log.
7. **`custom_addons/multichannel_hub_fulfillment/wizards/tracking_import_wizard.py`** — minimal refactor: `action_import` delegates to `import_log_from_bytes(...)` for the bulk-process path. (If existing wizard already does this internally, no change needed; verify in GREEN.)
8. **`custom_addons/multichannel_hub_fulfillment/security/ir.model.access.csv`** — append 3 rows for `logistics.partner` (ba_shipping read 1,0,0,0; ba_manager read 1,0,0,0; system 1,1,1,1).
9. **`custom_addons/multichannel_hub_fulfillment/__manifest__.py`** — bump version `19.0.1.0.15` → `19.0.1.0.16`; add `multichannel_hub_core` to `depends` (it already is); register new data + view files.
10. **`custom_addons/multichannel_hub_core/__manifest__.py`** — bump version since `gdrive_uploader.py` changed.

### Method-level skeleton — `logistics.partner`

```python
class LogisticsPartner(models.Model):
    _name = 'logistics.partner'
    _description = 'Logistics partner GDrive inbox configuration'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True)
    gdrive_inbox_folder_id = fields.Char()
    gdrive_archive_folder_id = fields.Char()
    poll_interval_minutes = fields.Integer(default=15, required=True)
    is_active = fields.Boolean(default=True, tracking=True)
    last_poll_at = fields.Datetime(readonly=True)
    last_success_poll_at = fields.Datetime(readonly=True)

    _sql_constraints = [('logistics_partner_code_uniq', 'UNIQUE(code)', 'Partner code must be unique')]

    @api.model
    def init(self):
        # Mirror UNIQUE constraint per drift template (8th confirmation)
        # ... pg_constraint IF NOT EXISTS pre-check ...

    @api.constrains('poll_interval_minutes')
    def _check_poll_interval_positive(self):
        for rec in self:
            if rec.poll_interval_minutes < 1:
                raise ValidationError(_('Poll interval must be ≥1 minute'))

    def _check_ba_manager_or_raise(self):
        if not self.env.user.has_group('multichannel_hub_fulfillment.group_ba_manager') \
                and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Toggling logistics partner requires BA Manager role'))

    def action_toggle_is_active(self):
        self.ensure_one()
        self._check_ba_manager_or_raise()
        # sudo(): BA-manager has read-only ACL; bypass the write gate AFTER user-context auth check
        self.sudo().write({'is_active': not self.is_active})
        return True

    @api.model
    def _cron_poll_inbox(self):
        partners = self.search([('is_active', '=', True),
                                ('gdrive_inbox_folder_id', '!=', False)])
        for partner in partners:
            elapsed = ... # check last_poll_at vs now() vs partner.poll_interval_minutes
            if not _due(partner): continue
            try:
                with self.env.cr.savepoint():
                    partner._poll_partner_inbox()
            except Exception as e:
                partner._record_gdrive_health_error(str(e))

    def _poll_partner_inbox(self):
        self.ensure_one()
        client = GdriveUploader()
        files = client.list_files(self.gdrive_inbox_folder_id, modified_after=self.last_poll_at)
        for f in files:
            if not f['name'].endswith('.xlsx'):
                continue
            if not _RATE_LIMITER.acquire(1):
                break  # defer remaining files to next tick
            existing = self.env['tracking.import.log'].sudo().search(
                [('source_gdrive_file_id', '=', f['id'])], limit=1)
            if existing:
                continue  # FR-030 idempotency
            data = client.download_file(f['id'])
            log = import_log_from_bytes(self.env, data, f['name'],
                                        source='gdrive', source_gdrive_file_id=f['id'])
            if log.state in ('ok', 'warning'):
                client.move_file(f['id'], self.gdrive_archive_folder_id)
                self.last_success_poll_at = fields.Datetime.now()
            else:
                marker = f"{f['name']}.error.txt"
                body = f"Import failed for log {log.name}: {log.error_count} errors"
                try:
                    client.upload_text(self.gdrive_inbox_folder_id, marker, body)
                except Exception:
                    pass  # marker is best-effort
        self.last_poll_at = fields.Datetime.now()
```

### Method-level skeleton — `tracking_importer.import_log_from_bytes`

```python
def import_log_from_bytes(env, file_bytes, filename, source='manual', source_gdrive_file_id=None):
    """Programmatic entry into the same import pipeline used by the wizard.

    Returns the fully-processed tracking.import.log (state in {ok, warning, error}).
    """
    parser = GkeExcelParser()
    parsed = parser.parse(file_bytes)
    log = env['tracking.import.log'].sudo().create({
        'filename': filename,
        'file_size_bytes': len(file_bytes),
        'schema_hash': parsed.header_hash,
        'header_columns': json.dumps(parsed.headers),
        'source': source,
        'source_gdrive_file_id': source_gdrive_file_id or False,
        'state': 'pending',
        'total_rows': len(parsed.rows),
    })
    importer = TrackingImporter(env)
    importer.process(log, parsed)  # creates lines, transitions state, writes fulfillment
    return log
```

(Exact method names depend on existing services — verify during GREEN coding; this is the contract, not the literal call sequence.)

---

## Phase 2 RED Test List

### Phase 1 — DB / static-asset (`tests/test_phase1_db.py` — append)

- T2-06-01 `test_logistics_partner_table_exists` — `information_schema.tables` query
- T2-06-02 `test_logistics_partner_code_unique_constraint` — `pg_constraint` query
- T2-06-03 `test_logistics_partner_acl_rows_exist` — 3 rows in `ir.model.access.csv`
- T2-06-04 `test_gdrive_uploader_has_list_files_method` — `hasattr(GdriveUploader, 'list_files')`
- T2-06-05 `test_gdrive_uploader_has_download_file_method` — same for `download_file`
- T2-06-06 `test_gdrive_uploader_has_move_file_method` — same for `move_file`
- T2-06-07 `test_gdrive_uploader_has_upload_text_method` — same for `upload_text`
- T2-06-08 `test_logistics_inbox_poller_cron_exists` — `ir.cron` record present after install

### Phase 2 — ORM behavior (`tests/test_phase2_orm_p2_06.py` — new file)

- T2-06-09 `test_create_logistics_partner_minimal` — happy-path create
- T2-06-10 `test_logistics_partner_code_unique_raises` — duplicate code → IntegrityError
- T2-06-11 `test_poll_interval_lt_one_raises` — value 0 → ValidationError
- T2-06-12 `test_action_toggle_is_active_blocked_for_non_ba_manager` — generic user → AccessError
- T2-06-13 `test_action_toggle_is_active_flips_for_ba_manager` — BA-manager flips True→False
- T2-06-14 `test_cron_skips_inactive_partner` — `is_active=False` → not polled
- T2-06-15 `test_cron_skips_partner_with_empty_inbox_folder` — empty `gdrive_inbox_folder_id` → not polled
- T2-06-16 `test_cron_respects_poll_interval` — partner polled within `poll_interval_minutes` since `last_poll_at` → not re-polled this tick
- T2-06-17 `test_list_files_passes_shared_drive_flags` — mock GdriveUploader.list_files asserts both flags True
- T2-06-18 `test_list_files_filters_by_modified_after` — `modifiedTime > <RFC3339>` clause present in query string
- T2-06-19 `test_poll_skips_existing_source_gdrive_file_id` — prior log with same file_id → skipped (FR-030)
- T2-06-20 `test_poll_downloads_and_imports_new_file` — new .xlsx file → log created with `source='gdrive'`, `source_gdrive_file_id=<id>`
- T2-06-21 `test_poll_skips_non_xlsx_files` — `.csv`, `.txt` files in inbox not downloaded
- T2-06-22 `test_poll_moves_file_to_archive_on_ok` — log.state=ok → `move_file` called with archive folder
- T2-06-23 `test_poll_moves_file_to_archive_on_warning` — log.state=warning → moved
- T2-06-24 `test_poll_leaves_file_in_inbox_on_error` — log.state=error → `move_file` NOT called
- T2-06-25 `test_poll_writes_error_marker_on_error` — `.error.txt` upload attempted
- T2-06-26 `test_poll_error_marker_failure_swallowed` — marker upload throws → no propagation; main flow continues
- T2-06-27 `test_poll_updates_last_poll_at_unconditionally` — `last_poll_at` set even on error
- T2-06-28 `test_poll_updates_last_success_poll_at_only_on_ok_or_warning` — error path → `last_success_poll_at` unchanged
- T2-06-29 `test_poll_consumes_rate_limiter` — TokenBucket.acquire(1) called before each API call
- T2-06-30 `test_poll_defers_partner_when_rate_limit_exhausted` — `acquire` returns False → partner polling stops gracefully (next tick retries)
- T2-06-31 `test_import_log_from_bytes_returns_processed_log` — helper returns log with state set
- T2-06-32 `test_import_log_from_bytes_sets_source_fields` — `source='gdrive'` + `source_gdrive_file_id` populated
- T2-06-33 `test_import_log_from_bytes_default_source_manual` — when source param omitted, defaults to `'manual'`
- T2-06-34 `test_convergence_wizard_uses_same_helper` — wizard `action_import` produces equivalent log shape (chosen field set)
- T2-06-35 `test_poll_writes_sync_health_on_auth_error` — googleapiclient HttpError 401 → `etsy.sync.health` write via getattr probe
- T2-06-36 `test_poll_continues_to_next_partner_on_partner_error` — partner A throws → partner B still polled

---

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| GDrive 404 on Shared Drive missing flags | Reuse `gdrive_uploader.py:144-150` flag pattern in all 3 new methods. Test T2-06-17 asserts. |
| File_id idempotency race (two cron ticks) | Single search query per file BEFORE download; second tick sees existing log and skips. Cron tick is short. |
| Rate-limiter exhaustion | `acquire(1)` per API call; defer remaining files this tick. Test T2-06-30 locks behavior. |
| Convergence with wizard pipeline drift | `import_log_from_bytes` is the new shared entry; wizard refactored to use it. Test T2-06-34 asserts. |
| Marker file write fails (permissions, quota) | Best-effort try/except; not fatal. Test T2-06-26. |
| Folder ID empty in seed | Cron skips partners with empty inbox; admin populates after install. Test T2-06-15. |
| `mail.thread` chatter spam from cron writes to `last_poll_at` | `last_poll_at` not in `tracking=True` set; only `is_active` is tracked. |
| Cross-module probe for `etsy.sync.health` | `getattr(env, 'etsy.sync.health', None)` pattern (memory feedback_odoo19_test_gotchas.md #99). |

---

## Agent Dispatch Order (Phases 2-8)

| Phase | Agent | Notes |
|---|---|---|
| 2 RED | `tdd-guide` | Write 36 tests, verify all fail for correct reasons |
| 3 GREEN | orchestrator inline | Plan is detailed enough; no architect needed |
| 4 Review | `code-reviewer` + `security-reviewer` parallel | Single message, two `Agent` calls |
| 5 Verify | orchestrator inline | install + tests + ruff + grep |
| 6 Commit | orchestrator inline | RED + GREEN commits, conventional format |
| 7 Document | orchestrator inline | tracker + tasks.md + findings.md |
| 8 Learn | orchestrator inline | `/learn` capture |
