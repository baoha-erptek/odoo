# Tasks: Operational Dashboard, Design File Workflow, Multi-Channel Foundation

> **FROZEN — SUPERSEDED by Master Plan 006** (owner sign-off 2026-04-13)
>
> This tasks.md is **not authoritative**. It describes a single-dashboard design that was rewritten after end-user feedback identified three distinct dashboards (Order / Tracking / Process), an address-change approval workflow, image + row-decoration requirements, and the need for a `sale.order.fulfillment` delegation mixin before any Phase 3-era field is added to `sale.order`.
>
> **Do not execute tasks from this file.** Spec 003 will be regenerated via `/speckit-specify` in Wave B of master-plan execution. Dependencies to apply to the rewrite:
> - [ADR-003](../006-master-plan/adrs/ADR-003-module-decomposition.md) — four-module split; dashboards/mixin land in `multichannel_hub_core`
> - [ADR-004](../006-master-plan/adrs/ADR-004-enterprise-alternatives.md) — custom `etsy.address.change.request`, design-file workflow without `documents` Enterprise
> - [ADR-005](../006-master-plan/adrs/ADR-005-carrier-unification.md) — `sale.order.shipping_carrier` Char → `shipping_carrier_id` M2O on `shipping.carrier`
> - [ADR-006](../006-master-plan/adrs/ADR-006-design-file-storage.md) — filestore/URL only, 10 MB cap; seed historical from `DESIGN_LINK_FRONT`/`BACK`
> - [ADR-007](../006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md) — fulfillment fields move to `sale.order.fulfillment` delegation sibling
>
> **Original (superseded) content preserved below for reference.**

---

**Input**: Design documents from `/specs/003-dashboard-design-multichannel/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md
**Blocking Dependency**: Review `specs/004-fulfillment-routing/data-model.md` before Phase 2 to ensure design approval -> fulfillment routing handoff is coherent

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Module structure and foundational model

- [ ] T001 Update __manifest__.py with new model (order.design.file) and new data/view/security files in `custom_addons/etsy_integration/__manifest__.py`
- [ ] T002 Register order_design_file model in `custom_addons/etsy_integration/models/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core model and security that ALL user stories depend on

- [ ] T003 Create order.design.file model with all fields (name, sale_order_id, sale_line_id, design_file, design_filename, preview_file, preview_filename, file_type, approval_status, approved_by, approval_date, rejection_note) inheriting mail.thread in `custom_addons/etsy_integration/models/order_design_file.py`
- [ ] T004 [P] Add design approval constraint: rejection_note required when approval_status='can_chinh_lai' in `custom_addons/etsy_integration/models/order_design_file.py`
- [ ] T005 [P] Add auto-set logic: approved_by and approval_date populated on write when status changes to 'duyet' in `custom_addons/etsy_integration/models/order_design_file.py`
- [ ] T006 [P] Add group_production_team security group under Etsy Integration module category in `custom_addons/etsy_integration/security/etsy_security.xml`
- [ ] T007 [P] Add ACL rules for order.design.file: full CRUD for production team + manager, read+create for salesman in `custom_addons/etsy_integration/security/ir.model.access.csv`
- [ ] T008 Add operational dashboard fields to sale.order: shipping_date, tracking_number, shipping_carrier, shipping_label_status, fulfillment_status, fulfillment_note, pic_user_id, order_priority in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T009 [P] Add multi-channel fields to sale.order: sales_channel (Selection: etsy/amazon/website/other), channel_order_ref (Char) in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T010 [P] Add computed fields to sale.order: design_file_ids (One2many), design_file_count (Integer), has_pending_designs (Boolean) in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T011 [P] Add fields to sale.order.line: design_file_ids (One2many), design_status (Selection, computed from files), product_type_id (Many2one to product.category) in `custom_addons/etsy_integration/models/sale_order_line.py`
- [ ] T012 Verify module installs cleanly with `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init`

**Checkpoint**: Foundation models and security ready. All user stories can proceed.

---

## Phase 3: User Story 1 - Operational Order Dashboard (Priority: P1)

**Goal**: Replace Google Sheets with a 21-column operational list view with inline editing for fulfillment fields

**Independent Test**: Open dashboard, verify 21 columns visible, inline-edit columns A-F, filter by status/shop/PIC

### Implementation for User Story 1

- [ ] T013 [US1] Create operational dashboard list view (tree editable="top") with 21 columns: 6 editable fulfillment fields + 15 read-only order fields in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T014 [US1] Create search view with filters: fulfillment_status, sales_channel, pic_user_id, etsy_shop_id, order_priority, shipping_label_status, date range in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T015 [US1] Create group-by options: shop, channel, PIC, priority, fulfillment status in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T016 [US1] Add window action and menu item for Operational Dashboard under Etsy Integration menu in `custom_addons/etsy_integration/views/menu.xml`
- [ ] T017 [US1] Add database indexes on sale_order for: fulfillment_status, sales_channel, pic_user_id, order_priority in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T018 [US1] Write test: verify dashboard fields exist and are writable on sale.order in `custom_addons/etsy_integration/tests/test_dashboard_fields.py`

