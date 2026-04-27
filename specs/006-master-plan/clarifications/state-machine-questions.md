---
title: "Clarification Pack — Configurable Order Pipeline (replaces MO state machine)"
date: "2026-04-26"
revision: "v2 — superseded the MO-based state machine framing per Owner direction 2026-04-26"
audience: "Owner + PD lead (primary), Architect (consulted)"
purpose: "Collect the answers needed to write ADR-010 (Configurable Order Pipeline). The original MO state-machine framing is superseded; this pack reframes around user-configurable pipelines on sale.order."
resolves_blockers:
  - Synthesis B2 (was: state machine has no transition graph; now: pipeline configurability not designed)
  - DA post-redpen N2 (VN-Packed 1 + [Fix]VN-Dish — these become editable pipeline states, not hard-coded enums)
  - E2 §8 decision #7 + #11
  - SRS REQ-PRO-03 (semantics column missing → reframed as default seed pipeline)
how_to_use: |
  Read the Context section. Answer Q1–Q9 (mark + initials + date).
  Hand to architect to write `../adrs/ADR-010-configurable-order-pipeline.md`.
estimated_session: "60 min Owner + PD"
---

# Context (read first)

**Original framing (now superseded)**: The synthesis treated the 17 Vietnamese sub-states from E2 §6 as a hard-coded state machine on `mrp.production.x_substate`, requiring an explicit transition graph (DAG), conditional path rules, and rework-loop semantics.

**Owner's clarification (2026-04-26)**:

> Don't use `mrp.production` yet. Build a **configurable pipeline** that users define and attach to products. The pipeline lives on `sale.order`, not on `mrp.production`. Default order status is `draft` for new orders. Historical orders that are already done get `state='done'` and the pipeline state can be blank or editable based on the user's choice.

This means:
- The 17 sub-states from E2 §6 become **one default seed pipeline** (probably named "Vietnam Internal Production"), not the only state machine.
- Each shop / product family / category can have its own pipeline.
- Stages within a pipeline are user-editable through admin UI.
- `sale.order.state` (draft / sent / sale / done / cancel) stays as the native Odoo field.
- A new field `sale.order.x_pipeline_state_id` (M2O → `order.pipeline.state`) tracks the current sub-state within the chosen pipeline.

This pack collects the design decisions needed to model that.

---

# Section A — Pipeline scope and assignment (3 questions)

## Q1. What's the assignment scope for pipelines?

| Option | Where pipelines attach |
|---|---|
| **A** | Per `product.template` (each product can have its own pipeline) |
| **B** | Per `product.category` (all products in a category share one pipeline) |
| **C** | Per `product.template` with category-level default (product overrides category) |
| **D** | Per shop (one pipeline per `etsy.shop`, applied to all orders from that shop) |
| **E** | Other — describe |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend C* — gives flexibility (per-product when needed) without forcing every product to be configured (category default fills the gap).

---

## Q2. What happens when an order has multiple line items with DIFFERENT pipelines?

