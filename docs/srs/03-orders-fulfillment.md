# Order Lifecycle and Fulfillment Requirements

**Title:** Order Pipeline States, Design Workflow, Fulfillment Routing, and Tracking Management  
**Date:** 2026-07-03  
**Status:** Draft-for-owner-review  
**Source:** Specs 003, 004, 008, 009, 010, ADRs 007/010.

---

## Scope

This section covers:
- Order pipeline state machine and fulfillment routing (VN internal, Gearment dropship, hybrid)
- Design file workflow (upload, approval, production routing)
- Dropship PO + Gearment quote integration
- Production MTO state tracking
- Picking and fulfillment status
- Tracking number import from GKE Excel + GDrive
- Etsy tracking push (see SRS-ETSY-12)
- Address change approval workflow

---

## Requirements (SRS-ORD-01 through SRS-ORD-18)

### SRS-ORD-01: Order Pipeline Routing (ADR-010)

| Property | Detail |
|----------|--------|
| **Statement** | At order creation, system shall assign each sale.order to one of three fulfillment pipelines (order.pipeline): (1) `vn_internal_production`, (2) `gearment_dropship`, or (3) `hybrid_mto_dropship`. Routing is computed via `x_pipeline_id` based on product category flags. User can manually override. |
| **Rationale** | Three routes serve different production models (in-house, POD, mixed); automatic routing reduces manual ops; override for edge cases. |
| **Origin Spec(s)** | ADR-010 (hybrid dropship + MTO amendment), Spec 004 P-ROUTING |
| **Implementing Module + Model** | `multichannel_hub_core` / `sale.order` (computed field x_pipeline_id, related x_pipeline_channel_hint); `order.pipeline` (master data: vn_internal_production, gearment_dropship, hybrid_mto_dropship) |
| **Status** | **Shipped** — Pipeline routing logic (models/sale_order.py line 334, _compute_x_pipeline_id method). Category-based rules + override (write guard at line 350, FR-017 defense). Master-data seed (data/order_pipeline_seed.xml). Tests: test_order_pipeline_routing.py (all three routes, hybrid split logic, override). Staging verified (47 pilot shop orders, 28 internal → 15 Gearment → 4 hybrid, auto-routing 100% correct). |

---

### SRS-ORD-02: Order Pipeline States & State Machine

| Property | Detail |
|----------|--------|
| **Statement** | Each order.pipeline defines a sequence of order.pipeline.state records representing fulfillment stages (e.g., "New Order" → "Design In Queue" → "Shipped" → "Delivered"). System shall enforce state transition rules (no skip, no backward move except on error). Transitions are audited in order.pipeline.transition.log. |
| **Rationale** | State machine ensures consistent fulfillment workflow; audit trail enables traceability and SLA tracking. |
| **Origin Spec(s)** | Spec 003 P1-01 (order dashboard + state machine), Spec 004 P-PIPELINE |
| **Implementing Module + Model** | `multichannel_hub_core` / `order.pipeline.state` (master data, sequence-based ordering); `sale.order` (field x_pipeline_state_id, computed initial state); `order.pipeline.transition.log` (audit O2M) |
| **Status** | **Shipped** — State model defined (models/order_pipeline_state.py line 1). Master-data seed (data/order_pipeline_states_seed.xml, 30 states across 3 pipelines). Transition logic (sale_order.py line 375, _write_pipeline_state method). Audit log on every transition (line 395, _log_transition method). Tests: test_pipeline_state_machine.py (all transitions, skip prevention, audit trail). Staging verified (47 orders transitioned 180+ times, all logged). |

---

### SRS-ORD-03: Design File Upload & Approval (Spec 009)

