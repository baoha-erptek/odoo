# Feature Specification: Fulfillment Routing, Production Assignment, and Partner Integration

**Feature Branch**: `004-fulfillment-routing`
**Created**: 2026-04-07
**Status**: Draft
**Input**: After design files are approved (Spec 003), route orders to external fulfillment partners (via API) or internal production. Primary partner is Gearment (API v3). Import tracking numbers from logistics partner Excel files (GKE Logistics). Auto-detect shipping carriers (USPS, UniUni, YunExpress). Add CRM messaging foundation and returns workflow.

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

As an administrator, I need to configure external fulfillment partners with their contact details, supported file formats, API credentials, and priority level (primary/secondary), so the system can auto-sync design files and order data to the correct partner.

**Why this priority**: Partners must be configured before orders can be routed to them. This is a prerequisite for the routing workflow. The primary partner (Gearment) requires specific configuration for its API authentication and rate limits.

**Independent Test**: Create a new fulfillment partner record with name, contact info, supported file formats (PNG, PDF), priority = "Primary", auth method = "Header Keys", and API endpoint URL. Verify the partner appears first in the routing dropdown when assigning orders. Test the connection using the partner's specific auth method.

**Acceptance Scenarios**:

1. **Given** the Settings or Configuration menu, **When** an administrator creates a new fulfillment partner, **Then** the required fields are: name, contact person, email, supported file formats, API sync method (manual/API), and partner priority (primary/secondary)
2. **Given** a configured partner with API sync method, **When** the administrator selects auth method "Header Keys" and enters client key + client secret, **Then** a "Test Connection" button verifies the API is reachable using the partner's specific authentication headers
3. **Given** a partner with supported file formats = [PNG, PDF], **When** an order with an AI-format design file is routed to this partner, **Then** the system warns: "Design file format (.ai) is not supported by this partner"
4. **Given** the partner list, **When** an administrator deactivates a partner, **Then** that partner no longer appears in the routing dropdown for new orders, but existing routed orders retain the historical assignment
5. **Given** a partner with API sync and webhook support, **When** the administrator enables webhooks and clicks "Register Webhooks", **Then** the system registers webhook subscriptions at the partner's webhook endpoint for order completion, cancellation, and tracking update events
6. **Given** a partner configured as "Primary", **When** an operations manager opens the routing dropdown for an order, **Then** the primary partner appears first/default in the list
7. **Given** a partner with API rate limits configured (e.g., 100 requests per 10 seconds), **When** viewing the partner record, **Then** the rate limit configuration is visible and enforced during sync operations

---

### User Story 3 - Partner API Sync (Design Files + Status) (Priority: P2)

As a fulfillment coordinator, I need the system to automatically push approved design files and order details to the assigned external partner via API, and receive tracking numbers and production status updates back, so I do not have to manually transfer files or check partner portals.

**Why this priority**: Manual file transfer and status checking is the current bottleneck. Automation reduces errors and saves hours of daily work. However, manual routing (US1) works without this -- operators can email files to partners as a fallback. The primary partner (Gearment) has a multi-step order flow requiring draft creation, price quoting, and manual approval before confirmation.

**Independent Test**: Route an order to a partner with API sync enabled. Trigger the sync. Verify design files are pushed to the partner API as URL references. Verify the system retrieves a price quote and displays it for operator approval. Simulate a partner webhook with tracking number. Verify tracking number appears on the order in the Odoo dashboard.

**Acceptance Scenarios**:

1. **Given** an order routed to a partner with API sync enabled, **When** the sync runs (manually triggered or via cron), **Then** approved design files (as publicly accessible URLs), product details, quantity, and shipping address are sent to the partner's API endpoint
2. **Given** a successful API push, **When** the partner's API returns a confirmation, **Then** the sync status on the order is marked "Synced" with a timestamp and the partner's reference ID is stored
3. **Given** a failed API push (timeout, 500 error), **When** the sync fails, **Then** the system logs the error, marks sync status as "Failed", and retries up to 3 times with exponential backoff
4. **Given** a partner that sends a webhook with tracking info, **When** the webhook is received, **Then** the tracking number and carrier are written to the sale order and fulfillment_status advances to "Da gui" (Shipped)
5. **Given** a partner without API sync (manual mode), **When** the order is routed, **Then** the system generates a downloadable package (ZIP) of design files for manual transfer
6. **Given** a partner API that is unreliable (down for >24 hours), **When** all retries fail, **Then** the system escalates by creating an activity notification for the PIC user and keeps the sync status as "Failed - Needs Manual Action"
7. **Given** a partner with a multi-step order flow (e.g., Gearment: draft -> price quote -> confirm), **When** the sync runs, **Then** the system creates a draft order at the partner, retrieves the price quote, and presents the quoted price to the operator for manual approval before confirming
8. **Given** a partner API with rate limits (e.g., 100 requests per 10 seconds), **When** pushing multiple orders in bulk, **Then** the system respects the configured rate limit and queues excess requests rather than exceeding the limit

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

### User Story 8 - Shipping Carrier Tracking Import (Priority: P2)

As an operations manager, I need to import tracking numbers and shipping details from a standardized Excel file provided by the logistics partner (GKE Logistics), so that tracking numbers are automatically matched to existing orders and the carrier is identified without manual data entry.

**Why this priority**: Tracking numbers currently require manual entry per order. With hundreds of orders per week, importing from the logistics partner's Excel file and auto-matching to orders saves significant time and eliminates transcription errors. This is independent of partner API sync (US3) -- tracking can come from either source.

**Independent Test**: Upload a GKE Logistics Excel file with 10 rows. Verify the system matches ORDER NUMBERs to existing sale orders, writes tracking numbers, auto-detects carriers (USPS vs UniUni vs YunExpress), and shows a summary of 8 matched / 2 unmatched.

**Acceptance Scenarios**:

1. **Given** a standardized Excel file with columns matching the GKE format (ORDER NUMBER, TRACKING NUMBER, COUNTRY, CONSIGNEE NAME, STATE, CITY, ADDRESS, POSTCODE, PRODUCT NAME, VALUE, QUANTITY, WEIGHT, COST, CREATIVE date, warehouse date, order status, label URL, QR code URL), **When** the operator uploads the file via the import wizard, **Then** the system parses each row and matches ORDER NUMBER to `sale.order.etsy_order_id`
2. **Given** a matched order, **When** the tracking number is written, **Then** the system auto-detects the shipping carrier from the tracking pattern (USPS: 20-22 digit numeric; UniUni: starts with "UU"; YunExpress: starts with "YT") and writes both tracking number and shipping carrier to the sale order
3. **Given** an ORDER NUMBER with suffix "-replace" (e.g., "4005375073-replace"), **When** importing, **Then** the system strips the suffix for matching, flags the order as a replacement, and links it to the original order
4. **Given** import completion, **When** the operator reviews results, **Then** a summary shows: N orders matched, N tracking numbers written, N orders not found, and carrier detection counts by carrier type
5. **Given** an Excel row where the ORDER NUMBER does not match any existing sale order, **When** importing, **Then** the row is logged as unmatched with the ORDER NUMBER for manual review
6. **Given** the import file contains label URLs (column: link label) and QR code URLs (column: link QR code), **When** importing, **Then** these URLs are stored on the sale order for shipping label access
7. **Given** an Excel file with 20 columns (including an explicit SHIPPING CARRIER column), **When** importing, **Then** the explicit carrier value overrides the auto-detected carrier. If the carrier column is missing (19-column format), auto-detection is used as fallback

---

### User Story 9 - Logistics Partner Google Drive Sync (Priority: P3)

As an operations manager, I need the system to automatically read tracking Excel files from per-logistics-partner Google Drive folders, so that tracking import happens without manual file download and upload.

