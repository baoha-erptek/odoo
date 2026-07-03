# Feature Specification: GKE Tracking Import, Carrier Detection, and Process Dashboard Handoff

> **STATUS (2026-07-03)**: Completed. All P2-01 user stories (GKE import wizard, carrier detection, stock moves, logging) shipped and production-ready. US6 (GDrive polling) deferred pending external dependency (E3). Open remainders consolidated into specs/015-project-completion/.

**Feature Branch**: `004a-tracking-import`
**Created**: 2026-04-13 · **Revised**: 2026-04-13 (GDrive polling added per Q7 answer)
**Status**: Draft (Wave B — pending plan.md + data-model.md)
**Authority**: [master plan 006](../006-master-plan/MASTER_PLAN.md), ADRs [001](../006-master-plan/adrs/ADR-001-spec-004-split.md) [003](../006-master-plan/adrs/ADR-003-module-decomposition.md) [005](../006-master-plan/adrs/ADR-005-carrier-unification.md) [006 §6](../006-master-plan/adrs/ADR-006-design-file-storage.md) [007](../006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md)
**Supersedes (this slice only)**: the tracking-import + carrier-detection portion of the archived Spec 004 (see `specs/004-fulfillment-routing/tasks.md` SUPERSEDED banner). Gearment adapter → Spec 004b. Returns/refunds/tickets → Spec 004c.
**Input**: Ship the highest-value-per-effort work on the roadmap — close the daily tracking reconciliation pain for BA-shipping by importing the GKE Logistics Excel into Odoo, auto-detecting carriers (USPS / UniUni / YunExpress), populating the unified `shipping.carrier` master data, and completing the Process Dashboard's transition-to-produced hook so PD sees stock moves and BA sees fresh tracking numbers within 5 minutes of each Excel upload.

---

## Relationship to sibling specs

- **Spec 002 (Phase 0)** ships first and establishes: `etsy.sync.health` observability model, batch-resumable wizard pattern, and the clean 17K-order baseline.
- **Spec 003 (Wave B, parallel)** owns the `sale.order.fulfillment` delegation mixin, the `shipping.carrier` model itself, the Tracking Dashboard that surfaces this spec's imports, and the Process Dashboard whose "Đã sản xuất" transition this spec completes.
- **This spec (004a)** owns the import wizard, the import log, the per-row import line model, the carrier detection service, and the `stock.move` generation on production-stage transitions.
- **Spec 004b / 004c / 005** do not depend on this spec landing; they depend on Spec 003's mixin.

Cross-cutting ADRs honoured:
- Models live in `multichannel_hub_fulfillment` per ADR-003.
- Tracking fields live on `sale.order.fulfillment` per ADR-007 (this spec writes through the delegated relation).
- Carrier identity is a M2O to `shipping.carrier` per ADR-005 (Spec 003 authors the model; this spec reads + writes it and ships additional seed rows).

## Clarifications captured from end-user + master-plan review

- Q: GKE Excel schema is not version-controlled by the supplier. What's the fingerprint strategy? → A: On each import, hash the normalised header row (columns, order, case-folded). Store the hash in `tracking.import.log`. Hard-fail with a clear message when a new hash is seen; require an explicit "Approve new schema" button (BA role) before the rows are processed.
- Q: Where do DD/MM/YYYY ambiguous dates resolve? → A: Explicit `dayfirst=True` parsing. Test fixtures MUST include at least one date with `day <= 12` to catch silent locale inversion.
- Q: How does the Process Dashboard stage transition to "Đã sản xuất" generate stock moves — is inventory decremented on transition or on shipment? → A: On transition to "Đã sản xuất". The stock move is from the "Raw Materials" source (future Spec 007 scope for pre-built kits) to a "Finished Goods — Ready to ship" location. Idempotent: re-invoking the transition on a row already in that stage is a no-op.
- Q: Does carrier auto-detection ever overwrite a manually-selected carrier? → A: Never. If `shipping_carrier_id` is already set on an order, the detector records its opinion in `tracking.import.line.detected_carrier_id` for audit but does not write to the order.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — GKE Excel import wizard with schema fingerprinting (Priority: P1)