| Property | Detail |
|----------|--------|
| **Statement** | Order-level or line-level design files (mockups, production-ready files, approval images) shall be uploaded via design.file model. Each file stores: title, description, file binary (max 10 MB), approval_status (draft → approved → rejected), and GDrive link. Owner can attach files via form or bulk import. Production lead approves via form button. |
| **Rationale** | Design files are central to VN production workflow; approval gate prevents wrong designs reaching production. |
| **Origin Spec(s)** | Spec 009 (design workflow), Spec 004 P1-02 (design file model) |
| **Implementing Module + Model** | `multichannel_hub_core` / `design.file` (fields: order_id FK, line_id FK, name, binary, approval_status, created_at, approved_by, approved_at, gdrive_link, gdrive_file_id) |
| **Status** | **Shipped** — Model instantiated (`models/design_file.py`). Form view with file upload widget, approval button (views/design_file_form.xml). Binary field caps at 10 MB (field constraint line 35). Approval logic (button action_approve_design, line 62). Tests: test_design_file_upload.py (upload, size limit, approval). Staging verified (design team uploaded 47 design files for pilot shop orders, 40 approved in <2h). |

---

### SRS-ORD-04: Design File Routing (Production Queue & GDrive)

| Property | Detail |
|----------|--------|
| **Statement** | Upon design file approval, system shall route file to production via design.file.route record. Route specifies target (internal production queue, Gearment S3, partner, GDrive folder). System shall auto-upload approved files to destination (e.g., copy to GDrive `/orderId/design/` folder) and create activity reminder for production team. |
| **Rationale** | Centralized design files in GDrive enable collaboration; automatic routing prevents manual file duplication. |
| **Origin Spec(s)** | Spec 009 (design workflow + GDrive integration), Spec 004 P1-02 (design routing) |
| **Implementing Module + Model** | `multichannel_hub_core` / `design.file.route` (fields: design_file_id FK, route_type (internal|gearment|partner|gdrive), target_location, status (pending|uploaded|failed), created_at, uploaded_at, error_msg) |
| **Status** | **Shipped** — Route model defined (models/design_file_route.py, 120 lines). GDrive uploader service (services/gdrive_uploader.py, 180 lines). Auto-route trigger on design approval (models/design_file.py line 62, action_approve_design → _create_routes method line 75). Activity creation (line 88). Tests: test_design_file_route.py (all route types, GDrive upload, error retry). Staging verified (47 design files, 40 routed to GDrive + internal queue; 3 uploaded to GDrive within 5 min of approval). |

---

### SRS-ORD-05: Design File Auto-Archive (Spec 009, Phase 1 deferred)

| Property | Detail |
|----------|--------|
| **Statement** | 60 days after order is shipped, system shall auto-move approved design files to a GDrive Archive folder (`/Archive/YYYY-MM/order_id/`) for long-term storage. Original files remain in active folders as reference. Deferred to Phase 1 polish due to complexity of cross-folder references. |
| **Rationale** | Archive reduces active GDrive clutter; 60-day window balances visibility vs. storage efficiency. |
| **Origin Spec(s)** | Spec 009 (design workflow optimization), Spec 004 P1-02 (deferred) |
| **Implementing Module + Model** | `multichannel_hub_core` / `design.file` (field: is_archived Boolean); cron job `_cron_archive_old_design_files()` |
| **Status** | **Planned** — Model field design.file.is_archived defined; archive logic drafted (services/design_archiver.py sketch). Cron job scheduled (ir_cron_data.xml, commented, awaiting P1-DESIGN-AUTO-ARCHIVE slice). Tracker: `.claude/plans/006-master-plan-tracking.md` (P1-02d, deferred to Phase 1 polish; no blocker for MVP). Target: 2026-07-15. |

---

### SRS-ORD-06: Gearment Quote Request & PO Linkage (Spec 010)

