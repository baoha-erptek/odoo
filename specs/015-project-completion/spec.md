# Spec 015: Project Completion — Consolidated Backlog

**Date**: 2026-07-03 (alignment update 2026-07-04)  
**Status**: Draft for Owner Review  
**Source of Truth**: Master Plan 006 tracking (`.claude/plans/006-master-plan-tracking.md`) + specs 001–014 analysis + **2026-07-04 code-verification audit** (docs commits `8b105ba`..`2d873c2`)

---

## Context: What Is Shipped

**Master Plan 006 Execution**: 82.7% complete (153 done of 185 total tracked items).

### Shipped Phases (P0–P2, Inbound + Staging E2E)

- **Phase 0** (89% complete): Architecture setup, Etsy OAuth approval, Gearment discovery, observability foundation
- **Phase 1** (78% complete): Order, Tracking, Process dashboards; design file workflows; address-change approval; Etsy pilot-shop cutover ready
- **Phase 2** (75% complete): Tracking import, GKE Excel sync, GDrive polling; 18 remaining shop cutovers pending pilot sign-off

**Live on Staging**: E2E drop-ship pilot (11 of 12 sections PASS; GDrive config gap in §5, not code defect).

**Live on Production (Pilot)**: JaHandmadeArt shop on API ingest (0 email fallback).

### Shipped Modules (4 of 7 implementation modules)

1. **etsy_integration** — Email parser, Gmail OAuth, import wizard, config fixes (Specs 001–002)
2. **design** — Design file models, views, approval workflows (Spec 003)
3. **multichannel_hub_core** — Dashboards, fulfillment delegation, carriers, address-change workflow (Specs 003–004a)
4. **multichannel_hub_fulfillment** — Tracking import wizard, Gearment adapter (P0 spike complete) (Specs 004a–004b)

### Shipped User Stories

- Etsy email ingestion (Spec 001 US1–US10)
- Financial data correction + order confirmation (Spec 002 US1–US6)
- Three dashboards + design workflows (Spec 003 US1–US7)
- Address-change approval (Spec 003 US4)
- Gearment adapter (Phase 0 spike, P4-01-A through P4-01-D, plus 5 hotfixes)

---

## 2026-07-04 Alignment Update (post drift audit)

The 2026-07-04 docs-vs-code audit (docs commits `8b105ba`, `b142dee`, `eb1429f`, `2d873c2`) verified every backlog claim against `main`. Two systematic corrections:

1. **23 backlog items were already shipped in code** but carried `todo`/`doing` states copied from the stale tracker. They are re-marked **`shipped*`** in the tables below (state footnote: *code-verified 2026-07-04; each flips to `done` only when its covering MF-E2E gate item passes on staging*). Biggest impact: the entire Etsy publish pipeline (P-PUB-CLIENT/DRAFT/IMAGES/INVENTORY/PUBLISH), product hub models + SKU wizards, Excel catalog sync (parse/ingest/cron/images), and the whole Spec 004a tracking-import stack. Phase 3 is NOT 1% done — its implementation slices are code-complete and lack only E2E verification.
2. **9 doc-promised features never existed in code** — corrected in docs; the ones worth building enter this backlog as `AUD-01`–`AUD-05` (below), plus scope corrections on T024/T036/T038/P1-07.

### Reprioritized goal — Main-Flow E2E Gate (MF-E2E)

**The production gate is now: all 5 owner flows (docs/owner/business-flows/v2/) complete and E2E-proven.** Owner-set dispatch order (2026-07-04): **MF-E2E-1 → MF-E2E-2 → MF-E2E-3a → (MF-E2E-3b when E2 keys arrive) → MF-E2E-4 last.** *Status 2026-07-05 (EOD): **all gates 0/1/2/3a/3b/4 done** — full re-run ×1 + flow-4 ×2 on staging with mhc 19.0.1.0.77 (ESTY-250) + ei 19.0.3.19.0 (publisher SKU-link fix); only P1-11 remains for live tracking-push confirmation. **The Gearment vendor escalation is CLOSED** — Defect-2026-05-10-05 + -02 fixed via live probes; flow-3b draft push + quote both proven live 200 (no mock fallback).* Each gate item = (a) extend the sectioned python runner (pattern: `scripts/e2e_demo_drop_ship_ordertest2.py`, currently 11/12 PASS) + (b) one Playwright UAT spec (`tests/e2e/`, reusing existing page-objects/specs) + (c) staging pass + BA sign-off. **T073 is the umbrella exit criterion** — it closes when all five gate items pass.