As a BA-shipping team member, I need a wizard where I upload today's GKE Excel, see a clear preview of matched/unmatched rows and carrier detection results, and then confirm the import so the tracking numbers land on the right orders without me needing to touch the shell or write formulas.

**Why this priority**: Tracking reconciliation is the single biggest daily pain after Spec 002's migration. Closing it ships the first operational win to BA-shipping and unlocks the Tracking Dashboard's daily usage.

**Independent Test**: Upload a known-good GKE Excel with 50 rows. The wizard must show: rows matched by ORDER NUMBER, rows unmatched, rows with carrier auto-detected, rows with carrier unknown (flagged `other`), total count, schema fingerprint state (known / new). Click "Import". Verify that matched rows' tracking numbers are written on the order's delegated fulfillment record, `tracking.import.log` has one row with `state='ok'`, `tracking.import.line` has one row per input row, and `etsy.sync.health.gke_tracking_import` reflects the success.

**Acceptance Scenarios**:

1. **Given** a BA user with a current GKE Excel file, **When** they open the Tracking Import wizard and upload, **Then** the system reads the header row, normalises column names (trim, uppercase, case-fold), computes a SHA-256 hash of the sequence, and compares to the persisted known-schema set on `ir.config_parameter` (`multichannel_hub_fulfillment.gke_schema_hashes`).
2. **Given** a new (unknown) schema hash, **When** detected, **Then** the wizard blocks processing, displays the incoming column list alongside the last-known column list as a diff, and offers an "Approve new schema" button restricted to the BA-manager role. Approval appends the hash to the allowed set and records an `etsy.sync.health` note.
3. **Given** an approved schema, **When** the wizard processes rows, **Then** each row produces a `tracking.import.line` with: input fields captured verbatim, `sale_order_id` resolved by `ORDER NUMBER` → `channel_order_ref` (indexed lookup, fallback to `etsy_order_id`), `detected_carrier_id` set by the auto-detector, and `state` in (`matched`, `unmatched`, `conflict`).
4. **Given** matched rows, **When** the user clicks "Import", **Then** the system writes (per-row savepoint): `tracking_number`, `shipping_carrier_id` (only if the order's current carrier is empty; otherwise recorded as `detected_carrier_id` for audit), `shipping_date`, and transitions the tracking state enum on the fulfillment sibling.
5. **Given** a row whose `has_pending_address_change == True` on the resolved order, **When** imported, **Then** the tracking number is written but the row is flagged in the import log; the Tracking Dashboard bulk "Mark shipped" continues to exclude the order (per Spec 003 FR-017).
6. **Given** the import finishes, **When** the log closes, **Then** `tracking.import.log.state` is `ok` / `warning` / `error` based on per-row counts; `etsy.sync.health.gke_tracking_import` is updated via the shared helper; and the Tracking Dashboard reflects the writes within 5 minutes (or immediately on page reload).
7. **Given** an import is interrupted mid-run (worker timeout, OOM), **When** re-run on the same file, **Then** rows already persisted with `state='matched'` are skipped based on `(log_id, source_row_hash)` idempotency; only unprocessed rows resume. No duplicate tracking writes.

---

### User Story 2 — Carrier auto-detection (USPS / UniUni / YunExpress / fallback) (Priority: P1)

As a tracking-import operator, I need the system to auto-detect which carrier a tracking number belongs to so I rarely have to pick a carrier by hand, but I also want clear visibility on "unknown" tracking numbers so I can add carriers to the master data and re-run detection.

**Why this priority**: Without auto-detection, every row requires manual carrier selection, which turns the wizard into a data-entry tool and defeats the productivity win.

**Independent Test**: Feed the detector tracking numbers covering USPS (e.g., `9214…`), UniUni (`UUS…`), YunExpress prefixes, and a synthetic unknown. Verify the first three match and the fourth is flagged `other` (or `unknown` routed to a review queue). Confirm detection rules live on `shipping.carrier.tracking_prefix_regex` and can be edited without code changes.

**Acceptance Scenarios**:

1. **Given** the seed `shipping.carrier` records (Spec 003 ships the model + initial seed; this spec adds per-carrier `tracking_prefix_regex`), **When** the detector is called with a tracking number, **Then** it tries each active carrier's `tracking_prefix_regex` in priority order and returns the first match.
2. **Given** no regex matches, **When** the detector falls back, **Then** the row's `detected_carrier_id` resolves to a `code='other'` seed row and the row is flagged `needs_review=True` for BA surfacing.
3. **Given** a carrier's regex is updated via the admin UI, **When** a later import runs, **Then** the new regex is effective without module restart (standard Odoo ORM behaviour).
4. **Given** multiple regex matches (ambiguous prefix), **When** encountered, **Then** the detector logs a warning to `etsy.sync.health` with the candidate carrier codes and picks the one with the highest `sequence` priority. Operators can resolve by tightening the regex.
5. **Given** a bulk "re-detect" admin action on historical `tracking.import.line` rows flagged `other`, **When** invoked, **Then** each row's `detected_carrier_id` is re-evaluated with the current regex set and updated, without writing to the linked order's already-saved `shipping_carrier_id`.

---

### User Story 3 — Process Dashboard "Đã sản xuất" stock-move hook (Priority: P1)

As a production team member using the Process Dashboard, when I move a row from "Đang sản xuất" to "Đã sản xuất", I need the system to generate the correct `stock.move` from production to finished-goods so inventory is accurate and downstream shipping can proceed without me running a second action.

**Why this priority**: Spec 003 defines the Process Dashboard UI but delegates the stock-move integration here because it's the only spec that knows about carrier/shipping plumbing. Without this hook, the dashboard is read-only for PD in practice.

**Independent Test**: From the Process Dashboard, transition an order to "Đã sản xuất". Verify exactly one `stock.move` is created from the configured production location to the finished-goods location, referencing the order's lines. Re-transition the same row; verify no duplicate move is created (idempotent). Transition a row that has no fulfilment picking yet; verify the wizard logs and does not silently succeed.

**Acceptance Scenarios**:

1. **Given** an order whose Process-Dashboard stage transitions from any non-final state to `da_san_xuat`, **When** the write commits, **Then** a `stock.move` is created from the `Production/Raw Materials` location to the `Stock/Finished Goods — Ready to Ship` location (xmlid configurable per warehouse), quantity = sum of `product_uom_qty` on the order's storable lines.
2. **Given** the same row already in state `da_san_xuat`, **When** the stage is set again (accidental double-click, re-import), **Then** the hook detects the existing move via `(order_id, purpose='production_completion')` marker and does nothing.
3. **Given** a row with no storable lines (e.g., all-service), **When** transitioned, **Then** the hook records an info-level entry to `etsy.sync.health` ("No stock move: no storable products on order X") and does not raise.
4. **Given** a multi-warehouse deployment (VN / US), **When** the hook runs, **Then** the source/destination locations are picked by the order's `warehouse_id` resolution (mapped from shop or a product-category default — the mapping policy is a configuration decision recorded in `plan.md`).
5. **Given** the row's transition fails at the stock level (e.g., negative available quantity with strict policy), **When** the user tries to set `da_san_xuat`, **Then** the transition is rolled back and the user sees a clear on-dashboard error referencing the blocker; the Process-Dashboard row remains in its prior state.

---

### User Story 4 — Tracking import log visibility + replay (Priority: P2)

As a BA-shipping supervisor, I need to see every historical tracking import with its state (ok / warning / error), the uploaded file hash, row counts, the user who uploaded, and per-row error messages, so I can audit imports and replay a failed file if necessary.

**Why this priority**: Audit and replay close the loop on tracking reconciliation. Without this view, a silently-failed import becomes visible only days later when BA notices orders stuck in "no tracking".

**Independent Test**: Open `Tracking Imports` list view. Pick one past import. Verify the log exposes the uploaded file (re-downloadable) and the per-row `tracking.import.line` children. Open a failed line; see the error text. Click "Re-process row"; verify the line retries atomically.

**Acceptance Scenarios**:

1. **Given** the Tracking Import list, **When** rendered, **Then** the columns are: import date, user, filename, schema hash, row_count, matched_count, conflict_count, error_count, state, sync_health_link.
2. **Given** a specific import log, **When** opened, **Then** the form shows a one2many to `tracking.import.line` with filters by state (matched / unmatched / conflict / error) and a "Re-process" action per row.
3. **Given** a conflict line (ORDER NUMBER matches multiple orders, e.g. replacement order lineage), **When** opened, **Then** the operator can choose which order the tracking writes to via a dropdown of candidates; the choice is recorded in chatter.
4. **Given** an error line whose cause has been fixed (e.g., schema was re-approved after the failed import), **When** the operator re-processes, **Then** only that single line is retried inside a savepoint; the parent log is updated and the summary recounted.
5. **Given** the `etsy.sync.health.gke_tracking_import` row, **When** viewed, **Then** it surfaces `last_run_at`, `last_successful_run_at`, `last_run_row_count`, `last_run_error_count`, and a smart-button link to the log list filtered by today.

---

### User Story 5 — Seed extension + admin UX for `shipping.carrier` (Priority: P2)

As a system administrator, I need the ability to add carriers, edit `tracking_prefix_regex`, and set `etsy_carrier_name` + `gearment_carrier_name` mappings without shipping a module patch, so operations can react to new logistics partners within hours instead of release cycles.

**Why this priority**: Logistics carriers change frequently (new regional couriers, Etsy enum updates). A seed-only model forces engineering changes for every new carrier, which is a standing tax the project cannot afford.

**Independent Test**: Create a new carrier via the admin form with a custom regex. Upload an Excel whose tracking numbers match the new regex. Verify the detector picks the new carrier without a restart. Edit the Etsy mapping and confirm Spec 005's tracking-push (future) would see the new value (via read-only assertion on `order.shipping_carrier_id.etsy_carrier_name`).

**Acceptance Scenarios**:

1. **Given** the admin form for `shipping.carrier`, **When** a user with `group_system` creates a new carrier, **Then** they must supply `name`, `code` (unique), and at minimum one of (`tracking_prefix_regex`, `etsy_carrier_name`).
2. **Given** a user without `group_system`, **When** they attempt to edit a carrier, **Then** the ACL blocks the write and surfaces a clear message.
3. **Given** seed data that this spec adds beyond Spec 003's initial set, **When** the module updates, **Then** seed rows are `noupdate="1"` and admin edits are preserved across upgrades.
4. **Given** a carrier whose `is_active = False`, **When** the detector runs, **Then** the carrier is skipped. Existing orders that already reference the inactive carrier continue to render its name (no retroactive blanking).

---

### User Story 6 — Google Drive auto-polling of logistics-partner tracking files (Priority: P1)

As a BA-shipping team member, I want the system to automatically pick up new tracking Excel files that logistics partners (GKE first, UniUni / YunExpress / USPS later) drop into their designated Google Drive folders, so that daily tracking reconciliation no longer depends on a human remembering to download and upload the file manually.

**Why this priority**: Adding GDrive as an automated source closes the remaining manual step in the tracking pipeline. Without it, US1's wizard still requires human upload every day, which is exactly the pain BA-shipping reported. Adding auto-polling costs one service-account setup and a cron; skipping it costs a recurring manual task forever.

**Independent Test**: Configure the GKE partner folder ID on the partner record. Drop a new tracking Excel into the configured GDrive folder. Wait up to one poll interval (default 15 minutes). Verify: (a) the file is downloaded by the service account, (b) it passes through the same Spec 004a import wizard path (schema fingerprint, row savepoints, idempotency), (c) the source file is moved to the partner's GDrive archive folder on success, (d) `tracking.import.log.source_gdrive_file_id` is populated, (e) a duplicate-dropped file is skipped (idempotent by `file_id`), (f) `etsy.sync.health.gke_tracking_import` and the shared `gdrive_integration` health row both reflect the run.

**Acceptance Scenarios**:

1. **Given** a `logistics.partner` record with `gdrive_inbox_folder_id` configured (e.g., for GKE), **When** the polling cron fires (default every 15 minutes), **Then** the service account lists files in the folder, filters by `modifiedTime > partner.last_poll_at`, and queues each new `.xlsx` file for import.
2. **Given** a new file is detected, **When** imported, **Then** the same wizard pipeline used by US1 is invoked programmatically — schema hash is computed, rows are processed in savepoints, `tracking.import.line` rows are created, the carrier detector runs, and the final state is `ok` / `warning` / `error` as per US1.
3. **Given** a successful import, **When** completed, **Then** the source file is moved in GDrive from `Logistics Inbox/<partner>/` to `Logistics Archive/<partner>/<YYYY>/` (per ADR-006 §6 folder structure), preserving the original filename.
4. **Given** an import fails (e.g., unknown schema hash, locked file, parse error), **When** the failure occurs, **Then** the source file is **left in place** (not archived), an error marker `.error.txt` is written next to it with the failure reason, and `etsy.sync.health.gke_tracking_import` shows an error state. The next poll interval retries the file until a human approves a new schema or removes the file.
5. **Given** a file with a `file_id` already recorded in any prior `tracking.import.log.source_gdrive_file_id` row (regardless of state), **When** the poller sees it again, **Then** the file is **skipped** (idempotent). This covers the edge case where a partner re-uploads the same file with a new `modifiedTime` but identical `file_id`.
6. **Given** the GDrive service-account credentials are invalid or the folder ID is wrong, **When** the poller runs, **Then** the cron logs the error on `etsy.sync.health.gdrive_integration`, does not retry within the same cron tick, and surfaces a red tile on the health dashboard.
7. **Given** the "Logistics Partner" admin form, **When** a system admin adds a new partner (e.g., "UniUni"), **Then** they can paste a GDrive folder ID, set the poll cadence, toggle the partner on/off, and the polling cron picks up the new partner without module restart.
8. **Given** manual upload via the US1 wizard is still available, **When** a BA user uploads a file that also happens to be in the GDrive inbox, **Then** the first-to-process path wins (both paths converge on the same `tracking.import.log` creation which is idempotent on `source_row_hash`); duplicates are filtered at the row level not the file level.

---

### Edge Cases

- **UTF-8 corruption**: Windows Excel occasionally exports CP1258 instead of UTF-8. The wizard MUST attempt UTF-8 first, detect BOM, and fall back with an on-screen warning. Diacritic round-trip tests MUST include Vietnamese customer-name fixtures.
- **DD/MM/YYYY inversion**: `03/02/2026` is 3rd Feb (not 2nd Mar). `dayfirst=True` is mandatory and fixture-tested with at least one ambiguous date.
- **Duplicate ORDER NUMBER across shops**: a historical bug allowed two shops to share a numeric ORDER NUMBER. The resolver uses `(channel_order_ref, sales_channel)` composite match; unresolved duplicates are routed to `tracking.import.line.state='conflict'` for manual choice (US4 AS3).
- **Replacement orders** (Spec 004c future) — when an original and its replacement both match an ORDER NUMBER, the conflict UI must show both and record the operator's choice in chatter.
- **Orders already cancelled** — writing a tracking number onto a cancelled order must fail with a `UserError` and route the line to `state='error'`.
- **File > 20 MB** — the import wizard rejects outright with a clear message; GKE's Excel has never exceeded 5 MB historically.
- **Detector regex compiles to a denial of service** — the admin form MUST reject regex patterns that match the empty string; a test MUST assert no catastrophic backtracking (simple length-bounded fixtures).
- **Race with Spec 005 tracking push** — Spec 005 is deferred, but the data-model design assumes the future Etsy push reads `order.shipping_carrier_id.etsy_carrier_name` post-write. No coupling logic here today.

---

## Requirements *(mandatory)*

### Import wizard + log

- **FR-001**: System MUST provide a wizard `tracking.import.wizard` accepting an Excel file, computing the normalised header hash, and gating processing on the hash being in an allowed set.
- **FR-002**: System MUST persist allowed header hashes on `ir.config_parameter` under key `multichannel_hub_fulfillment.gke_schema_hashes` and require a BA-manager role to append a new hash.
- **FR-003**: System MUST persist a `tracking.import.log` per upload with: `user_id`, `filename`, `file_attachment_id` (re-downloadable), `schema_hash`, `row_count`, `matched_count`, `conflict_count`, `error_count`, `state` (Selection), `sync_health_id` M2O, chatter mixins.
- **FR-004**: System MUST persist a `tracking.import.line` per input row capturing: input fields verbatim, `sale_order_id`, `detected_carrier_id`, `state` (`matched`/`unmatched`/`conflict`/`error`), `needs_review`, `error_message`, `source_row_hash` for idempotency.
- **FR-005**: System MUST process rows in savepoint batches (default 200 rows) and update the log + sync.health incrementally.
- **FR-006**: System MUST deduplicate row processing via `(log_id, source_row_hash)` composite so re-runs are idempotent.
- **FR-007**: System MUST write tracking fields onto `sale.order.fulfillment` (via Spec 003's delegation sibling) — `tracking_number`, `shipping_carrier_id` (only when empty), `shipping_date`, and transition the tracking state enum.
- **FR-008**: System MUST NOT overwrite a manually-selected `shipping_carrier_id`. Auto-detected carrier goes to `tracking.import.line.detected_carrier_id` for audit.
- **FR-009**: System MUST skip import-level bulk actions for orders with `has_pending_address_change == True` (consistency with Spec 003 FR-017) and mark those lines with a warning flag.
- **FR-010**: System MUST reject imports that would write tracking onto cancelled orders; route the row to `state='error'`.

### Carrier detection

- **FR-011**: System MUST implement a pure-Python `carrier_detector` service that takes a tracking number and returns a `shipping.carrier` record (or the `other` seed).
- **FR-012**: Detection MUST use `shipping.carrier.tracking_prefix_regex`, evaluated in `sequence` order, case-sensitive against the trimmed tracking number.
- **FR-013**: Unknown tracking MUST resolve to the `code='other'` seed and flag `needs_review=True` on the line.
- **FR-014**: The admin form MUST reject a regex that matches the empty string; tests MUST cover at least one catastrophic-backtracking pattern with a length-bounded timeout.
- **FR-015**: System MUST provide a bulk "Re-detect carriers" admin action over `tracking.import.line` that updates `detected_carrier_id` without touching `sale.order.fulfillment.shipping_carrier_id`.

### Process Dashboard stock-move hook

- **FR-016**: System MUST implement a transition hook that fires when `sale.order.fulfillment.production_stage` changes TO `da_san_xuat` from any non-final state.
- **FR-017**: The hook MUST create exactly one `stock.move` per transition, marked with a unique `(order_id, purpose='production_completion')` pair, and be idempotent on repeat invocations.
- **FR-018**: The hook MUST resolve source/destination locations from the order's `warehouse_id` and fail open (log + skip) for orders whose warehouse lacks the configured locations, not block the stage change.
- **FR-019**: The hook MUST NOT fire for orders with zero storable lines; it MUST log an info-level entry on sync.health and succeed.
- **FR-020**: System MUST refuse to invoke the hook when the order is in a final state (`shipped`, `done`, `cancel`) with a clear `UserError`.

### Google Drive polling (Revised 2026-04-13 per Q7 answer + ADR-006 §6)

- **FR-026**: System MUST implement a `logistics.partner` model with fields: `name`, `code` (unique), `gdrive_inbox_folder_id` (Char), `gdrive_archive_folder_id` (Char), `poll_interval_minutes` (Integer, default 15), `is_active` (Boolean), `last_poll_at` (Datetime), `last_success_poll_at` (Datetime). Seeded with GKE at module install; UniUni / YunExpress / USPS added via admin UI.
- **FR-027**: System MUST implement a `gdrive.client` service in `multichannel_hub_core` (not in this module) that wraps service-account authentication, resumable uploads (for design files — Spec 003 consumer), listing, downloads, and moves. This spec consumes the client; it does not own it.
- **FR-028**: System MUST implement a `logistics.inbox.poller` cron job that iterates active `logistics.partner` rows, lists files in each `gdrive_inbox_folder_id` filtered by `modifiedTime > last_poll_at`, and enqueues each new `.xlsx` file for import via the same pipeline as US1.
- **FR-029**: System MUST persist `source='gdrive'` and `source_gdrive_file_id` on `tracking.import.log` for polled imports, distinguishing them from manual uploads (`source='manual'`).
- **FR-030**: System MUST skip files whose `file_id` matches any prior `tracking.import.log.source_gdrive_file_id` (regardless of that log's state), guaranteeing per-file idempotency.
- **FR-031**: System MUST move successfully processed files from `gdrive_inbox_folder_id` to `gdrive_archive_folder_id/<YYYY>/` preserving the original filename; failed files MUST be left in place and annotated with a sibling `.error.txt` marker.
- **FR-032**: System MUST NOT overwrite US1's manual-upload path — both paths share the same wizard pipeline and the same per-row idempotency.
- **FR-033**: System MUST surface GDrive-related errors on `etsy.sync.health` under both the partner-specific row (`gke_tracking_import`) and a shared `gdrive_integration` row owned by the `gdrive.client`.
- **FR-034**: Poller MUST respect the shared rate limiter (`multichannel_hub_core/utils/rate_limiter.py`) to stay within GDrive's 1000-requests-per-100-seconds quota per service account.
- **FR-035**: System MUST provide an admin form for `logistics.partner` with ACL: `group_system` full access; BA-manager read + toggle `is_active` only.

### Observability + ACL + i18n

- **FR-021**: System MUST write to `etsy.sync.health` (forward-compatible with its future `multichannel.sync.health` rename per ADR-003) with `name='gke_tracking_import'` before, during (per batch), and after each import.
- **FR-022**: System MUST declare ACLs for the new models: BA operator = read/write on `tracking.import.wizard`, read on logs/lines; BA manager = full access; system admin = carrier master data.
- **FR-023**: System MUST declare record rules on `tracking.import.log` mirroring Spec 002 shop-isolation (where applicable).
- **FR-024**: All new user-visible strings MUST be covered by `i18n/vi_VN.po` (consistent with Spec 003 FR-032).
- **FR-025**: All new models MUST inherit `mail.thread` + `mail.activity.mixin` with `tracking=True` on state fields (consistent with Spec 003 FR-031).

### Key Entities

- **`tracking.import.log`** — one per upload; carries state, counts, sync.health link, chatter, the uploaded file as an attachment.
- **`tracking.import.line`** — one per input row; carries the raw input, the resolved `sale_order_id`, the detected carrier, the state, and an idempotency hash.
- **`tracking.import.wizard`** — transient; accepts the file, shows the preview, gates on schema hash, and kicks off the savepointed import.
- **`carrier_detector`** — stateless service; consumes a tracking number and the active carrier set; returns a `shipping.carrier` record. No ORM state.
- **Process-Dashboard stock-move hook** — a method on `sale.order.fulfillment` that fires on `production_stage` transitions to `da_san_xuat`; idempotent; writes a `stock.move` marked with a unique purpose.
- **Extended seed on `shipping.carrier`** — additional carriers + regexes beyond Spec 003's initial set (e.g., UniUni `^UUS[A-Z0-9]{10}$`, YunExpress prefix list, regional couriers discovered during UAT).
- **`logistics.partner`** — one row per external logistics supplier (GKE, UniUni, YunExpress, USPS, …). Owns the GDrive folder IDs and poll cadence. Seed ships with GKE only.
- **`logistics.inbox.poller`** — cron-driven service that polls active `logistics.partner` folders, enqueues new files into the US1 wizard pipeline, and archives on success. Stateless — all state lives on `logistics.partner` and `tracking.import.log`.

## Success Criteria *(mandatory)*

- **SC-001**: A standard daily GKE Excel import from BA-shipping completes in under 3 minutes, with ≥ 99% of rows matched to existing orders in a 60-day post-launch window.
- **SC-002**: Zero silent schema drift — every import whose header hash is new is blocked until explicit approval; audit trail captures 100% of approvals.
- **SC-003**: Auto-detect covers ≥ 95% of incoming tracking numbers in the first 30 days without manual carrier selection.
- **SC-004**: Zero duplicate `stock.move` rows generated by the Process-Dashboard hook over a 60-day sample.
- **SC-005**: Re-running an interrupted import on the same file produces zero duplicate tracking writes and re-uses the existing log.
- **SC-006**: `etsy.sync.health.gke_tracking_import` status surfaced on the shared dashboard tile; BA lead sees failure within 5 minutes of occurrence.
- **SC-007**: 100% of new user-visible strings translated to Vietnamese.
- **SC-008**: After GDrive polling (US6) goes live, the median delay between a partner uploading a tracking Excel to their GDrive folder and the tracking landing on orders is ≤ 20 minutes (1× poll interval + processing) measured over a 30-day window, with ≥ 98% of files processed without manual intervention.

## Assumptions

- Spec 002 is shipped; the 17K baseline is clean enough that `channel_order_ref` resolves reliably.
- Spec 003 is in-flight and will provide: `sale.order.fulfillment` mixin, `shipping.carrier` model + initial seed, Tracking Dashboard + Process Dashboard views.
- GKE remains the primary tracking data supplier; additional suppliers (DHL eCommerce direct API, regional couriers) are separate future specs.
- Multi-warehouse: logical warehouses are sufficient; no physical inventory sync required yet. Clarification pending from master-plan open question #9.
- The 3-day Gearment sandbox spike referenced in the master plan Phase 0 is NOT part of this spec. Its outcome informs Spec 004b only.
- File volumes: daily GKE Excel is < 5 MB, ≤ 2000 rows. This spec is not optimised for 100K-row imports; if needs arise, a dedicated background-queue variant lands as a later amendment.

## Out of Scope

- Gearment API adapter, OAuth, HMAC webhooks → **Spec 004b**.
- Returns, refunds, replace tickets → **Spec 004c**.
- ~~Google Drive automated ingestion of GKE files → permanently deferred (ADR-004, master plan §3).~~ **Reversed 2026-04-13 per Q7 answer**: GDrive polling is now US6 of this spec, using the service-account infrastructure from [ADR-006 §6](../006-master-plan/adrs/ADR-006-design-file-storage.md). ADR-004 rejected `documents_google_drive` (Enterprise module); direct GDrive API access via a service account is not Enterprise-dependent.
- Etsy tracking push (writing back to Etsy) → **Spec 005 Phase B** (post scope-approval).
- Raw-material decrements on production start → **Spec 007** (native `stock_forecasted`).
- Internal-production picking workflow, kitting, routings → beyond 004a; operational stock moves only in scope.

## Dependencies

| This spec needs | From | Why |
|---|---|---|
| `sale.order.fulfillment` delegation mixin | Spec 003 (ADR-007) | Tracking fields live there |
| `shipping.carrier` model + initial seed | Spec 003 (ADR-005) | Detector reads, importer writes |
| `etsy.sync.health` observability helper | Spec 002 (R8) | Import and hook write to it |
| Tracking Dashboard view | Spec 003 | Surfaces imported tracking |
| Process Dashboard view + state machine | Spec 003 | Transition triggers the stock-move hook |
| `channel_order_ref` field | Spec 003 (FR-024) | Resolver maps GKE ORDER NUMBER → order |
| `gdrive.client` service + auth | `multichannel_hub_core` (per ADR-006 §6) | US6 poller reads/moves GDrive files via this shared client |
| `logistics.partner` ACL + admin form scaffold | this spec | Module's own model — but depends on ADR-006 §6 folder structure |

| Other specs need from this | What |
|---|---|
| Spec 004b (Gearment) | `shipping.carrier.gearment_carrier_name` seed mappings; `etsy.sync.health` write-pattern |
| Spec 005 (Etsy API) | Reads `shipping_carrier_id.etsy_carrier_name` for tracking push |
| Spec 007 (raw-material inventory) | Coordinates on the production-stage stock-move hook to decrement raw materials |

## Revision History

- **2026-04-13**: Initial authoring per master-plan Wave B (ADR-001 split of Spec 004; 004a is the MVP slice).
- **2026-04-13 (revision)**: Added US6 Google Drive polling service + FR-026..FR-035 + `logistics.partner` entity + `logistics.inbox.poller` per MASTER_PLAN Q7 answer. Reversed the out-of-scope exclusion of GDrive ingestion. Aligns with [ADR-006 §6](../006-master-plan/adrs/ADR-006-design-file-storage.md) shared service-account policy.
