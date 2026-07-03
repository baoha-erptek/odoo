# Jira Sprint Draft — "Deliver the Promise" (Hatafa Etsy ERP)

**Project:** ESTY (erptek.atlassian.net) · **Drafted:** 2026-06-27 · **Source:** `docs/analysis/gap-matrix.md` + `mismatch-report.html` + `uiux-improvement.html`

> **STATUS: PUSHED TO LIVE ESTY — 2026-06-27.** 30 issues created (ESTY-214 … ESTY-243),
> labelled `deliver-the-promise`, with priorities (P0→Highest … P3→Low) and epic parent links.

### Created issues (live keys)

| Epic | Key | Children (key) |
|---|---|---|
| EPIC-DASH | **ESTY-214** | KPI band ESTY-221 · Curate columns ESTY-222 · Filter chips ESTY-223 · Auto-refresh ESTY-224 |
| EPIC-BOARD | **ESTY-215** | Kanban ESTY-225 · Drag-transition ESTY-226 · Overdue decoration ESTY-227 |
| EPIC-NAV | **ESTY-216** | Vendor muk_web ESTY-229 · Brand colors ESTY-230 · Sidebar ESTY-231 · Menu merge ESTY-232 · Role landings ESTY-233 |
| EPIC-ROLES | **ESTY-217** | group_rd/pd ESTY-234 · RD dashboard ESTY-235 · Sync-health tile ESTY-236 |
| EPIC-CARE | **ESTY-218** | Refund spike ESTY-237 · Refund API ESTY-238 |
| EPIC-POLISH | **ESTY-219** | Fulfillment rename ESTY-239 · Quote recipient ESTY-240 · Badges ESTY-241 · Side chatter ESTY-242 |
| EPIC-BLOCKED | **ESTY-220** | Conversations ESTY-243 |
| (standalone) | — | **ESTY-228** [BUG] Listing-backfill draft clobber (P0) |

Browse: `https://erptek.atlassian.net/browse/ESTY-214` (epics 214–220, work items 221–243, bug 228).

## Sprint goal

Close the visible promise-vs-built gaps. The functional contract is ~90% delivered; the felt gap is
**presentation + findability** (no dashboard KPIs, no pipeline board, fragmented nav) plus a few small
functional items (refund automation, RD dashboard, one backfill bug). Do the high-visibility / low-cost
work first.

## Priority key

- **P0** — kept-promise *failure* the user sees today (dashboard, board, a real bug). Do first.
- **P1** — high-value presentation / role completeness.
- **P2** — functional completeness (refund automation, RD dashboard, polish).
- **P3** — deferred / blocked (tracker rows only; do not build now).

## Sequencing (matches UI/UX rollout waves)

```
Wave 1 → EPIC-NAV (reuse muk_web chrome)          P1   1-2d   zero model change, unblocks look-and-feel
Wave 2 → EPIC-DASH (KPI band + curate)            P0   2-3d
Wave 3 → EPIC-BOARD (pipeline kanban)             P0   2-3d
Wave 2'→ ESTY-BUG-BACKFILL (fix in parallel)      P0   0.5d   independent
Wave 4 → EPIC-NAV menu merge + role landings      P1   2d
Wave 5 → EPIC-ROLES (group_rd/pd + RD dash)       P2   3-4d
Wave 6 → EPIC-POLISH (form/badges/quote)          P2   1-2d
        EPIC-CARE (refund API)                    P2   2-3d   gated on Etsy refund scope check
        EPIC-BLOCKED (conversations)              P3   —      tracker only
```

---

## EPIC-DASH — Operations Dashboard completion  ·  P0

> Promise: 3 KPI cards + curated table (flow-2 mockup + every role doc). Built: 25–34-col plain list, no KPIs. (`mismatch §3`, `§7`)

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Story | P0 | KPI band on Operations Dashboard | A tile row shows: Orders today, Awaiting design approval (w/ overdue count), Stuck in pipeline (>48h), Tracking-push failures. Counts via `read_group`; each tile click applies the matching filter. | 2d |
| | Story | P0 | Curate default columns + "Excel (34-col)" saved filter | Default list shows 8–12 high-signal columns; full 34-col Excel layout preserved as a named saved filter; no data lost. | 1d |
| | Story | P1 | Saved filter chips (Last 24h / Needs me / Unassigned / Dropship / MTO) | Chips present and functional on the dashboard search view. | 0.5d |
| | Task | P1 | Live auto-refresh via `muk_web_refresh` | Dashboard refreshes on interval (≈60s) without manual reload. Depends on EPIC-NAV W1. | 0.25d |

## EPIC-BOARD — Pipeline kanban  ·  P0

> Promise: pipeline kanban for production (role-3 doc). Built: state machine + tab + wizard, **no board view**. (`gap-matrix A/Flow3a`, UNWIRED)

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Story | P0 | `<kanban>` grouped by pipeline state on orders | Board shows the 13 seeded states as columns with order cards (order ref, SKU, qty, label, overdue tint). | 1.5d |
| | Story | P0 | Drag-to-transition through audited path | Dragging a card calls `_write_pipeline_state()` (same guard as wizard); an audit row is written; direct writes still blocked. | 1d |
| | Task | P2 | Overdue / urgent card decoration | Cards >48h in a non-final state show a danger marker; urgent label highlighted. | 0.5d |