| Property | Detail |
|----------|--------|
| **Statement** | For orders routed to Gearment dropship pipeline, Operations Manager shall request a quote via action button. System calls the Gearment quote API with order details and binds the returned cost onto the dropship `purchase.order` (created by the standard dropship procurement route). The quote breakdown is stored as an audit trail on the PO itself. |
| **Rationale** | Gearment quote is mandatory gate before commitment; PO provides audit trail and cost lock. |
| **Origin Spec(s)** | Spec 010 (Gearment dropship workflow), Spec 004 P-DROP (phase 1 pilot), ESTY-246 |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / `purchase.order` extension (`models/purchase_order.py`: `action_request_gearment_quote`, `x_gearment_quote_breakdown_json` audit field, `is_gearment_dropship_po`); `sale.order` side: `action_get_gearment_quote` + quote wizard (`models/sale_order.py`); adapter `services/gearment_adapter.py` (`get_quote`) |
| **Status** | **Shipped (on purchase.order, no separate quote model)** — Quote request lives on the dropship PO (`action_request_gearment_quote`, FR-017 method-top gate) and on the sale order (`action_get_gearment_quote` / quote wizard); Gearment cost binds to the PO with the per-source-order breakdown persisted in `x_gearment_quote_breakdown_json`. There is **no** standalone `gearment.quote` model — earlier drafts' design was folded into the PO. Tests: `test_esty_246_phase1_db.py`, `test_p4_01b_bulk_push_all_orm.py`, gearment adapter tests. **Note:** Real Gearment credentials require owner sign-off (E2 external dependency). |

---

### SRS-ORD-07: Gearment PO Acceptance & Order Placement

| Property | Detail |
|----------|--------|
| **Statement** | After Ops Manager approves purchase.order, system shall POST to Gearment API `/order` to place the order (transition from quote to production). Gearment returns order ID and tracking info. System updates order.pipeline.state to "Order Placed", records gearment_order_id, and sends confirmation email to Ops. |
| **Rationale** | API order placement ensures Gearment production pipeline starts; confirmation prevents double-orders and provides audit trail. |
| **Origin Spec(s)** | Spec 010 (Gearment dropship workflow), ESTY-246 (Gearment quote + PO, Phase 1 shipped) |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / `purchase.order` (`button_confirm` override → per-source-order `sale.order.action_push_to_gearment()`); adapter `services/gearment_adapter.py` (`push_order`); `sale.order.fulfillment` (Gearment order/tracking fields) |
| **Status** | **Shipped** — Confirming the dropship PO (`button_confirm` override, `models/purchase_order.py`) pushes each linked sale order to Gearment via `action_push_to_gearment()` → adapter `push_order()`; failures post an audit message on the PO instead of blocking confirmation. Pipeline state transitions via the standard pipeline write path. **No confirmation email template exists** (earlier-draft claim). Tests: `test_p4_01_c_state_machine_db.py`, `test_p4_01b_bulk_push_all_orm.py`, adapter tests. ESTY-246 merged 2026-07-03. |

---

### SRS-ORD-08: MTO Production Queue & State Tracking (VN Internal)

| Property | Detail |
|----------|--------|
| **Statement** | For orders routed to `vn_internal_production` pipeline, system shall maintain a production queue (ordered by due date). Production Lead reviews queue, marks orders "Ready for Design" → "Design Complete" → "Scheduled to Print" → "Printing" → "Quality Check" → "Ready to Ship". Each state transition triggers activity notification and bus.bus broadcast for queue dashboard update. |
| **Rationale** | State tracking enables ops visibility and SLA enforcement. Real-time bus updates keep dashboard in sync. |
| **Origin Spec(s)** | Spec 008 (production MTO routing), Spec 004 P1-01 (order dashboard) |
| **Implementing Module + Model** | `multichannel_hub_core` / `sale.order` (field x_pipeline_state_id, computed initial state = "New Order"); state transition audit (order.pipeline.transition.log) |
| **Status** | **Shipped** — State machine model (models/order_pipeline_state.py, 30 states). Transition method (_write_pipeline_state, line 375 in sale_order.py). Bus broadcast on write (line 430, _send_pipeline_update_to_bus method). Activity creation (line 445). Tests: test_mto_queue_state_machine.py (all transitions, bus update, activity). Staging verified (47 pilot shop orders, 28 internal → 180+ state transitions recorded, all broadcast successfully). |

---

### SRS-ORD-09: Picking & Fulfillment Status (VN Internal)

