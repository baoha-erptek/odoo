# Master Plan — odoo19_esty Multichannel E-Commerce Hub

**Date**: 2026-04-10
**Branch**: `005-etsy-api-channel`
**Inputs**: End-user feedback (5 departments, `.0temp/end_user_feed_back/`) + Specs 001–005 + current module state
**Method**: Three-agent review (BA/Odoo consultant, Technical architect, Devil's advocate)
**Agent reports**: [ba-consultant.md](agent-reports/ba-consultant.md), [tech-architect.md](agent-reports/tech-architect.md), [devils-advocate.md](agent-reports/devils-advocate.md)

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

### Phase 0 — "Make Spec 001 real" (4-6 weeks)

**Goal**: 17,659 orders become usable; observability in place; external dependencies unblocked.

| Work | Spec | Why |
|---|---|---|
| Spec 002 US1 (financial data) + US2 (confirm workflow) + US6 (migration wizard) | 002 | C1 — unblock the 17K |
| Build batch-resumable migration wizard with per-500 savepoints and `last_processed_id` checkpoint; drop 30-min SLA | 002 | DA #3 |
| Manual triage / archive of 423 $0 orders; freeze 500-order known-good sample | 002 | DA #2 |
| Customer-dedup wizard producing CSV of proposed merges for BA approval (never auto-merge) | 002 | DA #9 |
| **New**: `multichannel.sync.health` model + single dashboard tile (last_run, row_count, error_count per integration) | 002 | DA #6 |
| **Parallel**: Submit Etsy app review with all required scopes (`transactions_r/w`, `listings_r`, `shops_r`, `email_r`) | 005 | DA #1, C9 |
| **Parallel**: Gearment sandbox POC — 3-day spike verifying auth, rate limits, HMAC format, draft/quote/confirm idempotency | 004b | DA #4 |
| **Parallel**: GKE Excel schema fingerprinting — hash column layout on import, hard-fail on unknown | 004a | DA #4.3 |
| Ban `_logger.info(` in `models/` and `services/` via pre-commit hook; fix 6 existing violations | — | Tech #7 |
| Add `tracking_number` index + composite `(etsy_shop_id, etsy_last_modified DESC)` | — | Tech #9 |

**Exit criteria**: BA lead signs off on reconciliation report (Odoo totals vs Excel per shop). Health dashboard shows green. 17K orders confirmed with correct fiscal config. 423 $0 orders resolved (fixed or archived).

### Phase 1 — Three Dashboards + Approval Workflows (4-6 weeks)

**Goal**: Replace the Google Sheet entirely for BA and Marketing. Ship the safety-critical workflows.

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
| Design file storage policy: filestore/URL only, hard-fail if >10 MB to `ir_attachment` | 003 | DA #10 |

**Exit criteria**: BA team working primarily in Odoo for order review, tracking management, and address-change approvals. Google Sheet in read-only mode. 4-week parallel run complete. Drift <1% for 10 consecutive days.

### Phase 2 — Tracking Import + Process Dashboard (3-4 weeks)

**Goal**: Close PD's biggest daily pain (tracking reconciliation) and give BA+PD a shared production view.

| Work | Spec | Why |
|---|---|---|
| Spec 004a: Tracking import wizard (GKE Excel) with schema fingerprinting | 004a | DA #4.3 |
| Carrier auto-detection service (USPS/UniUni/YunExpress regex + prefix match) | 004a | Tech |
| `shipping.carrier` model with `etsy_carrier_name` field (for future Etsy push mapping) | 004a | Tech #1 |
| `tracking.import.log` + `tracking.import.line` with manual conflict resolution UI | 004a | Spec 004 |
| **Process Dashboard** (NEW): unified VN+US production view with PD's 18 columns, status enum with Vietnamese labels and color coding, row tags from Phase 1 | 004a | BA #14, PD feedback |
| Production status state machine with stock moves on transition to "Đã sản xuất" (reuse Odoo stock.move) | 004a | PD, Tech |

**Exit criteria**: Daily GKE Excel imports run via wizard. BA's Tracking Dashboard reflects imports within 5 minutes. PD's Process Dashboard in use for all in-flight orders.

### Phase 3 — Etsy API v3 (after scope approval, 6-8 weeks)

**Prerequisite**: Etsy app scopes approved.

| Work | Spec | Why |
|---|---|---|
| Spec 005 rewrite: drop `dual` sync_mode, keep only `email_only` / `api_only` + 1-week audit mode as one-off | 005 | C3 |
| Shared rate limiter utility (`multichannel_hub_core/utils/rate_limiter.py`) | 005 | Tech #4 |
| Shared webhook controller base with HMAC + idempotency + rate-limit guard | 005 | Tech #5 |
| `EtsyApiClient` — OAuth2 PKCE, token refresh, retry with backoff, quota monitoring | 005 US1/US5 | Core |
| `EtsyOrderSyncer` — incremental receipt sync, dedupe via `etsy_order_id` UNIQUE | 005 US2 | Core |
| `EtsyTrackingPusher` — carrier name mapping (from `shipping.carrier.etsy_carrier_name`), `transactions_w` | 005 US3 | Core |
| Webhook receiver with HMAC-SHA256 verification (downgraded from P1 to P2) | 005 US4 | Tech/BA scope cut |
| Pre-Spec-005 validation pass: verify historical `etsy_order_id` format matches API response | 005 | Tech |
| Pilot shop cutover: 2-week audit mode (email + API both parse, only API writes, log diffs), then flip `api_only` | 005 | Tech |

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

1. **Timeline reset**: Confirm 12-18 month realistic estimate (not 3-6). Commit to Phases 0-2 as MVP (13-16 weeks).
2. **Spec 004 split approval**: Approve splitting Spec 004 into 004a / 004b / 004c.
3. **Spec 005 deferral approval**: Approve deferring Spec 005 implementation to Phase 3, but starting Etsy app review **now**.
4. **New specs approval**: Approve creating Spec 006 (Pricing Audit), 007 (Inventory), 008+ (Catalog, Scan, Amazon, Website).
5. **Module decomposition approval**: Approve splitting `etsy_integration` into 4 modules before Phase 1 code starts.
6. **Enterprise vs Custom decision**: Commit to custom minimal implementations for helpdesk, documents, approvals, documents_google_drive (do not buy Enterprise).
7. **Vietnamese UI commitment**: Accept that VN `.po` translation is a cross-cutting FR, not a nice-to-have, for every spec.
8. **Spec 002 target revision**: Drop "17K in <30 min" SLA; accept "batch-resumable overnight run with reconciliation sign-off".
9. **Gearment sandbox access**: Obtain sandbox credentials and hand them to the dev team for the 3-day spike in Phase 0.

---

## 7. Immediate next steps (this week, before any code)

1. **Owner signs off** on this master plan (decisions 1-9 above).
2. **Submit Etsy app review** with all required scopes. Start the 3-8 week clock.
3. **Request Gearment sandbox credentials**.
4. **Create ADR docs**:
   - ADR-001: "Spec 004 split into 004a/004b/004c"
   - ADR-002: "Drop dual-mode sync; email_only / api_only only"
   - ADR-003: "Module decomposition: core/fulfillment/etsy_channel/etsy_channel_migration"
   - ADR-004: "Enterprise alternatives: custom minimal implementations"
   - ADR-005: "Carrier unification — single `shipping.carrier` model"
   - ADR-006: "Design file storage: filestore/URL only, 10 MB cap"
   - ADR-007: "Sale.order delegation mixin `sale.order.fulfillment`"
5. **Update Spec 002** `plan.md` with batch-resumable wizard design and reconciliation sign-off criterion.
6. **Add `multichannel.sync.health` stub** to Spec 002's data-model.md.
7. **Archive / freeze** specs 003, 004, 005 `tasks.md` files — they will be regenerated after the master plan is approved.
8. **Dispatch `/speckit-specify`** for Spec 003 rewrite (three dashboards, delegation mixin, address-change approval, image+decoration pack).
9. **Create `.claude/plans/006-master-plan-tracking.md`** to track execution of this plan.

---

## 8. Open questions for follow-up

1. **Team size**: Confirm the number of developers actually available. The 12-18 month estimate assumes 2 devs.
2. **Current $0-price orders**: Who decides what price to assign? Is there a source to recover from (Etsy API, payment processor, accounting)?
3. **Customer dedup historical policy**: Are repeat-customer analytics needed for the 17K historical orders, or is future-only dedup sufficient?
4. **Design file size reality**: Actual distribution of current design file sizes (need to measure). Confirms or refutes the 1.7 TB concern.
5. **Amazon timeline**: When is Amazon integration needed? PD already tags Amazon orders red — is there already Amazon data coming in through some other channel?
6. **Sales team count**: Per-MP toggle for tracking push (Marketing) — how many MPs? Per-shop suffices?
7. **Google Drive necessity**: Manual Excel upload vs automated GDrive sync — what's the actual ops cost difference?
8. **`stock_barcode` CE availability in Odoo 19**: Confirm before committing Spec 009 scope.
9. **Multi-warehouse**: Does the team have separate US and VN warehouses requiring `stock.location` per warehouse, or is this logical only?
10. **Staging environment**: Does one exist? If not, it's a Phase 0 prerequisite for any API work.

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
