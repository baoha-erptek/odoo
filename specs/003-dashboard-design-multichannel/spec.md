# Feature Specification: Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation

**Feature Branch**: `003-dashboard-design-multichannel`
**Created**: 2026-04-06 (v1), rewritten 2026-04-13 after master-plan review
**Status**: Draft (Wave B — pending plan.md + data-model.md refresh)
**Supersedes**: `_archive/spec-2026-04-06.md`
**Authority**: [master plan 006](../006-master-plan/MASTER_PLAN.md), ADRs [003](../006-master-plan/adrs/ADR-003-module-decomposition.md) [004](../006-master-plan/adrs/ADR-004-enterprise-alternatives.md) [005](../006-master-plan/adrs/ADR-005-carrier-unification.md) [006](../006-master-plan/adrs/ADR-006-design-file-storage.md) [007](../006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md)
**Input**: Replace the Google Sheet (BA/PD/MP/Audit tabs) with a coherent set of role-specific Odoo dashboards, ship the safety-critical address-change approval workflow, formalise the design file + 3-state approval flow, and lay a multi-channel foundation that Amazon / Website channels can plug into without schema churn.

---

## What changed vs the 2026-04-06 version

1. **Three dashboards, not one**: end-user feedback from BA, PD, and MP explicitly asked for distinct Order / Tracking / Process views with different columns, filters, and default sorts. Trying to serve all three roles from a single 21-column list was the original spec's scope miss.
2. **Address-change approval workflow added (P1, safety-critical)**: BA flagged that Marketing currently edits shipping addresses directly on `sale.order`, occasionally after a label has already been purchased. Duplicate-label spend is a recurring, unauditable incident. Requires a gated `etsy.address.change.request` model with BA approval.
3. **Product images + row decorations**: Marketing asked twice for `image_128` in list views and for colour-coded rows (qty≥2, duplicate buyer, Push order, Amazon order).
4. **Fulfillment-lifecycle fields live on a delegation sibling** (`sale.order.fulfillment`, ADR-007), not directly on `sale.order`. Prevents god-object bloat as specs 004a/004b/005 add fields.
5. **Unified carrier via `shipping.carrier`** (ADR-005) — the original spec's `shipping_carrier` Char is gone.
6. **Design-file storage policy codified** (ADR-006): 10 MB cap, URL-mode for large files, filestore only.
7. **Vietnamese UI + audit log elevated to explicit FRs** — previously implicit, now cross-cutting requirements.

## Clarifications captured from end-user feedback review (2026-04-10)

- Q: Should the three dashboards share a single data model or back each one with a separate report view? → A: Same data model; three saved views (`ir.actions.act_window`) with different column sets, default filters, and decorations.
- Q: Are PD's 18 columns a subset/superset of BA's Order dashboard? → A: Overlap but not subset; Process dashboard adds production stage + block reason + PD note and hides financial/MP columns.
- Q: Does the address-change workflow freeze ALL shipping fields or just the destination address? → A: All destination address fields (partner_shipping_id, street, street2, city, zip, state_id, country_id). Carrier + tracking remain editable because ops may still need to cancel a bought label.
- Q: On failed edits during a pending address change, do we block at UI level, ORM level, or both? → A: Both — `readonly` attrs on the form (UI hint) AND a server-side `@api.constrains` on `sale.order` write (hard enforcement).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Order Dashboard for BA daily triage (Priority: P1)

As a BA team member, I need a single list view that shows every order's commercial state (channel, shop, buyer, price, discount, MP note, PIC, overdue-approval flag) with product thumbnails and row-level colour cues, so I can triage hundreds of orders per day without opening each one.

**Why this priority**: The BA team is the largest daily consumer of the Google Sheet. Until this view lands, Odoo is a secondary system and the team keeps the sheet alive — defeating the whole project.

**Independent Test**: Open the Order Dashboard with 17K+ orders. Verify the first page renders in <3 s. Verify the product image column shows `image_128` inline. Verify a qty≥2 order shows the expected row decoration. Inline-edit the MP note, PIC, and priority on three arbitrary rows and confirm persistence after reload.

**Acceptance Scenarios**:

1. **Given** an authenticated BA user, **When** they open the Order Dashboard, **Then** the list shows at minimum: product image (thumbnail), shop, channel, order date, buyer, country, amount (in shop currency), discount flag, PIC, priority, MP note, design-status summary, overdue-approval marker, and tracking state.
2. **Given** an order with `product_uom_qty >= 2` on any line, **When** rendered, **Then** the row is decorated (e.g., `decoration-info`) so qty-multi orders stand out.
3. **Given** two orders from the same buyer in the last 7 days, **When** rendered, **Then** both rows carry a "duplicate buyer" decoration.
4. **Given** an order flagged Push by the store manager, **When** rendered, **Then** a dedicated avatar/icon column shows the store manager, and the row has a `decoration-danger` (Push) variant distinct from Urgent priority.
5. **Given** an order whose design-approval activity is >24 h overdue, **When** rendered, **Then** the overdue-approval marker column shows a warning glyph and the row sorts to the top of the "Overdue" saved filter.
6. **Given** 17,000+ orders exist, **When** the dashboard opens, **Then** the server-side paginated view returns the first 80 rows within 3 s without loading all records.
7. **Given** the BA user edits the MP note, PIC, or priority inline, **When** they leave the cell, **Then** the change saves and a chatter entry is recorded on the order (audit).

---

### User Story 2 — Tracking Dashboard for shipping ops (Priority: P1)

As a BA-shipping team member, I need a dedicated view focused on tracking + carrier + label state, with bulk actions to change state across many rows and with search by tracking number, so I can reconcile daily shipments from GKE and push batches of statuses efficiently.

**Why this priority**: Tracking reconciliation is the single biggest daily pain after order triage. BA's current workflow is: copy-paste tracking from GKE Excel into the sheet, then manually toggle label state per row. Without a dedicated Odoo view, this workflow stays in the sheet.

**Independent Test**: Open the Tracking Dashboard. Verify columns match BA's expected set (buyer, shop, tracking number, carrier, shipping date, label status, tracking state, has-pending-address-change flag). Enter a tracking number in the search box and confirm the row filters correctly. Select 10 rows and apply a bulk state change; verify all 10 update atomically.

**Acceptance Scenarios**:

1. **Given** the Tracking Dashboard, **When** rendered, **Then** the columns are: buyer, shop, channel, tracking number, carrier, shipping date, label status, tracking state (merged column: none/label-requested/label-ready/shipped/in-transit/delivered), has-pending-address-change flag, overdue-approval marker.
2. **Given** a tracking number typed in the search box, **When** the user presses Enter, **Then** the list filters to rows whose tracking number contains the query (case-insensitive, indexed lookup).
3. **Given** ≥2 selected rows, **When** the user invokes "Bulk → Mark shipped", **Then** all selected rows transition atomically, chatter is updated on each, and any row with `has_pending_address_change == True` is skipped with an on-screen warning.
4. **Given** an export request, **When** the user clicks "Export to Excel", **Then** the current filtered set is exported with columns matching the GKE import format so a round-trip is trivial.
5. **Given** an import of a GKE tracking Excel (delegated to Spec 004a), **When** it completes, **Then** the Tracking Dashboard reflects the newly-written tracking numbers within 5 minutes and the same rows visible in the Order Dashboard also show the updated state.

---

### User Story 3 — Process Dashboard for Production (VN+US) (Priority: P1)

As a production team member (PD), I need a dedicated view that unifies VN and US production queues with my 18 operational columns, status enum with Vietnamese labels + colours, production stage, block reason, and PD note, so I can see what to make today without switching between shops or filtering a generic list.

**Why this priority**: PD cannot currently use the BA-centric Google Sheet; they maintain a separate PD tab. Without a dedicated Odoo Process Dashboard, PD's adoption is zero and the existing sheet stays alive.

**Independent Test**: Open the Process Dashboard, verify PD's 18 columns are visible. Verify the status enum shows Vietnamese labels (Mới / Chờ file / Đang sản xuất / Đã sản xuất / Đã đóng gói / Đã gửi / Huỷ) with distinct colours. Move a row from "Đang sản xuất" to "Đã sản xuất" and verify a `stock.move` is generated (Spec 004a delivers the stock-move integration; here we only verify the state change writes correctly).

