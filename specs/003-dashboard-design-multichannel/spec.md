# Feature Specification: Operational Dashboard, Design File Workflow, and Multi-Channel Foundation

**Feature Branch**: `003-dashboard-design-multichannel`
**Created**: 2026-04-06
**Status**: Draft
**Input**: Replace Google Sheets-based order management with an Odoo operational dashboard, add design file upload and production team approval workflow, and lay the multi-channel foundation for future Amazon/WooCommerce integration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operational Order Dashboard (Priority: P1)

As an operations team member, I need a single working list view of all orders with both auto-populated order data and manually editable fulfillment fields, so I can manage daily order processing without switching to Google Sheets.

**Why this priority**: The team currently manages all order fulfillment in Google Sheets (21 columns). This is the primary pain point -- without this dashboard, Odoo does not replace the existing workflow. The current Odoo dashboard shows only analytics (graph/pivot), not an actionable order management view.

**Independent Test**: Open the operational dashboard, verify all 21 columns are visible. Inline-edit the shipping date, tracking number, carrier, label status, fulfillment status, and note fields on an existing Etsy order. Verify changes persist after page reload.

**Acceptance Scenarios**:

1. **Given** an existing Etsy sale order, **When** a team member opens the operational dashboard, **Then** all 21 fields are visible in a single list row: shipping date, tracking number, carrier, label status, fulfillment status, note, order image, date, buyer note, gift message, personalisation, quantity, shipping service, PIC, shop, order ID, country, sale price, shipping cost, promotion, total price
2. **Given** the operational dashboard, **When** a team member edits columns A-F (shipping date, tracking number, carrier, label status, fulfillment status, note) inline, **Then** the changes are saved immediately without opening a form view
3. **Given** the operational dashboard, **When** a team member assigns a PIC (Person In Charge) to an order, **Then** the assigned user appears in the PIC column and can filter the dashboard to see only their assigned orders
4. **Given** the operational dashboard, **When** filtering by fulfillment status "Cho file" (Waiting for file), **Then** only orders with that status appear
5. **Given** orders from multiple shops, **When** a team member groups by shop, **Then** orders are grouped with subtotals for order count and total price per shop

---

### User Story 2 - Design File Upload and Preview (Priority: P1)

As a production team member, I need to upload design files and preview images to specific order lines, so the design team can see what needs to be produced for each item.

**Why this priority**: The print-on-demand workflow requires design files attached to orders before production can start. Without file upload, the team must manage design files outside Odoo (Google Drive, email), breaking the single-system workflow.

**Independent Test**: Open a sale order form, navigate to the design files tab. Upload a design file (PNG/PDF) to an order line. Upload a preview image. Verify both files appear in the order detail and can be downloaded.

**Acceptance Scenarios**:

1. **Given** a sale order with order lines, **When** a team member uploads a design file to an order line, **Then** the file is stored as an attachment linked to that specific order line
2. **Given** an order line with a design file, **When** a team member uploads a preview/thumbnail image, **Then** the preview is displayed inline in the order line list within the sale order form
3. **Given** an order line, **When** multiple design files are uploaded (e.g., front and back designs), **Then** all files are listed under that order line with their filenames and upload dates
4. **Given** the design queue list view, **When** a team member views orders with design files, **Then** a visual indicator shows which lines have files attached and which are still missing files
5. **Given** a design file attachment, **When** a team member clicks on it, **Then** they can download the original file or preview it in the browser (for images)

---

### User Story 3 - Design Approval Workflow (Priority: P1)

As a production team lead, I need to review design files and mark them as approved, pending, or needing adjustment, so the team knows which orders are ready for production.

**Why this priority**: The approval workflow gates the production pipeline. Without it, there is no way to track which designs have been reviewed and approved, leading to production errors and rework.

**Independent Test**: Open the design queue, find an order line with a design file. Change the approval status to "Approved". Verify the status persists. Set another to "Needs Adjustment" with a rejection note. Filter by "Pending Review" status and verify only unreviewed items appear.

**Acceptance Scenarios**:

