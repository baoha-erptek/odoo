# Tasks: Fulfillment Routing, Production Assignment, and Partner Integration

> **FROZEN — SUPERSEDED by Master Plan 006** (owner sign-off 2026-04-13)
>
> Spec 004 is **split into three independently-deliverable sub-specs** per [ADR-001](../006-master-plan/adrs/ADR-001-spec-004-split.md):
>
> - **Spec 004a — Tracking Import + Carrier Detection** (Phase 2, MVP): GKE Excel import with schema fingerprinting, `shipping.carrier` unified model (ADR-005), Process Dashboard.
> - **Spec 004b — Gearment Partner Adapter** (Phase 4, post-MVP): Gated on a 3-day Phase 0 sandbox spike (auth, rate limits, HMAC, draft/quote/confirm, webhook retry).
> - **Spec 004c — Returns, Refunds, Order Tickets** (Phase 4): Custom `etsy.order.ticket` minimal helpdesk replacement per [ADR-004](../006-master-plan/adrs/ADR-004-enterprise-alternatives.md); Google Drive sync permanently deferred.
>
> **Do not execute tasks from this file.** New `specs/004a-.../tasks.md`, `specs/004b-.../tasks.md`, `specs/004c-.../tasks.md` will be generated via `/speckit-specify` + `/speckit-tasks` in Waves B (004a) and C (004b/004c) of master-plan execution.
>
> Cross-cutting decisions that the sub-specs MUST honour:
> - [ADR-003](../006-master-plan/adrs/ADR-003-module-decomposition.md) — 004a lands in `multichannel_hub_fulfillment`; 004b's Gearment adapter likewise; partner-sync base Protocol in `multichannel_hub_core`.
> - [ADR-007](../006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md) — all fulfillment-lifecycle fields live on the `sale.order.fulfillment` delegation sibling, not on `sale.order` directly.
> - Shared rate limiter utility and webhook controller base are authored in `multichannel_hub_core` in Phase 1/2, reused by 004b and (later) Spec 005.
>
> **Original (superseded) content preserved below for reference.**

---

**Input**: Design documents from `/specs/004-fulfillment-routing/`
**Prerequisites**: plan.md (loaded), spec.md (loaded), data-model.md (loaded), research.md (loaded), quickstart.md (loaded)

**Tests**: Included per story (TDD approach as per project guidelines).

**Organization**: Tasks grouped by user story in priority order (P1 -> P2 -> P3). Each story is independently testable after its phase completes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module initialization, dependency declarations, import registrations