| Option | Behaviour |
|---|---|
| **A** | Order picks the pipeline of the first / dominant line item (warning shown to user) |
| **B** | Order has multiple `x_pipeline_state_id` slots — one per line item — and the order is "done" only when all line states are terminal |
| **C** | Forbid mixed-pipeline orders at order-confirmation time (user must split into multiple orders) |
| **D** | Order picks the pipeline manually (user chooses; default = first line item's pipeline) |
| **E** | Other |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Note*: B is the most accurate but increases UI complexity. D is the most flexible. A is the simplest. Spec 003 design will benefit from a clear answer here.

---

## Q3. Can a `sale.order` change its pipeline after creation?

| Option | Behaviour |
|---|---|
| **A** | Yes, freely — admin can reassign pipeline at any time; current `x_pipeline_state_id` resets to first stage of new pipeline |
| **B** | Yes, but only while `sale.order.state = 'draft'` |
| **C** | No — pipeline is fixed at order confirmation |
| **D** | Only by admin role with audit log entry |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

---

# Section B — Pipeline editing semantics (3 questions)

## Q4. Who can edit a pipeline definition (add/remove/rename stages)?

| Option | Authority |
|---|---|
| **A** | Admin only |
| **B** | Admin + PD lead |
| **C** | Admin + PD lead + per-stage permission (e.g., MP can rename a "design approval" stage) |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

---

## Q5. What happens to in-flight orders when their pipeline definition is edited?

| Option | Behaviour |
|---|---|
| **A** | Pipeline definitions are **versioned**. Orders snapshot the pipeline version at confirmation time and use that version forever. New orders use the latest version. |
| **B** | Pipeline definitions are **mutable in place**. In-flight orders see the new stages immediately; the system tries to match the order's current stage to a stage in the new definition by name (orphans go to a manual reconciliation queue). |
| **C** | Pipelines are mutable in place but in-flight orders are **frozen** — they keep their current stage and are excluded from any new automation referencing newer stages, until manually finished. |
| **D** | Forbid editing a pipeline that has any in-flight orders using it. |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A* — versioning is the cleanest pattern for long-lived orders and matches Odoo's account-move pattern (lock once posted). It does require a migration story for the seed pipeline as people add stages.

---

## Q6. Can stages within a pipeline be reordered after orders have used them?

| Option | Behaviour |
|---|---|
| **A** | Yes (subject to Q5's answer about in-flight orders) |
| **B** | No — stages can be added or removed but never reordered (preserves historical analytics) |
| **C** | Yes for new pipeline versions only (with Q5=A versioning); in-flight orders unaffected |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

---

# Section C — Transitions (2 questions)

## Q7. Are stage transitions free-form (any → any) or DAG-enforced?

| Option | Transition rules |
|---|---|
| **A** | **Free-form**: user can move an order to any stage at any time. Audit logs record what happened. Simple to implement, easier to recover from "wrong-stage" errors. |
| **B** | **DAG-enforced**: pipeline definition includes allowed `from_stage_ids` per stage. UI only offers valid next stages. Stricter; matches "real" state-machine semantics. |
| **C** | **DAG with admin override**: B by default; admin role can force any transition with audit log. |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A or C*. Free-form (A) is what the Owner's clarification suggests ("can be blank or editable"). DAG-enforced (B) is more rigorous but adds friction; pure DAG would block the team from fixing data errors without code intervention.

---

## Q8. Can stages auto-advance based on triggers (e.g., "when payment received" → next stage)?

| Option | Behaviour |
|---|---|
| **A** | Yes — pipeline stage definition can include an optional Python condition / server action that auto-advances the order |
| **B** | Yes, but only for a fixed set of built-in triggers (payment received, file uploaded, tracking imported) — no Python evaluation |
| **C** | No — all transitions are manual |
| **D** | Phase 1 = manual only (C); add auto-triggers in Phase 2 (B or A) |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend D* — keeps Phase 1 scope small. Spec 003 ships the data model + manual UI; Phase 2 layers in triggers when there's a clear list of what to auto-advance.

---

# Section D — Default seed pipeline (1 question)

## Q9. Should we pre-seed the system with the 17 Vietnamese sub-states from E2 §6 as the default pipeline, or start blank?

| Option | Seed |
|---|---|
| **A** | **Yes — pre-seed** with the 17 stages (CHỜ FILE → … → VN-Fulfilled) as a pipeline named "Vietnam Internal Production". Shops/products start assigned to it; admin can replace. |
| **B** | **No — start blank.** Empty `order.pipeline` table. Admin must create at least one pipeline before any order can have a sub-state. (Native `sale.order.state` still works.) |
| **C** | Pre-seed as a **demo data** record (loaded only when `etsy_integration` is installed in demo mode). Production installs start blank. |
| **D** | Pre-seed but **mark as draft** — admin must approve before it becomes assignable. |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend A* — the team already operates with these 17 stages today; not pre-seeding forces them to recreate the configuration on day 1. The "VN-Packed 1", "[Fix]VN-Dish" semantics issues from the original DA report become **editable defaults** — if the team disagrees with a stage name or wants to delete one, they edit the pipeline definition. No code change needed.

---

# What happens after this is answered

1. Architect writes **ADR-010** (renamed: "Configurable Order Pipeline"; **NOT** "MO State Machine") with the answers locked in.
2. SRS v2.2 §7 REQ-PRO-03 reframed: instead of "17 colored production sub-states," it becomes "Configurable order pipeline; default seed pipeline matches the 17-stage Vietnamese internal production flow." Add new REQ-PIP-01..06 for pipeline config + state field + assignment rules + transition policy + edit semantics + default seed.
3. E2 v1.2 §6 reframed: the 17-state list is presented as the *default* not the *only* — owner-friendly Vietnamese explanation that "the system lets you change these."
4. Spec 003 data-model.md adds:
   - `order.pipeline` model (name, description, version, is_active)
   - `order.pipeline.state` model (pipeline_id, name, sequence, is_terminal, optional from_stage_ids per Q7)
   - `sale.order.x_pipeline_id` (M2O → `order.pipeline`, computed from product/category per Q1; manually overridable per Q3)
   - `sale.order.x_pipeline_state_id` (M2O → `order.pipeline.state`)
   - `product.template.x_default_pipeline_id` and/or `product.category.x_default_pipeline_id` per Q1
   - `order.pipeline.transition.log` (audit; per Q4 + Q7)
5. Default seed pipeline migration script (per Q9 if A or D) loaded as `data/order_pipeline_seed.xml`.
6. Historical orders migration: existing `sale.order` records with `state='done'` get `x_pipeline_state_id = NULL` (per Owner's note "can be blank or editable").

---

# What this REMOVES from the original synthesis

The following items from the original `state-machine-questions.md` are no longer needed:

- ❌ The 14×14 transition matrix (Q9 in v1) — replaced by Q7 (free-form vs DAG)
- ❌ "What does VN-Packed 1 mean?" — became user-editable; no need to define in code
- ❌ "What triggers `[Fix]VN-Dish`?" — same; admin creates rework stages as needed
- ❌ Backward-jump policy — Q7 covers it (free-form means yes; DAG means depends on definition)
- ❌ "Are there hidden states?" — N/A; admin adds them as needed

The risk that prior DA-N2 raised ("VN-Packed 1 is undefined") is now mitigated by **deferring the definition to runtime user configuration** instead of compile-time code. The risk shifts from "wrong code" to "wrong configuration", which is recoverable.

---

# Open questions NOT in this pack (deferred)

- Multi-technique product routing (DA N6 / synthesis M2) — becomes "can a product be in multiple categories with different default pipelines?" — answer per Q1+Q2; deeper design in Spec 003.
- Reporting / KPI on stage-by-stage durations — Phase 2 analytics.
- Stage SLA enforcement (e.g., "alert if order is in stage X for >Y hours") — Phase 2; can be a separate ADR if/when needed.
