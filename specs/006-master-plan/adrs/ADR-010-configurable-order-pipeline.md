# ADR-010: Configurable Order Pipeline (combines former state-machine + WC reassignment ADRs)

- **Status**: Accepted
- **Date**: 2026-04-26
- **Sign-off**: 2026-04-26 (owner; recorded via Stage-1 synthesis — Owner accepted recommended design with the principle "flexible, cover all known issues, stay in Odoo internal, utilise all resources")
- **Deciders**: Owner, architect (synthesis), PD lead, BA lead
- **Affects**: Spec 003 (data model US1/US2/US3), SRS REQ-PRO-03/04/09 (reframed), SRS new REQ-PIP-01..09, E2 §6 + §3.1
- **Related**: [ADR-001](ADR-001-spec-004-split.md), [ADR-009](ADR-009-file-lifecycle.md), [ADR-008a](ADR-008a-email-as-mandatory-backup.md), [`../clarifications/state-machine-questions.md`](../clarifications/state-machine-questions.md), [`../clarifications/wc-reassign-governance-questions.md`](../clarifications/wc-reassign-governance-questions.md)
- **Supersedes / collapses**: the proposed-but-never-written ADR-011 (WC reassignment governance) — its scope is folded into this ADR's §6 "Resource assignment per stage."

## Context

The 2026-04-26 red-pen review introduced 17 Vietnamese sub-states (E2 §6) and a WC-reassignment-governance requirement (REQ-PRO-09). The first synthesis treated these as hardcoded `mrp.production.x_substate` enum + `mrp.routing` audit-log model. Owner clarified later same day:

> Don't use `mrp.production` yet. Build a **configurable pipeline** that users define and attach to products. The pipeline lives on `sale.order`, not on `mrp.production`. Default order status is `draft` for new orders; historical orders that are already done get `state='done'` and the pipeline state can be blank or editable based on user choice.
>
> WC reassignment should follow the same approach — configurable; user configs the flow and applies for product category or product.

This collapses two would-be ADRs into one and moves the design from "MRP state machine" to "user-configurable order pipeline with per-stage resource assignment." The 17 Vietnamese sub-states become **one default seed pipeline**, not the only state machine.

Operating principles applied (Owner direction 2026-04-26):

- **Flexible** — configuration over code
- **Cover known issues** — explicit support for rework, multi-technique, in-flight edits
- **Stay in Odoo internal** — no external state machine engines, reuse Odoo's `Selection` / `mail.message` / `crm.team` patterns where possible
- **Utilise all resources** — leverage Odoo native `sale.order.state` for high-level status; layer pipeline state on top

## Decision

### 1. Five new models

#### `order.pipeline`
A named, versioned pipeline definition. Users create one or more; each is a sequence of stages.

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required, unique (e.g., "Vietnam Internal Production", "Gearment POD", "Multi-Technique Hybrid"). |
| `description` | Text | Optional human-readable purpose. |
| `version` | Integer | Auto-incremented on edits per §5 below. Starts at 1. |
| `parent_pipeline_id` | M2O → `order.pipeline` | Set on every version after the first; points to the immediately-preceding version. NULL for v1. |
| `is_active` | Boolean | Inactive pipelines hidden from new assignments but kept for in-flight order references. |
| `state_ids` | O2M → `order.pipeline.state` | The ordered stages. |
| `transition_policy` | Selection | `dag_with_admin_override` (default — admin role can force any transition) / `free_form` (any → any with audit) / `dag_strict` (only declared transitions). See §4. |

Versioning is immutable: editing an active pipeline (add/remove/rename/reorder stages) creates a **new version row** with `parent_pipeline_id` set. In-flight orders snapshot the version they were created against and use that version forever (see §5).

#### `order.pipeline.state`
A stage within a pipeline. Carries the optional resource assignment.

