# Feature Specification: Etsy Integration Configuration Fixes and Improvements

**Feature Branch**: `002-etsy-config-fixes`
**Created**: 2026-04-04
**Status**: Draft
**Input**: Fix all product configuration mismatches, sale order incomplete setup, and Odoo configuration gaps identified in BA_ANALYSIS_REPORT.md and deep Excel data analysis.

## Clarifications

### Session 2026-04-04

- Q: Should historical orders be confirmed to "sale" (creating open deliveries) or also auto-completed to "done"? → A: Confirm to "sale" then auto-complete deliveries to "done" -- historical orders are already shipped, so no open delivery orders should remain.
- Q: Should the migration wizard auto-merge existing duplicate partners or only improve matching for future imports? → A: Future-only -- improve dedup algorithm for new imports and generate a suspected-duplicates report for manual admin review. No automatic merging of existing partners.
- Q: Where should product category keyword mappings be stored? → A: JSON data file (data/product_category_keywords.json) loaded at runtime -- easy to edit, version-controlled, no extra DB model.
- Q: Should shop-level record rules apply to all models or just orders? → A: Apply to sale.order and etsy.email.log only. Products and partners are shared resources across shops.
- Q: Should USD orders be converted to EUR or kept in original currency? → A: Keep in original currency (set currency_id to USD on the order). Use Odoo's native multi-currency for consolidated reporting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct Financial Data on Orders (Priority: P1)

As a business owner, I need all 17,659 imported Etsy orders to show correct prices, shipping costs in totals, and proper currency handling so that Odoo revenue reports match the original Google Sheets data.

**Why this priority**: Without correct financial data, the Odoo deployment provides less value than the Sheets it replaced. 423 USD orders currently show $0.00 prices, shipping costs are excluded from order totals, and no tax/fiscal configuration exists. This blocks all reporting, invoicing, and accounting.

**Independent Test**: Import a sample of 10 orders (5 EUR, 5 USD) and verify that price_unit, shipping line item, and amount_total all match the Excel source data. Verify the dashboard revenue matches expected totals.

**Acceptance Scenarios**:

1. **Given** an Excel row with PRICE="$16.99" (USD), **When** the import wizard processes it, **Then** the sale order line has price_unit=16.99 and the order currency is USD
2. **Given** an Excel row with PRICE="EUR 19.70", **When** the import wizard processes it, **Then** the sale order line has price_unit=19.70 and the order currency is EUR
3. **Given** an order with SHIPPING_COST="EUR 4.49", **When** the order is created, **Then** a separate "Etsy Shipping" service line appears with price_unit=4.49 and is included in amount_total
4. **Given** any imported order, **When** viewed in the order form, **Then** the fiscal position is "Etsy Marketplace" and a 0% tax line appears for reporting
5. **Given** any imported order, **When** viewed in the order form, **Then** payment term is "Etsy Prepaid" (immediate) and sales team is "Etsy"

---

### User Story 2 - Order Confirmation and Delivery Workflow (Priority: P1)

As a fulfillment team member, I need imported orders to be confirmable (or auto-confirmed for historical data) so that delivery orders are created and I can track fulfillment status through the standard Odoo workflow.

**Why this priority**: All 17,659 orders sit in "draft" state. No delivery orders exist. No invoices can be generated. The fulfillment team cannot use Odoo for order processing.

**Independent Test**: Confirm a batch of draft Etsy orders and verify stock.picking records are created for each. Verify the dashboard shows confirmed order revenue.

**Acceptance Scenarios**:

1. **Given** 17,659 draft Etsy orders in the database, **When** the data migration wizard runs with "auto-confirm" enabled, **Then** all orders move to "sale" state, delivery orders (stock.picking) are created and immediately completed to "done" state (since historical orders are already shipped)
2. **Given** a new order imported via the Excel wizard, **When** the "auto-confirm" checkbox is checked, **Then** the order is automatically confirmed after creation
3. **Given** a new order imported via the email cron, **When** auto-confirm is disabled in settings, **Then** the order remains in draft for manual operator review
4. **Given** a confirmed order, **When** viewed in the sale order list, **Then** the order appears in Sales Analysis reports with correct revenue figures

---

### User Story 3 - Product Configuration and Categorization (Priority: P2)

