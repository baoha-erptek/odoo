# Data Model — Spec 004a Slice P2-01

**Slice**: P2-01 (US1 Excel import wizard with schema fingerprinting)
**Module**: `multichannel_hub_fulfillment`

Future slices (P2-02..P2-06) extend this model; declarations below anticipate them — see `## Forward declarations`.

---

## 1. `tracking.import.log` (Model, persistent)

Audit envelope for one Excel import. One log → many lines.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | yes | computed | `GKE-{create_date:%Y%m%d}-{seq}` via sequence `tracking.import.log.seq` |
| `state` | Selection | yes | `pending` | `pending` / `processing` / `ok` / `warning` / `error` |
| `source` | Selection | yes | `manual` | `manual` / `gdrive` (P2-06 populates `gdrive`) |
| `source_gdrive_file_id` | Char | no | False | populated by P2-06 only |
| `filename` | Char | yes | — | original upload filename, sanitized basename |
| `file_size_bytes` | Integer | yes | 0 | enforced ≤ ICP `multichannel_hub.large_file_threshold_bytes` |
| `schema_hash` | Char(64) | yes | — | SHA-256 hex of normalized header sequence |
| `header_columns` | Text | yes | — | JSON array of original headers (forensic) |
| `is_new_schema` | Boolean | yes | False | True if schema_hash not in ICP allowed set at upload time |
| `total_rows` | Integer | yes | 0 | from openpyxl row count |
| `matched_count` | Integer | yes | 0 | rows resolved to sale.order |
| `unmatched_count` | Integer | yes | 0 | rows with no order match |
| `conflict_count` | Integer | yes | 0 | rows with multiple matches |
| `error_count` | Integer | yes | 0 | rows raising during processing |
| `imported_count` | Integer | yes | 0 | rows successfully written to fulfillment |
| `address_change_flagged_count` | Integer | yes | 0 | matched rows where `has_pending_address_change=True` |
| `line_ids` | One2many | — | — | `tracking.import.line.log_id` |
| `start_at` | Datetime | no | False | set when `state` → `processing` |
| `finish_at` | Datetime | no | False | set when `state` → `ok`/`warning`/`error` |
| `triggered_by_user_id` | Many2one(`res.users`) | yes | `env.user` | uploader |
| `notes` | Html | no | False | operator-visible summary; MAY embed Markup-escape per P1-04 |

**Inherits**: `mail.thread` + `mail.activity.mixin` (audit chatter on state changes — `tracking=True` on `state`, `is_new_schema`).

**Indexes**:
- `(state, create_date DESC)` composite via `init()` raw SQL — Tracking Dashboard recent-imports query.
- `schema_hash` simple via `index=True` field arg — fingerprint lookup.

**Constraints**:
- `_sql_constraints`:
  - `tracking_import_log_name_uniq UNIQUE(name)` — sequence collision guard.
- `@api.constrains('file_size_bytes')` — C-TIL-001: `file_size_bytes <= ICP threshold`.
- `@api.constrains('state', 'finish_at', 'start_at')` — C-TIL-002: terminal state requires `finish_at >= start_at`.

**`init()` raw SQL**: composite index `(state, create_date DESC)` per `_sql_constraints` drift template (`pg_constraint IF NOT EXISTS` pre-check; mirror UNIQUE in case `_sql_constraints` registry-drift recurs — 4th confirmation pattern).

**ACL** (`security/ir.model.access.csv`):
| Group | R | W | C | U |
|---|---|---|---|---|
| `group_ba_shipping` | 1 | 1 | 1 | 0 |
| `group_ba_manager` | 1 | 1 | 1 | 1 |
| `base.group_system` | 1 | 1 | 1 | 1 |

---

## 2. `tracking.import.line` (Model, persistent)