| Field | Type | Notes |
|---|---|---|
| `pipeline_id` | M2O → `order.pipeline` | Required. |
| `name` | Char | Required (e.g., "CHỜ FILE", "VN-Dish", "VN-Packed 1"). Unique within pipeline. |
| `sequence` | Integer | Display order. |
| `is_initial` | Boolean | Exactly one stage per pipeline must have `is_initial=True`. The pipeline starts orders here. |
| `is_terminal` | Boolean | Marks "done" stages. Multiple terminal stages allowed (e.g., VN-Fulfilled, US-Fulfilled, Cancelled-by-Buyer). |
| `responsible_team_id` | M2O → `pipeline.team` | Optional default responsible team (see §6). |
| `next_stage_ids` | M2M → `order.pipeline.state` (`order_pipeline_state_transition_rel`) | Allowed direct successors. Empty for terminal stages. Used only when `transition_policy ∈ {dag_with_admin_override, dag_strict}`. |
| `color` | Selection | Odoo standard color enum, for kanban display (matches the "colored sub-states" requirement in REQ-PRO-03). |
| `auto_advance_trigger` | Selection | `none / on_payment / on_design_approved / on_tracking_imported` — Phase-1 supports `none` only; later phases can layer triggers (see §7). |

#### `pipeline.team`
A custom lightweight team model — the "resource" or "work-center" or "responsible group" for a stage. Modeled separately from `crm.team` (which carries CRM-specific fields) and separately from `mrp.workcenter` (which couples to MRP).

| Field | Type | Notes |
|---|---|---|
| `name` | Char | E.g., "Paper-print line", "Ceramic-stamp line", "MP", "PD-South". |
| `member_ids` | M2M → `res.users` | Members of the team. |
| `team_lead_id` | M2O → `res.users` | Optional lead (gets pings on stage SLA breaches if defined later). |
| `active` | Boolean | Standard. |

This model is intentionally minimal. If/when the project adopts MRP, `pipeline.team` can be linked to `mrp.workcenter` via an additional optional field; not in scope here.

#### `order.pipeline.transition.log`
The single audit table for everything that happens to a pipeline or to an order's pipeline state. One model, one query, one audit view (per the v2 question pack Q4=A recommendation).

| Field | Type | Notes |
|---|---|---|
| `change_type` | Selection | `pipeline_created / pipeline_versioned / stage_added / stage_removed / stage_renamed / stage_reordered / resource_changed / order_transition / order_pipeline_assigned / order_pipeline_changed` |
| `pipeline_id` | M2O → `order.pipeline` | Required for pipeline-structure changes. |
| `pipeline_state_id` | M2O → `order.pipeline.state` | Required for stage-level changes. |
| `sale_order_id` | M2O → `sale.order` | Required for order-level changes (transition, pipeline assigned/changed). |
| `from_value` | Char | JSON-serialised previous value (stage name, resource ID, etc.). |
| `to_value` | Char | JSON-serialised new value. |
| `reason` | Text | Optional free-text reason. Required for `change_type='order_transition'` if the transition is a backward jump under DAG policy. |
| `changed_by_user_id` | M2O → `res.users` | Who made the change. |
| `changed_at` | Datetime | When (DB default `now()`). |

#### Two new fields on `sale.order`

| Field | Type | Notes |
|---|---|---|
| `x_pipeline_id` | M2O → `order.pipeline` | The pipeline this order is using. Computed from product/category at confirmation time per §3; manually overridable. NULL for historical-archived orders (per Owner direction). |
| `x_pipeline_state_id` | M2O → `order.pipeline.state` | Current sub-state within the pipeline. Always within the pipeline pinned in `x_pipeline_id`. NULL when `x_pipeline_id` is NULL. |
| `x_responsible_team_id` | M2O → `pipeline.team` | Optional per-order override of the stage's default team. Computed from `x_pipeline_state_id.responsible_team_id` if not overridden. |

Plus default fields on product:

| Field | Type | Notes |
|---|---|---|
| `product.template.x_default_pipeline_id` | M2O → `order.pipeline` | Per-product default pipeline. |
| `product.category.x_default_pipeline_id` | M2O → `order.pipeline` | Per-category default pipeline (fallback if product has no override). |

### 2. Pipeline assignment scope (Q1=C — per-product with category-level default)

When a `sale.order` is confirmed:

1. For each `sale.order.line.product_id`, look up the effective default pipeline:
   - First: `product.template.x_default_pipeline_id`
   - Second: `product.category.x_default_pipeline_id`
   - Third: a tenant-wide default (system parameter `etsy_integration.default_pipeline_id`)
2. If all line products resolve to the **same pipeline** → assign that pipeline to the order.
3. If line products resolve to **different pipelines** → fall back to the per-order manual choice (Q2=D below).

Admin can also manually override at any time per §3.

### 3. Mixed-pipeline orders (Q2=D — manual with default)

When `sale.order` line items resolve to different default pipelines:

- The order's `x_pipeline_id` defaults to the pipeline of the **first** line item (lowest sequence).
- The order is flagged in the UI ("Mixed pipelines detected — confirm assignment").
- BA / admin can manually pick any of the candidate pipelines, or override entirely to a different pipeline.
- Recorded in `order.pipeline.transition.log` with `change_type='order_pipeline_assigned'`.

This avoids the complexity of multi-pipeline orders (which would require N stages tracked in parallel) at the cost of a single manual decision per mixed order. The team can later add hybrid pipelines that contain stages for all techniques (e.g., a "Multi-Technique" pipeline with sequential stages per technique).

### 4. Pipeline change after order creation (Q3=A — yes freely with audit log)

`x_pipeline_id` can be changed at any time by users with `etsy_integration.group_admin` or `group_pd_lead`. When changed:

- `x_pipeline_state_id` resets to the new pipeline's `is_initial` stage.
- A `change_type='order_pipeline_changed'` row is written.
- A `mail.message` is posted to the order chatter.

This supports recovery from data errors and supports re-classification when an order's nature changes mid-flight.

### 5. Pipeline editing semantics (Q5=A — versioning) and stage reordering (Q6=C — versions only)

Pipeline definitions are **immutable once an order has used them**. Editing an active pipeline (any field change on `order.pipeline.state`, including reorder) creates a new `order.pipeline` row with `parent_pipeline_id` set + `version` bumped. The previous version stays in the table but is marked `is_active=False` if no in-flight orders reference it.

Mechanics:
- The Pipeline form view's "Save" button on a pipeline that has any orders pointing to it triggers a confirmation: "This pipeline has N in-flight orders. Saving will create a new version. Existing orders will continue using version M."
- New orders use the latest active version of whichever pipeline they're assigned to.
- In-flight orders never auto-migrate. PD/BA can manually re-assign an in-flight order to the new version via the Q3 mechanism if desired.
- Pipelines with **zero** orders (just-created or never-used) can be edited in place without versioning — the "edit creates version" trigger fires only on first use.

This is the same pattern Odoo uses for `account.move` (lock once posted) and `stock.picking` (state transitions are immutable once advanced).

### 6. Resource assignment per stage (Q1=A custom team; Q2=B per-stage default + per-order override; Q3=A snapshot)

Every `order.pipeline.state` carries an optional `responsible_team_id` (M2O → `pipeline.team`). When an order enters a stage:

- The order's `x_responsible_team_id` is set from the stage's default (computed/stored).
- BA / PD lead can override per order by editing `x_responsible_team_id` directly (logged in `order.pipeline.transition.log` with `change_type='resource_changed'`).
- Reassigning a **stage's** default team only affects orders that **enter the stage after the change**. Orders already in that stage retain the resource they were assigned to (matches the immutable-on-entry pattern).
- This means: if Owner reassigns "ceramic family" from Line A to Line B, and there are 5 orders currently in the ceramic-stamp stage on Line A, those 5 orders stay on Line A. New orders entering the stage go to Line B.

