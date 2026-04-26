# Tasks: Etsy Config Fixes

**Input**: Design documents from `/specs/002-etsy-config-fixes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Regenerated**: 2026-04-19 to cover 2026-04-10 plan revisions (R4/R5/R8/R9/R10) and master-plan §7 alignment. Previous tasks.md backed up as `tasks.md.pre-regen-2026-04-19`.

**MVP slice landed 2026-04-26** on branch `002-etsy-config-fixes-mvp`: T001–T024 done (Phases 1–4: setup, foundational, US1, US2). Verified end-to-end against fixture `tests/data/sample_single_order.txt`: order goes parser → sale.order with full financial config → auto-confirmed → picking done → `invoice_status='invoiced'`, no `account.move` generated (per R5). Deferred: T025–T067 (US3–US10, migration wizard for 17K backlog) — next slice.

**Spec deviations to reconcile**:
- T002: dropped `use_quotations` from `team_etsy` — field removed in Odoo 19 (`crm.team`); team works with default settings.
- T005: only registered the 3 XML data files that exist in this slice (`etsy_shipping_product.xml`, `etsy_fiscal_data.xml`, `etsy_product_categories.xml`) plus `etsy_sync_health_views.xml` (added in T007). The wizard / discount / res_users views remain unregistered until their owning user stories land.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US6)
- Exact file paths included in all task descriptions
- **[R#]**: Cross-reference to research.md / plan.md research item (R1-R10)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create data files and module scaffolding needed by all user stories

- [x] T001 Create shipping service product data file in `custom_addons/etsy_integration/data/etsy_shipping_product.xml`
- [x] T002 [P] Create fiscal position, tax, payment term, sales team, and pricelists data file in `custom_addons/etsy_integration/data/etsy_fiscal_data.xml`
- [x] T003 [P] Create product category hierarchy data file in `custom_addons/etsy_integration/data/etsy_product_categories.xml`
- [x] T004 [P] Create product category keyword mapping in `custom_addons/etsy_integration/data/product_category_keywords.json`
- [x] T005 Update `custom_addons/etsy_integration/__manifest__.py` to version `19.0.2.0.0` and include all new data files in the `data` list (etsy_shipping_product.xml, etsy_fiscal_data.xml, etsy_product_categories.xml, etsy_sync_health_views.xml, data_migration_wizard_views.xml, etsy_discount_views.xml, res_users_views.xml)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure (observability, anomaly detection, categorizer, helpers) required by every user story. No user-story work may begin until this phase is complete.

### Observability (R8)

- [x] T006 [R8] Create `etsy.sync.health` model in `custom_addons/etsy_integration/models/etsy_sync_health.py` with fields: `name` (unique), `state` (idle/running/ok/warning/error), `last_run_at`, `last_successful_run_at`, `last_run_row_count`, `last_run_error_count`, `last_error_message`, `last_processed_id`, `notes`; plus classmethod `report_run(integration_name, *, row_count=None, error_count=None, error_message=None, last_id=None, state=None)` that upserts the row
- [x] T007 [R8] Create sync-health views in `custom_addons/etsy_integration/views/etsy_sync_health_views.xml` — list view with `decoration-danger`/`-warning`/`-success` on `state`, form view (readonly except `notes`), and menu item "Sync Health" under the Etsy menu
- [x] T008 [R8] Add `etsy.sync.health` ACL rows to `custom_addons/etsy_integration/security/ir.model.access.csv` — read for `base.group_user`, full for `sales_team.group_sale_manager`
- [x] T009 Update `custom_addons/etsy_integration/models/__init__.py` to import `etsy_sync_health`

### Price anomaly field (R9)

- [x] T010 [R9] Add `etsy_price_anomaly` Boolean computed field (indexed, stored) to `custom_addons/etsy_integration/models/sale_order.py` with `@api.depends('amount_total')` — `True` when `amount_total <= 0` on an Etsy order

### Services + helpers

- [x] T011 Create product categorizer service in `custom_addons/etsy_integration/services/product_categorizer.py` — loads `data/product_category_keywords.json` at init, method `categorize(product_name) -> product.category` returns first keyword match or "Uncategorized" fallback, case-insensitive
- [x] T012 [P] Add multi-currency `_parse_price(text)` method to `custom_addons/etsy_integration/services/order_creator.py` — detects `$`, `EUR`, `GBP`, `€`, `£` symbols/prefixes, returns `(amount, currency_code)` tuple, defaults to EUR when no symbol; replaces `_parse_eur()`
- [x] T013 [P] Add helper methods to `custom_addons/etsy_integration/services/order_creator.py`: `_get_shipping_product()`, `_get_fiscal_position()`, `_get_payment_term()`, `_get_sales_team()`, `_get_pricelist(currency_code)` — each looks up its XML record by xmlid, caches the result on the service
- [x] T014 Update `custom_addons/etsy_integration/services/__init__.py` to import `product_categorizer`

**Checkpoint**: Foundation ready — sync.health, anomaly field, categorizer, and helper methods are available; user-story work may begin in parallel.

---

## Phase 3: User Story 1 — Correct Financial Data (Priority: P1) 🎯 MVP

**Goal**: All orders show correct prices (EUR and USD), shipping as line items, fiscal position, payment term, sales team, currency.

**Independent Test**: Import 10 orders (5 EUR, 5 USD) via wizard and verify `amount_total`, `currency_id`, fiscal position, payment term, sales team, pricelist all match the Excel source.

### Implementation

- [x] T015 [US1] Update `process_parse_result()` in `custom_addons/etsy_integration/services/order_creator.py` to set `fiscal_position_id`, `payment_term_id`, `team_id`, `pricelist_id`, `currency_id` on order vals (uses helpers from T013)
- [x] T016 [US1] Update `process_parse_result()` in `custom_addons/etsy_integration/services/order_creator.py` to add an Etsy Shipping service line when `shipping_cost > 0`
- [x] T017 [US1] Update `process_parse_result()` in `custom_addons/etsy_integration/services/order_creator.py` to call `_parse_price()` (T012) and set the order's `currency_id` to the detected currency — *note: email_parser is EUR-only by design (ADR-008 maintenance mode), so the email path defaults to EUR; multi-currency detection runs on the wizard path (T018/T019).*
- [x] T018 [US1] Update `_parse_eur_price()` → `_parse_price()` in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` to detect USD/GBP currencies and return `(amount, currency_code)`
- [x] T019 [US1] Update `_create_order_from_rows()` in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` to add shipping line, set fiscal position, payment term, sales team, pricelist, currency
- [x] T020 [US1] Write test for multi-currency price parsing in `custom_addons/etsy_integration/tests/test_multi_currency_parsing.py` — EUR/USD/GBP detection, fallback to EUR, corrupted values *(12 cases pass)*

**Checkpoint**: New imports produce orders with correct financial configuration.

---

## Phase 4: User Story 2 — Order Confirmation Workflow (Priority: P1)

**Goal**: Historical orders can be confirmed and deliveries auto-completed to "done" state; no phantom "to invoice" records (R5).

**Independent Test**: Confirm a batch of draft orders and verify `stock.picking` records exist in `done` state and `invoice_status='invoiced'`.

### Implementation

- [x] T021 [US2] Add `auto_confirm` Boolean field (default `True`) to `custom_addons/etsy_integration/wizards/import_orders_wizard.py`
- [x] T022 [US2] [R5] Add auto-confirm logic in `action_import()` in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` — after order creation call `action_confirm()`, validate picking to `done`, **then `order.write({'invoice_status': 'invoiced'})` directly** to prevent phantom "to invoice" state. *Implemented as `sale.order._etsy_auto_confirm()` helper so the cron path (T024) shares the same logic.*
- [x] T023 [US2] Add `etsy_auto_confirm_email` Boolean (default `False`) to `custom_addons/etsy_integration/models/res_config_settings.py` for email cron toggle
- [x] T024 [US2] Update `_cron_fetch_etsy_emails()` in `custom_addons/etsy_integration/models/sale_order.py` to optionally auto-confirm based on the setting