## ESTY-BUG-BACKFILL — Listing-backfill draft clobber  ·  P0

> Built but defective: matched live listing stays `draft` because `_sync_channel_statuses` seeds a draft before the backfill's `state='published'` create. (`mismatch §8`, BUG)

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Bug | P0 | Backfill leaves live listing channel-status `draft` | After backfill of a matched/live listing, `product.channel.status.state == 'published'`. Regression test covers the `_sync_channel_statuses`-then-backfill ordering (`etsy_listing_backfill_wizard.py:79-92`, `product_template.py:370-373`). | 0.5d |

## EPIC-NAV — Unified navigation & branding  ·  P1

> Promise: one operational hub + brand chrome. Built: two separate apps (Etsy + Operations) w/ duplicate items; navbar not purple on local. (`mismatch §7`, DOC-DRIFT) · Reuse the in-house `muk_web_*` bundle.

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Task | P1 | Vendor `muk_web_*` bundle into `custom_addons/` | 7 modules (theme/appsbar/colors/chatter/dialog/group/refresh) copied from `openeducat_erp19/custom_addons/`, install clean (`-u --stop-after-init` exit 0), LGPL-3 preserved. | 0.5d |
| | Story | P1 | Apply `#714B67` brand palette via `muk_web_colors` | Top navbar + accents render brand purple consistently (not default light). | 0.5d |
| | Story | P1 | Left sidebar nav via `muk_web_appsbar` | Sidebar replaces top-bar-only nav; sections grouped Daily/Sell/Fulfil/Care/Watch/Setup. | 0.5d |
| | Story | P1 | Merge Etsy + Operations menu trees | Single hub; de-duplicate Design Queue↔Design Files and Listing Variants↔Listings; old menus removed or redirected. | 1.5d |
| | Story | P1 | Per-role landing pages | Each group lands on its primary section (table in `uiux-improvement.html §3`). | 1d |

## EPIC-ROLES — Role completeness & RD reporting  ·  P2

> Promise: 5 roles incl. RD price control + PD. Built: no `group_rd`/`group_pd`; RD price dashboard unbuilt (Story 6.5). (`mismatch §8`, MISSING)

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Story | P2 | Add `group_rd` and `group_pd` res.groups + ACLs | Groups defined; PD scoped to design approvals; RD scoped to price control + read dashboards; menu visibility wired. | 1d |
| | Story | P2 | RD Price-Control dashboard | View lists orders where price < shop min or ship-fee > expected; drill to order; anomaly domain documented. | 2.5d |
| | Task | P3 | Sync-health KPI tile | Surface `*.sync.health` error/warning counts as a tile on the dashboard (model + list already exist). | 0.5d |

## EPIC-CARE — After-sales automation  ·  P2

> Promise/implied: in-system refund. Built: `etsy.order.ticket` tracks refund; **no Etsy refund API call** (manual). (`mismatch §6`, PARTIAL)

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Spike | P2 | Confirm Etsy refund API + scope availability | Determine if the granted OAuth scopes permit `createReceiptRefund`; capture response shape. Gate the story below on the result. | 0.5d |
| | Story | P2 | Wire refund ticket → Etsy refund API | On BA-lead approve, call the refund endpoint; log request/response to `etsy.api.log`; ticket → `refunded` only on success; failure surfaces error. Depends on spike. | 2d |

## EPIC-POLISH — Order form & wizard polish  ·  P2

> Curation gaps (Flow 3b). (`mismatch §5`, KEPT-curation)

| Key | Type | Pri | Summary | Acceptance criteria | Est |
|---|---|---|---|---|---|
| | Task | P2 | Rename Gearment tab → "Fulfillment"; button → "Request Gearment Quote" | Labels match mockup vocabulary; no behavior change. | 0.25d |
| | Story | P2 | Recipient/address block in Gearment quote wizard | Read-only recipient + shipping address shown before confirm. | 0.5d |
| | Story | P2 | Status badges across forms | Pipeline stage, design status, tracking-push status render as `widget="badge"` + `decoration-*`. | 0.5d |
| | Task | P3 | Side chatter via `muk_web_chatter` on order form | Chatter docks to the side. Depends on EPIC-NAV W1. | 0.25d |

## EPIC-BLOCKED — External dependency  ·  P3 (tracker only)

| Key | Type | Pri | Summary | Note |
|---|---|---|---|---|
| | Story | P3 | Buyer conversations ingestion | BLOCKED on Etsy `conversations_r` scope (E1). Do not build. Re-open when scope granted. (`etsy_oauth.py:53`) |

---

## Deferred (owner decision — out of this sprint)

- Payload-preview tab (Flow 1) — v2.
- QC checklist + production scan (Flow 3a) — v2.

## Push checklist (after approval)

1. `jira-create` skill → create EPICs first, capture keys.
2. Create stories/tasks/bugs under each epic; set priority + estimate; link `depends`.
3. Record returned keys in the `Key` columns above; commit this file.
4. (Optional) add all to a new Jira sprint named "Deliver the Promise".
