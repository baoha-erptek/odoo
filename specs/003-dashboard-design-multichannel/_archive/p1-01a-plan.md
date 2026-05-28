# P1-01a Tactical Plan — Order Dashboard

**Slice**: P1-01a (Spec 003 US1, operator entry point)
**Branch**: `feature/006-master-plan-coding`
**Created**: 2026-04-29
**Source**: planner agent draft 2026-04-29 + orchestrator corrections (module placement, scope reinstated per owner Telegram msg 369–370 "go")

---

## 1. Slice scope

### IN scope (this slice)

| Task | Description |
|---|---|
| T021 (partial) | `sales_channel` Selection (`etsy`/`amazon`/`website`/`other`, indexed, required, `tracking=True`) + `channel_order_ref` Char (indexed, `tracking=True`) on `sale.order` per FR-024. Pipeline fields (`x_pipeline_id`, `x_pipeline_state_id`) deferred to P1-08. |
| T024 | Order Dashboard list view + `ir.actions.act_window` in `multichannel_hub_core/views/order_dashboard_views.xml` — 10 cols: image_128, sales_channel, date_order, partner_id, country (related), amount_total, mp_note, pic_user_id, order_priority (the last three delegated from `sale.order.fulfillment`), tracking_state (delegated), is_overdue_approval marker. Skip pipeline + design columns per scope. |
| T025 | Row decorations on the dashboard: `decoration-info="qty_total >= 2"`, `decoration-bf="is_duplicate_buyer"`, `decoration-danger="order_priority in ('push','urgent')"` (delegated), `decoration-warning="sales_channel == 'amazon'"`. |
| T026 | `is_duplicate_buyer` Boolean stored compute on `sale.order` — True when `partner_id` has another non-cancel `sale.order` with `date_order` in the previous 7 days. `@api.depends('partner_id', 'date_order', 'state')`. Document the recompute caveat (R2). |
| T027 | `is_overdue_approval` Boolean stored compute on `sale.order` — True when an open `mail.activity` of type `mail.mail_activity_data_todo` exists on the order with `date_deadline < today - 1 day` AND `sales_channel == 'etsy'` AND state != 'cancel'. `store=True`; recompute trigger via daily cron + activity write hooks (see D3). |
| T028 | ACL extension: `sales_team.group_sale_user` (Marketing/BA equivalent) gets write on `sale.order.fulfillment.{mp_note, pic_user_id, order_priority}` for inline-edit on the dashboard. Verify P1-05 ACL rows; extend `multichannel_hub_core/security/ir.model.access.csv` if needed. |
| T029 | Menu entry `Operations → Order Dashboard` in `multichannel_hub_core/views/menu.xml`. New menu file (mhc has no menu yet). |
| T030 | Phase-2 ORM test `multichannel_hub_core/tests/test_order_dashboard.py`: 200-row fixture (17K perf deferred to E2E sprint), decoration-logic tests, `is_duplicate_buyer` recompute test, `is_overdue_approval` compute test, inline-edit chatter audit (write to mp_note → chatter entry). |
| T031 | Phase-1 DB test `multichannel_hub_core/tests/test_dashboards_db.py`: composite index `(sales_channel, has_pending_address_change)` exists post-install; backfill is idempotent (re-running migration is no-op). |
| T060 | "Request address change" button on `sale.order` form in `etsy_integration/views/sale_order_views.xml` (existing file from P1-04). Lightweight: `<button name="action_request_address_change" type="object" string="Request address change" invisible="has_pending_address_change"/>` returns `act_window` for `etsy.address.change.request` with `default_order_id` in context. |
| `qty_total` field | New stored compute on `sale.order` summing `order_line.product_uom_qty` (`@api.depends('order_line', 'order_line.product_uom_qty')`). Required by T025 `decoration-info`. Lives in mhc. |

### Backfill (FR-025, idempotent)

