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
| **Implementing Module + Model** | `multichannel_hub_core` / view `operations_dashboard_views.xml` (merged unified dashboard, see SRS-OPS-03); computed fields on `sale.order` (`is_overdue_approval`, `stuck_route_badge`) |
| **Status** | **Shipped (merged into SRS-OPS-03)** — Delivered inside the unified Operations Dashboard (`views/operations_dashboard_views.xml`) per CEO directive 2026-05-03, not as a separate view file. List view with pipeline-stage column, saved filters (`data/operations_dashboard_saved_filters.xml`), decorations (red = `is_overdue_approval`, orange = `stuck_route_badge`). Export via standard Odoo list export. Tests: `test_order_dashboard.py`. **Not delivered as originally specced:** separate pivot view, bus.bus live update, dedicated export server action — if still wanted, belongs in the spec 015 backlog. |

---

### SRS-OPS-02: Tracking Dashboard & Real-Time Sync

| Property | Detail |
|----------|--------|
| **Statement** | Tracking Dashboard displays all orders with tracking numbers, grouped by carrier and delivery status. Real-time updates via bus.bus when fulfillment.tracking_number or tracking_state changes. Shows: carrier logo (from shipping.carrier icon field), tracking number (clickable deeplink via tracking_url), estimated delivery date, status badge (Label Requested, Shipped, Delivered). Filter by carrier, date range, state. Alert if tracking not updated > 7 days (stuck). |
| **Rationale** | Ops visibility into shipment pipeline; bus.bus enables instant customer query resolution. Stuck alerts catch fulfillment gaps. |
| **Origin Spec(s)** | Spec 003 P1-03 (tracking dashboard), Spec 004 P1-03 (fulfillment status) |
| **Implementing Module + Model** | `multichannel_hub_core` / view `operations_dashboard_views.xml` (merged unified dashboard, see SRS-OPS-03); `sale.order.fulfillment` (fields: `tracking_number`, `tracking_url`, `shipping_carrier_id`, `tracking_state`) |
| **Status** | **Shipped (merged into SRS-OPS-03)** — Delivered as tracking columns inside the unified Operations Dashboard list view (`views/operations_dashboard_views.xml`): `tracking_number`, `tracking_state` badge with per-state decorations (delivered/shipped/in_transit/returned). Tests: `test_tracking_dashboard.py`, `test_tracking_dashboard_db.py`. Tracking updates arrive asynchronously via Gearment webhook and tracking-import crons (5–15 min), **not** real-time bus.bus (no `_send_tracking_update_to_bus` exists). **Not delivered as originally specced:** kanban grouped by tracking_state, carrier icon display, bus.bus broadcast, dedicated stuck-alert (>7 days) decoration — spec 015 backlog candidates. |

---

### SRS-OPS-03: Operations Dashboard (CEO Directive, Unified)