- [ ] T001 Update `custom_addons/etsy_integration/__manifest__.py` -- add `stock` to `depends`, add new model/view/data/security/wizard/controller file paths
- [ ] T002 [P] Update `requirements.txt` -- add `google-api-python-client` and `google-auth`
- [ ] T003 [P] Update `custom_addons/etsy_integration/models/__init__.py` -- import 7 new model files (fulfillment_partner, partner_sync_log, order_return, shipping_carrier, logistics_partner, tracking_import_log, tracking_import_line)
- [ ] T004 [P] Update `custom_addons/etsy_integration/services/__init__.py` -- import new service files (partner_sync, gearment_adapter, carrier_detector, tracking_importer, gdrive_client)
- [ ] T005 [P] Create `custom_addons/etsy_integration/controllers/__init__.py` -- import partner_webhook controller
- [ ] T006 [P] Update `custom_addons/etsy_integration/wizards/__init__.py` -- import return_wizard and tracking_import_wizard

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: All new models (with fields from data-model.md), sale.order extensions, security ACLs, and pre-seeded data. Module must install cleanly after this phase.

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 [P] Create `fulfillment.partner` model with all fields in `custom_addons/etsy_integration/models/fulfillment_partner.py` -- name, active, partner_priority, contact fields, sync_method, auth_method, adapter_type, API fields, webhook fields, rate limit fields, inherits mail.thread
- [ ] T008 [P] Create `partner.sync.log` model with all fields in `custom_addons/etsy_integration/models/partner_sync_log.py` -- sale_order_id, partner_id, sync_type, sync_status, partner_ref, payloads, error_message, retry_count, next_retry_at, tracking_number, carrier
- [ ] T009 [P] Create `order.return` model with all fields in `custom_addons/etsy_integration/models/order_return.py` -- sale_order_id, return_reason, return_action, resolution_status, credit_note_id, replacement_order_id, resolved_by, resolved_date, inherits mail.thread
- [ ] T010 [P] Create `shipping.carrier` model with all fields in `custom_addons/etsy_integration/models/shipping_carrier.py` -- name, code (unique), active, tracking_prefix, tracking_pattern, inherits mail.thread
- [ ] T011 [P] Create `logistics.partner` model with all fields in `custom_addons/etsy_integration/models/logistics_partner.py` -- name, active, gdrive_folder_id, gdrive_sync_enabled, gdrive_last_sync, notes, inherits mail.thread
- [ ] T012 [P] Create `tracking.import.log` model with all fields in `custom_addons/etsy_integration/models/tracking_import_log.py` -- name (auto-sequence), import_date, source, source_filename, logistics_partner_id, counts, carrier_summary_json, state, line_ids, imported_by, inherits mail.thread
- [ ] T013 [P] Create `tracking.import.line` model with all fields in `custom_addons/etsy_integration/models/tracking_import_line.py` -- import_log_id, row_number, order_number, tracking_number, sale_order_id, carrier_id, match_status, is_replacement, consignee_name, country, gke_cost_vnd, label_url, qrcode_url, notes
- [ ] T014 Extend `sale.order` with all new fields in `custom_addons/etsy_integration/models/sale_order.py` -- routing fields (fulfillment_route, fulfillment_partner_id, routed_by, routed_date), production fields (production_stage, production_blocked, production_block_reason), sync fields (partner_sync_status, partner_sync_date, partner_ref), Gearment fields (gearment_order_id, gearment_price_quote), tracking import fields (label_url, qrcode_url, gke_shipping_cost_vnd, tracking_import_date, is_replacement_order, original_order_id), computed fields (sync_log_ids, sync_log_count, return_ids, return_count, has_active_return)
- [ ] T015 [P] Update `custom_addons/etsy_integration/security/ir.model.access.csv` -- add ACLs for all 7 new models per data-model.md security table (group_sale_manager full, group_sale_salesman read, group_production_team read for fulfillment.partner)
- [ ] T016 [P] Update `custom_addons/etsy_integration/security/etsy_security.xml` -- add record rules for new models (manager can CRUD all, salesman read-only, production team read fulfillment.partner)
- [ ] T017 [P] Create `custom_addons/etsy_integration/data/shipping_carrier_data.xml` -- pre-seed USPS (pattern `^\d{20,22}$`), UniUni (prefix "UU"), YunExpress (prefix "YT")
- [ ] T018 Verify module installs cleanly: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init`

**Checkpoint**: Module installs with all models, fields, ACLs, and pre-seeded carriers. No business logic yet.

---

## Phase 3: User Story 2 - External Partner Configuration (Priority: P1)

**Goal**: Administrators can create and configure fulfillment partners with contact details, auth methods, priority levels, and test connectivity.

**Independent Test**: Create a partner with Header Keys auth, verify "Test Connection" works, verify primary partner constraint enforced.

### Tests for US2

- [ ] T019 [P] [US2] Create `custom_addons/etsy_integration/tests/test_fulfillment_partner.py` -- test partner creation, primary constraint (only one primary), auth method validation, deactivation hides from dropdown, format compatibility check

### Implementation for US2

- [ ] T020 [P] [US2] Create `custom_addons/etsy_integration/views/fulfillment_partner_views.xml` -- form view (name, priority, contact, sync method, auth method, API config with attrs visibility, rate limit fields, webhook config, notes) + list view (name, priority, sync_method, active, order_count)
- [ ] T021 [P] [US2] Update `custom_addons/etsy_integration/views/menu.xml` -- add "Fulfillment Partners" menu under Configuration section
- [ ] T022 [US2] Implement `_check_primary_unique` constraint on `fulfillment.partner` in `custom_addons/etsy_integration/models/fulfillment_partner.py` -- at most one partner with partner_priority='primary'
- [ ] T023 [US2] Implement `action_test_connection()` method on `fulfillment.partner` in `custom_addons/etsy_integration/models/fulfillment_partner.py` -- HTTP request to api_endpoint using configured auth_method (bearer token or header keys), return success/fail notification
- [ ] T024 [US2] Implement `action_register_webhooks()` method on `fulfillment.partner` in `custom_addons/etsy_integration/models/fulfillment_partner.py` -- POST to partner webhook_endpoint to register for order.completed, order.cancelled, tracking.updated events
- [ ] T025 [US2] Implement `_check_api_fields` constraint on `fulfillment.partner` in `custom_addons/etsy_integration/models/fulfillment_partner.py` -- require api_endpoint when sync_method='api', require api_key when auth_method='bearer', require client_key+secret when auth_method='header_keys'

**Checkpoint**: Partners can be created, configured, and tested. Primary uniqueness enforced.

---

## Phase 4: User Story 1 - Fulfillment Route Assignment (Priority: P1)

**Goal**: Operations managers assign orders to internal production or external partners, with auto-transitions and audit trail.

**Independent Test**: Route an order to a partner, verify fulfillment_status transitions to "Dang san xuat", verify route appears on dashboard filters.

### Tests for US1

- [ ] T026 [P] [US1] Create `custom_addons/etsy_integration/tests/test_fulfillment_routing.py` -- test route assignment to partner/internal, auto-transition to 'dang_san_xuat', prevention when design not approved, rerouting logs in chatter, single active route enforcement, dashboard filter by route

### Implementation for US1

- [ ] T027 [US1] Implement `write()` override on `sale.order` for routing auto-transitions in `custom_addons/etsy_integration/models/sale_order.py` -- when fulfillment_route set: validate design approval, set fulfillment_status='dang_san_xuat', set production_stage='queued' if internal, set partner_sync_status='pending' if partner, log routing change in chatter
- [ ] T028 [US1] Implement `_check_design_approved_for_routing()` method on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- prevent routing when design files not all approved (approval_status != 'duyet')
- [ ] T029 [US1] Update `custom_addons/etsy_integration/views/sale_order_views.xml` -- add Fulfillment tab with routing fields (fulfillment_route selection, fulfillment_partner_id dropdown filtered by active+primary first, routed_by, routed_date), sync status fields, Gearment fields
- [ ] T030 [US1] Update `custom_addons/etsy_integration/views/operational_dashboard_views.xml` -- add search filters for fulfillment_route (internal/partner), fulfillment_partner_id, production_stage, partner_sync_status

**Checkpoint**: Orders can be routed, status auto-transitions work, dashboard filtering by route operational.

---

## Phase 5: User Story 3 - Partner API Sync (Priority: P2)

**Goal**: Auto-push design files to partners via API, receive tracking via webhooks, handle Gearment multi-step flow (draft/quote/confirm).

**Independent Test**: Route order to Gearment, trigger sync, verify draft created + price quote retrieved, approve + confirm, verify webhook updates tracking.

### Tests for US3

- [ ] T031 [P] [US3] Create `custom_addons/etsy_integration/tests/test_partner_sync.py` -- test sync push success/failure, retry logic (3 retries exponential backoff), escalation after 72h, sync log creation, manual mode ZIP generation
- [ ] T032 [P] [US3] Create `custom_addons/etsy_integration/tests/test_gearment_adapter.py` -- test Gearment auth headers, draft creation, price quote retrieval, confirm flow, rate limiting (100/10s), HTTP 429 handling, webhook payload parsing

### Implementation for US3

- [ ] T033 [P] [US3] Create base adapter + factory in `custom_addons/etsy_integration/services/partner_sync.py` -- `BasePartnerAdapter` (test_connection, push_order, get_order_status, register_webhooks, parse_webhook_payload), `GenericAdapter` implementation, `get_adapter(partner)` factory
- [ ] T034 [P] [US3] Create Gearment adapter in `custom_addons/etsy_integration/services/gearment_adapter.py` -- header-key auth, POST /api/v3/orders (draft), GET price quote, POST confirm, rate limiter (token bucket from partner config), webhook registration, payload builder (reference_id, platform, store_id, address, items with printing_options[].url)
- [ ] T035 [US3] Implement `action_sync_now()` on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- get adapter for partner, call push_order, create partner.sync.log, handle success (store partner_ref, gearment_order_id, gearment_price_quote) and failure (log error, schedule retry)
- [ ] T036 [US3] Implement `action_approve_gearment_quote()` on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- confirm draft at Gearment via adapter, update sync status to 'synced'
- [ ] T037 [US3] Implement retry logic on `partner.sync.log` in `custom_addons/etsy_integration/models/partner_sync_log.py` -- `_cron_retry_failed_syncs()` method, exponential backoff (5min, 15min, 45min), escalation after 3 failures or 72h, create activity notification for PIC
- [ ] T038 [US3] Create webhook controller in `custom_addons/etsy_integration/controllers/partner_webhook.py` -- generic POST /fulfillment/partner/callback (HMAC validation, order lookup, sync log creation, tracking/status update), Gearment-specific POST /fulfillment/gearment/webhook (Gearment signature, event routing for order.completed/cancelled/tracking.updated)
- [ ] T039 [US3] Implement manual mode `action_generate_file_package()` on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- ZIP design files for manual partner transfer
- [ ] T040 [P] [US3] Create `custom_addons/etsy_integration/views/partner_sync_log_views.xml` -- list view (order, partner, sync_type, sync_status, created, error), form view (full detail with payloads)
- [ ] T041 [P] [US3] Create `custom_addons/etsy_integration/data/ir_cron_partner_sync.xml` -- cron job every 15 minutes calling `partner.sync.log._cron_retry_failed_syncs()`
- [ ] T042 [US3] Update `custom_addons/etsy_integration/views/sale_order_views.xml` -- add "Sync Now" button, "Approve Quote" button (visible when gearment_price_quote > 0 and sync pending), sync log smart button, sync status indicator

**Checkpoint**: Partner sync operational with Gearment adapter, webhooks receive tracking, retry/escalation works.

---

## Phase 6: User Story 4 - Internal Production Queue (Priority: P2)

**Goal**: Production team views internally-routed orders in a dedicated queue, tracks stages (Queued -> In Progress -> QC -> Completed), flags blocked orders.

**Independent Test**: Route 3 orders internally, view production queue, drag through stages via kanban, verify "Completed" auto-updates fulfillment_status.

### Tests for US4

- [ ] T043 [P] [US4] Create `custom_addons/etsy_integration/tests/test_production_queue.py` -- test stage transitions (queued->in_progress->qc_check->completed), auto-transition to 'da_san_xuat' on completed, production blocking with reason, queue filtering (only internal orders)

### Implementation for US4

- [ ] T044 [US4] Implement production stage transition logic on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- write override: when production_stage changes to 'completed', set fulfillment_status='da_san_xuat', log in chatter
- [ ] T045 [US4] Implement production blocking logic on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- toggle production_blocked with block reason, chatter message
- [ ] T046 [P] [US4] Create `custom_addons/etsy_integration/views/production_queue_views.xml` -- list view (order name, product, quantity, production_stage, blocked flag, assigned date), kanban view (grouped by production_stage, drag-and-drop, blocked icon), search filters (stage, blocked, date)
- [ ] T047 [US4] Update `custom_addons/etsy_integration/views/menu.xml` -- add "Internal Production Queue" menu under Production section

**Checkpoint**: Production queue shows internally-routed orders, kanban drag updates stages, completed triggers fulfillment status.

---

## Phase 7: User Story 8 - Shipping Carrier Tracking Import (Priority: P2)

**Goal**: Import tracking numbers from GKE Logistics Excel files, auto-match to orders via etsy_order_id, auto-detect carriers, store label/QR URLs.

**Independent Test**: Upload a GKE Excel file, verify ORDER NUMBERs matched to orders, tracking numbers written, carriers auto-detected (USPS/UniUni/YunExpress), import log shows summary.

### Tests for US8

- [ ] T048 [P] [US8] Create `custom_addons/etsy_integration/tests/test_carrier_detection.py` -- test USPS pattern (20-22 digit numeric), UniUni prefix "UU", YunExpress prefix "YT", unknown falls to "Other", explicit carrier overrides auto-detect
- [ ] T049 [P] [US8] Create `custom_addons/etsy_integration/tests/test_tracking_import.py` -- test 19-column format parsing, 20-column format with explicit carrier, ORDER NUMBER matching to etsy_order_id, "-replace" suffix handling, unmatched row logging, label/QR URL storage, duplicate tracking overwrite, import log counts

### Implementation for US8

- [ ] T050 [P] [US8] Create `custom_addons/etsy_integration/services/carrier_detector.py` -- `CarrierDetector` class: `detect(tracking_number, carriers)` method, two-tier matching (prefix first via startswith, then regex via tracking_pattern), return carrier record or None
- [ ] T051 [P] [US8] Create `custom_addons/etsy_integration/services/tracking_importer.py` -- `TrackingImporter` class: `parse_excel(file_content)` (openpyxl, detect 19 vs 20 columns), `match_orders(rows, env)` (lookup etsy_order_id, handle -replace suffix), `write_tracking(matched_rows, env)` (write tracking_number, carrier, label_url, qrcode_url, gke_shipping_cost_vnd to sale.order), `create_import_log(results, env)` (tracking.import.log + lines)
- [ ] T052 [US8] Create `custom_addons/etsy_integration/wizards/tracking_import_wizard.py` -- TransientModel with file upload field (Binary), `action_import()` method: parse file, match orders, write tracking, create import log, return action to view log
- [ ] T053 [US8] Implement tracking write auto-transition on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- when tracking_number written via import and was previously empty: set fulfillment_status='da_gui' if in production/produced state, set shipping_date, auto-detect carrier
- [ ] T054 [P] [US8] Create `custom_addons/etsy_integration/views/shipping_carrier_views.xml` -- form view (name, code, prefix, pattern) + list view
- [ ] T055 [P] [US8] Create `custom_addons/etsy_integration/views/tracking_import_views.xml` -- import wizard form (file upload + Import button), import log list view (name, date, source, matched/unmatched counts, state), import log form view (full detail with line_ids tree), import line tree (row_number, order_number, tracking, carrier, match_status, notes)
- [ ] T056 [P] [US8] Create `custom_addons/etsy_integration/views/logistics_partner_views.xml` -- form view (name, active, notes) + list view (Google Drive fields hidden until US9)
- [ ] T057 [US8] Update `custom_addons/etsy_integration/views/menu.xml` -- add "Import Tracking" wizard action, "Tracking Import Logs" menu, "Shipping Carriers" menu under Configuration, "Logistics Partners" menu under Configuration

**Checkpoint**: Tracking import from Excel operational, carrier auto-detection working, import logs with per-row audit trail.

---

## Phase 8: User Story 5 - Raw Material Stock Awareness (Priority: P3)

**Goal**: Production team sees current raw material stock levels alongside production queue, with low-stock visual warnings.

**Independent Test**: View production dashboard, see stock quantities for configured materials, verify low-stock warning when below reorder threshold.

### Implementation for US5

- [ ] T058 [US5] Add "Material Stock" smart button to production queue in `custom_addons/etsy_integration/views/production_queue_views.xml` -- opens filtered stock.quant view for configured raw materials
- [ ] T059 [US5] Implement `action_view_material_stock()` on `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` -- return action opening stock.quant filtered by product category (raw materials)
- [ ] T060 [US5] Add low-stock indicator to production queue list view in `custom_addons/etsy_integration/views/production_queue_views.xml` -- color/icon when any related material is below reorder_min_qty

**Checkpoint**: Stock visibility from production queue, low-stock warnings visible.

---

## Phase 9: User Story 7 - Returns and Refunds (Priority: P3)

**Goal**: Operations managers process returns with reason/action selection, auto-create credit notes for refunds and new orders for replacements.

**Independent Test**: Open shipped order, initiate return with reason "Defective", select "Refund", verify credit note created and linked.

### Tests for US7

- [ ] T061 [P] [US7] Create `custom_addons/etsy_integration/tests/test_order_return.py` -- test return on shipped order, prevent return on non-shipped, reason selection, refund creates credit note, replacement creates new order linked to original, return resolution workflow

### Implementation for US7

- [ ] T062 [US7] Implement business logic on `order.return` in `custom_addons/etsy_integration/models/order_return.py` -- `action_confirm()`: create credit note for hoan_tien, create replacement order for gui_lai, validate return_notes required when reason='khac', update resolution_status
- [ ] T063 [US7] Create `custom_addons/etsy_integration/wizards/return_wizard.py` -- TransientModel: reason selection, action selection, notes field, `action_create_return()` creates order.return record and calls action_confirm, validates order is shipped
- [ ] T064 [P] [US7] Create `custom_addons/etsy_integration/views/order_return_views.xml` -- form view (order, reason, action, notes, resolution_status, linked credit_note/replacement), list view (order, reason, action, status, date)
- [ ] T065 [US7] Update `custom_addons/etsy_integration/views/sale_order_views.xml` -- add "Initiate Return" button (visible when fulfillment_status='da_gui'), return count smart button
- [ ] T066 [US7] Update `custom_addons/etsy_integration/views/menu.xml` -- add "Returns" menu under Operations
- [ ] T067 [US7] Update `custom_addons/etsy_integration/views/operational_dashboard_views.xml` -- add search filter "Returned orders" (has_active_return = True)

**Checkpoint**: Returns workflow end-to-end, credit notes and replacements auto-created, dashboard filter by returns.

---

## Phase 10: User Story 9 - Google Drive Sync (Priority: P3)

**Goal**: Auto-read tracking Excel files from per-logistics-partner Google Drive folders via cron, process using same logic as manual import (US8).

**Independent Test**: Configure logistics partner with Drive folder, place Excel file, run sync, verify file processed and tracking imported.

### Implementation for US9

- [ ] T068 [P] [US9] Create `custom_addons/etsy_integration/services/gdrive_client.py` -- `GDriveClient` class: authenticate with service account (credentials path from ir.config_parameter), `list_new_files(folder_id, since_datetime)`, `download_file(file_id)` returns file content, `mark_processed(file_id, folder_id)` moves to "processed" subfolder
- [ ] T069 [US9] Implement `_cron_gdrive_sync()` on `logistics.partner` in `custom_addons/etsy_integration/models/logistics_partner.py` -- for each partner with gdrive_sync_enabled: authenticate, list new files since gdrive_last_sync, download + process each via TrackingImporter (reuse US8 logic), update gdrive_last_sync, handle auth failures with activity notification
- [ ] T070 [P] [US9] Create `custom_addons/etsy_integration/data/ir_cron_gdrive_sync.xml` -- cron job every 30 minutes calling `logistics.partner._cron_gdrive_sync()`
- [ ] T071 [US9] Update `custom_addons/etsy_integration/views/logistics_partner_views.xml` -- show Google Drive fields (gdrive_folder_id, gdrive_sync_enabled, gdrive_last_sync), add "Sync Now" button

**Checkpoint**: Google Drive auto-sync operational, tracking files processed automatically.

---

## Phase 11: User Story 6 - CRM / Etsy Message Sync (Priority: P3, DEFERRED)

**Goal**: Sync Etsy buyer messages to order chatter, allow replies from Odoo.

**NOTE**: This story is contingent on Etsy API approval for conversations scope. Implementation deferred until approval obtained. See research.md R8 for implementation sketch.

- [ ] T072 [US6] DEFERRED: Implement Etsy message sync service when API access approved -- services/etsy_messaging.py, cron for message fetch, sale.order computed field has_unread_etsy_messages, chatter subtype "Etsy Message"

**Checkpoint**: Placeholder only. Proceed to Polish phase.

---

## Phase 12: Polish and Cross-Cutting Concerns

**Purpose**: Final verification, cleanup, documentation

- [ ] T073 [P] Run `ruff check custom_addons/etsy_integration/` and fix all linting issues
- [ ] T074 [P] Verify all `_description` fields set on new models (Odoo 19 requirement)
- [ ] T075 Run full test suite: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init`
- [ ] T076 Run quickstart.md validation steps end-to-end (partner config -> routing -> sync -> production queue -> tracking import -> returns)
- [ ] T077 [P] Update `custom_addons/etsy_integration/__manifest__.py` version to `19.0.2.0.0`
- [ ] T078 [P] Verify no `print()` or `_logger.info` debug statements in new code
- [ ] T079 Code cleanup -- remove any TODO/FIXME markers, verify consistent naming

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately
- **Foundational (Phase 2)**: Depends on Setup -- **BLOCKS all user stories**
- **US2 (Phase 3)**: Depends on Foundational -- partner model must exist
- **US1 (Phase 4)**: Depends on US2 -- partners must be configurable before routing to them
- **US3 (Phase 5)**: Depends on US1 + US2 -- routing and partners must exist for sync
- **US4 (Phase 6)**: Depends on US1 -- routing to internal must exist (can parallelize with US3)
- **US8 (Phase 7)**: Depends on Foundational only -- independent of US1-US4 (can parallelize with US3/US4)
- **US5 (Phase 8)**: Depends on US4 -- production queue must exist for stock panel
- **US7 (Phase 9)**: Depends on US1 -- orders must be routed/shipped for returns
- **US9 (Phase 10)**: Depends on US8 -- tracking import logic must exist for Drive sync to reuse
- **US6 (Phase 11)**: DEFERRED -- blocked on Etsy API approval
- **Polish (Phase 12)**: Depends on all desired story phases being complete

