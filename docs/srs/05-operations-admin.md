# Operations, Administration, and Observability Requirements

**Title:** Dashboards, Health Monitoring, API Logging, Configuration, Import Wizards, and Security Roles  
**Date:** 2026-07-03  
**Status:** Draft-for-owner-review  
**Source:** Specs 003, 004, 013, 014, master plan Phase 1 (P1-01, P1-03, P1-08, etc.).

---

## Scope

This section covers:
- Unified order, tracking, and operations dashboards (Phase 1)
- Sync health monitoring and observability
- API request/response logging
- System configuration (cron intervals, rate limits, thresholds)
- Import/export wizards (orders, products, tracking)
- Data migration tools
- ACL matrix and user group permissions
- I18n and Vietnamese business docs

---

## Requirements (SRS-OPS-01 through SRS-OPS-16)

### SRS-OPS-01: Order Dashboard & Analytics

| Property | Detail |
|----------|--------|
| **Statement** | Operations Manager shall access unified Order Dashboard showing: all orders grouped by shop and fulfillment status (pipeline stage). Pivot view shows order count/revenue by stage. List view displays order summary (order ID, customer, pipeline stage, design count, tracking status, due date). Filters: shop, date range, pipeline stage, customer. Color-coded decorations: red if overdue_approval, orange if stuck_route_badge. Export to Excel. |
| **Rationale** | Single pane of glass for order lifecycle visibility; enables rapid problem detection and SLA enforcement. |
| **Origin Spec(s)** | Spec 003 (tracking dashboard), Spec 004 P1-01 (order dashboard) |
| **Implementing Module + Model** | `multichannel_hub_core` / view `order_dashboard.xml` (pivot + list); computed fields on `sale.order` (is_overdue_approval, stuck_route_badge) |
| **Status** | **Shipped** — Dashboard view (views/order_dashboard.xml, 180 lines). Pivot by stage (pivot tab, group_by="x_pipeline_state_id/name"). List view with filters (shop, date, stage, partner). Decorations (red=overdue, orange=stuck). Export button (server_action_export_orders). Bus.bus live update on state change. Tests: test_order_dashboard.py (pivot accuracy, filters, decorations, export). Staging verified (dashboard opens, 47 orders displayed, pivot groups correctly). |

---

### SRS-OPS-02: Tracking Dashboard & Real-Time Sync

| Property | Detail |
|----------|--------|
| **Statement** | Tracking Dashboard displays all orders with tracking numbers, grouped by carrier and delivery status. Real-time updates via bus.bus when fulfillment.tracking_number or tracking_state changes. Shows: carrier logo (from shipping.carrier icon field), tracking number (clickable deeplink via tracking_url), estimated delivery date, status badge (Label Requested, Shipped, Delivered). Filter by carrier, date range, state. Alert if tracking not updated > 7 days (stuck). |
| **Rationale** | Ops visibility into shipment pipeline; bus.bus enables instant customer query resolution. Stuck alerts catch fulfillment gaps. |
| **Origin Spec(s)** | Spec 003 P1-03 (tracking dashboard), Spec 004 P1-03 (fulfillment status) |
| **Implementing Module + Model** | `multichannel_hub_core` / view `tracking_dashboard.xml` (list + kanban); `sale.order.fulfillment` (fields: tracking_number, tracking_url, shipping_carrier_id, tracking_state); bus.bus broadcast on fulfillment write |
| **Status** | **Shipped** — Dashboard view (views/tracking_dashboard.xml, 150 lines). List view with decorations (orange if no update > 7 days). Kanban view grouped by tracking_state. Carrier icon display (shipping_carrier_id.icon field). Deeplink formatting (tracking_url template per carrier, line 95). Bus broadcast on fulfillment change (sale_order_fulfillment.py write method, line 125, _send_tracking_update_to_bus). Tests: test_tracking_dashboard.py (realtime update, stuck detection, deeplink formatting). Staging verified (dashboard opens, 5 test orders with tracking displayed, state change broadcast within 1 sec). |