**Checkpoint**: Import wizard auto-confirms orders and marks them invoiced; cron has a configurable toggle.

---

## Phase 5: User Story 3 — Product Configuration (Priority: P2)

**Goal**: Products created as storable with proper category assignment.

**Independent Test**: Import an order with a new product, verify `is_storable=True` and correct category.

### Implementation

- [X] T025 [US3] Update `find_or_create_product()` in `custom_addons/etsy_integration/services/order_creator.py` to set `is_storable=True` on new products
- [X] T026 [US3] Update `find_or_create_product()` in `custom_addons/etsy_integration/services/order_creator.py` to call `product_categorizer.categorize()` (T011) and set `categ_id`
- [X] T027 [US3] Write test for product categorizer in `custom_addons/etsy_integration/tests/test_product_categorizer.py` — keyword matching, fallback to uncategorized, case-insensitivity

**Checkpoint**: New products are storable and categorized.

---

## Phase 6: User Story 4 — Improved Customer Dedup (Priority: P2)

**Goal**: Customer matching works reliably even without email/phone data for new imports. Historical dedup is BA-approved CSV only (Phase 8 / R10).

**Independent Test**: Import two orders from the same buyer with the same address; verify a single `res.partner` record.

### Implementation

- [X] T028 [US4] Update `find_or_create_partner()` in `custom_addons/etsy_integration/services/order_creator.py` — tier 1 email, tier 2 normalized name+address+city+zip (strip accents, lowercase, trim), tier 3 name+zip
- [X] T029 [US4] Update `_resolve_state()` in `custom_addons/etsy_integration/services/order_creator.py` — search by state `code` first (e.g., "CA"), then fall back to `name` ilike
- [X] T030 [US4] Expand country-name overrides in `custom_addons/etsy_integration/services/order_creator.py` for all 48 countries in the dataset (Czechia → Czech Republic, Republic of Korea → South Korea, etc.)