| ID | Flow (owner doc) | State | Blocker | Size | Scope + reuse |
|---|---|---|---|---|---|
| **MF-E2E-1** | flow-1 Tạo sản phẩm → publish draft → active | **done** (2026-07-04) | — | L | Runner `scripts/e2e_flow1_publish.py` **10/10 PASS ×2** on staging (`docs/engineering/uats/E2E_FLOW1_PUBLISH_2026-07-04.md`); `uat_huong_dan_tao_san_pham.spec.ts` 11 pass ×2 + `uat_real_apron_publish.spec.ts` pass ×2 (live drafts). Live listings created→active→verified→deactivated on JaHandmadeArt. 2 product bugs found+fixed (19.0.3.16.0): `publish()` unscoped PATCH path 404; variant↔combo match ignored per-variant default_code when a non-publishable variant axis (Material) exists. SKU-drift-job decision: no scheduled job needed (see findings 2026-07-04). True Etsy DELETE needs `listings_d` scope — owner item. |
| **MF-E2E-2** | flow-2 Nhận đơn hàng Etsy | **done** (2026-07-04, staging scope) | P1-11 only for prod-shop assertions | M | Runner `scripts/e2e_flow2_orders.py` **7/7 PASS ×2** (`docs/engineering/uats/E2E_FLOW2_ORDERS_2026-07-04.md`): live receipt re-sync + dedupe (orders AND partners unchanged), cursor idempotency, manual fallback switch (audit-logged), email-path ingest + pipeline classification, sync-health rows for BOTH paths (new in 19.0.3.17.0). Playwright 7 pass ×2 incl. new TC-009. Owner items: active_source UI-toggle vs doc; tracking-push retry loop → 3a. |
| **MF-E2E-3a** | flow-3a Giao hàng in nội bộ | **done** (2026-07-04) | — (ENV-FIX-MRP verified present) | M | Runner `scripts/e2e_flow3a_fulfillment.py` **10/10 PASS ×2** (`docs/engineering/uats/E2E_FLOW3A_FULFILLMENT_2026-07-04.md`): Route-A SO → auto-MO → design approve → MO done → DO validated → GENERATED GKE xlsx (real refs) → GDrive poller → carrier auto-detect → Etsy push flags. Playwright 7 pass ×2. 4 product fixes: push retry cap (ei 3.18.0), poller-path carrier detect + bin_size schema compute (mhf 1.0.26), design-reject UI path (mhc 1.0.76). Live `pushed` confirmation → P1-11 (synthetic receipt proves path to API boundary). |
| **MF-E2E-3b** | flow-3b Giao hàng Gearment dropship | **done** (2026-07-05, LIVE — no mock) | — (Gearment validator CLOSED) | M | E2 keys LIVE. Runner `scripts/e2e_flow3b_dropship.py` all sections ×2 (`docs/engineering/uats/E2E_FLOW3B_DROPSHIP_2026-07-05.md`): §3 LIVE `POST /orders/draft` → **200** real outbound_ref; §4 LIVE `POST /orders/price` → quote **$12.99** → state `quoted`; LIVE HMAC webhook (**closes P0-18b2**) + Etsy push boundary. Demo §6 live push+quote ×2. Defect-2026-05-10-05 + -02 CLOSED via live probes (full draft/quote schema corrected + Money nanos-as-cents). mhf 19.0.1.0.28. See `specs/004-fulfillment-routing/findings.md` 2026-07-05 closure. |
| **MF-E2E-4** | flow-4 Hậu mãi | **done** (2026-07-05) | — | M | Runner `scripts/e2e_flow4_aftersales.py` **8/8 PASS ×2** on staging (`docs/engineering/uats/E2E_FLOW4_AFTERSALES_2026-07-05.md`): address-change request → BA-Lead approve → `partner_shipping_id` applied (C-SO-001 unlock path) + reject path w/ required reason; reprint = second MO created+completed + second `sale.order.fulfillment` tracking row + push-cron attempt; `etsy.order.ticket` RT draft→approve→refunded with non-BA-Lead approve blocked (FR-017 RPC gate). UI evidence f4_* screenshots. Canonical `new_values` shape = shipping-partner swap (per `test_address_change_workflow.py`); no dedicated reprint action exists — replacement MO via `mrp.production.create` documented in runner. |
| **MF-E2E-0** | Runner §5 config fix | **done** (2026-07-04) | — | S | Drop-ship runner **12/12 PASS** on staging `esty_odoo19` (`docs/engineering/uats/E2E_DEMO_DROP_SHIP_ORDERTEST2_2026-07-04.md`). Turned out to be provisioning, not just ICP: GDrive SA json + env var + google libs on staging container, ICP via ORM (raw SQL bypasses ormcache), 5 demo users seeded, nginx webhook header demo_esty→esty_odoo19, runner networkidle→selector waits. |

### JIRA ticket alignment — `.docs/tasks/` (added 2026-07-04)

Local ticket workspaces live under `.docs/tasks/<ESTY-ID>/` (legacy pre-2026-05-21 excluded). Alignment against the MF-E2E gates:

| Ticket | Title (short) | State | Flow / gate | Gate coverage note |
|---|---|---|---|---|
| ESTY-205 | Per-user Etsy shop scoping (record rules) | pushed | flow-2 | Scoping rules exercised implicitly by MF-E2E-2 role logins; ORM tests `test_shop_user_scoping` |
| ESTY-206 | Full receipt→sale.order field coverage | pushed | flow-2 | Live re-sync of receipt 3818231452 in MF-E2E-2 §A validates mapping on real data; ORM tests `test_etsy_order_coverage` |
| ESTY-207 | Manual "Pull Etsy Orders" button | pushed | flow-2 | ORM tests `test_manual_pull_button`; cron path verified by MF-E2E-2 §A/§B |
| ESTY-208 | Etsy coupon as per-line discount % | pushed | flow-2 | Covered by ESTY-206 mapping tests; anchor S03339 amount reconciles |
| ESTY-209 | Line product image on pulled orders | pushed | flow-2 | `widget="image_url"` path; adapter enrichment tests (memory: adapter-enrichment call-count trap) |
| ESTY-210 | Ingest currency conversion (shop→company) | pushed | flow-2 | Verified live: anchor S03339 re-priced 734,914 VND → 16.21 USD after pricelist rework (MF-E2E-2 anchor re-audit) |
| ESTY-244 | Split Design into standalone module + design.order | landed (In Review) | flow-3a | Landed on `feature/006` (commit `abdb49a56d0`); `design` module v19.0.1.1.0, 19/19 tests. Deployed + verified on staging `esty_odoo19`. flow-3a §3 extended to approve the design.order + assert the MO badge. |
| ESTY-249 | MO 'Design Ready' badge (informational) | landed (In Review) | flow-3a | Same commit `abdb49a56d0`. Computed `mrp.production.design_ready`/`design_order_id` + ribbon/banner/smart-button; not a core state (ADR-019 amendment). Browser-verified on real staging MO `WH/MO/00002`. |
| ESTY-246 | PO-level Gearment quote (dropship) | IN PROCESS | flow-3b | Folded into MF-E2E-3b scope: gate must exercise the PO "Request Gearment Quote" path once the ticket lands (SO-level quote wizard covered meanwhile). |