---

### SRS-OPS-03: Operations Dashboard (CEO Directive, Unified)

| Property | Detail |
|----------|--------|
| **Statement** | Single unified Operations Dashboard combining order + tracking + inventory + design status. CEO directive 2026-05-03: one dashboard, not split. Shows: KPI tiles (today's orders, ready-to-ship count, overdue count, low-stock SKUs). Grid of status cards (VN internal production queue, Gearment processing, customer feedback pending). Quick-action buttons (Mark Picked, Request Quote, Approve Design, Export Tracking). Drill-down to detailed reports (list views). |
| **Rationale** | Unified view prevents ops context switching; KPI tiles enable rapid SLA assessment. One source of truth for exec reporting. |
| **Origin Spec(s)** | Spec 004 P1-DASH-MERGE (CEO directive 2026-05-03), Phase 1 P1-01 exit criterion |
| **Implementing Module + Model** | `multichannel_hub_core` / view `operations_dashboard.xml` (dashboard widget layout); computed KPI fields on `sale.order` + cron-refreshed metrics |
| **Status** | **Shipped** — Unified dashboard (views/operations_dashboard.xml, 220 lines). KPI tiles with computed fields (today_order_count, ready_to_ship_count, overdue_count, low_stock_sku_count). Status cards with drill-down actions. Quick-action buttons. Widget layout via form/qweb. Tests: test_operations_dashboard.py (KPI accuracy, drill-down paths, actions). Staging verified (dashboard loads, 47 orders, KPIs show correct counts). |

---

### SRS-OPS-04: Sync Health Monitoring & Multi-Channel Observability

| Property | Detail |
|----------|--------|
| **Statement** | System shall track sync health for each data integration (Etsy API order fetch, email ingest, GKE tracking import, Gearment webhook, inventory sync). multichannel.sync.health model stores: last_sync_at, last_error (error message), consecutive_failures (counter), status (healthy|warning|unhealthy), recovery_action (auto-retry|manual_intervention|paused). Cron jobs increment failure counter on error; reset on success. Dashboard widget shows status of all integrations (green=healthy, yellow=warning, red=unhealthy). Threshold: 3 consecutive failures → warning; 5+ → unhealthy + alert. |
| **Rationale** | Observability into sync pipeline; early alert on integration failures prevents data gaps. Multi-channel sync status enables triage. |
| **Origin Spec(s)** | Spec 004 P-HEALTH (sync health monitoring), Spec 003 (tracking dashboard) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.sync.health` (fields: sync_type Selection (etsy_order|email|gke_tracking|gearment_webhook|inventory), last_sync_at Datetime, last_error Text, consecutive_failures Integer, status Selection, recovery_action Selection) |
| **Status** | **Shipped** — Sync health model (models/multichannel_sync_health.py, 85 lines). Health widget view (views/sync_health_widget.xml, 60 lines). Cron jobs increment/reset counters (services/sync_health_manager.py, 120 lines). Alert creation on threshold (line 85, _maybe_create_alert method). Tests: test_sync_health_monitoring.py (counter logic, status transitions, alerts). Staging verified (5 sync types tracked, status accurate, warning threshold triggers). |

---

### SRS-OPS-05: API Request & Response Logging (multichannel.api.log)

| Property | Detail |
|----------|--------|
| **Statement** | Every external API call (Etsy, Gearment, GDrive, Gmail, ECB) shall be logged in multichannel.api.log with: api_type (etsy|gearment|gdrive|gmail|ecb), request_body (JSON), response_body (first 4000 chars), status_code (HTTP), success Boolean, created_at Datetime, order_id FK (if relevant). Logs retained for 30 days (older purged via cron). Used for debugging sync failures, API quota monitoring, and audit trail. |
| **Rationale** | API logs enable troubleshooting of integration failures; audit trail for compliance; quota monitoring prevents rate-limit surprises. |
| **Origin Spec(s)** | Spec 004 P-HEALTH (observability), Spec 013 (audit trail) |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / `multichannel.api.log` (model, 50 lines); cron `_cron_purge_old_api_logs()` (30-day retention) |
| **Status** | **Shipped** — API log model (models/multichannel_api_log.py, 50 lines). Log entries created by each integration (etsy_order_syncer line 95, gearment_quote_requester line 140, gdrive_uploader line 60, etc.). Purge cron (ir_cron_data.xml line 115, 30-day retention). Tests: test_api_logging.py (log entry creation, response truncation, purge logic). Staging verified (5 Etsy API calls logged; logs queryable). |

---

### SRS-OPS-06: System Configuration Parameters (ir.config_parameter)

| Property | Detail |
|----------|--------|
| **Statement** | System-wide settings shall be configurable via res.config.settings form (Odoo settings page). Parameters include: etsy_api_cron_interval (10 min default), email_ingest_cron_interval (10 min), gke_tracking_cron_interval (4 hours), gearment_quote_auto_fetch (Boolean), inventory_sync_interval (2 hours), smtp_rate_limit_per_minute (default 60), api_request_timeout_sec (default 30), gke_tracking_gdrive_folder_id, gearment_webhook_secret, ecb_currency_api_key. Form includes Help text explaining each parameter. |
| **Rationale** | Centralized config reduces code changes; enables ops tuning without deploy. |
| **Origin Spec(s)** | Spec 013 (system configuration), best practice |
| **Implementing Module + Model** | `multichannel_hub_core` / model `res.config.settings` (extended with all parameters as fields); wizard view `res_config_settings.xml` |
| **Status** | **Shipped** — Config model (models/res_config_settings.py, 95 lines). Settings form view (views/res_config_settings_form.xml, 180 lines). All key parameters with help text. Tests: test_config_parameters.py (get_values/set_values, validation). Staging verified (settings page loads, parameters editable and saved). |

---

### SRS-OPS-07: Cron Job Management & Monitoring

| Property | Detail |
|----------|--------|
| **Statement** | System defines 10+ cron jobs (ir.cron records): order ingest (Etsy API + email), tracking import (GKE), tracking push (Etsy), Gearment webhook retry, currency rate sync, health monitor, api log purge, duplicate buyer recompute, overdue approval recompute, design file archival (deferred). Each cron has: name, model, method, interval_number, interval_type (minutes|hours|days). Admin can enable/disable cron via form button. Dashboard shows last run time + next run time for each cron. Cron failures logged to multichannel.sync.health. |
| **Rationale** | Centralized cron management enables ops to tune automation without code changes. Last-run dashboard enables quick diagnosis of sync gaps. |
| **Origin Spec(s)** | Spec 004 P-HEALTH (observability), best practice |
| **Implementing Module + Model** | `ir.cron` (Odoo core model, seed via ir_cron_data.xml); cron dashboard view (views/cron_monitor_dashboard.xml) |
| **Status** | **Shipped** — 10 cron jobs seeded (ir_cron_data.xml, 120 lines). Cron dashboard (views/cron_monitor_dashboard.xml, 95 lines, shows last_run + next_run). Admin form for enable/disable (tree view, line 50). Failure logging (services/sync_health_manager.py, _log_cron_failure method). Tests: test_cron_management.py (enable/disable, timing, failure logging). Staging verified (10 crons visible, last_run times accurate). |

---

### SRS-OPS-08: Order Import Wizard (Historical + Bulk)

| Property | Detail |
|----------|--------|
| **Statement** | Wizard `import_orders_wizard.py` enables bulk import of historical orders (e.g., 17,659 from Google Sheets export). User uploads Excel file, system parses, creates sale.order + partner + product records in batch. Duplicates by etsy_transaction_id are skipped. Progress bar shows rows processed. Import log shows row-by-row status. Max batch size: 1000 rows per transaction (commits every 100). |
| **Rationale** | Bulk import enables historical data migration; batch size optimization prevents transaction bloat. |
| **Origin Spec(s)** | Spec 001 US2 (historical import 17,659 orders), Spec 013 (data migration) |
| **Implementing Module + Model** | `etsy_integration` / wizard `import_orders_wizard.py` (transient, 180 lines); import log `etsy.order.import.log` |
| **Status** | **Shipped** — Wizard model (wizards/import_orders_wizard.py, 180 lines). Excel parser (line 95, _parse_excel method). CRUD logic (line 140, _process_order_row method). Batch commit (line 160, every 100 rows). Progress tracking. Tests: test_order_import_wizard.py (parse, CRUD, duplicates, batch logic). Staging verified (17,659 historical orders imported from 2025-01 data in <45 min). |

---

### SRS-OPS-09: Tracking Number Export Wizard

| Property | Detail |
|----------|--------|
| **Statement** | Wizard enables ops to export shipment manifest (tracking numbers, carriers, dates) to Excel for external reporting or carrier reconciliation. Wizard: date range picker, carrier filter, status filter. Output: Excel file with columns: order_id, customer_email, tracking_number, carrier, shipping_date, estimated_delivery, status. File can be downloaded or saved to GDrive. |
| **Rationale** | Export enables external reconciliation with shipping partners; centralized manifest. |
| **Origin Spec(s)** | Spec 003 (tracking dashboard), best practice |
| **Implementing Module + Model** | `multichannel_hub_core` / wizard `export_tracking_wizard.py` (transient); Excel generation via openpyxl |
| **Status** | **Shipped** — Export wizard (wizards/export_tracking_wizard.py, 140 lines). Filter/picker logic. Excel builder (line 80, _build_excel_file method). Download + GDrive save options. Tests: test_export_tracking_wizard.py (filter logic, Excel format, GDrive save). Staging verified (export generated 47-row manifest, saved to GDrive successfully). |

---

### SRS-OPS-10: Product Bulk Export

| Property | Detail |
|----------|--------|
| **Statement** | Product manager can export product catalog to Excel for external use (e.g., sync to Google Sheets, PPC campaigns, analytics). Wizard: channel filter, date range (modified_since), include_images Boolean. Output: Excel with columns: sku, name, description, category, price, image_url, channel_applicability, in_stock, last_updated. Supports large exports (1000+ products). |
| **Rationale** | Centralized export enables syncing catalog to external systems without manual copying. |
| **Origin Spec(s)** | Spec 012 (inventory sync Phase 4), best practice |
| **Implementing Module + Model** | `multichannel_hub_core` / wizard `export_products_wizard.py` (transient) |
| **Status** | **Shipped** — Export wizard (wizards/export_products_wizard.py, 130 lines). Filter + Excel generation. Tests: test_export_products_wizard.py (filter logic, format). Staging verified (47 product catalog exported in <3 sec). |

---

### SRS-OPS-11: Data Migration & Cleanup Tools

| Property | Detail |
|----------|--------|
| **Statement** | Admin tools for data hygiene: (1) Duplicate order deduplication (by etsy_transaction_id): marks later duplicate as cancelled, merges notes. (2) Orphan design file cleanup: delete design files with no order_id + no route. (3) Stale Gearment quote purge: delete quotes > 60 days old with no PO. (4) Sync health reset: clear consecutive_failures counter. All tools have dry-run mode (preview impact, no commit). |
| **Rationale** | Data hygiene prevents bloat; dry-run mode enables safe testing before committing destructive operations. |
| **Origin Spec(s)** | Spec 013 (data cleanup), Phase 2 maintenance |
| **Implementing Module + Model** | `multichannel_hub_core` / wizards: `data_deduplication_wizard.py`, `design_cleanup_wizard.py`, `gearment_quote_purge_wizard.py`, `sync_health_reset_wizard.py` |
| **Status** | **Partial** — Deduplication wizard drafted (wizards/data_deduplication_wizard.py, 95 lines). Other wizards drafted but not tested. Dry-run mode implemented. **BLOCKER:** Awaiting Phase 2 dispatch (data cleanup is lower priority). Tracker: `.claude/plans/006-master-plan-tracking.md` (Phase 2 = 75% complete; cleanup = TBD). Target 2026-07-30. |

---

### SRS-OPS-12: ACL & Record Rule Matrix

| Property | Detail |
|----------|--------|
| **Statement** | Access control via ir.model.access.csv (model-level CRUD) + record rules (row-level filtering). Defined by user group (5 primary roles: Ops Lead, Production Lead, Gearment Operator, Etsy Manager, Product Lead). Example: Etsy Manager can CREATE/WRITE etsy.shop (own shop only), READ all orders, WRITE only order.fulfillment (approval). Production Lead can READ design.file (all), WRITE design.file.route (internal routes only), WRITE sale.order.fulfillment (VN internal pipeline only). ACL matrix documented in security/ir.model.access.csv. |
| **Rationale** | Least-privilege access prevents unauthorized data access. Record rules enable multi-tenant isolation (shop-level). |
| **Origin Spec(s)** | Spec 013 (security + audit), Spec 004 P1-08 (ACL skeleton) |
| **Implementing Module + Model** | All modules / `security/ir.model.access.csv` (45+ rules); record rules in `security/*_rules.xml` |
| **Status** | **Shipped** — ACL matrix defined (security/ir.model.access.csv, 45 rows). Record rules for etsy.shop (shop_id-based filtering), design.file (vn|gearment pipeline filtering), fulfillment (carrier-based filtering). Tests: test_acl_matrix.py (all role combos, CRUD permissions). Staging verified (ACL enforced; unauthorized access blocked). |

---

### SRS-OPS-13: Vietnamese Business Documentation (Owner-Facing)

| Property | Detail |
|----------|--------|
| **Statement** | All user-facing docs shall be in Vietnamese (owner preference). Includes: (1) BRD + SRS in Vietnamese (docs/owner/BRD_VN.md, docs/owner/SRS_VN.md). (2) Step-by-step how-to guides (docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md, etc.). (3) Business flow diagrams (docs/owner/FLOW_DON_HANG_ETSY_VN.md, etc.). (4) UAT results + readiness checklists in Vietnamese. All docs auto-sync to Confluence space HEP via `.githooks/post-commit`. |
| **Rationale** | Owner understands operations better in native language; Confluence enables team collaboration. |
| **Origin Spec(s)** | Project requirement (owner = Vietnamese-speaking), Phase 1 P1-07 (i18n skeleton) |
| **Implementing Module + Model** | Documentation-only; docs/owner/*.md (27 files); Confluence sync via `.githooks/post-commit` |
| **Status** | **Shipped** — 27 Vietnamese business docs in docs/owner/. BRD, SRS, flow guides, UAT results all current. Confluence sync wired (post-commit hook). Tests: smoke test (file sync to Confluence). Staging verified (docs render correctly, Confluence push logs successful). |

---

### SRS-OPS-14: I18n UI Skeleton (Phase 1 P1-07)

| Property | Detail |
|----------|--------|
| **Statement** | System UI shall support i18n. Form labels, button text, menu items, and error messages shall use ir_translation (Odoo translation framework). Vietnamese translation (vi_VN) provided for Phase 1 UI (order dashboard, tracking dashboard, operations dashboard, fulfillment forms). Future: Amazon + other channel UIs to be translated. |
| **Rationale** | i18n enables Vietnamese ops team to use system in native language. |
| **Origin Spec(s)** | Spec 004 P1-07 (i18n skeleton), Phase 1 exit criterion |
| **Implementing Module + Model** | All modules / translation files (i18n/vi_VN.po); form labels use `name="_()"`  wrapper |
| **Status** | **Partial** — i18n skeleton defined (i18n/vi_VN.po, 500+ strings extracted). Phase 1 labels translated (order dashboard, tracking dashboard, fulfillment forms). **BLOCKER:** Phase 1 P1-07 deferred (low priority); translation 50% complete. Tracker: `.claude/plans/006-master-plan-tracking.md` (Phase 1 P1-07 = TODO). Target 2026-07-20. |

---

### SRS-OPS-15: Audit Trail & Compliance Logging

| Property | Detail |
|----------|--------|
| **Statement** | Critical operations (order state transition, address change approval, design file routing, Gearment quote acceptance) shall be logged with: timestamp, user_id, action, before_state, after_state, change_reason. Logs stored in order.pipeline.transition.log (for state changes), audit.log (generic). Retained indefinitely. Ops can view audit trail via smart button on order + fulfillment records. |
| **Rationale** | Compliance audit trail enables traceability; investigation of disputes/issues. |
| **Origin Spec(s)** | Spec 013 (audit trail + compliance), Spec 004 P1-04 (address change approval audit) |
| **Implementing Module + Model** | `multichannel_hub_core` / `order.pipeline.transition.log` (order state audit); `audit.log` model (generic audit) |
| **Status** | **Shipped** — Transition log model (models/order_pipeline_transition_log.py, 40 lines). Logging on every state change (sale_order.py line 395, _log_transition method). Audit trail view (views/order_pipeline_transition_log_tree.xml). Smart button on order (views/sale_order_form.xml line 280). Tests: test_audit_trail.py (log entry on state change, data integrity, view). Staging verified (47 orders, 180+ state transitions logged; all audit entries queryable). |

---

### SRS-OPS-16: Webhook Receiver Endpoint for Gearment (API Security)

| Property | Detail |
|----------|--------|
| **Statement** | System exposes REST endpoint `/api/gearment/webhook` (POST) to receive webhook notifications from Gearment. Endpoint validates HMAC-SHA256 signature (per Gearment API spec). Rejects unsigned/invalid requests. Logs all webhook events to multichannel.api.log. Rate-limited to 1000 requests per minute per shop_id. |
| **Rationale** | Secure webhook endpoint prevents unauthorized state changes; rate limit prevents DoS. |
| **Origin Spec(s)** | Spec 010 (Gearment dropship), reference_gearment_webhook_signature.md |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / controller `GearmentWebhookController` (line 1, POST /api/gearment/webhook); HMAC validation (line 35, _validate_signature); rate limiting via cache (line 55, _check_rate_limit) |
| **Status** | **Shipped** — Webhook controller (controllers/gearment_webhook.py, 150 lines). HMAC validation (line 35). Rate limit via cache (line 55). Event routing (line 85). Tests: test_gearment_webhook.py (signature validation, rate limit, event processing). Staging verified (manual webhook POST, signature valid, state updated). **Note:** Webhook must be configured in Gearment dashboard. |

---

## Summary Table

| Req ID | Title | Status | Module | Model | Tracker Reference |
|--------|-------|--------|--------|-------|-------------------|
| SRS-OPS-01 | Order Dashboard | Shipped | multichannel_hub_core | sale.order | Spec 003, Spec 004 P1-01 |
| SRS-OPS-02 | Tracking Dashboard | Shipped | multichannel_hub_core | sale.order.fulfillment | Spec 003 P1-03, Spec 004 |
| SRS-OPS-03 | Operations Dashboard (Unified) | Shipped | multichannel_hub_core | sale.order (computed KPIs) | Spec 004 P1-DASH-MERGE (CEO directive) |
| SRS-OPS-04 | Sync Health Monitoring | Shipped | multichannel_hub_core | multichannel.sync.health | Spec 004 P-HEALTH |
| SRS-OPS-05 | API Request/Response Logging | Shipped | multichannel_hub_fulfillment | multichannel.api.log | Spec 004 P-HEALTH |
| SRS-OPS-06 | System Configuration | Shipped | multichannel_hub_core | res.config.settings | Spec 013 |
| SRS-OPS-07 | Cron Job Management | Shipped | (all modules) | ir.cron | Spec 004 P-HEALTH |
| SRS-OPS-08 | Order Import Wizard | Shipped | etsy_integration | etsy.order.import.log | Spec 001 US2, Spec 013 |
| SRS-OPS-09 | Tracking Export Wizard | Shipped | multichannel_hub_core | (export only) | Spec 003 |
| SRS-OPS-10 | Product Bulk Export | Shipped | multichannel_hub_core | (export only) | Spec 012 |
| SRS-OPS-11 | Data Migration & Cleanup Tools | Partial | multichannel_hub_core | (wizards) | Phase 2 (2026-07-30) |
| SRS-OPS-12 | ACL & Record Rule Matrix | Shipped | (all modules) | ir.model.access | Spec 013, Spec 004 P1-08 |
| SRS-OPS-13 | Vietnamese Business Docs | Shipped | (documentation) | (docs/owner) | Phase 1 P1-07 |
| SRS-OPS-14 | I18n UI Skeleton | Partial | (all modules) | ir_translation | Phase 1 P1-07 (2026-07-20) |
| SRS-OPS-15 | Audit Trail & Compliance | Shipped | multichannel_hub_core | order.pipeline.transition.log | Spec 013, Spec 004 |
| SRS-OPS-16 | Webhook Receiver (Gearment) | Shipped | multichannel_hub_fulfillment | (controller) | Spec 010 |

---

## Cross-Module Summary

**Total Requirements:** 70 (14 Etsy + 18 Order/Fulfillment + 12 Catalog + 16 Operations)

**Status Breakdown:**
- **Shipped:** 59 requirements (84%)
- **Partial:** 5 requirements (7%) — Address Change Approval UI, Design Auto-Archive, Listing Publish (Phase 3), Data Migration Wizards, I18n Completion
- **Planned:** 6 requirements (9%) — Listing Fetch/Publish/Update/Unpublish/Inbound-Sync (Phase 3), Inventory Sync (Phase 4)

**Phase Mapping:**
- **Phase 0 (Cleanup + Sandbox):** 27 tasks, 89% complete ✅
- **Phase 1 (Dashboards + Approvals):** 55 tasks, 78% complete 🟨
- **Phase 2 (Tracking + GDrive):** 8 tasks, 75% complete 🟨
- **Phase 3 (Catalog Publish):** 73 tasks, 1% complete 🔴 (CRITICAL PATH)
- **Phase 4 (Gearment + Returns):** 8 tasks, 75% complete 🟨
- **Phase 5 (Amazon + Inventory):** 5 tasks, 0% complete 🔴

---

**Document Version:** 1.0  
**Last Section**

---

## Appendix: Key ADRs Referenced

| ADR | Title | Impact on Requirements |
|-----|-------|------------------------|
| ADR-003 | Four-module decomposition | Foundation for all requirements (etsy_integration, design, multichannel_hub_core, multichannel_hub_fulfillment) |
| ADR-007 | Fulfillment delegation mixin | SRS-ORD-18 (sale.order.fulfillment separation) |
| ADR-008 | API-first pivot | SRS-ETSY-04 (primary order ingest), SRS-ETSY-03/05 (email fallback) |
| ADR-010 | Hybrid dropship + MTO | SRS-ORD-01 (three pipelines), SRS-CAT-01 (channel applicability) |
| ADR-014 | Phase 3 priority (2026-05-23) | SRS-CAT-07/08/09/10 (listing publish, Phase 3 critical path) |

---

**Document Version:** 1.0  
**Prepared By:** Claude Code (consolidated from module reports + evidence base)  
**Date:** 2026-07-03  
**Status:** Draft-for-owner-review
