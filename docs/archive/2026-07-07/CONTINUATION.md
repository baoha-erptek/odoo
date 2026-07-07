# Session continuation prompt — "achieve Màn hình Odoo state"

> Paste the block below into a new session to resume. Self-contained; a fresh
> session can pick up without re-deriving context. Written 2026-06-21.

```
Continue the "achieve Màn hình Odoo state" work on the odoo19_esty project. This
is a resumption — prior session shipped a lot. Work LOCAL-FIRST (db namco_odoo19,
container namco_odoo19, http://localhost:8169, admin/admin) and follow the
TFV/openeducat methodology (design-first via odoo-functional-mockup for UI).

BRANCH: feature/006-master-plan-coding (do NOT branch; this is the long-lived MP006 branch).

READ FIRST (the state of truth):
- docs/owner/business-flows/COMPARISON_MOCKUP_VS_ACTUAL_v2.md  (code-grounded gap matrix + Phase-D backlog with done/deferred status)
- docs/owner/business-flows/CONTRACT-v1.0.md  (UI + functional contract + UAT gates, frozen at 6 shipped slices)
- docs/design/HATAFA.design.md  (design tokens; design-md lint clean)
- docs/owner/design-system/{MU_SYSTEM.md, FORM_CURATION_GUIDE.md, PHASE_3_SCOPE.md, findings.md}
- The plan: /home/odoo/.claude/plans/deeply-check-for-docs-owner-business-flo-zesty-canyon.md

ALREADY DONE (shipped + Phase-2 ORM tested + install-clean; combined 3-module
sweep = 12 tests 0 failed; commits on the branch):
- D#1 buyer-note->chatter (b41c0f3), D#2 Gearment API/Webhook views (3d4f42e),
  D#3 Pipeline tab+transition wizard+"In Lại" reprint state (a818449),
  D#4 channel-status kanban (5422544), D#6 listing error-surface (c66ba56),
  D#7 after-sales refund ticket etsy.order.ticket (5d8c5e6).
- Phase A audit + Phase B contract/DESIGN.md + 17 staging screenshots + scripts/seed_demo_local.py.

REMAINING TASKS (do in this order, each as an MP006 9-phase slice: RED->GREEN->
verify -u --stop-after-init->commit; commit msg "[module] type(scope): ..."):
1. Phase C — product.template Tier-3 curation: hide standard clutter (Routes/MTO,
   Logistics, Description-for-receipts/delivery) behind groups="base.group_no_one"
   on the product form, per FORM_CURATION_GUIDE. RUN odoo-functional-mockup FIRST
   (baseline->taste->craft->diff) — owner wants design-first. Reuse the shipped
   mu_tokens.scss scoping pattern. Beware: reviewers misread field-vs-view groups
   (see memory feedback_reviewer_field_vs_view_groups_misread) — grep the model
   field defn before applying fixes. Also close P-DS-3b (sale.order/stock.picking
   audit-first; only curate if a gap is confirmed).
2. D#8 — Fulfillment Tracking Detail form (Flow 3b #5): needs NEW fields on
   sale.order.fulfillment (gearment_order_ref, webhook timestamps, etsy_pushed
   status) + wiring in services/gearment_webhook_dispatcher.py to populate them,
   + a form view. Medium slice.
3. D#5 — Payload preview tab (Flow 1 #3): LOW priority/optional. A read-only
   computed summary on the etsy-side multichannel.listing of the resolved Etsy
   payload. Must live in etsy_integration (mhc must not import etsy code). Make
   the compute pure/best-effort (no API calls, try/except). Confirm with owner
   it's wanted before building.
BLOCKED (do not build, tracker note only): conversations ingestion — Etsy
   conversations_r OAuth scope forbidden (etsy_oauth.py:37-39, external dep E1).
OWNER DECISION NEEDED: QC checklist + production scan view (Flow 3a #4/#5) — in v1 scope?

FINAL VALIDATION (Phase E, after the above):
- Capture clean local screenshots of D#3 (order Pipeline tab), D#6 (listing
  danger alert when state=error), D#7 (After-Sales ticket form). These were
  deferred last session due to browse friction. Use gstack /browse; FRESH login;
  the dev DB shows a "database expired" banner (ignore). GOTCHAS that blocked
  screenshots before: (a) Listings list has a default Editable/Draft filter that
  hides error/published rows — clear facets first; (b) row-click via $B click is
  flaky — use JS .click() on '.o_data_row td.o_data_cell:not(.o_list_record_selector)'
  or snapshot -i @ref; (c) navigate by /odoo/action-<module.xmlid>, open records
  via list->click (NOT /web#id= legacy hash). Seed data via scripts/seed_demo_local.py.
  Note: prior session granted local admin (uid 2) the BA-lead/marketing/BA groups
  so role-gated screens (tickets) are visible in dev.
- Then run gstack /qa autofix on the new surfaces and rework if bugs found.
- Update CONTRACT-v1.0 + v2 audit; sync owner docs to Confluence (commits touching
  docs/owner/** auto-sync via .githooks/post-commit unless [skip-confluence]).

KEY GOTCHAS (learned this work):
- Odoo 19 action URL = /odoo/action-<module.xmlid> (bare xmlid does NOT resolve —
  must be module-qualified).
- Search-view group-by filters: put after <separator/>, NOT inside <group expand>
  (RELAXNG rejects expand on group).
- noupdate=1 seed: NEW records DO load on -u; edits to EXISTING records do not
  (would need a migration).
- Verify with: docker exec namco_odoo19 odoo -d namco_odoo19 -u <module>
  --test-enable --test-tags /<module>:<TestClass> --http-port 8170 --no-http
  --stop-after-init   (the --http-port avoids the in-container port clash).
- pipeline state transitions MUST go through sale.order._write_pipeline_state()
  (direct x_pipeline_state_id writes are blocked by the FR-017 guard).

Start by reading the v2 audit + CONTRACT, then dispatch Phase C (design-first).
```