**Checkpoint**: Operational dashboard functional with all 21 columns and inline editing

---

## Phase 4: User Story 2 - Design File Upload and Preview (Priority: P1)

**Goal**: Upload design files and preview images to sale order lines

**Independent Test**: Upload design file + preview to order line, verify storage and download

### Implementation for User Story 2

- [ ] T019 [US2] Create design file form view (file upload, preview display, approval fields) in `custom_addons/etsy_integration/views/order_design_file_views.xml`
- [ ] T020 [US2] Create design file tree view (list within sale order) in `custom_addons/etsy_integration/views/order_design_file_views.xml`
- [ ] T021 [US2] Add "Design Files" tab to sale.order form view with One2many to order.design.file in `custom_addons/etsy_integration/views/sale_order_views.xml`
- [ ] T022 [US2] Add design file count badge on sale order form (design_file_count) in `custom_addons/etsy_integration/views/sale_order_views.xml`
- [ ] T023 [US2] Add has_design_files visual indicator to design queue list view in `custom_addons/etsy_integration/views/etsy_design_queue_views.xml`
- [ ] T024 [US2] Write test: create design file, verify file storage, verify One2many relation in `custom_addons/etsy_integration/tests/test_design_file.py`

**Checkpoint**: Design files can be uploaded, previewed, and downloaded per order line

---

## Phase 5: User Story 3 - Design Approval Workflow (Priority: P1)

**Goal**: Production team reviews and approves/rejects design files with 3-state workflow

**Independent Test**: Set approval status on design files, verify constraints, filter design queue by status

### Implementation for User Story 3

- [ ] T025 [US3] Create kanban view for design queue with 3 columns: Cho duyet, Duyet, Can chinh lai in `custom_addons/etsy_integration/views/etsy_design_queue_views.xml`
- [ ] T026 [US3] Update design queue search view with filters for approval_status in `custom_addons/etsy_integration/views/etsy_design_queue_views.xml`
- [ ] T027 [US3] Add approval status change buttons (Approve / Request Adjustment) on design file form in `custom_addons/etsy_integration/views/order_design_file_views.xml`
- [ ] T028 [US3] Implement action_approve() and action_request_adjustment() methods on order.design.file with group check in `custom_addons/etsy_integration/models/order_design_file.py`
- [ ] T029 [US3] Add record rule: only group_production_team and group_sale_manager can write approval_status on order.design.file in `custom_addons/etsy_integration/security/etsy_security.xml`
- [ ] T030 [US3] Write test: approval workflow (approve sets user+date, reject requires note, non-production user cannot approve) in `custom_addons/etsy_integration/tests/test_design_file.py`
- [ ] T031 [US3] Write test: design_status computed field on sale.order.line reflects least-approved file in `custom_addons/etsy_integration/tests/test_design_file.py`

**Checkpoint**: Design approval workflow fully functional with security enforcement

---

## Phase 6: User Story 4 - Multi-Channel Foundation (Priority: P2)

**Goal**: Tag all orders with sales_channel, backfill existing Etsy orders

**Independent Test**: Verify existing orders show "Etsy" channel, filter dashboard by channel

### Implementation for User Story 4

- [ ] T032 [US4] Create post_init_hook or data migration to backfill sales_channel='etsy' and channel_order_ref=etsy_order_id on existing orders in `custom_addons/etsy_integration/data/channel_backfill.py`
- [ ] T033 [US4] Register post_init_hook in __manifest__.py in `custom_addons/etsy_integration/__manifest__.py`
- [ ] T034 [US4] Update order_creator.py to set sales_channel='etsy' and channel_order_ref=etsy_order_id when creating orders from email in `custom_addons/etsy_integration/services/order_creator.py`
- [ ] T035 [US4] Add sales_channel field to operational dashboard list and search views in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T036 [US4] Write test: verify backfill sets sales_channel and channel_order_ref on existing Etsy orders in `custom_addons/etsy_integration/tests/test_dashboard_fields.py`
- [ ] T037 [US4] Write test: verify backfill is idempotent (running twice produces same result) in `custom_addons/etsy_integration/tests/test_dashboard_fields.py`

**Checkpoint**: All orders tagged with sales channel, dashboard supports channel filtering

---

## Phase 7: User Story 5 - Order Priority and Sorting (Priority: P2)

**Goal**: Assign priority levels to orders and sort dashboard by priority

**Independent Test**: Set priority on orders, sort dashboard by priority, verify urgent orders first

### Implementation for User Story 5

- [ ] T038 [US5] Add priority column to operational dashboard list view with optional decoration (color/bold for urgent) in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T039 [US5] Add default_order="order_priority desc, date_order desc" to dashboard action in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T040 [US5] Write test: verify priority default is 'normal' for new orders, verify sort order in `custom_addons/etsy_integration/tests/test_dashboard_fields.py`

