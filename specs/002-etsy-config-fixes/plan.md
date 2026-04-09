# Implementation Plan: Etsy Config Fixes

**Branch**: `002-etsy-config-fixes` | **Date**: 2026-04-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-etsy-config-fixes/spec.md`

## Summary

Fix all product configuration mismatches, sale order incomplete setup, and Odoo configuration gaps in the etsy_integration module. The existing Phase 1 MVP correctly ingests and parses Etsy order emails/Excel, but imported data lacks financial configuration (taxes, shipping lines, payment terms), products are misconfigured (non-storable, uncategorized), customer dedup is fragile, and all 17,659 orders are stuck in draft. This plan addresses 17 issues across 4 priority levels with a data migration wizard to remediate existing records.

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (sale_management, stock, contacts, mail), openpyxl
**Storage**: PostgreSQL 16+ via Odoo ORM
**Testing**: Odoo TransactionCase, tagged tests (`--test-tags /etsy_integration`)
**Target Platform**: Docker container (namco_odoo19), Linux server
**Project Type**: Odoo module extension (custom_addons/etsy_integration)
**Performance Goals**: Migration wizard processes 17,659 orders in under 30 minutes; import wizard handles 20K rows without browser timeout
**Constraints**: Odoo 19 CE only (no Enterprise), single-threaded workers, must not break existing etsy_integration module
**Scale/Scope**: 17,659 existing orders, 2,294 products, 19 shops, 48 countries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Odoo-Native First | PASS | All fixes use standard Odoo models (fiscal.position, payment.term, product.category, sales.team). No custom parallel structures. |
| II. Email Parser Isolation | PASS | Parser changes are limited to price detection (multi-currency). Parser remains ORM-free. |
| III. Data Integrity First | PASS | Migration wizard uses savepoints. Import wizard moves from cr.commit() to savepoint-based batching. |
| IV. Test-Driven Development | PASS | Each fix will have corresponding tests. Migration wizard testable via TransactionCase. |
| V. Incremental Migration | PASS | This is Phase 2 work (product catalog, customer CRM, reporting) per constitution. Builds on Phase 1. |
| VI. Security by Default | PASS | No new credentials. Shop-level record rules add security. |
| VII. Simplicity Over Completeness | PASS | JSON keyword file over DB model for categories. No product variants (deferred). No auto-merge of partners. |

## Project Structure

### Documentation (this feature)

```text
specs/002-etsy-config-fixes/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit-tasks)
```

### Source Code (repository root)

```text
custom_addons/etsy_integration/
├── __manifest__.py                          # Add new data files
├── models/
│   ├── sale_order.py                        # Add etsy_has_discount computed field
│   ├── sale_order_line.py                   # Add etsy_design_status field
│   ├── product_product.py                   # Add category assignment helper
│   └── res_users.py                         # NEW: Add etsy_shop_ids M2M for record rules
├── services/
│   ├── order_creator.py                     # Multi-currency, shipping line, fiscal pos, categories, dedup
│   ├── image_downloader.py                  # Batch size limit
│   └── product_categorizer.py               # NEW: Keyword-based product categorization service
├── wizards/
│   ├── import_orders_wizard.py              # Header mapping, savepoints, multi-currency, auto-confirm
│   └── data_migration_wizard.py             # NEW: Batch fix existing records
├── views/
│   ├── data_migration_wizard_views.xml      # NEW: Migration wizard form
│   ├── etsy_discount_views.xml              # NEW: Discount analytics pivot/graph
│   ├── etsy_design_queue_views.xml          # Add status column and filter
│   └── menu.xml                             # Add migration wizard menu item
├── data/
│   ├── etsy_fiscal_data.xml                 # NEW: Fiscal position, tax, payment term, sales team, pricelists
│   ├── etsy_product_categories.xml          # NEW: Product category hierarchy
│   ├── product_category_keywords.json       # NEW: Keyword-to-category mapping
│   ├── ir_cron_data.xml                     # Add image download cron
│   └── etsy_shipping_product.xml            # NEW: Shipping service product
├── security/
│   ├── ir.model.access.csv                  # Add migration wizard ACL
│   └── etsy_security.xml                    # Add shop-level record rules
└── tests/
    ├── test_multi_currency_parsing.py       # NEW: EUR/USD/GBP price parsing
    ├── test_data_migration.py               # NEW: Migration wizard tests
    ├── test_product_categorizer.py          # NEW: Keyword categorization tests
    └── test_import_wizard_headers.py        # NEW: Header-based mapping tests