### New items from audit (AUD-01…AUD-05)

Docs promised these; code never had them. Corrected docs now say "not implemented"; items below decide their fate. Origin for all: 2026-07-04 drift audit.

| ID | Title | State | Priority | Size | Notes (code anchors verified) |
|---|---|---|---|---|---|
| **AUD-01** | Email-fallback auto-switch state machine (ADR-008a) | **todo** | **P2** | M | `etsy.shop.health_check_consecutive_failures` / `recovery_probe_consecutive_successes` fields (etsy_shop.py L255/L261) and `etsy.shop.source.change.log` reasons `auto-failover`/`recovery-probe` already exist — only the transition logic is missing; today the switch is a manual admin toggle (C-ESY-002). Flow-2 resilience. |
| **AUD-02** | Route C hold-queue operator screen | **todo** | **P2** | M | `mhc.sku.family.default_route='tbd'` exists (sku_family.py); no screen/kanban for reclassifying held orders — TO-BE diagram C01/C02 currently manual on the order. Flow-3 routing. |
| **AUD-03** | Refund push to Etsy API | **todo** | P3 | M | `etsy.order.ticket` workflow shipped (draft→approve→refunded, BA-Lead gated); refund itself executed manually in Etsy Shop Manager. This item = API push on approve. Flow-4 future. |
| **AUD-04** | Sync-health alerting escalation | **todo** | P3 | M | `multichannel.sync.health`/`etsy.sync.health` record checkpoints only — no consecutive-failure threshold, no mail.activity alert (SRS-OPS-04 fiction removed). Include token-refresh-failure activity (SRS-ETSY-02 leftover). |
| **AUD-05** | Real material BoMs (replace 1:1 pass-through) | **todo** | P4 | L | `product_mto_bom_wizard.py:76-84` creates phantom 1:1 BOM; real định mức nguyên liệu needs owner-supplied data. `owner-action`. Prereq for P5-01 raw-material forecasts. |

---

## Consolidated Backlog (60 items as consolidated 2026-07-03 — states re-verified 2026-07-04, see Alignment Update)

### Legend

- **ID**: Original slice/task ID from tracker or spec
- **Title**: Feature/task description
- **Origin**: Spec ID + P/US reference
- **State**: `todo` (not started), `doing` (in progress), `blocked` (waiting on external), `shipped*` (code-verified 2026-07-04; flips to `done` when its MF-E2E gate item passes), `superseded` (absorbed by another item)
- **Blocker**: External dependency or prerequisite
- **Size**: S (≤1 day), M (2–5 days), L (1–2 weeks)
- **Priority**: P1 (production cutover), P2 (hardening), P3 (polish/reporting), P4 (deferred)

---

## P0: Phase 0 Foundation & Infrastructure (4 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P0-02** | Owner obtains Gearment sandbox API credentials | Spec 004b + E2 | **done** (2026-07-04 — keys in .env verified LIVE, 200 on catalog; develop account per owner) | E2 dep (partial) | S | Dashboard creds obtained 2026-04-27; API sandbox keys (GEARMENT_API_KEY, GEARMENT_API_SECRET, GEARMENT_WEBHOOK_HMAC_SECRET) still pending. Owner action: request from Gearment dashboard. Unblocks P1-11 round-trip verify + P0-18b2 webhook discovery. `owner-action` |
| **P0-04** | Provision staging environment `129.150.63.207` | Spec 004a Phase 0 | **doing** | None | M | Demo deploy live 2026-05-01 on staging server (Oracle Cloud aarch64). Remaining ops TODO: nightly prod-restore cron + `web.base.url` ICP set to `https://odoo.hatafax.com`. Infrastructure task (Ops + Dev). |
| **P0-20** | Module decomposition kickoff (ADR-003) | Spec 005 ADR-003 | **doing** | P0-11 | M | Skeleton landed 2026-04-27 (multichannel_hub_core empty module installed). P1-05 + P1-06 populate core with fulfillment + carrier models. Documentation task (P0-20-DOCS) deferred, tracked separately below. |
| **P-BUG-ESTY-188** | Fix createListing 400 on Etsy API POST | Spec 011 + 005 | **doing** | E1 ✓ | S | Root cause: missing `readiness_state_id` on shop (never bootstrapped after field added in 19.0.2.15.0). Surgical mitigation landed 2026-06-05 (commit `297fc717b04`); migration bootstraps state IDs on next Etsy OAuth refresh. Defensive + monitoring. |

---

