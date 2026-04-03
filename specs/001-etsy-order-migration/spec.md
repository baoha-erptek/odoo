# Feature Specification: Etsy Order Migration to Odoo 19 CE

**Feature Branch**: `001-etsy-order-migration`
**Created**: 2026-04-02
**Status**: Draft
**Input**: Migration of standalone Python email parser + Google Sheets system to Odoo 19 CE custom module

## Background

An existing Python application (`esty_email_collection`) monitors a Gmail inbox for Etsy marketplace order notification emails. It parses 34 fields per order using regex patterns and writes results to three Google Sheets (Orders, Designs, Customers). The system runs every 10 minutes and has accumulated 17,659 orders across multiple Etsy shops (Viktor, Julien, Carina, etc.).

The goal is to replace Google Sheets with Odoo 19 CE, gaining proper CRM, sale order workflow, product catalog, reporting, and multi-user access.

## User Scenarios & Testing

### User Story 1 - Automated Etsy Email Ingestion (Priority: P1)

As a shop operator, I want Etsy order notification emails to be automatically parsed and stored as Odoo sale orders, so I no longer need Google Sheets to track orders.

**Why this priority**: This is the core value proposition. Without automated email-to-order ingestion, the migration has zero value.

**Independent Test**: Send a test Etsy order email to the monitored inbox, wait for the next cron cycle, and verify a sale.order with correct line items appears in Odoo.

**Acceptance Scenarios**:

1. **Given** a new Etsy order email arrives in the labeled Gmail inbox, **When** the scheduled cron job runs, **Then** a new sale.order is created in Odoo with the correct order ID, shop, customer, shipping address, and line items (product, quantity, price, options).
2. **Given** an Etsy email has already been processed, **When** the cron job encounters the same email again, **Then** no duplicate order is created (deduplication by Etsy Transaction ID).
3. **Given** an Etsy email with multiple transaction IDs (multi-item order), **When** the cron processes it, **Then** a single sale.order is created with multiple sale.order.line records, one per transaction.
4. **Given** the Gmail API is temporarily unavailable, **When** the cron job runs, **Then** the error is logged and the job retries on the next cycle without data loss.

---

### User Story 2 - Historical Data Import (Priority: P1)

As a shop operator, I want all 17,659 existing orders imported from the Excel file into Odoo, so I have complete historical data in one system.

**Why this priority**: Equal to P1 because the system is useless without historical context. Operators need to search past orders.

**Independent Test**: Run the import script, then verify total order count matches, and spot-check 10 random orders for field accuracy.

**Acceptance Scenarios**:

1. **Given** the Excel file with 17,659 rows, **When** the import script runs, **Then** all rows are imported as sale.order records with correct field mapping.
2. **Given** duplicate TRANSACTION_IDs in the Excel data, **When** import runs, **Then** duplicates are skipped and logged.
3. **Given** orders with country names (not ISO codes), **When** import runs, **Then** country names are correctly mapped to res.country records.
4. **Given** orders from different shops, **When** import runs, **Then** each order is linked to the correct Etsy shop record.

---

### User Story 3 - Multi-Shop Management (Priority: P2)

As a business owner managing multiple Etsy shops, I want each shop to be a distinct entity in Odoo with its own orders, so I can track performance per shop.

**Why this priority**: The business operates multiple shops. Shop-level filtering and reporting is essential for daily operations.

**Independent Test**: View the shop list, click a shop, see only that shop's orders.

**Acceptance Scenarios**:

1. **Given** orders from shops Viktor, Julien, and Carina, **When** I filter by shop "Viktor", **Then** only Viktor's orders appear.
2. **Given** a new shop name appears in an Etsy email, **When** the parser encounters it, **Then** a new etsy.shop record is auto-created.

---

### User Story 4 - Customer Management (Priority: P2)

As a shop operator, I want Etsy buyers automatically created as Odoo contacts with their shipping details, so I can look up customer history.

**Why this priority**: Customer data enables CRM, repeat buyer identification, and address management.

**Independent Test**: Search for a customer name in the Contacts module, see their linked orders.

**Acceptance Scenarios**:

1. **Given** a new order from buyer "Andrea Flint" with shipping address, **When** the order is processed, **Then** a res.partner record is created with name, address, country, email, and phone.
2. **Given** another order from the same buyer (matched by email or name+address), **When** processed, **Then** the existing partner is reused (no duplicate).
3. **Given** a customer with orders from multiple shops, **When** I view the customer record, **Then** all their orders across all shops are visible.

---

### User Story 5 - Product Catalog (Priority: P2)

As a shop operator, I want products automatically created from order line items, so I can see which products sell best.

**Why this priority**: Product catalog enables inventory thinking and sales analytics.

**Independent Test**: View the product list, see distinct products with their images.

**Acceptance Scenarios**:

1. **Given** an order with product "Never Forget The Difference You Have Made Retirement Ring Dish", **When** processed, **Then** a product.product record is created with that name and the Etsy image URL.
2. **Given** the same product appears in another order, **When** processed, **Then** the existing product is reused.
3. **Given** a product with options (Size: Square, Color: Gold), **When** processed, **Then** the variant details are stored as fields on the sale order line (etsy_size, etsy_color, etsy_option), not as Odoo product attributes.

---

### User Story 6 - Order Dashboard & Reporting (Priority: P3)

As a business owner, I want a dashboard showing order volume, revenue, and trends per shop, so I can make business decisions.

**Why this priority**: This is the analytical payoff of moving from Sheets to Odoo.

**Independent Test**: Open the Etsy Orders dashboard, see charts for daily order volume and revenue by shop.

**Acceptance Scenarios**:

1. **Given** historical orders imported, **When** I open the dashboard, **Then** I see total orders, total revenue, and orders-per-day graph.
2. **Given** multiple shops, **When** I filter by shop, **Then** charts update to show that shop's data only.
3. **Given** a date range filter, **When** applied, **Then** all metrics reflect only that period.

---

### User Story 7 - Parse Failure Monitoring (Priority: P3)

As a system administrator, I want to be notified when email parsing fails, so I can investigate format changes quickly.

**Why this priority**: Etsy can change email templates without notice, breaking regex parsing. Early detection is critical.

**Independent Test**: Send a malformed test email, verify an alert appears in Odoo.

**Acceptance Scenarios**:

1. **Given** an email that fails to parse (no transaction IDs found), **When** the cron runs, **Then** the raw email is saved to an `etsy.email.log` record with status "failed" and the error message.
2. **Given** parse failures exceed a threshold (e.g., 5 in a row), **When** this is detected, **Then** an Odoo activity or notification is created for the admin user.

---

### User Story 8 - Shipping Information Tracking (Priority: P3)

As a shop operator, I want shipping details (service type, processing time, address) visible on each order, so I can manage fulfillment.

**Why this priority**: Operational need but not blocking initial migration.

**Independent Test**: Open an order, see the shipping tab with carrier, processing time, and full delivery address.

**Acceptance Scenarios**:

1. **Given** an order with shipping service "Standard" and processing time "9-10 business days", **When** I view the order, **Then** these fields are visible on the order form.
2. **Given** an order with a discount code, **When** I view the order, **Then** the discount and subtotal are correctly reflected.

---

### User Story 9 - Design Tracking for Personalized Orders (Priority: P3)

As a design team member, I want personalized order details (personalization text, gift messages, design links) in a dedicated view, so I can fulfill custom orders efficiently.

**Why this priority**: The current system maintains a separate "Designs" sheet. This workflow needs to survive the migration.

**Independent Test**: Open the design queue view, see orders that have personalization or gift messages.

**Acceptance Scenarios**:

1. **Given** an order with personalization "June 2025", **When** I open the design queue, **Then** this order appears with personalization text, product name, and image.
2. **Given** an order with a gift message, **When** viewed, **Then** the gift message is displayed prominently.

---

### User Story 10 - Gmail OAuth2 Configuration (Priority: P1)

As an administrator, I want to configure Gmail API credentials within Odoo's settings, so the email fetching service can authenticate without manual token management.

**Why this priority**: Without working Gmail auth, no emails can be fetched. This is foundational.