Per-row record with raw input + resolution outcome + idempotency hash.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `log_id` | Many2one(`tracking.import.log`) | yes | — | ondelete=cascade, index=True |
| `row_number` | Integer | yes | 0 | 1-indexed within source file |
| `source_row_hash` | Char(64) | yes | — | SHA-256 of `|`-joined raw cell values; idempotency key |
| `state` | Selection | yes | `pending` | `pending` / `matched` / `unmatched` / `conflict` / `imported` / `error` |
| `raw_order_number` | Char | yes | — | verbatim ORDER NUMBER cell |
| `raw_tracking_number` | Char | no | False | verbatim TRACKING cell |
| `raw_carrier_label` | Char | no | False | verbatim CARRIER cell (free-text from GKE) |
| `raw_shipping_date` | Char | no | False | verbatim DATE cell as string (pre-parse) |
| `raw_payload` | Text | yes | — | JSON dict of all cells for this row (forensic) |
| `parsed_shipping_date` | Date | no | False | dayfirst=True parsed |
| `sale_order_id` | Many2one(`sale.order`) | no | False | resolved via `channel_order_ref` → fallback `etsy_order_id` |
| `fulfillment_id` | Many2one(`sale.order.fulfillment`) | no | False | denormalized for write-target |
| `detected_carrier_id` | Many2one(`shipping.carrier`) | no | False | populated by P2-02; declared here |
| `applied_carrier_id` | Many2one(`shipping.carrier`) | no | False | written if order's current carrier is empty |
| `address_change_flag` | Boolean | yes | False | True if resolved order has `has_pending_address_change` |
| `error_message` | Text | no | False | sanitized exception text on `state='error'` |
| `notes` | Char | no | False | operator note |

**Indexes**:
- `(log_id, state)` composite via `init()` raw SQL.
- `sale_order_id` via `index=True`.
- `source_row_hash` via `index=True` (lookups during idempotency check).

**Constraints**:
- `_sql_constraints`:
  - `tracking_import_line_idempotency_uniq UNIQUE(log_id, source_row_hash)` — re-run idempotency.
- `@api.constrains('state', 'sale_order_id')` — C-TIL-003: `state='matched'` requires `sale_order_id`.
- `@api.constrains('state', 'error_message')` — C-TIL-004: `state='error'` requires `error_message`.

**`init()` raw SQL**: mirror UNIQUE constraint per drift template + composite `(log_id, state)`.

**ACL**:
| Group | R | W | C | U |
|---|---|---|---|---|
| `group_ba_shipping` | 1 | 1 | 1 | 0 |
| `group_ba_manager` | 1 | 1 | 1 | 1 |
| `base.group_system` | 1 | 1 | 1 | 1 |

**No `mail.thread`** — high volume (500+ rows per import).

---

## 3. `tracking.import.wizard` (TransientModel)

Upload + preview + import action.

| Field | Type | Required | Notes |
|---|---|---|---|
| `excel_file` | Binary (`attachment=True`) | yes | size cap enforced via existing `ir.attachment` 10 MB check (P1-02a) + wizard-level `@api.constrains` |
| `excel_filename` | Char | yes | uploaded original filename |
| `state` | Selection | yes | `draft` / `previewed` / `done` |
| `schema_hash` | Char(64) | computed | SHA-256 of normalized header sequence; `compute='_compute_schema_hash'`, `store=False` |
| `is_new_schema` | Boolean | computed | comparison vs ICP allowed set |
| `header_diff_html` | Html | computed | rendered diff vs last-known schema for BA review |
| `preview_log_id` | Many2one(`tracking.import.log`) | no | populated by `action_preview()` |
| `preview_line_ids` | One2many | computed | from `preview_log_id.line_ids` |

**Methods**:
- `action_preview()` — parse file, create log + lines (state='pending'), compute counts, transition wizard to `state='previewed'`.
- `action_approve_schema()` — gated `_check_ba_manager_or_raise()`; appends current `schema_hash` to ICP `multichannel_hub_fulfillment.gke_schema_hashes` (JSON list); records `etsy.sync.health` event with `kind='gke_schema_approved'`. NO row processing.
- `action_import()` — gated `_check_ba_shipping_or_raise()` (any BA-shipping or above); requires `schema_hash` ∈ allowed set; iterates `preview_line_ids`, applies per-row savepoint write to `sale.order.fulfillment`, transitions log state on completion, calls `etsy.sync.health._record_event()` via sudo (cross-module, commented).
- `action_cancel()` — discard preview, drop log + lines.

**ACL**:
| Group | R | W | C | U |
|---|---|---|---|---|
| `group_ba_shipping` | 1 | 1 | 1 | 1 |
| `group_ba_manager` | 1 | 1 | 1 | 1 |

**No `unlink` for shipping** — TransientModel auto-vacuum handles cleanup.

---

## 4. Forward declarations (consumed by sibling slices)