1. **Given** a design file on an order line, **When** a production team member reviews it, **Then** they can set the approval status to one of: "Cho duyet" (Pending Review), "Duyet" (Approved), or "Can chinh lai" (Needs Adjustment)
2. **Given** a design file set to "Can chinh lai" (Needs Adjustment), **When** the team member sets this status, **Then** they must provide a rejection note explaining what needs to change
3. **Given** a design file set to "Duyet" (Approved), **When** the status is saved, **Then** the system records which user approved it and when
4. **Given** the design queue, **When** filtering by "Cho duyet" (Pending Review), **Then** only order lines with unreviewed or pending design files appear
5. **Given** the design queue, **When** viewed as a kanban board, **Then** three columns appear: "Cho duyet", "Duyet", and "Can chinh lai", with order line cards that can be dragged between columns
6. **Given** a non-production team member (e.g., sales user), **When** they view a design file, **Then** they can see the approval status but cannot change it

---

### User Story 4 - Multi-Channel Foundation (Priority: P2)

As a business owner, I need each order to be tagged with its sales channel (Etsy, Amazon, Website) so I can filter, report, and manage orders by channel, even though only Etsy is active now.

**Why this priority**: Adding the channel field now prevents a costly retrofit when Amazon and Website channels are added later. All dashboard views, reports, and fulfillment workflows must be channel-aware from the start.

**Independent Test**: View an existing Etsy order and verify it shows "Etsy" in the sales channel field. Create a test order manually and set the channel to "Amazon". Filter the dashboard by channel and verify only the correct orders appear.

**Acceptance Scenarios**:

1. **Given** any existing Etsy order, **When** viewing the order form or dashboard, **Then** the "Sales Channel" field displays "Etsy"
2. **Given** a new order being created, **When** the user selects a sales channel, **Then** the options are: Etsy, Amazon, Website, Other
3. **Given** the operational dashboard, **When** filtering by "Sales Channel = Etsy", **Then** only Etsy orders appear
4. **Given** the operational dashboard, **When** grouping by sales channel, **Then** orders are grouped with subtotals per channel
5. **Given** all 17,659+ existing Etsy orders, **When** the channel backfill migration runs, **Then** all orders have sales_channel set to "etsy" and channel_order_ref set to the value of etsy_order_id

---

### User Story 5 - Order Priority and Sorting (Priority: P2)

As an operations manager, I need to assign priority levels to orders and sort the dashboard by priority, so the team processes urgent orders first.

**Why this priority**: Without priority management, the team processes orders in arbitrary order. Urgent or time-sensitive orders (e.g., rush shipping, VIP customers) may be delayed.

**Independent Test**: Set one order to "Urgent" priority and another to "Normal". Sort the dashboard by priority and verify urgent orders appear first.

**Acceptance Scenarios**:

1. **Given** a sale order, **When** an operations manager sets the priority, **Then** the options are: "Binh thuong" (Normal), "Cao" (High), "Khan cap" (Urgent)
2. **Given** the operational dashboard, **When** sorting by priority, **Then** urgent orders appear first, then high, then normal
3. **Given** the operational dashboard, **When** filtering by priority "Khan cap" (Urgent), **Then** only urgent orders are shown
4. **Given** a new order imported from Etsy, **When** it enters the system, **Then** it defaults to "Binh thuong" (Normal) priority

---

### User Story 6 - Fulfillment Status Tracking (Priority: P2)

As an operations team member, I need to track each order through fulfillment stages on the dashboard, so I can see at a glance which orders need attention at each stage.

**Why this priority**: The Google Sheet workflow tracks status with column E. Without equivalent status tracking in Odoo, the team loses visibility into where each order is in the fulfillment pipeline.

**Independent Test**: Set an order's fulfillment status to "Cho file" (Waiting for file), then change it through each stage. Verify dashboard filters work for each status.

**Acceptance Scenarios**:

1. **Given** a sale order, **When** a team member sets the fulfillment status, **Then** the options include at minimum: "Moi" (New), "Cho file" (Waiting for design file), "Dang san xuat" (In Production), "Da san xuat" (Produced), "Da dong goi" (Packed), "Da gui" (Shipped), "Huy" (Cancelled)
2. **Given** the operational dashboard, **When** filtering by fulfillment status, **Then** only orders matching the selected status appear
3. **Given** the operational dashboard, **When** viewing the dashboard with color coding, **Then** different fulfillment statuses are visually distinguishable (e.g., status badge colors)
4. **Given** an order with fulfillment status "Da gui" (Shipped), **When** viewing the order, **Then** the shipping date and tracking number are populated