**Checkpoint**: Customer dedup handles no-email scenarios for new imports; state/country resolution improved.

---

## Phase 7: User Story 5 — Import Wizard Robustness (Priority: P2)

**Goal**: Wizard uses header-based column mapping and savepoint batching.

**Independent Test**: Import Excel with reordered columns; kill mid-import and verify no orphaned records.

### Implementation

- [ ] T031 [US5] [R6] Replace all `_COL_*` constants with header-based mapping in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` — read first row, build `{normalized_header: index}` dict, fail fast if required headers (TRANSACTION_ID, ORDER_ID, PRODUCT_NAME, PRICE, QUANTITY) are missing
- [ ] T032 [US5] [R4] Replace `self.env.cr.commit()` with `self.env.cr.savepoint()` per **500-order batch** (not 100) in `custom_addons/etsy_integration/wizards/import_orders_wizard.py`; log failing batch IDs to `etsy.sync.health` via `report_run()`
- [ ] T033 [US5] Add `warning_count` and `validation_notes` fields to `custom_addons/etsy_integration/wizards/import_orders_wizard.py` — tracks zero-price warnings, unparseable values, missing headers
- [ ] T034 [US5] Write test for header-based mapping in `custom_addons/etsy_integration/tests/test_import_wizard_headers.py` — column reordering, missing required header, missing optional header

**Checkpoint**: Wizard robust against column reordering and partial failures.

---

## Phase 8: User Story 6 — Data Migration Wizard (Priority: P1)

**Goal**: One-click, resumable wizard to remediate all 17,659 existing orders with full observability, anomaly quarantine, and BA-approved dedup.

**Independent Test**: Run wizard on full database, kill worker mid-run, re-run with `resume_from_checkpoint=True`, verify all counts match expectations and idempotency holds.

### Wizard model + core (R4/R5/R8/R9/R10)

- [ ] T035 [US6] Create `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — TransientModel `etsy.data.migration.wizard` with fields: `excel_file` (Binary), `excel_filename` (Char), `auto_confirm` (Boolean, default True), `fix_shipping_lines` (Boolean, default True), `fix_financial_config` (Boolean, default True), `fix_product_config` (Boolean, default True), `generate_dedup_report` (Boolean, default True), `include_anomalies` (Boolean, default False, R9), `resume_from_checkpoint` (Boolean, default True, R4), `batch_size` (Integer, default 500, R4), `last_processed_id` (Integer, readonly, R4), `sync_health_id` (Many2one `etsy.sync.health`, R8), `status_message` (Text, readonly)
- [ ] T036 [US6] [R9] Implement `_quarantine_anomalies()` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — flags `etsy_price_anomaly=True` on orders with `amount_total <= 0`, exports them to `/tmp/etsy_anomalies_<timestamp>.csv` (transaction_id, order_id, shop, raw_price), returns count. Idempotent.
- [ ] T037 [US6] [R4] Implement batched iteration in `action_migrate()` — builds domain (add `('id','>', last_processed_id)` when resuming and `('etsy_price_anomaly','=', include_anomalies)` always), iterates in `batch_size`-sized chunks ordered by `id`, each chunk inside `env.cr.savepoint()`, updates `last_processed_id` after each successful chunk
- [ ] T038 [US6] [R8] In `action_migrate()` call `etsy.sync.health.report_run('data_migration', state='running', last_id=0)` at start and update after each batch (row_count/error_count/last_id); finalize to `ok`/`warning`/`error` at end based on error ratio (<5% = warning, ≥5% = error); set `sync_health_id` on the wizard
- [ ] T039 [US6] Implement `_fix_financial_config(orders)` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — batch-sets `fiscal_position_id`, `payment_term_id`, `team_id`, `pricelist_id`, `currency_id` on all Etsy orders (uses helpers from T013)
- [ ] T040 [US6] Implement `_fix_shipping_lines(orders)` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — adds Etsy Shipping line to orders with `etsy_shipping_cost > 0` and no existing shipping line; idempotent check by product_id
- [ ] T041 [US6] Implement `_fix_prices_from_excel(orders)` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — re-parses USD prices from uploaded Excel (openpyxl), matches by `etsy_transaction_id`, updates `price_unit` and `currency_id` (only when current `price_unit == 0`)
- [ ] T042 [US6] Implement `_fix_product_config(products)` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — sets `is_storable=True`, runs categorizer on all Etsy products touched in the current batch
- [ ] T043 [US6] [R5] Implement `_confirm_and_complete(orders)` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — confirms draft orders, validates `stock.picking` to `done`, **then writes `invoice_status='invoiced'` directly** (do NOT generate invoices); idempotent — skips orders already in `sale`/`done` state
- [ ] T044 [US6] [R10] Implement `_generate_dedup_report(partners)` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — finds Etsy partner clusters by normalized name+address+city+zip, writes `/tmp/proposed_partner_merges_<timestamp>.csv` with columns `keep_partner_id,keep_name,merge_partner_id,merge_name,confidence,reason`. **Never modifies partners.**
- [ ] T045 [US6] [R10] Implement `action_apply_merges()` in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — reads a BA-approved CSV (file upload field `approved_merges_file`), iterates per-row inside `env.cr.savepoint()`, merges using `res.partner.merge_selected_contact_ids()` pattern; logs each merge to sync.health
- [ ] T046 [US6] Implement `action_migrate()` orchestration in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` — calls `_quarantine_anomalies()` first, then loops batches invoking the `_fix_*` and `_confirm_and_complete` helpers (gated by checkbox fields), finalizes sync.health, writes summary counts to `status_message`
- [ ] T047 [US6] Create wizard view in `custom_addons/etsy_integration/views/data_migration_wizard_views.xml` — form with checkboxes, file upload, `batch_size`, `include_anomalies`, `resume_from_checkpoint`, `last_processed_id` (readonly), `sync_health_id` smart button, action buttons `action_migrate` and `action_apply_merges`, status display
- [ ] T048 [US6] Add migration wizard + apply-merges menu items to `custom_addons/etsy_integration/views/menu.xml` under Etsy menu (gated to `sales_team.group_sale_manager`)
- [ ] T049 [US6] Add `etsy.data.migration.wizard` ACL to `custom_addons/etsy_integration/security/ir.model.access.csv` for `sales_team.group_sale_manager`
- [ ] T050 [US6] Update `custom_addons/etsy_integration/wizards/__init__.py` to import `data_migration_wizard`
- [ ] T051 [US6] Write test for migration wizard in `custom_addons/etsy_integration/tests/test_data_migration.py` — covers financial fix, shipping lines, product config, confirm+invoice_status, anomaly quarantine (R9), CSV export format
- [ ] T052 [US6] [R4] Write resumability test in `custom_addons/etsy_integration/tests/test_data_migration_resume.py` — seed 1,200 orders, run wizard with `batch_size=500`, simulate interruption after first batch (raise in second batch, rollback savepoint), re-invoke with `resume_from_checkpoint=True`, assert only orders with `id > last_processed_id` are processed
- [ ] T053 [US6] Write idempotency test in `custom_addons/etsy_integration/tests/test_data_migration_idempotent.py` (covers SC-009) — run `action_migrate()` twice on the same fixture, assert identical `sync.health` counts and no duplicate shipping lines / no state churn
- [ ] T054 [US6] [R10] Write apply-merges test in `custom_addons/etsy_integration/tests/test_data_migration_merges.py` — seed 3 partner clusters, call `_generate_dedup_report()`, feed an approved subset back to `action_apply_merges()`, assert correct merges and per-row savepoint rollback on the unapproved row

**Checkpoint**: Migration wizard fully resilient — resumable, idempotent, observable, BA-gated on dedup.

---

## Phase 9: User Story 7 — Discount Analytics (Priority: P3)

**Goal**: Discount code usage visible via pivot/graph views.

**Independent Test**: Open discount analytics, verify top codes and counts match Excel data.

### Implementation

- [ ] T055 [US7] Add `etsy_has_discount` Boolean computed field (`stored=True`) to `custom_addons/etsy_integration/models/sale_order.py` with `@api.depends('etsy_discount_code')`
- [ ] T056 [US7] Create discount analytics views in `custom_addons/etsy_integration/views/etsy_discount_views.xml` — pivot (rows=`etsy_discount_code`, measures=count+`amount_total`), graph (bar), search filter "Has Discount", action
- [ ] T057 [US7] Add discount analytics menu item to `custom_addons/etsy_integration/views/menu.xml`

**Checkpoint**: Discount analytics accessible from Etsy menu.

---

## Phase 10: User Story 8 — Image Download Cron (Priority: P3)

**Goal**: Scheduled job downloads product images automatically.

**Independent Test**: After cron runs, verify products with `etsy_image_url` now have `image_1920` populated.

### Implementation

- [ ] T058 [US8] Add image-download cron record to `custom_addons/etsy_integration/data/ir_cron_data.xml` — model=`product.template`, method=`cron_download_pending_images`, interval=30 min
- [ ] T059 [US8] Update `cron_download_pending_images()` in `custom_addons/etsy_integration/services/image_downloader.py` to limit batch to 50 products per cycle, remove `time.sleep(1)`, report per-run stats to `etsy.sync.health` via `report_run('image_download', ...)` (R8)

**Checkpoint**: Images download automatically on schedule, observable via sync.health.

---

## Phase 11: User Story 9 — Shop-Level Record Rules (Priority: P3)

**Goal**: Shop owners only see their own shop's data (sale.order + etsy.email.log only).

**Independent Test**: Create two users assigned to different shops, verify each only sees their own orders.

### Implementation

- [ ] T060 [US9] Create `custom_addons/etsy_integration/models/res_users.py` — extend `res.users` with `etsy_shop_ids` Many2many to `etsy.shop`
- [ ] T061 [US9] Update `custom_addons/etsy_integration/models/__init__.py` to import `res_users`
- [ ] T062 [US9] Add sale.order record rule to `custom_addons/etsy_integration/security/etsy_security.xml` — domain `['|',('etsy_shop_id','=',False),('etsy_shop_id','in',user.etsy_shop_ids.ids)]` for `base.group_user`, global for `sales_team.group_sale_manager`
- [ ] T063 [US9] Add etsy.email.log record rule to `custom_addons/etsy_integration/security/etsy_security.xml` — domain filters by `sale_order_id.etsy_shop_id`
- [ ] T064 [US9] Add user form extension to show `etsy_shop_ids` in `custom_addons/etsy_integration/views/res_users_views.xml`

**Checkpoint**: Shop isolation enforced at record-rule level.

---

## Phase 12: User Story 10 — Design Queue Status (Priority: P4)

**Goal**: Design team can track order personalization workflow status.

**Independent Test**: Set an item to "In Progress", filter by "Pending", verify correct filtering.

### Implementation

- [ ] T065 [US10] Add `etsy_design_status` Selection field to `custom_addons/etsy_integration/models/sale_order_line.py` — choices: pending/in_progress/completed, default pending
- [ ] T066 [US10] Update design queue view in `custom_addons/etsy_integration/views/etsy_design_queue_views.xml` — add status column, filter by status, group by status

**Checkpoint**: Design queue has trackable status workflow.

---

## Phase 13: Polish, Reconciliation & Cross-Cutting

**Purpose**: Final validation, reconciliation sign-off (mandatory gate), and cleanup.

- [ ] T067 Build per-shop reconciliation report in `custom_addons/etsy_integration/wizards/data_migration_wizard.py` method `action_reconciliation_report()` — computes per-shop `SUM(amount_total)` and order-count from Odoo, joins against an uploaded source Excel totals file, exports `/tmp/reconciliation_<timestamp>.csv` with deltas; **this is the mandatory BA sign-off gate per plan.md §Verification step 6**
- [ ] T068 [P] Add reconciliation-report menu item + button on migration wizard form in `custom_addons/etsy_integration/views/data_migration_wizard_views.xml`
- [ ] T069 [P] Run `ruff check custom_addons/etsy_integration/` and fix any linting issues
- [ ] T070 [P] Run `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` to verify clean module update
- [ ] T071 Run full test suite: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init` — must include T052 (resume) and T053 (idempotency) and T054 (merges)
- [ ] T072 Execute `quickstart.md` verification steps 1–7 against a staging DB restore; capture outputs
- [ ] T073 Run migration wizard on full production-snapshot DB on staging (`129.150.63.207`); verify `etsy.sync.health` shows `data_migration` state=`ok`, 423 anomalies quarantined, 17,236 good orders confirmed + `invoice_status=invoiced`
- [ ] T074 Produce reconciliation CSV (T067), submit to BA lead, obtain written sign-off (mandatory gate per master-plan §Phase 0 exit criteria)

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (XML records needed for xmlid lookups; `etsy.sync.health` model needed for observability writes)
- **Phase 3–7 (US1–US5)**: All depend on Phase 2 completing
- **Phase 8 (US6 Migration)**: Depends on Phases 3–7 (uses all their fix logic) **and** Phase 2 R8/R9 scaffolding
- **Phase 9–12 (US7–US10)**: Independent of each other; depend only on Phase 2
- **Phase 13 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (Financial)**: Phase 2 — can start first (MVP)
- **US2 (Confirmation)**: Phase 2 — parallel with US1
- **US3 (Products)**: Phase 2 (needs categorizer T011)
- **US4 (Dedup)**: Phase 2 — independent
- **US5 (Wizard Robustness)**: Phase 2 + R4/R8 — independent
- **US6 (Migration)**: Depends on US1 + US2 + US3 + US4 + R8/R9/R10 scaffolding
- **US7–US10**: Independent of each other