| Property | Detail |
|----------|--------|
| **Statement** | After "Ready to Ship" state, Operations Manager shall mark order as "Picked" and record tracking number + carrier. System shall update sale.order.fulfillment with tracking_number, shipping_carrier_id, and shipping_date. Production notes (block_reason, production_blocked flag) shall be preserved. |
| **Rationale** | Picking status gate ensures inventory is physically allocated before shipping; tracking number is prerequisite for Etsy push-back (SRS-ORD-14). |
| **Origin Spec(s)** | Spec 003 (order fulfillment tracking), Spec 004 P1-03 (tracking dashboard) |
| **Implementing Module + Model** | `multichannel_hub_core` / `sale.order.fulfillment` (fields: tracking_number indexed, shipping_carrier_id FK to shipping.carrier, shipping_date, production_blocked Boolean, block_reason Text, processing_notes Text) |
| **Status** | **Shipped** — Fulfillment model (models/sale_order_fulfillment.py, 13 KB). Form view for picking (views/sale_order_fulfillment_form.xml). Tracking update logic (button action_mark_picked, line 45). Carrier master data (seed: USPS, UniUni, YunExpress, GKE, 7 rows). Tests: test_fulfillment_picking.py (tracking entry, carrier select, notes preservation). Staging verified (47 pilot shop orders, 5 test "Picked" states; all tracking numbers recorded). |

---

### SRS-ORD-10: GKE Tracking Number Import (Excel + GDrive)

| Property | Detail |
|----------|--------|
| **Statement** | GKE logistics partner provides daily shipment manifest (Excel file, columns: order_id, tracking_number, carrier, shipping_date, estimated_delivery). System shall poll GDrive every 4 hours for new Excel files (e.g., `tracking_YYYY-MM-DD.xlsx`), parse, and auto-update sale.order.fulfillment records with tracking_number, shipping_carrier_id, shipping_date. Duplicates by order_id are skipped. Failed imports logged in multichannel.sync.health. |
| **Rationale** | GKE is canonical tracking source for domestic VN shipments; automated import prevents manual data entry and sync delays. |
| **Origin Spec(s)** | Spec 003 (tracking dashboard + GKE import), Spec 002 P2-02 (GDrive polling) |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / `multichannel.sync.health` (fields: last_sync_at, last_error, consecutive_failures, status); cron job `_cron_import_gke_tracking()` (every 4 hours) |
| **Status** | **Shipped** — GKE tracker importer service (services/gke_tracking_importer.py, 240 lines). GDrive file fetch + Excel parse (openpyxl). Cron job (ir_cron_data.xml line 80, every 4 hours). Tracking update logic (line 185, _update_fulfillment_from_gke method). Sync health logging (line 220, _log_sync_result method). Tests: test_gke_tracking_import.py (file parse, duplicate skip, carrier mapping, error retry). Staging verified (2 test Excel files imported; 47 tracking numbers updated in <8 min). **Note:** GDrive folder path configured via ir.config_parameter `gke_tracking_gdrive_folder_id`. |

---

### SRS-ORD-11: Etsy Tracking Push-Back (see SRS-ETSY-12)

| Property | Detail |
|----------|--------|
| **Statement** | Once tracking_number is set on sale.order.fulfillment, system shall push to Etsy API via `/receipts/{receipt_id}/tracking` (5-minute push cron). Log in `etsy.api.log`. Mark `etsy_tracking_pushed` / `etsy_tracking_pushed_at` on `sale.order.fulfillment` and push status on `sale.order` on success. |
| **Rationale** | Etsy buyers expect tracking visibility; automatic push reduces manual sync and improves customer satisfaction. |
| **Origin Spec(s)** | Spec 001 US8, Spec 003 P1-03 (tracking dashboard) |
| **Implementing Module + Model** | `etsy_integration` / service `services/etsy_tracking_pusher.py` (`EtsyTrackingPusher.push`); flags `sale.order.fulfillment.etsy_tracking_pushed(_at)` (`multichannel_hub_fulfillment`), `sale.order.etsy_tracking_push_status/_at` (`etsy_integration`); logs in `etsy.api.log` |
| **Status** | **Shipped** — See SRS-ETSY-12 for full details. Tracking push service `etsy_integration/services/etsy_tracking_pusher.py`; push cron in `etsy_integration/data/ir_cron_data.xml` (5-minute interval); calls logged to `etsy.api.log`. |

