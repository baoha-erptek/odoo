# Tasks: Etsy Config Fixes

**Input**: Design documents from `/specs/002-etsy-config-fixes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US6)
- Exact file paths included in all task descriptions

---

## Phase 1: Setup

**Purpose**: Create new files and XML data records needed by all user stories

- [ ] T001 Create shipping service product data file in `custom_addons/etsy_integration/data/etsy_shipping_product.xml`
- [ ] T002 [P] Create fiscal position, tax, payment term, sales team, and pricelists data file in `custom_addons/etsy_integration/data/etsy_fiscal_data.xml`
- [ ] T003 [P] Create product category hierarchy data file in `custom_addons/etsy_integration/data/etsy_product_categories.xml`
- [ ] T004 [P] Create product category keyword mapping in `custom_addons/etsy_integration/data/product_category_keywords.json`
- [ ] T005 Update `custom_addons/etsy_integration/__manifest__.py` to include all new data files in the `data` list (etsy_shipping_product.xml, etsy_fiscal_data.xml, etsy_product_categories.xml)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core service changes that all user stories depend on

- [ ] T006 Create product categorizer service in `custom_addons/etsy_integration/services/product_categorizer.py` -- loads keywords JSON, matches product names to categories, returns product.category record
- [ ] T007 [P] Add multi-currency `_parse_price(text)` method to `custom_addons/etsy_integration/services/order_creator.py` -- detects EUR/USD/GBP symbols, returns (amount, currency_code) tuple, replaces `_parse_eur()`
- [ ] T008 [P] Add helper methods to `custom_addons/etsy_integration/services/order_creator.py`: `_get_shipping_product()`, `_get_fiscal_position()`, `_get_payment_term()`, `_get_sales_team()`, `_get_pricelist(currency_code)` -- each looks up the XML record by xmlid, caches result
- [ ] T009 Update `custom_addons/etsy_integration/services/__init__.py` to import product_categorizer module

**Checkpoint**: Foundation ready -- all helper methods and services available for user story implementation

---

## Phase 3: User Story 1 - Correct Financial Data (Priority: P1)

**Goal**: All orders show correct prices (EUR and USD), shipping as line items, fiscal position, payment term, sales team, and currency

**Independent Test**: Import 10 orders (5 EUR, 5 USD) via wizard and verify amount_total, currency, and all financial fields

### Implementation for User Story 1

- [ ] T010 [US1] Update `process_parse_result()` in `custom_addons/etsy_integration/services/order_creator.py` to set fiscal_position_id, payment_term_id, team_id, pricelist_id, currency_id on order vals
- [ ] T011 [US1] Update `process_parse_result()` in `custom_addons/etsy_integration/services/order_creator.py` to add Etsy Shipping service product as order line when shipping_cost > 0
- [ ] T012 [US1] Update `process_parse_result()` in `custom_addons/etsy_integration/services/order_creator.py` to use `_parse_price()` for multi-currency price detection and set currency accordingly
- [ ] T013 [US1] Update `_parse_eur_price()` in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` to detect USD/GBP currencies (rename to `_parse_price()`)
- [ ] T014 [US1] Update `_create_order_from_rows()` in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` to add shipping line, set fiscal position, payment term, sales team, pricelist, currency
- [ ] T015 [US1] Write test for multi-currency price parsing in `custom_addons/etsy_integration/tests/test_multi_currency_parsing.py`

**Checkpoint**: New imports produce orders with correct financial configuration

---

## Phase 4: User Story 2 - Order Confirmation Workflow (Priority: P1)

**Goal**: Historical orders can be confirmed and deliveries auto-completed to "done" state

**Independent Test**: Confirm a batch of draft orders and verify stock.picking records exist in "done" state

### Implementation for User Story 2

- [ ] T016 [US2] Add `auto_confirm` Boolean field to `custom_addons/etsy_integration/wizards/import_orders_wizard.py` (default=True)
- [ ] T017 [US2] Add auto-confirm logic in `action_import()` in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` -- after order creation, call `action_confirm()` then validate picking to done
- [ ] T018 [US2] Add `etsy_auto_confirm_email` Boolean to `custom_addons/etsy_integration/models/res_config_settings.py` (default=False) for email cron auto-confirm toggle
- [ ] T019 [US2] Update `_cron_fetch_etsy_emails()` in `custom_addons/etsy_integration/models/sale_order.py` to optionally auto-confirm based on settings

