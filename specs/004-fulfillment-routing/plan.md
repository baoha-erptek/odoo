# Implementation Plan: Fulfillment Routing, Production Assignment, and Partner Integration

**Branch**: `004-fulfillment-routing` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-fulfillment-routing/spec.md`

## Summary

After design files are approved (Spec 003), add fulfillment routing to direct orders to either external partners (with API sync for design files and tracking) or internal production (with stage tracking and material awareness). Primary partner is Gearment (API v3, multi-step draft/quote/confirm flow). Import tracking numbers from GKE Logistics Excel files with carrier auto-detection (USPS, UniUni, YunExpress). Google Drive sync for automated tracking file pickup. Also add CRM messaging foundation and returns workflow. This spec defines 7 new models (fulfillment.partner, partner.sync.log, order.return, shipping.carrier, logistics.partner, tracking.import.log, tracking.import.line), extends sale.order with routing and tracking import fields, and adds production queue, carrier config, and tracking import views.

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (sale_management, stock, contacts, mail), openpyxl, google-api-python-client, google-auth
**Storage**: PostgreSQL 16+ via Odoo ORM
**Testing**: Odoo TransactionCase, HttpCase
**Target Platform**: Linux Docker container (Odoo 19 CE)
**Project Type**: Odoo module extension (custom_addons/etsy_integration)
**Performance Goals**: Production queue responsive with 1000+ active orders, API sync completes within 30 seconds per order
**Constraints**: Odoo 19 CE only (no Enterprise features), must not break Spec 001/002/003 functionality
**Scale/Scope**: 17,659+ existing orders, 5-10 external partners, 5-15 production team users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Odoo-Native First | PASS | Using standard sale.order extensions, Odoo views, stock.quant for material visibility |
| II. Email Parser Isolation | PASS | No changes to email parser; routing is a separate concern |
| III. Data Integrity First | PASS | Routing is atomic (one active route per order), sync logs audit all API attempts |
| IV. Test-Driven Development | PASS | Tests required for routing logic, sync service, production stage transitions |
| V. Incremental Migration | PASS | This is Phase 4; each user story is independently deliverable |
| VI. Security by Default | PASS | Partner API credentials in ir.config_parameter; production team group reused from Spec 003 |
| VII. Simplicity Over Completeness | PASS | Simple stage field for production (not full MRP), manual routing (not automated rules) |

## Project Structure

### Documentation (this feature)

```text
specs/004-fulfillment-routing/
├── plan.md              # This file
├── research.md          # Phase 0: Research decisions
├── data-model.md        # Phase 1: Data model design
├── quickstart.md        # Phase 1: Quick verification guide
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2: Task list (/speckit-tasks)
```

### Source Code (repository root)

```text
custom_addons/etsy_integration/
├── models/
│   ├── sale_order.py              # MODIFY: Add routing, Gearment, and tracking import fields
│   ├── fulfillment_partner.py     # NEW: External partner config (priority, auth, adapter, rate limits)
│   ├── partner_sync_log.py        # NEW: API sync attempt audit log
│   ├── order_return.py            # NEW: Return/refund request model
│   ├── shipping_carrier.py        # NEW: Carrier config with tracking patterns
│   ├── logistics_partner.py       # NEW: Logistics partner with Google Drive config
│   ├── tracking_import_log.py     # NEW: Tracking import audit log
│   └── tracking_import_line.py    # NEW: Per-row tracking import detail
├── services/
│   ├── partner_sync.py            # NEW: Base adapter + adapter registry/factory
│   ├── gearment_adapter.py        # NEW: Gearment API v3 adapter (draft/quote/confirm)
│   ├── carrier_detector.py        # NEW: Carrier auto-detection from tracking patterns
│   ├── tracking_importer.py       # NEW: Excel parsing + order matching for tracking import
│   └── gdrive_client.py           # NEW: Google Drive file listing + download
├── controllers/
│   └── partner_webhook.py         # NEW: Webhook endpoint (generic + Gearment-specific)
├── views/
│   ├── fulfillment_partner_views.xml   # NEW: Partner config form/list
│   ├── production_queue_views.xml      # NEW: Internal production queue (list + kanban)
│   ├── partner_sync_log_views.xml      # NEW: Sync log list view
│   ├── order_return_views.xml          # NEW: Return request form/list
│   ├── shipping_carrier_views.xml      # NEW: Carrier config form/list
│   ├── tracking_import_views.xml       # NEW: Import log list/form + wizard view
│   ├── logistics_partner_views.xml     # NEW: Logistics partner config form/list
│   ├── sale_order_views.xml            # MODIFY: Add routing + tracking fields to order form
│   ├── operational_dashboard_views.xml # MODIFY: Add route/production/carrier filters
│   └── menu.xml                        # MODIFY: Add production queue, partner, carrier, import menus
├── security/
│   ├── etsy_security.xml          # MODIFY: Add record rules for new models
│   └── ir.model.access.csv        # MODIFY: Add ACL for 7 new models
├── data/
│   ├── ir_cron_partner_sync.xml   # NEW: Cron job for partner sync retry
│   ├── ir_cron_gdrive_sync.xml    # NEW: Cron job for Google Drive tracking sync
│   └── shipping_carrier_data.xml  # NEW: Pre-seeded carriers (USPS, UniUni, YunExpress)
├── wizards/
│   ├── return_wizard.py           # NEW: Return initiation wizard
│   └── tracking_import_wizard.py  # NEW: Upload tracking Excel file wizard
└── tests/
    ├── test_fulfillment_routing.py # NEW: Routing logic, constraints, auto-transitions
    ├── test_partner_sync.py        # NEW: API sync service, retry logic
    ├── test_gearment_adapter.py    # NEW: Gearment adapter (draft/quote/confirm flow)
    ├── test_production_queue.py    # NEW: Production stage transitions
    ├── test_order_return.py        # NEW: Return/refund workflow
    ├── test_tracking_import.py     # NEW: Excel import + order matching + carrier detection
    └── test_carrier_detection.py   # NEW: Carrier pattern matching tests
```

**Structure Decision**: Extend existing `etsy_integration` module. Seven new models (fulfillment.partner, partner.sync.log, order.return, shipping.carrier, logistics.partner, tracking.import.log, tracking.import.line), five new services (partner_sync, gearment_adapter, carrier_detector, tracking_importer, gdrive_client), one controller (webhook), two wizards, extended fields on sale.order.

## Complexity Tracking

No constitution violations. All features use standard Odoo patterns (model extensions, list/kanban views, security groups, cron jobs, HTTP controllers for webhooks). Gearment adapter adds moderate complexity (specific API contract, multi-step order flow, rate limiting) mitigated by adapter pattern isolating partner-specific logic. Google Drive adds external dependency (google-api-python-client) declared in requirements.txt. Tracking import reuses the proven wizard pattern from Spec 001's import_orders_wizard.
