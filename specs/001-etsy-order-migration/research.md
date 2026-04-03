# Research: Etsy Order Migration

**Feature**: 001-etsy-order-migration
**Date**: 2026-04-02

## 1. Current System Analysis

### 1.1 Architecture

```
Gmail Inbox (labeled emails)
    |
    v
Gmail API (OAuth2) --- token.pickle + credentials.json
    |
    v
Python Script (read_emails.py, 487 lines)
    |-- regex_02.json (43 patterns)
    |-- strings.json (multi-language labels)
    |-- regex_constants.py (60 field constants)
    |-- res/iban_countries.xlsx (country mapping)
    |
    v
pandas DataFrame
    |
    v
Google Sheets API (gspread) --- service_account.json
    |
    v
3 Google Sheets:
    - Orders (34 columns, 17,659 rows)
    - Designs (15 columns)
    - Customers (10 columns)
```

### 1.2 Email Parsing Pipeline

1. **Fetch**: Gmail API `messages.list()` with label filter, paginated
2. **Dedup Check**: Extract ORDER_ID from email subject `[orderid]` or `(orderid)`, check against existing sheet data
3. **Decode**: Base64-decode email body (plain text + HTML parts)
4. **Extract Transactions**: Regex split between "Order details" and "Item total:" markers, then split by "Transaction ID" boundaries
5. **Per Transaction**:
   - Product name, SKU from plain text
   - Options (size, color, style, quantity, etc.) from plain text with multi-language label matching
   - Pricing (item price, shipping cost, discount, subtotal) from plain text
   - Shipping address fields from HTML (CSS class-based selectors like `first-line'>`, `city'>`)
   - Image URLs from HTML (etsystatic.com domain regex)
   - Buyer info and notes from plain text
6. **Country Mapping**: Country name -> ISO Alpha-2 via Excel lookup
7. **Output**: DataFrame -> Google Sheets batch update
8. **Cleanup**: Remove Gmail label from processed messages

### 1.3 Data Volume Analysis

- **Total orders**: 17,659
- **Columns per order**: 34
- **Shops identified**: Viktor, Julien, Carina (possibly more)
- **Currency**: EUR (all prices)
- **Date range**: June 2025 onwards (based on sample data)
- **Average order**: 1-2 line items, EUR 15-25 price range
- **Product types**: Handcrafted goods (ring dishes, temporary tattoos, personalized items)

### 1.4 Identified Issues in Current System

| Issue | Severity | Impact |
|-------|----------|--------|
| Credentials committed to git | CRITICAL | Security breach risk |
| No error handling for API failures | HIGH | Silent data loss |
| No tests | HIGH | Regression risk |
| `print()` instead of logging | MEDIUM | No audit trail |
| Brittle regex tied to email format | MEDIUM | Breaks on Etsy template changes |
| Country mapping via Excel file | LOW | Stale data, should use ISO library |
| Opens strings.json on every iteration | LOW | Performance (minor) |
| No monitoring/alerting | HIGH | Undetected failures |

## 2. Odoo 19 CE Capabilities Assessment

### 2.1 Relevant Built-in Modules

| Module | Relevance | Notes |
|--------|-----------|-------|
| `sale` | CORE | sale.order, sale.order.line — main data model |
| `contacts` | CORE | res.partner — customer management |
| `product` | CORE | product.product, product.template — product catalog |
| `mail` | USEFUL | Mail threading, activity scheduling, notifications |
| `base` | CORE | ir.cron, ir.config_parameter, res.country |
| `web` | CORE | OWL 2 framework for custom views |
| `board` | USEFUL | Dashboard creation (CE) |

### 2.2 CE vs EE Feature Gap (for this project)

| Feature | CE | EE | Impact |
|---------|----|----|--------|
| Sale orders | Yes | Yes | No gap |
| Product catalog | Yes | Yes | No gap |
| CRM | Yes | Yes (more) | CE sufficient |
| Reporting (pivot/graph) | Yes | Yes (more) | CE sufficient for basic reports |
| Studio | No | Yes | Must code all customizations |
| Marketing automation | No | Yes | Not needed |
| Inventory | Yes | Yes | Optional for Phase 2+ |
| Multi-currency | Yes | Yes | Needed for EUR |

**Conclusion**: CE is sufficient for Phase 1 and likely Phase 2. No EE blockers identified.

### 2.3 Odoo 19 Specific Features

- **Python 3.12+**: Modern Python features available (match/case, etc.)
- **OWL 2**: Component-based frontend framework
- **Improved ORM**: Better performance for bulk operations
- **ir.cron enhancements**: Better scheduling and error handling
- **fetchmail module**: Built-in IMAP integration (alternative to Gmail API)

## 3. Etsy API Investigation

### 3.1 Etsy Open API v3

Etsy provides an official REST API (Open API v3) that could replace email parsing:

| Aspect | Email Parsing (Current) | Etsy API (Future) |
|--------|------------------------|-------------------|
| Reliability | Fragile (regex) | Stable (structured JSON) |
| Data completeness | Limited to email content | Full order data |
| Real-time | 10-min polling | Webhook possible |
| Authentication | Gmail OAuth2 | Etsy OAuth2 (different) |
| Rate limits | Gmail: 250 quota units/sec | Etsy: 10 req/sec |
| Setup complexity | Medium | High (Etsy app registration) |

