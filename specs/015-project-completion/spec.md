# Spec 015: Project Completion — Consolidated Backlog

**Date**: 2026-07-03  
**Status**: Draft for Owner Review  
**Source of Truth**: Master Plan 006 tracking (`.claude/plans/006-master-plan-tracking.md`) + specs 001–014 analysis

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

## Consolidated Backlog: 60 Non-Done Items

### Legend

- **ID**: Original slice/task ID from tracker or spec
- **Title**: Feature/task description
- **Origin**: Spec ID + P/US reference
- **State**: `todo` (not started), `doing` (in progress), `blocked` (waiting on external)
- **Blocker**: External dependency or prerequisite
- **Size**: S (≤1 day), M (2–5 days), L (1–2 weeks)
- **Priority**: P1 (production cutover), P2 (hardening), P3 (polish/reporting), P4 (deferred)

---

## P0: Phase 0 Foundation & Infrastructure (4 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P0-02** | Owner obtains Gearment sandbox API credentials | Spec 004b + E2 | **doing** | E2 dep (partial) | S | Dashboard creds obtained 2026-04-27; API sandbox keys (GEARMENT_API_KEY, GEARMENT_API_SECRET, GEARMENT_WEBHOOK_HMAC_SECRET) still pending. Owner action: request from Gearment dashboard. Unblocks P1-11 round-trip verify + P0-18b2 webhook discovery. `owner-action` |
| **P0-04** | Provision staging environment `129.150.63.207` | Spec 004a Phase 0 | **doing** | None | M | Demo deploy live 2026-05-01 on staging server (Oracle Cloud aarch64). Remaining ops TODO: nightly prod-restore cron + `web.base.url` ICP set to `https://odoo.hatafax.com`. Infrastructure task (Ops + Dev). |
| **P0-20** | Module decomposition kickoff (ADR-003) | Spec 005 ADR-003 | **doing** | P0-11 | M | Skeleton landed 2026-04-27 (multichannel_hub_core empty module installed). P1-05 + P1-06 populate core with fulfillment + carrier models. Documentation task (P0-20-DOCS) deferred, tracked separately below. |
| **P-BUG-ESTY-188** | Fix createListing 400 on Etsy API POST | Spec 011 + 005 | **doing** | E1 ✓ | S | Root cause: missing `readiness_state_id` on shop (never bootstrapped after field added in 19.0.2.15.0). Surgical mitigation landed 2026-06-05 (commit `297fc717b04`); migration bootstraps state IDs on next Etsy OAuth refresh. Defensive + monitoring. |

---

## P1: Production Cutover Critical Path (19 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P-HUB-SPEC** | Central product hub architecture spec | Spec 009 | **doing** | None | M | Planner authoring; unblocks all 15 Phase 3 implementation slices |
| **P1-11** | Pilot-shop cutover (JaHandmadeArt OAuth→API) | Spec 005 P0-15 | **todo** | E2 keys | S | Ready to execute; awaiting Gearment API sandbox keys (E2 dependency) + owner sign-off |
| **P1-13** | Additional 2–4 shops cutover | Spec 005 P0-16 | **todo** | P1-11 | M | Depends on P1-11 pilot success |
| **P2-07** | Gmail cron rebind (email→API cutover) | Spec 004a + 005 | **todo** | P1-11 | S | Phase 1 + 2 inter-phase exit criterion; rebind cron from 10-min email to API call; fallback email only |
| **P2-08** | Remaining 15 shops cutover to `api_only` | Spec 005 | **todo** | P2-07 | M | Operational after P1-11 + P2-07; batch cutover of shops 2–19 |
| **P-HUB-PROD-MODEL** | Product hub models (channels + status + template extensions) | Spec 009 P1-01 | **todo** | P-HUB-SPEC | M | Foundation; unblocks all publish slices. Models: `multichannel.sales.channel`, `product.channel.status`, `product.template` extensions |
| **P-HUB-WIZARD** | SKU derivation wizard + UI | Spec 009 P1-02 | **todo** | P-HUB-PROD-MODEL | M | Operator tool for catalog hygiene; displays SKU precedence logic |
| **P-HUB-SKU-DRIFT** | Drift detection model + job | Spec 009 P1-03 | **todo** | P-HUB-PROD-MODEL | M | Detects SKU collisions; flags for resolution via wizard |
| **P-PUB-CLIENT** | EtsyApiClient write methods (post/put/patch/post_multipart) | Spec 011 P2-01 | **todo** | P-HUB-SPEC | M | Unblocks all 5 publish slices; wraps requests.Session with auth + retry logic |
| **P-PUB-DRAFT** | Draft listing wizard (Etsy v3 flow) | Spec 011 P2-02 | **todo** | P-PUB-CLIENT | M | UI wizard: supply → draft upload → quote quote → result display |
| **P-PUB-IMAGES** | Image upload + variant image assignment | Spec 011 P2-03 | **todo** | P-PUB-CLIENT | M | POST multipart to `/listings/{id}/images` + PUT variant images |
| **P-PUB-INVENTORY** | Inventory writeback to Etsy | Spec 011 P2-04 | **todo** | P-HUB-SKU-DRIFT | M | Pushes stock levels to Etsy for each variant; respects `multichannel.listing.available_qty_override` |
| **P-PUB-PUBLISH** | Publish state transition (draft→active) | Spec 011 P2-05 | **todo** | P-PUB-IMAGES | S | Final state machine transition; updates `multichannel.listing.publication_state` |
| **P-PUB-E2E** | E2E runner for publish pipeline (Spec 011 US5) | Spec 011 P2-06 | **todo** | P-PUB-PUBLISH | L | Runs full inbound (Etsy email)→outbound (Etsy publish) loop; staging + production validation |
| **P-HUB-XLS-PARSE** | Excel catalog parser (XLS→JSON) | Spec 010 P0-01 | **todo** | P-HUB-SPEC | M | Reads shop Excel export; extracts product + variant rows; validates schema |
| **P-HUB-XLS-INGEST** | Excel catalog ingest (JSON→models) | Spec 010 P0-02 | **todo** | P-HUB-XLS-PARSE | M | Creates/updates `multichannel.listing` + variant records; idempotent via etsy_listing_id |
| **P-HUB-XLS-CRON** | Scheduled catalog sync (daily) | Spec 010 P0-03 | **todo** | P-HUB-XLS-INGEST | S | `ir_cron_data.xml` entry; logs sync health to `multichannel.sync.health` |
| **P-HUB-IMAGES** | Image download from Etsy (catalog sync) | Spec 010 P0-04 | **todo** | P-HUB-XLS-INGEST | M | Batch download listing images; store in `ir.attachment`; link to variant records |

