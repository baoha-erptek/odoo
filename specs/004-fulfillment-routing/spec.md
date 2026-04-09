# Feature Specification: Fulfillment Routing, Production Assignment, and Partner Integration

**Feature Branch**: `004-fulfillment-routing`
**Created**: 2026-04-07
**Status**: Draft
**Input**: After design files are approved (Spec 003), route orders to external fulfillment partners (via API) or internal production. Add CRM messaging foundation and returns workflow.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fulfillment Route Assignment (Priority: P1)

As an operations manager, I need to assign each approved order to either an external fulfillment partner or internal production, so the team knows where each order is being manufactured and can track it accordingly.

**Why this priority**: This is the core "push logic" from the system architecture. Without routing, approved designs sit in limbo with no clear next step. This bridges the gap between Spec 003's design approval and actual production/fulfillment.

**Independent Test**: Open an order with approved design files. Assign it to "Partner A" or "Internal Production". Verify the routing decision is recorded, the fulfillment status advances to "In Production", and the order appears in the correct production queue.

**Acceptance Scenarios**:

1. **Given** an order with all design files approved (approval_status = 'duyet'), **When** an operations manager assigns a fulfillment route, **Then** the options include: internal production and each configured external partner
2. **Given** an order assigned to an external partner, **When** the route is saved, **Then** the fulfillment_status automatically transitions to "Dang san xuat" (In Production) and the partner name is visible on the dashboard
3. **Given** an order assigned to internal production, **When** the route is saved, **Then** the fulfillment_status automatically transitions to "Dang san xuat" and the order appears in the internal production queue
4. **Given** an order already routed to Partner A, **When** operations reroutes it to internal production, **Then** the previous routing is logged in the audit trail and the new route is active
5. **Given** the operational dashboard (Spec 003), **When** filtering by fulfillment route, **Then** only orders assigned to the selected route appear (e.g., "Show me all orders routed to Partner A")
6. **Given** an order with unapproved design files, **When** a user attempts to assign a fulfillment route, **Then** the system prevents routing and displays a message: "All design files must be approved before routing"

---

### User Story 2 - External Partner Configuration (Priority: P1)

As an administrator, I need to configure external fulfillment partners with their contact details, supported file formats, and API credentials, so the system can auto-sync design files and order data to them.

**Why this priority**: Partners must be configured before orders can be routed to them. This is a prerequisite for the routing workflow.

**Independent Test**: Create a new fulfillment partner record with name, contact info, supported file formats (PNG, PDF), and API endpoint URL. Verify the partner appears in the routing dropdown when assigning orders.

**Acceptance Scenarios**:

1. **Given** the Settings or Configuration menu, **When** an administrator creates a new fulfillment partner, **Then** the required fields are: name, contact person, email, supported file formats, and API sync method (manual/API)
2. **Given** a configured partner with API sync method, **When** the administrator enters API endpoint URL and credentials, **Then** a "Test Connection" button verifies the API is reachable
3. **Given** a partner with supported file formats = [PNG, PDF], **When** an order with an AI-format design file is routed to this partner, **Then** the system warns: "Design file format (.ai) is not supported by this partner"
4. **Given** the partner list, **When** an administrator deactivates a partner, **Then** that partner no longer appears in the routing dropdown for new orders, but existing routed orders retain the historical assignment

---

### User Story 3 - Partner API Sync (Design Files + Status) (Priority: P2)

As a fulfillment coordinator, I need the system to automatically push approved design files and order details to the assigned external partner via API, and receive tracking numbers and production status updates back, so I do not have to manually transfer files or check partner portals.

**Why this priority**: Manual file transfer and status checking is the current bottleneck. Automation reduces errors and saves hours of daily work. However, manual routing (US1) works without this -- operators can email files to partners as a fallback.

**Independent Test**: Route an order to a partner with API sync enabled. Trigger the sync. Verify design files are pushed to the partner API. Simulate a partner callback with tracking number. Verify tracking number appears on the order in the Odoo dashboard.

**Acceptance Scenarios**:

1. **Given** an order routed to a partner with API sync enabled, **When** the sync runs (manually triggered or via cron), **Then** approved design files and order details (product, quantity, shipping address) are sent to the partner's API endpoint
2. **Given** a successful API push, **When** the partner's API returns a confirmation, **Then** the sync status on the order is marked "Synced" with a timestamp
3. **Given** a failed API push (timeout, 500 error), **When** the sync fails, **Then** the system logs the error, marks sync status as "Failed", and retries up to 3 times with exponential backoff
4. **Given** a partner that sends a callback/webhook with tracking info, **When** the callback is received, **Then** the tracking number and carrier are written to the sale order and fulfillment_status advances to "Da gui" (Shipped)
5. **Given** a partner without API sync (manual mode), **When** the order is routed, **Then** the system generates a downloadable package (ZIP) of design files for manual transfer
6. **Given** a partner API that is unreliable (down for >24 hours), **When** all retries fail, **Then** the system escalates by creating an activity notification for the PIC user and keeps the sync status as "Failed - Needs Manual Action"

---

### User Story 4 - Internal Production Queue and Status Tracking (Priority: P2)

As a production team lead, I need to see all orders assigned to internal production in a dedicated queue, track each order through production stages, and flag orders that are blocked by material shortages, so I can manage the production floor efficiently.

**Why this priority**: Internal production needs its own workflow separate from partner-fulfilled orders. The production team needs a focused view without partner orders cluttering it.

**Independent Test**: Route 3 orders to internal production. Open the internal production queue. Move one order from "Queued" to "In Progress" to "QC Check" to "Completed". Verify status changes are reflected on the main dashboard.

**Acceptance Scenarios**:

1. **Given** orders routed to internal production, **When** a production team lead views the internal production queue, **Then** only internally-routed orders appear, sorted by priority then date
2. **Given** an order in the internal production queue, **When** the team lead updates the production stage, **Then** the options are: "Xep hang" (Queued), "Dang lam" (In Progress), "Kiem tra CL" (QC Check), "Hoan thanh" (Completed)
3. **Given** an order with production stage "Hoan thanh" (Completed), **When** the stage is saved, **Then** the sale order fulfillment_status automatically updates to "Da san xuat" (Produced)
4. **Given** the production queue, **When** a team lead marks an order as "Blocked - Missing Material", **Then** a flag icon appears and the reason is visible in the list
5. **Given** the production queue as a kanban board, **When** viewing by production stage, **Then** cards can be dragged between columns to update stage

---

### User Story 5 - Raw Material Stock Awareness (Priority: P3)

As a production team lead, I need to see current stock levels of key raw materials (blank products, ink, packaging) alongside the production queue, so I can flag orders that cannot proceed due to material shortages before they block the production line.

**Why this priority**: Material shortages cause production delays. Awareness prevents accepting orders that cannot be fulfilled. However, this extends into inventory management which may be better handled by Odoo's native stock module -- this story focuses on visibility, not full inventory management.

**Independent Test**: View the production dashboard. See current stock quantities for 3 configured raw materials. When stock for "T-shirt blanks Size M" drops below the reorder threshold, verify a visual warning appears.

**Acceptance Scenarios**:

1. **Given** the internal production queue, **When** a team lead views the production dashboard, **Then** a sidebar or panel shows current stock levels for configured raw materials
2. **Given** a raw material with stock below its reorder threshold, **When** viewing the production dashboard, **Then** a visual warning (color/icon) highlights the low-stock material
3. **Given** a raw material at zero stock, **When** an order requiring that material is in the production queue, **Then** the order is flagged with "Material shortage" and the specific material is named
4. **Given** the stock visibility panel, **When** a team lead clicks a material, **Then** they navigate to the Odoo stock quant view for that product (native Odoo)

---

### User Story 6 - CRM / Etsy Message Sync (Priority: P3)

As a customer service representative, I need to see Etsy buyer messages alongside their orders in Odoo, and reply to messages from within Odoo, so I do not need to switch between Etsy Seller Portal and Odoo for customer communication.