These fields are declared on P2-01 models but fully populated by later slices:
- `tracking.import.line.detected_carrier_id` — written by **P2-02** carrier detector.
- `tracking.import.log.source` = `gdrive` + `source_gdrive_file_id` — written by **P2-06** GDrive poller.
- `tracking.import.line.state` enum extended in **P2-03** for stock-move-hook transitions (no schema change; selection list grows).

---

## 5. Extensions to existing models

**`sale.order.fulfillment`** (multichannel_hub_core, owned by P1-05):

No new fields in this slice. Writes hit existing fields:
- `tracking_number` (Char)
- `shipping_date` (Date)
- `tracking_state` (Selection — transition to `'shipped'` on import)
- `shipping_carrier_id` (Many2one — only if currently empty per spec §US1 AC4)

Address-change defense-in-depth (P1-03 `_ADDRESS_LOCK_FIELDS`):
- `tracking_number`, `shipping_date`, `tracking_state` are NOT in `_ADDRESS_LOCK_FIELDS` (locked set is `partner_shipping_id`, `partner_id`, etc.). No bypass context needed.
- Verify in Phase 2 RED test: import on order with `has_pending_address_change=True` succeeds; `partner_shipping_id` write would still raise.

**`etsy.sync.health`** (etsy_integration, owned by Spec 002 W3.1):

New `kind` enum values added by this slice:
- `gke_tracking_import` — per-import event
- `gke_schema_approved` — when BA-manager approves new schema

Helper `_record_event(kind, ok_count, warning_count, error_count, notes)` already exists; reuse.

---

## 6. ICPs (`ir.config_parameter`)

| Key | Type | Default | Owner |
|---|---|---|---|
| `multichannel_hub_fulfillment.gke_schema_hashes` | JSON list of SHA-256 hex | `[]` | this slice |
| `multichannel_hub.large_file_threshold_bytes` | int | `10485760` (10 MB) | reused from P1-02a |
| `multichannel_hub_fulfillment.import_batch_size` | int | `200` | this slice (savepoint batch size) |

ICP writes for `gke_schema_hashes` go through `action_approve_schema()` only. Direct `ir.config_parameter.set_param` from BA users blocked by base ACL (already system-only).

---

## 7. Sequences (`ir.sequence`)

| Code | Name | Prefix | Padding |
|---|---|---|---|
| `tracking.import.log.seq` | GKE Tracking Import Log | `GKE-` | 6 |

---

## 8. Groups (`res.groups`)

Audit existing first; declare only if missing:
- `multichannel_hub_fulfillment.group_ba_shipping` — BA shipping operator (uploads Excel, approves rows).
- `multichannel_hub_fulfillment.group_ba_manager` — BA manager (approves new schema; `implied_ids` includes `group_ba_shipping`).

If `group_ba_lead` from P1-04 covers `group_ba_manager` semantics, reuse instead of declaring new. **Decide during Phase 3 GREEN**.

---

## 9. State machine (`tracking.import.log.state`)

```
draft → pending → processing → {ok | warning | error}
```

Transitions:
- `draft` → `pending`: wizard `action_preview()`.
- `pending` → `processing`: wizard `action_import()` start.
- `processing` → `ok`: 0 errors + 0 warnings.
- `processing` → `warning`: 0 errors + ≥1 row with `state in (unmatched, conflict, address_change_flag=True)`.
- `processing` → `error`: ≥1 row with `state='error'` OR top-level exception.

`tracking=True` on `state` for chatter audit.

---

## 10. State machine (`tracking.import.line.state`)

```
pending → {matched, unmatched, conflict} → {imported, error}
```

Transitions:
- `pending` → `matched`: `sale_order_id` resolved.
- `pending` → `unmatched`: no order match.
- `pending` → `conflict`: ≥2 orders match `channel_order_ref`.
- `matched` → `imported`: write to fulfillment succeeded.
- `matched` → `error`: write raised (savepoint rolled back).
- `unmatched`/`conflict` → `error`: never auto-transitioned; manual via P2-04 replay slice.

---

## 11. Composite-index summary

| Table | Index | Reason |
|---|---|---|
| `tracking_import_log` | `(state, create_date DESC)` | Tracking Dashboard recent-imports |
| `tracking_import_log` | `schema_hash` | fingerprint lookup |
| `tracking_import_line` | `(log_id, state)` | log-detail view |
| `tracking_import_line` | UNIQUE `(log_id, source_row_hash)` | idempotency |
| `tracking_import_line` | `sale_order_id` | order-detail back-reference |
| `tracking_import_line` | `source_row_hash` | dedup lookup |