**Acceptance Scenarios**:

1. **Given** the Process Dashboard, **When** rendered, **Then** the columns are: order date, shop, product image, product name, variant attributes, qty, personalisation, PD note, design-status summary, production stage, production blocked flag, block reason, PIC (PD), priority, row-decorations (qty≥2, Push, Amazon), and the unified VN+US warehouse indicator.
2. **Given** a multi-warehouse environment, **When** PD applies the "Warehouse" filter, **Then** rows show per-warehouse queues and can be grouped by warehouse.
3. **Given** the Process Dashboard list, **When** PD changes a row's production stage via inline edit, **Then** the new value persists, chatter records the transition with user and timestamp, and if the new value is "Đã sản xuất" the system delegates to Spec 004a's hook for `stock.move` generation (MVP: emit a signal; full integration in 004a).
4. **Given** a row with `production_blocked = True`, **When** rendered, **Then** the row is decorated red and the block reason is visible in a tooltip or dedicated column.
5. **Given** Vietnamese is the user's language, **When** status labels render, **Then** all values use diacritics (e.g., "Đang sản xuất", not "Dang san xuat"). UTF-8 is preserved across export/import round-trips.

---

### User Story 4 — Address-Change Approval Workflow (Priority: P1, safety-critical)

As a Marketing team member (MP) who received a buyer request to change the shipping address, I need to file an address-change request that a BA lead approves before the order's destination fields are overwritten, so we never buy a label against stale data and never silently corrupt a shipped order's audit trail.

**Why this priority**: The current process lets any MP edit `sale.order.partner_shipping_id` directly. Incidents happen: a label is bought, then the address changes, producing a second label and an unrecoverable logistics mistake. BA flagged this as the top safety gap.

**Independent Test**: As an MP user, open a shipped-but-not-delivered order, attempt to edit the shipping address directly — verify the form fields are read-only and a banner instructs the user to file an address-change request. File the request with new values and a reason. Log in as a BA lead; see a `mail.activity` on the order; approve the request. Verify the order's destination fields update and the request state becomes `approved`. Attempt to buy a label on the Tracking Dashboard while a request is `requested` — verify the row is skipped with a warning.

**Acceptance Scenarios**:

1. **Given** an order with no pending address-change request, **When** an authorised user (BA/Manager) edits a destination field, **Then** the write succeeds and chatter records the change (`tracking=True`).
2. **Given** an order with no pending request, **When** an MP user (Marketing group, not BA) attempts to edit a destination field, **Then** the UI shows the fields as read-only and offers a "Request address change" button.
3. **Given** the MP user opens the request form, **When** they submit new values (partner_shipping_id, street, street2, city, zip, state_id, country_id) plus a reason, **Then** an `etsy.address.change.request` record is created in state `requested`, a `mail.activity` is assigned to the BA approver group with type "To Do" and summary "Approve address change for order <ref>", and the order's destination fields become read-only for everyone.
4. **Given** a request in state `requested`, **When** a BA lead clicks "Approve" on the request form, **Then** the stored new values are applied to the `sale.order` in a single transaction, the request transitions to `approved`, chatter records both the approval and the old→new value deltas, and the destination fields become editable again (subject to standard ACLs).
5. **Given** a request in state `requested`, **When** a BA lead clicks "Reject" with a rejection reason, **Then** the request transitions to `rejected`, the order's destination fields remain unchanged and become editable again, and the MP user receives a chatter @mention with the rejection reason.
6. **Given** the Tracking Dashboard bulk "Mark shipped" action, **When** the operation runs, **Then** orders with `has_pending_address_change == True` are excluded from the batch with an on-screen warning listing the skipped order references.
7. **Given** a server-side `sale.order.write` call, **When** a destination field change is attempted while a request is `requested`, **Then** a `UserError` is raised (hard enforcement independent of UI).

---

### User Story 5 — Design Files + 3-State Approval (Priority: P1)

