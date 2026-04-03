# Implementation Plan: Etsy Order Migration to Odoo 19 CE

**Branch**: `001-etsy-order-migration` | **Date**: 2026-04-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-etsy-order-migration/spec.md`

## Summary

Migrate Etsy order collection from a standalone Python script + Google Sheets to an Odoo 19 CE custom module (`etsy_integration`). The module extends sale.order, product.product, and res.partner with Etsy-specific fields, implements a Gmail API email fetcher as an ir.cron job, and provides a regex-based email parser to create sale orders automatically. Includes import wizard for 17,659 historical orders from Excel.

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 requirement)
**Primary Dependencies**: Odoo 19 CE framework (ORM, views, cron, mail, stock)
**Storage**: PostgreSQL 16+ via Odoo ORM
**Testing**: Odoo TransactionCase + standalone pytest for parser
**Target Platform**: Docker (Linux, amd64)
**Project Type**: Odoo 19 CE custom module
**Performance Goals**: Process 50+ emails per 10-minute cron cycle
**Constraints**: Gmail API rate limits (250 quota units/sec), Odoo ORM overhead for bulk creates
**Scale/Scope**: 17,659 existing orders + ~50-100 new orders/day

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Odoo-Native First | PASS | Uses sale.order, res.partner, product.product with extensions |
| II. Email Parser Isolation | PASS | Parser in `services/email_parser.py`, no ORM dependency |
| III. Data Integrity First | PASS | Atomic transactions, unique constraints on etsy IDs |
| IV. Test-Driven Development | PASS | Parser tests + Odoo TransactionCase tests planned |
| V. Incremental Migration | PASS | 3-phase approach: ingest, catalog, analytics |
| VI. Security by Default | PASS | Credentials in ir.config_parameter, .gitignore for secrets |
| VII. Simplicity Over Completeness | PASS | Raw email storage for parse failures; no over-engineering |

## Project Structure

### Documentation (this feature)

```text
specs/001-etsy-order-migration/
├── spec.md              # Feature specification
├── research.md          # Technical research and investigation
├── plan.md              # This file
├── data-model.md        # Detailed data model design
└── tasks.md             # Actionable task breakdown
```

### Source Code (Odoo module)

```text
custom_addons/etsy_integration/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── etsy_shop.py              # etsy.shop model
│   ├── etsy_email_log.py         # etsy.email.log model
│   ├── sale_order.py             # sale.order extension
│   ├── sale_order_line.py        # sale.order.line extension
│   ├── product_product.py        # product.product extension
│   └── res_config_settings.py    # Settings page
├── services/
│   ├── __init__.py
│   ├── email_parser.py           # Regex-based email parser (no ORM)
│   ├── gmail_client.py           # Gmail API wrapper (OAuth2)
│   ├── order_creator.py          # ORM-based order creation service
│   └── image_downloader.py       # Fetch Etsy images, store in Odoo filestore
├── wizards/
│   ├── __init__.py
│   └── import_orders_wizard.py   # Excel import wizard
├── data/
│   ├── ir_cron_data.xml          # Cron job definition
│   ├── regex_patterns.json       # Migrated from regex_02.json
│   └── string_labels.json        # Migrated from strings.json
├── security/
│   ├── ir.model.access.csv
│   └── etsy_security.xml         # Record rules
├── views/
│   ├── etsy_shop_views.xml
│   ├── etsy_email_log_views.xml
│   ├── sale_order_views.xml      # Extended views
│   ├── import_orders_wizard_views.xml
│   ├── res_config_settings_views.xml
│   └── menu.xml
├── tests/
│   ├── __init__.py
│   ├── test_email_parser.py      # Parser unit tests
│   ├── test_order_creation.py    # ORM integration tests
│   ├── test_deduplication.py     # Dedup logic tests
│   └── test_import_wizard.py     # Import tests
├── static/
│   └── description/
│       └── icon.png
└── i18n/
```

**Structure Decision**: Standard Odoo module layout within `addons/` directory. Parser service layer is isolated in `services/` to maintain testability independent of ORM.

## Data Model Design

### Entity Relationship

```
etsy.shop (1) ---< (many) sale.order
                            |
                            |--- etsy_order_id (unique)
                            |--- date_order
                            |--- partner_id -> res.partner (buyer/shipping)
                            |--- etsy_shop_id -> etsy.shop
                            |--- etsy_note_from_buyer
                            |--- etsy_gift_message
                            |--- etsy_shipping_service
                            |--- etsy_processing_time
                            |--- etsy_shipping_cost
                            |--- etsy_discount_code
                            |--- etsy_subtotal
                            |
                            +---< (many) sale.order.line
                                          |--- etsy_transaction_id (unique)
                                          |--- product_id -> product.product
                                          |--- etsy_personalisation
                                          |--- etsy_sku
                                          |--- etsy_option
                                          |--- etsy_color
                                          |--- etsy_size
                                          |--- etsy_side
                                          |--- etsy_face_mask_size
                                          |--- etsy_image_url
                                          |--- etsy_design_link_front
                                          |--- etsy_design_link_back

