# Research: Fulfillment Routing, Production Assignment, and Partner Integration

## R1: Fulfillment Route Storage -- Field on sale.order vs Separate Model

**Decision**: Store routing as fields directly on sale.order: `fulfillment_route` (Selection: internal/partner), `fulfillment_partner_id` (Many2one to fulfillment.partner), `routed_by` (Many2one to res.users), `routed_date` (Datetime).

**Rationale**: A separate routing model adds complexity for a 1:1 relationship. The order always has exactly one active route. Rerouting overwrites the fields and logs the change in chatter (mail.thread). This is consistent with how Spec 003 handles fulfillment_status (field on sale.order, not separate model).

**Alternatives considered**:
- Separate fulfillment.route model with history: More normalized but over-engineering for a manual routing decision that changes rarely. Chatter already provides audit trail.
- Many2many for multi-route: Spec explicitly says "single active route per order".

## R2: Partner Sync Architecture -- Cron vs Real-time Push

**Decision**: Hybrid approach. Manual "Sync Now" button triggers immediate push. Failed syncs are retried via a cron job (every 15 minutes, max 3 retries with exponential backoff).

**Rationale**: Immediate sync provides fast feedback when operators manually push. Cron handles retries without blocking the UI. This matches the Gmail fetch pattern from Spec 001 (cron-based polling with manual trigger option).

**Alternatives considered**:
- Pure cron (batch all syncs every 15 min): Too slow for operators who want immediate feedback
- Pure real-time (sync on route save): Blocks UI if partner API is slow; no retry mechanism
- Celery/background workers: Not available in Odoo CE without custom infrastructure

## R3: Partner API Architecture -- Adapter Pattern with Gearment as Reference

**Decision**: Implement a `BasePartnerAdapter` abstract class with concrete subclasses: `GearmentAdapter` for Gearment's specific API and `GenericAdapter` as a fallback for partners using the standard REST contract. A factory function `get_adapter(partner)` returns the correct adapter based on the `adapter_type` field on `fulfillment.partner`.

**Rationale**: Gearment has a fixed, non-negotiable API (v3 at `apiv2.gearment.com/integration-handler`). We cannot ask them to implement our generic contract. The adapter pattern isolates partner-specific logic (auth, payload format, multi-step flows) from the core routing system (US1). The `GenericAdapter` serves as the fallback for simpler partners.

**Adapter interface**:
```
BasePartnerAdapter:
  - test_connection() -> bool
  - push_order(sale_order) -> dict (partner_ref, price_quote, etc.)
  - get_order_status(partner_ref) -> dict
  - register_webhooks(callback_url, events) -> list of webhook IDs
  - parse_webhook_payload(headers, body) -> dict
```

**Gearment adapter specifics**:
- Auth: `X-Gearment-Client-Key` + `X-Gearment-Client-Secret` headers
- Order flow: POST `/api/v3/orders` (create draft) -> GET price quote -> Manual operator approval -> POST confirm
- Design files: Passed as URLs in `printing_options[].url` (files must be publicly accessible)
- Payload: `reference_id`, `platform`, `store_id`, `address`, `shipping_method`, line items with `variant_id`, `quantity`, `printing_options` (location_code + design URL)
- Webhooks: POST `/api/v3/webhooks` to register; events: `order.completed`, `order.cancelled`, `tracking.updated`
- Rate limit: 100 requests / 10 seconds (block for 1 minute on HTTP 429)

**Generic adapter contract**:
```
POST {partner_api_endpoint}/orders
Headers: Authorization: Bearer {api_key}
Body: {
  "order_ref": "SO12345",
  "channel_ref": "etsy-order-123",
  "shipping_address": {...},
  "items": [
    {"product": "...", "quantity": 1, "design_files": ["https://url-to-file.png"]}
  ]
}
Response: {"status": "received", "partner_ref": "P-789"}
```

**Alternatives considered**:
- Single generic contract forcing all partners to adapt: Rejected because Gearment's API is fixed and we must adapt to them
- Partner-specific Odoo modules (separate module per partner): Over-engineering for 5-10 partners; adapter classes within the same module are sufficient
- SOAP/EDI: Too complex for print-on-demand partners
- FTP file drop: No real-time status feedback

## R4: Internal Production Tracking -- Simple Stage vs MRP Module

**Decision**: Use a simple Selection field (`production_stage`) on sale.order with 4 values: queued/in_progress/qc_check/completed. Do NOT install or depend on Odoo's MRP module.

**Rationale**: The production team is 5-15 people managing a print-on-demand workflow (print, cut, pack). This is not complex manufacturing with BOMs, work centers, or routing. A simple stage field with kanban view is sufficient and avoids the complexity of MRP. If the business grows to need full MRP, a future spec can migrate the stage field to mrp.production records.