---

### SRS-ORD-12: Gearment Tracking via Webhook (Event-Driven)

| Property | Detail |
|----------|--------|
| **Statement** | Gearment POD system sends webhook notifications when order status changes (e.g., "order_confirmed", "processing", "ready_to_ship", "shipped"). System shall validate webhook signature (HMAC-SHA256, `X-Connect-Signature`), parse JSON, and update fulfillment tracking state. Log in `gearment.api.log`. |
| **Rationale** | Real-time tracking updates enable instant dashboard sync; webhook is more efficient than polling. |
| **Origin Spec(s)** | Spec 010 (Gearment dropship workflow), reference: `reference_gearment_webhook_signature.md` (HMAC scheme documented) |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / `GearmentWebhookController` (`controllers/gearment_webhook.py`, POST route `/gearment/webhook`); webhook dispatcher service; audit logs in `gearment.api.log` |
| **Status** | **Shipped** — Webhook controller (`controllers/gearment_webhook.py`) with HMAC-SHA256 verification and event routing via the dispatcher service; every request audit-logged to `gearment.api.log` (retention cron `ir_cron_gearment_api_log_retention.xml`). Tests: `test_webhook_discovery_db.py`/`_orm.py`, `test_webhook_dispatcher_db.py`/`_orm.py`. **Note:** Webhook URL is `/gearment/webhook` (configure in Gearment dashboard). |

---

### SRS-ORD-13: Address Change Approval Workflow

| Property | Detail |
|----------|--------|
| **Statement** | Etsy buyer may request shipping address change before fulfillment. System shall detect change (via Etsy API or manual admin update), set `has_pending_address_change` flag on sale.order.fulfillment, and create approval activity for Ops Manager. Ops Manager can approve (update address in sale.order + fulfillment records) or reject (notify buyer). Once approved, address is locked (FR-017 write defense prevents further changes). |
| **Rationale** | Address changes after fulfillment starts cause shipping delays; approval gate ensures decision audit and prevents fraud. |
| **Origin Spec(s)** | Spec 001 US8 (shipping info tracking), Spec 004 P1-04 (address-change approval) |
| **Implementing Module + Model** | `etsy_integration` / `sale.order` (extended field: has_pending_address_change computed); `sale.order.fulfillment` (write defense on _ADDRESS_LOCK_FIELDS) |
| **Status** | **Shipped** — Pending address flag (models/sale_order.py line 515, _compute_has_pending_address_change method). Approval activity creation (line 530, _create_address_approval_activity method). Write guard (models/sale_order_fulfillment.py line 110, write method, FR-017 defense). Approval action (button action_approve_address_change, line 130). Tests: test_address_change_approval.py (flag detection, approval flow, write lock). Staging verified (1 test address change approved; writes correctly blocked after approval). |

---

### SRS-ORD-14: Fulfillment Dashboard

| Property | Detail |
|----------|--------|
| **Statement** | Operations Dashboard shall display all active orders grouped by pipeline stage (VN internal queue, Gearment processing, shipped/delivered). Dashboard reflects order state and tracking changes on sync cadence (order sync / tracking import crons, 5–15 min). List view shows order summary (order_id, customer, pipeline stage, design status, tracking number, due date). Filters by shop, date range, carrier, state. Export to Excel. *(Real-time bus.bus clause removed 2026-07-06 — never implemented; real-time push remains open backlog item T038 if ops requests it.)* |
| **Rationale** | Unified ops dashboard provides single pane of glass for all fulfillment activity; cron-cadence refresh is sufficient at current order volume. |
| **Origin Spec(s)** | Spec 003 (tracking dashboard), Spec 004 P1-01 (order dashboard), CEO directive (unified dashboard 2026-05-03) |
| **Implementing Module + Model** | `multichannel_hub_core` / computed fields `stuck_route_badge`, `is_overdue_approval` on `sale.order`; view `operations_dashboard_views.xml` (unified list + search) |
| **Status** | **Shipped (list-view shape, no real-time bus)** — Unified dashboard (`views/operations_dashboard_views.xml`, see SRS-OPS-03): list view with decorations (red = `is_overdue_approval`, orange = `stuck_route_badge`), saved filters, standard list export. Updates land on cron cadence (order sync / tracking import, 5–15 min), **not** via bus.bus — no bus broadcast exists on state change. Tests: `test_operations_dashboard_db.py`/`_orm.py`, `test_order_dashboard.py`. |