**Checkpoint**: Import wizard auto-confirms orders; cron has configurable auto-confirm

---

## Phase 5: User Story 3 - Product Configuration (Priority: P2)

**Goal**: Products created as storable with proper category assignment

**Independent Test**: Import an order with a new product, verify is_storable=True and correct category

### Implementation for User Story 3

- [ ] T020 [US3] Update `find_or_create_product()` in `custom_addons/etsy_integration/services/order_creator.py` to set `is_storable=True` on new products
- [ ] T021 [US3] Update `find_or_create_product()` in `custom_addons/etsy_integration/services/order_creator.py` to call `product_categorizer.categorize()` and set `categ_id`
- [ ] T022 [US3] Write test for product categorizer in `custom_addons/etsy_integration/tests/test_product_categorizer.py` -- test keyword matching, fallback to uncategorized, case insensitivity

**Checkpoint**: New products are storable and categorized

---

## Phase 6: User Story 4 - Improved Customer Dedup (Priority: P2)

**Goal**: Customer matching works reliably even without email/phone data

**Independent Test**: Import orders from same buyer with same address, verify single partner record

### Implementation for User Story 4

- [ ] T023 [US4] Update `find_or_create_partner()` in `custom_addons/etsy_integration/services/order_creator.py` -- add name+address+city+zip as secondary match strategy (normalized: strip accents, lowercase, trim)
- [ ] T024 [US4] Update `_resolve_state()` in `custom_addons/etsy_integration/services/order_creator.py` -- search by state `code` field first (for 2-letter codes like "CA"), then fall back to `name` ilike
- [ ] T025 [US4] Expand country name overrides in `custom_addons/etsy_integration/services/order_creator.py` for all 48 countries in the dataset (Czechia, Republic of Korea, etc.)

**Checkpoint**: Customer dedup handles no-email scenarios; state/country resolution improved

---

## Phase 7: User Story 5 - Import Wizard Robustness (Priority: P2)

**Goal**: Wizard uses header-based column mapping and savepoint batching

**Independent Test**: Import Excel with reordered columns; kill mid-import and verify no orphaned records

### Implementation for User Story 5

- [ ] T026 [US5] Replace all `_COL_*` constants with header-based mapping in `custom_addons/etsy_integration/wizards/import_orders_wizard.py` -- read first row, build {header: index} dict, validate required headers
- [ ] T027 [US5] Replace `self.env.cr.commit()` with `self.env.cr.savepoint()` per 100-order batch in `custom_addons/etsy_integration/wizards/import_orders_wizard.py`
- [ ] T028 [US5] Add `warning_count` and `validation_notes` fields to `custom_addons/etsy_integration/wizards/import_orders_wizard.py` -- track zero-price warnings, unparseable values, missing headers
- [ ] T029 [US5] Write test for header-based mapping in `custom_addons/etsy_integration/tests/test_import_wizard_headers.py`

**Checkpoint**: Wizard robust against column reordering and partial failures

---

## Phase 8: User Story 6 - Data Migration Wizard (Priority: P1)

**Goal**: One-click wizard to fix all existing imported records

**Independent Test**: Run wizard on full database, verify all counts match expected

### Implementation for User Story 6