This satisfies REQ-PRO-09's audit-trail requirement (everything in `order.pipeline.transition.log`) and the in-flight-safety concern (snapshot on entry, no mid-flight team reassignment) raised by DA post-redpen N3.

### 7. Transition policy (Q7=C — DAG with admin override)

Per pipeline, the `transition_policy` field controls what transitions are allowed:

- **`dag_strict`** — only `next_stage_ids` allowed. UI hides invalid options. No backward jumps.
- **`dag_with_admin_override`** *(default)* — `next_stage_ids` for normal users; `etsy_integration.group_admin` can pick any stage with a required `reason` field. Audit log captures the override.
- **`free_form`** — any user can pick any stage. Audit logs everything. Useful during early adoption / data cleanup.

Backward jumps and rework loops are modeled as DAG cycles in `next_stage_ids` (a stage can list itself as `next_stage_ids` for "stay in stage; reset timer" semantics, or list earlier stages for explicit rework paths). The default seed pipeline (§9) has explicit `next_stage_ids` populated.

### 8. Auto-advance triggers (Q8=D — Phase 1 manual only)

Phase 1 ships `auto_advance_trigger='none'` on all stages. Manual transitions only.

Phase 2+ may layer triggers from a built-in catalog: `on_payment`, `on_design_approved`, `on_tracking_imported`, etc. Each trigger is an internal Odoo event hooked from the relevant subsystem (sale, design.file, stock.picking) and is implemented as a server action that calls `_advance_pipeline_state()` on the order. This keeps the configuration declarative (admin picks from a dropdown) without exposing Python evaluation to admin users.

### 9. Default seed pipeline (Q9=A — pre-seed the 17 Vietnamese stages)

A `data/order_pipeline_seed.xml` file ships with the module containing one pipeline named **"Vietnam Internal Production"** (translatable: `Sản xuất nội bộ Việt Nam`). It contains the 17 stages from E2 §6:

```
1.  CHỜ FILE                  (initial)
2.  CHỜ DUYỆT
3.  ĐÃ GỬI PROOF
4.  US-od                     (parallel branch — for US outsource)
5.  Vietnam-od                (parallel branch — for Vietnam outsource)
6.  VN-Dish
7.  VN-Dish NG                (rework branch from VN-Dish)
8.  [Fix]VN-Dish              (rework branch — design re-cut)
9.  VN-SP mới
10. VN-Apron
11. VN-Handkerchief
12. VN-Packed
13. VN-Packed 1               (operator/line variant; admin can rename or delete)
14. VN-Fulfilled              (terminal)
15. Bad approval              (terminal — review failed)
16. Production overdue        (parallel — informational tag stage)
17. Cancelled                 (terminal — buyer cancellation)
```

`next_stage_ids` are pre-populated with sensible defaults; admin can edit to refine.

The `transition_policy` is set to `dag_with_admin_override` so the team can run the pipeline strictly while still having an escape hatch for data fixes.

The semantics that the original DA-N2 risk worried about ("VN-Packed 1 means what?", "[Fix]VN-Dish triggered by what?") become **editable**: if the team disagrees with a stage name, they rename it; if they want to delete `VN-Packed 1`, they edit the pipeline → new version is auto-created → in-flight orders keep using the old version. **No code change required to fix wrong semantics.**

A second seed pipeline ships for Gearment-POD orders ("Gearment POD") with a much shorter stage list (Awaiting Push → Pushed → Awaiting Tracking → Fulfilled). Admin can extend.

### 10. Backfill of historical orders

The 17,659 historical orders being normalized in Spec 002:

- All historical orders default to `x_pipeline_id = NULL`, `x_pipeline_state_id = NULL`.
- Native `sale.order.state = 'done'` (per Owner direction "history orders which already done, order status will be done").
- Admin can optionally bulk-assign historical orders to a "Historical / archived" pipeline (single terminal stage) for reporting consistency. This is admin-discretionary, not automated.

## Consequences

### Positive