**Alternatives considered**:
- Odoo MRP module (mrp.production): Massive scope increase, requires BOM management, work center configuration, complex views. Over-engineering for a team that currently uses Google Sheets.
- Separate production.order model: Adds a 1:1 model that duplicates sale.order data. Unnecessary when a stage field and filtered view achieves the same result.

## R5: Raw Material Stock Visibility -- Custom Dashboard vs Stock Module Integration

**Decision**: Use Odoo's native stock.quant model for material tracking. The production queue view includes a "Material Stock" smart button that opens a filtered stock.quant view showing configured raw materials. Low-stock warnings are computed from stock.quant + product.template.reorder_min_qty.

**Rationale**: Odoo's stock module already handles quantity tracking, warehouse locations, and reorder rules. Building a custom inventory system violates Constitution Principle I (Odoo-Native First). The production team only needs visibility, not a separate inventory management interface.

**Alternatives considered**:
- Custom material.inventory model: Duplicates stock.quant functionality
- Embedded stock panel in production queue: Complex OWL widget, hard to maintain
- External inventory system: Breaks single-system goal

## R6: Partner Webhook Security -- HMAC Signature vs API Key

**Decision**: Use a per-partner webhook secret stored in fulfillment.partner. Partners must include an HMAC-SHA256 signature in the X-Webhook-Signature header. The controller validates the signature before processing.

**Rationale**: API keys in URL parameters can be logged; HMAC signatures verify both identity and payload integrity. This is the standard pattern used by Stripe, GitHub, and Shopify webhooks.

**Alternatives considered**:
- API key in header: Simpler but no payload integrity check
- IP allowlist: Too restrictive for partners with dynamic IPs
- OAuth2: Over-engineering for simple callbacks

## R7: Returns Workflow -- Wizard vs Direct Model

**Decision**: Use a TransientModel wizard (return.order.wizard) triggered from a button on the sale order form. The wizard collects reason, action, and notes, then creates an order.return record and associated accounting entries (credit note for refunds).