**Independent Test**: Enter credentials in Odoo settings, click "Test Connection", see success message.

**Acceptance Scenarios**:

1. **Given** valid Gmail OAuth2 credentials, **When** I configure them in Odoo settings, **Then** the connection test succeeds and emails can be fetched.
2. **Given** an expired OAuth2 token, **When** the cron job runs, **Then** the token is automatically refreshed using the refresh token.

---

### Edge Cases

- What happens when an Etsy email has zero transaction IDs? (Store as unparseable, flag for review)
- What happens when the shipping country is not in the country mapping? (Store raw country name, flag)
- What happens when an email has images from a CDN that's down? (Store URL, skip image download)
- What happens when the Gmail label is removed mid-processing? (Process all fetched messages, log warning)
- What happens when EUR prices need conversion? (Store as-is in EUR, use Odoo's multi-currency if needed)

## Requirements

### Functional Requirements

- **FR-001**: System MUST fetch Etsy order emails from Gmail via OAuth2 API on a configurable schedule (default: every 10 minutes)
- **FR-002**: System MUST parse Etsy order notification emails extracting all 34 fields using regex patterns
- **FR-003**: System MUST create sale.order records with line items (sale.order.line) for each parsed order
- **FR-004**: System MUST auto-create res.partner records for new customers with shipping address
- **FR-005**: System MUST auto-create product.product records for new products with image URLs
- **FR-006**: System MUST deduplicate orders by Etsy Transaction ID (etsy_transaction_id)
- **FR-007**: System MUST support multiple Etsy shops as separate entities
- **FR-008**: System MUST import existing 17,659 orders from Excel file
- **FR-009**: System MUST store raw email content for failed parses for manual review
- **FR-010**: System MUST remove Gmail label from successfully processed emails
- **FR-011**: System MUST map country names to ISO Alpha-2 codes using Odoo's res.country
- **FR-012**: System MUST handle multi-language field labels (English, German personalisation variants)
- **FR-013**: System MUST provide a tree/form view for Etsy orders with all extracted fields
- **FR-014**: System MUST provide a filtered view for orders requiring design work (personalization/gift messages)

### Key Entities

- **Etsy Shop** (`etsy.shop`): Represents an Etsy storefront. Key attributes: name, owner, active status.
- **Etsy Email Log** (`etsy.email.log`): Raw email storage for audit trail and failed parse recovery. Key: gmail_message_id, raw_body, parse_status, error_message.
- **Sale Order** (extends `sale.order`): Standard Odoo sale order extended with etsy_order_id, etsy_shop_id, etsy_note_from_buyer, etsy_gift_message, etsy_shipping_service, etsy_processing_time.
- **Sale Order Line** (extends `sale.order.line`): Extended with etsy_transaction_id, etsy_personalisation, etsy_sku, etsy_design_link_front, etsy_design_link_back.
- **Product** (extends `product.product`): Extended with etsy_image_url for the Etsy CDN image.
- **Partner** (extends `res.partner`): No custom fields needed beyond standard address fields.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of incoming Etsy order emails are either successfully parsed into sale.orders or logged as parse failures within 15 minutes of arrival
- **SC-002**: Zero duplicate orders in the database (unique constraint on etsy_transaction_id)
- **SC-003**: Historical import covers all 17,659 rows with less than 1% data loss (mismatched/unparseable rows documented)
- **SC-004**: System handles at least 50 orders per cron cycle without timeout
- **SC-005**: Admin can identify and investigate parse failures within 5 clicks from the dashboard
- **SC-006**: Shop operators can find any historical order by order ID, customer name, or date within 10 seconds

## Assumptions

- Gmail API access will remain available (Google does not deprecate the API)
- Etsy email notification format remains sufficiently stable (regex patterns may need periodic updates)
- All order prices are in EUR (single currency)
- The existing shops (Viktor, Julien, Carina) are the complete set, with potential for new shops
- Odoo 19 CE provides sufficient sale order functionality without Enterprise features
- The Docker infrastructure from odoo19_namco project can be adapted
- Users have basic familiarity with Odoo's web interface
- No real-time integration with Etsy API is required for Phase 1 (email-only)