**Why this priority**: Currently operators must download Excel files from Google Drive and re-upload them into the system. Automating this removes a manual step. However, manual upload (US8) provides the same functionality -- this story adds convenience automation. P3 because manual import is a viable workflow for current volume.

**Independent Test**: Configure a Google Drive folder for "GKE Logistics". Place a new Excel file in the folder. Wait for the sync cron to run. Verify the file is downloaded, processed using the same logic as manual import (US8), and marked as processed.

**Acceptance Scenarios**:

1. **Given** a configured logistics partner with a Google Drive folder ID and sync enabled, **When** the sync cron runs, **Then** the system authenticates with Google Drive, lists files in the folder, and identifies unprocessed files (new since last sync)
2. **Given** an unprocessed file in a logistics partner's Drive folder, **When** the sync downloads it, **Then** the file is processed using the same matching and carrier detection logic as manual Excel import (US8)
3. **Given** a processed file, **When** the import completes successfully, **Then** the file is marked as processed (moved to a "processed" subfolder or flagged by name prefix) to prevent re-import on the next sync cycle
4. **Given** the logistics partner configuration screen, **When** an administrator sets up a new logistics partner, **Then** they provide: partner name, Google Drive folder ID, and sync enabled toggle

---

### Edge Cases

- What happens when an order is routed to a partner but the partner is deactivated before fulfillment completes? The routing remains valid for that order; only new routing is prevented.
- What happens when a partner API sync pushes files but the partner never confirms receipt? After 72 hours with no confirmation, the system creates an escalation activity for the PIC.
- What happens when the same order is routed to both internal and partner? The system enforces a single active route per order; rerouting replaces the previous route.
- What happens when a return is initiated on an order still in production? The system allows the return request but warns: "Order is still in production. Cancel production first?"
- What happens when stock reaches zero mid-production? Orders in "In Progress" stage continue (materials already consumed), but "Queued" orders are flagged as blocked.
- What happens when a partner sends a callback for an order that was rerouted away from them? The system logs the callback but does not update the order (stale route check).
- What happens when the same ORDER NUMBER appears in multiple Excel import files? The system overwrites the tracking number if a newer file has a different value, and logs the change in chatter.
- What happens when an Excel row has a tracking number but no ORDER NUMBER? The row is skipped and logged as invalid.
- What happens when auto-detection cannot determine the carrier (tracking pattern does not match known patterns)? The shipping carrier is set to "Other" and flagged for manual review.
- What happens when the GKE Excel has costs in VND (COST column) but the order is in EUR? The VND cost is stored in a separate field for reference and does NOT overwrite the order's sale price.
- What happens when Google Drive API authentication expires? The system logs the auth failure and creates an activity notification for the admin, similar to Gmail OAuth handling in Spec 001.
- What happens when the Gearment price quote is significantly higher than expected? The operator reviews the quote and can reject/cancel the draft order without confirming.

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
- **FR-021**: System MUST support configuring partners with primary/secondary priority designation, with the primary partner appearing first in routing dropdowns
- **FR-022**: System MUST support multiple authentication methods per partner: Bearer token and custom header keys (e.g., client key + client secret)
- **FR-023**: System MUST respect per-partner API rate limits when pushing orders in bulk (e.g., max 100 requests per 10 seconds for Gearment)
- **FR-024**: System MUST support multi-step partner order flows: create draft, retrieve price quote for operator review, and confirm only after manual approval
- **FR-025**: System MUST register and manage webhook subscriptions at partner APIs for order completion, cancellation, and tracking update events
- **FR-026**: System MUST provide an Excel import wizard for logistics partner tracking files supporting both 19-column (legacy, no carrier) and 20-column (with explicit carrier) formats
- **FR-027**: System MUST match imported ORDER NUMBERs to existing sale orders via `etsy_order_id` and write tracking numbers to matched orders
- **FR-028**: System MUST auto-detect shipping carrier from tracking number patterns: USPS (20-22 digit numeric), UniUni (prefix "UU"), YunExpress (prefix "YT"), with "Other" as fallback
- **FR-029**: System MUST handle "-replace" suffix in ORDER NUMBERs by stripping the suffix for matching and flagging the order as a replacement
- **FR-030**: System MUST store label URLs and QR code URLs from the import file on the sale order for shipping label access
- **FR-031**: System MUST support reading tracking files from per-logistics-partner Google Drive folders via automated cron sync
- **FR-032**: System MUST log all tracking imports with an audit trail including match/unmatch counts, carrier detection results, and per-row details