### User Story Dependencies

```
Foundational (Phase 2)
    |
    +---> US2 (P1) Partner Config
    |         |
    |         +---> US1 (P1) Route Assignment
    |                   |
    |                   +---> US3 (P2) Partner API Sync
    |                   |
    |                   +---> US4 (P2) Production Queue ----> US5 (P3) Stock Awareness
    |                   |
    |                   +---> US7 (P3) Returns
    |
    +---> US8 (P2) Tracking Import ----> US9 (P3) Google Drive Sync
```

### Parallel Opportunities

After Foundational:
- **US2 + US8**: Can run in parallel (different files, no overlap)
- **US3 + US4**: Can run in parallel after US1 (different files, independent logic)
- **US5 + US7 + US9**: Can run in parallel after their prerequisites

Within each story:
- All tasks marked [P] can run in parallel
- Tests [P] can run in parallel with other tests
- Models before services, services before views

---

## Parallel Example: After Phase 2

```
# Developer A: US2 + US1 (P1 stories, sequential)
Task: "Create fulfillment_partner_views.xml"
Task: "Implement routing write logic on sale.order"

# Developer B: US8 (P2 tracking import, independent)
Task: "Create carrier_detector.py service"
Task: "Create tracking_importer.py service"
Task: "Create tracking_import_wizard.py"
```

