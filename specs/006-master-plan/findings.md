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

---

## P1-DROP-CALLSITE pre-implementation reconciliation 2026-05-04

**Trigger:** Phase 0 dispatch for P1-DROP-CALLSITE surfaced three contradictions between ADR-010 amendment, the actual seed, the existing code, and the slice description in the tracker. Per playbook §"When the playbook breaks", STOP and escalate before any code touches the tree.

**Contradictions found:**

1. **Stage codes drift between ADR §9 (original 2026-04-26) and the actual `gearment_pod` seed.** ADR-010 §9 named the four stages "Awaiting Push → Pushed → Awaiting Tracking → Fulfilled"; the seed shipped `draft → quoted → confirmed → shipped`. Amendment §1 then re-cited "Pushed" and "Fulfilled" without noticing the seed had drifted. Net effect: the slice description references state codes that do not exist.

2. **Push-failure semantics ambiguous under PO `action_confirm`.** Existing pre-amendment code rolled the SO pipeline back to `quoted` inside a savepoint and let cron retry. Under PO confirm, two paths are defensible: raise `UserError` (clean transactional story; PO stays `draft`) vs catch-and-log (PO confirm proceeds; cron retries). ADR-010 amendment §"Cost we are accepting" mentions two-state-machine drift as a risk but does not pick a path.

3. **Legacy cleanup scope undefined.** Tracker row says only "Relocate the push call." After relocation, four helpers and one cron become orphans (`_write_pipeline_state` override, `_gearment_push_should_fire`, `_enqueue_gearment_push`, `_cron_retry_stalled_gearment_pushes` + its XML row). Slice could leave them for a later refactor (strict relocation) or remove them in-slice (honest diff).

**Resolution (Owner directive 2026-05-04 — "update related documents first"; orchestrator-recommended triplet 1A / 2A / 3B accepted by absence of pushback):**

1. **1A — Semantic alias, no seed change.** P1-DROP-CALLSITE treats `confirmed` ≡ ADR's "Pushed" and `shipped` ≡ ADR's "Fulfilled". Tests and code reference the existing seed codes. A future `P1-DROP-PIPELINE-RENAME` slice can rename the stages via the standard pipeline UI (auto-versioning per ADR-010 §5) — not in scope here.

2. **2A — Raise `UserError` on push failure.** PO `action_confirm` aborts; the transaction rolls back; PO stays `draft`; SO pipeline does not advance to `confirmed`. Operator re-clicks Confirm on the PO to retry. Chatter messages on the SO are posted via `self.env.cr.savepoint(flush=False)` so the failure is auditable even though the outer transaction rolls back.

3. **3B — Remove orphans in this slice.** Same conventional commit as the relocation: strip `_write_pipeline_state` gearment branch (likely entire override), delete `_gearment_push_should_fire` + `_enqueue_gearment_push`, delete `_cron_retry_stalled_gearment_pushes` + the corresponding XML cron row in `data/ir_cron_gearment_retry.xml`. Keep `action_push_to_gearment` — its body is the actual push and gets called from the new `purchase.order.action_confirm`.

**Why this matters for the next contributor:**

- ADR text aspires to terminology that may have already drifted from the seed. When a slice references a stage code from an ADR, **always grep the seed XML first** — don't trust the ADR alone.
- "Relocation" slices nearly always have orphan-cleanup tails. Phase 0 should grep for callsites of the relocated method and surface dead-code candidates as part of the slice scope, not as a separate slice. Strict relocation that leaves orphans is technical debt by another name.
- Push-failure semantics under a real Odoo state machine (PO confirm) is materially different from a custom hook (where you control the transaction boundary). The hook could swallow + rollback partially; PO confirm can only succeed-or-raise. This is a recurring shape — note for future similar slices.

**Documents updated this turn (no code yet):**

- `specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md` — appended §"Clarifications 2026-05-04 (P1-DROP-CALLSITE pre-implementation)" + revision-history entry.
- This file — section above.
- `.claude/plans/006-master-plan-tracking.md` — P1-DROP-CALLSITE row description expanded with the three resolutions in the Notes column.

**Cost paid:** ~10 minutes orchestrator analysis + ~5 minutes doc edits. Zero code rework. Phase 1 (Plan / RED) blocked behind these reconciliations is now unblocked.


---

## 2026-05-04 — drop-ship E2E demo run on staging (gotchas + ops blockers)

Discovered while building `scripts/e2e_demo_drop_ship_ordertest2.py` and running it against `https://odoo.hatafax.com` / DB `demo_esty`. First run after deploying P1-OPS-DESIGN-LINK + P1-DESIGN-AUTO-GDRIVE: **11/12 sections PASS**.

### Gotchas (each is now load-bearing in the runner script)

1. **`tracking.import.line` field name**: it's `sale_order_id` (Many2one), not `matched_order_id`. The earlier email-fallback runner used the right name — I copy-pasted the wrong one. Caught by `KeyError: 'matched_order_id'` from `_determine_fields_to_fetch`. Fixup: `["state", "sale_order_id", "raw_tracking_number"]` in the `search_read` call.