As a shop owner, I need products to be properly configured as storable items with meaningful categories so that I can track inventory levels and filter products by type (Ring Dishes, Temporary Tattoos, Mugs, etc.).

**Why this priority**: 2,294 products are created as non-storable consumables with no category. No inventory tracking is possible. Products cannot be organized, filtered, or reported by type.

**Independent Test**: After running the migration wizard, verify that all Etsy products have is_storable=True and are assigned to a category. Filter products by "Ring Dishes" category and verify correct products appear.

**Acceptance Scenarios**:

1. **Given** a new product imported from Etsy, **When** it is auto-created, **Then** it has is_storable=True and type='consu' (enabling stock tracking)
2. **Given** a product named "Personalized Ring Dish Engagement Gift", **When** auto-categorization runs, **Then** the product is assigned to "Etsy Products / Ring Dishes"
3. **Given** 2,294 existing products with no category, **When** the data migration wizard runs, **Then** each product is assigned to the most appropriate category based on name keywords
4. **Given** a product name that does not match any keyword, **When** auto-categorization runs, **Then** it is assigned to "Etsy Products / Uncategorized"

---

### User Story 4 - Improved Customer Deduplication (Priority: P2)

As a customer service representative, I need repeat Etsy buyers to be correctly linked to their existing customer record so I can see their full order history in one place, even when email and phone data are missing.

**Why this priority**: The Excel data has 0% email and 0% phone populated. The current email-first dedup strategy fails completely for historical imports, creating excessive duplicate partner records.

**Independent Test**: Import 100 orders from the same buyer (same name, different order dates, varying addresses) and verify they link to one partner record. Verify the partner's order count matches.

**Acceptance Scenarios**:

1. **Given** two orders with SHIPPING_NAME="John Smith", SHIPPING_ADDRESS1="123 Main St", SHIPPING_CITY="Portland", SHIPPING_ZIPCODE="97201", **When** both are imported, **Then** they link to the same res.partner
2. **Given** an order with SHIPPING_STATE="CA", **When** the state is resolved, **Then** it matches California (by code), not Georgia (by ilike name match)
3. **Given** an order with SHIPPING_COUNTRY="Czechia", **When** country is resolved, **Then** it maps to the Czech Republic res.country record
4. **Given** a buyer who orders to both home and office addresses, **When** both orders are imported, **Then** the system either correctly deduplicates by name+city or creates separate partners (no false merge)

---

### User Story 5 - Import Wizard Robustness (Priority: P2)

As a system administrator, I need the Excel import wizard to reliably handle column reordering, mixed currencies, and partial failures without corrupting data or losing progress.

**Why this priority**: The current wizard uses hardcoded column positions (breaks if columns reorder), unsafe cr.commit() calls (partial data on crash), and no progress reporting for 17K row imports.

**Independent Test**: Reorder two columns in the Excel file and re-import. Verify all data maps correctly. Kill the import mid-run and verify no partial orders with missing lines exist.

**Acceptance Scenarios**:

1. **Given** an Excel file with columns in different order than expected, **When** import runs, **Then** columns are matched by header name, not position
2. **Given** an import of 17,659 rows that fails at row 5,000, **When** the failure occurs, **Then** the first 4,900 rows are committed in complete batches and the error is logged with the failing order ID
3. **Given** a completed import, **When** the wizard displays results, **Then** it shows: imported count, skipped (duplicate) count, failed count, and any zero-price warnings

---

### User Story 6 - Data Migration Wizard (Priority: P1)

As a system administrator, I need a one-click wizard to fix all existing imported data (confirm orders, add shipping lines, set fiscal position, fix USD prices, categorize products, set is_storable) so the database transitions from raw import to production-ready state.

**Why this priority**: All other user stories create fixes for future imports, but the 17,659 existing records also need remediation. Without a migration wizard, each fix requires manual SQL or per-record editing.

**Independent Test**: Run the migration wizard on the full database. Verify order count, total revenue, product categories, and partner dedup before and after.

**Acceptance Scenarios**:

1. **Given** 17,659 draft orders without shipping lines, **When** migration wizard runs, **Then** shipping line items are added to all orders with non-zero etsy_shipping_cost
2. **Given** 423 orders with price_unit=0.0 (USD parsing failure), **When** migration wizard runs with the source Excel file attached, **Then** prices are re-parsed from the Excel and corrected
3. **Given** all orders without fiscal position or payment term, **When** migration wizard runs, **Then** all Etsy orders get "Etsy Marketplace" fiscal position and "Etsy Prepaid" payment term
4. **Given** 2,294 products without categories, **When** migration wizard runs, **Then** all products are categorized and set to is_storable=True
5. **Given** the migration wizard completes, **When** viewing the summary, **Then** it shows counts: orders confirmed, deliveries completed, shipping lines added, prices fixed, products categorized, suspected duplicate partners (report only, no auto-merge)

---

### User Story 7 - Discount Code Analytics (Priority: P3)

As a business owner, I need to see which Etsy discount codes are most used and their revenue impact so I can evaluate promotion effectiveness across shops.

**Why this priority**: 52.9% of orders have discount codes but they are stored as plain text with no analytics. This is useful but not blocking.

**Independent Test**: Open the discount analytics view and verify it shows discount codes grouped by usage count and total order value.

**Acceptance Scenarios**:

1. **Given** orders with discount codes, **When** viewing the discount analytics pivot view, **Then** each code shows usage count and total order value
2. **Given** a search for discount code "VIKRUN10", **When** results load, **Then** it shows 959 orders associated with this code
3. **Given** the Etsy orders list, **When** filtering by "Has Discount", **Then** only orders with a non-empty discount code appear

---

### User Story 8 - Image Download Automation (Priority: P3)

As a design team member, I need product images to be automatically downloaded and stored on product records so I can see product visuals without clicking external Etsy URLs.

**Why this priority**: The image download service exists but no scheduled job triggers it. Products have etsy_image_url but empty image_1920 fields.

**Independent Test**: After registering the cron, wait for one cycle and verify images are downloaded for products that had URLs but no images.

**Acceptance Scenarios**:

1. **Given** products with etsy_image_url set but no image_1920, **When** the image download cron runs, **Then** images are downloaded in batches of 50 and stored on the product
2. **Given** the cron running, **When** an image download fails for one product, **Then** the failure is logged and the cron continues with the next product

---

### User Story 9 - Shop-Level Data Isolation (Priority: P3)

As a shop owner, I should only see orders, revenue, and data for my own Etsy shop(s), not for other owners' shops, to maintain data privacy and focus.

**Why this priority**: BA analysis identified this as BR-SHOP-04. Currently all users see all shops. Important for multi-tenant security but not blocking initial usage.

**Independent Test**: Create two users, each assigned to a different shop. Verify each user only sees their own shop's orders.

**Acceptance Scenarios**:

1. **Given** user "Viktor" assigned to shop "Viktor", **When** Viktor views the order list, **Then** only orders with etsy_shop_id="Viktor" are visible
2. **Given** user "Admin" with manager role, **When** Admin views the order list, **Then** all shops' orders are visible
3. **Given** the dashboard, **When** Viktor views it, **Then** revenue and order count reflect only Viktor's shop

---

### User Story 10 - Design Queue Status Tracking (Priority: P4)

As a design team member, I need to mark personalized orders as "Pending", "In Progress", or "Completed" in the design queue so the team knows which orders still need design work.

**Why this priority**: The design queue view exists but has no status field. Nice-to-have for workflow management.

**Independent Test**: Open design queue, change an item's status to "In Progress", verify the status persists and is filterable.

**Acceptance Scenarios**:

1. **Given** a sale order line with personalisation text in the design queue, **When** a team member sets status to "In Progress", **Then** the status is saved and visible in the list
2. **Given** the design queue, **When** filtering by "Pending" status, **Then** only items not yet started appear

---

### Edge Cases

