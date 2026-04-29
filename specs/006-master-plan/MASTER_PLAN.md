# Master Plan — odoo19_esty Multichannel E-Commerce Hub

**Date**: 2026-04-10 (original) · **Last revised**: 2026-04-26 (Stage-2 ADRs landed: [ADR-008a v2](adrs/ADR-008a-email-as-mandatory-backup.md), [ADR-009](adrs/ADR-009-file-lifecycle.md), [ADR-010](adrs/ADR-010-configurable-order-pipeline.md), [ADR-012](adrs/ADR-012-gdrive-failover.md))
**Branch**: `main` (single-workspace forward; worktrees reserved for rework)
**Inputs**: End-user feedback (5 departments, `.0temp/end_user_feed_back/`) + Specs 001–005 + current module state + Stage-1 clarifications (`clarifications/`)
**Method**: Three-agent review (BA/Odoo consultant, Technical architect, Devil's advocate) + Stage-1 synthesis (2026-04-26)
**Agent reports**: [ba-consultant.md](agent-reports/ba-consultant.md), [tech-architect.md](agent-reports/tech-architect.md), [devils-advocate.md](agent-reports/devils-advocate.md), [SYNTHESIS-gap-2026-04-26.md](agent-reports/SYNTHESIS-gap-2026-04-26.md)

> **Pivot notice (2026-04-13, refined 2026-04-26)**: Spec 005 (Etsy API v3) moves from Phase 3 to **Phase 0 sandbox + Phase 1 production cutover**. Etsy app scope review is the critical-path external dependency. See [ADR-008](adrs/ADR-008-api-first-pivot.md).
>
> **Source-switching refinement (2026-04-26)**: API and email come from the same upstream (etsy.com) and produce the same canonical record. Build **one ingestion pipeline** with a swappable upstream adapter (`api` | `email`). The email parser is **not** legacy code; it is a **permanent failover** source — no retirement timeline, no sunset, no maintenance-mode caveat. Auto-failover on health-check failure; auto-recovery on probe success. See [ADR-008a v2](adrs/ADR-008a-email-as-mandatory-backup.md). The `sync_mode` enum from ADR-002 is superseded by `etsy.shop.active_source`; the `etsy_channel_legacy` module name from ADR-003 is renamed to `etsy_channel_email`.
>
> **Stage-2 ADRs landed (2026-04-26)**: [ADR-008a v2](adrs/ADR-008a-email-as-mandatory-backup.md) (single-pipeline source-switching), [ADR-009](adrs/ADR-009-file-lifecycle.md) (`design.file` + `design.file.route` + `design.print.batch`), [ADR-010](adrs/ADR-010-configurable-order-pipeline.md) (configurable order pipeline + resource assignment, supersedes the would-be hardcoded sub-state enum and collapses ADR-011), [ADR-012](adrs/ADR-012-gdrive-failover.md) (GDrive service account, queue+backoff, Discord as permanent escape hatch).

---

## Vision (from owner's hand-drawn flow)

A central hub on Odoo 19 CE ingesting orders from **Etsy / Amazon / Website**, running them through a **design-approval + production** pipeline, and pushing fulfillment to **external partners (Gearment)** or **internal production** with full tracking back to the channel of origin.

---

## Executive summary

### The three headlines

1. **Spec 001 is not shipped** — 17,659 orders are stuck in draft, 423 have $0 price, customer dedup is 0%. Every subsequent spec is building on broken data. **Nothing has business value until Spec 002 lands.**

2. **The current roadmap is over-indexed on API integrations and under-indexed on dashboard UX** — end users (BA, Marketing, PD, Sales-Audit) are asking for **three specialised dashboards**, approval workflows, product images, color tags, and a pricing audit tool. **None of these need Etsy or Gearment API work.** The 6-8 week MVP ships zero API calls.

3. **The plan is 2-3x under-estimated** — ~194+ tasks (plus Spec 005's unwritten list) with 1-3 devs is realistically **12-18 months**, not 3-6. Spec 004 alone is three specs in a trench coat. Spec 005 is blocked on Etsy app review which takes 3-8 weeks.

### What changes

- **Split Spec 004 into 004a / 004b / 004c** (tracking import / Gearment / returns-refunds)
- **Defer Spec 005** entirely past MVP; start Etsy app review **in parallel** (this week)
- **Rewrite Spec 003** around three dashboards (Order / Tracking / Process) with native Odoo leverage
- **Create Spec 006**: Sales Pricing Audit (multi-currency + delta vs catalogue)
- **Create Spec 007**: Raw-material inventory + forecasting (native `stock` + `stock_forecasted`)
- **Reserve Spec 008+** for Ticket system, Catalog Dashboard, Scan sheet, Amazon, Website
- **Module decomposition**: split `etsy_integration` -> `multichannel_hub_core`, `multichannel_hub_fulfillment`, `etsy_channel`, `etsy_channel_migration`

---

## 1. Current reality check

### What's actually shipped (Spec 001)
- `etsy_integration` v19.0.1.0.0: email ingestion + historical import + ~17,659 orders
- **Data quality failures**: 423 orders with $0 price, most stuck in draft, 0% customer dedup coverage on email, products all non-storable, fiscal position missing, payment term missing, sales team missing
- Realistic completion vs business value: **~40%**

### What's planned but zero code
- **Spec 002** (62 tasks): data migration wizard
- **Spec 003** (53 tasks): operational dashboard + design workflow + multi-channel foundation
- **Spec 004** (79 tasks): fulfillment routing + Gearment + GKE + returns + GDrive
- **Spec 005** (~50-90 tasks estimated): Etsy API v3 + webhooks + dual-mode sync

### What's completely missing from all specs
- Three separate dashboards (Order / Tracking / Process)
- Address-change approval workflow (safety-critical)
- Product images in list views (Marketing asked twice)
- Row color tags (qty>=2, duplicate, Push, Amazon)
- Ticket system (replace/refund, Dreamship-style)
- Audit log as explicit FR
- Sales Pricing Audit dashboard (multi-currency EUR rollup)
- Raw-material inventory + forecasting
- Catalog Dashboard per product
- Barcode scan sheet
- System health / observability dashboard
- Amazon integration (PD already tags Amazon orders red)
- Etsy message **export** (read-only, distinct from Conversations scope)

---

## 2. Consensus findings (all three agents agreed)

| # | Finding | Evidence | Action |
|---|---|---|---|
| C1 | Spec 002 must ship first, end-to-end, in production | BA: "no other feature has value"; Tech: "building on broken data"; DA: "real completion 40%" | Phase 0 commitment |
| C2 | Spec 004 is too large | BA: restructure around value; Tech: Gearment alone is 5 weeks; DA: "3 specs pretending to be 1" | Split 004a/004b/004c |
| C3 | Dual-mode sync is a trap | BA: defer 005; Tech: drop dual, keep only email_only/api_only; DA: race conditions unmanaged | Kill `dual` sync_mode |
| C4 | Three dashboards, not one | BA: explicit; Tech: delegation mixin will help; DA: "treated as a rename" | Rewrite Spec 003 |
| C5 | Missing observability is a time bomb | BA: implicit; Tech: implicit; DA: explicit | Build `multichannel.sync.health` in Phase 0 |
| C6 | Helpdesk is Enterprise-only, plans assume it exists | BA: flagged; Tech: noted; DA: explicit | Build minimal custom `etsy.order.ticket` |
| C7 | Raw-material inventory should reuse Odoo `stock` + `stock_forecasted` | BA: native leverage; Tech: don't build parallel model; DA: forecasting underestimated 5-10x | New Spec 007 using native modules |
| C8 | Timeline is 2-3x underestimated | BA: 6-8 week MVP is radical cut; Tech: implicit (Gearment 5 weeks); DA: 12-18 months realistic | Re-communicate to stakeholders |
| C9 | Etsy app scope review is a blocking external dependency | BA: can defer; Tech: implicit; DA: 3-8 weeks, parallel | Submit review **this week** |
| C10 | Product images in list is trivial but missing | BA: Marketing asked twice; Tech: `widget="image"`; DA: N/A | Add to Spec 003 US1 |

---

## 3. Key conflicts and resolutions

| Topic | BA view | Tech view | DA view | **Resolution** |
|---|---|---|---|---|
| Spec 005 priority | Defer entirely past MVP | Keep but drop dual-mode | Blocked on Etsy scope review anyway | **Defer implementation, submit review in parallel.** Start Spec 005 coding only after OAuth scopes approved. |
| Spec 004 split | Absorb tracking import into MVP, defer Gearment | Keep monolithic spec, refactor internally | Split into 3 sub-specs | **Split into 004a (tracking+carrier, MVP), 004b (Gearment), 004c (returns)**. Matches BA's sequencing. |
| Module decomposition | N/A | 4 modules (core/fulfillment/etsy_channel/migration) | N/A | **Adopt 4-module split before Spec 003 code starts.** |
| Pricing audit home | New Spec 006 | SQL view + optional snapshot model | N/A | **New Spec 006. Implementation: SQL view for dashboard, snapshot model for historical reports.** |
| Dashboard design | Three separate dashboards | Delegation mixin to manage field bloat | Treated as rename — underestimate | **Three dashboards + delegation mixin. Spec 003 fully rewritten.** |
| Ticket system | Custom minimal, not helpdesk | N/A | Decide build vs buy this week | **Custom minimal `etsy.order.ticket` on sale.order. Do not buy Enterprise.** |

---

## 4. Revised phased roadmap

All timelines assume 2 devs, 18 effective days/month, 2-3 days/task realistic. Slack for triage and review.

### Phase 0 — "Make Spec 001 real" + Spec 005 sandbox scaffolding (5-7 weeks)

**Goal**: 17,659 orders become usable; observability in place; external dependencies unblocked; Etsy API client scaffolding landed against a dev token so Phase 1 cutover starts the moment scopes are approved.

**Revised 2026-04-13 per [ADR-008](adrs/ADR-008-api-first-pivot.md)**: Spec 005 Phase 0 work (OAuth scaffolding, client library, order syncer against dev shop, test harness) lands in parallel with Spec 002 cleanup. Etsy scope review is now **critical path**, not parallel-nice-to-have.

| Work | Spec | Why |
|---|---|---|
| **Priority 1 — submit Etsy app scope review this week** (all scopes: `transactions_r/w`, `listings_r/w`, `shops_r`, `email_r`, optional `conversations_r`) | 005 | ADR-008 §4, C9 |
| Spec 002 US1 (financial data) + US2 (confirm workflow) + US6 (migration wizard) | 002 | C1 — unblock the 17K |
| Build batch-resumable migration wizard with per-500 savepoints and `last_processed_id` checkpoint; drop 30-min SLA | 002 | DA #3 |
| Manual triage / archive of 423 $0 orders; freeze 500-order known-good sample | 002 | DA #2 |
| Customer-dedup wizard producing CSV of proposed merges for BA approval (never auto-merge) | 002 | DA #9 |
| **New**: `multichannel.sync.health` model + single dashboard tile (last_run, row_count, error_count per integration, `parser_template_drift` metric per ADR-008 §7) | 002 | DA #6, ADR-008 |
| **Spec 005 sandbox**: OAuth2 PKCE flow against dev token, `EtsyApiClient`, shared rate limiter, `EtsyOrderSyncer` against owner's dev shop, `etsy.api.log`, VCR-style test fixtures recorded from dev shop (2-3 representative shops read-only where owner is collaborator) | 005 | ADR-008 §2 |
| **Parallel**: Gearment sandbox POC — 3-day spike verifying auth, rate limits, HMAC format, draft/quote/confirm idempotency | 004b | DA #4 |
| **Parallel**: GKE Excel schema fingerprinting — hash column layout on import, hard-fail on unknown | 004a | DA #4.3 |
| Ban `_logger.info(` in `models/` and `services/` via pre-commit hook; fix 6 existing violations | — | Tech #7 |
| Add `tracking_number` index + composite `(etsy_shop_id, etsy_last_modified DESC)` | — | Tech #9 |
| Provision staging instance at `129.150.63.207` with nightly prod DB snapshot restore; point outbound calls at Etsy/Gearment sandboxes | infra | Q10 answer 2026-04-13 |

**Exit criteria**: BA lead signs off on reconciliation report (Odoo totals vs Excel per shop). Health dashboard shows green. 17K orders confirmed with correct fiscal config. 423 $0 orders resolved. Etsy scope review **submitted** (acceptance ≠ received). Spec 005 client passes integration tests against dev-token shop with zero writes to any non-dev shop.

**Progress as of 2026-04-26**:
- ✅ Spec 002 US1 (financial data, T015–T020) + US2 (auto-confirm workflow, T021–T024) landed in 002 MVP commit `874e06ada5f`.
- ✅ `etsy.sync.health` observability model (T006–T009) landed in 002 MVP — feeds P0-11 dashboard work.
- ✅ Spec 002 US3 (product config — storable + auto-categorize, T025–T027) + US4 (3-tier customer dedup, ISO state-code lookup, ~50 country overrides, T028–T030) landed on `main` 2026-04-26 (Wave 1 GREEN, 3 commits). Module installs cleanly; 6 W1 tests pass.
- ✅ Spec 005 sandbox tasks.md generated (110 tasks across 10 phases). Architect advisory landed; Owner accepted defaults pending W7 E2E review. P0-14..17 unblocked.
- ✅ Workflow pivot to single-workspace-on-main (`.claude/plans/006-implementation-playbook.md` rev 1) — eliminates worktree-mount friction; worktrees reserved for rework/bugfix.
- ⏳ **Next**: W3 — Spec 002 US5 (import wizard robustness, header-based mapping, 500-row savepoints) + US6 (17K migration wizard, batch-resumable). T032 (savepoint refactor) auto-clears 4 inherited test failures from MVP slice.
- ⚠️ Critical path: **E1 Etsy scope review still not submitted** — every additional week widens the Phase 1 slip.

### Phase 1 — Three Dashboards + Approval Workflows + Spec 005 production cutover (5-8 weeks)

**Goal**: Replace the Google Sheet entirely for BA and Marketing. Ship the safety-critical workflows. **And** begin per-shop default to `active_source='api'` as soon as Etsy scopes are approved (with email failover staying live behind the same canonical pipeline).

**Revised 2026-04-13 per [ADR-008](adrs/ADR-008-api-first-pivot.md), refined 2026-04-26 per [ADR-008a v2](adrs/ADR-008a-email-as-mandatory-backup.md)**: Spec 005 production cutover runs in parallel with dashboard work once scopes arrive. Dashboards don't block on scopes; cutover doesn't block on dashboards (but benefits from the Tracking Dashboard being live). "Cutover" now means flipping `etsy.shop.active_source='api'`; the email adapter remains the per-shop failover source forever.

**Status snapshot (updated as slices land)**:

- ✅ **P1-05 `sale.order.fulfillment` delegation mixin** (Spec 003 + ADR-007 Direction A) — landed 2026-04-27 on `feature/006-master-plan-coding`. 12 fields + `_inherits` extension on `sale.order`; post_init backfill for 17K existing orders.
- ✅ **P1-06 unified `shipping.carrier`** (Spec 003 + ADR-005) — landed 2026-04-27. Standalone model + 7-row seed (USPS / UniUni / YunExpress / 4PX / DHL eCommerce / FedEx SmartPost / GKE Local); `shipping_carrier_id` Many2one on fulfillment row.
- ✅ **P1-04 Address-change approval workflow** (Spec 003 US4, safety-critical) — landed 2026-04-29. New `etsy.address.change.request` model + `mail.thread` + 3 constraints + atomic `action_approve` with `approve_address_change=True` context bypass on C-SO-001; 3 BA groups; sale.order banner + readonly `partner_shipping_id` while pending. RPC-level group gate + Markup-escaped chatter bodies (security review CRITICAL fixes).
- ✅ **P1-01a Order Dashboard** (Spec 003 US1, operator entry point) — landed 2026-04-29. New fields `sales_channel` + `channel_order_ref` on sale.order (mhc, indexed, FR-024/025 backfill via post_init_hook + migration script). Stored computes `qty_total` / `is_duplicate_buyer` (cron-driven retroactive) / `is_overdue_approval` (cron picks up calendar-only transitions). Order Dashboard list view + 4 row decorations + Operations menu. Composite index `(sales_channel, has_pending_address_change)` in etsy_integration. T060 "Request address change" button placeholder. Pipeline fields (`x_pipeline_id` / `x_pipeline_state_id`) + C-SO-002 + design_status rollup + 17K-row perf benchmark deferred to P1-08 / P1-02 / E2E sprint.
- ✅ **P1-02a Design file MVP** (Spec 003 US5, email-fallback E2E unblocker) — landed 2026-04-29. New `design.file` Model in `multichannel_hub_core` (mail.thread + activity.mixin, `tracking=True` on state, Vietnamese 3-col kanban under Operations menu, RPC-gated `action_approve`/`action_reject`). 10 MB cap dual-enforced (`@api.constrains` + `ir.attachment` `@api.model_create_multi` override) configurable via `multichannel_hub.large_file_threshold_bytes` ICP. `sale.order.line.design_status` stored compute (lowest-state-wins). Idempotent T078 historical seed from `etsy_design_link_front/back`. New `group_production_team` + 3 ACL rows. P1-02 split into b/c/d for routing, GDrive upload, and bulk PDF — all `todo` after P1-02a.
- ✅ **P1-03 Tracking Dashboard** (Spec 003 US2) — landed 2026-04-29. New mhc fields `pd_pic_user_id` + `warehouse_zone` + `order_id` back-ref on `sale.order.fulfillment`; etsy_integration `_inherit` extension adds `etsy_ship_notified_at` (`groups=base.group_system`). Tracking Dashboard list (13 cols + decoration) + search (5 group-by filters) + Operations menu + Mark-Shipped server action. `action_bulk_mark_shipped` RPC-gated + silent-skip + sticky warning per FR-017; **write-level `_ADDRESS_LOCK_FIELDS` defense-in-depth** (security CRITICAL fix — defeats direct-RPC bypass). bus.bus channel `multichannel_hub.fulfillment_update` emit on write+create gated to ship-relevant fields. Production_team R/W ACL row + migration backfill for `order_id`. T036 Excel export deferred to P2-01 (Spec 004a US1 owns canonical GKE schema).
- ⏳ **P1-02b Design file routing** — `design.file.route` model + auto-route on confirm + stuck-route badge.
- ⏳ **P2-01..05 GKE Excel tracking import** (Spec 004a US1–US5) — closes the email-fallback E2E demo loop with P1-03 Tracking Dashboard. Includes the deferred T036 export-format design (FR-006 round-trip).
- ⏳ **P1-10..13 Spec 005 production cutover** — `waiting` on E1 (Etsy scope review submitted 2026-04-27, awaiting 3–8 weeks).

| Work | Spec | Why |
|---|---|---|
| Rewrite Spec 003: Order Dashboard | 003 (rewritten) | C4 |
| Order Dashboard: product image (`image_128` widget), merged Tracking state column, row decorations (qty>=2, duplicate, Push, Amazon), store-manager avatar, MP note field, overdue-approval marker | 003 | BA #1-5, Marketing requests, C10 |
| Tracking Dashboard (NEW): dedicated page with export/import, bulk state change, search, tracking fields sync to Order Dashboard | 003 | BA #6 |
| **Address-change approval workflow** (NEW): `etsy.address.change.request` model, Requested/Approved/Rejected states, `mail.activity` to BA, lock sale.order shipping fields while pending, sync to Tracking Dashboard | 003 | BA #9, safety-critical |
| Design file upload + 3-state approval (Cho duyet/Duyet/Can chinh lai) with kanban view | 003 US2/US3 | Already planned |
| Audit log as explicit FR: `tracking=True` across all tracked fields + chatter tab AC | 003 | BA #8 |
| Extract `sale.order.fulfillment` delegation mixin before code is written | 003/004 | Tech #3 |
| Unify carrier model: promote `sale.order.shipping_carrier` to `Many2one('shipping.carrier')`, delete `etsy.carrier.mapping` | 003 | Tech #1 |
| Vietnamese UI: wrap all strings in `_()`, commit `.po` file | 003 | BA R10 |
| Design file storage policy: GDrive-URL primary, filestore fallback, hard-fail if >10 MB to `ir_attachment` | 003 | [ADR-006 revised 2026-04-13](adrs/ADR-006-design-file-storage.md) |
| **Spec 005 production cutover** (gated on scope approval): pilot shop flips to `active_source='api'` once the API adapter has succeeded at least once; health-check cron + recovery probe per ADR-008a §3 govern auto-failover/auto-recovery. Target: 3-5 shops cutover by end of Phase 1, rest in Phase 2. | 005 | ADR-008a §2-§3 |
| **Spec 005 production OAuth**: replace dev token with per-shop production OAuth flow; wire `EtsyTrackingPusher` to the Tracking Dashboard's tracking writes (reads `shipping.carrier.etsy_carrier_name`) | 005 | ADR-008 |
| **Health metric tiles** (permanent ops): `active_source_per_shop`, `auto_failover_count_7d`, `time_since_last_recovery_probe_success`, `parser_template_drift` per ADR-008a §6 | 005/006 | ADR-008a §6 |

**Exit criteria**: BA team working primarily in Odoo for order review, tracking management, and address-change approvals. Google Sheet in read-only mode. 4-week parallel run complete. Drift <1% for 10 consecutive days. At least one pilot shop running `active_source='api'` in production with the health-check cron + recovery probe operational and zero data loss across at least one observed auto-failover/auto-recovery cycle (or 30 days without a failover event, whichever comes first).

### Phase 2 — Tracking Import + Process Dashboard + remaining shop cutovers (4-5 weeks)

**Goal**: Close PD's biggest daily pain (tracking reconciliation) and give BA+PD a shared production view. **Default `active_source='api'` for the remaining 14-16 shops** (email failover stays live behind the same canonical pipeline; nothing is decommissioned).

**Revised 2026-04-13, refined 2026-04-26**: Spec 004a now includes the GDrive polling service (per [Q7 answer](#8-open-questions-for-follow-up); GDrive failover details per [ADR-012](adrs/ADR-012-gdrive-failover.md)). Remaining shop cutovers run in the background against the already-live Spec 005 pipeline. The email adapter is **not** sunset; it stays operational on the same cron and the same canonical pipeline as a permanent failover (ADR-008a §4).

| Work | Spec | Why |
|---|---|---|
| Spec 004a: Tracking import wizard (GKE Excel) with schema fingerprinting | 004a | DA #4.3 |
| Carrier auto-detection service (USPS/UniUni/YunExpress regex + prefix match) | 004a | Tech |
| `shipping.carrier` model with `etsy_carrier_name` field (for future Etsy push mapping) | 004a | Tech #1 |
| `tracking.import.log` + `tracking.import.line` with manual conflict resolution UI | 004a | Spec 004 |
| **Process Dashboard** (NEW): unified VN+US production view with PD's 18 columns, status enum with Vietnamese labels and color coding, row tags from Phase 1 | 004a | BA #14, PD feedback |
| Production status state machine with stock moves on transition to "Đã sản xuất" (reuse Odoo stock.move) | 004a | PD, Tech |
| **GDrive polling service** (NEW per Q7 answer 2026-04-13): cron-driven poll of per-partner GDrive folders (GKE first, UniUni/YunExpress/USPS later), detect new Excel files by `file_id` + `modified_time`, auto-ingest via the Spec 004a wizard. OAuth via service account. Manual upload remains fallback. | 004a | Q7 answer |
| Remaining per-shop default to `active_source='api'` (14-16 shops) | 005 | ADR-008a §2 |

**Exit criteria**: Daily GKE Excel imports run via wizard (manual OR auto-polled from GDrive). BA's Tracking Dashboard reflects imports within 5 minutes. PD's Process Dashboard in use for all in-flight orders. All 19 shops default to `active_source='api'`; the Gmail cron continues polling on the same schedule as the permanent failover source — it is never disabled.

### Phase 3 — REMOVED per [ADR-008](adrs/ADR-008-api-first-pivot.md)

**2026-04-13**: Spec 005 work has been redistributed across Phases 0–2. The freed Phase 3 capacity moves directly into Phase 4 (Gearment + returns + pricing audit), effectively accelerating that phase by ~4 weeks.

The original Phase 3 content is preserved below for traceability but is no longer a distinct phase in the execution plan.

---

#### ~~Original Phase 3 — Etsy API v3 (after scope approval, 6-8 weeks)~~

**~~Prerequisite~~**: ~~Etsy app scopes approved.~~

| Work | Spec | Why |
|---|---|---|
| Spec 005 rewrite: replace `sync_mode` enum with `etsy.shop.active_source` (`api` | `email`) per [ADR-008a v2 §2](adrs/ADR-008a-email-as-mandatory-backup.md); the 1-week audit mode is no longer needed since both sources share the same canonical pipeline | 005 | C3 (superseded by ADR-008a) |
| Shared rate limiter utility (`multichannel_hub_core/utils/rate_limiter.py`) | 005 | Tech #4 |
| Shared webhook controller base with HMAC + idempotency + rate-limit guard | 005 | Tech #5 |
| `EtsyApiClient` — OAuth2 PKCE, token refresh, retry with backoff, quota monitoring | 005 US1/US5 | Core |
| `EtsyOrderSyncer` — incremental receipt sync, dedupe via `etsy_order_id` UNIQUE | 005 US2 | Core |
| `EtsyTrackingPusher` — carrier name mapping (from `shipping.carrier.etsy_carrier_name`), `transactions_w` | 005 US3 | Core |
| Webhook receiver with HMAC-SHA256 verification (downgraded from P1 to P2) | 005 US4 | Tech/BA scope cut |
| Pre-Spec-005 validation pass: verify historical `etsy_order_id` format matches API response | 005 | Tech |
| Pilot shop cutover: flip `active_source='api'` once API adapter has succeeded; health-check + recovery probe per ADR-008a §3 cover any subsequent transient outage. No "audit mode" needed — both adapters produce the same canonical record. | 005 | Tech (superseded by ADR-008a) |

**Explicitly out of scope for MVP of Spec 005**: bidirectional listing management (US6, defer to P3), Etsy customer messaging (US7, deferred — Conversations scope not granted).

### Phase 4 — Gearment + Returns + Pricing Audit (6-8 weeks)

| Work | Spec | Why |
|---|---|---|
| Spec 004b: Gearment adapter (prerequisite: Phase 0 spike validated) | 004b | Consensus split |
| `fulfillment.partner` adapter base (Protocol), Gearment adapter with draft/quote/confirm state machine, rate limiter reuse, HMAC webhook handler with idempotency | 004b | Tech/DA |
| Spec 004c: Returns/refunds workflow + `etsy.order.ticket` minimal custom (replace/refund with BA approval) | 004c | BA #7 |
| **New Spec 006**: Sales Pricing Audit dashboard — SQL view reading sale.order + res.currency.rate, computed `amount_total_eur` and `price_delta_vs_catalogue`, state bands (under/at/over) with list decorations | 006 | BA R5 |
| Etsy message export (read-only CSV) — distinct from Conversations scope, uses public messaging API if available | 005 or 006 | Marketing |

### Phase 5 — Inventory, Catalog, Scan, Amazon (parallel tracks from Phase 4)

| Work | Spec | Why |
|---|---|---|
| **New Spec 007**: Raw-material inventory — Excel seed wizard, `product.template` with `type='product'` in "Raw Materials" category, auto-decrement via stock.move on production transition, native `stock.warehouse.orderpoint` + `stock_forecasted` report, 1/3/12-month forecasting, low-stock alerts | 007 | PD feedback |
| **New Spec 008**: Catalog Dashboard (per-product template + mockup + smart buttons to orders) | 008 | BA #11 |
| **New Spec 009**: Barcode scan sheet (evaluate `stock_barcode` CE fit; fallback custom `/scan` controller) | 009 | BA #15 |
| **New Spec 010**: Amazon channel integration (reuse `multichannel_hub_core` — `sales_channel` already scaffolded) | 010 | PD already tags Amazon orders |
| **New Spec 011**: Website channel integration | 011 | Owner's vision |

---

## 5. Risk register (top 15 with mitigations)

| # | Risk | Likelihood | Impact | Mitigation | Phase |
|---|---|---|---|---|---|
| R1 | Etsy scopes denied (`transactions_w`) | Medium | High — Spec 005 loses half value | Submit review **this week**; document per-scope fallback plan | Phase 0 |
| R2 | 17K migration OOMs or partially rolls back | High | High — data in mixed state | Batch-resumable wizard with 500-row savepoints + checkpoint; overnight run; rollback plan | Phase 0 |
| R3 | Gearment v3 API undocumented / rate-limit scope unknown | High | Medium — blocks Phase 4 | 3-day sandbox spike **in Phase 0** | Phase 0 |
| R4 | GKE Excel schema changes silently | High | High — tracking corruption | Schema fingerprint + hard-fail on unknown schema | Phase 2 |
| R5 | Customer dedup false merges (GDPR) | Medium | Critical — legal exposure | BA-approval CSV, never auto-merge | Phase 0 |
| R6 | Design file storage exceeds `ir_attachment` capacity | Medium | High — DB bloat | Filestore/URL only, 10 MB hard cap | Phase 1 |
| R7 | Dual-mode sync race conditions | Medium | High — silent data corruption | Drop dual mode; audit mode only | Phase 3 |
| R8 | Etsy OAuth refresh fails day 91 | Medium | High — sync silently stops | Health dashboard watches `last_successful_sync_at`; alerts at 24h gap | Phase 0/3 |
| R9 | Etsy rate limit + QPD exhaustion during bulk sync | High | Medium — partial sync | Respect bucket; cron cadence tuned to QPD; health dashboard tracks headroom | Phase 3 |
| R10 | Vietnamese diacritics corrupted in Excel round-trip | Medium | Medium — data quality | UTF-8 sanity check on every import; never trust Windows Excel exports | Phase 0/2 |
| R11 | GKE date format DD/MM/YYYY misparsed without `dayfirst=True` | High | Medium — date inversions | Explicit date-parsing tests with day<=12 fixture | Phase 2 |
| R12 | Timeline slippage (2-3x under-estimate) | High | High — stakeholder expectations | Re-communicate 12-18 month realistic; ship MVP (Phases 0-2) first | Phase 0 |
| R13 | Spec 003 field bloat on sale.order (40+ new fields) | High | Medium — cognitive load + form chaos | Delegation mixin `sale.order.fulfillment` **before** Spec 003 code starts | Phase 1 |
| R14 | Helpdesk / documents / documents_google_drive assumed but Enterprise-only | High | High — redesign mid-flight | Decision memo this week; commit to custom minimal models | Phase 0 |
| R15 | Observability absent; outages found 2-3 days late by BA | High | Medium — trust erosion | `multichannel.sync.health` model + dashboard tile in Phase 0 | Phase 0 |

---

## 6. Decisions required from owner (this week)

**Status: ALL SIGNED OFF — 2026-04-13.**

| # | Decision | Outcome |
|---|---|---|
| 1 | **Timeline reset** — 12–18 months realistic; Phases 0–2 (13–16 weeks) as MVP | Approved |
| 2 | **Spec 004 split** into 004a / 004b / 004c | Approved ([ADR-001](adrs/ADR-001-spec-004-split.md)) |
| 3 | **Spec 005 deferral** to Phase 3; Etsy app review submission runs in parallel now | Approved ([ADR-002](adrs/ADR-002-drop-dual-sync-mode.md) + spec.md deferral banner) |
| 4 | **New specs** 006 (Pricing Audit), 007 (Inventory), 008+ (Catalog, Scan, Amazon, Website) | Approved |
| 5 | **Module decomposition** into 4 modules before Phase 1 code | Approved ([ADR-003](adrs/ADR-003-module-decomposition.md)) |
| 6 | **Enterprise vs Custom** — build custom minimal implementations (no Enterprise buy) | Approved ([ADR-004](adrs/ADR-004-enterprise-alternatives.md)) |
| 7 | **Vietnamese UI** as cross-cutting FR for every spec | Approved |
| 8 | **Spec 002 SLA revision** — drop `<30 min`, adopt batch-resumable overnight + reconciliation sign-off | Approved (already reflected in plan.md 2026-04-10 revision) |
| 9 | **Gearment sandbox access** — owner to obtain credentials for Phase 0 spike | Committed |

Clarification applied to decision 3: `sync_mode` keeps exactly two values (`email_only`, `api_only`), with **`api_only` as the default for new shops**; existing 19 shops remain `email_only` until per-shop cutover (see [ADR-002](adrs/ADR-002-drop-dual-sync-mode.md)). **Superseded 2026-04-26 by [ADR-008a v2 §2](adrs/ADR-008a-email-as-mandatory-backup.md)**: the `sync_mode` enum is replaced by `etsy.shop.active_source` (`api` | `email`) with health-check-driven auto-failover and recovery-probe auto-recovery; the migration mapping is `email_only` → `active_source='email'`, `api_only` → `active_source='api'`.

Additional ADRs accepted at the same sign-off (not in original §6 list but flagged during review):
- [ADR-005](adrs/ADR-005-carrier-unification.md) — Unified `shipping.carrier`; delete `etsy.carrier.mapping`
- [ADR-006](adrs/ADR-006-design-file-storage.md) — **Revised 2026-04-13**: GDrive-URL primary, filestore fallback, 10 MB cap
- [ADR-007](adrs/ADR-007-fulfillment-delegation-mixin.md) — `sale.order.fulfillment` delegation mixin

**Stage-2 ADRs accepted 2026-04-26 (recorded in `decision-log.md`):**

| # | Decision | Outcome |
|---|---|---|
| 14 | **Email parser as permanent failover** behind a single canonical ingestion pipeline; source-switching via `etsy.shop.active_source`; health-check + recovery probe; supersedes ADR-002 sync_mode enum and ADR-003 `etsy_channel_legacy` naming | Approved ([ADR-008a v2](adrs/ADR-008a-email-as-mandatory-backup.md)) |
| 15 | **File lifecycle data model** — `design.file` + `design.file.route` + `design.print.batch`; immutable history via `parent_file_id`; queued-job route delivery with stuck-route warning | Approved ([ADR-009](adrs/ADR-009-file-lifecycle.md)) |
| 16 | **Configurable order pipeline** — `order.pipeline` + `order.pipeline.state` + `pipeline.team` + `order.pipeline.transition.log`; default seed is the 17 Vietnamese stages; admin can add pipelines (e.g., Gearment POD, Multi-Technique Hybrid); resource assignment per stage with per-order override; pipeline auto-versioning on first-use edit; collapses ADR-011 | Approved ([ADR-010](adrs/ADR-010-configurable-order-pipeline.md)) |
| 17 | **GDrive failover** — service account, alert + queue + backoff on auth failure, **no auto-fallback to Discord**; Discord remains the permanent **manual** escape hatch (no sunset) | Approved ([ADR-012](adrs/ADR-012-gdrive-failover.md)) |

**Pivot sign-off 2026-04-13 (supersedes decision 3):**

| # | Decision | Outcome |
|---|---|---|
| 10 | **API-first pivot** — email parsing enters maintenance mode; Spec 005 moves to Phase 0 (sandbox) + Phase 1 (cutover); scope review is critical path | Approved ([ADR-008](adrs/ADR-008-api-first-pivot.md)) |
| 11 | **GDrive for design files + tracking Excel** — ADR-006 revised: design files primary-store on GDrive with URL in Odoo; Spec 004a expanded with GDrive polling cron (Q7 answer) | Approved (ADR-006 revision, Spec 004a amendment) |
| 12 | **Amazon + Website** — architecture-planning only during Phases 0–2; implementation after all 19 Etsy shops on `api_only` in production | Approved (Q5 answer) |
| 13 | **Staging environment** — confirmed at `129.150.63.207`; nightly prod snapshot restore is a Phase 0 infra task (Q10 answer) | Approved |

---

## 7. Immediate next steps (this week, before any code)

**Wave A (completed 2026-04-13):**

1. ✅ Owner signed off on all 9 decisions.
2. ✅ ADRs 001–007 authored, reviewed, and marked Accepted.
3. ✅ Spec 002 `plan.md` — already contains batch-resumable wizard, R8/R9/R10 revisions, reconciliation sign-off criterion.
4. ✅ Spec 002 `data-model.md` — added `etsy_price_anomaly`, `etsy.sync.health` model, wizard resume/anomaly/health fields, ACL rows.
5. ✅ Spec 005 `spec.md` + `plan.md` — deferral banner; `sync_mode` reduced to 2 values with `api_only` default; `sync_audit_mode` added; US4 webhooks P1→P2; `etsy.carrier.mapping` removed per ADR-005.
6. ✅ Spec 003 `tasks.md` — frozen with SUPERSEDED banner pointing to Wave B rewrite.
7. ✅ Spec 004 `tasks.md` — frozen with SUPERSEDED banner; 004a/004b/004c split noted.

**Still to do (actions, not spec-edits):**

8. **Submit Etsy app review** with all required scopes — **CRITICAL PATH** per [ADR-008](adrs/ADR-008-api-first-pivot.md). Start the 3–8 week clock. Guide for owner: [guides/vi/etsy-app-review-guide.md](guides/vi/etsy-app-review-guide.md).
9. **Request Gearment sandbox credentials** (owner task per decision 9). Guide for owner: [guides/vi/gearment-sandbox-guide.md](guides/vi/gearment-sandbox-guide.md).
10. **Create `.claude/plans/006-master-plan-tracking.md`** to track execution of this plan. *(Created 2026-04-13.)*
11. **Provision staging environment** at `129.150.63.207` with nightly prod DB snapshot restore (Q10 answer, decision 13).
12. **Revise ADR-006** to add GDrive-URL primary mode (decision 11). *(Completed 2026-04-13.)*
13. **Amend Spec 004a** scope to include GDrive polling cron for logistics partners (decision 11). *(Completed 2026-04-13.)*

**Wave B (completed 2026-04-13):**

11. ✅ Spec 003 `spec.md` rewritten — 7 user stories covering three dashboards (Order / Tracking / Process), address-change approval workflow (safety-critical), design-file 3-state approval with 10 MB cap + URL mode (ADR-006), multi-channel foundation, audit + Vietnamese i18n as cross-cutting FRs, delegation mixin + unified carrier alignment (ADRs 003 / 005 / 007). Old spec archived under `_archive/`.
12. ✅ Spec 004a `spec.md` authored at `specs/004a-tracking-import/` — 5 user stories covering GKE Excel wizard with schema fingerprinting, carrier detection service, Process Dashboard stock-move hook, import log + line + replay, carrier admin UX. ADR-001 split formalised.

**Wave B deferred (non-blocking):**

- `plan.md` + `data-model.md` regeneration for Spec 003 and Spec 004a. Spec.md is authoritative; plan/data-model can be produced when implementation starts.

**Wave C (after Phase 0 ships):**

13. New specs `004b`, `004c`, `006` (Pricing Audit), `007` (Inventory); rewrite Spec 005 post scope approval; then 008+.

---

## 8. Open questions for follow-up

1. **Team size**: Confirm the number of developers actually available. The 12-18 month estimate assumes 2 devs.
2. **Current $0-price orders**: Who decides what price to assign? Is there a source to recover from (Etsy API, payment processor, accounting)?
3. **Customer dedup historical policy**: Are repeat-customer analytics needed for the 17K historical orders, or is future-only dedup sufficient?
4. **Design file size reality**: **ANSWERED 2026-04-13** — Design files to be stored on **Google Drive**, not in Odoo filestore or `ir_attachment`. Odoo stores only the GDrive URL/file ID reference. This supersedes ADR-006's filestore-only path for design files; filestore remains for small thumbnails. Action: revise [ADR-006](adrs/ADR-006-design-file-storage.md) to add GDrive-URL as the primary storage mode; Odoo field stores `gdrive_file_id` + public/preview URL.
5. **Amazon timeline**: **ANSWERED 2026-04-13** — Amazon integration is **system-architecture planning only** during Phases 0–3. Implementation starts **after Etsy full flow is live in production** (end of Phase 3 / Spec 005 cutover). Confirms Spec 010 stays in Phase 5. Action: ensure `multichannel_hub_core` abstractions (`sales_channel`, delegation mixin, unified carrier) are Amazon-ready by Phase 1 exit, but no Amazon code before Etsy cutover.
6. **Sales team count**: Per-MP toggle for tracking push (Marketing) — how many MPs? Per-shop suffices?
7. **Google Drive necessity**: **ANSWERED 2026-04-13** — GDrive is **required**, not optional. Logistics partners (GKE, and future UniUni/YunExpress/USPS) will upload Excel tracking files to their own GDrive folders. Odoo runs a scheduled cron that polls each partner's folder, detects new files, and auto-imports via the Spec 004a wizard. Action: Spec 004a scope expands to include GDrive polling service (per-partner folder config, OAuth service account, incremental import by file-id + modified-time). Manual Excel upload remains as fallback.
8. **`stock_barcode` CE availability in Odoo 19**: Confirm before committing Spec 009 scope.
9. **Multi-warehouse**: Does the team have separate US and VN warehouses requiring `stock.location` per warehouse, or is this logical only?
10. **Staging environment**: **NEEDS MORE DETAIL FROM OWNER.** Context: a staging environment is a **separate, production-like Odoo instance** (same module versions, same DB schema, copy or anonymised subset of production data) used to test risky changes **before** they touch production. It is a Phase 0 prerequisite for any API work because: (a) Gearment/Etsy API tokens need somewhere safe to call without polluting live orders; (b) the 17K-order migration wizard (Spec 002) must be dry-run end-to-end on a full DB copy to verify row-count reconciliation before the production run; (c) OAuth refresh and webhook HMAC paths cannot be tested against production without risking silent data corruption (R7/R8). Typical setup: second docker-compose stack on a different host/port (e.g. `staging.odoo.internal:8169`) with nightly DB snapshot restore from prod, `--test-enable` allowed, and all outbound partner calls pointed at sandbox endpoints. **Question for owner**: (i) does any non-production Odoo instance exist today? (ii) if not, is infra/budget available to stand one up in Phase 0? (iii) who owns the nightly DB snapshot job?

---

## Appendix A — Consensus matrix (summary of agent agreement)

| Topic | BA | Tech | DA |
|---|---|---|---|
| Ship Spec 002 first | YES | YES | YES |
| Split Spec 004 | Restructure | Keep | Split in 3 |
| Drop dual-mode sync | Defer 005 | Drop | Race conditions |
| Three dashboards | YES | Delegation helps | Treated as rename |
| Address-change approval missing | YES | N/A | N/A |
| Ticket system via custom (not helpdesk) | YES | N/A | Enterprise trap |
| Raw material = native stock | YES | YES | Forecasting underestimated |
| Product images + decorations | YES | Trivial | N/A |
| Observability absent | Implicit | Implicit | Explicit |
| Timeline underestimated | 6-8 week MVP cut | Gearment 5 weeks alone | 12-18 months |
| Etsy scopes blocking | Can defer | N/A | Submit review NOW |
| Carrier model fragmented | N/A | Tech #1 | N/A |
| Design file storage sizing | N/A | N/A | 1.7 TB risk |
| Vietnamese i18n as cross-cutting FR | YES | N/A | Diacritic corruption risk |
| Module decomposition into 4 | N/A | YES | N/A |

---

## Appendix B — Source files consulted

### End-user feedback (all in `.0temp/end_user_feed_back/`)
- `Phòng BA.docx` — 15 numbered requests from BA department
- `Phòng Marketing.pdf` — Marketing requests (tracking toggle, images, deadlines, push, overdue marker, store-manager icon, popup notifications, message export)
- `Feedback PD.xlsx` — Production dashboard + raw material inventory + forecasting + status enum
- `Feedback phòng RD.xlsx` — **Actually Sales/Pricing Audit** (mislabeled): multi-currency EUR rollup + delta vs catalogue
- `Đề xuất hệ thống mẫu.xlsx` — UI mockups for Order / Tracking / Processing dashboards

### Current Etsy data structure
- `.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx` — 34-column main sheet (TRANSACTION_ID through SUBTOTAL)
- `.0temp/sample_bc_don_hang2026_04_08.xls` — 19-column GKE tracking manifest (ORDER NUMBER through link qrcode)

### Existing specs
- `specs/001-etsy-order-migration/` (SHIPPED, 59/61 tasks)
- `specs/002-etsy-config-fixes/` (PLANNED, 62 tasks)
- `specs/003-dashboard-design-multichannel/` (PLANNED, 53 tasks)
- `specs/004-fulfillment-routing/` (PLANNED, 79 tasks)
- `specs/005-etsy-api-channel/` (PLANNED, spec+plan done, tasks.md missing)

### Shipped module
- `custom_addons/etsy_integration/` v19.0.1.0.0 (~1,776 LOC)
