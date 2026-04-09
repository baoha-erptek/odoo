# Implementation Plan: Operational Dashboard, Design File Workflow, Multi-Channel Foundation

**Branch**: `003-dashboard-design-multichannel` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-dashboard-design-multichannel/spec.md`

## Summary

Replace the Google Sheets-based order management workflow with an Odoo operational dashboard (21-column list view with inline editing), add design file upload and production team approval workflow (3-state: Pending/Approved/Needs Adjustment), and add a sales_channel field to future-proof for multi-channel (Amazon, WooCommerce) integration.

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (sale_management, stock, contacts, mail)
**Storage**: PostgreSQL 16+ via Odoo ORM
**Testing**: Odoo TransactionCase, HttpCase
**Target Platform**: Linux Docker container (Odoo 19 CE)
**Project Type**: Odoo module extension (custom_addons/etsy_integration)
**Performance Goals**: Dashboard loads in <3s with 17,000+ orders, server-side pagination (80 records/page)
**Constraints**: Odoo 19 CE only (no Enterprise features), must not break existing Spec 001/002 functionality
**Scale/Scope**: 17,659+ existing orders, 19 shops, 2,294 products, 5-15 production team users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Odoo-Native First | PASS | Using standard sale.order extensions, Odoo list/kanban views, ir.attachment for files |
| II. Email Parser Isolation | PASS | No changes to email parser; dashboard and design files are Odoo-only concerns |
| III. Data Integrity First | PASS | Design file approval is atomic; channel backfill migration is idempotent |
| IV. Test-Driven Development | PASS | Tests required for design file model, approval workflow, channel backfill |
| V. Incremental Migration | PASS | This is Phase 3 (dashboard + design), each user story is independently deliverable |
| VI. Security by Default | PASS | New group_production_team security group; ACL on order.design.file |
| VII. Simplicity Over Completeness | PASS | Channel field is minimal (Selection, not a full connector model). Design files use ir.attachment. |

## Project Structure

### Documentation (this feature)

```text
specs/003-dashboard-design-multichannel/
├── plan.md              # This file
├── research.md          # Phase 0: Research decisions
├── data-model.md        # Phase 1: Data model design
├── quickstart.md        # Phase 1: Quick verification guide
├── contracts/           # Phase 1: No external interfaces (Odoo-internal only)
├── checklists/          # Quality checklist
│   └── requirements.md
└── tasks.md             # Phase 2: Task list (/speckit-tasks)
```

### Source Code (repository root)

```text
custom_addons/etsy_integration/
├── models/
│   ├── sale_order.py              # MODIFY: Add operational dashboard fields, sales_channel, priority
│   ├── sale_order_line.py         # MODIFY: Add design_status computed field, product_type_id
│   └── order_design_file.py       # NEW: Design file model with approval workflow
├── views/
│   ├── operational_dashboard_views.xml  # NEW: 21-column list view + search filters
│   ├── order_design_file_views.xml      # NEW: Design file form/list in sale order
│   ├── etsy_design_queue_views.xml      # MODIFY: Add kanban view, approval status filters
│   ├── sale_order_views.xml             # MODIFY: Add design files tab to form
│   └── menu.xml                         # MODIFY: Add dashboard menu entry
├── security/
│   ├── etsy_security.xml          # MODIFY: Add group_production_team
│   └── ir.model.access.csv       # MODIFY: Add ACL for order.design.file
├── data/
│   └── channel_backfill.xml       # NEW: Post-init hook or migration to backfill sales_channel
└── tests/
    ├── test_design_file.py        # NEW: Design file CRUD, approval workflow
    ├── test_dashboard_fields.py   # NEW: Operational fields, channel backfill
    └── test_security.py           # NEW: Production team group access
```

**Structure Decision**: Extend existing `etsy_integration` module. One new model (`order.design.file`), extended fields on `sale.order` and `sale.order.line`, new views for dashboard and design workflow.

## Complexity Tracking

No constitution violations. All features use standard Odoo patterns (model extensions, list/kanban views, security groups, ir.attachment-based file storage).