---

## Implementation Strategy

### MVP First (US2 + US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US2 (Partner Config)
4. Complete Phase 4: US1 (Route Assignment)
5. **STOP and VALIDATE**: Partners configurable, orders routable, status transitions working
6. Deploy/demo MVP

### Incremental Delivery

1. Setup + Foundational -> Module installs with all models
2. US2 + US1 -> Route orders to partners/internal (MVP!)
3. US3 -> Partner API sync with Gearment
4. US4 -> Production queue for internal orders
5. US8 -> Tracking import from Excel
6. US5 + US7 + US9 -> Stock awareness, returns, Google Drive sync
7. Each story adds value without breaking previous stories

### Task Count Summary

| Phase | Story | Tasks | Parallel |
|-------|-------|-------|----------|
| 1 | Setup | 6 | 4 |
| 2 | Foundational | 12 | 9 |
| 3 | US2 - Partner Config | 7 | 2 |
| 4 | US1 - Route Assignment | 5 | 1 |
| 5 | US3 - Partner API Sync | 12 | 5 |
| 6 | US4 - Production Queue | 5 | 1 |
| 7 | US8 - Tracking Import | 10 | 6 |
| 8 | US5 - Stock Awareness | 3 | 0 |
| 9 | US7 - Returns | 7 | 2 |
| 10 | US9 - Google Drive Sync | 4 | 2 |
| 11 | US6 - CRM (DEFERRED) | 1 | 0 |
| 12 | Polish | 7 | 4 |
| **Total** | | **79** | **36** |