| Property | Detail |
|----------|--------|
| **Statement** | Single unified Operations Dashboard combining order + tracking + inventory + design status. CEO directive 2026-05-03: one dashboard, not split. Shows: KPI tiles (today's orders, ready-to-ship count, overdue count, low-stock SKUs). Grid of status cards (VN internal production queue, Gearment processing, customer feedback pending). Quick-action buttons (Mark Picked, Request Quote, Approve Design, Export Tracking). Drill-down to detailed reports (list views). |
| **Rationale** | Unified view prevents ops context switching; KPI tiles enable rapid SLA assessment. One source of truth for exec reporting. |
| **Origin Spec(s)** | Spec 004 P1-DASH-MERGE (CEO directive 2026-05-03), Phase 1 P1-01 exit criterion |
| **Implementing Module + Model** | `multichannel_hub_core` / view `operations_dashboard_views.xml` (decorated list-view cockpit); computed fields on `sale.order` / `sale.order.line` (`is_overdue_approval`, `stuck_route_badge`, `tracking_state` related) |
| **Status** | **Shipped** — Unified dashboard (`views/operations_dashboard_views.xml`): list + search views over order lines with pipeline, design, shipping-service, and tracking columns; saved filters (`data/operations_dashboard_saved_filters.xml`); bulk "Mark Shipped" server action (`action_server_bulk_mark_shipped`). Delivered as a decorated list-view cockpit, **not** a KPI-tile widget layout — the KPI tile fields named in earlier drafts (today_order_count, ready_to_ship_count, low_stock_sku_count) were never implemented. Tests: `test_operations_dashboard_db.py`, `test_operations_dashboard_orm.py`, `test_operations_dashboard_line_*.py`, `test_dashboards_db.py`. |

---

### SRS-OPS-04: Sync Health Monitoring & Multi-Channel Observability

| Property | Detail |
|----------|--------|
| **Statement** | System shall track sync health for each data integration (Etsy API order fetch, email ingest, GKE tracking import, Gearment webhook, inventory sync). multichannel.sync.health model stores: last_sync_at, last_error (error message), consecutive_failures (counter), status (healthy|warning|unhealthy), recovery_action (auto-retry|manual_intervention|paused). Cron jobs increment failure counter on error; reset on success. Dashboard widget shows status of all integrations (green=healthy, yellow=warning, red=unhealthy). Threshold: 3 consecutive failures → warning; 5+ → unhealthy + alert. |
| **Rationale** | Observability into sync pipeline; early alert on integration failures prevents data gaps. Multi-channel sync status enables triage. |
| **Origin Spec(s)** | Spec 004 P-HEALTH (sync health monitoring), Spec 003 (tracking dashboard) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.sync.health` (fields: `channel_id` M2O, `metric_key` Char, `status` Selection, `last_run_at`/`last_success_at`/`last_error_at` Datetime, `last_error_message` Text, `rows_processed`/`rows_failed` Integer; `record()` upsert classmethod). Etsy channel additionally has its own `etsy.sync.health` (`etsy_integration/models/etsy_sync_health.py`). |
| **Status** | **Shipped (simpler shape than specced)** — Sync health models (`models/multichannel_sync_health.py`, `etsy_integration/models/etsy_sync_health.py`) record per-channel/per-metric checkpoints via `record()`, written by syncers and crons. Views: `views/multichannel_sync_health_views.xml`, `etsy_integration/views/etsy_sync_health_views.xml`. Tests: `test_phase1_sync_health_db.py`, `test_phase2_sync_health_orm.py`. **Not implemented as originally specced:** consecutive-failure counter, recovery_action field, threshold-based alert creation (no `_maybe_create_alert`), dedicated dashboard widget — status reflects last run only. Alerting escalation = spec 015 backlog candidate. |

---

### SRS-OPS-05: API Request & Response Logging (etsy.api.log / gearment.api.log)

| Property | Detail |
|----------|--------|
| **Statement** | External API calls to Etsy and Gearment shall be logged in per-channel log models (`etsy.api.log`, `gearment.api.log`) with endpoint, request/response payloads, status, and timestamps. Logs purged via retention crons. Used for debugging sync failures, API quota monitoring, and audit trail. GDrive/Gmail/ECB calls surface via sync-health checkpoints instead. |
| **Rationale** | API logs enable troubleshooting of integration failures; audit trail for compliance; quota monitoring prevents rate-limit surprises. |
| **Origin Spec(s)** | Spec 004 P-HEALTH (observability), Spec 013 (audit trail) |
| **Implementing Module + Model** | Per-channel log models, not one generic model: `etsy.api.log` (`etsy_integration/models/etsy_api_log.py`) and `gearment.api.log` (`multichannel_hub_fulfillment/models/gearment_api_log.py`) |
| **Status** | **Shipped (per-channel shape)** — Etsy calls logged to `etsy.api.log` (written by `etsy_api_client.py` / syncers); Gearment calls logged to `gearment.api.log` (written by the Gearment adapter/webhook dispatcher). Retention sweep cron `cron_etsy_api_log_cleanup` (`etsy_integration/data/ir_cron_data.xml`). There is **no** unified `multichannel.api.log` model; GDrive/Gmail/ECB calls are logged via sync-health checkpoints and `_logger`, not a dedicated API-log table. |

---

### SRS-OPS-06: System Configuration Parameters (ir.config_parameter)

| Property | Detail |
|----------|--------|
| **Statement** | System-wide settings shall be configurable via res.config.settings form (Odoo settings page). Parameters include: etsy_api_cron_interval (10 min default), email_ingest_cron_interval (10 min), gke_tracking_cron_interval (4 hours), gearment_quote_auto_fetch (Boolean), inventory_sync_interval (2 hours), smtp_rate_limit_per_minute (default 60), api_request_timeout_sec (default 30), gke_tracking_gdrive_folder_id, gearment_webhook_secret, ecb_currency_api_key. Form includes Help text explaining each parameter. |
| **Rationale** | Centralized config reduces code changes; enables ops tuning without deploy. |
| **Origin Spec(s)** | Spec 013 (system configuration), best practice |
| **Implementing Module + Model** | `etsy_integration` + `design` / `res.config.settings` extensions (`models/res_config_settings.py` + `views/res_config_settings_views.xml` in each); remaining knobs as raw `ir.config_parameter` keys (e.g. `multichannel_hub.large_file_threshold_bytes`, design auto-create toggle) |
| **Status** | **Shipped (subset)** — Settings-form extensions exist in `etsy_integration` and `design` (not `multichannel_hub_core`); hub/fulfillment tunables live as documented `ir.config_parameter` keys read at runtime. Cron intervals are tuned directly on the `ir.cron` records rather than via settings fields. Parameter set differs from the original draft list — see each module's `res_config_settings.py` for the authoritative fields. |

---

### SRS-OPS-07: Cron Job Management & Monitoring

| Property | Detail |
|----------|--------|
| **Statement** | System defines 10+ cron jobs (ir.cron records): order ingest (Etsy API + email), tracking import (GKE), tracking push (Etsy), Gearment webhook retry, currency rate sync, health monitor, api log purge, duplicate buyer recompute, overdue approval recompute, design file archival (deferred). Each cron has: name, model, method, interval_number, interval_type (minutes|hours|days). Admin can enable/disable cron via form button. Dashboard shows last run time + next run time for each cron. Cron failures logged to multichannel.sync.health. |
| **Rationale** | Centralized cron management enables ops to tune automation without code changes. Last-run dashboard enables quick diagnosis of sync gaps. |
| **Origin Spec(s)** | Spec 004 P-HEALTH (observability), best practice |
| **Implementing Module + Model** | `ir.cron` (Odoo core model), seeded across module data files: `etsy_integration/data/ir_cron_data.xml` + `ir_cron_currency_rates.xml`, `multichannel_hub_core/data/ir_cron_data.xml` + `product_catalog_cron.xml`, `multichannel_hub_fulfillment/data/logistics_partner_data.xml` |
| **Status** | **Shipped (standard tooling, no custom dashboard)** — 10+ cron jobs seeded across the module data files above (order sync 5 min, tracking push 5 min, email fetch 10 min, currency refresh, catalog sync, logistics inbox poll 15 min, API-log retention sweep, etc.). Enable/disable + last-run/next-run monitoring via standard Odoo Settings → Technical → Scheduled Actions. Failures surface through the sync-health checkpoints (SRS-OPS-04) and cron error logs. **Not implemented:** custom cron-monitor dashboard view (`cron_monitor_dashboard.xml` never existed). |

---

### SRS-OPS-08: Order Import Wizard (Historical + Bulk)

| Property | Detail |
|----------|--------|
| **Statement** | Wizard `import_orders_wizard.py` enables bulk import of historical orders (e.g., 17,659 from Google Sheets export). User uploads Excel file, system parses, creates sale.order + partner + product records in batch. Duplicates by etsy_transaction_id are skipped. Progress bar shows rows processed. Import log shows row-by-row status. Max batch size: 1000 rows per transaction (commits every 100). |
| **Rationale** | Bulk import enables historical data migration; batch size optimization prevents transaction bloat. |
| **Origin Spec(s)** | Spec 001 US2 (historical import 17,659 orders), Spec 013 (data migration) |
| **Implementing Module + Model** | `etsy_integration` / wizard `etsy.import.orders.wizard` (`wizards/import_orders_wizard.py`, transient) |
| **Status** | **Shipped** — Import wizard (`wizards/import_orders_wizard.py`): file upload, header mapping, row parsing, duplicate skip by transaction id, row-level issues recorded in the wizard's `validation_notes` (there is **no** separate `etsy.order.import.log` model). Tests: `test_import_wizard.py`, `test_import_wizard_headers.py`. Historical backlog remediation handled separately by `wizards/data_migration_wizard.py` (see SRS-OPS-11). |

---

### SRS-OPS-09: Tracking Number Export Wizard

| Property | Detail |
|----------|--------|
| **Statement** | Wizard enables ops to export shipment manifest (tracking numbers, carriers, dates) to Excel for external reporting or carrier reconciliation. Wizard: date range picker, carrier filter, status filter. Output: Excel file with columns: order_id, customer_email, tracking_number, carrier, shipping_date, estimated_delivery, status. File can be downloaded or saved to GDrive. |
| **Rationale** | Export enables external reconciliation with shipping partners; centralized manifest. |
| **Origin Spec(s)** | Spec 003 (tracking dashboard), best practice |
| **Implementing Module + Model** | (planned) `multichannel_hub_core` / wizard `export_tracking_wizard.py` (transient); Excel generation via openpyxl |
| **Status** | **Planned** — No `export_tracking_wizard.py` exists in any module. Interim: standard Odoo list export from the unified Operations Dashboard (tracking columns are exportable). Dedicated wizard with GDrive save = spec 015 backlog. |

---

### SRS-OPS-10: Product Bulk Export

| Property | Detail |
|----------|--------|
| **Statement** | Product manager can export product catalog to Excel for external use (e.g., sync to Google Sheets, PPC campaigns, analytics). Wizard: channel filter, date range (modified_since), include_images Boolean. Output: Excel with columns: sku, name, description, category, price, image_url, channel_applicability, in_stock, last_updated. Supports large exports (1000+ products). |
| **Rationale** | Centralized export enables syncing catalog to external systems without manual copying. |
| **Origin Spec(s)** | Spec 012 (inventory sync Phase 4), best practice |
| **Implementing Module + Model** | (planned) `multichannel_hub_core` / wizard `export_products_wizard.py` (transient) |
| **Status** | **Planned** — No `export_products_wizard.py` exists in any module. Interim: standard Odoo list export on product views. Dedicated catalog-export wizard = spec 015 backlog. |

---

### SRS-OPS-11: Data Migration & Cleanup Tools

| Property | Detail |
|----------|--------|
| **Statement** | Admin tools for data hygiene: (1) Duplicate order deduplication (by etsy_transaction_id): marks later duplicate as cancelled, merges notes. (2) Orphan design file cleanup: delete design files with no order_id + no route. (3) Stale Gearment quote purge: delete quotes > 60 days old with no PO. (4) Sync health reset: clear consecutive_failures counter. All tools have dry-run mode (preview impact, no commit). |
| **Rationale** | Data hygiene prevents bloat; dry-run mode enables safe testing before committing destructive operations. |
| **Origin Spec(s)** | Spec 013 (data cleanup), Phase 2 maintenance |
| **Implementing Module + Model** | `etsy_integration` / wizard `wizards/data_migration_wizard.py` (historical Etsy backlog remediation) |
| **Status** | **Partial (different shape than specced)** — The shipped tool is `etsy_integration/wizards/data_migration_wizard.py`: batched remediation of the historical order backlog with resumable iteration (`last_processed_id`), anomaly quarantine, per-batch `etsy.sync.health` checkpoints, fix helpers (financial config, shipping lines, prices-from-Excel, product config, confirm-and-complete), duplicate report generation + `action_apply_merges`. The four separately-named cleanup wizards from earlier drafts (`data_deduplication_wizard`, `design_cleanup_wizard`, `gearment_quote_purge_wizard`, `sync_health_reset_wizard`) do **not** exist. Remaining hygiene tools = spec 015 backlog. |

---

### SRS-OPS-12: ACL & Record Rule Matrix

| Property | Detail |
|----------|--------|
| **Statement** | Access control via ir.model.access.csv (model-level CRUD) + record rules (row-level filtering). Defined by user group (5 primary roles: Ops Lead, Production Lead, Gearment Operator, Etsy Manager, Product Lead). Example: Etsy Manager can CREATE/WRITE etsy.shop (own shop only), READ all orders, WRITE only order.fulfillment (approval). Production Lead can READ design.file (all), WRITE design.file.route (internal routes only), WRITE sale.order.fulfillment (VN internal pipeline only). ACL matrix documented in security/ir.model.access.csv. |
| **Rationale** | Least-privilege access prevents unauthorized data access. Record rules enable multi-tenant isolation (shop-level). |
| **Origin Spec(s)** | Spec 013 (security + audit), Spec 004 P1-08 (ACL skeleton) |
| **Implementing Module + Model** | All modules / `security/ir.model.access.csv` (~129 rows across the 4 modules: etsy_integration 44, multichannel_hub_core 65, multichannel_hub_fulfillment 16, design 4); record rules in each module's `security/*.xml` |
| **Status** | **Shipped** — ACL matrix defined across all four modules' `security/ir.model.access.csv`. Record rules include Etsy shop-scoped order access (`sale_order_etsy_shop_user_scope_rule`) and published-listing unlink protection (`rule_multichannel_listing_published_no_unlink`). Access enforcement is covered by scattered per-feature security assertions inside the module test suites rather than a single `test_acl_matrix.py` (which does not exist). |

---

### SRS-OPS-13: Vietnamese Business Documentation (Owner-Facing)

| Property | Detail |
|----------|--------|
| **Statement** | All user-facing docs shall be in Vietnamese (owner preference). Includes: (1) BRD + SRS in Vietnamese (docs/owner/BRD_VN.md, docs/owner/SRS_VN.md). (2) Step-by-step how-to guides (docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md, etc.). (3) Business flow diagrams (docs/owner/FLOW_DON_HANG_ETSY_VN.md, etc.). (4) UAT results + readiness checklists in Vietnamese. All docs auto-sync to Confluence space HEP via `.githooks/post-commit`. |
| **Rationale** | Owner understands operations better in native language; Confluence enables team collaboration. |
| **Origin Spec(s)** | Project requirement (owner = Vietnamese-speaking), Phase 1 P1-07 (i18n skeleton) |
| **Implementing Module + Model** | Documentation-only; docs/owner/*.md (22 files) + business-flow HTML pages (docs/owner/business-flows/); Confluence sync via `.githooks/post-commit` |
| **Status** | **Shipped** — 22 Vietnamese business docs in docs/owner/ plus the business-flows HTML set (v2). Flow guides and UAT material current. Confluence sync wired (post-commit hook, space HEP). |

---

### SRS-OPS-14: I18n UI Skeleton (Phase 1 P1-07)

| Property | Detail |
|----------|--------|
| **Statement** | System UI shall support i18n. Form labels, button text, menu items, and error messages shall use ir_translation (Odoo translation framework). Vietnamese translation (vi_VN) provided for Phase 1 UI (order dashboard, tracking dashboard, operations dashboard, fulfillment forms). Future: Amazon + other channel UIs to be translated. |
| **Rationale** | i18n enables Vietnamese ops team to use system in native language. |
| **Origin Spec(s)** | Spec 004 P1-07 (i18n skeleton), Phase 1 exit criterion |
| **Implementing Module + Model** | (planned) All modules / translation files (i18n/vi_VN.po) via the standard Odoo translation framework |
| **Status** | **Planned (not started)** — No `i18n/*.po` files exist in any custom module; no translation strings have been extracted. Some owner-facing surfaces (e.g. the `design` module's state labels) currently ship Vietnamese-first hardcoded strings instead of using the translation framework. Phase 1 P1-07 remains TODO in `.claude/plans/006-master-plan-tracking.md`. |

---

### SRS-OPS-15: Audit Trail & Compliance Logging

| Property | Detail |
|----------|--------|
| **Statement** | Critical operations (order state transition, address change approval, design file routing, Gearment quote acceptance) shall be logged with: timestamp, user_id, action, before_state, after_state, change_reason. Logs stored in order.pipeline.transition.log (for state changes), audit.log (generic). Retained indefinitely. Ops can view audit trail via smart button on order + fulfillment records. |
| **Rationale** | Compliance audit trail enables traceability; investigation of disputes/issues. |
| **Origin Spec(s)** | Spec 013 (audit trail + compliance), Spec 004 P1-04 (address change approval audit) |
| **Implementing Module + Model** | `multichannel_hub_core` / `order.pipeline.transition.log` (order state audit; O2M `pipeline_transition_log_ids` on `sale.order`); domain-specific audit models: `etsy.address.change.request`, `etsy.shop.source.change.log` (etsy_integration) |
| **Status** | **Shipped (per-domain shape)** — Pipeline state changes write an `order.pipeline.transition.log` row in the same transaction (`models/order_pipeline_transition_log.py`; `sale.order.pipeline_transition_log_ids` O2M surfaces them on the order's Pipeline tab). Address changes audited in `etsy.address.change.request`; shop source toggles in `etsy.shop.source.change.log`. Chatter/tracking covers remaining field-level history. Tests: `test_audit_chatter_orm.py`, `test_audit_coverage_db.py`. There is **no** generic `audit.log` model — auditing is per-domain by design. |

---

### SRS-OPS-16: Webhook Receiver Endpoint for Gearment (API Security)

| Property | Detail |
|----------|--------|
| **Statement** | System exposes REST endpoint `/gearment/webhook` (POST) to receive webhook notifications from Gearment. Endpoint validates HMAC-SHA256 signature (`X-Connect-Signature`, per Gearment API spec: url_path + nonce + timestamp + base64url(body)). Rejects unsigned/invalid requests. Audit-logs webhook events to `gearment.api.log`. |
| **Rationale** | Secure webhook endpoint prevents unauthorized state changes. |
| **Origin Spec(s)** | Spec 010 (Gearment dropship), reference_gearment_webhook_signature.md |
| **Implementing Module + Model** | `multichannel_hub_fulfillment` / controller `GearmentWebhookController` (`controllers/gearment_webhook.py`, POST `/gearment/webhook`, `auth='public'`, `csrf=False`); HMAC verification + event dispatch via the webhook dispatcher service |
| **Status** | **Shipped** — Webhook controller (`controllers/gearment_webhook.py`) with HMAC-SHA256 verification and per-request audit logging to `gearment.api.log`. Event routing via the dispatcher service. Tests: `test_webhook_discovery_db.py`/`_orm.py`, `test_webhook_dispatcher_db.py`/`_orm.py`. **Not implemented:** request rate limiting (deliberate — invalid signatures are logged and rejected; no rate-limit layer). **Note:** Webhook must be configured in Gearment dashboard. |

---

## Summary Table

| Req ID | Title | Status | Module | Model | Tracker Reference |
|--------|-------|--------|--------|-------|-------------------|
| SRS-OPS-01 | Order Dashboard | Shipped (merged into OPS-03) | multichannel_hub_core | sale.order | Spec 003, Spec 004 P1-01 |
| SRS-OPS-02 | Tracking Dashboard | Shipped (merged into OPS-03) | multichannel_hub_core | sale.order.fulfillment | Spec 003 P1-03, Spec 004 |
| SRS-OPS-03 | Operations Dashboard (Unified) | Shipped | multichannel_hub_core | sale.order / sale.order.line | Spec 004 P1-DASH-MERGE (CEO directive) |
| SRS-OPS-04 | Sync Health Monitoring | Shipped | multichannel_hub_core + etsy_integration | multichannel.sync.health, etsy.sync.health | Spec 004 P-HEALTH |
| SRS-OPS-05 | API Request/Response Logging | Shipped | etsy_integration + multichannel_hub_fulfillment | etsy.api.log, gearment.api.log | Spec 004 P-HEALTH |
| SRS-OPS-06 | System Configuration | Shipped (subset) | etsy_integration + design | res.config.settings | Spec 013 |
| SRS-OPS-07 | Cron Job Management | Shipped | (all modules) | ir.cron | Spec 004 P-HEALTH |
| SRS-OPS-08 | Order Import Wizard | Shipped | etsy_integration | etsy.import.orders.wizard | Spec 001 US2, Spec 013 |
| SRS-OPS-09 | Tracking Export Wizard | Planned | multichannel_hub_core | (export only) | Spec 003 |
| SRS-OPS-10 | Product Bulk Export | Planned | multichannel_hub_core | (export only) | Spec 012 |
| SRS-OPS-11 | Data Migration & Cleanup Tools | Partial | etsy_integration | data_migration_wizard | Phase 2 (2026-07-30) |
| SRS-OPS-12 | ACL & Record Rule Matrix | Shipped | (all modules) | ir.model.access | Spec 013, Spec 004 P1-08 |
| SRS-OPS-13 | Vietnamese Business Docs | Shipped | (documentation) | (docs/owner) | Phase 1 P1-07 |
| SRS-OPS-14 | I18n UI Skeleton | Planned | (all modules) | ir_translation | Phase 1 P1-07 (2026-07-20) |
| SRS-OPS-15 | Audit Trail & Compliance | Shipped | multichannel_hub_core + etsy_integration | order.pipeline.transition.log + per-domain audit models | Spec 013, Spec 004 |
| SRS-OPS-16 | Webhook Receiver (Gearment) | Shipped | multichannel_hub_fulfillment | (controller /gearment/webhook) | Spec 010 |

---

## Cross-Module Summary

**Total Requirements:** 70 (14 Etsy + 18 Order/Fulfillment + 12 Catalog + 16 Operations)

**Status Breakdown** (updated 2026-07-04 after code-drift audit):
- **Shipped:** 56 requirements (80%)
- **Partial:** 4 requirements (6%) — Address Change Approval UI, Design Auto-Archive, Listing Publish (Phase 3), Data Migration/Cleanup Tools
- **Planned:** 10 requirements (14%) — Listing Fetch/Publish/Update/Unpublish/Inbound-Sync (Phase 3), Inventory Sync (Phase 4), Tracking Export Wizard, Product Bulk Export, I18n UI Skeleton

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