## P1: Production Cutover Critical Path (19 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P-HUB-SPEC** | Central product hub architecture spec | Spec 009 | **done** (2026-07-04 — specs implemented; publish stack E2E-proven by MF-E2E-1) | None | M | Specs 009/010/011 authored and implemented (spec 009 status banner is stale). |
| **P1-11** | Pilot-shop cutover (JaHandmadeArt OAuth→API) | Spec 005 P0-15 | **todo** | E2 keys | S | Ready to execute; awaiting Gearment API sandbox keys (E2 dependency) + owner sign-off |
| **P1-13** | Additional 2–4 shops cutover | Spec 005 P0-16 | **todo** | P1-11 | M | Depends on P1-11 pilot success |
| **P2-07** | Gmail cron rebind (email→API cutover) | Spec 004a + 005 | **todo** | P1-11 | S | Phase 1 + 2 inter-phase exit criterion; rebind cron from 10-min email to API call; fallback email only |
| **P2-08** | Remaining 15 shops cutover to `api_only` | Spec 005 | **todo** | P2-07 | M | Operational after P1-11 + P2-07; batch cutover of shops 2–19 |
| **P-HUB-PROD-MODEL** | Product hub models (channels + status + template extensions) | Spec 009 P1-01 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `multichannel_hub_core/models/multichannel_sales_channel.py`, `product_channel_status.py`, `product_template.py` (x_channel_applicability_ids) |
| **P-HUB-WIZARD** | SKU derivation wizard + UI | Spec 009 P1-02 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `wizards/product_sku_builder_wizard.py` + views; UAT 2026-05-26 (`docs/engineering/uats/`) |
| **P-HUB-SKU-DRIFT** | Drift detection model + job | Spec 009 P1-03 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `wizards/product_sku_canonicalise_wizard.py` (SKU drift canonicalisation) + `x_sku_v2_status` dirty-flag machinery. No separate scheduled drift job — verify need in MF-E2E-1. |
| **P-PUB-CLIENT** | EtsyApiClient write methods (post/put/patch/post_multipart) | Spec 011 P2-01 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `etsy_integration/services/etsy_api_client.py` (`post` L344, `put` L353, `patch` L362, `post_multipart` L371; 401-refresh + retry). Landed in etsy_integration, NOT the planned `multichannel_hub_catalog` module. |
| **P-PUB-DRAFT** | Draft listing wizard (Etsy v3 flow) | Spec 011 P2-02 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `etsy_integration/wizards/etsy_publish_wizard.py` (`action_run_publish_draft_only`) + `services/etsy_listing_publisher.py` (`create_draft`) |
| **P-PUB-IMAGES** | Image upload + variant image assignment | Spec 011 P2-03 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `etsy_listing_publisher.upload_images` + variant-image assignment (Spec 011 P-PUB-VARIANT-PROPERTIES) |
| **P-PUB-INVENTORY** | Inventory writeback to Etsy | Spec 011 P2-04 | **done** (2026-07-04, MF-E2E-1) | — | M | Code: `etsy_listing_publisher.push_inventory` + `services/etsy_inventory_pusher.py`; wizard `action_run_inventory_only` |
| **P-PUB-PUBLISH** | Publish state transition (draft→active) | Spec 011 P2-05 | **done** (2026-07-04, MF-E2E-1) | — | S | Code: `etsy_listing_publisher.publish` + wizard `action_run_publish` |
| **P-PUB-E2E** | E2E runner for publish pipeline (Spec 011 US5) | Spec 011 P2-06 | **superseded** | — | L | Absorbed into **MF-E2E-1** (Main-Flow E2E Gate, below) |
| **P-HUB-XLS-PARSE** | Excel catalog parser (XLS→JSON) | Spec 010 P0-01 | **shipped\*** (not exercised by MF-E2E-1 run 2026-07-04 — needs own verification) | — | M | Code: `multichannel_hub_core/models/product_catalog_import_run.py` + `product_catalog_import_line.py` + `product_catalog_sheet_fingerprint.py` |
| **P-HUB-XLS-INGEST** | Excel catalog ingest (JSON→models) | Spec 010 P0-02 | **shipped\*** (not exercised by MF-E2E-1 run 2026-07-04 — needs own verification) | — | M | Code: `wizards/catalog_import_run_wizard.py` + import-run models |
| **P-HUB-XLS-CRON** | Scheduled catalog sync (daily) | Spec 010 P0-03 | **shipped\*** (not exercised by MF-E2E-1 run 2026-07-04 — needs own verification) | — | S | Code: `data/product_catalog_cron.xml` (`ir_cron_catalog_sync`, no-op until `multichannel_hub.catalog_cron_source_path` ICP set) |
| **P-HUB-IMAGES** | Image download from Etsy (catalog sync) | Spec 010 P0-04 | **shipped\*** (not exercised by MF-E2E-1 run 2026-07-04 — needs own verification) | — | M | Code: `multichannel_hub_core/models/multichannel_product_image.py` + `ir_cron_download_pending_etsy_images` (etsy_integration) |

---

## P2: Operational Hardening (23 items)