### Parallel Opportunities

Within Phase 1: `T001 || T002 || T003 || T004`

Within Phase 2 (after T006 lands):
```
T007 || T008 || T010 || T011 || T012 || T013
```

After Phase 2, US1–US5 run in parallel:
```
US1 (T015-T020) || US2 (T021-T024) || US3 (T025-T027) || US4 (T028-T030) || US5 (T031-T034)
```

US6 (T035-T054) runs after US1–US5 complete.

US7–US10 can run in parallel with US1–US5 or after:
```
US7 (T055-T057) || US8 (T058-T059) || US9 (T060-T064) || US10 (T065-T066)
```

---

## Implementation Strategy

### MVP (deliverable after ~2 weeks)

1. **Phase 1**: Setup data files (T001–T005)
2. **Phase 2**: Foundational — sync.health, anomaly field, categorizer, helpers (T006–T014)
3. **Phase 3**: US1 financial fixes (T015–T020) — new imports correct
4. **Phase 8 partial**: US6 core wizard (T035–T046) — existing data remediated with resumability, anomaly quarantine, and observability
5. **Phase 13 partial**: T067, T073, T074 — reconciliation sign-off
6. **STOP and VALIDATE**: Revenue reconciles to Excel totals; BA lead signs off.

### Full delivery (after MVP)

