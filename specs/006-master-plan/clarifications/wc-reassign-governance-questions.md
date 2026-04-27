---
title: "Clarification Pack — Configurable Resource Assignment (folded into Configurable Pipeline)"
date: "2026-04-26"
revision: "v2 — superseded the MRP-routing-audit framing per Owner direction 2026-04-26"
audience: "Owner + PD lead (primary), Architect (consulted)"
purpose: "Collect the answers needed to fold work-center assignment into ADR-010 (Configurable Order Pipeline). The original MRP-based routing-audit framing is superseded."
resolves_blockers:
  - Synthesis H1 (WC reassignment governance — now: pipeline-stage-to-resource assignment configurability)
  - DA post-redpen N3 (no audit trail / no sign-off — now: pipeline-stage edits are audited via the same mechanism as pipeline edits)
  - E2 §8 decision #12
how_to_use: |
  Read the Context section. Answer Q1–Q5 (mark + initials + date).
  Hand to architect to fold into `../adrs/ADR-010-configurable-order-pipeline.md` (no separate ADR-011 needed under the new design).
estimated_session: "20 min Owner + PD"
---

# Context (read first)

**Original framing (now superseded)**: The synthesis treated WC reassignment as a `mrp.routing` reassignment problem requiring an audit-log model (`mrp.routing.assignment.change`), `effective_date_start/end` semantics, lock-on-progress rules, and Owner sign-off cadence — leading to a proposed standalone ADR-011.

**Owner's clarification (2026-04-26)**:

> Follow the same approach as the state machine — configurable. User configures the flow and applies it for product category or product.

This means **work-center reassignment is not a separate concern** — it's the same configuration pattern as the order pipeline. Work-centers (or "stages", or "teams handling each stage") are attributes of pipeline stages, not a separate routing model.

Concretely:
- Pipeline stages (from ADR-010) carry an optional `responsible_team_id` (or `workcenter_id`) per stage.
- Reassigning a category to a different work-center = editing the pipeline stage, OR assigning a different pipeline to the category.
- Audit log = the same one used for pipeline edits.
- No separate `mrp.routing.assignment.change` model. No separate ADR-011.

This pack collects the few remaining decisions specific to the resource-assignment slice.

---

# Section A — Resource model on pipeline stages (2 questions)

## Q1. What "resource" do pipeline stages carry?

| Option | Field on `order.pipeline.state` |
|---|---|
| **A** | `responsible_team_id` (M2O → `crm.team` / a custom `pipeline.team`). Lightweight; matches how Odoo handles most ownership. |
| **B** | `workcenter_id` (M2O → `mrp.workcenter`). Reuses Odoo MRP infrastructure; couples pipelines to MRP setup even when MRP is not otherwise used. |
| **C** | `responsible_user_id` (M2O → `res.users`). Person-level; useful for small teams. |
| **D** | `responsible_team_id` AND optional `responsible_user_id` (team owns the stage; specific user can be assigned per order) |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A* (or D) — the Owner's clarification said "don't use `mrp.production` yet"; that suggests staying away from MRP models too. A custom `pipeline.team` model (or reusing `crm.team`) is decoupled from MRP and easy to migrate to MRP later if needed.

---

## Q2. Is the resource assignment per-pipeline-stage (one resource per stage) or per-order-stage (resource can be overridden per order)?

| Option | Granularity |
|---|---|
| **A** | Per-pipeline-stage only — every order in stage X is automatically owned by the stage's resource |
| **B** | Per-pipeline-stage default + per-order override — order-level reassignment is allowed by admin |
| **C** | Per-order required — every order must explicitly assign a resource at every stage transition |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend B* — matches the configurable-pipeline philosophy (defaults + overrides).

---

# Section B — Lock semantics for in-flight orders (1 question — the one DA-N3 cared about)

## Q3. What happens when a pipeline stage's resource is reassigned, and there are in-flight orders currently in that stage?