**Rationale**: A wizard provides a guided flow with validation (e.g., can't return an order not yet shipped). The persistent order.return model stores the return record for reporting. This separates the initiation flow (wizard) from the data (model).

**Alternatives considered**:
- Direct model creation (no wizard): No validation flow, users can create returns on non-shipped orders
- Odoo stock.return.picking: Only handles physical return, not refund/replacement decision
- Custom state machine: Over-engineering for <5% return rate

## R8: CRM / Etsy Message Sync -- Feasibility Assessment

**Decision**: DEFER to implementation phase. Etsy's API v3 has a Messages endpoint (GET /v3/application/shops/{shop_id}/conversations) but it requires Etsy App approval with "conversations" scope. This is a business process dependency (Etsy must approve the app), not just a technical decision.

**Rationale**: The technical implementation is straightforward (fetch messages via API, create mail.message records in Odoo, post replies via API). But the blocker is Etsy app approval, which is outside development control. US6 is P3 and contingent on this approval.

**Implementation sketch** (for when approval is obtained):
- New service: `services/etsy_messaging.py` (fetch conversations, post replies)
- New cron: Fetch messages every 10 minutes
- Model extension: sale.order gets `has_unread_etsy_messages` computed field
- View: Chatter messages tagged with subtype "Etsy Message"

**Alternatives considered**:
- Scraping Etsy seller portal: Violates Etsy ToS
- Email-based messaging (rely on Etsy email notifications): Already captured in order notes but not threaded

## R9: Tracking Import -- Excel Upload vs Direct API

**Decision**: Excel file upload (manual or from Google Drive) is the primary mechanism for receiving tracking data from GKE Logistics. A new wizard `tracking.import.wizard` follows the same pattern as the existing `import_orders_wizard.py`.

**Rationale**: GKE Logistics does not expose a REST API. Their workflow produces standardized Excel files (19 or 20 columns) stored in Google Drive. The import wizard pattern already exists in the codebase and should be reused. The system supports both the legacy 19-column format (no carrier column) and the new 20-column format (with explicit carrier column). When the carrier column is missing, carrier auto-detection fills the gap.

**Excel column mapping** (GKE standard format):
| Col | Header | Maps to |
|-----|--------|---------|
| 0 | ORDER NUMBER | Match key: `sale.order.etsy_order_id` |
| 1 | TRACKING NUMBER | `sale.order.tracking_number` (Spec 003 field) |
| 2-7 | COUNTRY, CONSIGNEE, STATE, CITY, ADDRESS, POSTCODE | Verification only (not overwritten) |
| 8 | PRODUCT NAME | Verification only |
| 9-13 | VALUE, QUANTITY, WEIGHT, WEIGHT GKE, COST | `gke_shipping_cost_vnd` (col 13 only) |
| 14 | CREATIVE | Production date (informational) |
| 15 | Date received | Warehouse date (informational) |
| 16 | Order status | Import status from GKE (informational) |
| 17 | Label link | `sale.order.label_url` |
| 18 | QR code link | `sale.order.qrcode_url` |
| 19 | SHIPPING CARRIER | `sale.order.shipping_carrier` (optional, overrides auto-detect) |

**Replacement order handling**: ORDER NUMBERs with "-replace" suffix (e.g., "4005375073-replace") are stripped to "4005375073" for matching and flagged as `is_replacement_order = True`.

**Alternatives considered**:
- GKE Logistics API: Does not exist
- CSV instead of Excel: GKE provides Excel format; changing their workflow is out of scope
- Real-time webhook from GKE: Not available

## R10: Carrier Auto-Detection -- Prefix vs Regex

**Decision**: Two-tier matching algorithm. First check `tracking_prefix` (fast string startswith). If no prefix match, fall back to `tracking_pattern` regex. If neither matches, set carrier to "Other".

**Rationale**: Most carriers have distinctive prefixes (UU for UniUni, YT for YunExpress). USPS has no prefix but a distinctive length/pattern (20-22 digit numeric). The two-tier approach is fast for the common case (O(n) prefix check) and flexible for edge cases (regex fallback).

**Carrier patterns** (from sample data analysis):
- USPS: No prefix, pattern `^\d{20,22}$` (pure digits, 20-22 chars)
- UniUni: Prefix "UU" (e.g., "UUS6482620070536484")
- YunExpress: Prefix "YT"

**Extensibility**: New carriers added by creating a `shipping.carrier` record with appropriate prefix or pattern. No code changes needed.

**Alternatives considered**:
- Regex only: Slower for simple prefix cases
- Hardcoded carrier detection in code: Not extensible without code changes
- External carrier detection API: Over-engineering for 3 known carriers

## R11: Google Drive Integration -- Service Account vs OAuth2

**Decision**: Use Google Service Account (server-to-server auth) for reading files from shared Drive folders. The service account email is granted read access to each logistics partner's folder. Credentials stored as a JSON key file path in `ir.config_parameter`.

**Rationale**: Service accounts do not require interactive OAuth2 consent flow. The existing Gmail integration (Spec 001) uses OAuth2 with refresh tokens, but Google Drive file reading is a server-side background task that benefits from non-interactive auth. The service account approach is simpler for unattended cron-based access.

**Sync workflow**:
1. Cron job runs every 30 minutes (configurable via `ir.config_parameter`)
2. For each `logistics.partner` with `gdrive_sync_enabled = True`:
   a. Authenticate with Google Drive API using service account
   b. List files in `gdrive_folder_id` modified since `gdrive_last_sync`
   c. For each new file: download to memory, process using the same logic as manual import (R9)
   d. Move processed file to "processed" subfolder or rename with prefix
   e. Update `gdrive_last_sync` on the logistics partner record

**Dependencies**: `google-api-python-client`, `google-auth` Python packages (add to requirements.txt)

**Alternatives considered**:
- OAuth2 with refresh token (same as Gmail): Viable but requires manual re-auth if token expires
- Polling Google Sheets API directly: More complex, requires sheet-specific logic instead of file download
- Watching folder via Google Drive push notifications: Complex to set up, requires public webhook endpoint

## R12: Rate Limiting -- Implementation Approach

**Decision**: In-memory token bucket per adapter instance. Each `GearmentAdapter` tracks requests made within the current rate window. When the limit is reached, the adapter sleeps or queues remaining requests.

**Rationale**: Gearment allows 100 requests per 10 seconds. For batch syncs of 50-100 orders, this is easily exceeded. A simple in-memory counter with timestamp check is sufficient -- no external rate limiter library needed at this scale.

**Implementation**: Read `rate_limit_requests` and `rate_limit_window` from the `fulfillment.partner` record. Before each API call, check if the current window's request count is exhausted. If so, sleep until the window resets. On HTTP 429, pause for 60 seconds (Gearment's block duration) and retry.

**Alternatives considered**:
- External rate limiter (Redis, etc.): Over-engineering for single-instance Odoo
- No rate limiting (let partner API reject): Risks 1-minute blocks on every bulk sync
- Queue-based with Celery: Not available in Odoo CE without custom infrastructure