---

### User Story 7 - Label Status Management (Priority: P3)

As a shipping team member, I need to track label status for each order so I know which orders need shipping labels generated, which have labels ready, and which do not need labels.

**Why this priority**: Label management is part of the Google Sheet workflow (Column D). Important for shipping efficiency but not blocking core operations.

**Independent Test**: Set an order's label status to "Can get label" (Need to get label). Verify it appears in the "need label" filter. Change to "Da get" (Label ready). Verify it moves to the correct filter.

**Acceptance Scenarios**:

1. **Given** a sale order, **When** a team member sets the label status, **Then** the options are: "Khong can" (Not needed), "Can get label" (Need to get label), "Da get" (Label ready)
2. **Given** the operational dashboard, **When** filtering by label status "Can get label", **Then** only orders needing labels appear
3. **Given** a new order entering the system, **When** no label action has been taken, **Then** the default label status is empty/unset

---

### Edge Cases

- What happens when a design file upload exceeds the Odoo attachment size limit? The system should reject the upload with a clear error message indicating the maximum file size.
- What happens when a team member tries to approve a design file that has already been approved? The system should allow re-approval (updating the approver and date) without error.
- What happens when an order line has multiple design files with different approval statuses? The overall order line design status should reflect the least-approved file (e.g., if one is "Pending" and one is "Approved", the line status shows "Pending").
- What happens when the sales_channel backfill migration runs on orders that already have a channel set? The migration should be idempotent -- skip orders that already have a sales_channel value.
- What happens when a user deletes a design file that has been approved? The system should allow deletion but log it in the chatter for audit trail.
- What happens when the dashboard has 17,000+ orders? The view should use server-side pagination and not attempt to load all records at once. Default page size of 80 records.
- What happens when a design file upload exceeds 10MB? The system should validate file size before storage and reject uploads exceeding the configured maximum with a clear error message.
- What happens when a design file is rejected (can_chinh_lai) and a new version is uploaded? The new file is a separate record; the rejected file remains for audit trail. No parent-child link between versions (simplicity over completeness).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an operational list view with 21 columns matching the Google Sheet layout, with columns A-F editable inline
- **FR-002**: System MUST allow uploading design files (Binary) to individual sale order lines
- **FR-003**: System MUST allow uploading preview/thumbnail images for design files
- **FR-004**: System MUST support a 3-state design approval workflow: "Cho duyet" (Pending Review), "Duyet" (Approved), "Can chinh lai" (Needs Adjustment)
- **FR-005**: System MUST require a rejection note when setting approval status to "Can chinh lai"
- **FR-006**: System MUST record the approving user and timestamp when a design file is approved
- **FR-007**: System MUST restrict design approval actions to members of the production team security group
- **FR-008**: System MUST provide a kanban view for the design queue with 3 columns by approval status
- **FR-009**: System MUST add a "sales_channel" field to sale orders with values: etsy, amazon, website, other
- **FR-010**: System MUST add a "channel_order_ref" field to store the external order reference generically
- **FR-011**: System MUST backfill existing Etsy orders with sales_channel="etsy" and channel_order_ref from etsy_order_id
- **FR-012**: System MUST support PIC (Person In Charge) assignment per sale order
- **FR-013**: System MUST support order priority levels: Normal, High, Urgent
- **FR-014**: System MUST support fulfillment status tracking with at minimum 7 stages
- **FR-015**: System MUST support label status tracking with 3 states
- **FR-016**: System MUST provide dashboard filters for: sales channel, shop, PIC, priority, fulfillment status, label status, date range
- **FR-017**: System MUST compute an overall design status per order line from its attached design files
- **FR-018**: System MUST allow grouping the dashboard by shop, channel, PIC, priority, or fulfillment status
- **FR-019**: System MUST handle 17,000+ orders with server-side pagination in the dashboard view

### Key Entities