| Option | Behaviour |
|---|---|
| **A** | **In-flight orders keep the OLD resource** (snapshot at order arrival in stage). New orders entering the stage get the NEW resource. Matches the pipeline-versioning pattern from ADR-010 Q5=A. |
| **B** | **In-flight orders move to the NEW resource immediately.** Cleaner UI but creates handover work for the new owner. |
| **C** | **Forbid resource reassignment while orders are in-flight in that stage** — admin must wait until queue is empty. |
| **D** | **Allow with explicit override** — UI shows "N orders in flight; reassign anyway?" — default behaviour is A. |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A or D*. DA post-redpen N3's costing/accounting concern dissolves under A — no labor split across resources. Under D, the admin can opt into B when they understand the implication.

---

# Section C — Audit trail (1 question)

## Q4. Where do resource-assignment changes appear in the audit trail?

| Option | Mechanism |
|---|---|
| **A** | **Same `order.pipeline.transition.log`** that ADR-010 already creates — add a `change_type` enum (`stage_added`, `stage_removed`, `stage_renamed`, `resource_changed`, `transition`). One model, one query, one audit view. |
| **B** | Separate `pipeline.resource.change.log` model — keeps resource changes isolated from pipeline-structure changes |
| **C** | Use `mail.message` on the pipeline record — free chatter trail; lighter weight |
| **D** | A + C combined — A is source of truth; C is the user-facing chatter |

**Architect / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A* — keeps ADR-010 from spawning satellite log models. One fact table for everything that happens to a pipeline.

---

# Section D — Reversibility / cooling-off (1 question)

## Q5. If a resource reassignment was made in error, what's the recovery mechanism?

| Option | Recovery |
|---|---|
| **A** | Just create another reassignment back to the old resource. Audit shows both changes. No special "undo" mechanism. |
| **B** | "Undo" button restores the previous resource within a 1h cooling-off window. After 1h, treat as A. |
| **C** | Reassignments are not reversible — the audit trail records the old state but the active state moves forward only. (Strongest discipline.) |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A* — simplest, no extra model state, easy to explain to admin users.

---

# What happens after this is answered

1. Architect folds answers into **ADR-010 (Configurable Order Pipeline)** under a new section "§N. Resource assignment per stage."
2. **No separate ADR-011 written.** The original ADR-011 slot is marked "merged into ADR-010 per Owner direction 2026-04-26."
3. Spec 003 data-model.md adds:
   - `pipeline.team` (or `crm.team` reuse, per Q1) with name + members
   - `order.pipeline.state.responsible_team_id` (and optionally `_user_id` per Q1=D)
   - `sale.order.x_responsible_team_id` (override per Q2)
   - `change_type` field on `order.pipeline.transition.log` (per Q4)
4. SRS v2.2 §7 REQ-PRO-09 reframed: "Resource assignment is part of the configurable pipeline (REQ-PIP-*)" instead of "mrp.routing reassignment with audit log."
5. E2 v1.2 §3.1 footnote updated: "Trưởng nhóm xếp đội phụ trách cho từng giai đoạn pipeline; có thể đổi cho danh mục sản phẩm hoặc sản phẩm cụ thể."

---

# What this REMOVES from the original pack

The following items from the v1 pack are no longer needed:

- ❌ "How often does WC reassignment happen?" — N/A; configuration changes happen on demand
- ❌ "Should reason / justification be mandatory?" — covered by audit log (Q4); no separate workflow
- ❌ "Effective date model" — N/A; changes are immediate; in-flight behavior covered by Q3
- ❌ "Snapshot field `x_routing_id_at_creation`" — replaced by the pipeline-versioning pattern in ADR-010 Q5
- ❌ Separate `mrp.routing.assignment.change` model — collapsed into `order.pipeline.transition.log`

---

# Open questions NOT in this pack (deferred)

- Workload balancing (assigning orders to specific team *members* based on capacity) — Phase 2 feature; needs separate design.
- Resource calendar / availability (e.g., "team X is on holiday — auto-reassign new orders to team Y") — Phase 2.
- KPI reporting (orders per resource, stage durations per resource) — Phase 2 analytics.