As a production team lead, I need designers to upload front/back design files (or paste URLs to existing CDN assets) and I need to approve / reject each file with a rejection note, so production only runs on verified designs and stale URLs are caught before printing.

**Why this priority**: Gating print production on explicit design approval is what prevents expensive mis-prints. The workflow exists informally today (over email + Drive) and is invisible in Odoo.

**Independent Test**: On an order, upload a 200 KB preview and paste a URL for the 80 MB print-res TIFF. Verify the system accepts the URL (ADR-006 storage policy). Attempt to upload a 15 MB binary and verify it is rejected with a clear message. As a production lead, approve one file and reject another with a note. Verify the kanban shows the three states and the order rolls up to the least-approved child.

**Acceptance Scenarios**:

1. **Given** a sale order, **When** a user uploads a design file ≤ 10 MB, **Then** the binary is stored via `ir.attachment` on filestore (not in PG) and a preview thumbnail (≤ 2 MB) is generated/attached.
2. **Given** a user attempts to upload a design file > 10 MB on a restricted model (`order.design.file`, `sale.order`, `tracking.import.line`), **When** the write is attempted, **Then** a `ValidationError` is raised with text: "File exceeds 10 MB limit. Use URL mode or Drive/S3 link instead."
3. **Given** a large design file, **When** the user pastes a URL instead, **Then** the design-file record stores `storage_mode='url'`, `file_url`, `file_name`, `file_size`, `file_checksum` (SHA-256 if reachable), and the preview thumbnail alone is stored locally.
4. **Given** a design-file record, **When** a production-team user sets approval state to `approved`, `rejected`, or `pending`, **Then** the record tracks user and timestamp; `rejected` requires a non-empty `rejection_reason`.
5. **Given** multiple design-file children under an order line, **When** any child is `pending` or `rejected`, **Then** the line's rolled-up design status is the lowest of its children (order: `rejected` < `pending` < `approved`).
6. **Given** the kanban view, **When** rendered, **Then** three columns exist (`Chờ duyệt`, `Duyệt`, `Cần chỉnh lại`) and design-file cards can be dragged between columns by production-team members only.
7. **Given** a non-production user, **When** they view the kanban, **Then** they see approval states but cannot change them (ACL enforced).
8. **Given** the historical 17,659 orders, **When** the Spec 002 migration wizard runs, **Then** design files are created with `storage_mode='url'` populated from the source Excel's `DESIGN_LINK_FRONT` / `DESIGN_LINK_BACK` columns; no download, no rehosting.

---

### User Story 6 — Multi-Channel Foundation (Priority: P2)

As an owner, I need every sale order to be tagged with a sales channel (Etsy / Amazon / Website / Other) plus a generic `channel_order_ref`, so the three dashboards, future channel connectors, and all reports operate on a channel-aware schema from day one.

**Why this priority**: Deferring channel fields forces a second migration once Amazon/Website arrive — and every dashboard view, search, and report must then be retrofitted. Cheap to do now, expensive to do later.

**Independent Test**: Open any Etsy order; verify `sales_channel='etsy'` and `channel_order_ref == etsy_order_id`. Create a test order manually and set `sales_channel='amazon'`; filter the Order Dashboard by channel and verify the split. Run the backfill migration and verify idempotency (re-run is a no-op).

**Acceptance Scenarios**:

1. **Given** a new sale order, **When** created, **Then** `sales_channel` is a Selection with values `etsy`, `amazon`, `website`, `other`, indexed and required.
2. **Given** any existing Etsy order post-backfill, **When** viewed, **Then** `sales_channel='etsy'` and `channel_order_ref == etsy_order_id`.
3. **Given** the backfill migration is re-run, **When** it iterates existing orders, **Then** rows with a non-empty `sales_channel` are skipped (idempotent).
4. **Given** an Amazon-tagged order, **When** the Order Dashboard renders, **Then** the row shows an `decoration-warning` (Amazon) variant distinct from Push/Urgent decorations.
5. **Given** the three dashboards, **When** the user applies "Channel = Etsy", **Then** only Etsy rows render. Channel is available as a group-by key on all three dashboards.

---