2. **`gearment.api.log.direction` is NULL on outbound rows.** Only the inbound webhook controller (`controllers/gearment_webhook.py`) sets `direction='inbound'` explicitly; the outbound adapter (`gearment_adapter.push_order`) leaves it NULL. Filter by `endpoint LIKE 'POST /api/%'` to find outbound push attempts. (Could also be argued the adapter should set `direction='outbound'` — small follow-up worth a 5-line fix.)

3. **Direct `write({'x_pipeline_state_id': ...})` with `bypass_pipeline_state_guard` skips the auto-push hook.** The Gearment auto-push lives inside `multichannel_hub_fulfillment/models/sale_order.py:_write_pipeline_state` (post-super hook). When an external script bypasses the FR-017 guard via direct write + ctx, it ALSO bypasses this hook. Symptoms: pipeline state correctly moves to `gearment_pod/confirmed`, but `x_gearment_outbound_ref` stays empty and no `gearment.api.log` row is created. Fix in the runner: explicitly call `sale.order.action_push_to_gearment` after the pipeline write. **Tracker note**: this isn't a bug per se — `_write_pipeline_state` is the canonical entry point — but it's a non-obvious side effect of the bypass-context pattern from the previous email-fallback runner. Worth a docstring on the bypass context behavior.

4. **`_gearment_push_should_fire` gates on `product.template.x_gearment_sku`.** Even when `_write_pipeline_state` IS reached (i.e., not via bypass), the auto-push won't fire if no line's product template has `x_gearment_sku` set (P1-DROP-SEED defaults it via `@api.onchange`/`create`/`write`, but pre-existing demo products may lack it). For demo seeding: either backfill `x_gearment_sku` on the line products before §6, or call `action_push_to_gearment` explicitly to bypass the gate.

5. **Live Gearment endpoint returns HTTP 0/404 for synthetic SKUs.** Expected. The runner now treats "outbound api.log row exists OR x_gearment_outbound_ref set" as evidence the wiring fired — http_status=0 is a valid signal for "the request reached the network and got rejected upstream", and the chatter chain (`Gearment push failed: 404 ... Pipeline rolled back to Quoted; please review and retry.`) is the human-readable trail.

### Ops blockers (operator-side, not code)

These are pre-existing config gaps on `demo_esty` that block §1 and §5 of the runner:

- **Gmail OAuth ICPs on `demo_esty`** are empty: `etsy_integration.gmail_client_id`, `gmail_client_secret`, `gmail_refresh_token`. Without them, the `cron_fetch_etsy_emails` cron silently no-ops (no exception). The runner's §1 falls back to picking the most recent `sales_channel='etsy'` `sale.order` so downstream sections can still demonstrate the pipeline against a known-good order. To get fresh `ordertest2` ingestion: run the OAuth dance once, populate the three ICPs, label 2-3 inbox messages with `ordertest2`, fire the cron via XML-RPC.
- **GDrive folder ICP** `multichannel_hub.design_file_default_gdrive_folder_id` is empty. Slice 2's cron silently no-ops when unset (intentional — see code path in `design.file._cron_sync_approved_to_gdrive`). To enable §5 promotion: set the ICP to a Drive folder ID matching `^[A-Za-z0-9_-]{20,80}$`.

### Suggested follow-ups (not done this session)