```

**Structure Decision**: All changes within the existing `custom_addons/etsy_integration/` module. No new modules needed. New files are added to existing directories following the established pattern.

---

## Phase 0: Research

### R1: Odoo 19 Fiscal Position and Tax Setup

**Decision**: Create fiscal position + 0% tax via XML data file (`noupdate="1"`)
**Rationale**: Standard Odoo pattern for module-provided master data. Fiscal position maps no tax to the 0% "Etsy Tax Collected" tax. Applied to orders during creation.
**Alternatives considered**: Manual setup via UI (rejected: not reproducible), ir.config_parameter (rejected: not the right model for tax config)

### R2: Odoo 19 Product Category Hierarchy

**Decision**: Create category tree via XML data file. Keyword mapping via JSON file loaded by a service.
**Rationale**: XML for categories provides stable xmlids for referencing. JSON for keywords allows easy editing without XML escaping issues. Service layer keeps logic testable.
**Alternatives considered**: Dedicated etsy.category.keyword model (rejected: over-engineering per constitution VII), hardcoded Python dict (rejected: hard to maintain)

### R3: Multi-Currency Price Parsing

**Decision**: Extend the existing `_parse_eur_price()` to detect currency symbol/prefix and return `(amount, currency_code)` tuple. Set `currency_id` on the sale order based on detected currency.
**Rationale**: Minimal change to existing parser. Odoo handles multi-currency natively once currency_id is set correctly.
**Alternatives considered**: Convert all to EUR at import time (rejected: loses original price information), separate parsers per currency (rejected: unnecessary duplication)

### R4: Savepoint-Based Batch Processing

**Decision**: Replace `self.env.cr.commit()` with `self.env.cr.savepoint()` context manager per batch of 100 orders. On batch failure, rollback that batch only and log the failing order IDs.
**Rationale**: Preserves Odoo's transaction model. Partial failures are recoverable. No orphaned records.
**Alternatives considered**: Single transaction for all (rejected: 17K records in one transaction risks OOM), keep cr.commit with better error handling (rejected: still breaks Odoo patterns)

### R5: Order Confirmation + Delivery Completion for Historical Data

**Decision**: Migration wizard calls `order.action_confirm()` then `picking.button_validate()` (with immediate transfer wizard auto-processing) for each order. Process in batches of 100 with savepoints.
**Rationale**: Standard Odoo workflow. action_confirm creates stock.picking. button_validate completes the delivery. This gives proper stock moves and a clean audit trail.
**Alternatives considered**: Direct SQL state update (rejected: bypasses ORM constraints and stock moves), background job via queue_job (rejected: not in CE, adds dependency)

### R6: Header-Based Column Mapping

**Decision**: Read first row of Excel, build `{normalized_header: column_index}` dictionary. Normalize by stripping whitespace, uppercasing. Required headers: TRANSACTION_ID, ORDER_ID, PRODUCT_NAME. Optional headers: all others (default to empty/zero if missing).
**Rationale**: Robust against column reordering. Clear error if required columns missing.
**Alternatives considered**: Regex fuzzy matching on headers (rejected: over-engineering), user-configurable mapping UI (rejected: one-time import, not worth the UI)

### R7: Shop-Level Record Rules

**Decision**: Add `etsy_shop_ids` Many2many field on `res.users`. Create `ir.rule` on `sale.order` with domain `[('etsy_shop_id', 'in', user.etsy_shop_ids.ids)]` for the Etsy User group. Managers see all. Apply same pattern to `etsy.email.log`.
**Rationale**: Standard Odoo record rule pattern. M2M on users allows assigning multiple shops. Products and partners remain shared (per clarification).
**Alternatives considered**: Separate group per shop (rejected: doesn't scale to 19+ shops), company-based isolation (rejected: overkill, only one company)

---

## Phase 1: Design

### Data Files to Create

#### 1. `data/etsy_shipping_product.xml`
- `product.product` record: name="Etsy Shipping", type="service", sale_ok=True, purchase_ok=False
- xmlid: `etsy_integration.product_etsy_shipping`

#### 2. `data/etsy_fiscal_data.xml`
- `account.tax`: name="Etsy Tax Collected (0%)", amount=0, type_tax_use="sale"
- `account.fiscal.position`: name="Etsy Marketplace"
- `account.fiscal.position.tax`: maps all sale taxes to the 0% Etsy tax
- `account.payment.term`: name="Etsy Prepaid", line_ids with days=0 (immediate)
- `crm.team`: name="Etsy", use_quotations=True
- `product.pricelist`: name="Etsy EUR", currency_id=EUR
- `product.pricelist`: name="Etsy USD", currency_id=USD

#### 3. `data/etsy_product_categories.xml`
Category hierarchy:
```
Etsy Products (parent)
├── Ring Dishes
├── Temporary Tattoos
├── Mugs & Drinkware
├── Jewelry
├── Home Decor
├── Personalized Gifts
├── Stickers
├── Clothing & Accessories
├── Pet Products
└── Uncategorized
```

#### 4. `data/product_category_keywords.json`
```json
{
  "ring_dishes": ["ring dish", "jewelry dish", "trinket dish", "ring holder"],
  "temporary_tattoos": ["tattoo", "temporary tattoo", "fake tattoo"],
  "mugs_drinkware": ["mug", "cup", "tumbler", "drinkware", "coffee"],
  "jewelry": ["necklace", "bracelet", "earring", "ring", "pendant"],
  "home_decor": ["pillow", "candle", "wall art", "frame", "ornament"],
  "personalized_gifts": ["personalized", "custom", "engraved", "monogram"],
  "stickers": ["sticker", "decal", "label"],
  "clothing": ["shirt", "hoodie", "hat", "scarf", "clothing"],
  "pet_products": ["pet", "dog", "cat", "collar", "leash"]
}
```
Categories matched in order; first match wins. "personalized_gifts" is intentionally broad as a catch-all before "uncategorized".

### Service Changes

#### `services/order_creator.py` Changes:
1. **`_parse_price(text)`** -- new method replacing `_parse_eur()`:
   - Detects `$`, `EUR`, `GBP`, `\u20ac`, `\u00a3` symbols
   - Returns `(float_amount, currency_code)` tuple
   - Falls back to EUR if no symbol detected
   - Logs warning for truly unparseable values

2. **`_get_shipping_product()`** -- returns the Etsy Shipping service product (cached via xmlid lookup)

3. **`_get_fiscal_position()`** -- returns Etsy Marketplace fiscal position (cached)

4. **`_get_payment_term()`** -- returns Etsy Prepaid payment term (cached)

5. **`_get_sales_team()`** -- returns Etsy sales team (cached)

6. **`_get_pricelist(currency_code)`** -- returns EUR or USD pricelist

7. **`process_parse_result()`** -- updated to:
   - Set fiscal_position_id, payment_term_id, team_id, pricelist_id on order
   - Add shipping cost as order line (Etsy Shipping product)
   - Set currency_id based on detected price currency
   - Set is_storable=True on new products

8. **`find_or_create_product()`** -- updated to:
   - Set `is_storable=True`
   - Call `product_categorizer.categorize(product_name)` for category assignment

9. **`find_or_create_partner()`** -- improved dedup:
   - Primary: email (if available)
   - Secondary: name + address1 + city + zip (normalized)
   - Tertiary: name + zip (current fallback)
   - State resolution: check `code` field first, then `name` with ilike

#### `services/product_categorizer.py` (NEW):
- Loads `data/product_category_keywords.json` at init
- `categorize(product_name) -> product.category`: matches product name against keywords
- Returns xmlid-referenced category or "Uncategorized" default
- Case-insensitive matching, checks all keywords per category

### Wizard Changes

#### `wizards/import_orders_wizard.py` Changes:
1. **Header-based mapping**: Read row 1, build header dict, replace all `_COL_*` constants
2. **Multi-currency `_parse_price()`**: Detect currency, return `(amount, currency_code)`
3. **Savepoint batching**: Replace `cr.commit()` with `cr.savepoint()` per 100-order batch
4. **Auto-confirm option**: Add `auto_confirm` Boolean field (default True for historical)
5. **Shipping line**: Add Etsy Shipping product line for each order with shipping cost
6. **Financial config**: Set fiscal position, payment term, sales team, pricelist, currency
7. **Validation report**: Add `warning_count` and `validation_notes` fields to wizard result

#### `wizards/data_migration_wizard.py` (NEW):
TransientModel `etsy.data.migration.wizard` with:
- `excel_file` (Binary, optional) -- for USD price re-parsing
- `auto_confirm` (Boolean, default=True)
- `fix_shipping_lines` (Boolean, default=True)
- `fix_financial_config` (Boolean, default=True)
- `fix_product_config` (Boolean, default=True)
- `generate_dedup_report` (Boolean, default=True)
- `status_message` (Text, readonly) -- results summary

**`action_migrate()`** pipeline:
1. Find all Etsy orders: `sale.order.search([('is_etsy_order','=',True)])`
2. If fix_financial_config: Set fiscal_position_id, payment_term_id, team_id on all orders
3. If fix_shipping_lines: For orders with etsy_shipping_cost > 0 and no shipping line, add one
4. If fix_product_config: Set is_storable=True, run categorizer on all Etsy products
5. If excel_file provided: Re-parse USD prices from Excel, match by etsy_transaction_id
6. If auto_confirm: Confirm draft orders, then validate all stock.picking to "done"
7. If generate_dedup_report: Find partners with same normalized name+zip, write report
8. Display summary counts

### Model Changes

#### `models/sale_order.py`:
- Add `etsy_has_discount` Boolean computed field: `@api.depends('etsy_discount_code')`

#### `models/sale_order_line.py`:
- Add `etsy_design_status` Selection field: `[('pending','Pending'),('in_progress','In Progress'),('completed','Completed')]`, default='pending'

#### `models/res_users.py` (NEW):
- Extend `res.users` with `etsy_shop_ids` Many2many to `etsy.shop`

### View Changes

#### `views/data_migration_wizard_views.xml` (NEW):
- Form view with checkboxes for each fix type, file upload for Excel, action button, status display

#### `views/etsy_discount_views.xml` (NEW):
- Pivot view: rows=etsy_discount_code, measures=order count + amount_total
- Graph view: bar chart of discount code usage
- Search view: filter "Has Discount"
- Action: menu item under Etsy menu

#### `views/etsy_design_queue_views.xml`:
- Add `etsy_design_status` column and filter

#### `data/ir_cron_data.xml`:
- Add second cron record for `image_downloader.cron_download_pending_images()`, interval=30min

### Security Changes

#### `security/etsy_security.xml`:
- Add `ir.rule` on `sale.order`: domain `['|',('etsy_shop_id','=',False),('etsy_shop_id','in',user.etsy_shop_ids.ids)]` for group `base.group_user`
- Add `ir.rule` on `etsy.email.log` with similar shop-based filtering
- Manager group bypasses (global=True for managers)

#### `security/ir.model.access.csv`:
- Add `etsy.data.migration.wizard` ACL for sales_team.group_sale_manager

---

## Verification Plan

1. **Module update**: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init`
2. **Data files loaded**: Verify fiscal position, tax, payment term, sales team, pricelists, product categories exist
3. **Run migration wizard**: Execute from Odoo UI, verify all counts in summary
4. **Financial reconciliation**: `SELECT SUM(amount_total) FROM sale_order WHERE is_etsy_order = true` matches expected
5. **Order states**: `SELECT state, COUNT(*) FROM sale_order WHERE is_etsy_order = true GROUP BY state` shows all "sale" or "done"
6. **Product config**: `SELECT COUNT(*) FROM product_template WHERE is_etsy_product = true AND is_storable = true` matches total Etsy products
7. **Run tests**: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init`
8. **Ruff check**: `ruff check custom_addons/etsy_integration/`

## Complexity Tracking

No constitution violations. All changes use standard Odoo patterns.