- [ ] T030 [US6] Create `custom_addons/etsy_integration/wizards/data_migration_wizard.py` -- TransientModel with fields: excel_file, auto_confirm, fix_shipping_lines, fix_financial_config, fix_product_config, generate_dedup_report, status_message
- [ ] T031 [US6] Implement `_fix_financial_config()` in data_migration_wizard.py -- batch-set fiscal_position_id, payment_term_id, team_id, pricelist_id on all Etsy orders
- [ ] T032 [US6] Implement `_fix_shipping_lines()` in data_migration_wizard.py -- add Etsy Shipping line to orders with etsy_shipping_cost > 0 and no existing shipping line
- [ ] T033 [US6] Implement `_fix_prices_from_excel()` in data_migration_wizard.py -- re-parse USD prices from uploaded Excel, match by etsy_transaction_id, update price_unit and currency
- [ ] T034 [US6] Implement `_fix_product_config()` in data_migration_wizard.py -- set is_storable=True, run categorizer on all Etsy products
- [ ] T035 [US6] Implement `_confirm_and_complete()` in data_migration_wizard.py -- confirm draft orders, validate stock.picking to done, process in batches of 100 with savepoints
- [ ] T036 [US6] Implement `_generate_dedup_report()` in data_migration_wizard.py -- find partners with same normalized name+zip, write report to status_message
- [ ] T037 [US6] Implement `action_migrate()` in data_migration_wizard.py -- orchestrates all fix methods based on checkbox selections, writes summary
- [ ] T038 [US6] Create wizard view in `custom_addons/etsy_integration/views/data_migration_wizard_views.xml` -- form with checkboxes, file upload, action button, status display
- [ ] T039 [US6] Add migration wizard menu item to `custom_addons/etsy_integration/views/menu.xml` under Etsy menu
- [ ] T040 [US6] Add `etsy.data.migration.wizard` ACL to `custom_addons/etsy_integration/security/ir.model.access.csv` for sales_team.group_sale_manager
- [ ] T041 [US6] Update `custom_addons/etsy_integration/wizards/__init__.py` to import data_migration_wizard
- [ ] T042 [US6] Write test for migration wizard in `custom_addons/etsy_integration/tests/test_data_migration.py`

**Checkpoint**: Migration wizard can fix all existing data in one operation

---

## Phase 9: User Story 7 - Discount Analytics (Priority: P3)

**Goal**: Discount code usage visible via pivot/graph views

**Independent Test**: Open discount analytics, verify top codes and counts match Excel data

### Implementation for User Story 7

- [ ] T043 [US7] Add `etsy_has_discount` Boolean computed field to `custom_addons/etsy_integration/models/sale_order.py` -- `@api.depends('etsy_discount_code')`, stored=True
- [ ] T044 [US7] Create discount analytics views in `custom_addons/etsy_integration/views/etsy_discount_views.xml` -- pivot (rows=discount_code, measures=count+amount_total), graph (bar chart), search filter "Has Discount"
- [ ] T045 [US7] Add discount analytics menu item to `custom_addons/etsy_integration/views/menu.xml`
- [ ] T046 [US7] Update `custom_addons/etsy_integration/__manifest__.py` to include etsy_discount_views.xml

**Checkpoint**: Discount analytics accessible from Etsy menu

---

## Phase 10: User Story 8 - Image Download Cron (Priority: P3)

**Goal**: Scheduled job downloads product images automatically

**Independent Test**: After cron runs, verify products with etsy_image_url now have image_1920 populated

### Implementation for User Story 8

- [ ] T047 [US8] Add image download cron record to `custom_addons/etsy_integration/data/ir_cron_data.xml` -- model=product.template, method=cron_download_pending_images, interval=30min
- [ ] T048 [US8] Update `cron_download_pending_images()` in `custom_addons/etsy_integration/services/image_downloader.py` to limit batch to 50 products per cycle, remove `time.sleep(1)`

**Checkpoint**: Images download automatically on schedule

---

## Phase 11: User Story 9 - Shop-Level Record Rules (Priority: P3)

**Goal**: Shop owners only see their own shop's data

**Independent Test**: Create two users assigned to different shops, verify each only sees their own orders

### Implementation for User Story 9

- [ ] T049 [US9] Create `custom_addons/etsy_integration/models/res_users.py` -- extend res.users with etsy_shop_ids Many2many to etsy.shop
- [ ] T050 [US9] Update `custom_addons/etsy_integration/models/__init__.py` to import res_users
- [ ] T051 [US9] Add sale.order record rule to `custom_addons/etsy_integration/security/etsy_security.xml` -- domain: `['|',('etsy_shop_id','=',False),('etsy_shop_id','in',user.etsy_shop_ids.ids)]` for base.group_user, global for managers
- [ ] T052 [US9] Add etsy.email.log record rule to `custom_addons/etsy_integration/security/etsy_security.xml` -- filter by linked order's shop
- [ ] T053 [US9] Add user form view extension to show etsy_shop_ids in `custom_addons/etsy_integration/views/res_users_views.xml`
- [ ] T054 [US9] Update `custom_addons/etsy_integration/__manifest__.py` to include res_users_views.xml