- **Design File**: A file (image, PDF, or design format) attached to a sale order line, with approval status tracking. Has a parent order line, optional preview image, approval status, approver, and rejection note.
- **Sales Channel**: A classification of the sales source (Etsy, Amazon, Website, Other) stored on each sale order for filtering and reporting.
- **Fulfillment Status**: The current stage of order fulfillment, from "New" through "Shipped", tracked per sale order.
- **PIC Assignment**: The team member responsible for managing a specific order through its fulfillment lifecycle.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operations team no longer uses Google Sheets for daily order management -- 100% of order processing happens in the Odoo dashboard
- **SC-002**: All 21 columns from the Google Sheet are accessible in the Odoo operational dashboard
- **SC-003**: Design files can be uploaded, previewed, and approved within the Odoo interface without external tools
- **SC-004**: Production team approval/rejection cycle for design files completes in under 30 seconds per file
- **SC-005**: Dashboard loads and is interactive within 3 seconds for a dataset of 17,000+ orders
- **SC-006**: 100% of existing Etsy orders display the correct sales channel after backfill migration
- **SC-007**: Dashboard filters reduce the visible order set to the operator's working scope (by PIC, status, shop) in one click
- **SC-008**: Design queue shows real-time status of pending, approved, and needs-adjustment items with zero manual status tracking

## Assumptions

- The existing etsy_integration module (Spec 001) is installed and functional with 17,659+ orders in the database
- Spec 002 (config fixes) will be completed before or concurrently with this spec, providing correct financial data, product categories, and order confirmation
- The Odoo instance has the `sale_management`, `stock`, `contacts`, and `mail` modules installed
- Design files are typically PNG, JPG, PDF, or AI format, under 10MB per file
- The production team is a small group (5-15 people) who need a dedicated security group
- Amazon and WooCommerce channel adapters will be separate future specs that extend the sales_channel selection field
- The operational dashboard replaces (not supplements) the Google Sheets workflow
- The team works primarily in Vietnamese; field labels should use Vietnamese with English technical names
- Fulfillment routing (push to partner vs internal production) is Spec 004 scope; this spec only adds the fulfillment status field for tracking
- Spec 004 data model (fulfillment routing, partner config, production stages) should be reviewed before implementing Spec 003's design approval workflow to ensure the handoff point is coherent

## Out of Scope

The following items were identified during the three-angle investigation (BA, Technical Architecture, Devil's Advocate) and are explicitly excluded from Spec 003:

- **CRM / 2-way Etsy messaging** -- Owner wants this (visible in system architecture diagram under "Dashboard > CRM"). Addressed in Spec 004 US6 (contingent on Etsy API approval).
- **Fulfillment routing / push logic** -- Deciding whether orders go to external partners or internal production. Fully covered in Spec 004 (US1-US4).
- **Partner API integration** -- Auto-syncing design files and tracking to/from external partners. Covered in Spec 004 (US3).
- **Internal production tracking** -- Manufacturing stages and production queue. Covered in Spec 004 (US4).
- **Raw material inventory** -- Stock level visibility for production. Covered in Spec 004 (US5).
- **Returns/refunds workflow** -- Reverse flow for shipped orders. Covered in Spec 004 (US7).
- **Inventory sync across channels** -- Overselling prevention when multiple channels share inventory. Future spec (005+).
- **Amazon/WooCommerce connectors** -- Actual channel adapters beyond the sales_channel field. Future spec (005+).
- **Google Sheet tabs MP, BA, PD, Policy/Audit** -- The operational dashboard replaces the "Dashboard v1" tab and partially covers "Dashboard PD". The remaining 4 tabs (Marketing, Business Analysis, Policy/Audit, Other Proposals) are future scope.
- **Design file version control** -- Tracking v1/v2/v3 of design files with parent-child relationships. Considered but deferred to keep the design file model simple.

## Investigation Reference

A comprehensive three-angle analysis (BA/Odoo Consultant, Technical Architect, Devil's Advocate) was conducted on 2026-04-07. See `specs/003-dashboard-design-multichannel/investigation.md` for the full report covering:
- 16-item gap analysis between owner's vision and spec coverage
- 6 CRITICAL risks and 9 HIGH risks identified
- Architecture assessment (8.5/10 separation of concerns, 7/10 multi-channel readiness)
- Google Sheet tab mapping (6 tabs, 1.5 covered by this spec)
- Recommended phasing: Spec 003 -> 004 -> 005+
