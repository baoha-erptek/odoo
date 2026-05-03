# MP006 — Findings, surprises, and open items

This file is the project's running log of *non-obvious* discoveries during MP006 implementation. Per the playbook (Phase 8 Learn), update this file when something surprised us, when an ADR needs a re-evaluation note, or when the playbook itself broke and we had to escalate.

For routine slice notes, use the tracker (`.claude/plans/006-master-plan-tracking.md`). For architectural decisions, use an ADR. Use *this* file for the in-between: re-evaluations of past decisions, gotchas that survived a slice but warrant flagging for the next contributor, and contradictions between docs that took us a turn to resolve.

---

## Re-evaluation 2026-05-03 — Hybrid dropship + MTO under ADR-010

**Trigger:** Owner question 2026-05-03: *"About current Fulfillment pipelines, let check for current implemented approaches and these documents: for gearment_pod — [Odoo 19 dropshipping.rst]; For internal_production — [Odoo 19 mto.rst]. Seem we need to follow this already supported by Odoo instead of create something new. Recheck for these."*

**What we found:**

- The current Fulfillment pipeline (mhc + mhf) is **100% custom**. Zero use of `purchase`, `mrp`, `stock.route`. Replaced by `order.pipeline` + `order.pipeline.state` + `order.pipeline.transition.log` + `pipeline.team` + `sale.order.x_pipeline_*` extensions.
- This was deliberate per ADR-010 (Accepted 2026-04-26) under owner direction *"Don't use mrp.production yet."* The 17-stage VN production pipeline cannot be expressed in `mrp.production`'s 6-state model and was the primary reason for the custom design.
- Odoo 19 standard dropshipping (Purchase + Dropship route) and standard MTO (Purchase + MRP + MTO route) **do** cover the inventory/financial/audit half of what we built — just not the workflow half.

**Decision (Owner 2026-05-03 via `AskUserQuestion`):** Path B (Hybrid). ADR-010 amended, not superseded. Standard Odoo plumbing layered under the configurable pipeline as a lifecycle anchor.

- Gearment-POD pipeline → standard Dropship route. Real `purchase.order`. Real dropship `stock.picking` (Vendors→Customers). `gearment_adapter.push_order` REST call relocates from pipeline-transition hook to `purchase.order.action_confirm`.
- `vn_internal_production` pipeline → standard MTO route. Real `mrp.production`. Pipeline syncs to MO state at boundaries only (MO confirmed → CHỜ FILE; MO done → VN-Fulfilled). Mid-stage transitions remain manual.
- ADR-010 §"Amendment 2026-05-03" appended; ADR-007 reconfirmed (sibling stays canonical, dropship picking fields become inputs to the sibling, not replacements).

**Why the original ADR-010 was right and wrong simultaneously:**

- **Right** about the workflow half. `mrp.production`'s 6-state model is too coarse for the 17 VN PD/BA stages (CHỜ DUYỆT, ĐÃ GỬI PROOF, VN-Dish, VN-Dish NG, [Fix]VN-Dish, VN-SP mới, VN-Apron, VN-Handkerchief, VN-Packed, VN-Packed 1, …). User-configurable pipelines + versioning + transition-log audit are still net-positive vs hardcoding.
- **Wrong** about the inventory/financial half. The original §Alternatives rejection of "reuse `mrp.routing` + `mrp.workcenter`" conflated *`mrp.production`-as-lifecycle-anchor* with *MRP-as-workflow-engine*. The first is cheap; only the second is heavy. The amendment uses the first only.

**Cost being accepted:**

- Two state machines per order (sync hooks must stay correct via tests).
- In-flight Gearment-POD orders need migration handling — new code path checks `x_gearment_outbound_ref` first and treats those as "already pushed, skip PO creation."
- ~10–15 existing tests need updates that asserted "PO not created" or "MO does not exist."
- BOM seed-data surface for `vn_internal_production` products — pass-through BOM is acceptable; auto-creation wizard mitigates master-data bloat.

**Slices authorized:** P1-DROP-DEPS → P1-DROP-SEED → P1-DROP-CALLSITE → P1-MTO-DEPS → P1-MTO-SEED → P1-MTO-SYNC. Sequential, dropship branch first. See tracker §"P1 Hybrid dropship + MTO re-architect."

**Plan file:** `/home/odoo/.claude/plans/about-current-fulfillment-pipelines-snuggly-newell.md`.

---

## P1-DROP-DEPS dep clarification 2026-05-03