**Checkpoint**: Shop isolation enforced at record rule level

---

## Phase 12: User Story 10 - Design Queue Status (Priority: P4)

**Goal**: Design team can track order personalization workflow status

**Independent Test**: Set an item to "In Progress", filter by "Pending", verify correct filtering

### Implementation for User Story 10

- [ ] T055 [US10] Add `etsy_design_status` Selection field to `custom_addons/etsy_integration/models/sale_order_line.py` -- choices: pending, in_progress, completed; default=pending
- [ ] T056 [US10] Update design queue view in `custom_addons/etsy_integration/views/etsy_design_queue_views.xml` -- add status column, filter by status, group by status

**Checkpoint**: Design queue has trackable status workflow

---

## Phase 13: Polish and Cross-Cutting

**Purpose**: Final validation, cleanup, and documentation

- [ ] T057 Update `custom_addons/etsy_integration/__manifest__.py` with correct version (19.0.2.0.0) and complete data file list
- [ ] T058 [P] Run `ruff check custom_addons/etsy_integration/` and fix any linting issues
- [ ] T059 [P] Run `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` to verify clean module update
- [ ] T060 Run full test suite: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init`
- [ ] T061 Execute quickstart.md verification steps (financial reconciliation, product categories, order states)
- [ ] T062 Run data migration wizard on full database and verify summary counts

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies -- start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (data files must exist for xmlid lookups)
- **Phase 3-7 (US1-US5)**: All depend on Phase 2 foundational methods
- **Phase 8 (US6 Migration)**: Depends on Phases 3-7 (all fix logic must exist before migration wizard can use it)
- **Phase 9-12 (US7-US10)**: Independent of each other, depend only on Phase 2
- **Phase 13 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (Financial)**: Phase 2 only -- can start first
- **US2 (Confirmation)**: Phase 2 only -- can run parallel with US1
- **US3 (Products)**: Phase 2 only (needs categorizer from T006)
- **US4 (Dedup)**: Phase 2 only -- independent
- **US5 (Wizard)**: Phase 2 only -- independent
- **US6 (Migration)**: Depends on US1 + US2 + US3 + US4 (uses their fix logic)
- **US7-US10**: Independent of each other

### Parallel Opportunities

Within Phase 1:
```
T001 || T002 || T003 || T004  (all create independent data files)
```

Within Phase 2:
```
T006 || T007 || T008  (independent services/methods)
```

After Phase 2, user stories US1-US5 can run in parallel:
```
US1 (T010-T015) || US2 (T016-T019) || US3 (T020-T022) || US4 (T023-T025) || US5 (T026-T029)
```

After US1-US5 complete, US6 (T030-T042) runs.

US7-US10 can run in parallel with US1-US5 or after:
```
US7 (T043-T046) || US8 (T047-T048) || US9 (T049-T054) || US10 (T055-T056)
```

---

## Implementation Strategy

### MVP First (US1 + US6)

1. Phase 1: Setup data files
2. Phase 2: Foundational methods
3. Phase 3: US1 (financial fixes) -- new imports are correct
4. Phase 8: US6 (migration wizard) -- existing data fixed
5. **STOP and VALIDATE**: Revenue matches Excel totals

### Full Delivery

1. MVP above
2. Phase 4: US2 (confirmation workflow)
3. Phase 5-7: US3-US5 (products, dedup, wizard robustness)
4. Phase 9-12: US7-US10 (analytics, images, security, design queue)
5. Phase 13: Polish and full validation

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 62 |
| Phase 1 (Setup) | 5 |
| Phase 2 (Foundational) | 4 |
| US1 (Financial) | 6 |
| US2 (Confirmation) | 4 |
| US3 (Products) | 3 |
| US4 (Dedup) | 3 |
| US5 (Wizard Robustness) | 4 |
| US6 (Migration Wizard) | 13 |
| US7 (Discounts) | 4 |
| US8 (Images) | 2 |
| US9 (Shop Rules) | 6 |
| US10 (Design Status) | 2 |
| Polish | 6 |
| New files to create | 8 |
| Existing files to modify | 12 |