---

## P2: Operational Hardening (23 items)

### Phase 1 Polish & Exit Criteria (10 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P1-07** | Vietnamese i18n completion | Spec 003 P3-03 | **todo** | None | M | Phase 1 exit criterion; translate all field labels, menu entries, status values, error messages |
| **P1-01b** | Order-line dashboard refactor (model swap) | Spec 003 P1-01 | **doing** | P4-01-D | M | Swap from `sale.order` to `sale.order.line` granularity; enables bulk actions for P4-01-D |
| **P1-02c** | Spec 003 US5 GDrive upload wizard | Spec 003 US5 | **todo** | P1-09 ✓ | M | GDrive upload wizard for design files; fields: `gdrive_file_id`, `gdrive_preview_url`, `gdrive_folder_id` + upload service via service account. P1-09 (GDrive auth scaffolding) completed; ready to implement. |
| **P1-02d** | A4 batch print layout | Spec 003 P1-02 | **todo** | None | S | Design file batch print template; owner red-flag item |
| **P1-DESIGN-AUTO-ARCHIVE** | Auto-archive design files after publish | Spec 003 P1-02 | **doing** | P-PUB-PUBLISH | M | State transition: archive after Etsy publish confirmation |
| **P-DOCS-FLOW-VN** | Vietnamese operator flow docs | Spec 003 + 006 | **doing** | P-PUB-E2E | L | Can author in parallel; finalize post-E2E. Covers order ingest→fulfillment→shipment tracking workflow. |
| **P3-LEAD-MAIL-ALIAS** | Forward email alias → Odoo lead routing | Spec 007 | **todo** | None | S | Off critical path; maps external email to lead creation |
| **P3-LEAD-API-ROUTING** | Etsy messages → lead routing | Spec 007 | **todo** | P1-MSG-API-PULL | M | Off critical path; dependent on conversations_r re-submission |
| **T067** | Reconciliation report (Spec 002 exit gate) | Spec 002 Phase 13 | **todo** | None | M | BA reconciliation CSV: Odoo `SUM(amount_total)` vs source Excel; required before staging deploy |
| **T070** | Module install test (clean DB) | Spec 002 Phase 13 | **todo** | T067 | S | Verify all modules install cleanly on fresh Odoo instance |
| **T073** | Staging E2E + BA sign-off (Spec 002) | Spec 002 Phase 13 | **todo** | T067 | M | Full end-to-end on staging; BA reconciliation approval gate |

### Spec 004a: Tracking Import (Phase 2, 6 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P2-01-MODELS** | Tracking import models + views | Spec 004a | **todo** | None | M | `tracking.import.log`, `tracking.import.line`, `sale.order.fulfillment` extensions; carrier auto-detect regex |
| **P2-01-WIZARD** | Tracking import wizard (GKE Excel upload) | Spec 004a | **todo** | P2-01-MODELS | M | UI wizard: upload Excel → parse → preview → confirm; carrier detection logic |
| **P2-01-CARRIER** | Shipping carrier model + master data | Spec 004a | **todo** | None | S | `shipping.carrier` model (already in multichannel_hub_core); populate USPS/UniUni/YunExpress master data |
| **P2-02-CARRIER-DETECT** | Carrier auto-detection (regex matching) | Spec 004a | **todo** | P2-01-WIZARD | M | Parse tracking number + prefix; match to carrier via `shipping.carrier.tracking_pattern_regex` |
| **P2-03-GKE-SCHEMA** | GKE schema fingerprint validation | Spec 004a | **todo** | P2-01-WIZARD | S | Pre-flight check: Excel columns match known GKE schema; warn on mismatch |
| **P2-04-SYNC-HEALTH** | Tracking sync health reporting | Spec 004a | **todo** | P2-01-CARRIER | S | Log import statistics to `multichannel.sync.health`; report match/unmatch counts |

