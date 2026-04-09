# Implementation Plan: Fulfillment Routing, Production Assignment, and Partner Integration

**Branch**: `004-fulfillment-routing` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-fulfillment-routing/spec.md`

## Summary

After design files are approved (Spec 003), add fulfillment routing to direct orders to either external partners (with API sync for design files and tracking) or internal production (with stage tracking and material awareness). Also add CRM messaging foundation and returns workflow. This spec defines 3 new models (fulfillment.partner, partner.sync.log, order.return), extends sale.order with routing fields, and adds production queue views.

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (sale_management, stock, contacts, mail)
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
│   ├── sale_order.py              # MODIFY: Add routing fields (fulfillment_partner_id, fulfillment_route, production_stage)
│   ├── fulfillment_partner.py     # NEW: External partner configuration model
│   ├── partner_sync_log.py        # NEW: API sync attempt audit log
│   └── order_return.py            # NEW: Return/refund request model
├── services/
│   └── partner_sync.py            # NEW: Partner API sync service (push files, receive callbacks)
├── controllers/
│   └── partner_webhook.py         # NEW: Webhook endpoint for partner callbacks
├── views/
│   ├── fulfillment_partner_views.xml   # NEW: Partner config form/list
│   ├── production_queue_views.xml      # NEW: Internal production queue (list + kanban)
│   ├── partner_sync_log_views.xml      # NEW: Sync log list view
│   ├── order_return_views.xml          # NEW: Return request form/list
│   ├── sale_order_views.xml            # MODIFY: Add routing fields to order form
│   ├── operational_dashboard_views.xml # MODIFY: Add route/production filters
│   └── menu.xml                        # MODIFY: Add production queue and partner menus
├── security/
│   ├── etsy_security.xml          # MODIFY: Add record rules for partner sync logs
│   └── ir.model.access.csv        # MODIFY: Add ACL for new models
├── data/
│   └── ir_cron_partner_sync.xml   # NEW: Cron job for partner sync retry
├── wizards/
│   └── return_wizard.py           # NEW: Return initiation wizard
└── tests/
    ├── test_fulfillment_routing.py # NEW: Routing logic, constraints, auto-transitions
    ├── test_partner_sync.py        # NEW: API sync service, retry logic
    ├── test_production_queue.py    # NEW: Production stage transitions
    └── test_order_return.py        # NEW: Return/refund workflow
```

**Structure Decision**: Extend existing `etsy_integration` module. Three new models (fulfillment.partner, partner.sync.log, order.return), one new service (partner_sync), one new controller (webhook), extended fields on sale.order.

## Complexity Tracking

No constitution violations. All features use standard Odoo patterns (model extensions, list/kanban views, security groups, cron jobs, HTTP controllers for webhooks).
