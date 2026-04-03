# Business Analysis Report: Etsy Order Collection Migration to Odoo 19 CE

**Project**: Migration of Etsy Email-Based Order Collection System to Odoo 19 Community Edition
**Date**: 2026-04-02
**Version**: 1.0
**Author**: Business Analysis Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Stakeholder Analysis](#2-stakeholder-analysis)
3. [Current Process Map (As-Is)](#3-current-process-map-as-is)
4. [Gap Analysis](#4-gap-analysis)
5. [Data Migration Requirements](#5-data-migration-requirements)
6. [User Stories](#6-user-stories)
7. [Business Rules](#7-business-rules)
8. [Risk Assessment](#8-risk-assessment)
9. [Success Metrics](#9-success-metrics)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Recommended Module Architecture](#11-recommended-module-architecture)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

### Problem Statement

The current Etsy order collection system is a standalone Python application that monitors a Gmail inbox for Etsy order notification emails, extracts 34 fields per order using regex, and writes results to three separate Google Sheets. While functional, it suffers from critical limitations: no workflow management, no customer lifecycle tracking, fragile regex-based parsing, no audit trail, flat-file storage with no relational integrity, and zero reporting capability beyond spreadsheet formulas.

### Proposed Solution

Migrate the order collection pipeline into a custom Odoo 19 CE module that leverages Odoo's native capabilities: the `sale.order` workflow (quotation to confirmed to shipped), `res.partner` for customer/contact management, `product.product` for catalog management, `delivery.carrier` for shipping, and the built-in `fetchmail.server` with `google_gmail` module for email ingestion. The regex parsing engine will be ported into Odoo as a server action or scheduled cron job.

### Value Proposition

| Dimension | Google Sheets (Current) | Odoo 19 CE (Proposed) |
|-----------|------------------------|----------------------|
| Customer management | Flat rows, UUID-based IDs, no dedup | `res.partner` with dedup, lifecycle, history |
| Order workflow | No states, no transitions | Draft -> Confirmed -> Shipped -> Done |
| Product catalog | Product name as free text | `product.template` with variants, SKU, images |
| Shipping | Text fields only | `delivery.carrier`, tracking, address validation |
| Reporting | Manual Google Sheets formulas | Built-in dashboards, pivot tables, custom reports |
| Multi-user access | Google Sheets sharing (no roles) | Role-based access control (RBAC) with groups |
| Audit trail | None | Chatter, `mail.tracking.value`, log timestamps |
| Data integrity | No constraints, no FK | Relational DB, unique constraints, computed fields |
| Scalability | 10M cell limit per sheet | PostgreSQL, no practical row limit |

---

## 2. Stakeholder Analysis

### 2.1 Primary Stakeholders

| Stakeholder | Role | Current Workflow | Needs |
|-------------|------|-----------------|-------|
| **Shop Owners** (Viktor, Julien, Carina, etc.) | Business owners running Etsy shops | Review Google Sheets for their shop's orders; manually track fulfillment status | Per-shop filtered views, order status tracking, revenue reports by shop |
| **Fulfillment Team** | Processes and ships orders | Reads order details from Sheets, manually tracks shipped/pending | Order picking lists, shipping label data, fulfillment status workflow |
| **Design Team** | Creates personalized products | Reviews Design Sheet (15 columns) for personalization, color, side info | Design queue view, image preview, personalization notes, production status |
| **Customer Service** | Handles buyer inquiries | Searches Sheets by name/order ID, reads notes and gift messages | Customer 360 view, order history, communication log |

### 2.2 Secondary Stakeholders

| Stakeholder | Role | Needs |
|-------------|------|-------|
| **System Administrator** | Maintains the email collection pipeline | Monitoring dashboard, error alerts, Gmail token management |
| **Accountant/Finance** | Revenue tracking, tax reporting | Revenue reports by shop/period, discount tracking, shipping cost analysis |
| **Business Analyst/Owner** | Strategic decisions | Cross-shop analytics, customer segmentation, product performance |

### 2.3 Stakeholder Communication Matrix

| Stakeholder | Frequency | Method | Content |
|-------------|-----------|--------|---------|
| Shop Owners | Daily | Odoo dashboard | New orders, revenue, pending fulfillment |
| Fulfillment | Real-time | Odoo kanban/list | Order queue, shipping details |
| Design Team | Daily | Odoo filtered view | Personalization queue |
| Customer Service | On-demand | Odoo search | Customer/order lookup |
| Admin | Weekly + alerts | Odoo logs, email | System health, sync errors |
| Finance | Monthly | Odoo reports | Revenue, costs, margins |

---

## 3. Current Process Map (As-Is)

### 3.1 High-Level Process Flow

```
[Etsy Buyer Places Order]
        |
        v
[Etsy Sends Notification Email to Gmail]
        |
        v
[Systemd Timer Triggers Every 10 Minutes]
        |
        v
[Python Script Authenticates to Gmail API]
        |
        v
[Script Queries Gmail for Labeled Emails (e.g., "ordertest2")]
        |
        v
[For Each Email: Check Dedup Against Existing Sheet Data]
        |  
        +-- [Duplicate Found] --> Skip
        |
        +-- [New Order] --> Parse Email
                |
                v
        [Extract text/plain + text/html MIME Parts]
                |
                v
        [Regex Engine: Extract 34 Fields Per Transaction]
                |
                +--> [Extract TRANSACTION_IDS block between "Order details" and "Item total:"]
                |
                +--> [Split by "Transaction ID" boundary]
                |
                +--> [For each transaction: extract fields via regex_02.json patterns]
                |
                +--> [Extract images from HTML (i.etsystatic.com URLs)]
                |
                +--> [Country name -> ISO Alpha-2 code (via iban_countries.xlsx)]
                |
                +--> [Extract buyer contact, gift message, notes]
                |
                v
        [Build 3 DataFrames: Orders (34 cols), Designs (15 cols), Customers (10 cols)]
                |
                v
        [Batch Update Google Sheets]
                |
                v
        [Remove Gmail Label from Processed Emails]
```

### 3.2 Detailed Data Extraction Logic

The email parsing operates on two MIME types simultaneously:

1. **text/plain**: Used for extracting most structured fields (transaction IDs, order details, buyer notes, shipping costs, subtotals, gift messages, discount codes)
2. **text/html**: Used for extracting image URLs (via CSS class selectors like `first-line'>`), shipping addresses (parsed from HTML spans), and processing time

Key parsing behaviors:
- **Multi-transaction emails**: A single Etsy order notification can contain multiple transactions (items). The script splits by `(?=Transaction ID)` boundary.
- **Conditional field extraction**: Fields like Size, Color, Option, Personalisation are only parsed if their label text is detected in the remaining unparsed string.
- **Multi-language label support**: Personalisation handles English, British English, and German variants (`Personalisierung:`).
- **Image URL upscaling**: Thumbnail URLs (75x75) are replaced with 300x300 for higher quality.
- **Shipping cost parsing**: Extracts both cost amount and service type (e.g., "Standard", "Express") from a single field.

### 3.3 Current System Components

| Component | Technology | Location | Purpose |
|-----------|-----------|----------|---------|
| `run.py` | Python 3.10 | VPS | Entry point, config via env vars |
| `read_emails.py` | Python + pandas | VPS | Core parsing and sheet update logic |
| `common.py` | Python | VPS | Gmail OAuth2 authentication |
| `regex_02.json` | JSON | VPS | 43 regex patterns for field extraction |
| `regex_constants.py` | Python | VPS | 60 field name constants + standalone regex patterns |
| `strings.json` | JSON | VPS | Multi-language label variations for 20 fields |
| `res/iban_countries.xlsx` | Excel | VPS | Country name to ISO Alpha-2 code mapping (used at runtime) |
| Gmail OAuth2 | Google API | Cloud | `credentials.json` + `token.pickle` |
| Google Sheets SA | Google API | Cloud | `regal-cursor-369422-cf806b3ad787.json` |
| Systemd Timer | Linux | VPS | 10-minute polling schedule |

### 3.4 Current Data Model (Flat)

**Orders Sheet (34 columns)**:
```
TRANSACTION_ID | IMG_URL | IMG | DATE | NOTE_FROM_BUYER | GIFT_MESSAGE |
PERSONALISATION | SKU | SHOP | ORDER_ID | SHIPPING_NAME | SHIPPING_ADDRESS1 |
SHIPPING_ADDRESS2 | SHIPPING_CITY | SHIPPING_STATE | SHIPPING_ZIPCODE |
SHIPPING_COUNTRY | SHIPPING_PHONE | SHIPPING_EMAIL | PRODUCT_NAME | OPTION |
COLOR | SIZE | SIDE | FACE_MASK_SIZE | QUANTITY | DESIGN_LINK_FRONT |
DESIGN_LINK_BACK | SHIPPING_SERVICE | PROCESSING_TIME | SHIPPING_COST |
PRICE | DISCOUNT_CODE | SUBTOTAL
```

**Design Sheet (15 columns)**:
```
TRANSACTION_ID | IMG | DATE | NOTE_FROM_BUYER | GIFT_MESSAGE |
PERSONALISATION | SKU | SHOP | ORDER_ID | PRODUCT_NAME | OPTION | COLOR |
SIZE | SIDE | QUANTITY
```

**Customer Sheet (10 columns)**:
```
ID (UUID8) | BUYER | BUYER_EMAIL | BUYER_PHONE | ORDER_ID |
TRANSACTION_ID | DATE | IMG | PRODUCT_NAME | SHIPPING_NAME
```

---

## 4. Gap Analysis

### 4.1 Functional Gaps

| # | Current Limitation | Odoo 19 CE Solution | Priority |
|---|-------------------|---------------------|----------|
| G1 | **No order status workflow** -- orders are rows with no state | `sale.order` provides Draft -> Confirmed -> Done states; extensible to add Shipped, Fulfilled | Critical |
| G2 | **No customer deduplication** -- each transaction creates a new UUID customer row | `res.partner` with unique constraint on email; `_find_or_create()` pattern | Critical |
| G3 | **No product catalog** -- PRODUCT_NAME is free text per transaction | `product.template` + `product.product` with SKU, variants (color/size), images | High |
| G4 | **No shipping/delivery tracking** -- SHIPPING_SERVICE and address are text fields | `delivery.carrier` for carrier management; `stock.picking` for delivery tracking (if `stock` module installed) | High |
| G5 | **No multi-user access control** -- Google Sheets sharing is all-or-nothing | Odoo user groups: Shop Manager, Fulfillment Operator, Design Viewer, Customer Service | High |
| G6 | **No audit trail** -- changes to sheet data are untracked | Odoo chatter (mail.thread), `mail.tracking.value` on every field change | Medium |
| G7 | **No reporting/analytics** -- manual spreadsheet formulas | Odoo pivot views, graph views, custom reports, dashboard | Medium |
| G8 | **No order-to-invoice flow** -- financial data is just text columns | `account.move` integration via sale order confirmation (requires `account` module) | Medium |
| G9 | **No personalization/design workflow** -- Design Sheet is a passive reference | Custom model or `sale.order.line` extension for design queue with status | Medium |
| G10 | **No image storage** -- IMG_URL is an external Etsy CDN link; IMG is a Google Sheets formula | `ir.attachment` for product images, or store as binary field on product | Low |
| G11 | **No discount/coupon management** -- DISCOUNT_CODE is free text | `sale.loyalty` module for coupon/promo tracking | Low |
| G12 | **No multi-currency support** -- PRICE and SUBTOTAL are raw text | Odoo multi-currency with `res.currency`, pricelist support | Low |

### 4.2 Technical Gaps

| # | Current Limitation | Odoo 19 Solution |
|---|-------------------|-----------------|
| T1 | **Gmail API via standalone OAuth** -- `token.pickle` requires manual refresh | Odoo `google_gmail` module provides built-in OAuth2 with `fetchmail.server` integration |
| T2 | **Regex parsing is fragile** -- any Etsy email format change breaks extraction | Port regex engine into Odoo; add error logging per field; consider fallback/fuzzy matching |
| T3 | **No error recovery** -- failed emails are silently skipped | Odoo `fetchmail.server` has error tracking (`error_date`, `error_message`), auto-deactivation after 5 days of failures |
| T4 | **Country lookup at runtime from Excel** -- `res/iban_countries.xlsx` loaded on every parse | Odoo `res.country` provides ISO codes natively; no external file needed |
| T5 | **No batch processing metrics** -- `print()` statements for debugging | Odoo `_logger` framework, server log rotation, optional monitoring |
| T6 | **Google Sheets 10M cell limit** -- 17,659 rows x 34 cols = ~600K cells (6% of limit) | PostgreSQL: effectively unlimited; partitioning available if needed |

### 4.3 Value-Add Opportunities (Not in Current System)

| Opportunity | Description | Odoo Module |
|-------------|-------------|-------------|
| **CRM Pipeline** | Track Etsy buyers as leads, convert to opportunities | `crm` |
| **Email Marketing** | Send follow-up campaigns to Etsy customers | `mass_mailing` |
| **Inventory Management** | Track stock levels for products sold on Etsy | `stock` |
| **Purchase Orders** | Auto-create POs when stock runs low | `purchase` |
| **Website/eCommerce** | Publish Etsy products on an Odoo-powered website | `website_sale` |
| **Helpdesk** | Customer support ticketing for Etsy buyers | Community alternatives or custom |

---

## 5. Data Migration Requirements

### 5.1 Scope

| Dataset | Volume | Source | Target |
|---------|--------|--------|--------|
| Orders | 17,659 rows x 34 columns | Google Sheets (Main) | `sale.order` + `sale.order.line` + custom fields |
| Designs | ~17,659 rows x 15 columns | Google Sheets (Design) | `sale.order.line` extension or custom model |
| Customers | ~17,659 rows x 10 columns | Google Sheets (Customer) | `res.partner` (deduplicated) |

### 5.2 Migration Strategy

**Phase 1: Data Export**
1. Export all three Google Sheets to CSV using the Sheets API or manual download
2. Validate row counts match expected totals
3. Identify and document data quality issues (nulls, malformed values, encoding)

**Phase 2: Data Transformation**

```
[Raw CSV] --> [Dedup Customers by Email] --> [Create res.partner records]
                                                    |
[Raw CSV] --> [Extract Unique Products by PRODUCT_NAME+SKU] --> [Create product.template]
                                                                        |
[Raw CSV] --> [Map to sale.order (grouped by ORDER_ID)] --> [Create sale.order + sale.order.line]
                     |                                              |
                     +--> [Link to res.partner]                    +--> [Link to product.product]
                     +--> [Map SHOP to etsy.shop]                  +--> [Set custom fields]
```

**Key Transformations**:

| Source Field | Target Model.Field | Transformation |
|-------------|-------------------|----------------|
| TRANSACTION_ID | `sale.order.line.etsy_transaction_id` | Direct copy, unique constraint |
| ORDER_ID | `sale.order.etsy_order_id` | Direct copy; group lines by this |
| SHOP | `sale.order.etsy_shop_id` (M2O to `etsy.shop`) | Map to Etsy shop master record |
| BUYER + BUYER_EMAIL | `res.partner.name` + `res.partner.email` | Dedup by email; merge names |
| SHIPPING_NAME..SHIPPING_COUNTRY | `res.partner` (delivery address) | Create child partner (type=delivery) |
| PRODUCT_NAME + SKU | `product.template.name` + `product.template.default_code` | Dedup by SKU or name |
| COLOR, SIZE, OPTION, SIDE | `product.template.attribute_line_ids` | Map to product attribute variants |
| QUANTITY | `sale.order.line.product_uom_qty` | Cast to float |
| PRICE | `sale.order.line.price_unit` | Clean (remove currency symbols, negative signs) |
| SUBTOTAL | `sale.order.amount_total` | Verify vs computed sum |
| SHIPPING_COST | `sale.order.delivery_price` or custom field | Parse numeric value |
| SHIPPING_SERVICE | `delivery.carrier.name` | Map to carrier master data |
| DATE | `sale.order.date_order` | Parse email date header format |
| IMG_URL | `product.template.image_1920` | Download and store as binary (batch) |
| PERSONALISATION | `sale.order.line.etsy_personalisation` | Text field, direct copy |
| NOTE_FROM_BUYER | `sale.order.note` | Direct copy |
| GIFT_MESSAGE | `sale.order.etsy_gift_message` | Custom field, direct copy |
| DESIGN_LINK_FRONT/BACK | `sale.order.line.etsy_design_link_front/back` | URL fields |
| DISCOUNT_CODE | `sale.order.etsy_discount_code` | Custom field |
| PROCESSING_TIME | `sale.order.line.etsy_processing_time` | Char field |
| FACE_MASK_SIZE | `sale.order.line.etsy_face_mask_size` | Deprecated product-specific; map to variant |

**Phase 3: Data Loading**
1. Load `etsy.shop` master data (Viktor, Julien, Carina, etc.)
2. Load `delivery.carrier` master data (Standard, Express, etc.)
3. Load `res.partner` (deduplicated customers + delivery addresses)
4. Load `product.template` + `product.product` (with variants where applicable)
5. Load `sale.order` headers (grouped by ORDER_ID)
6. Load `sale.order.line` items (linked to orders and products)
7. Set all migrated orders to a "Migrated" or "Done" state (they are historical)

**Phase 4: Validation**
- Row count reconciliation: source CSV rows vs Odoo records
- Financial reconciliation: sum of SUBTOTAL in sheets vs sum of `amount_total` in Odoo
- Customer count: unique emails in sheets vs `res.partner` count
- Transaction ID uniqueness: no duplicates in `sale.order.line.etsy_transaction_id`

### 5.3 Data Quality Issues (Anticipated)

| Issue | Fields Affected | Mitigation |
|-------|----------------|------------|
| Missing emails | BUYER_EMAIL (may be blank) | Create partner with name only; flag for review |
| Inconsistent country names | SHIPPING_COUNTRY | Use the same `iban_countries.xlsx` mapping; fallback to Odoo `res.country` name search |
| Duplicate customers (same buyer, different email) | BUYER | Post-migration dedup wizard |
| Free-text prices with currency symbols | PRICE, SUBTOTAL, SHIPPING_COST | Regex to strip non-numeric characters; manual review of outliers |
| Multi-language personalization labels | PERSONALISATION | Store raw text; label cleanup is not needed (value is buyer-provided) |
| Missing TRANSACTION_ID | Rare edge cases | Generate synthetic ID (e.g., `MIGRATED-{row_number}`) |
| Historical date formats | DATE | Parse with `dateutil.parser.parse()` for flexibility |

---

## 6. User Stories

### US-01: Automated Email Ingestion

**As** a system administrator,
**I want** Etsy order notification emails to be automatically fetched and parsed into Odoo sale orders,
**So that** the team does not need to manually enter order data.

**Acceptance Criteria**:
- **Given** a new Etsy order notification email arrives in the configured Gmail inbox
- **When** the scheduled cron job runs (every 10 minutes)
- **Then** the email is parsed and a new `sale.order` is created with all 34 fields mapped to Odoo fields
- **And** the original email is linked to the sale order via Odoo chatter
- **And** the Gmail label is removed from the processed email

### US-02: Multi-Shop Order Filtering

**As** a shop owner (Viktor/Julien/Carina),
**I want** to see only orders from my specific Etsy shop,
**So that** I can focus on my shop's fulfillment without noise from other shops.

**Acceptance Criteria**:
- **Given** I am logged into Odoo with my shop-specific user account
- **When** I navigate to the Sale Orders list
- **Then** I see only orders where `etsy_shop_id` matches my assigned shop
- **And** I can remove the filter to see all shops if I have multi-shop access
- **And** the dashboard widgets (total orders, revenue) reflect my filtered shop

### US-03: Order Fulfillment Workflow

**As** a fulfillment team member,
**I want** to move orders through a defined workflow (New -> In Progress -> Shipped -> Done),
**So that** everyone can see the current status of each order at a glance.

**Acceptance Criteria**:
- **Given** a new sale order has been created from an Etsy email
- **When** I open the order and click "Confirm"
- **Then** the order moves to "Confirmed" state
- **And** when I record the shipment, the order moves to "Shipped"
- **And** the order appears in the correct kanban column at each stage
- **And** state transitions are logged in the chatter with timestamp and user

### US-04: Customer Deduplication

**As** a customer service representative,
**I want** repeat Etsy buyers to be recognized and linked to their existing Odoo partner record,
**So that** I can see their full order history in one place.

**Acceptance Criteria**:
- **Given** an incoming Etsy order email contains a buyer email address
- **When** the system processes the email
- **Then** it searches `res.partner` for an existing record with that email
- **And** if found, the new sale order is linked to the existing partner
- **And** if not found, a new `res.partner` is created with the buyer's name and email
- **And** the partner's order history shows all orders across all shops

### US-05: Transaction Deduplication

**As** a system administrator,
**I want** duplicate Etsy transactions to be detected and rejected,
**So that** the same order line is never imported twice.

**Acceptance Criteria**:
- **Given** an Etsy email is processed that contains a TRANSACTION_ID
- **When** the TRANSACTION_ID already exists in `sale.order.line.etsy_transaction_id`
- **Then** the duplicate line is skipped
- **And** a warning is logged in the system log
- **And** the rest of the email's transactions (if multi-item) are still processed

### US-06: Design Team Queue

**As** a design team member,
**I want** a dedicated view showing orders that require personalization or custom design work,
**So that** I can prioritize and track my design tasks.

**Acceptance Criteria**:
- **Given** I navigate to the Design Queue view
- **When** the view loads
- **Then** I see only sale order lines where `etsy_personalisation` is not empty OR `etsy_design_link_front` is not empty
- **And** each card shows: product image, product name, personalization text, color, size, side, quantity
- **And** I can mark a design as "Completed" which updates a status field on the order line

### US-07: Product Catalog Auto-Creation

**As** a shop owner,
**I want** new products from Etsy orders to be automatically added to the Odoo product catalog,
**So that** I do not need to manually create product records.

**Acceptance Criteria**:
- **Given** an incoming Etsy order contains a PRODUCT_NAME not yet in the system
- **When** the email is processed
- **Then** a new `product.template` is created with the product name and SKU
- **And** if COLOR or SIZE data is present, product attribute values are created or matched
- **And** the product image is downloaded from IMG_URL and stored as `image_1920`
- **And** if the product already exists (matched by SKU or exact name), the existing product is reused

### US-08: Revenue Reporting by Shop

**As** a business owner,
**I want** to see revenue, order volume, and average order value broken down by Etsy shop and time period,
**So that** I can make informed business decisions.

**Acceptance Criteria**:
- **Given** I navigate to the Sales Analysis report
- **When** I group by "Etsy Shop" and filter by date range
- **Then** I see total revenue, number of orders, and average order value per shop
- **And** I can further drill down by product, country, or month
- **And** the data includes both historical (migrated) and new orders

### US-09: Shipping Address Management

**As** a fulfillment team member,
**I want** each order's shipping address to be properly structured and linked to the customer,
**So that** I can generate accurate shipping labels.

**Acceptance Criteria**:
- **Given** an Etsy order email contains shipping address fields (name, address1, address2, city, state, zip, country)
- **When** the email is processed
- **Then** a delivery address is created as a child `res.partner` (type='delivery') linked to the buyer
- **And** the country name is resolved to an Odoo `res.country` record using ISO Alpha-2 codes
- **And** the delivery address is set as the `partner_shipping_id` on the sale order
- **And** if the same buyer has an identical shipping address from a previous order, the existing address is reused

### US-10: Email Parse Error Handling

**As** a system administrator,
**I want** email parsing failures to be logged with details and retryable,
**So that** no orders are silently lost.

**Acceptance Criteria**:
- **Given** an Etsy notification email cannot be fully parsed (e.g., missing TRANSACTION_ID, unexpected format)
- **When** the parsing error occurs
- **Then** the email is moved to a "Failed" queue (not removed from Gmail label)
- **And** an error record is created in a custom `etsy.import.log` model with: email subject, error message, raw email body, timestamp
- **And** the administrator can view failed imports in a dedicated list view
- **And** the administrator can retry processing from the Odoo UI

### US-11: Gift Message and Buyer Notes

**As** a fulfillment team member,
**I want** gift messages and buyer notes to be prominently displayed on the order,
**So that** I can include the correct note/gift card with the shipment.

**Acceptance Criteria**:
- **Given** an Etsy order has a GIFT_MESSAGE or NOTE_FROM_BUYER
- **When** I view the sale order form
- **Then** the gift message is displayed in a dedicated, visually distinct section
- **And** the buyer note is displayed separately from internal notes
- **And** both fields are visible when printing the delivery slip/packing list

### US-12: Historical Data Migration Verification

**As** a business owner,
**I want** to verify that all 17,659 historical orders have been migrated correctly,
**So that** I can trust the Odoo system as the single source of truth.

**Acceptance Criteria**:
- **Given** the data migration has been completed
- **When** I run the migration verification report
- **Then** the total number of sale order lines matches the source row count (17,659)
- **And** the sum of order subtotals matches the source spreadsheet total (within rounding tolerance)
- **And** the number of unique customers in Odoo is less than or equal to the source (due to dedup)
- **And** every TRANSACTION_ID from the source exists exactly once in Odoo

---

## 7. Business Rules

### 7.1 Deduplication Rules

| Rule ID | Rule | Implementation |
|---------|------|---------------|
| BR-DUP-01 | **Transaction-level dedup**: No two `sale.order.line` records may share the same `etsy_transaction_id` | SQL unique constraint on `sale_order_line.etsy_transaction_id` (where not null) |
| BR-DUP-02 | **Order-level dedup**: An ORDER_ID from an email subject must be checked against existing `sale.order.etsy_order_id` before processing | Python check in email parser; skip entire email if ORDER_ID exists |
| BR-DUP-03 | **Within-batch dedup**: Multiple emails in the same 10-minute batch that reference the same TRANSACTION_ID must be deduplicated | In-memory set of processed IDs within a single cron run (mirrors current `processed_ids` logic) |
| BR-DUP-04 | **Customer dedup by email**: Buyers with the same email address map to the same `res.partner` | `res.partner._find_or_create(email)` or custom search-then-create |
| BR-DUP-05 | **Delivery address dedup**: Identical shipping addresses (same name + street + city + zip + country) for the same partner should reuse existing child partner | Hash-based comparison before creating new delivery address |

### 7.2 Multi-Shop Rules

| Rule ID | Rule | Implementation |
|---------|------|---------------|
| BR-SHOP-01 | Every sale order must be assigned to exactly one Etsy shop | Required `Many2one` field `etsy_shop_id` on `sale.order` |
| BR-SHOP-02 | Shop names are extracted from the "Shop:" field in email body | Regex pattern: `(?<=Shop:).*` |
| BR-SHOP-03 | If a shop name is not found in master data, create a new `etsy.shop` record automatically | `etsy.shop._find_or_create(name)` |
| BR-SHOP-04 | Shop owners may only view/edit orders belonging to their assigned shop(s) | Record rule on `sale.order`: `[('etsy_shop_id', 'in', user.etsy_shop_ids.ids)]` |
| BR-SHOP-05 | Cross-shop reporting is available only to the Administrator and Business Owner roles | Group-based access: `group_etsy_manager` has cross-shop access |

### 7.3 Multi-Language Personalization Rules

| Rule ID | Rule | Implementation |
|---------|------|---------------|
| BR-LANG-01 | The system must recognize personalization field labels in English (`Personalization:`), British English (`Personalisation:`), and German (`Personalisierun:`, `Personalisierung:`) | Regex: `(?=Personalization:\|Personalisation:\|personalisation:\|Personalisierun:\|Personalisierung:)` |
| BR-LANG-02 | Color field labels must be recognized in both American (`Color:`) and British (`Colour:`) English, plus uppercase variants | Regex: `(?:(?=Color:)\|(?=Colour:)\|(?=color:)\|(?=COLOR:)\|(?=COLOUR:))` |
| BR-LANG-03 | The parsed value (buyer's input) is stored as-is, regardless of label language | No transformation on the extracted value; preserve Unicode |
| BR-LANG-04 | New label variants may be added without code changes | Store label variants in an Odoo configuration record (equivalent to `strings.json`), editable by admin |

### 7.4 Country Code Mapping Rules

| Rule ID | Rule | Implementation |
|---------|------|---------------|
| BR-CC-01 | Full country names from Etsy emails must be mapped to ISO 3166-1 Alpha-2 codes | Use Odoo `res.country` (which stores Alpha-2 codes natively) |
| BR-CC-02 | Country lookup must be case-insensitive and handle partial matches | `self.env['res.country'].search([('name', 'ilike', country_name)], limit=1)` |
| BR-CC-03 | If no country match is found, store the raw text in a fallback field and flag for manual review | Custom field `etsy_country_raw` on `res.partner`; create activity for admin |
| BR-CC-04 | The external `iban_countries.xlsx` file is eliminated; all country data comes from Odoo master data | No external file dependency; `res.country` is pre-populated with 249 countries |

### 7.5 Pricing and Financial Rules

| Rule ID | Rule | Implementation |
|---------|------|---------------|
| BR-FIN-01 | PRICE represents the unit price per item (before discount) | Maps to `sale.order.line.price_unit` |
| BR-FIN-02 | SUBTOTAL is the order-level total (sum of all lines after discounts + shipping) | Maps to `sale.order.amount_total`; validated against computed value |
| BR-FIN-03 | SHIPPING_COST is a per-order cost, not per-line | Maps to a dedicated delivery line on `sale.order` or custom field |
| BR-FIN-04 | DISCOUNT_CODE is informational only (no automatic discount calculation) | Stored as text field on `sale.order`; manual discount via `price_reduce` if needed |
| BR-FIN-05 | Negative signs in PRICE values are stripped (current behavior) | Clean during parsing: `price.replace('-', '')` |

### 7.6 Image Handling Rules

| Rule ID | Rule | Implementation |
|---------|------|---------------|
| BR-IMG-01 | Product images are extracted from HTML email content via Etsy CDN URLs | Regex on `i.etsystatic.com` domain |
| BR-IMG-02 | Thumbnail URLs (75x75) are upscaled to 300x300 | String replacement before storage |
| BR-IMG-03 | Images are downloaded and stored as binary attachments in Odoo | `ir.attachment` or `product.template.image_1920` binary field |
| BR-IMG-04 | If image download fails, the URL is stored as a fallback | `product.template.etsy_image_url` char field |

---

## 8. Risk Assessment

### 8.1 Risk Matrix

| ID | Risk | Likelihood | Impact | Severity | Mitigation |
|----|------|-----------|--------|----------|------------|
| R1 | **Etsy changes email format** -- regex patterns break | High | Critical | **Critical** | Version the regex patterns in Odoo; add format-change detection (log when expected fields are empty); implement email quarantine for unparseable messages |
| R2 | **Gmail API quota exhaustion** -- daily limit of 1B quota units (but individual operations have costs) | Low | High | **Medium** | Batch processing (current); monitor quota usage via Google Cloud Console; implement exponential backoff |
| R3 | **OAuth token refresh failure** -- `token.pickle` expires and cannot auto-refresh | Medium | Critical | **High** | Odoo `google_gmail` module handles token refresh natively via `google.gmail.mixin`; monitor token expiration; alert admin 7 days before expiry |
| R4 | **Data loss during migration** -- rows dropped or corrupted in CSV export/import | Low | Critical | **High** | Checksum validation at every stage; row count reconciliation; parallel running period (both systems active for 30 days) |
| R5 | **Performance degradation** -- Odoo cron takes longer than 10 minutes per cycle | Low | Medium | **Low** | Profile email parsing; batch size limits (current: 50 per server in `_fetch_mail`); optimize regex compilation (compile once, reuse) |
| R6 | **Multi-shop access control misconfiguration** -- shop owner sees other shop's data | Medium | High | **High** | Record rules with automated tests; security audit before go-live; penetration testing on role boundaries |
| R7 | **Etsy sends emails in new language** -- unrecognized field labels | Medium | Medium | **Medium** | Configurable label variants (not hardcoded); monitoring for unmatched labels; quarterly regex review |
| R8 | **Google Sheets data inconsistency** -- source data has hidden errors | Medium | Medium | **Medium** | Pre-migration data audit; spot-check 100 random records; reconciliation report |
| R9 | **Odoo 19 CE lacks features available in Enterprise** -- e.g., advanced reports, studio | Low | Medium | **Low** | Identify Enterprise-only features needed upfront; build custom alternatives or install OCA modules |
| R10 | **VPS/server downtime** -- email collection stops | Low | High | **Medium** | Docker-based deployment with restart policy; health check monitoring; email backlog accumulates safely in Gmail |

### 8.2 Risk Response Plan

**For R1 (Email Format Change) -- Highest Priority Risk**:
1. **Detection**: After each parsing run, log the percentage of fields that returned empty. If > 20% of orders have empty TRANSACTION_ID or PRODUCT_NAME, trigger an alert.
2. **Quarantine**: Unparseable emails remain labeled in Gmail (label not removed). A separate Odoo view shows "Pending Review" emails.
3. **Rapid Response**: Regex patterns stored in Odoo `ir.config_parameter` or a dedicated model, editable by admin without code deployment.
4. **Testing**: Maintain a library of 50+ sample Etsy email bodies as test fixtures. Run regression tests on regex changes.

**For R3 (OAuth Token Refresh)**:
1. Odoo `google_gmail` module stores `google_gmail_refresh_token` and `google_gmail_access_token` on the `fetchmail.server` record.
2. Token refresh is handled automatically by `_generate_oauth2_string()` in `google.gmail.mixin`.
3. If refresh fails, `fetchmail.server.error_date` is set; after 5 days of continuous failure, the server is auto-deactivated and admin is notified.
4. Add a scheduled action to check token validity proactively (weekly).

---

## 9. Success Metrics

### 9.1 Migration Success KPIs

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **Data completeness** | 100% of source TRANSACTION_IDs exist in Odoo | SQL query: `SELECT COUNT(DISTINCT etsy_transaction_id) FROM sale_order_line WHERE etsy_transaction_id IS NOT NULL` vs source CSV row count |
| **Financial accuracy** | Order totals within 0.01 tolerance of source | Compare `SUM(amount_total)` in Odoo vs `SUM(SUBTOTAL)` in source (after cleaning) |
| **Customer dedup ratio** | At least 30% reduction in unique customer records | Unique emails in source vs `res.partner` count in Odoo |
| **Zero data loss** | No TRANSACTION_ID from source missing in Odoo | Full outer join between source CSV and Odoo extract |
| **Migration duration** | Complete within 4 hours | Timed execution of migration scripts |

### 9.2 Operational Success KPIs (Post Go-Live)

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **Email-to-order latency** | < 15 minutes from email receipt to Odoo sale order | Compare `mail.message.date` vs `sale.order.create_date` |
| **Parse success rate** | > 99% of emails successfully parsed | `etsy.import.log` records with status='success' / total |
| **System uptime** | > 99.5% (< 3.65 hours downtime/month) | Monitoring (e.g., Netdata, uptime checks) |
| **User adoption** | 100% of stakeholders using Odoo within 30 days of go-live | Login audit trail |
| **Parallel run accuracy** | 100% match between Odoo and Google Sheets during parallel period | Daily reconciliation report |
| **Order processing time** | 20% reduction in time from order receipt to shipment | Compare average `date_order` to shipment date, before vs after |

### 9.3 Business Value KPIs (3 months post go-live)

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **Time saved on manual data entry** | Eliminate 100% of manual sheet work | Team survey + time tracking |
| **Reporting speed** | Ad-hoc reports in < 2 minutes (vs hours in Sheets) | User feedback |
| **Customer service response time** | 30% faster (due to 360 customer view) | Average resolution time |
| **Error rate** | < 1% order data errors (vs estimated 3-5% in current system) | Weekly spot-check audit |

---

## 10. Non-Functional Requirements

### 10.1 Performance

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| NFR-PERF-01 | Email polling interval: configurable, default 10 minutes | Match current system behavior; adjustable via `ir.cron` |
| NFR-PERF-02 | Email parse time: < 2 seconds per email | Current system processes ~50 emails in < 60 seconds |
| NFR-PERF-03 | Batch size: process up to 100 emails per cron run | Odoo default is 50; increase for peak periods (e.g., holiday sales) |
| NFR-PERF-04 | Google Sheets update eliminated | Zero latency to external APIs for data storage |
| NFR-PERF-05 | Database query response: < 500ms for order list views with 100K records | Standard Odoo indexing + custom indexes on `etsy_transaction_id`, `etsy_order_id` |

### 10.2 Reliability

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| NFR-REL-01 | Failed email parsing must not block subsequent emails | Each email processed in its own transaction (Odoo `_fetch_mail` pattern: commit after each message) |
| NFR-REL-02 | System must recover from Gmail API temporary failures | Exponential backoff; Odoo's built-in 5-day error tolerance with auto-deactivation |
| NFR-REL-03 | Database backup: daily automated backup | PostgreSQL `pg_dump` via cron; 30-day retention |
| NFR-REL-04 | Container restart policy: `unless-stopped` | Docker Compose `restart: unless-stopped` |
| NFR-REL-05 | No single point of failure for credential storage | OAuth tokens stored in Odoo DB (encrypted); backup credentials in secure vault |

### 10.3 Data Integrity

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| NFR-INT-01 | `etsy_transaction_id` must be unique across all `sale.order.line` records | SQL unique partial index: `CREATE UNIQUE INDEX ON sale_order_line (etsy_transaction_id) WHERE etsy_transaction_id IS NOT NULL` |
| NFR-INT-02 | `etsy_order_id` must be unique across all `sale.order` records | SQL unique partial index on `sale_order` |
| NFR-INT-03 | Every `sale.order` must reference a valid `res.partner` | Foreign key constraint (native Odoo Many2one) |
| NFR-INT-04 | Every `sale.order.line` must reference a valid `product.product` | Foreign key constraint (native Odoo Many2one) |
| NFR-INT-05 | Financial fields (`price_unit`, `product_uom_qty`) must be non-negative | Python `@api.constrains` validation |
| NFR-INT-06 | Country codes must resolve to valid `res.country` records | Constraint + fallback field for unresolved countries |

### 10.4 Security

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| NFR-SEC-01 | Gmail OAuth credentials must not be stored in source code | Odoo `fetchmail.server` stores tokens in DB; `credentials.json` in Docker secret mount |
| NFR-SEC-02 | Shop-level data isolation via Odoo record rules | `ir.rule` on `sale.order` filtering by `etsy_shop_id` |
| NFR-SEC-03 | Customer PII (email, phone, address) accessible only to authorized roles | Field-level access groups or record rules on `res.partner` |
| NFR-SEC-04 | All API communications over HTTPS/TLS | Gmail API enforces TLS; Odoo behind reverse proxy with SSL |
| NFR-SEC-05 | Audit log for all order state changes | Odoo chatter (`mail.thread`) on `sale.order` |

### 10.5 Scalability

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| NFR-SCA-01 | Support up to 100,000 orders without performance degradation | PostgreSQL handles this natively; proper indexing required |
| NFR-SCA-02 | Support up to 20 Etsy shops | `etsy.shop` model with no hard-coded shop list |
| NFR-SCA-03 | Support up to 10 concurrent users | Odoo 19 CE with workers=4 handles this comfortably |

### 10.6 Maintainability

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| NFR-MNT-01 | Regex patterns must be editable without code deployment | Store in `ir.config_parameter` or dedicated model with UI |
| NFR-MNT-02 | Field label variants (strings.json equivalent) must be admin-configurable | Dedicated `etsy.field.label` model |
| NFR-MNT-03 | Module must follow Odoo 19 coding standards | Ruff linting, standard module structure |
| NFR-MNT-04 | Automated tests with > 80% code coverage | Unit tests for regex parsing, integration tests for email-to-order flow |

---

## 11. Recommended Module Architecture

### 11.1 Module: `etsy_order_import`

```
custom_addons/etsy_order_import/
+-- __manifest__.py
+-- __init__.py
+-- models/
|   +-- __init__.py
|   +-- etsy_shop.py              # etsy.shop: master data for Etsy shops
|   +-- etsy_import_log.py        # etsy.import.log: parsing error tracking
|   +-- etsy_regex_pattern.py     # etsy.regex.pattern: configurable regex rules
|   +-- etsy_field_label.py       # etsy.field.label: multi-language label config
|   +-- sale_order.py             # sale.order extension: etsy_* custom fields
|   +-- sale_order_line.py        # sale.order.line extension: etsy_* custom fields
|   +-- res_partner.py            # res.partner extension: Etsy buyer fields
|   +-- product_template.py       # product.template extension: Etsy product fields
|   +-- fetchmail_server.py       # fetchmail.server extension: Etsy email parsing
+-- views/
|   +-- etsy_shop_views.xml
|   +-- etsy_import_log_views.xml
|   +-- sale_order_views.xml      # Form/tree/search view extensions
|   +-- sale_order_line_views.xml
|   +-- res_partner_views.xml
|   +-- etsy_dashboard.xml
|   +-- menu.xml
+-- security/
|   +-- ir.model.access.csv
|   +-- etsy_security.xml         # Groups + record rules
+-- data/
|   +-- etsy_cron.xml             # Scheduled action for email polling
|   +-- etsy_regex_data.xml       # Default regex patterns (from regex_02.json)
|   +-- etsy_label_data.xml       # Default field labels (from strings.json)
+-- wizard/
|   +-- etsy_import_wizard.py     # Manual import wizard (CSV upload)
|   +-- etsy_migration_wizard.py  # One-time historical data migration
+-- report/
|   +-- etsy_order_report.xml     # Custom report templates
+-- tests/
|   +-- __init__.py
|   +-- test_email_parsing.py     # Regex parsing unit tests
|   +-- test_deduplication.py     # Dedup logic tests
|   +-- test_country_mapping.py   # Country code resolution tests
|   +-- test_order_creation.py    # End-to-end email-to-order tests
|   +-- test_access_rights.py     # Security/access control tests
+-- static/
|   +-- description/
|   |   +-- icon.png
|   |   +-- index.html
+-- i18n/
    +-- etsy_order_import.pot
```

### 11.2 Dependencies

```python
# __manifest__.py
{
    'name': 'Etsy Order Import',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'depends': [
        'sale_management',    # Sale order workflow
        'contacts',           # Partner management
        'product',            # Product catalog
        'delivery',           # Shipping carriers
        'mail',               # Fetchmail + chatter
        'google_gmail',       # Gmail OAuth2 integration
    ],
    'data': [...],
    'installable': True,
    'application': True,
}
```

### 11.3 Key Model Extensions

**`sale.order`** (additional fields):
- `etsy_order_id` (Char, indexed, unique)
- `etsy_shop_id` (Many2one -> `etsy.shop`)
- `etsy_gift_message` (Text)
- `etsy_discount_code` (Char)
- `etsy_import_date` (Datetime)

**`sale.order.line`** (additional fields):
- `etsy_transaction_id` (Char, indexed, unique)
- `etsy_personalisation` (Text)
- `etsy_design_link_front` (Char/URL)
- `etsy_design_link_back` (Char/URL)
- `etsy_processing_time` (Char)
- `etsy_design_status` (Selection: pending/in_progress/completed)

**`res.partner`** (additional fields):
- `etsy_buyer_name` (Char) -- original Etsy display name
- `is_etsy_customer` (Boolean)

**`product.template`** (additional fields):
- `etsy_product_name` (Char) -- original Etsy listing name
- `etsy_image_url` (Char) -- fallback URL if image download fails

### 11.4 Security Groups

| Group | Internal Name | Access |
|-------|--------------|--------|
| Etsy User | `group_etsy_user` | View own shop orders (read-only) |
| Etsy Operator | `group_etsy_operator` | Create/edit orders, manage fulfillment |
| Etsy Shop Manager | `group_etsy_shop_manager` | Full CRUD on assigned shop(s) |
| Etsy Administrator | `group_etsy_admin` | Full access to all shops, config, regex patterns |

---

## 12. Appendices

### Appendix A: Field Mapping Reference (Complete)

| # | Source Field | Source Type | Target Model | Target Field | Target Type | Notes |
|---|------------|------------|-------------|-------------|------------|-------|
| 1 | TRANSACTION_ID | Text | sale.order.line | etsy_transaction_id | Char(64) | Unique constraint |
| 2 | IMG_URL | URL | product.template | etsy_image_url | Char(512) | Fallback storage |
| 3 | IMG | Formula | product.template | image_1920 | Binary | Download from URL |
| 4 | DATE | Text | sale.order | date_order | Datetime | Parse email header date |
| 5 | NOTE_FROM_BUYER | Text | sale.order | note | Text | Internal note |
| 6 | GIFT_MESSAGE | Text | sale.order | etsy_gift_message | Text | Custom field |
| 7 | PERSONALISATION | Text | sale.order.line | etsy_personalisation | Text | Multi-language input |
| 8 | SKU | Text | product.template | default_code | Char(64) | Product reference |
| 9 | SHOP | Text | sale.order | etsy_shop_id | Many2one | FK to etsy.shop |
| 10 | ORDER_ID | Text | sale.order | etsy_order_id | Char(64) | Unique constraint |
| 11 | SHIPPING_NAME | Text | res.partner | name | Char | Delivery address partner |
| 12 | SHIPPING_ADDRESS1 | Text | res.partner | street | Char | Delivery address |
| 13 | SHIPPING_ADDRESS2 | Text | res.partner | street2 | Char | Delivery address |
| 14 | SHIPPING_CITY | Text | res.partner | city | Char | Delivery address |
| 15 | SHIPPING_STATE | Text | res.partner | state_id | Many2one | res.country.state lookup |
| 16 | SHIPPING_ZIPCODE | Text | res.partner | zip | Char | Delivery address |
| 17 | SHIPPING_COUNTRY | Text | res.partner | country_id | Many2one | res.country lookup |
| 18 | SHIPPING_PHONE | Text | res.partner | phone | Char | Delivery address |
| 19 | SHIPPING_EMAIL | Text | res.partner | email | Char | Buyer email |
| 20 | PRODUCT_NAME | Text | product.template | name | Char | Auto-create if new |
| 21 | OPTION | Text | sale.order.line | etsy_option | Char | Product variant hint |
| 22 | COLOR | Text | product.attribute.value | name | Char | Attribute: Color |
| 23 | SIZE | Text | product.attribute.value | name | Char | Attribute: Size |
| 24 | SIDE | Text | sale.order.line | etsy_side | Char | Custom field |
| 25 | FACE_MASK_SIZE | Text | sale.order.line | etsy_face_mask_size | Char | Legacy product-specific |
| 26 | QUANTITY | Text | sale.order.line | product_uom_qty | Float | Cast to numeric |
| 27 | DESIGN_LINK_FRONT | URL | sale.order.line | etsy_design_link_front | Char(512) | URL field |
| 28 | DESIGN_LINK_BACK | URL | sale.order.line | etsy_design_link_back | Char(512) | URL field |
| 29 | SHIPPING_SERVICE | Text | delivery.carrier | name | Char | Lookup/create carrier |
| 30 | PROCESSING_TIME | Text | sale.order.line | etsy_processing_time | Char | Raw text |
| 31 | SHIPPING_COST | Text | sale.order | etsy_shipping_cost | Float | Parse numeric |
| 32 | PRICE | Text | sale.order.line | price_unit | Float | Parse, strip negatives |
| 33 | DISCOUNT_CODE | Text | sale.order | etsy_discount_code | Char | Informational |
| 34 | SUBTOTAL | Text | sale.order | amount_total | Float | Verify vs computed |

### Appendix B: Regex Patterns (from regex_02.json)

The following 43 regex patterns will be migrated into the `etsy.regex.pattern` model:

```
TRANSACTION_IDS: (?<=Order details|Order Details)(.|\n)*(?=Item total:)
TRANSACTION_SPLIT: (?=Transaction ID)
TRANSACTION_ID: (?=Transaction ID:)
PRODUCT_NAME: (?=Item:)
SIZE: (?=Size:|size:|SIZE:)
COLOR: (?:(?=Color:)|(?=Colour:)|(?=color:)|(?=COLOR:)|(?=COLOUR:))
PERSONALISATION: (?=Personalization:|Personalisation:|personalisation:|Personalisierun:|Personalisierung:)
ORDER_ID: (?<=http://www.etsy.com/your/orders/).*(?=\n)
SHOP: (?<=Shop:).*
SHIPPING_NAME: (?<=[^-]name'>)[^<]*
SHIPPING_ADDRESS1: (?<=first-line'>)[^<]*
SHIPPING_COUNTRY: (?<=country-name'>)[^<]*
... (full list preserved from regex_02.json)
```

### Appendix C: Etsy Shop Master Data

| Shop Name | Status | Notes |
|-----------|--------|-------|
| Viktor | Active | Primary shop |
| Julien | Active | |
| Carina | Active | |
| (others TBD) | TBD | Extract unique SHOP values from migration data |

### Appendix D: Parallel Run Plan

| Week | Activity |
|------|----------|
| Week 1 | Deploy Odoo module; begin email processing in Odoo alongside existing system |
| Week 2 | Daily reconciliation: compare Odoo orders vs Google Sheets entries |
| Week 3 | Fix discrepancies; tune regex patterns; resolve edge cases |
| Week 4 | Stakeholder sign-off; cut over to Odoo as primary; keep Sheets as read-only backup |
| Week 5+ | Decommission Google Sheets pipeline; remove Gmail label processing from old system |

### Appendix E: Glossary

| Term | Definition |
|------|-----------|
| **TRANSACTION_ID** | Etsy's unique identifier for a single line item within an order |
| **ORDER_ID** | Etsy's unique identifier for an order (may contain multiple transactions) |
| **Shop** | An individual Etsy storefront (e.g., Viktor, Julien) |
| **Personalisation** | Buyer-provided custom text for product customization |
| **fetchmail.server** | Odoo's built-in model for incoming email server configuration |
| **google_gmail** | Odoo 19 CE module providing Gmail OAuth2 integration for fetchmail |
| **Record Rule** | Odoo's row-level security mechanism filtering records by domain |
| **Chatter** | Odoo's built-in activity and messaging system on records |

---

*End of Business Analysis Report*