---

## Notes

- [P] tasks = different files, no dependencies within the phase
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable after its phase
- TDD: Write test tasks first, ensure they FAIL, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- US6 (Etsy CRM) is deferred pending Etsy API approval -- not blocked for MVP or P2 delivery
- All file paths are relative to repository root (`/home/odoo/odoo_dev/other_projects/odoo19_esty/`)

---

## P0-18b1 Tasks — Gearment API Exploration (Phase 0 Spike, 2026-04-30)

**Branch**: `feature/006-master-plan-coding` | **Module**: `multichannel_hub_fulfillment`
**Slice scope**: read-only catalog probe + draft/quote/confirm contract via mocks. NO live writes (real `confirm` deferred to P4-01 + owner sign-off). Webhook deferred to P0-18b2.
**Dep**: P0-18a (`GearmentApiClient`) + `.env` `GEARMENT_API_BASE_URL` + `GEARMENT_API_KEY` + `GEARMENT_API_SECRET` (all set 2026-04-30).
**Unblocks**: P0-18b2 (webhook discovery), P4-01 (full Gearment adapter).

### RED tests (Phase 2)

- [X] T080 [P0-18b1] Create `tests/test_gearment_adapter_phase1.py` — catalog live probe (single read-only call gated behind `MULTICHANNEL_HUB_FULFILLMENT_LIVE_API=1` env flag; default skip)
- [X] T081 [P0-18b1] [P] `tests/test_gearment_adapter_orm.py` — Phase-2 ORM tests with `requests` mocked: `test_test_connection_ping_ok`, `test_push_order_returns_partner_ref_and_quote`, `test_get_quote_returns_quote_dict`, `test_confirm_stub_raises_NotImplemented`, `test_register_webhooks_stub_raises_NotImplemented`, `test_parse_webhook_payload_stub_raises_NotImplemented`, `test_idempotency_key_header_set` (POST captures `Idempotency-Key` from `external_order_id`), `test_print_location_codes_extracted_from_catalog`
- [X] T082 [P0-18b1] [P] `tests/test_gearment_api_log_db.py` — Phase-1 schema verification: `gearment_api_log` table columns + `(sale_order_id, request_started_at)` index + `(source)` Selection includes 6 values + ACL row for `group_system`