**Why this priority**: The owner explicitly wants 2-way Etsy CRM sync (visible in the system architecture diagram under "Dashboard > CRM"). However, Etsy's messaging API access is restricted and may require OAuth approval. This is high complexity with uncertain API availability, so it is P3 for now.

**Independent Test**: View an Etsy order in Odoo. See the buyer's original message and any follow-up messages in the chatter. Compose a reply in Odoo and verify it appears in the Etsy conversation.

**Acceptance Scenarios**:

1. **Given** an Etsy order with buyer messages, **When** viewing the order in Odoo, **Then** all Etsy messages appear in the order's chatter thread, tagged with "Etsy Message"
2. **Given** the Etsy messages in chatter, **When** a CSR composes a reply and clicks "Send to Etsy", **Then** the message is posted to the Etsy conversation via API
3. **Given** a new incoming Etsy message on an existing order, **When** the sync cron runs, **Then** the new message appears in the order chatter within the next sync cycle
4. **Given** the operational dashboard, **When** filtering by "Has unread messages", **Then** only orders with unread Etsy messages appear

---

### User Story 7 - Returns and Refunds Workflow (Priority: P3)

As an operations manager, I need to process customer returns and refunds within Odoo, tracking the reason, replacement or refund decision, and return shipping, so returns do not require a separate spreadsheet or manual Etsy portal work.

**Why this priority**: Returns are currently handled ad-hoc outside Odoo. As order volume grows (especially with Amazon/Website channels), a structured returns process becomes essential. P3 because the current volume is manageable manually.

**Independent Test**: Open a shipped order. Initiate a return with reason "Defective product". Choose "Refund" action. Verify the return is logged, the order status reflects the return, and a refund record is created.

**Acceptance Scenarios**:

1. **Given** a shipped order (fulfillment_status = 'da_gui'), **When** an operations manager initiates a return, **Then** they select a return reason from: "Loi san pham" (Defective), "Sai san pham" (Wrong item), "Khach doi y" (Customer changed mind), "Khac" (Other)
2. **Given** a return initiated, **When** the manager selects the action, **Then** the options are: "Hoan tien" (Refund), "Gui lai" (Replacement), "Giam gia" (Partial refund/discount)
3. **Given** a refund action, **When** confirmed, **Then** a credit note is created in Odoo linked to the original sale order
4. **Given** a replacement action, **When** confirmed, **Then** a new sale order is created linked to the original order as a replacement, inheriting shipping address and product details
5. **Given** the dashboard, **When** filtering by "Returned orders", **Then** all orders with an active return appear

---

### Edge Cases

- What happens when an order is routed to a partner but the partner is deactivated before fulfillment completes? The routing remains valid for that order; only new routing is prevented.
- What happens when a partner API sync pushes files but the partner never confirms receipt? After 72 hours with no confirmation, the system creates an escalation activity for the PIC.
- What happens when the same order is routed to both internal and partner? The system enforces a single active route per order; rerouting replaces the previous route.
- What happens when a return is initiated on an order still in production? The system allows the return request but warns: "Order is still in production. Cancel production first?"
- What happens when stock reaches zero mid-production? Orders in "In Progress" stage continue (materials already consumed), but "Queued" orders are flagged as blocked.
- What happens when a partner sends a callback for an order that was rerouted away from them? The system logs the callback but does not update the order (stale route check).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow assigning a fulfillment route (internal or specific partner) to sale orders with all design files approved
- **FR-002**: System MUST prevent routing orders whose design files are not fully approved
- **FR-003**: System MUST automatically transition fulfillment_status to "Dang san xuat" when a route is assigned
- **FR-004**: System MUST allow configuring external fulfillment partners with name, contact info, supported file formats, and API sync method
- **FR-005**: System MUST provide a "Test Connection" function for partner API endpoints
- **FR-006**: System MUST push approved design files and order details to partner APIs (when API sync is enabled)
- **FR-007**: System MUST handle API sync failures with retry logic (up to 3 retries with exponential backoff)
- **FR-008**: System MUST receive partner callbacks/webhooks with tracking numbers and status updates
- **FR-009**: System MUST generate a downloadable file package for partners without API sync (manual mode)
- **FR-010**: System MUST provide an internal production queue view showing only internally-routed orders
- **FR-011**: System MUST support 4 internal production stages: Queued, In Progress, QC Check, Completed
- **FR-012**: System MUST automatically update fulfillment_status to "Da san xuat" when production stage reaches "Completed"
- **FR-013**: System MUST allow flagging production orders as blocked with a reason
- **FR-014**: System MUST display current raw material stock levels alongside the production queue
- **FR-015**: System MUST highlight materials below reorder threshold with visual warnings
- **FR-016**: System MUST allow initiating returns on shipped orders with reason and action selection
- **FR-017**: System MUST create credit notes for refund actions and new orders for replacement actions
- **FR-018**: System MUST log all routing changes, sync attempts, and return actions in the audit trail (chatter)
- **FR-019**: System MUST enforce a single active fulfillment route per order (rerouting replaces previous)
- **FR-020**: System MUST sync Etsy buyer messages to the sale order chatter and allow replies back to Etsy