etsy.email.log
    |--- gmail_message_id (unique)
    |--- raw_body_text
    |--- raw_body_html
    |--- parse_status (success/failed/skipped)
    |--- error_message
    |--- sale_order_id -> sale.order (if successful)

res.partner (extended)
    |--- is_etsy_customer (Boolean)
    |--- etsy_buyer_name (Char)
```

### Key Constraints

- `sale.order.etsy_order_id`: Unique, indexed
- `sale.order.line.etsy_transaction_id`: Unique, indexed
- `etsy.email.log.gmail_message_id`: Unique, indexed
- `etsy.shop.name`: Unique

## Integration Architecture

### Email Processing Sequence

```
[ir.cron] (every 10 min)
    |
    v
[gmail_client.py] fetch_new_emails(label)
    |--- Gmail API: messages.list(q="label:X")
    |--- Gmail API: messages.get(id, format='full')
    |--- Returns: List[RawEmail]
    |
    v
[For each RawEmail]
    |
    v
[email_parser.py] parse_etsy_email(raw_email)
    |--- Decode base64 body (text + HTML)
    |--- Check for "Order details" marker
    |--- Split transactions by "Transaction ID"
    |--- Extract fields per transaction via regex
    |--- Returns: ParseResult(orders, customers, designs) or ParseError
    |
    v
[order_creator.py] create_or_skip(parse_result)
    |--- Check dedup: etsy_transaction_id exists?
    |--- Find or create res.partner (match by email/name+zip)
    |--- Find or create product.product (match by name)
    |--- Find or create etsy.shop (match by name)
    |--- Create sale.order + sale.order.line
    |--- Log to etsy.email.log (success)
    |
    v
[gmail_client.py] remove_label(message_ids, label)
    |--- Gmail API: messages.batchModify
```

### Error Handling Strategy

| Error Type | Handling | Recovery |
|------------|----------|----------|
| Gmail API auth failure | Log error, skip cycle | Admin alert; auto-refresh token |
| Gmail API rate limit | Backoff, retry | Next cron cycle |
| Email parse failure | Store raw email in etsy.email.log | Manual review via UI |
| ORM create failure | Rollback transaction | Log error, retry next cycle |
| Duplicate detection | Skip silently | Log as "skipped" in email log |
| Network timeout | Catch, log, skip message | Retry next cycle |

## Phase Plan

### Phase 1: Core Pipeline (MVP) - US1, US2, US10

**Goal**: Replace Google Sheets with Odoo for order storage. Email -> parse -> sale.order pipeline working.

**Deliverables**:
- `etsy_integration` module with models, views, security
- Email parser service (migrated from read_emails.py)
- Gmail API client with OAuth2
- Order creation service with deduplication
- ir.cron for 10-minute scheduling
- Excel import wizard for historical data
- Settings page for Gmail configuration
- Basic tree/form views for orders

### Phase 2: Catalog & CRM - US3, US4, US5

**Goal**: Proper product catalog with images, customer CRM, multi-shop management.

**Deliverables**:
- Product matching and auto-creation with variant attributes
- Customer deduplication and merge suggestions
- Shop-specific views and filters
- Customer order history on partner form
- Product sales statistics

### Phase 3: Analytics & Monitoring - US6, US7, US8, US9

**Goal**: Dashboard, reporting, parse failure monitoring, design queue.

**Deliverables**:
- Order dashboard with charts (pivot + graph views)
- Parse failure monitoring with alerts
- Design queue view for personalized orders
- Shipping information display
- Revenue and volume reporting per shop

## Complexity Tracking

No constitution violations requiring justification.

| Decision | Rationale |
|----------|-----------|
| Custom parser over fetchmail | Fetchmail (IMAP) cannot manage Gmail labels; parser already exists and works |
| New models (etsy.shop, etsy.email.log) | Clean separation; shop is a real business entity; email log needed for audit |
| Services layer in module | Testability; parser has no ORM dependency; can be replaced with Etsy API later |
| Orders stay in draft state | Team decision (Q1): manual confirmation workflow by operators |
| Include stock module | Team decision (Q2): inventory tracking needed; adds `stock` to dependencies |
| Download Etsy images | Team decision (Q4): fetch from etsystatic.com, store in Odoo product image field |
| English primary, i18n optional | Team decision (Q5): English-only interface; i18n/vi_VN.po added if translations needed per constitution |
| Full Sheets retirement | Team decision (Q6): no dual-write; Sheets archived as static backup |
| Dynamic shop creation | Team decision (Q7): more shops exist; auto-create from emails |
| Etsy API deferred to Phase 3 | Team decision (Q8): email parsing for now; API as future strategic improvement |