- `multichannel_hub_core/__init__.py` `post_init_hook(env)` and `multichannel_hub_core/migrations/19.0.1.0.3/post-fr025-backfill.py` `migrate(cr, version)` BOTH backfill: rows where `etsy_order_id` is non-empty get `sales_channel='etsy'` + `channel_order_ref=etsy_order_id`; rows where `etsy_order_id` is NULL/empty AND `sales_channel` is NULL get `sales_channel='other'`.
- Both paths share a helper `_backfill_sales_channel(env)` so logic is identical between fresh install and upgrade (per memory gotcha #12: post_init_hook fires on `-i`, migration script on `-u`; both are needed).
- Idempotency: only `WHERE sales_channel IS NULL` rows are touched. Re-running `-u multichannel_hub_core` is a no-op.

### DEFERRED (marked `[~]` in tasks.md)

| Task | Why | Defer to |
|---|---|---|
| T021 (pipeline fields) | `x_pipeline_id` / `x_pipeline_state_id` need `order.pipeline` (ADR-010, P1-08) | P1-08 |
| T022 C-SO-002 | Pipeline-policy constraint, same dependency | P1-08 |
| T023 | `design_status` rolled-up compute on sale.order.line — depends on `design.file` (P1-02) | P1-02 |
| 17K-row perf benchmark | Practical only end-to-end with real fixture | E2E sprint (W7) |
| T060 full wizard UX | Quick `act_window` lands here; full wizard with new-address-fields validation lands when address-change UX gets a dedicated slice | future |

---

## 2. Decisions D1–D5

### D1 — `sales_channel` + `channel_order_ref` + qty_total + dashboard view live in `multichannel_hub_core` (NOT etsy_integration)

mhc CLAUDE.md prohibits Etsy-named code, but the Selection value `'etsy'` is an enum member, not a model name — fine. Channel-agnostic fields belong in the foundation module so future `amazon_channel` / `website_channel` modules can `_inherit('sale.order')` and read these without depending on `etsy_integration`. The data-model.md §1 lists these on `sale.order` without module attribution; ADR-003 + module CLAUDE.md make mhc the canonical home.

### D2 — Backfill via post_init_hook + migration script (both)

Per memory gotcha #12: `post_init_hook` runs on `-i` (fresh install of mhc on a new DB), migration scripts run on `-u` (upgrade of mhc that already has data). The 17K existing Etsy orders are on a DB that already has mhc installed, so the migration script is the path that fires for them. New environments need post_init_hook. Both call the same private helper `_backfill_sales_channel`. Bump mhc manifest version to `19.0.1.0.3` to trigger the migration. Idempotent: `WHERE sales_channel IS NULL` only.

### D3 — `is_overdue_approval` recompute trigger

Stored compute. Two recompute paths:
1. On `mail.activity` write/unlink: monkey-patch isn't acceptable; instead, the compute reads `mail.activity` lazily and we accept *staleness* up to one day.
2. **Daily cron** at 03:00 UTC re-invalidates the compute on all in-flight Etsy orders (state != 'cancel') so the dashboard is fresh by start-of-day. Cron defined in `multichannel_hub_core/data/ir_cron_data.xml`.

Acceptable trade-off: dashboard might show "not overdue" until cron runs, even if an activity tipped over at 11pm. BA workflow runs morning shift — by 8am the cron has run.

### D4 — Order Dashboard view does NOT inherit Odoo's standard sale.order list

It's a *new* `ir.ui.view` with `model='sale.order'` and a unique `name`. No `inherit_id`. The standard sale.order list keeps its existing columns; the dashboard is a separate view with its own `act_window`. Avoids xpath fragility and lets us define the column set + decorations cleanly.

### D5 — T060 button in `etsy_integration`, not mhc

The button references `etsy.address.change.request` which is an Etsy-specific model. The button lives where the model lives — in `etsy_integration/views/sale_order_views.xml` (already extended in P1-04). When future channels have their own address-change models, they ship their own button.

---

## 3. File touch list (commit order)

All paths under `custom_addons/`.

| Order | File | Action | Tasks |
|---|---|---|---|
| 1 | `multichannel_hub_core/models/sale_order.py` | modify | T021p (sales_channel, channel_order_ref), qty_total compute, T026 (is_duplicate_buyer compute), T027 (is_overdue_approval compute) |
| 2 | `multichannel_hub_core/__init__.py` | modify | post_init_hook + `_backfill_sales_channel` helper |
| 3 | `multichannel_hub_core/migrations/19.0.1.0.3/post-fr025-backfill.py` | new | Migration calling the same helper |
| 4 | `multichannel_hub_core/__manifest__.py` | modify | Bump version to 19.0.1.0.3; add new view + menu + cron files to data list; declare post_init_hook |
| 5 | `multichannel_hub_core/views/order_dashboard_views.xml` | new | T024 list view + act_window + T025 decorations |
| 6 | `multichannel_hub_core/views/menu.xml` | new | T029 menu entry |
| 7 | `multichannel_hub_core/data/ir_cron_data.xml` | new | Daily overdue-marker recompute cron (D3) |
| 8 | `multichannel_hub_core/security/ir.model.access.csv` | modify | T028 — verify/extend ACLs for inline-edit fields on sale.order.fulfillment |
| 9 | `etsy_integration/views/sale_order_views.xml` | modify | T060 button |
| 10 | `etsy_integration/models/sale_order.py` | modify | `action_request_address_change` returning act_window for etsy.address.change.request |
| 11 | `multichannel_hub_core/tests/test_dashboards_db.py` | new | T031 — composite index + backfill idempotency |
| 12 | `multichannel_hub_core/tests/test_order_dashboard.py` | new | T030 — decorations + computes + chatter audit |
| 13 | `multichannel_hub_core/tests/__init__.py` | modify | wire imports |
| 14 | `specs/003-dashboard-design-multichannel/tasks.md` | modify | mark `[X]` / `[~]` per scope |
| 15 | `.claude/plans/006-master-plan-tracking.md` | modify | P1-01a row → done + change-log |
| 16 | `specs/006-master-plan/MASTER_PLAN.md` | modify | Phase 1 status snapshot adds P1-01a (per new playbook rule) |
| 17 | `specs/003-dashboard-design-multichannel/findings.md` | modify | append P1-01a entry |

---

## 4. Agent dispatch

| Phase | Agent | Tier | Task |
|---|---|---|---|
| 2 (RED) | `tdd-guide` | Sonnet | Write Phase 1 DB + Phase 2 ORM tests covering all in-scope items. Apply known Odoo 19 framework deltas (memory #1, #36–#41) on first pass. |
| 3 (GREEN) | inline (Sonnet executor) | Sonnet | Implement files 1–13 in order. Mark tasks.md as items close. |
| 4 (Review) | `code-reviewer` + `security-reviewer` | Sonnet (parallel) | Two Agent calls in one message. Security: backfill SQL safety, ACL gates on inline-edit fields, no PII in cron logs. Code: tracking=True coverage, recompute correctness, idempotent migration. |

No Opus expected.

---

## 5. Top risks

1. **R1 — Backfill idempotency under partial failure**: 17K UPDATE inside a transaction is fine if it commits cleanly. If the migration is interrupted mid-batch, partial writes survive. Mitigation: single UPDATE with `WHERE sales_channel IS NULL` — re-running picks up where it left off; no checkpoint needed for ~17K rows in one statement.

2. **R2 — `is_duplicate_buyer` retroactive recompute**: when a NEW order arrives, the new order is `is_duplicate_buyer=True` if a same-partner order in last 7 days exists. But the OLD order also needs to flip from False to True. `@api.depends('partner_id', 'date_order', 'state')` only triggers recompute on the changed record. Mitigation: in the new-order create hook, find sibling orders in window and explicitly `invalidate_recordset(['is_duplicate_buyer'])` on them. Document in code.

3. **R3 — `decoration-bf` rendering**: Odoo 19 list-view RelaxNG accepts `decoration-bf` (bold) but the standard widget set is limited. Verify by inspection on a quick install. Fallback: use `decoration-warning` with a different threshold, or a custom `widget`.

4. **R4 — Cron timing for overdue marker**: if the dashboard is opened before cron has fired today, an order that tipped overdue at 11pm last night shows as not-overdue until 03:00. Acceptable per D3; document in findings.md so BAs aren't surprised.

5. **R5 — qty_total recompute under multi-line edits**: if a line is unlinked, `@api.depends` must catch it. Use `@api.depends('order_line', 'order_line.product_uom_qty')` (depends on the recordset and the field). Test includes a line-delete scenario.

---

## 6. Slice exit criteria (machine-checkable)

- [ ] All 10 in-scope task IDs marked `[X]` in `specs/003-dashboard-design-multichannel/tasks.md`. T023 + T060 (full wizard) + T021 pipeline-fields tail marked `[~]` deferred.
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core,etsy_integration --http-port=18069 --gevent-port=18072 --stop-after-init` exits 0
- [ ] `--test-tags /multichannel_hub_core,/etsy_integration` exits 0
- [ ] Composite index `(sales_channel, has_pending_address_change)` exists in `sale_order` (verified by Phase-1 DB test)
- [ ] Backfill is idempotent — Phase-1 DB test re-runs the migration helper and asserts no row count change
- [ ] Order Dashboard renders 10 cols; decorations visible for qty_total + amazon + push + duplicate-buyer fixtures
- [ ] Inline-edit on `mp_note` produces a chatter entry (P1-05's `tracking=True` + Phase-2 audit test)
- [ ] Menu `multichannel_hub_core.menu_order_dashboard` resolvable via `env.ref()`
- [ ] No `_logger.info(` / `print(` in changed files
- [ ] Tracker `006-master-plan-tracking.md` P1-01 row state→`done` (P1-01a closes P1-01 except for the deferred pipeline tail)
- [ ] **MASTER_PLAN.md Phase 1 status snapshot updated** with `✅ P1-01a Order Dashboard landed 2026-04-29` (per new playbook rule)
- [ ] `findings.md` entry appended (or explicit "no new patterns")

---

## 7. Open questions for owner (none blocking)

1. Menu parent — top-level `Operations` menu, or nest under `Sales`? Default: top-level under `Operations` so future Tracking + Process dashboards have a home. Flag if rather under Sales.

Default-resolved; proceed.

---

## 8. Next phase

Phase 2 (RED) — tdd-guide with this plan + spec references + memory gotchas. Tests must FAIL for the right reason.