### Phase 1 Polish & Exit Criteria (10 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P1-07** | Vietnamese i18n completion | Spec 003 P3-03 | **done** (2026-07-05, commit `7dd5ed37c2a`) | — | **L** | `i18n/vi.po` authored for all 4 custom modules (design 85 / mhf 326 / etsy 716 / mhc 994 entries; polib-validated, identity-scan QA). vi_VN loaded on local + staging; staging internal users switched. Verified live: full Vietnamese hub UI + KPI band (see mockup-v3 session, `feature/mockup-v3-uiux` merged to main `c112194d2e5`). |
| **P1-01b** | Order-line dashboard refactor (model swap) | Spec 003 P1-01 | **shipped\*** (not exercised by MF-E2E-1 run 2026-07-04 — needs own verification) | — | M | Code: `views/operations_dashboard_views.xml` — model swapped to `sale.order.line` 2026-05-10; bulk Mark-Shipped server action live |
| **P1-02c** | Spec 003 US5 GDrive upload wizard | Spec 003 US5 | **done** (2026-07-04, TC-MTO-002 upload wizard URL-mode green ×2) | — | M | Code: `multichannel_hub_core/models/design_file_upload_wizard.py` (url/small/gdrive storage modes) + `cron_design_file_gdrive_sync` promotion cron |
| **P1-02d** | A4 batch print layout | Spec 003 P1-02 | **todo** | None | S | Design file batch print template; owner red-flag item |
| **P1-DESIGN-AUTO-ARCHIVE** | Auto-archive design files after publish | Spec 003 P1-02 | **doing** | P-PUB-PUBLISH | M | State transition: archive after Etsy publish confirmation |
| **P-DOCS-FLOW-VN** | Vietnamese operator flow docs | Spec 003 + 006 | **done** (2026-07-05, commit `94c7e21aec0`) | — | L | Shipped as `docs/owner/HUONG_DAN_*_VN.md` v2.0 (4 guides, new Vận-hành menu paths, 21 fresh themed screenshots) + `business-flows/v3/` (11 pages, real staging captures) + consolidated PDF `docs_huong_dan_uat_vn.pdf`; synced to Confluence + docs.hatafa.erptek.net/v3/. |
| **P3-LEAD-MAIL-ALIAS** | Forward email alias → Odoo lead routing | Spec 007 | **todo** | None | S | Off critical path; maps external email to lead creation |
| **P-GEAR-PRINT-SIDES** | Design print-location (front/back) modeling + push guards | Gearment E2E audit 2026-07-05 | **todo** | None | M | Payload builder hardcodes 1st file=FRONT, 2nd=BACK by position; `design.file` has no side field, no UI. Add `print_location` selection + show on design tab/order form; builder reads it. Plus: block push when an eligible Gearment line has zero approved design files (today it silently drops); pre-push URL reachability check (GDrive links must be public). Files: `gearment_payload_builder.py`, `design_file.py` + views. |
| **P-GEAR-AUTOCONFIRM** | Gearment draft → confirmed order (chargeable) | Gearment E2E audit 2026-07-05 | **todo** | **owner decision** | M | Odoo only creates DRAFT orders on Gearment; `adapter.confirm()` (/orders/draft/labeled) exists but is never called — production starts only after manual confirm in the Gearment dashboard. Needs owner sign-off (spends real money) + decide trigger (auto on PO confirm vs explicit button vs cron with cap). |
| **P3-LEAD-API-ROUTING** | Etsy messages → lead routing | Spec 007 | **todo** | P1-MSG-API-PULL | M | Off critical path; dependent on conversations_r re-submission |
| **T067** | Reconciliation report (Spec 002 exit gate) | Spec 002 Phase 13 | **todo** | None | M | BA reconciliation CSV: Odoo `SUM(amount_total)` vs source Excel; required before staging deploy |
| **T070** | Module install test (clean DB) | Spec 002 Phase 13 | **todo** | T067 | S | Verify all modules install cleanly on fresh Odoo instance |
| **T073** | Staging E2E + BA sign-off (Spec 002) | Spec 002 Phase 13 | **todo** | T067 | M | Full end-to-end on staging; BA reconciliation approval gate. **2026-07-04: umbrella exit criterion of the Main-Flow E2E Gate — closes when MF-E2E-0..4 all pass.** |

### Spec 004a: Tracking Import (Phase 2, 6 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P2-01-MODELS** | Tracking import models + views | Spec 004a | **done** (2026-07-04, MF-E2E-3a/0) | — | M | Code: `multichannel_hub_fulfillment/models/tracking_import_log.py`, `tracking_import_line.py` |
| **P2-01-WIZARD** | Tracking import wizard (GKE Excel upload) | Spec 004a | **done** (2026-07-04, MF-E2E-3a/0) | — | M | Code: `multichannel_hub_fulfillment/wizards/tracking_import_wizard.py` (incl. `action_approve_schema` FR-017 gate); plus GDrive inbox poller `logistics_partner._cron_poll_inbox` (P2-06) |
| **P2-01-CARRIER** | Shipping carrier model + master data | Spec 004a | **done** (2026-07-04, MF-E2E-3a/0) | — | S | Code: `models/shipping_carrier.py` + `data/shipping_carrier_data.xml` (USPS/UniUni/YunExpress seeded) |
| **P2-02-CARRIER-DETECT** | Carrier auto-detection (regex matching) | Spec 004a | **done** (2026-07-04, MF-E2E-3a/0) | — | M | Code: `shipping_carrier.tracking_prefix_regex` + safety constraint `_check_tracking_prefix_regex_safe` |
| **P2-03-GKE-SCHEMA** | GKE schema fingerprint validation | Spec 004a | **done** (2026-07-04, MF-E2E-3a/0) | — | S | Code: schema-hash whitelist ICP `multichannel_hub_fulfillment.gke_schema_hashes` in `tracking_import_wizard.py` |
| **P2-04-SYNC-HEALTH** | Tracking sync health reporting | Spec 004a | **done** (2026-07-04, MF-E2E-3a/0) | — | S | Code: `logistics_partner.py` records per-partner errors + gdrive_integration events to sync health |

### Spec 004b: Gearment Adapter Completion (4 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P0-18b2** | Webhook signature discovery + live POST tests | Spec 004b P0-18b2 | **done** (2026-07-04 — HMAC verified live ×2: flow-3b runner §5 + TC-DROP-005) | — | M | ngrok tunnel; inspect inbound webhook HMAC header name + algorithm; test draft/confirm flow |
| **P4-02** | Returns/refunds workflow | Spec 004c | **todo** | P4-01-D | L | Return reason selection → refund/replace action; credit note generation; replacement order creation |
| **P4-03** | Pricing audit dashboard | Spec 004 Phase 4 | **todo** | None | M | Pivot/graph: cost comparison (Etsy list vs Odoo sale vs Gearment quote) per product/channel |
| **ENV-FIX-MRP** | Owner MRP config (env task) | Spec 003 | **done** (2026-07-04 — GO-probe verified Manufacture+MTO routes live; MF-E2E-3a auto-MO proven) | None | S | Owner-side: configure MRP routes for internal production; not code |

### Spec 002 Data Issues (2 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **T055** | Discount analytics (Spec 002 US7) | Spec 002 | **todo** | None | S | Pivot/graph views for discount code usage; deferred to W4+ (nice-to-have) |
| **T058** | Image download cron registration (Spec 002 US8) | Spec 002 | **shipped\*** | — | S | Code: `ir_cron_download_pending_etsy_images` (`etsy_integration/data/ir_cron_data.xml`, 30-min interval) |

---

## P3: Polish & Reporting (18 items)