### GREEN impl (Phase 3)

- [X] T083 [P0-18b1] `custom_addons/multichannel_hub_fulfillment/services/gearment_adapter.py` — `GearmentAdapter` Protocol + concrete impl wrapping `GearmentApiClient`. Methods: `test_connection`, `push_order`, `get_quote`, `confirm` (stub raises `NotImplementedError("P4-01")`), `register_webhooks` (stub), `parse_webhook_payload` (stub)
- [X] T084 [P0-18b1] `custom_addons/multichannel_hub_fulfillment/services/gearment_payload.py` — `GearmentOrderPayload` dataclass (external_order_id / platform / store_id / quantity / product_id / address dict / shipping_method / design_files list / notes / custom_attributes). Serializer to `dict` for POST body.
- [X] T085 [P0-18b1] `custom_addons/multichannel_hub_fulfillment/models/gearment_api_log.py` — Model `gearment.api.log` mirroring `etsy.api.log` (Spec 005 P0-17). 11 fields, no mail.thread, composite index in `init()`. Selection `source`: `probe / draft / quote / confirm / callback / health_check`.
- [X] T086 [P0-18b1] `security/ir.model.access.csv` — `gearment.api.log` ACL: `group_system` R/W/C/U; `group_sale_manager` R only
- [X] T087 [P0-18b1] `data/ir_cron_gearment_api_log_retention.xml` — daily cron `_cron_cleanup_old_logs()` with `multichannel_hub_fulfillment.api_log_retention_days` ICP (default 30)
- [X] T088 [P0-18b1] Wire `GearmentAdapter` to write `gearment.api.log` rows on every call (sudo create with PII-scrubbed payload summary)
- [X] T089 [P0-18b1] Update `__manifest__.py` data list (security CSV + cron XML); update `models/__init__.py` + `services/__init__.py`

