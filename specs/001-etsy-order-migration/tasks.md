# Tasks: Etsy Order Migration to Odoo 19 CE

**Input**: Design documents from `specs/001-etsy-order-migration/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, etc.)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, module scaffold, Docker configuration

- [X] T001 Create Odoo module scaffold: `custom_addons/etsy_integration/__manifest__.py`, `__init__.py`
- [X] T002 [P] Configure Docker Compose for Odoo 19 CE at `/home/odoo/odoo_dev/other_projects/odoo19_esty/` with addons path including `addons/etsy_integration`
- [X] T003 [P] Create `.gitignore` for the `etsy_odoo_migration` project (exclude credentials, .pyc, node_modules, .specify internal state)
- [X] T004 [P] Copy regex pattern files from `esty_email_collection` to module: `regex_02.json` -> `custom_addons/etsy_integration/data/regex_patterns.json`, `strings.json` -> `custom_addons/etsy_integration/data/string_labels.json`
- [X] T005 [P] Set up test infrastructure: `custom_addons/etsy_integration/tests/__init__.py` with test loader configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models, security, and base views that ALL user stories depend on

### Models

- [X] T006 Create `etsy.shop` model in `custom_addons/etsy_integration/models/etsy_shop.py` with fields: name (required, unique), active, order_count (computed), order_ids (One2many)
- [X] T007 [P] Create `etsy.email.log` model in `custom_addons/etsy_integration/models/etsy_email_log.py` with fields: gmail_message_id (unique), subject, date_received, raw_body_text, raw_body_html, parse_status (selection), error_message, sale_order_id (M2O), retry_count
- [X] T008 [P] Extend `sale.order` in `custom_addons/etsy_integration/models/sale_order.py` with Etsy fields: etsy_order_id (unique), etsy_shop_id (M2O), etsy_note_from_buyer, etsy_gift_message, etsy_shipping_service, etsy_processing_time, etsy_shipping_cost, etsy_discount_code, etsy_subtotal, etsy_email_log_id, is_etsy_order (computed)
- [X] T009 [P] Extend `sale.order.line` in `custom_addons/etsy_integration/models/sale_order_line.py` with Etsy fields: etsy_transaction_id (unique), etsy_personalisation, etsy_sku, etsy_option, etsy_color, etsy_size, etsy_side, etsy_face_mask_size, etsy_image_url, etsy_design_link_front, etsy_design_link_back
- [X] T010 [P] Extend `product.product` in `custom_addons/etsy_integration/models/product_product.py` with fields: etsy_image_url, is_etsy_product
- [X] T011 [P] Extend `res.partner` in `custom_addons/etsy_integration/models/res_partner.py` with fields: is_etsy_customer, etsy_buyer_name
- [X] T012 [P] Extend `res.config.settings` in `custom_addons/etsy_integration/models/res_config_settings.py` with Gmail config fields: etsy_gmail_label, etsy_gmail_client_id, etsy_gmail_client_secret, etsy_gmail_refresh_token, etsy_cron_interval

### Security

- [X] T013 Create `custom_addons/etsy_integration/security/ir.model.access.csv` with access rules for etsy.shop and etsy.email.log (read for base.group_user, full for sales_team.group_sale_manager)
- [X] T014 [P] Create `custom_addons/etsy_integration/security/etsy_security.xml` with security groups if needed

### Base Views

- [X] T015 Create `custom_addons/etsy_integration/views/menu.xml` with top-level Etsy menu and submenus (Orders, Shops, Email Log, Settings)
- [X] T016 [P] Create `custom_addons/etsy_integration/views/etsy_shop_views.xml` with tree and form views for etsy.shop
- [X] T017 [P] Create `custom_addons/etsy_integration/views/etsy_email_log_views.xml` with tree and form views for etsy.email.log (include status filters, raw body preview)
- [X] T018 [P] Create `custom_addons/etsy_integration/views/sale_order_views.xml` with inherited form view adding Etsy tab (notebook page) showing Etsy-specific fields
- [X] T019 [P] Create `custom_addons/etsy_integration/views/res_config_settings_views.xml` with Gmail configuration section in Settings

### Module Registration

- [X] T020 Update `custom_addons/etsy_integration/__manifest__.py` with all dependencies (sale_management, stock, contacts, mail), data files (security, views, cron), and module metadata
- [X] T021 Update `custom_addons/etsy_integration/models/__init__.py` to import all model files

**Checkpoint**: Module installs cleanly. Empty Etsy menu visible. Settings page configurable.

---

## Phase 3: User Story 1 - Automated Etsy Email Ingestion (Priority: P1)

**Goal**: Emails parsed and stored as sale.order records automatically.

**Independent Test**: Configure Gmail creds in settings, send test email, verify order appears after cron run.

### Tests for User Story 1

- [X] T022 [US1] Create parser unit tests in `custom_addons/etsy_integration/tests/test_email_parser.py`: test with sample email text, verify all 34 fields extracted correctly, test multi-transaction email, test edge cases (missing fields, malformed data)
- [X] T022b [P] [US1] Add multi-language parser test cases in `test_email_parser.py`: test German label variants ("Personalisierung" vs "Personalisation", "Versandart" vs "Shipping service"), verify parser handles both English and German field labels per FR-012
- [X] T023 [P] [US1] Create order creation tests in `custom_addons/etsy_integration/tests/test_order_creation.py`: test partner creation, product creation, sale.order creation, deduplication by transaction_id

### Implementation for User Story 1

- [X] T024 [US1] Create email parser service in `custom_addons/etsy_integration/services/email_parser.py`: port regex logic from `read_emails.py`, no ORM dependency, returns structured ParseResult dataclass. Functions: `parse_etsy_email(text_body, html_body) -> ParseResult` (must handle English and German field labels per FR-012), `extract_transactions(text) -> List[Transaction]`, `extract_shipping_from_html(html) -> ShippingAddress`, `map_country_code(country_name) -> str`
- [X] T025 [US1] Create Gmail API client in `custom_addons/etsy_integration/services/gmail_client.py`: OAuth2 authentication using stored refresh_token, `fetch_labeled_emails(label) -> List[RawEmail]`, `remove_label(message_ids, label)`, token auto-refresh logic
- [X] T026 [US1] Create order creator service in `custom_addons/etsy_integration/services/order_creator.py`: `find_or_create_partner(shipping_data) -> res.partner`, `find_or_create_product(product_data) -> product.product`, `find_or_create_shop(shop_name) -> etsy.shop`, `create_sale_order(parse_result) -> sale.order`, deduplication checks
- [X] T027 [US1] Create cron job definition in `custom_addons/etsy_integration/data/ir_cron_data.xml`: model method `_cron_fetch_etsy_emails`, interval 10 minutes, calls gmail_client -> parser -> order_creator pipeline
- [X] T028 [US1] Implement cron method on `sale.order` (or dedicated model): `_cron_fetch_etsy_emails()` orchestrating the full pipeline with error handling, logging, and email log creation
- [X] T029 [US1] Add sample email test data in `custom_addons/etsy_integration/tests/data/`: sample_single_order.txt, sample_multi_order.txt, sample_malformed.txt (captured from real Etsy emails)

**Checkpoint**: Cron job runs, fetches emails, creates sale.orders. Deduplication prevents duplicates. Failed parses logged.

---

## Phase 4: User Story 2 - Historical Data Import (Priority: P1)

**Goal**: All 17,659 existing orders imported from Excel into Odoo.

**Independent Test**: Run import wizard with Excel file, verify order count and spot-check data.

### Tests for User Story 2

- [X] T030 [US2] Create import wizard tests in `custom_addons/etsy_integration/tests/test_import_wizard.py`: test field mapping, test duplicate handling, test country code mapping, test EUR price parsing

### Implementation for User Story 2

- [X] T031 [US2] Create import wizard model in `custom_addons/etsy_integration/wizards/import_orders_wizard.py`: Binary field for Excel upload, process method that reads with openpyxl, maps fields per data-model.md mapping table, creates partners/products/orders in batches (commit every 100 records), progress logging
- [X] T032 [US2] Create import wizard view in `custom_addons/etsy_integration/wizards/import_orders_wizard_views.xml`: file upload form, import button, status display
- [X] T033 [US2] Add wizard to menu and register in `__init__.py`
- [X] T034 [US2] Handle data quirks: EUR price strings ("€19.70" -> 19.70 float), country name-to-code mapping using res.country, date string parsing, Google Sheets formula strings in IMG column (skip)

**Checkpoint**: 17,659 orders imported. Shop, customer, product records created. No duplicates.

---

## Phase 5: User Story 10 - Gmail OAuth2 Configuration (Priority: P1)

**Goal**: Admin can configure Gmail credentials in Odoo settings UI.

**Independent Test**: Enter credentials in settings, click Test Connection, see success.

### Implementation for User Story 10

- [X] T035 [US10] Implement "Test Connection" button on res.config.settings: calls gmail_client.test_connection() using stored credentials, displays success/failure message
- [X] T036 [US10] Implement OAuth2 flow helper: initial authorization URL generation, callback handling for first-time setup (may require a simple controller endpoint `/etsy/oauth/callback`)
- [X] T037 [US10] Document the Gmail OAuth2 setup process in `custom_addons/etsy_integration/static/description/gmail_setup.md`

**Checkpoint**: Admin can configure Gmail access without editing files. Token refresh works automatically.

---

## Phase 6: User Story 3 - Multi-Shop Management (Priority: P2)

**Goal**: Orders filterable and manageable per Etsy shop.

**Independent Test**: Open shop list, click a shop, see its orders.

### Implementation for User Story 3

- [X] T038 [P] [US3] Add shop filter to sale.order tree view (search arch): filter by etsy_shop_id, group by etsy_shop_id
- [X] T039 [P] [US3] Add order count and revenue summary to etsy.shop form view (stat buttons)
- [X] T040 [US3] Create action from shop to filtered orders: `action_view_orders` on etsy.shop model

**Checkpoint**: Shop management works. Orders filterable by shop.

---

## Phase 7: User Story 4 - Customer Management (Priority: P2)

**Goal**: Etsy buyers as Odoo contacts with order history.

**Independent Test**: Search customer name in Contacts, see linked orders.

### Implementation for User Story 4

- [X] T041 [US4] Implement smart partner matching in `order_creator.py`: match by email (primary), then by name + zip (fallback), then create new
- [X] T042 [US4] Add "Etsy Orders" smart button on res.partner form view (count of linked sale.orders where is_etsy_order=True)
- [X] T043 [P] [US4] Add `is_etsy_customer` filter to partner search view

**Checkpoint**: Customers auto-created, deduplicated, browsable with order history.

---

## Phase 8: User Story 5 - Product Catalog (Priority: P2)

**Goal**: Products auto-created with Etsy images, searchable.

**Independent Test**: Open product list, see Etsy products with images.

### Implementation for User Story 5

- [X] T044 [US5] Implement smart product matching in `order_creator.py`: match by exact product name, auto-create if not found, set etsy_image_url
- [X] T044b [US5] Create image downloader service in `custom_addons/etsy_integration/services/image_downloader.py`: download product images from etsystatic.com URLs, store in Odoo product `image_1920` field, handle CDN failures gracefully (store URL only if download fails), replace '75x75' with '300x300' in URLs
- [X] T044c [P] [US5] Create image downloader tests in `custom_addons/etsy_integration/tests/test_image_downloader.py`: test URL transformation, test download failure handling, test image storage in product record
- [X] T045 [P] [US5] Add Etsy image display on product form (widget for etsy_image_url showing image preview)
- [X] T046 [P] [US5] Add `is_etsy_product` filter to product search view

**Checkpoint**: Products auto-created, searchable, with images.

---

## Phase 9: User Stories 6, 7, 8, 9 - Analytics & Monitoring (Priority: P3)

**Goal**: Dashboard, monitoring, shipping, design queue.

### Implementation

- [X] T047 [P] [US6] Create Etsy dashboard action with pivot and graph views: orders by date, revenue by shop, top products
- [X] T048 [P] [US7] Implement parse failure monitoring: add `_check_parse_failures()` method called after cron, creates mail.activity if >5 consecutive failures
- [X] T049 [P] [US8] Add shipping info tab to sale.order form: shipping_service, processing_time, full delivery address display
- [X] T050 [P] [US9] Create design queue view: tree view of sale.order.line where etsy_personalisation != '' OR gift_message != '', grouped by order, showing image, personalization text, product name
- [X] T051 [US6] Add date range and shop filters to dashboard

**Checkpoint**: Full analytics and monitoring operational. Design team has a working queue.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality, documentation, deployment readiness

- [X] T052 [P] Create module icon at `custom_addons/etsy_integration/static/description/icon.png`
- [X] T053 [P] Write `custom_addons/etsy_integration/README.md` with installation and configuration instructions
- [X] T054 Code review: security audit (no credentials in code, proper ACLs, SQL injection check)
- [ ] T055 Performance test: bulk import 17K orders, measure time, optimize if >30 minutes
- [X] T056 [P] Create sample data for demo mode in `custom_addons/etsy_integration/data/demo_data.xml`
- [X] T056b [P] Create empty i18n directory `custom_addons/etsy_integration/i18n/` with placeholder .pot file for future translations
- [ ] T057 Final module install test: fresh database, install module, run import, verify all views work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3 (US1 - Email Ingestion)**: Depends on Phase 2 foundation
- **Phase 4 (US2 - Import)**: Depends on Phase 2 foundation; can run PARALLEL with Phase 3
- **Phase 5 (US10 - OAuth Config)**: Depends on Phase 3 gmail_client.py
- **Phase 6-8 (US3,4,5)**: Depend on Phase 2; can run PARALLEL after Phase 2
- **Phase 9 (US6,7,8,9)**: Depends on data from Phase 3 or 4
- **Phase 10 (Polish)**: After all user stories

### Parallel Opportunities

```
Phase 1 (Setup)
    |