- What happens when an Excel PRICE cell contains text like "EUR 18.89From Alanna and's wedding registry" (corrupted value)? System should parse the numeric portion (18.89) and log a warning.
- What happens when QUANTITY contains "Pack of 2" instead of a number? System should extract the numeric value (2) or default to 1 with a warning.
- What happens when SHIPPING_COUNTRY is empty? System should skip country resolution and log a warning, not fail the entire order.
- What happens when a product name exceeds 256 characters (Odoo field limit)? System should truncate to 255 characters.
- What happens when the migration wizard is run twice? It should be idempotent -- already-confirmed orders are skipped, already-categorized products are skipped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse prices in EUR, USD, and GBP currencies, detecting the currency from the prefix/suffix symbol
- **FR-002**: System MUST create a separate "Etsy Shipping" service line item on each order for shipping costs, included in amount_total
- **FR-003**: System MUST assign "Etsy Marketplace" fiscal position and 0% "Etsy Tax Collected" tax to all Etsy orders
- **FR-004**: System MUST assign "Etsy Prepaid" payment term and "Etsy" sales team to all Etsy orders
- **FR-005**: System MUST create pricelists for EUR and USD, set the appropriate one based on detected order currency, and keep orders in their original currency (no conversion to EUR)
- **FR-006**: System MUST support auto-confirmation of orders during import (configurable, default off for email cron, on for wizard)
- **FR-007**: System MUST create products with is_storable=True to enable inventory tracking
- **FR-008**: System MUST auto-categorize products into an Etsy-specific category hierarchy based on product name keywords loaded from a JSON configuration file
- **FR-009**: System MUST improve customer deduplication by matching on name+address+city when email is unavailable
- **FR-010**: System MUST resolve US state codes (e.g., "CA") by checking the state code field before falling back to name matching
- **FR-011**: System MUST use header-based column mapping in the import wizard instead of positional indices
- **FR-012**: System MUST use savepoint-based batch processing instead of raw cr.commit() in the import wizard
- **FR-013**: System MUST provide a data migration wizard to batch-fix all existing imported records
- **FR-014**: System MUST register a scheduled job for image downloads, processing up to 50 products per cycle
- **FR-015**: System MUST add shop-level record rules on sale.order and etsy.email.log restricting visibility to assigned shop owners (products and partners remain shared)
- **FR-016**: System MUST add a design status field (pending/in_progress/completed) to sale order lines in the design queue
- **FR-017**: System MUST provide discount code analytics via pivot and graph views

### Key Entities

- **Etsy Shipping Product**: Service-type product used as the line item for shipping costs on all Etsy orders
- **Etsy Marketplace Fiscal Position**: Fiscal position mapping Etsy tax handling (0% collected by marketplace)
- **Etsy Prepaid Payment Term**: Immediate payment term reflecting Etsy's prepaid model
- **Etsy Sales Team**: Sales team grouping all Etsy-originated orders
- **Etsy Product Category Hierarchy**: Parent "Etsy Products" with children: Ring Dishes, Temporary Tattoos, Mugs, Jewelry, Home Decor, Personalized Gifts, Stickers, Clothing, Uncategorized
- **Data Migration Wizard**: One-time transient model that applies all configuration fixes to existing records

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of imported order totals (amount_total) match the source Excel SUBTOTAL + SHIPPING_COST values within 0.01 tolerance
- **SC-002**: 0 orders with price_unit=0.00 where the source Excel PRICE was non-zero (currently 423 affected)
- **SC-003**: 100% of Etsy orders have a fiscal position, payment term, and sales team assigned
- **SC-004**: 100% of Etsy products have is_storable=True and a non-default product category
- **SC-005**: The Odoo Sales Analysis dashboard shows total revenue matching the source data
- **SC-006**: All historical orders are confirmable and generate delivery orders (stock.picking)
- **SC-007**: The import wizard correctly processes an Excel file with reordered columns without data corruption
- **SC-008**: Customer duplicate rate is reduced (fewer unique partners than unique SHIPPING_NAME+ZIPCODE combinations)
- **SC-009**: The data migration wizard is idempotent -- running it twice produces the same result as running it once

## Assumptions

- The existing etsy_integration module (spec 001) is installed and functional as the baseline
- The source Excel file "Esty main 2 - 15h VN 06 08 2025.xlsx" is the authoritative data source for historical orders
- Etsy collects and remits marketplace tax; orders in Odoo use a 0% tax for reporting only
- All Etsy orders are prepaid; no receivables or credit management is needed
- Product variants (Color/Size as product.attribute) are deferred to a future spec; variant data continues to be stored as text fields on order lines
- The Odoo instance uses EUR as its base currency; USD is enabled as an additional active currency
- Docker containers will be started before running verification tests
- The 19 Etsy shops in the data (Julien, Viktor, Jessica, Birgit, Sven, Carina, etc.) are all active