### Spec 004b: Gearment Adapter Completion (4 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **P0-18b2** | Webhook signature discovery + live POST tests | Spec 004b P0-18b2 | **blocked** | E2 keys | M | ngrok tunnel; inspect inbound webhook HMAC header name + algorithm; test draft/confirm flow |
| **P4-02** | Returns/refunds workflow | Spec 004c | **todo** | P4-01-D | L | Return reason selection → refund/replace action; credit note generation; replacement order creation |
| **P4-03** | Pricing audit dashboard | Spec 004 Phase 4 | **todo** | None | M | Pivot/graph: cost comparison (Etsy list vs Odoo sale vs Gearment quote) per product/channel |
| **ENV-FIX-MRP** | Owner MRP config (env task) | Spec 003 | **doing** | None | S | Owner-side: configure MRP routes for internal production; not code |

### Spec 002 Data Issues (2 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **T055** | Discount analytics (Spec 002 US7) | Spec 002 | **todo** | None | S | Pivot/graph views for discount code usage; deferred to W4+ (nice-to-have) |
| **T058** | Image download cron registration (Spec 002 US8) | Spec 002 | **todo** | None | S | Register `ir_cron_data.xml` entry for batch image downloads (service exists); deferred to W4+ |

---

## P3: Polish & Reporting (18 items)

### Spec 003 Dashboard Polish (8 items)

| ID | Title | Origin | State | Blocker | Size | Notes |
|---|---|---|---|---|---|---|
| **T024** | 14-column Order Dashboard | Spec 003 Phase 3 | **todo** | P1-DESIGN-AUTO-ARCHIVE | S | Add design_status + address-change columns; deferred pending prerequisites |
| **T030** | Perf test (17K rows <3s) | Spec 003 Phase 3 | **todo** | None | M | Load test Order Dashboard with 17K rows; verify <3s load time |
| **T036** | Excel export (tracking) | Spec 003 Phase 4 | **todo** | P2-01-WIZARD | M | Tracking Dashboard → Excel with GKE import format; used by ops for manual adjustments |
| **T038** | Bus.bus web-client subscription (Spec 003) | Spec 003 Phase 4 | **todo** | None | M | Real-time dashboard updates via WebSocket; deferred to web-client phase |
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
| **T065–T066** | Design queue status tracking (Spec 002 US10) | Spec 002 Phase 12 | **todo** | None | S | Add etsy_design_status selection field to sale.order.line; deferred |

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

### By State

| State | Count | % |
|---|---|---|
| `todo` | 49 | 81.7% |
| `doing` | 8 | 13.3% |
| `blocked` | 3 | 5.0% |
| **Total Non-Done** | **60** | **100%** |

*Note: 8 "doing" items are actively in progress or partially complete (P0-02 owner-side partial; P0-04 ops-side partial; P0-20 skeleton done; P-BUG-ESTY-188 fix landed; P-HUB-SPEC planner authoring; P1-01b refactor blocked; P-DOCS-FLOW-VN documentation parallel; ENV-FIX-MRP owner-side). 3 "blocked" items await E2 (Gearment keys) or E1 re-submission (conversations_r). State convention: `todo (blocked-by: X)` used for logical blockers within-plan; `blocked` state used for external dependency blockers only.*

### By Priority

| Priority | Count | Est. Duration | Critical Path? |
|---|---|---|---|
| **P1** (Production Cutover) | 18 | 8–10 weeks | YES — gates production release |
| **P2** (Hardening) | 22 | 6–8 weeks | YES (parallel) — gates full E2E |
| **P3** (Polish/Reporting) | 18 | 4–6 weeks | NO — post-E2E nice-to-haves |

### By Phase

| Phase | Item Count | Completion % | Est. to 100% |
|---|---|---|---|
| P0 | 3 | 89% | 1 week (E2 keys) |
| P1 | 10 | 78% | 3 weeks (P1-11 + P2-07 gate) |
| P2 | 6 | 75% | 2 weeks (shop cutover) |
| **P3 (NEW)** | 72 | 1% | 8–10 weeks (all 15 slices) |
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
| P1-07 | todo | P1-07 | Dev: Vietnamese i18n completion |
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
| P-DOCS-FLOW-VN | doing | P-DOCS-FLOW-VN | Owner+Dev: Vietnamese operator flow docs |
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