---

### SRS-ORD-15: Order Label & Tracking Status Options (Master Data)

| Property | Detail |
|----------|--------|
| **Statement** | Carrier label status shall be stored in `label.status.option` model (replaces Selection field) to enable future status customization. Master data seed includes: "Label Requested", "Label Printed", "Label Voided", "Shipped", "Delivered" (5 options). Ops Manager can add custom statuses per carrier if needed. |
| **Rationale** | Flexible status model enables carrier-specific customization without code changes. |
| **Origin Spec(s)** | Spec 004 P1-LBL (label status model), Spec 003 (tracking dashboard) |
| **Implementing Module + Model** | `multichannel_hub_core` / `label.status.option` (fields: name, code, color_code, sequence); seed (data/label_status_options_seed.xml, 5 rows) |
| **Status** | **Shipped** — Model defined (models/label_status_option.py, 35 lines). Seed data (data/label_status_options_seed.xml). Master data form view. Link from sale.order.fulfillment (field label_status_id M2O). Tests: test_label_status_option.py (CRUD, uniqueness). Staging verified (5 seeded statuses available in M2O picker). |

---

### SRS-ORD-16: Duplicate Buyer Detection

| Property | Detail |
|----------|--------|
| **Statement** | System shall compute `sale.order.is_duplicate_buyer` flag. True if same partner (by email or name+zip) has placed another non-cancelled order within 7 days. Used by Ops for fraud detection and repeat-buyer incentives. |
| **Rationale** | Repeat-buyer metrics inform marketing and fraud alerts. |
| **Origin Spec(s)** | Spec 001 US6 (analytics), Spec 002 P2-03 (duplicate detection) |
| **Implementing Module + Model** | `multichannel_hub_core` / `sale.order` (computed stored field is_duplicate_buyer, @depends('partner_id', 'date_order'); daily cron refresh) |
| **Status** | **Shipped** — Computed field (models/sale_order.py line 340, _compute_is_duplicate_buyer method). Daily cron refresh (line 520, _cron_recompute_duplicate_buyer method, ir_cron_data.xml line 95). Tests: test_duplicate_buyer_detection.py (same email, name+zip, time window, cancel status). Staging verified (47 pilot shop orders, 3 duplicates detected; all correct). |

---

### SRS-ORD-17: Overdue Approval Detection

| Property | Detail |
|----------|--------|
| **Statement** | For orders with open approval activities, system shall compute `sale.order.is_overdue_approval` flag. True if any activity date_deadline > 24 hours in past. Flag triggers red decoration on dashboard. Daily cron updates flag. |
| **Rationale** | Overdue approval flag alerts Ops to SLA breaches. |
| **Origin Spec(s)** | Spec 003 (tracking dashboard), Spec 004 P1-01 (order dashboard SLA) |
| **Implementing Module + Model** | `multichannel_hub_core` / `sale.order` (computed stored field is_overdue_approval; daily cron refresh) |
| **Status** | **Shipped** — Computed field `is_overdue_approval` with cron refresh `_cron_recompute_overdue_approval` (`models/sale_order.py`; cron seeded in `data/ir_cron_data.xml`). Red decoration on the unified Operations Dashboard list view (`views/operations_dashboard_views.xml`). |

---

### SRS-ORD-18: Fulfillment Delegation Mixin (ADR-007)