7. Phase 4: US2 confirmation workflow (+ invoice_status write)
8. Phase 5–7: US3-US5 (products, dedup, wizard robustness)
9. Phase 9–12: US7–US10 (analytics, images, security, design queue)
10. Phase 13 remainder: Polish, tests, ruff, module update

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 74 |
| Phase 1 (Setup) | 5 |
| Phase 2 (Foundational: observability + anomaly + helpers) | 9 |
| US1 (Financial) | 6 |
| US2 (Confirmation) | 4 |
| US3 (Products) | 3 |
| US4 (Dedup) | 3 |
| US5 (Wizard Robustness) | 4 |
| US6 (Migration Wizard + resumability + dedup CSV) | 20 |
| US7 (Discounts) | 3 |
| US8 (Images) | 2 |
| US9 (Shop Rules) | 5 |
| US10 (Design Status) | 2 |
| Polish & Reconciliation | 8 |
| New files to create | 11 (adds `models/etsy_sync_health.py`, `views/etsy_sync_health_views.xml`, `tests/test_data_migration_resume.py`, `tests/test_data_migration_idempotent.py`, `tests/test_data_migration_merges.py` vs previous count) |
| Existing files to modify | 13 |

---

## Coverage vs 2026-04-10 Plan Revisions

| Plan item | Tasks |
|---|---|
| R4 — 500-row savepoint batching + `last_processed_id` checkpoint | T032, T035, T037, T052 |
| R5 — skip auto-invoice, write `invoice_status='invoiced'` directly | T022, T043 |
| R8 — `etsy.sync.health` model + views + helper + ACL | T006, T007, T008, T009, T038, T059 |
| R9 — `etsy_price_anomaly` field + `_quarantine_anomalies()` + CSV | T010, T036, T037 (domain filter) |
| R10 — dedup CSV for BA + `action_apply_merges()` | T044, T045, T054 |
| SC-009 idempotency verification | T053 |
| Plan Verification §6 reconciliation sign-off | T067, T068, T073, T074 |

---

## Revision History

- **2026-04-04**: Original tasks.md (62 tasks) generated from initial plan.
- **2026-04-19**: Regenerated (74 tasks) to cover the 2026-04-10 plan revisions (R4/R5/R8/R9/R10), add idempotency + resumability tests, and add the mandatory reconciliation sign-off gate. Previous version preserved as `tasks.md.pre-regen-2026-04-19`.