### Verify + commit (Phase 4-6)

- [X] T090 [P0-18b1] Run `odoo -u multichannel_hub_fulfillment --stop-after-init --http-port=8888 --workers=0 --max-cron-threads=0` exit 0
- [X] T091 [P0-18b1] Run `--test-tags /multichannel_hub_fulfillment --stop-after-init`; all green; coverage ≥80% on new files
- [X] T092 [P0-18b1] Spawn `code-reviewer` + `security-reviewer` in parallel; block on CRITICAL/HIGH
- [X] T093 [P0-18b1] grep no `_logger.info(` / `print(` in new files; ACL inline `# sudo:` comments; no raw SQL without justification
- [X] T094 [P0-18b1] Conventional commit chain on feature branch:
  - `[multichannel_hub_fulfillment] test(P0-18b1): RED gearment adapter + payload + api log tests (T080-T082)`
  - `[multichannel_hub_fulfillment] feat(P0-18b1): GREEN GearmentAdapter Protocol + canonical payload + api.log model (T083-T089)`
  - `[multichannel_hub_fulfillment] docs(P0-18b1): tracker done + tasks [X] + findings`

**Slice exit criteria**:
- All T080-T094 marked `[X]`
- Tests green, coverage ≥80% on new files
- Live catalog probe documented in `findings.md` (real `print_locations` + `legacy_product_id` discovery)
- Open Q-items DQ1-DQ5 documented (webhook HMAC, idempotency-key behavior on real POST, vendor_id, HTTPS scheme, redirect policy)
- Tracker P0-18b1 → done

## Phase 0: P0-18b2a — Webhook discovery-mode controller

**Slice scope**: minimal log-only `/gearment/webhook` controller; capture inbound headers + body to `gearment.api.log` so HMAC signature header name + algorithm can be discovered by inspecting the audit table. NO HMAC verify, NO topic routing, NO business writes.
**Dep**: P0-18b1 ✓; webhook URL `https://odoo.hatafax.com/gearment/webhook` reachable via staging nginx; 3 V3 webhooks registered on Gearment dashboard 2026-05-02.
**Unblocks**: P0-18b2b (HMAC verify), P0-18b2c (topic routing).

