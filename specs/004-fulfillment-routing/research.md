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

## R3: Partner API Contract -- Generic REST vs Partner-specific Adapters

**Decision**: Define a generic REST contract (POST with JSON body + file attachments). Each partner implements this contract on their end. If a partner has a different API, create a partner-specific adapter in a subclass.

**Rationale**: Most print-on-demand partners accept REST APIs. A generic contract reduces per-partner development. Partner-specific adapters can be added as subclasses of a base PartnerSyncService without changing the core model.

**Contract sketch**:
```
POST {partner_api_endpoint}/orders
Headers: Authorization: Bearer {api_key}
Body: {
  "order_ref": "SO12345",
  "channel_ref": "etsy-order-123",
  "shipping_address": {...},
  "items": [
    {"product": "...", "quantity": 1, "design_files": ["base64_encoded_file"]}
  ]
}
Response: {"status": "received", "partner_ref": "P-789"}

Callback (partner -> Odoo):
POST {odoo_base_url}/fulfillment/partner/callback
Body: {
  "partner_ref": "P-789",
  "order_ref": "SO12345",
  "status": "shipped",
  "tracking_number": "1Z999AA10123456784",
  "carrier": "UPS"
}
```

**Alternatives considered**:
- SOAP/EDI: Too complex for small print-on-demand partners
- FTP file drop: No real-time status feedback
- Partner-specific integrations from day 1: Over-engineering; most partners will adapt to our contract

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