### Key Entities

- **Fulfillment Partner**: An external production/fulfillment provider with contact info, supported file formats, API endpoint, and credentials. Can be active or inactive.
- **Fulfillment Route**: The assignment of a sale order to either internal production or a specific partner. Records who routed it and when. Only one active route per order.
- **Partner Sync Log**: A record of each API sync attempt (push or callback), including status (pending/success/failed), timestamps, error messages, and retry count.
- **Production Stage**: The current manufacturing status for internally-routed orders, from Queued through Completed.
- **Return Request**: A customer return or refund request on a shipped order, with reason, action (refund/replace/discount), and resolution status.
- **Shipping Carrier**: A known shipping carrier (e.g., USPS, UniUni, YunExpress) with name, code, and tracking number pattern (prefix or regex) for auto-detection. Extensible -- new carriers added by creating a new record.
- **Logistics Partner**: An external logistics company (e.g., GKE Logistics) that provides tracking data via Excel files stored in Google Drive. Configured with folder ID and sync settings.
- **Tracking Import Log**: A record of each Excel file import session, including source (manual upload or Google Drive), file name, match/unmatch counts, carrier detection summary, and per-row detail lines.

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
- **SC-009**: Tracking numbers from logistics partner Excel files are matched to orders and populated within 2 minutes of import completion
- **SC-010**: Carrier auto-detection correctly identifies USPS, UniUni, and YunExpress from tracking number patterns with 99%+ accuracy for known patterns
- **SC-011**: Google Drive sync picks up new tracking files within one sync cycle (configurable interval, default 30 minutes)

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
- Gearment is the primary fulfillment partner with a stable v3 API at `https://apiv2.gearment.com/integration-handler`, authenticated via `X-Gearment-Client-Key` + `X-Gearment-Client-Secret` headers
- GKE Logistics provides tracking data in standardized Excel files with the 19-column format described in US8; a 20-column format with explicit carrier column is being adopted
- Google Drive API is available via service account for unattended server-side access to logistics partner folders
- The `openpyxl` library is already available in the system (used by existing Excel import wizard in Spec 001)
- Carrier tracking patterns are stable and distinctive: USPS (20-22 digit pure numeric), UniUni (prefix "UU"), YunExpress (prefix "YT")
- New carriers can be added by configuring a name + tracking pattern record (extensible without code changes)
- Google Drive folders are organized per logistics partner (not per carrier); one folder may contain files with mixed carriers

## Out of Scope

- **Automated routing rules** (e.g., auto-route based on product type or capacity) -- routing is manual in this spec
- **Full MRP/manufacturing module integration** -- US4 uses a simple stage field, not mrp.production records
- **Partner billing/invoicing** -- financial settlement with partners is handled outside this system
- **Multi-warehouse stock management** -- uses single stock location for raw materials
- **Amazon/WooCommerce channel-specific return workflows** -- only generic returns covered; channel-specific logic is future specs
- **Etsy API approval process** -- obtaining Etsy API access for messaging is a business process, not a technical spec
- **Direct GKE Logistics API integration** -- tracking data comes via Excel files, not a GKE API; GKE does not expose a REST API
- **Shipping label generation** -- labels and QR codes are provided by GKE Logistics; the system stores their URLs but does not generate labels
- **Shipping cost reconciliation** -- VND costs from the GKE Excel are stored for reference but not converted or reconciled with order prices in EUR
- **Multi-carrier rate shopping** -- no comparison of shipping rates across carriers; carrier is determined by the logistics partner