**Trigger:** Phase 0 dispatch for P1-DROP-DEPS surfaced a contradiction between ADR-010 amendment text and the slice exit criterion.

- ADR-010 amendment §"What we are now layering on top of the configurable pipeline" §1 said *"Add `purchase` to `multichannel_hub_core` depends."*
- Tracker row P1-DROP-DEPS exit criterion said *"Dropship route exists + `active=True`."*
- The Dropship `stock.route` (`stock_dropshipping.route_drop_shipping`) is defined in `addons/stock_dropshipping/data/stock_data.xml`, not in `purchase`. `purchase` alone does not register the route, the dropship `stock.picking.type`, or the dropship `stock.rule`.

**Resolution (Owner 2026-05-03 — Path A):** Treat ADR-010's "purchase" as shorthand. The actual dep is `stock_dropshipping`, which transitively pulls `sale_purchase_stock` → `purchase` + `sale_stock` + `stock` + `sale` + `purchase`. ADR-010 amended in place (no new ADR; no semantic change — dependency closure is identical to the original architectural intent of "use the standard Dropship route"). Tracker row notes amended; slice resumes with `stock_dropshipping` as the explicit dep.

**Why this matters for the next contributor:**

- When an ADR mentions a "standard Odoo route" (Dropship, MTO, etc.), the dep that activates that route is rarely the bare module that owns the route's *consumer code* (`purchase`, `mrp`). It is almost always a higher-level orchestration module (`stock_dropshipping`, `mrp`+`sale_stock` interaction modules, etc.) that registers the route as seed data.
- Phase 0 dispatch is the right place to catch this. Don't paper over the contradiction by adding both `purchase` and `stock_dropshipping`; pick the one that owns the route and let transitive deps do the rest.

**Cost paid:** ~3 minutes of doc patching + 1 owner question. No code rework.

## P1-DROP-SEED — privilege-escalation false positive 2026-05-03

**Context:** During Phase 4 review of P1-DROP-SEED, the security-reviewer agent flagged HIGH-priority privilege escalation: any user with `product.template` write permission can indirectly add a vendor to `seller_ids` and a route to `route_ids` via setting `x_gearment_sku`, with no group gate on the override.

**Triage (orchestrator):** **False positive.** The `write()` override does on the user's behalf what the user can already do directly:

- Anyone with write permission on `product.template` already has write permission on `seller_ids` and `route_ids` (both are inherited from `product` / `stock` / `purchase` standard ACLs — no separate field-level group restriction in Odoo CE).
- The override is a *convenience* / *consistency* mechanism, not a privilege grant. There is no escalation possible: a malicious operator who could set `x_gearment_sku` could equally set `seller_ids = [Command.create({'partner_id': any_partner_id})]` directly via RPC.
- Group-gating `x_gearment_sku` to `sale_team.group_sale_manager` (the agent's recommendation) would *break the operator workflow* described in ADR-010 amendment — product setup is an inventory/operations task, not a sales-management one.

**Resolution:** No code change. Documented here so future security reviewers don't re-flag.

**Pattern for future similar false positives:** "X is privilege escalation" is only true when X grants the user the ability to write a field they couldn't otherwise write. CRUD-override slices that compose existing fields based on a single trigger field rarely qualify — but the agent's reflex is to flag them regardless. Triage by checking whether the trigger field grants new write capability vs. orchestrating existing capabilities.

**Cost paid:** ~5 minutes orchestrator triage + this finding. Tracker note + commit body cite this finding by section.

## P1-DROP-SEED — Odoo 19 test-API drift 2026-05-03

Two Odoo 19 API gotchas surfaced while landing tests for this slice. Both pre-known (memory `feedback_odoo19_test_gotchas.md`) but worth re-confirming because they bit on the first run:

1. **`product.template.type='product'` rejected.** The `type` Selection no longer accepts `'product'` — only `'consu'`, `'service'`, etc. Replacement: set `is_storable=True` on the template. Test factory used both `type='product'` AND `is_storable=True`; removing `type` was sufficient (Odoo derived `type='consu'` from the bool).

2. **`recordset.refresh()` is gone.** Replacement: `invalidate_recordset()`. Test-helper trickle: a Form-save round-trip test used `product.refresh()`; trivial fix.

Both gotchas are already in the memory file. No new entry needed; this is just the 5th and 6th confirmation that the rules are real and bite during RED→GREEN. Cost: 2 extra docker test runs (~30s each).