Phase 2 (Foundation) — all T006-T021 marked [P] run in parallel
    |
    +--- Phase 3 (US1: Email Ingestion)  ---|
    |                                        |--- Phase 5 (US10: OAuth Config)
    +--- Phase 4 (US2: Import) [PARALLEL] ---|
    |
    +--- Phase 6 (US3: Shops)     [PARALLEL]
    +--- Phase 7 (US4: Customers) [PARALLEL]
    +--- Phase 8 (US5: Products)  [PARALLEL]
    |
    +--- Phase 9 (US6,7,8,9: Analytics) — all T047-T051 run in parallel
    |
Phase 10 (Polish)
```

### Within Each Phase

- Models before views
- Security before views
- Tests before implementation (TDD where practical)
- Services before cron integration

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3 + 4 + 5)

1. Complete Setup + Foundation -> Module installs
2. Complete Email Ingestion -> Live email processing works
3. Complete Import -> Historical data loaded
4. Complete OAuth Config -> Admin self-service
5. **STOP and VALIDATE**: All orders in Odoo, email pipeline running

### Incremental Delivery After MVP

6. Add Multi-Shop -> Business can filter by shop
7. Add Customer CRM -> Look up buyers
8. Add Product Catalog -> See what sells
9. Add Analytics -> Make business decisions