**Recommendation**: Phase 1 uses email parsing (proven, working). Phase 3 evaluates Etsy API migration as a strategic upgrade path.

## 4. Data Model Mapping

### 4.1 Field-to-Odoo Mapping (Complete)

| # | Current Field | Odoo Model | Odoo Field | Type | Notes |
|---|--------------|------------|------------|------|-------|
| 1 | TRANSACTION_ID | sale.order.line | etsy_transaction_id | Char | Unique constraint |
| 2 | IMG_URL | sale.order.line | etsy_image_url | Char | URL to etsystatic.com |
| 3 | IMG | - | - | - | Google Sheets formula, not needed |
| 4 | DATE | sale.order | date_order | Datetime | Parse from email date header |
| 5 | NOTE_FROM_BUYER | sale.order | etsy_note_from_buyer | Text | Buyer note |
| 6 | GIFT_MESSAGE | sale.order | etsy_gift_message | Text | Gift message |
| 7 | PERSONALISATION | sale.order.line | etsy_personalisation | Text | Per-line customization |
| 8 | SKU | sale.order.line | etsy_sku | Char | Etsy SKU |
| 9 | SHOP | sale.order | etsy_shop_id | M2O -> etsy.shop | Shop reference |
| 10 | ORDER_ID | sale.order | etsy_order_id | Char | Unique constraint |
| 11 | SHIPPING_NAME | res.partner | name | Char | Delivery address partner |
| 12 | SHIPPING_ADDRESS1 | res.partner | street | Char | Address line 1 |
| 13 | SHIPPING_ADDRESS2 | res.partner | street2 | Char | Address line 2 |
| 14 | SHIPPING_CITY | res.partner | city | Char | City |
| 15 | SHIPPING_STATE | res.partner | state_id | M2O -> res.country.state | State/province |
| 16 | SHIPPING_ZIPCODE | res.partner | zip | Char | Postal code |
| 17 | SHIPPING_COUNTRY | res.partner | country_id | M2O -> res.country | ISO Alpha-2 mapped |
| 18 | SHIPPING_PHONE | res.partner | phone | Char | Phone number |
| 19 | SHIPPING_EMAIL | res.partner | email | Char | Email address |
| 20 | PRODUCT_NAME | product.product | name | Char | Product name |
| 21 | OPTION | sale.order.line | etsy_option | Char | Product option |
| 22 | COLOR | sale.order.line | etsy_color | Char | Color variant |
| 23 | SIZE | sale.order.line | etsy_size | Char | Size variant |
| 24 | SIDE | sale.order.line | etsy_side | Char | Side specification |
| 25 | FACE_MASK_SIZE | sale.order.line | etsy_face_mask_size | Char | Specific product attr |
| 26 | QUANTITY | sale.order.line | product_uom_qty | Float | Standard Odoo field |
| 27 | DESIGN_LINK_FRONT | sale.order.line | etsy_design_link_front | Char | URL |
| 28 | DESIGN_LINK_BACK | sale.order.line | etsy_design_link_back | Char | URL |
| 29 | SHIPPING_SERVICE | sale.order | etsy_shipping_service | Char | Standard/Express |
| 30 | PROCESSING_TIME | sale.order | etsy_processing_time | Char | "9-10 business days" |
| 31 | SHIPPING_COST | sale.order | etsy_shipping_cost | Float | Parse EUR amount |
| 32 | PRICE | sale.order.line | price_unit | Float | Parse EUR amount |
| 33 | DISCOUNT_CODE | sale.order | etsy_discount_code | Char | Applied coupon |
| 34 | SUBTOTAL | sale.order | etsy_subtotal | Float | Parse EUR amount |

### 4.2 New Models Required

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `etsy.shop` | Etsy storefront entity | name, active |
| `etsy.email.log` | Email audit trail | gmail_message_id, raw_body, parse_status, error_message, sale_order_id |
| `etsy.config` | Module configuration (transient) | gmail_label, client_id, client_secret, refresh_token |

## 5. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Etsy changes email template | HIGH | HIGH | Store raw emails; alert on parse failures; keep regex patterns maintainable |
| Gmail OAuth2 token expiry | MEDIUM | HIGH | Implement auto-refresh; alert admin on auth failure |
| Data loss during migration | LOW | CRITICAL | Dry-run import with validation; keep Excel as backup |
| Odoo 19 CE missing needed feature | LOW | MEDIUM | Assessed: CE is sufficient for all Phase 1-2 requirements |
| Performance: bulk import of 17K orders | LOW | MEDIUM | Batch processing with commit intervals |
| Duplicate customer creation | MEDIUM | LOW | Match by email first, then name+zip fallback |
| EUR currency formatting inconsistency | MEDIUM | LOW | Standardize parsing: strip currency symbol, handle comma vs dot |

## 6. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Email fetching method | Gmail API (not IMAP) | Gmail API provides label management and structured message access; IMAP cannot remove labels |
| OAuth2 token storage | ir.config_parameter (encrypted) | Odoo-native, accessible from cron jobs, admin-configurable |
| Parser architecture | Standalone Python module imported by Odoo | Testable independently, replaceable with API parser later |
| Country mapping | Odoo's res.country model | Replace Excel lookup with ORM query; pre-populated with ISO codes |
| Scheduling | ir.cron (10-min interval) | Odoo-native, configurable via UI, includes error handling |
| Historical import | Custom management command / wizard | One-time operation via Odoo wizard reading Excel with openpyxl |