**Checkpoint**: Orders sortable and filterable by priority

---

## Phase 8: User Story 6 - Fulfillment Status Tracking (Priority: P2)

**Goal**: Track orders through fulfillment stages with status filters

**Independent Test**: Change fulfillment status through stages, verify dashboard filters per status

### Implementation for User Story 6

- [ ] T041 [US6] Add fulfillment_status column to dashboard list with decoration_info/danger/success for visual status badges in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T042 [US6] Add statusbar widget for fulfillment_status on sale.order form view in `custom_addons/etsy_integration/views/sale_order_views.xml`
- [ ] T043 [US6] Write test: verify all 7 fulfillment statuses are selectable and filterable in `custom_addons/etsy_integration/tests/test_dashboard_fields.py`

**Checkpoint**: Fulfillment status tracking fully operational on dashboard and form

---

## Phase 9: User Story 7 - Label Status Management (Priority: P3)

**Goal**: Track shipping label status per order

**Independent Test**: Set label status, filter by "need label", verify filter results

### Implementation for User Story 7

- [ ] T044 [US7] Add shipping_label_status column to dashboard list view in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T045 [US7] Add shipping_label_status filter to dashboard search view in `custom_addons/etsy_integration/views/operational_dashboard_views.xml`
- [ ] T046 [US7] Write test: verify label status selection values and default in `custom_addons/etsy_integration/tests/test_dashboard_fields.py`

**Checkpoint**: Label status tracking complete

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, verification, module update

- [ ] T047 Run full module update and verify no XML/Python errors: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init`
- [ ] T048 [P] Run ruff check on all modified/new Python files: `ruff check custom_addons/etsy_integration/`
- [ ] T049 [P] Run full test suite: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init`
- [ ] T050 Execute quickstart.md verification steps end-to-end
- [ ] T051 Verify dashboard performance with 17,000+ orders using load test script: open dashboard with 3 filters applied (shop + status + priority), verify page load < 3 seconds, verify inline edit response < 1 second
- [ ] T052 [P] Add file size validation constraint on order.design.file: reject uploads exceeding 10MB with clear error message in `custom_addons/etsy_integration/models/order_design_file.py`
- [ ] T053 [P] Update __manifest__.py version to 19.0.2.0.0

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 -- BLOCKS all user stories
- **US1 Dashboard (Phase 3)**: Depends on Phase 2
- **US2 File Upload (Phase 4)**: Depends on Phase 2 (independent of US1)
- **US3 Approval (Phase 5)**: Depends on Phase 2 + US2 (needs design files to exist)
- **US4 Multi-Channel (Phase 6)**: Depends on Phase 2 (independent of US1-3)
- **US5 Priority (Phase 7)**: Depends on US1 (dashboard must exist for column)
- **US6 Fulfillment Status (Phase 8)**: Depends on US1 (dashboard must exist)
- **US7 Label Status (Phase 9)**: Depends on US1 (dashboard must exist)
- **Polish (Phase 10)**: Depends on all desired user stories complete

### User Story Dependencies

```
Phase 2 (Foundation)
  |
  +-- US1 (Dashboard) ----+-- US5 (Priority)
  |                        +-- US6 (Fulfillment Status)
  |                        +-- US7 (Label Status)
  |
  +-- US2 (File Upload) --+-- US3 (Approval Workflow)
  |
  +-- US4 (Multi-Channel) -- independent
```

### Parallel Opportunities

**After Phase 2 completes, these can run in parallel:**
- US1 (Dashboard views) + US2 (Design file model/views) + US4 (Channel backfill)

**Within each story, [P] tasks run in parallel:**
- T004, T005 (model constraints in same file but independent logic)
- T006, T007 (security XML and CSV)
- T009, T010, T011 (different model files)

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 1-2: Setup + Foundation
2. Complete US1: Operational Dashboard (replace Google Sheets)
3. Complete US2 + US3: Design file upload + approval workflow
4. **STOP and VALIDATE**: Team can start using Odoo for daily operations
5. Deploy to production

### Incremental Delivery

1. Foundation -> Dashboard (MVP!) -> Test with team
2. Add Design Files + Approval -> Deploy
3. Add Multi-Channel field -> Deploy
4. Add Priority + Fulfillment Status + Label Status -> Deploy
5. Each increment adds value without breaking previous functionality

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 53 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundation) | 10 |
| US1 (Dashboard) | 6 |
| US2 (File Upload) | 6 |
| US3 (Approval) | 7 |
| US4 (Multi-Channel) | 6 |
| US5 (Priority) | 3 |
| US6 (Fulfillment) | 3 |
| US7 (Label) | 3 |
| Polish | 7 |
| Parallel opportunities | 15 tasks marked [P] |
| Test tasks | 10 (embedded in story phases) |

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP scope: US1 + US2 + US3 (dashboard + design files + approval)