- **Zero hardcoded enum** for production sub-states. The 17 Vietnamese stages are seed data, fully editable. The codebase doesn't need a code change when the team renames a stage or adds a new one.
- **Resolves D-11, D-12, D-16, REQ-PRO-03/04/09** in one design.
- **Multi-technique products** (D-16 / DA N6) are handled by creating a "Multi-Technique" pipeline with sequential stages — no new model, no special case.
- **Audit trail centralised** in `order.pipeline.transition.log` — one query gets the full history of any pipeline edit, stage rename, resource reassignment, or order transition.
- **In-flight safety** (no mid-flight resource reassignment surprise) — matches the immutable-on-entry pattern Odoo uses elsewhere; satisfies DA post-redpen N3 without ceremony.
- **Owner principle "stay in Odoo internal" honored** — no external state-machine engine, no MRP coupling, reuses native `sale.order.state` for high-level status.
- **Owner principle "flexible" honored** — pipelines, stages, resources, and transition policy are all configuration not code.

### Negative

- **5 new models** (one is a tiny `pipeline.team`). Onboarding cost for new developers; mitigated by the design being a single conceptual unit ("configurable pipelines") rather than scattered.
- **Versioning UI is non-trivial** — confirming "save will create a new version" on every edit is an extra modal. Mitigation: only triggered when in-flight orders exist; greenfield pipelines edit in place.
- **DAG navigation in the form view** needs a custom widget to show `next_stage_ids` per stage clearly. Standard `Many2many` widget is too dense.
- **Mixed-pipeline orders** require BA attention. Mitigation: §3 fallback gives a working default; a hybrid pipeline can be configured for known mixed-product cases.
- **Phase-1 manual-only auto-advance** means PD has to click through transitions; some teams may want triggers immediately. Mitigation: Phase 2 layer-on plan is in §8; nothing in Phase 1 prevents it.

### Neutral

- ACL groups follow the existing `etsy_integration` pattern (`group_admin`, `group_pd_lead`, `group_mp`, `group_ba`).
- `mail.message` chatter on `order.pipeline` and on `sale.order` is free Odoo functionality.
- Reporting on stage durations and resource utilisation comes naturally from `order.pipeline.transition.log` — Phase-2 BI can query it directly.

## Alternatives considered