### Spec 003 Dashboard Polish (8 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **T024** | 14-column Order Dashboard | Spec 003 Phase 3 | **todo** | P1-DESIGN-AUTO-ARCHIVE | S | Add design_status + address-change columns. Audit 2026-07-04 addition: pivot view + kanban-by-tracking_state also never shipped (SRS-OPS-01/02 fiction) — fold into this polish scope if owner still wants them. |
| **T030** | Perf test (17K rows <3s) | Spec 003 Phase 3 | **todo** | None | M | Load test Order Dashboard with 17K rows; verify <3s load time |
| **T036** | Excel export (tracking) | Spec 003 Phase 4 | **todo** | — | M | Audit 2026-07-04: dedicated export wizards (SRS-OPS-09/10) never shipped; standard Odoo list export from the unified Operations Dashboard is the interim. This item = the dedicated wizard (GKE format + GDrive save). |
| **T038** | Bus.bus web-client subscription (Spec 003) | Spec 003 Phase 4 | **todo** | None | M | Audit 2026-07-04: **no bus.bus code exists anywhere** (`_send_tracking_update_to_bus` was doc fiction); dashboard currently refreshes on cron cadence (5–15 min). This item = build broadcast + subscription from scratch, if still wanted. |
| **T040–T044** | Warehouse zone mapping + stock move on transition | Spec 003 Phase 5 | **todo** | P-HUB-PROD-MODEL | M | Process Dashboard: map pipelines to warehouse zones; generate stock.move on "Đã sản xuất" transition (idempotent) |
| **T052–T059** | Design-file URL validation + recovery | Spec 003 Phase 6 | **todo** | None | M | Unreachable-URL warning chip; background job to re-validate design file URLs weekly |

### Spec 005 Minor Items (2 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P1-MSG-SCOPE** | Re-submit `conversations_r` scope to Etsy | Spec 005 P0-15 | **blocked** | None | S | Owner action: Etsy declined optional scope in initial approval; re-submit for buyer-message API |
| **P1-MSG-API-PULL** | Etsy message polling (conversations_r) | Spec 005 P0-15 | **blocked** | P1-MSG-SCOPE | M | Blocked on `conversations_r` scope approval; pulls inbound Etsy messages for CRM integration |

### Spec 007–008 (CRM + Listings, Deferred)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **T060–T064** | Shop-level record rules (Spec 002 US9) | Spec 002 Phase 11 | **todo** | None | M | Multi-user shop isolation via res.users.etsy_shop_ids + ACL; deferred to W4+ |
| **T065–T066** | Design queue status tracking (Spec 002 US10) | Spec 002 Phase 12 | **shipped\*** | — | S | Code: `multichannel_hub_core/models/sale_order_line.py` — `design_status` rollup (T023) live on the line dashboard |

### Phase 5: Inventory & Future Channels (4 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P5-01** | Raw-material inventory + forecasts | Spec 005 Phase 5 | **todo** | P4-02 | L | Native stock + forecasts + Excel wizard; VN production planning |
| **P5-02** | Catalog dashboard per product | Spec 005 Phase 5 | **todo** | P-HUB-PROD-MODEL | M | Product-centric view: inventory, pricing, channel status, sales trends |
| **P5-03** | Barcode scan sheet (evaluate `stock_barcode` CE) | Spec 005 Phase 5 | **todo** | P5-01 | M | Production line scanning; standard module check first |
| **P5-04 & P5-05** | Amazon + Website channels | Spec 005 Phase 5 | **todo** | P-PUB-E2E | L | Strategic hold until Etsy live; shared adapter patterns with Etsy channel |

### Documentation & SDS (2 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P0-20-DOCS** | Module decomposition documentation (Spec 005 ADR-003) | Spec 006 ADR-003 | **todo** | None | M | Document 4-module architecture: etsy_integration, multichannel_hub_core/fulfillment/listing |
| **SRS/SDS-REBUILD** | Consolidated SRS + SDS (security + arch diagrams) | Spec 015 | **todo** | None | L | Address critique.md: auth credential redaction, system architecture diagram, ER diagram, sequence diagrams, DEPLOYMENT_ARCHITECTURE.md |

---

## External Dependencies

| ID | Dependency | Status | Blocker For | Next Action |
|---|---|---|---|---|
| **E1** | Etsy OAuth scopes (4 required approved; `conversations_r` rejected) | ✅ APPROVED (4/5) | P1-MSG-SCOPE | Re-submit `conversations_r` (owner action) |
| **E2** | Gearment API sandbox keys (GEARMENT_API_KEY, GEARMENT_API_SECRET, GEARMENT_WEBHOOK_HMAC_SECRET) | 🟨 PARTIAL (dashboard creds only) | P1-11 round-trip verify, P0-18b2 | Owner request from Gearment dashboard |
| **E3** | Google Drive service account JSON | ✅ DONE | None | Ready to use (in secrets/) |
| **E2E-DROP-SHIP-RUNNER** | Demo runner script validation | ✅ DONE (11/12 sections PASS) | Production readiness gate | Config gap only (GDrive folder ICP); no code defect |

---

## Consolidated Backlog Statistics

### By State (re-verified 2026-07-04)

| State | Count | Notes |
|---|---|---|
| `shipped*` | 23 | Code-verified shipped; await MF-E2E gate pass to flip `done` (13 in P1 publish/hub/XLS, 9 in P2 tracking/design, T065–T066) |
| `superseded` | 1 | P-PUB-E2E → MF-E2E-1 |
| `todo` | 27 | Genuinely not started |
| `doing` | 6 | P0-02, P0-04, P0-20, P-BUG-ESTY-188, P-DOCS-FLOW-VN, ENV-FIX-MRP |
| `blocked` | 3 | P0-18b2 + MF-E2E-3b (E2 keys); P1-MSG-API-PULL (E1 scope) |
| **New (MF-E2E + AUD)** | **11** | 6 gate items + 5 audit items |
| **Active backlog (todo+doing+blocked+new)** | **47** | |