All declared via field `index=True` where simple; composite + UNIQUE mirrored in `init()` raw SQL per drift template.

---

## 12. `logistics.partner` (Model, persistent — added by P2-06)

Per-supplier configuration for the GDrive polling cron.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | yes | — | Display name (e.g., "GKE Logistics") |
| `code` | Char | yes | — | Folder-path-friendly code; UNIQUE; index=True |
| `gdrive_inbox_folder_id` | Char | no | False | GDrive folder ID where partner drops `.xlsx` |
| `gdrive_archive_folder_id` | Char | no | False | GDrive folder where successful files are moved |
| `poll_interval_minutes` | Integer | yes | 15 | Min minutes between polls; ≥1 (constraint) |
| `is_active` | Boolean | yes | True | tracking=True; soft-disable without deletion |
| `last_poll_at` | Datetime | no | False | Set by cron after every poll attempt (success or fail) |
| `last_success_poll_at` | Datetime | no | False | Set by cron only on log.state in (`ok`,`warning`) |

**Inherits**: `mail.thread` (audit chatter on `is_active` toggle).

**Constraints**:
- `_sql_constraints`: `logistics_partner_code_uniq UNIQUE(code)` — mirrored in `init()` raw SQL per drift template (8th use).
- `@api.constrains('poll_interval_minutes')` — value < 1 raises ValidationError.

**Methods**:
- `_check_ba_manager_or_raise()` — gate helper.
- `action_toggle_is_active()` — RPC for BA-manager. Calls gate, then `sudo().write({'is_active': not self.is_active})` (sudo bypasses BA-manager's read-only ACL after explicit auth check).
- `_cron_poll_inbox()` (@api.model) — cron entry; iterates active partners, savepoint per partner.
- `_poll_partner_inbox(self)` — per-partner: list_files → idempotency check by `source_gdrive_file_id` → download → `import_log_from_bytes` → archive on success / `.error.txt` marker on failure.

**ACL** (`security/ir.model.access.csv`):
| Group | R | W | C | U |
|---|---|---|---|---|
| `multichannel_hub_fulfillment.group_ba_shipping` | 1 | 0 | 0 | 0 |
| `multichannel_hub_fulfillment.group_ba_manager` | 1 | 0 | 0 | 0 |
| `base.group_system` | 1 | 1 | 1 | 1 |

**Idempotency contract**: file-level by `tracking.import.log.source_gdrive_file_id`; row-level by `tracking.import.line` UNIQUE `(log_id, source_row_hash)` (forwarded from P2-01).

**Seed** (`data/logistics_partner_data.xml`, `noupdate="1"`):
- GKE row with `code='gke'`, folder IDs left empty (admin populates after install per `feedback_staging_gdrive_provisioning.md`).
- `ir.cron` row `cron_logistics_inbox_poller` calling `model._cron_poll_inbox()` every 15 minutes.

---

## 13. `GdriveUploader` extension (services/gdrive_uploader.py — modified by P2-06)

Existing class (P1-09) is extended in place; new methods consume the same service-account auth path:

| Method | Signature | Notes |
|---|---|---|
| `list_files` | `(folder_id: str, modified_after: datetime|None=None) -> list[dict]` | Lists `.xlsx` candidates; `q="'<folder>' in parents and trashed=false"`; both Shared-Drive flags ON; optional `modifiedTime > '<rfc3339>'` clause. |
| `download_file` | `(file_id: str) -> bytes` | `MediaIoBaseDownload`; returns content. |
| `move_file` | `(file_id: str, new_parent_folder_id: str) -> dict` | `files().update(addParents=..., removeParents=<old>, supportsAllDrives=True)`. |
| `upload_text` | `(folder_id: str, filename: str, body: str) -> dict` | Small text/plain via `MediaInMemoryUpload`; used for `.error.txt` marker. |

---

## 14. `tracking_importer.import_log_from_bytes` (module-level helper — added by P2-06)

```
import_log_from_bytes(env, file_bytes: bytes, filename: str,
                      source: str = 'manual',
                      source_gdrive_file_id: str | None = None) -> tracking.import.log
```

Programmatic entry to the same import pipeline used by the wizard. Returns the fully-processed log (state in {`ok`, `warning`, `error`}). Wizard's `action_import` is refactored to delegate to this helper — both manual and GDrive paths converge on a single code path (FR-032).