### User Story 7 — Audit Log + Vietnamese UI as cross-cutting FRs (Priority: P2)

As a compliance-conscious owner, I need every edit to a tracked field on orders, design files, address-change requests, and fulfillment state to appear in the chatter with old/new values and user attribution, and I need every form label / button / menu / status value to be available in Vietnamese (the team's working language), so we have a defensible audit trail and zero English-only friction for daily operators.

**Why this priority**: Audit is implicit in Odoo but only if `tracking=True` is set on each field; omitting it is silent and unrecoverable later. Vietnamese labels are not optional for this team — English-only menus have been the top user-adoption friction reported by BA and PD.

**Independent Test**: Edit an order's PIC, priority, fulfillment stage, and shipping address via the approval workflow. Open the chatter tab; verify one entry per tracked change with old/new values and the editor's name. Switch the Odoo language to Vietnamese; verify every new label (dashboards, buttons, status values, kanban columns, error messages) shows the translated string.

**Acceptance Scenarios**:

1. **Given** every model introduced by this spec, **When** declared, **Then** the model inherits `mail.thread` and `mail.activity.mixin`; every user-visible field sets `tracking=True` unless it is a Binary or a technical counter.
2. **Given** a tracked-field edit (PIC, priority, fulfillment stage, design status, address-change state, shipping carrier, tracking state), **When** the write commits, **Then** a `mail.tracking.value` row is created and visible in the chatter with old/new values and editor.
3. **Given** a user switches their preferred language to Vietnamese, **When** they open any dashboard or form introduced by this spec, **Then** every label, button, status value, menu entry, kanban column title, error message, and help text renders in Vietnamese with correct diacritics.
4. **Given** the module's `i18n/` directory, **When** packaged, **Then** `vi_VN.po` is present, non-empty, and covers 100% of new strings introduced by this spec. A CI check asserts coverage.
5. **Given** round-trip data flows (Excel import, Excel export, CSV export, chatter email notifications), **When** Vietnamese strings pass through, **Then** UTF-8 encoding is preserved end-to-end (no mojibake, no diacritic loss).

---

### Edge Cases

- A duplicate-buyer decoration must NOT false-positive on repeat loyal customers; the "duplicate" signal is a 7-day sliding window on `partner_id + shipping address hash`, not on name-only match.
- Overdue-approval markers must exclude orders whose `sales_channel` is `amazon` (no design approval workflow there yet) and orders in final states (`shipped`, `done`, `cancel`).
- Inline edit on the dashboards must honour ACLs — an MP user inline-editing a destination field should see the value render read-only with the approval-workflow hint, not a silent write failure.
- A design file whose URL becomes unreachable (Etsy CDN 404) must surface a warning chip in the kanban without failing the render.
- Process Dashboard's stage transition to "Đã sản xuất" must be idempotent — accidental double-click or double-submit must not generate two `stock.move` records (Spec 004a implements the guard; this spec verifies the behaviour).
- Address-change request filed on an already-shipped order must be rejected by a constraint with a helpful message ("Order already shipped — create a return/ticket instead").
- If the Etsy CDN URLs in historical orders are empty (missing `DESIGN_LINK_FRONT` / `BACK`), the migration wizard creates an empty `order.design.file` placeholder with `storage_mode='url'` and `file_url=NULL`, flagged for later manual fill.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Dashboards

- **FR-001**: System MUST provide three distinct dashboards — Order, Tracking, Process — backed by the same `sale.order` + `sale.order.fulfillment` data, each with its own column set, default filters, default sort, and row decorations.
- **FR-002**: System MUST render product thumbnails (`image_128`) inline on the Order Dashboard and the Process Dashboard without additional form-open navigation.
- **FR-003**: System MUST support list-row decorations driven by: `product_uom_qty >= 2`, duplicate-buyer 7-day window, `order_priority IN ('push','urgent')`, and `sales_channel = 'amazon'`. Decorations compose (e.g., Push + Amazon = stacked badges).
- **FR-004**: System MUST paginate dashboards server-side at 80 rows per page; initial load of the first page MUST complete within 3 seconds for a 17,000+ row dataset on the target environment.
- **FR-005**: System MUST allow inline edit on Order Dashboard for: MP note, PIC, priority, fulfillment stage, label status — subject to ACL.
- **FR-006**: System MUST allow inline edit on Tracking Dashboard for: tracking number, carrier (M2O to `shipping.carrier`), shipping date, label status, tracking state.
- **FR-007**: System MUST allow inline edit on Process Dashboard for: production stage, PD note, `production_blocked`, block reason, PIC (PD).
- **FR-008**: System MUST provide a merged Tracking State column (Selection: none / label_requested / label_ready / shipped / in_transit / delivered) that is read on all three dashboards and writable via Tracking Dashboard.
- **FR-009**: System MUST display an overdue-approval marker on any order whose design-approval `mail.activity` is ≥ 24 hours past due date (excluding final-state orders and non-etsy channels).
- **FR-010**: System MUST display a store-manager avatar column on Order and Process dashboards, sourced from `etsy.shop.manager_user_id` (or the channel-specific equivalent).

#### Address-Change Approval

- **FR-011**: System MUST introduce model `etsy.address.change.request` with at minimum: `order_id` (M2O sale.order), `requested_fields` (JSON listing changed keys), `new_values` (JSON with new scalar values), `state` (Selection: requested / approved / rejected), `requested_by`, `approved_by`, `rejection_reason`, `mail.thread` + `mail.activity.mixin` inheritance.
- **FR-012**: System MUST compute a boolean `has_pending_address_change` on `sale.order` driven by the presence of any related request in state `requested`.
- **FR-013**: System MUST render `partner_shipping_id`, `street`, `street2`, `city`, `zip`, `state_id`, `country_id` as read-only on `sale.order` form + Order Dashboard + Tracking Dashboard when `has_pending_address_change == True`.
- **FR-014**: System MUST enforce at ORM level (via `@api.constrains` or `_write` override on `sale.order`) that a write to any destination field fails with `UserError` when `has_pending_address_change == True`, regardless of UI state.
- **FR-015**: System MUST post a `mail.activity` to the BA-approver group on request creation and auto-complete the activity on approve/reject.
- **FR-016**: System MUST reject creation of an address-change request on orders in final states (`shipped`, `done`, `cancel`) via a `@api.constrains` hook, with a message pointing to the returns/ticket flow.
- **FR-017**: Tracking Dashboard bulk actions (mark shipped, request label, etc.) MUST exclude rows with `has_pending_address_change == True` and warn the operator on-screen.

#### Design Files

- **FR-018**: System MUST introduce model `order.design.file` with at minimum: `order_line_id` (M2O), `storage_mode` (Selection: `small` / `url`), `design_file` (Binary, `attachment=True`), `preview_file` (Binary, `attachment=True`), `file_url` (Char), `file_name` (Char), `file_size` (Integer bytes), `file_checksum` (Char SHA-256), `state` (Selection: pending / approved / rejected), `rejection_reason` (Text), `approved_by`, `approved_at`, chatter mixins.
- **FR-019**: System MUST override `ir.attachment.create` to reject writes > 10 MB attached to `order.design.file`, `sale.order`, or `tracking.import.line` with `ValidationError` — threshold configurable via `ir.config_parameter` (`multichannel_hub.large_file_threshold_bytes`).
- **FR-020**: System MUST support URL-mode storage (`storage_mode='url'`) with locally-stored preview thumbnail ≤ 2 MB.
- **FR-021**: System MUST compute a roll-up `design_status` on `sale.order.line` equal to the lowest child state (order: `rejected` < `pending` < `approved`).
- **FR-022**: System MUST provide a kanban view on `order.design.file` with three Vietnamese-labelled columns; drag-drop restricted to the production-team ACL group.
- **FR-023**: System MUST be compatible with the Spec 002 migration: historical orders seed `order.design.file` rows with `storage_mode='url'` from `DESIGN_LINK_FRONT` / `DESIGN_LINK_BACK`.

#### Multi-Channel Foundation

- **FR-024**: System MUST add `sales_channel` (Selection: `etsy`, `amazon`, `website`, `other`, indexed, required) and `channel_order_ref` (Char, indexed) to `sale.order`.
- **FR-025**: System MUST provide a backfill migration setting `sales_channel='etsy'` + `channel_order_ref = etsy_order_id` on existing Etsy orders; the migration MUST be idempotent.
- **FR-026**: Dashboards MUST expose `sales_channel` as a filter and group-by key; all saved searches MUST be channel-aware.

#### Unified Carrier

- **FR-027**: System MUST introduce model `shipping.carrier` with `name`, `code` (unique), `is_active`, `tracking_url_template`, `tracking_prefix_regex`, `etsy_carrier_name` (Selection mapping to Etsy enum), `gearment_carrier_name`, `notes` — owned by the shared core module (ADR-003).
- **FR-028**: System MUST replace any previous `sale.order.shipping_carrier` Char with `shipping_carrier_id` M2O to `shipping.carrier`, stored on the `sale.order.fulfillment` delegation sibling (ADR-005 + ADR-007).
- **FR-029**: System MUST ship seed carriers covering USPS, UniUni, YunExpress, 4PX, DHL eCommerce, FedEx SmartPost, GKE Local, each with the correct `etsy_carrier_name` mapping or explicit `other` fallback.

#### Delegation Mixin

- **FR-030**: System MUST introduce `sale.order.fulfillment` via `_inherits = {'sale.order': 'order_id'}` hosting fulfillment-lifecycle fields (production stage, tracking number, `shipping_carrier_id`, shipping date, label status, fulfillment status, PD note, MP note, PIC, priority, `production_blocked`, block reason, `has_pending_address_change` mirror) per ADR-007. Auto-create the sibling on `sale.order` create.

#### Audit & i18n (cross-cutting)

- **FR-031**: Every model introduced by this spec MUST inherit `mail.thread` + `mail.activity.mixin`. Every user-visible scalar field MUST set `tracking=True` unless it is a Binary or a pure technical counter.
- **FR-032**: System MUST ship `i18n/vi_VN.po` with 100% coverage of new strings. CI MUST fail on missing translations.
- **FR-033**: System MUST preserve UTF-8 end-to-end across Excel/CSV import/export and email notifications; tests MUST include diacritic round-trip fixtures.

### Key Entities

- **Order Dashboard view** — a saved `ir.actions.act_window` on `sale.order` with a channel-aware default filter, 80-row pagination, inline-editable BA columns, product thumbnails, row decorations, overdue-approval marker, store-manager avatar.
- **Tracking Dashboard view** — saved view on `sale.order.fulfillment` (through delegated access) focused on tracking fields; bulk-action-capable; import/export-aware; skips rows with pending address changes.
- **Process Dashboard view** — saved view for PD with 18 operational columns, warehouse grouping, Vietnamese-coloured status chips, production-stage inline edit that delegates to Spec 004a's stock-move hook.
- **`etsy.address.change.request`** — gated destination-change model with approval state, JSON new-value payload, BA-activity integration, ORM-level write guard on `sale.order`.
- **`order.design.file`** — file record with dual small/URL storage mode, 3-state approval, chatter mixins, kanban.
- **`shipping.carrier`** — unified carrier master data with Etsy and Gearment name mappings (replaces the old `shipping_carrier` Char and Spec 005's `etsy.carrier.mapping`).
- **`sale.order.fulfillment`** — delegation sibling hosting the fulfillment-lifecycle fields; keeps `sale.order` lean per ADR-007.

## Success Criteria *(mandatory)*

- **SC-001**: BA team runs daily order triage, tracking reconciliation, and production handoff entirely in Odoo for ≥ 10 consecutive business days with the Google Sheet in read-only mode.
- **SC-002**: First-page Order Dashboard render ≤ 3 s on the target environment against the full 17K+ order dataset.
- **SC-003**: Zero duplicate-label incidents caused by silent address edits during a 60-day post-launch window.
- **SC-004**: Address-change requests reach a decision (approve / reject) in under 4 business hours median, measured on activity close timestamps over a rolling 30-day window.
- **SC-005**: 100% of historical Etsy orders display the correct `sales_channel` and a non-null `channel_order_ref` post-backfill.
- **SC-006**: 100% of new user-visible strings are translated in `vi_VN.po`; CI enforces. Zero reported mojibake incidents in Excel/CSV round-trips.
- **SC-007**: Audit — every approval, rejection, or destination-field change produces at least one chatter entry with old/new values and the acting user; randomised sampling of 50 edits finds 100% chatter coverage.
- **SC-008**: Three dashboards' column sets, filters, and decorations match the BA/PD/MP feedback documents without ad-hoc local customisation by end users after training.

## Assumptions

- Spec 002 is shipped or concurrent; financial data, product categories, and order confirmation are in place.
- Spec 004a will deliver the tracking import wizard and the `stock.move` integration that the Process Dashboard's stage transition delegates to.
- The team keeps a single Odoo company; multi-company partitioning is out of scope.
- Odoo 19 CE only — no Enterprise modules (`helpdesk`, `documents`, `approvals`) per ADR-004.
- Warehouse structure: two logical warehouses (VN production, US production / dropship). A master-plan open question asks whether this is logical-only or true `stock.location` per warehouse; resolution expected before Process Dashboard implementation.
- BA approver group has ≤ 5 members; routing the approval activity to the group (not a specific user) is acceptable.
- Design-file URLs referenced in historical data are Etsy CDN links (`etsystatic.com`) that remain reachable during the 12-month horizon; a future archival task (post-MVP) may localise them to filestore.
- `image_128` on `product.template` is reliably populated during Spec 002 categorisation; if not, Order Dashboard falls back to a placeholder glyph rather than failing render.

## Out of Scope

- **Fulfillment routing, partner integrations** — Spec 004b (Gearment) and beyond.
- **Tracking import wizard itself** — Spec 004a. This spec defines the Tracking Dashboard that consumes the imported data.
- **Returns / refunds / replace tickets** — Spec 004c (ADR-004 custom `etsy.order.ticket`).
- **Etsy messaging / 2-way CRM** — deferred with Spec 005 (conversations scope not granted).
- **Raw-material inventory + forecasting** — Spec 007 (PD feedback; native `stock_forecasted`).
- **Sales pricing audit dashboard** — Spec 006.
- **Amazon / Website channel connectors** — Specs 010 / 011; this spec only ensures the foundation is ready.
- **Google Drive auto-sync of design files** — permanently deferred (ADR-004, ADR-006).

## Dependencies

| This spec needs | From | Why |
|---|---|---|
| Confirmed financial data + product categorisation | Spec 002 | Order Dashboard shows correct `amount_total`, image, category |
| Delegation mixin `sale.order.fulfillment` | ADR-007 (this spec owns the mixin) | All fulfillment-lifecycle fields live here |
| Unified `shipping.carrier` model + seed | ADR-005 (this spec owns it) | Tracking Dashboard + future Etsy push + Gearment |
| 10 MB attachment guard | ADR-006 (this spec owns it) | Design-file storage policy |
| Module decomposition into `multichannel_hub_core` | ADR-003 | Mixin + carrier + dashboards ship in the shared core so Amazon/Website reuse |

| Other specs need from this | What |
|---|---|
| Spec 004a | `shipping.carrier` seed; `sale.order.fulfillment` mixin; Tracking Dashboard to surface imports; Process Dashboard stage enum |
| Spec 004b (Gearment) | Delegation mixin + carrier + dashboards to surface partner state |
| Spec 004c (returns/tickets) | Chatter / activity scaffolding + dashboards to link tickets |
| Spec 005 (Etsy API) | `shipping.carrier.etsy_carrier_name` for tracking push; `sales_channel` for channel tagging; dashboards to surface API sync state |
| Specs 010 / 011 (Amazon / Website) | Channel foundation + delegation mixin reuse |

## Revision History

- **2026-04-06**: v1 authored (single dashboard, 7 user stories). Archived under `_archive/spec-2026-04-06.md`.
- **2026-04-13**: Full rewrite per master-plan Wave B. Three dashboards, address-change approval workflow, delegation mixin adoption, unified carrier, 10 MB file cap, Vietnamese i18n + audit as explicit FRs.