- **`gearment_adapter.push_order` should write `direction='outbound'`** on the `gearment.api.log` row it creates (one-line fix; matches the inbound controller's behavior; saves runners and dashboards from filtering by endpoint pattern).
- **Optional `action_push_to_gearment_now()` wrapper** that runs the bypass-friendly pipeline write + explicit push in one call, so the runner doesn't have to know about both hooks. Could deprecate the bypass-context altogether once P1-DROP-CALLSITE relocates the trigger to PO `action_confirm`.
- **Slice 3 (local-blob retention cleanup) was deferred** from P1-DESIGN-AUTO-GDRIVE per the original plan. The `synced_to_gdrive_at` field is in place; a future cron can find rows older than `multichannel_hub.design_file_local_retention_days` (default 7) and clear `design_file` (the blob), preserving the record + `gdrive_file_id` link.

---

## 2026-05-06 — Pre-existing test failure surfaced during P1-MTO-DEPS verification

While running the full `multichannel_hub_core` test suite (271 tests) at slice close, one pre-existing failure showed up: `TestHistoricalSeedT078.test_seed_skips_empty_urls` in `test_design_file_lifecycle.py` — `AssertionError: 1 != 0 : No design.file should be created with empty file_url`.

**Confirmed pre-existing**, not caused by P1-MTO-DEPS:

- Failure reproduces deterministically with the MTO manifest change reverted (manifest at version 19.0.1.0.14, no `mrp` dep, MTO test file removed) — same `1 != 0` against the same test.
- The seed method (`design.file._seed_from_historical_lines` in `models/design_file.py:430`) explicitly guards via `url = (getattr(line, field_name) or '').strip()` then `if not url: continue` — yet a row with `file_url=False` slips through.
- Likely demo / fixture drift: a pre-existing `design.file` with empty `file_url` is being counted by the `('file_url', '=', False)` search domain, regardless of seed behavior. Test asserts post-condition, not delta from the seed call.

**Not blocking** P1-MTO-DEPS (manifest-only slice; my new `TestMtoDep` class passes 2/2). Logged here so the next session touching `design.file` lifecycle picks this up — likely a 1-line fix to either:
- Filter the test's search by `is_seed=True` (only assert about seeded rows), or
- Tighten the seed method to also skip lines whose URL is `False` (not just empty string after `.strip()`), or
- Clean up demo data that introduces the empty-url row.

**ruff not in container**: Phase 5 ruff verification was skipped because `ruff` is not installed in `namco_odoo19` and not on the host. Recommend adding `ruff` to `Dockerfile.base` so future slices can run lint inside the container.

## 2026-05-06 — P1-MTO-SEED surprises (4 reusable patterns)

Encountered while landing P1-MTO-SEED. All four are likely to recur in future slices that touch standard Odoo flags or write Many2many fields to inactive records — capture so we don't re-discover them.

### 1. Cross-module XML overrides on `noupdate=1` records silently skip
`<record id="stock.route_warehouse0_mto" model="stock.route">` inside a fresh `<data>` block (no `noupdate`) in our seed XML did NOT update `active=True`, even on the upgrade path. Root cause: the original record's `ir_model_data` row was created by the `stock` module with `noupdate=1`, and Odoo's loader honors that flag on the *target record's* data row regardless of what `<data noupdate=...>` we wrap our override in. Verified via `psql` showing `active=f` post-`-u`.

**Fix pattern**: route configuration / cross-module flag flips must be done **programmatically** in `post_init_hook` (for `-i`) and a matching `migrations/<version>/post-*.py` (for `-u`). Mirror logic in both. Idempotent guards (`if not route.active:`) keep re-runs safe.

Reusable for: any future slice that needs to flip an `active`, `product_selectable`, `auto_apply`, `is_published`, or similar flag on a standard Odoo seed record.

### 2. Migration version-bump timing trap
If `__manifest__.py` version is bumped BEFORE the corresponding `migrations/<version>/post-*.py` exists, the first `-u` will:
1. See the version change
2. Update database tables
3. Update `ir_module_module.latest_version` to the new version
4. **NOT run the (non-existent) migration**

Subsequent `-u` runs with the migration in place will NOT re-run it because the DB is already at target version. Result: silently broken upgrade path for everyone who already updated.

**Two recovery paths**:
- (a) Bump version AGAIN to the next slot (e.g., `.16` → `.17`) and put the migration there. This is what we did for P1-MTO-SEED — we burned `.16` permanently and shipped under `.17`. Tracker row documents the gap.
- (b) Manually `UPDATE ir_module_module SET latest_version='<prev>' WHERE name='<module>';` then re-run `-u` with the migration in place. Hacky; only works if no users are running production environments yet.

**Preventive habit**: **author the migration script BEFORE bumping the manifest version**. Stage them in the same commit. Verify with `ls migrations/<new-version>/` before any `-u`.

### 3. Many2many `_active_test` filter hides linked-but-inactive records
`product.template.route_ids` (and any Many2many with `_active_test=True` semantics) returns ONLY active records on read. Writing `(4, inactive_route_id)` succeeds — the relation row is created — but `assertIn(inactive_route, product.route_ids)` will fail because the read filters it out.

**Symptom**: test errors like `stock.route(1,) not found in stock.route(614,)` where the missing route is the one with `active=False`. Misleading because it looks like the write didn't happen.

**Fix pattern**: ensure the standard route is **active** (Pattern #1 above) before any wizard / setup code writes it onto a product. The wizard's tests then implicitly verify activation worked.

### 4. `route_ids` domain enforced UI-side only — writes to non-product-selectable routes succeed
The field def `route_ids = fields.Many2many('stock.route', ..., domain=[('product_selectable', '=', True)])` blocks the route from showing in the UI dropdown but does NOT block ORM writes. Standard mrp tests confirm this (`mrp/tests/test_bom.py:836` writes Manufacture even when `product_selectable=False`).

**Implication**: in our wizard we still flip `Manufacture.product_selectable=True` (so admins can manually attach the route via the product form), but if we *only* needed programmatic linking, we wouldn't have to. Knowing this lets future slices skip the flag flip if there's no admin-UI requirement.

## 2026-05-06 — P1-MTO-SYNC: Odoo 19 `mrp.production` lacks `procurement_group_id`

**Discovered while landing P1-MTO-SYNC**. The planner (and a few past tracker entries) assumed Odoo 19 `mrp.production` exposes a `procurement_group_id` Many2one we could walk to `procurement_group_id.sale_ids` for MO→SO linkage. **It does not.**

What `mrp.production` actually has in Odoo 19:
- `production_group_id` → `mrp.production.group` (MRP-internal sibling grouping; backorders, etc.)
- `origin` (Char) — populated by the MTO procurement to the SO name (e.g. `S00042`)
- `move_finished_ids` / `move_dest_ids` — stock-move chain (works but multi-hop)

**Canonical walk for MO → SO in this codebase**:

```python
def _linked_sale_order(self):
    self.ensure_one()
    if not self.origin:
        return self.env['sale.order']
    return self.env['sale.order'].search(
        [('name', '=', self.origin)], limit=1)
```

Sibling MOs on the same SO share the same `origin`, so `search([('origin', '=', so.name)])` enumerates them all.

**Caveats / future hardening**:
- `mrp.production.origin` is unindexed — fine for current MO volumes, may want btree if MO count per database scales.
- `sale.order.name` is unique per Odoo sequence; multi-company isolation comes from sequence-per-company, but if cross-company SOs ever share names the search needs `('company_id', '=', self.company_id.id)` added. Not adding now (YAGNI).
- If we ever need the inverse (SO → MOs) more efficiently, look at `sale.order.procurement_group_id.stock_move_ids.production_id` — that path *does* exist (MO has `move_dest_ids` reverse).

**Implication for future slices**: any code documentation referring to `mrp.production.procurement_group_id` is wrong for Odoo 19. Update the planner default and any ADR that mentions it.

---

### P-UAT-AUTOMATION-2FLOWS — Phase A/B/C authoring (2026-05-31)

**Authoring shipped in 4 commits on `feature/006-master-plan-coding`:**
- `aee31f6de03` — 6 POMs (sale_order_form, design_files_kanban, gearment_quote_wizard, tracking_import_wizard, address_change_request_form, email_log)
- `863add87ef9` — fixtures (extends seed_uat_data + seed_ba_user 4 roles + cleanup_uat_data), Gearment HMAC stub `gearment_webhook_post.py`, `preflight_check.py` wired into globalSetup, asset builder `build_uat_assets.py`, real-order anchor JSON
- `3489926e65c` — Flow-2 spec (8 TCs) + Flow-3 spec (14 TCs)
- `73e0417d9c0` — Phase 4 review fixes (1 CRITICAL + 3 HIGH)

**Verify**: `npx playwright test --list` → 40 tests in 5 files, exit 0.

**Phase D handoff (owner-gated)**:
- Run preflight: `STAGING_ADMIN_PASSWORD=... python3 tests/e2e/fixtures/preflight_check.py`
- Suite run: `cd tests/e2e && npm run test:don-hang-etsy && npm run test:giao-hang && npm run report`
- Defects classify A/B/C per plan file Phase D; A → new `P-UAT-FIX-*` MP006 slice on a branch off `feature/006-master-plan-coding`, full 9-phase loop; B/C → land under this findings.md entry.

**Known shape of expected-skips at runtime**:
- TC-002 (Etsy Test Connection): hits live Etsy GET; cheap but counts.
- TC-006 Address change: auto-skips if seeded ADDR-001 is not is_etsy_order. Follow-up to extend `seed_uat_orders` to mark Etsy-typed.
- TC-DROP-002/003: auto-skip when `GEARMENT_API_KEY` missing (preflight catches).
- TC-DROP-005 webhook: auto-skips when `GEARMENT_API_SECRET` missing.
- TC-ETSY-PUSH-001/002: auto-skip when SO is not `is_etsy_order` (same follow-up as TC-006).

**Mid-slice surprises captured**:
1. `cleanup_uat_data.py` only had `action_cancel` semantics for draft SOs; ConfirmedOrders are deliberately left for owner review.
2. `seed_ba_user.py` refactor changed `BA_USER_PASSWORD=` to the first of 4 lines — backward-compatible because globalSetup parses all `<ROLE>_PASSWORD=` lines now.
3. Real S00007 anchor freezing went into `fixtures/real_order_reference.json` for spec-side reads + preflight verification. If owner advances S00007's pipeline manually, preflight will fail loudly with "x_pipeline_state_id.code drifted".
4. `design_files_kanban._ensureGroupedByState()` heuristic is brittle (reviewer flagged MEDIUM); not fixed — kept as Phase D triage candidate per code-reviewer guidance.

### P-UAT-AUTOMATION-2FLOWS — Phase D start: 3 preflight authoring bugs (2026-05-31)

First Phase D run surfaced 3 classification-B (test-infra) bugs in `tests/e2e/fixtures/preflight_check.py`. All fixed in a single commit; no `custom_addons/` touched.

| Bug | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `PREFLIGHT FAIL: env: missing required keys ETSY_KEYSTRING, ETSY_SHARED_SECRET` | Authoring assumed Etsy creds lived in env. They actually live in `/opt/odoo/secrets/etsy_credentials.json` (encrypted), referenced via `ir.config_parameter['etsy.oauth.credentials_path']` + `['etsy.oauth.fernet_key']`. No code in `custom_addons/` reads those env vars. | Removed `ETSY_KEYSTRING`/`ETSY_SHARED_SECRET` from `REQUIRED_ENV_KEYS`; added new `_check_etsy_oauth_wiring()` that verifies both `ir.config_parameter` keys are populated. |
| 2 | `cron: no active cron matches 'Etsy: Sync'` | `CRON_NAME_FRAGMENTS` used wrong substrings. Actual active crons on staging: `Etsy: API Receipts Sync`, `Etsy: Listing Metadata Sync`, `Etsy: Listing Variant Inventory Sync`, `Etsy: Push Tracking to Etsy`, `Etsy: Download Pending Product Images`, `Etsy: API Log Retention Sweep`, `Etsy: Message Dedupe Retention Sweep`. `Etsy: Fetch Order Emails` is INACTIVE (legacy per API-first pivot 2026-04-13). | Narrowed `CRON_NAME_FRAGMENTS` to `Etsy: API Receipts Sync` + `Etsy: Push Tracking` — the two crons the new specs actually depend on. Dropped `Etsy: Email` (legacy) and over-broad `Tracking` fragment. |
| 3 | `shop-defaults: Invalid field 'token_expires_at' on 'etsy.shop'` | Field name authored from memory was wrong. Real column: `etsy_oauth_token_expires_at` (alongside `etsy_oauth_access_token`, `etsy_oauth_refresh_token`). | Renamed both the search_read fields list and the `.get()` site in `_check_shop_defaults`. |

**Verification**: `python3 tests/e2e/fixtures/preflight_check.py` → exit 0, `PREFLIGHT OK — staging ready for UAT suite`.

**Authoring-bug pattern worth remembering** — when writing a preflight check, the script's own field names / env keys / cron substrings must be cross-checked against actual staging state, not against the developer's mental model. Memory entry candidate for `feedback_odoo19_test_gotchas.md`: "preflight scripts that name-match runtime artifacts (cron names, ORM fields, ir.config_parameter keys, env vars) need a one-time live-staging dry-run before they're declared green — even if the spec authoring agent's plan looks self-consistent."

### P-UAT-AUTOMATION-2FLOWS — Phase D BLOCKER: Playwright auth path fails against staging (2026-05-31)

After unblocking preflight, Phase D-2 (deploy) and Phase D-3 (seed) executed clean:
- 3 modules rsynced + `odoo -u etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment --stop-after-init` exit 0 + container restart
- `npm run seed:ba-user` created 4 role users (uid 5, 28, 29, 30)
- `npm run seed:uat-data` created 4 UAT orders (3311–3314) + email-log dedupe fixture

**Phase D-4 (baseline Flow-1 spec) FAILED on a previously-passing suite**: 4 failed, 10 skipped, 1 passed. All 4 failures share the same root cause and are NOT defects in custom_addons — they are an auth-path regression in `fixtures/odoo-auth.ts` against the current staging build of Odoo 19.

**Symptom**: every `loginAs*()` call ends at `expect(page.locator('nav.o_main_navbar, header.o_navbar').first()).toBeVisible()` timing out, screenshot shows the login form with "Wrong login/password" alert.

**What was tried and ruled out**:

| Hypothesis | Test | Result |
|---|---|---|
| `STAGING_BA_LEAD_PASSWORD` stale | curl POST /web/login with same .env values | succeeds — redirects to /odoo |
| Same creds via Python urllib JSON-RPC `/web/session/authenticate` | direct request | uid=2 success |
| Same creds via Python XML-RPC `common.authenticate` | preflight + seed scripts | uid=2 success (logged every run) |
| Rate-limit / brute-force lockout | 3 rapid Python urllib auths | all 3 succeed |
| `waitForURL` regex too permissive (matches /web/login) | narrowed to `/\/odoo(\/|$|\?|#)|\/web\/(?!login)/` | unchanged |
| Form submission bypasses captcha hook (`data-captcha="login"`) | switched between `button[type="submit"].click()` and JS `form.submit()` | both fail; also `website_cf_turnstile` + `google_recaptcha` are `uninstalled` on staging — no captcha actually loaded |
| Form hidden by `class="oe_login_form d-none"` until passkey-detect JS resolves | added `form.oe_login_form` waitFor visible | unchanged |
| Password not actually filled (passkey JS clears the field) | value-length verify + refill on mismatch | refill did not change outcome |
| Sidestep form entirely via `page.request.post('/web/session/authenticate')` | JSON-RPC body identical to working Python urllib | Odoo returns `odoo.exceptions.AccessDenied` |
| Stale `session_id` cookie poisoning JSON-RPC | `page.context().clearCookies()` before authenticate | AccessDenied unchanged |

**What we know for certain**:
- Credentials are correct (every non-browser auth path accepts them).
- Staging is reachable (preflight + module update + seed scripts all worked).
- No captcha module is installed (`website_cf_turnstile` + `google_recaptcha` both `uninstalled`).
- The failure is browser-context-specific: Python urllib with browser-mimicking UA also succeeds, so it is NOT a nginx UA-block.

**Unknown root cause** (candidates):
1. Odoo 19 added a browser-fingerprint check to `/web/session/authenticate` that headless Chromium fails silently (returns AccessDenied instead of a specific error).
2. A nginx/Cloudflare rule in front of staging that fingerprints headless Chromium (sec-ch-ua: "HeadlessChrome") and either drops the body or rewrites the request.
3. A residual Odoo session state from `globalSetup` (which spawns XML-RPC seed scripts) that interferes with browser-side auth — though `clearCookies()` did not help.

**Phase D STOPPED here per playbook §"When the playbook breaks"**. Continuing to guess at fixes burns context without converging.

**Recommended next-session steps** (any one suffices):
- Run `tests/e2e` from the staging host itself (Option 2 from earlier dispatch question) — same-host browser to same-host Odoo eliminates nginx/Cloudflare fingerprint suspects.
- Hand to `e2e-runner` agent with this findings entry + the trace.zip artifact to deep-dive.
- Switch `loginAs` to use an out-of-band XML-RPC authentication: call `/xmlrpc/2/common.authenticate` from Node (or Python helper), then plant the resulting `session_id` cookie on the browser context via `page.context().addCookies()`. This is a known Odoo E2E pattern but needs the XML-RPC→session-cookie bridge wired.
- Owner side: temporarily disable any WAF / rate-limit rule on `/web/login` + `/web/session/authenticate` on staging and re-run; if it passes, the suspect is confirmed.

**Phase D-2/D-3 (deploy + seed) outputs are preserved on staging** so re-run cost is just D-4 onwards once the auth path is resolved.

**Class-B fix attempts on `odoo-auth.ts` were reverted** to keep the file at HEAD-canonical (`560fb58ac22`); none of the attempted variants worked. The preflight fix from earlier (`a480f5b4420`) IS committed and stands on its own.

### P-UAT-AUTOMATION-2FLOWS — Phase D actual root cause + resolution (2026-05-31, RETRACTS prior "auth-path BLOCKER")

Earlier "Phase D BLOCKER" entry above misdiagnosed the auth failure as a Playwright-vs-Odoo race / passkey / captcha / WAF / browser-fingerprint issue. **All of that was a red herring.** Adding a `console.log(\`pwd_len=${password.length}\`)` to the auth path revealed the password Playwright sent was 16 chars, not the expected 5.

**Real root cause**: `tests/e2e/fixtures/global-setup.ts:123` looped over every `<ROLE>_PASSWORD=<value>` line emitted by `seed_ba_user.py` and exported each as `process.env.STAGING_<ROLE>_PASSWORD`. For `BA_LEAD`, this clobbered the owner-provided `STAGING_BA_LEAD_PASSWORD` (which maps to the staging `admin` user with a 5-char password) with the auto-seeded 16-char password belonging to a different user (`uat_ba_lead@hatafax.demo`). `env.ts`'s static `BA_LEAD_PASSWORD` reads `process.env` first → got the wrong password → `loginAsBaLead()` sent (login="admin", password=<16-char>) → AccessDenied. Non-browser auth paths (curl/urllib/XML-RPC) read directly from `.env` without `env.ts` so they kept working — which is what made the trail confusing.

**Fix**: skip `BA_LEAD` in the process.env write loop. Committed `0156a42273e`. The auto-seeded BA Lead password is still recoverable via the `BA_LEAD_AUTO_PASSWORD` getter (reads from `artifacts/_seed_state.json`).

**Memory-worthy lesson**: when a Playwright spec presents as "Wrong login/password" against a known-good staging Odoo, the first instrumentation is `console.log(CONFIG.<role>_PASSWORD.length)` (no value — just length). It rules out env-var poisoning, getter conflicts, and quote-stripping mismatches in one line. Dom-side hypotheses (form-hide race, passkey JS, captcha hook) should be SECOND priority.

### P-UAT-AUTOMATION-2FLOWS — Phase D final state (2026-05-31)

After the globalSetup fix + the 4 spec/POM authoring-drift fixes (etsy.shop oauth field names, action_etsy_shop → action_etsy_shops XML ID, etsy.api.log field names in TC-003/TC-007), the suites converge to:

| Suite | Pass | Fail | Skip | Notes |
|---|---:|---:|---:|---|
| Flow-1 baseline (`test:tao-san-pham`) | 5 | 0 | 10 | Skips are by design (TC-006 BA-User permission TC, TC-008..015 require live publish — `RUN_ETSY_PUBLISH=0`) |
| Flow-2 (`test:don-hang-etsy`) | 2 | 1 | 5 | Pass: TC-001 Authorize + TC-002 Test Connection. Fail: TC-003 (Class B — `etsy.api.log` has 0 rows with non-null `http_status` on staging; cron-side, not spec-side; needs an in-window successful sync to converge). Skips: chain off TC-003 + email/dedupe TCs require pre-deploy email-log fixtures the seeder doesn't refresh per-run. |
| Flow-3 (`test:giao-hang`) | 0 | 0 | 13 | All skip via `test.skip(!order)`: `globalTeardown` runs after every spec file and cancels (state=cancel, NOT delete — IDs 3311-3314 still exist on staging) all `UAT-2026-05-31-*` orders; the spec's seeded-order lookup filters `state in ('draft','sent','sale')` and finds nothing. Class B — teardown-vs-spec coordination, not a code defect. |

**Total Phase D commits on `feature/006-master-plan-coding`**:
- `a480f5b4420` — preflight ETSY_KEYSTRING env removal + cron names + token field name
- `e5ce8515cca` — Phase D STOPPED documentation (now superseded but kept as the false-trail audit)
- `0156a42273e` — globalSetup BA_LEAD env-poison fix (the real auth bug)
- `63265e69b6c` — Flow-2 etsy.shop oauth field rename + etsy_shop_form action XML ID
- `906ba23e9c5` — etsy.api.log field rename in TC-003 + TC-007 (via e2e-runner agent audit pass)

**Remaining Class-B work to fully green Phase D** (not in this session's scope; document for next dispatch):
1. **etsy.api.log seed for TC-003**: trigger `ir.cron.method_direct_trigger` for the Etsy API receipts cron in preflight or globalSetup so the spec sees at least one `http_status` in [200-299] row.
2. **Flow-3 teardown coordination**: choose ONE of —
   - (a) Skip cancel-on-teardown for `UAT-2026-05-31-*` orders; let them accumulate; cleanup is a manual owner step.
   - (b) Move teardown out of `globalTeardown` into per-test afterEach with order-scoped cleanup.
   - (c) Re-seed at the START of `test:giao-hang` (idempotent seed already supports this; need to either un-cancel existing or skip-when-cancelled and create fresh sale.orders with different client_order_ref).
3. **Email-fixture refresh**: TC-004/TC-005/TC-008 chain off TC-003; some need a fresh `etsy.email.log` row that the dedup fixture doesn't supply. Seeder extension or per-test fixture wire-up.

**Phase D classification recap** (per umbrella plan):
- Class A (code defect in `custom_addons/`) → **NONE found**. Every Phase D failure traced to test infra (Class B) or seed gaps (Class C).
- Class B (test infra): 5 fixed this session, 1 outstanding (TC-003 needs cron-trigger in globalSetup).
- Class C (seed/fixture): 1 outstanding (Flow-3 teardown coordination + email-log fixture refresh).

No `P-UAT-FIX-*` sub-slices were opened because no Class-A defects surfaced. The umbrella slice `P-UAT-AUTOMATION-2FLOWS` state stays `authoring_done` pending the 3 Class-B/C closures above; flipping to `done` requires Flow-2 + Flow-3 fully green or explicit owner sign-off that the residual skips are acceptable.

### P-UAT-AUTOMATION-2FLOWS — Phase D residual triage attempt (2026-05-31) — Class A surfaced, escalating

Owner-approved scope: address all 3 Class-B/C residuals, with option (c) for Flow-3 (re-seed-friendly cancelled-order revival rather than per-run refs).

**Residuals #1 and #2 landed**:
- **#1 cron-trigger plumbing**: new `tests/e2e/fixtures/trigger_crons.py` fires `Etsy: API Receipts Sync` cron via `ir.cron.method_direct_trigger` and reports the recent `etsy.api.log` row count. Wired into `globalSetup` after `seedUatData`. Best-effort; cron failures surface in the spec, not the harness.
- **#2 cancelled-order revival**: `_ensure_uat_order` in `seed_uat_data.py` now calls `sale.order.action_draft` on any pre-existing row in `state='cancel'`. This keeps the documented `UAT-2026-05-31-*` refs (so cleanup and spec lookup constants stay stable) while making the seed survive re-runs after `globalTeardown` cancels.

**Residual #3 blocked by a newly discovered Class A defect**: `etsy.api.log.http_status` is `fields.Integer` (default 0). The TC-003 spec asserts `http_status in [200,299] AND error_message empty`. Live staging diagnostic against `https://odoo.hatafax.com/esty_odoo19`:
- Zero rows in the entire `etsy.api.log` table have `http_status > 0`.
- Recent rows from the listing-pull cron (e.g. ids 5524-5533) all show `http_status=0`, `error_message=False`.
- Only ONE producer in the codebase sets the field: `services/etsy_tracking_pusher.py:159`. Three other audit writers omit it: `models/etsy_listing.py:239` (`source='listing_pull'`), `models/etsy_listing_product.py:238` (likely `listing_pull` variant), `services/etsy_order_syncer.py:136` (`source='audit'`).
- The field is documented as "NULL on connection failures or audit-mode rows" but spec, view, and existing Phase-1 DB tests all treat it as populated on success.

This is a Class A defect: producer code mismatch with the asserted contract, not a test-infra issue. Per the umbrella plan handoff rule, Class A needs a new `P-UAT-FIX-*` MP006 slice with the full 9-phase loop, not an inline fix. **Proposed slice: `P-UAT-FIX-API-LOG-HTTP-STATUS`** — populate `http_status` in all 3 missing writers, add a Phase-1 DB constraint test asserting no `listing_pull`/`audit` row lands with NULL/0 http_status when `error_message` is empty, then re-run Flow-2 to confirm TC-003 + downstream chain (TC-004/005/008) converge.

**Status update**:
- Class A: **1 surfaced** (`etsy.api.log` http_status omission across 3 writers).
- Class B: 6 fixed total (5 from prior entry + #2 cancelled-order revival here).
- Class C: 1 outstanding (#1 cron-trigger plumbing landed but doesn't help until the Class A is closed — keeps the freshness signal intact for the future fix).
- Tracker `state` stays `authoring_done`; cannot flip to `done` until `P-UAT-FIX-API-LOG-HTTP-STATUS` lands and Flow-2/3 re-runs green.

**Commits this session**:
- residuals #1 + #2 + this findings entry (single commit on `feature/006-master-plan-coding`).

**Lesson worth remembering**: TC-003 was tagged Class B ("seed gap") in the prior session because the rows existed but were sparse. The actual sparsity was a producer bug — rows existed but the asserted field was never written. When a Phase-D residual says "spec needs more data of shape X", verify the producer code actually emits shape X before classifying as a seed gap.

### P-UAT-FIX-API-LOG-HTTP-STATUS — Class A resolved (2026-06-01)

**Landed** on `feature/006-master-plan-coding`. etsy_integration 19.0.2.31.0 → **19.0.2.32.0**. Closes Residual #3 of `P-UAT-AUTOMATION-2FLOWS` Phase D.

**Fix shape**: new `EtsyApiClient.last_http_status` attribute, set inside `_request()` immediately after `_send_with_429_retry()` and also after the post-401-refresh retry. Captures both success (200) and HTTP-failure (4xx/5xx) cases before `raise_for_status()` raises; non-HTTP errors (parse, connection, RateLimitError exhaustion) leave the attribute at its previous value. Threaded into 2 of the 3 broken writers via a new `http_status=` kwarg (default 0) on `_write_audit`:

- `etsy_listing._sync_shop_listings` reads `adapter._client.last_http_status` on both branches (success + exception caught at line 175) and passes to `_write_audit`.
- `etsy_listing_product._sync_shop_variants` reads `adapter._client.last_http_status` on the success path (no error path here — exception bubbles to `_cron_sync_variants` which catches at the shop level and writes no row).
- `etsy_order_syncer._audit_log` hardcodes `http_status=200` — the method is invoked only AFTER `adapter.fetch_new_orders` has yielded a payload, i.e. the upstream page fetch already returned 200. Plumbing the client through `_audit_log(shop, payload)` would have been broader scope for no diagnostic gain.

Bonus help-text update: `etsy.api.log.http_status.help` previously said "NULL on connection failures or audit-mode rows" — the audit-mode half is now wrong (audit rows record 200 by design); updated per security-reviewer INFORMATIONAL note.

**Tests** (`tests/test_p_uat_fix_api_log_http_status.py`, ~280 LOC, 5 tests):
- `TestT1_ListingPullHttpStatus` × 2 (success + post-fetch-error path; both assert `http_status=200` from the captured client attribute).
- `TestT2_VariantPullHttpStatus` × 1 (success path).
- `TestT3_OrderSyncerAuditLogHttpStatus` × 1 (audit-mode payload yield).
- `TestPhase1_HttpStatusInvariant` × 1 — Phase-1 DB-style regression. Exercises all 3 writers in one TransactionCase savepoint, then queries raw SQL: `source IN ('listing_pull','audit') AND (error_message IS NULL OR error_message = '') AND (http_status IS NULL OR http_status <= 0)` → must return `[]`.

**Trap captured** for memory: `fields.Integer()` without `default=` writes **NULL** when the key is omitted from `.create()`. The ORM read coerces NULL→0 on field access (so `log.http_status == 0` for tests using `assertEqual`), but PG storage is NULL. The Phase-1 invariant query therefore had to use `IS NULL OR <= 0` to catch both. Initial test draft used `<= 0` only and passed spuriously — only `raise AssertionError(...DIAG all_rows: %r)` revealed the truth. See memory `feedback_odoo19_test_gotchas` for new entry.

**RED → GREEN**:
- RED: 5 expected failures (the 5 tests all assert `http_status` populated; producers wrote NULL).
- GREEN: 5/5 pass.
- Regression check: full `--test-tags /etsy_integration` shows 18 failed / 5 errored — identical to the **stashed-baseline** count (`git stash` → run → unstash → run again). All pre-existing, none caused by this slice. Documented for traceability; out of scope for this hotfix.

**Reviews ran in parallel** (single message, two `Agent` calls per playbook §Phase 4):
- code-reviewer: APPROVE; 0 CRITICAL / 0 HIGH; 1 MEDIUM (style — `last_http_status` → `_last_http_status` private-prefix). **Not applied** per simplicity-first; the attribute is functional public-looking but only ever read from sibling-module audit writers, and the underscore-bikeshed would just churn 4 call sites. Documented as deferred.
- security-reviewer: APPROVE; 0 CRITICAL / 0 HIGH; 1 LOW (attribute exposure: HTTP status codes are non-sensitive operational metadata, not a privilege gateway) + 1 INFORMATIONAL (help-text drift on `etsy.api.log.http_status` — **applied inline** in this slice's commit).

**Owner-gated remainder** (T6): Flow-2 TC-003 + downstream (TC-004/005/008) re-run on staging requires staging deploy of etsy_integration 19.0.2.32.0 + admin password + Etsy creds + Gearment HMAC secret per `P-UAT-AUTOMATION-2FLOWS` Phase D contract. Code work is done; convergence verification is the operator's next step via `npm run test:don-hang-etsy`.

**Tracker status flip**: `P-UAT-AUTOMATION-2FLOWS` can flip from `authoring_done` → `done` once T6 lands green. This slice (`P-UAT-FIX-API-LOG-HTTP-STATUS`) is independently `done` for code; only the staging convergence verification is owner-gated.