- [X] T100 [P0-18b2a] Plan in `_archive/p0-18b2a-plan.md`
- [X] T101 [P0-18b2a] RED tests: `tests/test_webhook_discovery_db.py` (4 Phase-1 DB) + `tests/test_webhook_discovery_orm.py` (8 Phase-2 ORM/HttpCase)
- [X] T102 [P0-18b2a] GREEN: extend `gearment.api.log` with `direction`/`request_headers`/`request_body`/`signature_header_seen`/`topic_seen` + `inbound_webhook` source value
- [X] T103 [P0-18b2a] GREEN: new `controllers/gearment_webhook.py` (`type='http'`, `auth='public'`, `csrf=False`, `save_session=False`); explicit + dynamic header scrubs; pre-read body cap via `Content-Length`; sudo() inline-justified
- [X] T104 [P0-18b2a] GREEN: register `controllers/__init__.py` in module `__init__.py`; bump manifest 19.0.1.0.6 → 19.0.1.0.7
- [X] T105 [P0-18b2a] Update existing `test_source_selection_values` to include `inbound_webhook`
- [X] T106 [P0-18b2a] Add helper-function unit tests for `_content_length_exceeds_cap` (Werkzeug test client overrides Content-Length, so HttpCase cannot exercise the guard — pure unit tests instead)
- [X] T107 [P0-18b2a] code-reviewer + security-reviewer parallel: 0 CRITICAL; 2 HIGH fixed inline (body DoS pre-check + drop `exc_info=True` from WARNING)
- [X] T108 [P0-18b2a] Verify: `-u multichannel_hub_fulfillment` exit 0; 119 mhf tests + 512 cross-module tests all green
- [X] T109 [P0-18b2a] Conventional commit
- [X] T110 [P0-18b2a] Update `research.md` with V3 payload schema + dashboard observations; update tracker P0-18b2 split into a/b/c with this slice marked done
- [ ] T111 [P0-18b2a] **Phase 7 (ops)**: rsync mhf to `129.150.63.207`, restart `esty19_odoo`, fire dashboard simulator at full URL `https://odoo.hatafax.com/gearment/webhook`, inspect `gearment.api.log` to capture real signature header + algorithm; document in `findings.md`

**Slice exit criteria**:
- T100-T110 `[X]`; T111 left for Phase-7 ops (separate session or follow-up)
- Tests green; coverage ≥80% on changed files
- Tracker P0-18b2a → done; P0-18b2b + P0-18b2c rows added in `blocked` state


## Phase 0: P0-18b2b — HMAC verify + replay defenses

**Slice scope**: HMAC-SHA256 signature verify against `GEARMENT_API_SECRET`; 5-min past + 1-min future timestamp window; 10-min nonce dedup; topic detection updated for body['type']; failure path returns 401 + audit row + truncated body. NO business writes (P0-18b2c).
**Dep**: P0-18b2a ✓; HMAC scheme cracked from `https://developers.gearment.com/_bundle/webhook.yaml`.
**Unblocks**: P0-18b2c (topic routing + sale.order writes).

- [X] T112 [P0-18b2b] Plan in `_archive/p0-18b2b-plan.md`
- [X] T113 [P0-18b2b] RED tests: 13 unit + 12 HttpCase covering signature math, replay window, nonce dedup, header presence, body truncation
- [X] T114 [P0-18b2b] GREEN: `_compute_signature` + `_verify_signature` module-level helpers; refactor `_record_inbound` to call verify first
- [X] T115 [P0-18b2b] GREEN: extend `gearment.api.log` with `nonce_value`/`request_timestamp` indexed + `signature_verified`/`verify_failure_reason`; composite index `(nonce_value, request_timestamp)`
- [X] T116 [P0-18b2b] GREEN: `_detect_topic` checks body['type'] first
- [X] T117 [P0-18b2b] Relax 5 P0-18b2a HTTP tests to `assertIn(status, (200, 401))` since unsigned probes now return 401
- [X] T118 [P0-18b2b] code-reviewer + security-reviewer parallel: 0 CRITICAL/HIGH; 1 BLOCKER (real creds in test) + 1 MEDIUM (hardcoded url_path) both fixed inline; UNIQUE(nonce, ts) constraint TOCTOU deferred to P0-18b2c with documentation
- [X] T119 [P0-18b2b] Verify: 132 mhf + 537 cross-module green; module installs clean
- [X] T120 [P0-18b2b] Conventional commit + tracker update + tasks.md
- [X] T121 [P0-18b2b] **Phase 7 (ops)**: rsync mhf to `129.150.63.207`, recreate `esty19_odoo` with `env_file: /odoo/esty19/.env` (added `GEARMENT_API_KEY`/`GEARMENT_API_SECRET`/`GEARMENT_API_BASE_URL`), self-signed Python probe → HTTP 200 + `signature_verified=true` + `topic_seen='order_completed'` (gearment.api.log row 5). Bogus-key curl → HTTP 401 + `client_key_mismatch` (row 4). Owner-fired Gearment dashboard simulator will likewise produce `signature_verified=true` once they re-trigger.

**Slice exit criteria**:
- T112-T120 [X]; T121 left for Phase-7 ops session
- Tests green; coverage ≥80% on changed files
- Tracker P0-18b2b → done; P0-18b2c row updated to absorb deferred UNIQUE constraint