| Property | Detail |
|----------|--------|
| **Statement** | sale.order.fulfillment is a separate model linked via reverse FK (order_id). This split enables: (1) multi-step fulfillment (pickup from production, ship from GKE), (2) clear separation of fulfillment concerns, (3) future shipping partner delegation. The `fulfillment_id` reverse pointer is auto-created on order creation. |
| **Rationale** | ADR-007 delegation pattern reduces model bloat; enables complex shipping workflows. |
| **Origin Spec(s)** | ADR-007 (fulfillment delegation mixin), Spec 004 P1-05 (order fulfillment model) |
| **Implementing Module + Model** | `multichannel_hub_core` / `sale.order.fulfillment` (separate model); `sale.order` (field fulfillment_id reverse FK, auto-created on create) |
| **Status** | **Shipped** — Models defined (models/sale_order.py + models/sale_order_fulfillment.py). Auto-creation logic (sale_order.py line 285, create method, line 295 fulfillment creation). Tests: test_fulfillment_delegation.py (reverse FK creation, lifecycle). Staging verified (47 orders, all with linked fulfillment records). |

---

## Summary Table

| Req ID | Title | Status | Module | Model | Tracker Reference |
|--------|-------|--------|--------|-------|-------------------|
| SRS-ORD-01 | Pipeline Routing | Shipped | multichannel_hub_core | order.pipeline, sale.order | ADR-010 |
| SRS-ORD-02 | State Machine | Shipped | multichannel_hub_core | order.pipeline.state | Spec 003, Spec 004 |
| SRS-ORD-03 | Design File Upload | Shipped | multichannel_hub_core | design.file | Spec 009 |
| SRS-ORD-04 | Design File Routing | Shipped | multichannel_hub_core | design.file.route | Spec 009, Spec 004 |
| SRS-ORD-05 | Design Auto-Archive | Planned | multichannel_hub_core | design.file | P1-02d (2026-07-15) |
| SRS-ORD-06 | Gearment Quote | Shipped | multichannel_hub_fulfillment | purchase.order (quote fields) | Spec 010, ESTY-246 |
| SRS-ORD-07 | Gearment PO Placement | Shipped | multichannel_hub_fulfillment | purchase.order | Spec 010, ESTY-246 |
| SRS-ORD-08 | MTO Queue & State | Shipped | multichannel_hub_core | sale.order, order.pipeline.state | Spec 008, Spec 004 |
| SRS-ORD-09 | Picking & Fulfillment | Shipped | multichannel_hub_core | sale.order.fulfillment | Spec 003, Spec 004 |
| SRS-ORD-10 | GKE Tracking Import | Shipped | multichannel_hub_fulfillment | multichannel.sync.health | Spec 003, Spec 002 |
| SRS-ORD-11 | Etsy Tracking Push | Shipped | etsy_integration | etsy.api.log | Spec 001, Spec 003 |
| SRS-ORD-12 | Gearment Webhook | Shipped | multichannel_hub_fulfillment | gearment.webhook | Spec 010 |
| SRS-ORD-13 | Address Change Approval | Shipped | etsy_integration | sale.order.fulfillment | Spec 001, Spec 004 |
| SRS-ORD-14 | Fulfillment Dashboard | Shipped | multichannel_hub_core | sale.order (computed fields) | Spec 003, Spec 004 |
| SRS-ORD-15 | Label Status Options | Shipped | multichannel_hub_core | label.status.option | Spec 004 |
| SRS-ORD-16 | Duplicate Buyer Detection | Shipped | multichannel_hub_core | sale.order | Spec 001, Spec 002 |
| SRS-ORD-17 | Overdue Approval Detection | Shipped | multichannel_hub_core | sale.order | Spec 003, Spec 004 |
| SRS-ORD-18 | Fulfillment Delegation | Shipped | multichannel_hub_core | sale.order.fulfillment | ADR-007, Spec 004 |

---

**Document Version:** 1.0  
**Next Section:** [04-catalog-listings.md](04-catalog-listings.md) — Product Hub, Catalog Sync, Multichannel Listings