### Key Entities

- **Fulfillment Partner**: An external production/fulfillment provider with contact info, supported file formats, API endpoint, and credentials. Can be active or inactive.
- **Fulfillment Route**: The assignment of a sale order to either internal production or a specific partner. Records who routed it and when. Only one active route per order.
- **Partner Sync Log**: A record of each API sync attempt (push or callback), including status (pending/success/failed), timestamps, error messages, and retry count.
- **Production Stage**: The current manufacturing status for internally-routed orders, from Queued through Completed.
- **Return Request**: A customer return or refund request on a shipped order, with reason, action (refund/replace/discount), and resolution status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All approved orders are routed to a fulfillment destination within 1 business day of design approval
- **SC-002**: Partner API sync delivers design files to partners within 5 minutes of manual or automated trigger
- **SC-003**: Partner tracking numbers appear in Odoo within 1 sync cycle of partner callback (no manual data entry)
- **SC-004**: Internal production queue shows real-time production stage for all internally-routed orders
- **SC-005**: Returns/refunds are logged in Odoo with linked credit notes or replacement orders -- no separate spreadsheet needed
- **SC-006**: Operations team can filter the dashboard by fulfillment route, production stage, sync status, and return status in one click
- **SC-007**: Material shortage warnings appear before production begins, preventing blocked production starts
- **SC-008**: 100% of routing changes and sync attempts are logged in the audit trail for accountability

## Assumptions

- Spec 003 (dashboard + design file workflow) is completed and deployed before this spec
- Design files stored via Spec 003's order.design.file model are accessible for API sync
- External partners have either a REST API endpoint or accept manual file transfers (no FTP/EDI/SOAP required for MVP)
- Partner API authentication uses API keys or OAuth2 (not complex certificate-based auth)
- Etsy's Messaging API may have restricted access; US6 (CRM sync) is contingent on API availability
- The Odoo stock module is installed and basic product stock tracking is configured
- Raw material stock visibility (US5) uses Odoo's native stock.quant model, not a custom inventory system
- Returns volume is manageable (<5% of orders) and does not require a dedicated returns team
- Partner callbacks use standard HTTP webhooks (POST to an Odoo controller endpoint)
- The system handles at most 5-10 external partners in the near term
- Fulfillment routing to partners is a manual decision by operations managers, not automated rules (automated routing is a future enhancement)

## Out of Scope

- **Automated routing rules** (e.g., auto-route based on product type or capacity) -- routing is manual in this spec
- **Full MRP/manufacturing module integration** -- US4 uses a simple stage field, not mrp.production records
- **Partner billing/invoicing** -- financial settlement with partners is handled outside this system
- **Multi-warehouse stock management** -- uses single stock location for raw materials
- **Amazon/WooCommerce channel-specific return workflows** -- only generic returns covered; channel-specific logic is future specs
- **Etsy API approval process** -- obtaining Etsy API access for messaging is a business process, not a technical spec