1. **Hardcoded `mrp.production.x_substate` enum with 17 stages** (the morning's design) — rejected by Owner. Couples to MRP we don't yet need; locks "VN-Packed 1" semantics in code; can't adapt to team workflow changes without dev work.
2. **Use Odoo's `account.payment.term` pattern** (linked rows with sequence) — rejected. That pattern doesn't carry transition policy, audit log, or resource assignment. Building those on top would re-invent this ADR with worse ergonomics.
3. **Reuse `mrp.routing` + `mrp.workcenter`** — rejected per Owner direction "don't use mrp.production yet." Couples to MRP infrastructure that isn't otherwise warranted in Phase 1.
4. **Separate ADR-011 for resource assignment** — rejected per Owner direction "WC reassignment should follow the same approach." Folded into §6 here.
5. **Free-form text field for sub-state** (no model) — rejected. Loses search, color-coded kanban, transition rules, audit, and SLA-tracking.
6. **External state-machine engine (e.g., python-statemachine)** — rejected per Owner principle "stay in Odoo internal." Adds dependency for no functional gain over the model-driven design here.
7. **Single mutable pipeline (no versioning)** — rejected. In-flight orders would silently see structural changes; analytics would be unreliable. The versioning cost is small and the safety is large.

## Implementation notes

Spec 003 tasks (added to its `tasks.md` after this ADR + ADR-009 land):

Models:
- `models/order_pipeline.py` (`order.pipeline`)
- `models/order_pipeline_state.py` (`order.pipeline.state`, `_sql_constraints` on (pipeline_id, name) unique)
- `models/pipeline_team.py` (`pipeline.team`)
- `models/order_pipeline_transition_log.py` (`order.pipeline.transition.log`)
- Extension on `models/sale_order.py` for `x_pipeline_id`, `x_pipeline_state_id`, `x_responsible_team_id`
- Extension on `models/product_template.py` for `x_default_pipeline_id`
- Extension on `models/product_category.py` for `x_default_pipeline_id`

Methods:
- `sale.order._compute_default_pipeline()` (per §2)
- `sale.order._advance_pipeline_state(target_state_id, reason='')` (per §7)
- `sale.order._reassign_pipeline(new_pipeline_id, reason='')` (per §4)
- `order.pipeline._create_new_version()` (per §5; called from `write()` when in-flight orders exist)
- `order.pipeline.state._compute_responsible_team_for_order(order)` (per §6)

Views:
- `order.pipeline` form (with stages list, transition policy selector, version history)
- `order.pipeline.state` form (with `next_stage_ids` widget)
- `pipeline.team` form (members, lead)
- `order.pipeline.transition.log` list (filter by pipeline / order / change_type)
- `sale.order` form extension (current pipeline state widget; "Advance" button per allowed transition)
- Process Dashboard kanban grouped by `x_pipeline_state_id`

Wizards:
- "Re-assign pipeline" (admin-triggered from sale.order action menu)
- "Promote to new pipeline version" (triggered when admin edits pipeline with in-flight orders)

Data:
- `data/order_pipeline_seed.xml` (Vietnam Internal Production pipeline + Gearment POD pipeline + Multi-Technique pipeline templates)
- `data/pipeline_team_seed.xml` (initial teams: MP, BA, PD-South, PD-North, Paper-print, Ceramic-stamp, Heatpress, Embroidery, Assembly, Personalize)

Security:
- `etsy_integration.group_pipeline_admin` (full pipeline edit)
- `etsy_integration.group_pd_lead` (resource reassignment)
- Existing `etsy_integration.group_admin` extended with pipeline override permissions

Tests:
- Phase 1 (DB):
  - Every `order.pipeline` has exactly one stage with `is_initial=True`
  - Every non-terminal stage in a `dag_strict` pipeline has at least one entry in `next_stage_ids`
  - `order.pipeline.transition.log` has a row for every stage transition
- Phase 2 (ORM):
  - Confirm a sale.order with one product → `x_pipeline_id` populated from product default → `x_pipeline_state_id` is the initial stage
  - Confirm a sale.order with mixed-pipeline products → pipeline defaults to first line + UI flag
  - Edit a pipeline with in-flight orders → new version created → in-flight orders still reference old version
  - Edit a pipeline with no in-flight orders → no version created
  - Reassign a stage's `responsible_team_id` → existing in-stage orders unchanged → next entry uses new team
  - Admin override under `dag_with_admin_override` → audit log records `reason`
  - Backward transition under `dag_strict` → blocked
  - Backfill: historical sale.order with `state='done'` and `x_pipeline_id=NULL` is valid

Operational follow-through:

- Owner / PD lead reviews the seed pipeline once after first install; edits to taste; pipeline auto-versions if any seed orders already exist.
- Add `order.pipeline.transition.log` to the Process Dashboard tile area for debugging stuck orders.
- Operations runbook: "An order is stuck in stage X — what to check" page references this ADR §6 + §7.

## Amendment 2026-05-03 — Hybrid with standard Odoo dropship + MTO routes

**Status:** Accepted (Owner direction 2026-05-03 — Path B chosen via `AskUserQuestion`).
**Affects:** `multichannel_hub_core` + `multichannel_hub_fulfillment` manifests, P1-DROP-* and P1-MTO-* slice family in [`.claude/plans/006-master-plan-tracking.md`](../../../.claude/plans/006-master-plan-tracking.md).
**Does NOT supersede** the §Decision sections above — the configurable pipeline machinery, the 17 VN seed stages, the versioning semantics, and FR-017 write-defense remain canonical.

### What changed

The 2026-04-26 §Decision rejected three uses of standard Odoo MRP/Purchase plumbing (alternatives 1–3, lines 245–248). On 2026-05-03 the owner re-cited the Odoo 19 docs for [Dropshipping](https://github.com/odoo/documentation/blob/19.0/content/applications/inventory_and_mrp/inventory/shipping_receiving/daily_operations/dropshipping.rst) and [MTO replenishment](https://github.com/odoo/documentation/blob/19.0/content/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment/mto.rst) and asked whether the project should follow them instead. After re-evaluation the answer is **partial yes**: the inventory/financial leg should adopt standard Odoo, but the workflow leg should keep the configurable pipeline.

### What we are now layering on top of the configurable pipeline

1. **Gearment-POD pipeline gets standard Dropshipping plumbing.**
   - Add `purchase` to `multichannel_hub_core` depends.
   - Seed Gearment as a `res.partner` with `supplier_rank=1`. Products with `x_gearment_sku` set get the Dropship route on their Inventory tab and Gearment in `seller_ids`.
   - SO confirmation now auto-creates a real `purchase.order` (vendor = Gearment) and a `stock.picking` of type Dropship (Partners/Vendors → Partners/Customers).
   - The `gearment_adapter.push_order()` REST call relocates from `_write_pipeline_state` hook (`multichannel_hub_fulfillment/models/sale_order.py:63-115`) to a new `purchase.order._inherit` extension's `action_confirm` override. PO confirm → Gearment REST → stamp `x_gearment_outbound_ref` on the SO + advance `order.pipeline.state` to `Pushed`. Dropship picking done → advance pipeline to `Fulfilled`.
   - The `order.pipeline` "Gearment POD" stays as a thin **status overlay** driven by hooks on the standard PO/picking, NOT a parallel state machine.

2. **`vn_internal_production` pipeline gets standard MTO plumbing.**
   - Add `mrp` to `multichannel_hub_core` depends.
   - Enable MTO route on products on `vn_internal_production`. Each gets a minimal pass-through BOM (1 finished good ← 1 phantom component) — auto-created via wizard to avoid master-data bloat.
   - SO confirmation auto-creates `mrp.production`. New `multichannel_hub_core/models/mrp_production.py` (`_inherit = 'mrp.production'`) syncs the SO's `order.pipeline.state` at boundaries only: MO `confirmed` → pipeline=`CHỜ FILE`; MO `done` → pipeline=`VN-Fulfilled`.
   - **The 17 VN PD/BA workflow stages (CHỜ DUYỆT, ĐÃ GỬI PROOF, VN-Dish, VN-Dish NG, [Fix]VN-Dish, VN-SP mới, VN-Apron, VN-Handkerchief, VN-Packed, VN-Packed 1, …) remain in `order.pipeline` and are advanced manually through the existing UI.** `mrp.production`'s 6-state model (draft/confirmed/progress/to_close/done/cancel) cannot represent them — the flexibility argument from the original §Decision still holds for these stages.

### Why this does not contradict the original Owner direction

Owner direction 2026-04-26 was *"Don't use `mrp.production` yet. Build a configurable pipeline that users define and attach to products."* — emphasis on **yet** and on **user-configurable workflow**. The amendment honors both:

- The configurable pipeline remains the source of truth for workflow state. The 17-stage VN pipeline is unchanged. Pipeline-versioning, transition-log audit, per-stage resource assignment, FR-017 write-defense — all unchanged.
- `mrp.production` enters the picture only as a **lifecycle anchor** at two boundary points (initial / terminal), not as the workflow engine the original ADR rejected.
- Alternative 1 from the original §Decision (hardcoded `mrp.production.x_substate` enum) is still rejected — the 17 VN stages stay editable seed data, not Python enums.

### Why this is worth doing now (and was wrong to skip earlier)

- **Inventory dashboards.** The standard Odoo Inventory Overview's "Dropship" card and Manufacturing Overview's "To Process" card become accurate. The custom Operations Dashboard (P1-DASH-MERGE) does not need to re-implement these.
- **Accounting integration.** Standard PO confirmation books the COGS journal entry on Gearment dropships. MO `done` books WIP→FG on internal production. Without these, the accounting team must back-fill manually for every order.
- **Stock moves audit.** Dropship `stock.picking` (Vendors→Customers) gives a real audit row for every Gearment fulfillment that the custom `sale.order.fulfillment.tracking_state` field cannot.
- **Upgrade safety.** When Odoo 20 ships, standard routes / `purchase.order` / `mrp.production` are guaranteed-supported migration paths. The custom-only design has no such guarantee.
- **Cost was over-estimated in the original ADR.** "Couples to MRP infrastructure that isn't otherwise warranted" (alt 2/3 rejection) reads now as conflating *mrp.production-as-lifecycle-anchor* with *mrp.routing+workcenter-as-workflow-engine*. The first is cheap; only the second is heavy. The amendment uses the first only.

### Cost we are accepting

- **Two state machines per order.** `mrp.production.state` + `order.pipeline.state` for internal-production orders; `purchase.order.state` + `stock.picking.state` + `order.pipeline.state` for Gearment-POD orders. Sync logic lives in two new `_inherit` extensions and must be kept correct via tests (P1-DROP-CALLSITE, P1-MTO-SYNC).
- **In-flight order migration.** Existing Gearment-POD orders with `x_gearment_outbound_ref` set predate the dropship-route change. The new code path checks the field first and treats those as "already pushed, skip PO creation." Documented in P1-DROP-CALLSITE.
- **Test surface widens.** Existing P1 tests that assert "PO is not created" / "MO does not exist" must be updated. Estimated ~10–15 test changes across `multichannel_hub_*/tests/`.
- **BOM seed-data surface.** Every `vn_internal_production` product needs a BOM. Pass-through BOM is acceptable; auto-creation wizard mitigates master-data bloat.

### Slice plan

The 6 code slices (`P1-DROP-DEPS` → `P1-DROP-SEED` → `P1-DROP-CALLSITE` → `P1-MTO-DEPS` → `P1-MTO-SEED` → `P1-MTO-SYNC`) plus this doc-only prep slice (`P1-DROP-MTO-DOC`) live in [`.claude/plans/006-master-plan-tracking.md`](../../../.claude/plans/006-master-plan-tracking.md) Phase 1 §"P1 Hybrid dropship + MTO re-architect." Each runs the standard MP006 9-phase loop. Sequence: dropship branch first (smaller scope, isolated to mhf), then MTO branch.

### Re-evaluation trigger documented

Verbatim 2026-05-03 owner prompt: *"About current Fulfillment pipelines, let check for current implemented approaches and these documents: for gearment_pod — [dropshipping.rst]; For internal_production — [mto.rst]. Seem we need to follow this already supported by Odoo instead of create something new. Recheck for these."* — captured in [`specs/006-master-plan/findings.md`](../findings.md) §Re-evaluation 2026-05-03.

## Revision history

- **2026-04-26**: Initial authoring. Accepted same day. Combines former state-machine ADR-010 + WC-reassignment ADR-011 per Owner direction "WC reassignment should follow the same approach." Recommended answers from `state-machine-questions.md` v2 Q1-Q9 and `wc-reassign-governance-questions.md` v2 Q1-Q5 are baked in (Owner accepted recommendations: "Go with your recommendation first, we'll comeback if thing changed or have issues").
- **2026-05-03**: Amendment "Hybrid with standard Odoo dropship + MTO routes" appended. Accepted same day via `AskUserQuestion`. Adds `purchase` + `mrp` to mhc deps; layers standard PO/MO/Dropship plumbing under the configurable pipeline as a lifecycle anchor; pipeline machinery, 17 VN seed stages, versioning, and FR-017 write-defense remain canonical. Authorizes P1-DROP-* and P1-MTO-* slice family.