*Note: 8 "doing" items are actively in progress or partially complete (P0-02 owner-side partial; P0-04 ops-side partial; P0-20 skeleton done; P-BUG-ESTY-188 fix landed; P-HUB-SPEC planner authoring; P1-01b refactor blocked; P-DOCS-FLOW-VN documentation parallel; ENV-FIX-MRP owner-side). 3 "blocked" items await E2 (Gearment keys) or E1 re-submission (conversations_r). State convention: `todo (blocked-by: X)` used for logical blockers within-plan; `blocked` state used for external dependency blockers only.*

### By Priority

| Priority | Active Count | Est. Duration | Critical Path? |
|---|---|---|---|
| **P1** (Production Cutover = Main-Flow E2E Gate) | 11 (MF-E2E-0..4 + P1-11, P1-13, P2-07, P2-08, T067, T073) | **3–5 weeks** (publish/hub/tracking code already shipped) | YES — gates production release |
| **P2** (Hardening) | 14 (incl. AUD-01, AUD-02) | 4–6 weeks | Parallel |
| **P3** (Polish/Reporting) | 18 (incl. AUD-03, AUD-04) | 4–6 weeks | NO — post-E2E |
| **P4** (Deferred) | 4 (incl. AUD-05) | — | NO |

> Duration collapsed from 8–10 weeks to 3–5: the audit showed Phase 3 publish + hub + catalog-sync + tracking-import code is already on `main`; remaining P1 work is E2E verification, cutovers, and reconciliation — not implementation.

### By Phase

| Phase | Item Count | Completion % | Est. to 100% |
|---|---|---|---|
| P0 | 3 | 89% | 1 week (E2 keys) |
| P1 | 10 | 78% | 2–3 weeks (P1-11 + P2-07 gate) |
| P2 | 6 | 95% (tracking-import stack shipped\*) | E2E verify only |
| **P3** | 72 | **~85% code-complete** (was misreported 1% — implementation slices shipped between 2026-05 and 2026-07; E2E verification outstanding) | 2–3 weeks (MF-E2E-1) |
| P4 | 2 | 75% | 2 weeks (returns + pricing) |
| P5 | 4 | 0% | 4–6 weeks (parallel, low priority) |

---

## Model/Field Evidence (Shipped vs. Remaining)

### Shipped Models

- `sale.order` (extended with 20+ Etsy fields), `sale.order.line` (etsy_transaction_id + options)
- `etsy.shop`, `etsy.email.log`, `etsy.sync.health`, `etsy.address.change.request`
- `product.product` (etsy_image_url), `res.partner` (is_etsy_customer)
- `design.file`, `order.design.file`, `order.pipeline`, `order.pipeline.state`, `order.pipeline.transition.log`
- `shipping.carrier`, `sale.order.fulfillment` (delegation sibling)
- `multichannel.sync.health` (observability)

### Remaining Models (Phase 3+)

- `multichannel.sales.channel` (new; Spec 009)
- `product.channel.status` (new; Spec 009)
- `multichannel.listing`, `multichannel.listing.variant` (Spec 008/011)
- `gearment.api.log` (Spec 004b; mostly done, webhook discovery TBD)

---

## State Classification Convention

**Problem**: Tracker treats some items as `todo` with internal logical blockers (e.g., P1-02c depends on P1-09, both internal). Spec-015 initially marked these as `blocked`. This creates a two-convention system.

**Resolution** (applied in this spec):

- **`todo (blocked-by: <ID>)`**: Item is not started but has a known internal prerequisite within the plan. The blocker is another development task (same developer team controls both). Example: P1-02c `todo (blocked-by: P1-09 ✓)` — internal design workflow dependency.
- **`blocked`**: Item is blocked by an external dependency outside the development team's control OR cannot proceed without critical external input. Blockers are external (E1 Etsy scopes, E2 Gearment keys) or organizational (owner decision, ops provisioning milestone). Examples: P0-18b2 (awaits E2 keys); P1-MSG-API-PULL (awaits E1 scope re-approval).
- **`doing`**: Item is in progress, partially complete, or actively being worked on. Includes defensive monitoring (P-BUG-ESTY-188), owner-side actions (P0-02), skeleton+doc-split (P0-20), planner-authoring (P-HUB-SPEC), ops infrastructure (P0-04).

**Rationale**: Internal blockers don't justify a separate state (they're tracked in notes/dependencies). External blockers warrant explicit visibility because the team cannot unblock them alone.

---

## Traceability Appendix: Master Plan 006 Tracker → Spec 015

Every non-done tracker item from `.claude/plans/006-master-plan-tracking.md` appears in this spec. The table below maps tracker IDs to spec backlog items.

> **2026-07-04**: tracker states were stale for 23 items (marked `shipped*` above with code anchors); the tracker remains the historical record — this spec's Alignment Update is now the authoritative state. New IDs MF-E2E-0..4 and AUD-01..05 originate here (no tracker rows).

### Included Items (60 total)

| Tracker ID | State | Spec Item(s) | Notes |
|---|---|---|---|
| P0-02 | doing | P0-02 | Owner: obtain Gearment API sandbox keys |
| P0-04 | doing | P0-04 | Ops: staging server provisioning (demo deploy live) |
| P0-18b2 | blocked | P0-18b2 | Dev: webhook signature discovery (blocked E2) |
| P0-20 | doing | P0-20 | Dev: module decomposition skeleton (docs separate in P0-20-DOCS) |
| P-BUG-ESTY-188 | doing | P-BUG-ESTY-188 | Dev: createListing 400 fix (mitigation landed) |
| P1-01b | doing | P1-01b | Dev: order-line dashboard refactor |
| P1-02c | todo | P1-02c | Dev: GDrive upload wizard (depends P1-09 ✓) |
| P1-02d | todo | P1-02d | Dev: A4 batch print layout |
| P1-07 | done | P1-07 | Dev: Vietnamese i18n completion (2026-07-05) |
| P1-11 | todo | P1-11 | Dev+Owner: pilot shop cutover (depends E2) |
| P1-13 | todo | P1-13 | Dev+Owner: 2–4 additional shops cutover |
| P1-MSG-SCOPE | blocked | P1-MSG-SCOPE | Owner: re-submit conversations_r scope to Etsy |
| P1-MSG-API-PULL | blocked | P1-MSG-API-PULL | Dev: message polling (depends P1-MSG-SCOPE) |
| P2-01-MODELS | todo | P2-01-MODELS | Dev: tracking import models |
| P2-01-WIZARD | todo | P2-01-WIZARD | Dev: tracking import wizard |
| P2-01-CARRIER | todo | P2-01-CARRIER | Dev: carrier model + seed data |
| P2-02-CARRIER-DETECT | todo | P2-02-CARRIER-DETECT | Dev: carrier auto-detection |
| P2-03-GKE-SCHEMA | todo | P2-03-GKE-SCHEMA | Dev: GKE schema validation |
| P2-04-SYNC-HEALTH | todo | P2-04-SYNC-HEALTH | Dev: tracking sync health reporting |
| P2-07 | todo | P2-07 | Dev: Gmail cron rebind (email→API cutover) |
| P2-08 | todo | P2-08 | Ops: remaining 15 shops cutover |
| P3-LEAD-MAIL-ALIAS | todo | P3-LEAD-MAIL-ALIAS | Dev: email alias → lead routing (off critical path) |
| P3-LEAD-API-ROUTING | todo | P3-LEAD-API-ROUTING | Dev: message poller → leads (off critical path) |
| P4-02 | todo | P4-02 | Dev: returns/refunds workflow |
| P4-03 | todo | P4-03 | Dev: pricing audit dashboard |
| P5-01 | todo | P5-01 | Dev: raw-material inventory (deferred) |
| P5-02 | todo | P5-02 | Dev: product catalog dashboard (deferred) |
| P5-03 | todo | P5-03 | Dev: barcode scanning (deferred) |
| P5-04/P5-05 | todo | P5-04 & P5-05 | Dev: Amazon + website channels (deferred) |
| T024 | todo | T024 | Dev: 14-column Order Dashboard polish |
| T030 | todo | T030 | Dev: dashboard perf test (17K rows) |
| T036 | todo | T036 | Dev: Excel export (tracking) |
| T038 | todo | T038 | Dev: bus.bus web-client subscription |
| T040–T044 | todo | T040–T044 | Dev: warehouse zone mapping + stock move |
| T052–T059 | todo | T052–T059 | Dev: design-file URL validation + recovery |
| T055 | todo | T055 | Dev: discount analytics (nice-to-have) |
| T058 | todo | T058 | Dev: image download cron registration |
| T060–T064 | todo | T060–T064 | Dev: shop-level record rules (deferred) |
| T065–T066 | todo | T065–T066 | Dev: design queue status tracking (deferred) |
| T067 | todo | T067 | Dev: reconciliation report |
| T070 | todo | T070 | Dev: module install test |
| T073 | todo | T073 | Dev+Owner: staging E2E + BA sign-off |
| P-HUB-SPEC | doing | P-HUB-SPEC | Dev: product hub spec (planner authoring) |
| P-HUB-PROD-MODEL | todo | P-HUB-PROD-MODEL | Dev: product hub models |
| P-HUB-WIZARD | todo | P-HUB-WIZARD | Dev: SKU derivation wizard |
| P-HUB-SKU-DRIFT | todo | P-HUB-SKU-DRIFT | Dev: SKU drift detection |
| P-HUB-XLS-PARSE | todo | P-HUB-XLS-PARSE | Dev: Excel parser |
| P-HUB-XLS-INGEST | todo | P-HUB-XLS-INGEST | Dev: Excel ingest wizard |
| P-HUB-XLS-CRON | todo | P-HUB-XLS-CRON | Dev: daily catalog sync cron |
| P-HUB-IMAGES | todo | P-HUB-IMAGES | Dev: image download from Etsy |
| P-PUB-CLIENT | todo | P-PUB-CLIENT | Dev: EtsyApiClient write methods |
| P-PUB-DRAFT | todo | P-PUB-DRAFT | Dev: draft listing wizard |
| P-PUB-IMAGES | todo | P-PUB-IMAGES | Dev: image upload + variant assignment |
| P-PUB-INVENTORY | todo | P-PUB-INVENTORY | Dev: inventory writeback to Etsy |
| P-PUB-PUBLISH | todo | P-PUB-PUBLISH | Dev: publish state transition |
| P-PUB-E2E | todo | P-PUB-E2E | Dev: E2E publish pipeline validation |
| P-DOCS-FLOW-VN | done | P-DOCS-FLOW-VN | Owner+Dev: Vietnamese operator flow docs (2026-07-05) |
| P0-20-DOCS | todo | P0-20-DOCS | Dev: module decomposition documentation |
| SRS/SDS-REBUILD | todo | SRS/SDS-REBUILD | Dev: consolidated SRS + SDS |
| ENV-FIX-MRP | doing | ENV-FIX-MRP | Owner: MRP route configuration (not code) |

### Excluded Items (with reason)

None. All non-done tracker items (state: `todo`, `doing`, `blocked`) are represented in the backlog.

---

## References

- **Master Plan 006 Tracker**: `.claude/plans/006-master-plan-tracking.md` (primary source)
- **Implementation Playbook**: `.claude/plans/006-implementation-playbook.md` (9-phase per-slice loop)
- **Specs Directory**: `specs/001–014/spec.md` (historical record; archives retained)
- **Module Code**: `custom_addons/etsy_integration/`, `custom_addons/design/`, `custom_addons/multichannel_hub_*/`
