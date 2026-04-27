# SRS — Etsy Multichannel Order Management Hub (English)

**Version:** v2.2 (incorporates Owner's 2026-04-26 afternoon clarifications + Stage-2 ADRs)
**Release date:** 2026-04-26
**Project owner:** Etsy Shop project owner
**Status:** Draft — pending department sign-off
**Scope:** Centralised Etsy order management — pull orders via Etsy API (with email parsing as permanent failover), manage on 3 dashboards, route to internal production or Gearment partner, push tracking back to Etsy.
**Source of requirements:** Feedback from BA / Marketing / Production (PD) / Pricing Audit (RD) departments + sample-system proposal + Owner's red-pen on `.0temp/E2_Quy_trinh_san_xuat_edit.pdf` + Stage-1 synthesis (2026-04-26).

> **This is the English mirror of `SRS_Multichannel_Hub_VN.md`** (which itself mirrors `SRS_Multichannel_Hub_VN.xlsx`). v2.2 is the source-of-truth pending the VN re-mirror.

## Changes vs. v2.1

1. **REQ-SYN-00 RESOLVED** (was BLOCKER). The "API ROI" question is reframed: the case is template-drift fragility (Etsy controls the email format unilaterally; API is a versioned contract), not historic error rate. See `clarifications/spec-005-roi-memo.md` v2 + `adrs/ADR-008a-email-as-mandatory-backup.md` v2.
2. **NEW family REQ-SRC-01..04** — Source-switching contract for the single ingestion pipeline. Email parser is now a permanent failover behind the same canonical pipeline (no dual-write, no reconciliation). Auto-failover on health-check failure; auto-recovery on probe success.
3. **NEW family REQ-PIP-01..09** — Configurable order pipeline + resource assignment. The 17 Vietnamese sub-states ship as one default seed pipeline; admin can edit and create more pipelines. Resource assignment is per-stage default with per-order override. Replaces the would-be hardcoded `mrp.production.x_substate` enum + `mrp.routing` audit-log models.
4. **REQ-PRO-03 / REQ-PRO-04 / REQ-PRO-09 reframed** — point to the configurable pipeline (REQ-PIP-*). The Process Dashboard now displays the configurable pipeline state per order; stage definitions are managed via REQ-PIP-* (§10.5).
5. **REQ-MSG-01 rewritten** — now ingests `buyer_message` field via existing `transactions_r` scope. Surfaces inline on the order form + on a top-level Customer Message Hub view. Read access MP+BA+Owner. Does NOT ingest Etsy Conversations content (scope rejected). Resolves the H8 contradiction with E2 pain #17.
6. **REQ-FIL-04 expanded** — points to ADR-012. Discord is the permanent manual escape hatch (no sunset). GDrive uses a service account; failures alert + queue + backoff (no auto-failover to Discord).
7. **NEW REQ-FIL-05 / REQ-FIL-06** — backed by ADR-009 (file lifecycle data model: `design.file`, `design.file.route`, `design.print.batch`).
8. **NEW §11 Module map** — confirms ADR-001 4-module split (D-20) and lists the module ownership of each REQ-* family.

---

## Table of contents
1. [Overview & roadmap](#1-overview--3-phase-roadmap)
2. [User roles](#2-user-roles)
3. [Etsy order sync (single pipeline + source switching)](#3-etsy-order-sync-single-pipeline--source-switching)
4. [Legacy data normalization](#4-legacy-17659-orders-normalization)
5. [Order Dashboard](#5-order-dashboard-ba--marketing)
6. [Tracking Dashboard](#6-tracking-dashboard-ba)
7. [Process Dashboard](#7-process-dashboard-pd--ba)
8. [Approval flows](#8-approval-flows-design-file--address--ticket)
9. [Tracking & fulfillment](#9-tracking-import--production-handoff)
10. [File lifecycle, auto-transition & customer-message hub](#10-file-lifecycle-auto-transition--customer-message-hub)
10.5. [Configurable order pipeline](#105-configurable-order-pipeline-new-v22)
11. [Module map (per ADR-001)](#11-module-map-per-adr-001)
12. [Extension features (Phase 2-3)](#12-extension-features-phase-2-3)
13. [Sign-off](#13-sign-off)

---

## 1. Overview & 3-phase roadmap

### What does this system do?
1. Auto-pull new orders from Etsy via API (primary) with email parsing as permanent failover behind the same canonical pipeline.
2. Display orders on 3 specialised dashboards for BA, Marketing, Production.
3. Let the design team (BA) upload print files and the production team (PD) approve them via MP.
4. Route approved orders to either the in-house workshop or the Gearment partner, then push tracking back to Etsy.
5. Design files uploaded **once**, route read-permissions to MP/BA/PD/Partner; PD bulk-downloads with A4 layout for printing.
6. Customer Message Hub aggregates buyer messages from 19 shops (`buyer_message` field via `transactions_r`; no Conversations content).
7. **(NEW v2.2)** Order workflow uses a **configurable pipeline** per product/category — the team defines stages, transitions, and resource assignments through admin UI rather than code.

### Strategic decisions (signed off in `decision-log.md`)
- Etsy API is primary; email parser is permanent failover (D-13 RESOLVED — see ADR-008a v2).
- Run on Odoo 19 CE (no Enterprise purchase).
- Vietnamese is the default UI language.
- Gearment is the primary fulfillment partner in Phase 2.
- 4-module split per ADR-001 (D-20 — pending one-line Owner confirmation; default assumption: in force).
- Order pipeline is user-configurable (D-11 + D-12 + D-16 RESOLVED — see ADR-010).

### 3-phase roadmap

| Phase | Content & acceptance criteria |
|---|---|
| **Phase 1 — MVP (~3-4 months)** | Etsy API sync (with email failover) • Source-switching health-check + auto-recovery • Normalize 17,659 legacy orders • 3 dashboards: Order, Tracking, Process • Configurable order pipeline (default seed = 17 Vietnamese stages) • Design-file lifecycle (single upload, multi-route) • Address-change approval • Tracking import from GKE Logistics Excel. **ACCEPTANCE:** BA Lead signs reconciliation; Odoo replaces Sheet for 1 month with <1% drift; default seed pipeline operational with ≥80% of orders reaching a terminal stage. |
| **Phase 2 — Expansion (~3-4 months)** | Push orders to Gearment via API and receive tracking • Replace/refund ticket system (BA approves) • Pricing Audit dashboard with EUR conversion + daily check • Customer Message Hub (`buyer_message` ingestion). **ACCEPTANCE:** Gearment orders run live without errors for 2 consecutive weeks; RD signs off on Pricing Audit. |
| **Phase 3 — Future (~4-6 months)** | Raw-material inventory + 1/3/12-month forecast • Catalog Dashboard per product • PD barcode scan sheet • Amazon and Website channels • AI analytics / BI tool integration. **ACCEPTANCE:** detail decisions deferred to end of Phase 2. |

---

## 2. User roles

(v2.1 — corrected per Owner red-pen; unchanged in v2.2)

| # | Department / Role | Primary responsibilities | Main screens |
|---|---|---|---|
| 1 | **Project Owner** | Strategic decisions, sign-off per phase, overall progress and metrics. | Weekly KPI summary; all dashboards (read-only). |
| 2 | **BA** | **Creates design files** and pushes them internally for MP approval; coordinates orders (US-od / VN-od); supplies tracking; approves address-change and replace/refund tickets. | Order Dashboard, Tracking Dashboard, address-change approvals, tickets, **Customer Message Hub** (read). |
| 3 | **Marketing (MP)** | Manages 19 Etsy stores, pushes priority orders, **approves design files made by BA**, sends preview files to buyers, handles customer messages, requests address changes, sets US-od / Vietnam-od. | Order Dashboard, order detail form, popups, **Customer Message Hub** (read+search). |
| 4 | **Production (PD)** | Actual production; **maintains pipeline state** through stages (configurable per ADR-010); scans finished parcels; manages raw-material inventory. | Process Dashboard, Scan sheet, raw-material inventory, Bulk-print wizard. |
| 5 | **Pricing Audit (RD)** | **Checks sale price + shipping price daily**; spots mis-priced orders; multi-currency reporting; broadcasts on Discord for MP same-day fix. | Pricing Audit Dashboard. |
| 6 | **Warehouse** | Issues raw materials when PD requests. After Odoo: raw materials auto-deducted on stage transition (when configured). | Inventory; Forecast 30/90/365 days. |

---

## 3. Etsy order sync (single pipeline + source switching)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| **REQ-SYN-00** *(rev v2.2)* | **Etsy API + email failover (decision recorded)** | RESOLVED. Owner direction (2026-04-26): API primary; email permanent failover behind a single canonical pipeline (no dual-write, no reconciliation). Rationale: template-drift fragility (Etsy controls email format unilaterally); API gives a versioned contract. See `decision-log.md` D-13 + ADR-008a v2. | Owner | n/a | locked |
| REQ-SYN-01 | Secure Etsy account connection | Owner enters Settings → 'Connect Etsy' → logs in once. System remembers connection and auto-renews; warns 7 days before re-auth needed. | Owner | P0 | P1 |
| REQ-SYN-02 | Auto-pull new orders every 5 minutes | System pulls new or updated orders from Etsy every 5 min via the *active source* (REQ-SRC-02). No duplicates. | BA, MP | P0 | P1 |
| REQ-SYN-03 | Do not overwrite human-entered data | When upstream reports an update on an existing order, system updates only payment/shipping state from upstream; preserves MP note, owner, design-approval state set by departments. | BA | P0 | P1 |
| REQ-SYN-04 | Auto-push tracking to Etsy | When BA enters tracking + carrier, system sends to Etsy within 5 min. | BA, MP | P0 | P1 |
| REQ-SYN-05 | Per-store auto-push toggle | Marketing has 'Auto-push tracking to Etsy' switch per store. | MP | P1 | P1 |
| REQ-SYN-06 | Etsy message history export | Marketing picks date range → 'Export messages' → downloads Excel of all messages (rows from `etsy.buyer.message` per REQ-MSG-01). | MP (#6) | P1 | P2 |
| **REQ-SRC-01** *(NEW v2.2)* | **Canonical payload contract** | Both `EtsyApiAdapter` and `EtsyEmailAdapter` produce the same canonical record (`etsy.order.payload`). Source-specific fields nullable; downstream UI shows "—" when missing. Downstream code is source-agnostic. | Owner direction | P0 | P1 |
| **REQ-SRC-02** *(NEW v2.2)* | **`etsy.shop.active_source` field** | New field with values `api` / `email`. Default after scopes granted: `api`. Default before scopes: `email`. Manual override allowed by admin. Supersedes ADR-002's `sync_mode` enum. | Owner direction | P0 | P1 |
| **REQ-SRC-03** *(NEW v2.2)* | **Health-check + auto-failover cron** | Every 5 min, probe the active source. After 3 consecutive failures → auto-switch to the other source; raise HIGH alert; record in `etsy.shop.source.change.log`. Configurable per shop. | Owner direction | P0 | P1 |
| **REQ-SRC-04** *(NEW v2.2)* | **Recovery-probe cron + auto-switch-back** | When in failover, probe the original primary hourly. After 6 consecutive successes → auto-switch back, unless `etsy.shop.auto_recovery=False` (sticky manual override). | Owner direction | P0 | P1 |

---

## 4. Legacy 17,659 orders normalization

(unchanged in v2.2; historical orders default to `state='done'` with `x_pipeline_id=NULL` per ADR-010 §10)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-MIG-01 | Upload 17,659 legacy orders from Excel | Admin uploads historical Excel; system reads and creates orders. Resumable on interruption. | Owner | P0 | P1 |
| REQ-MIG-02 | Fix 423 zero-price orders | 423 orders are recorded with $0. System recalculates from source; unrecoverable orders go to a list for BA manual fix. | RD | P0 | P1 |
| REQ-MIG-03 | Detect currency USD / EUR / GBP / CAD / VND | Reads currency symbols ($, €, £, C$, ₫) and assigns each order. Original currency preserved. | RD | P0 | P1 |
| REQ-MIG-04 | Split shipping cost into a dedicated line | Each order has a separate 'Etsy shipping fee' line so order total matches source within $0.01. | RD | P0 | P1 |
| REQ-MIG-05 | Customer dedup with BA approval | System proposes candidate duplicates → exports Excel → BA ticks approve → uploads back to merge. **No auto-merge.** | BA | P0 | P1 |
| REQ-MIG-06 | Reconciliation report & sign-off | After normalization, exports reconciliation report (total orders, revenue, shipping fee, error count). BA Lead signs before next phase. | Owner, BA | P0 | P1 |
| **REQ-MIG-07** *(NEW v2.2)* | **Historical-order pipeline placeholder** | Per ADR-010 §10: historical orders get `state='done'`, `x_pipeline_id=NULL`, `x_pipeline_state_id=NULL`. Optional bulk-assign to a "Historical / archived" pipeline (single terminal stage) is admin-discretionary. | Owner direction | P0 | P1 |

---

## 5. Order Dashboard (BA + Marketing)

(unchanged in v2.2)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-ORD-01 | Display 10 core columns | Shop, Order ID, Tracking, IMG, Date, Status, Quantity, Shipping Service, Country, Total. | BA (#1) | P0 | P1 |
| REQ-ORD-02 | Shop and Order ID as the first two columns | Search works on both. | BA (#1) | P1 | P1 |
| REQ-ORD-03 | Drop columns: Ship-out date, retail price, PIC | Ship-out auto-set on PD scan; retail prices fold into Total; PIC inferred from shop. | BA (#1) | P1 | P1 |
| REQ-ORD-04 | Merge Tracking + Label state + Carrier into one column | Shows: 'Awaiting label' / 'Buying label' / `<carrier>: <number>`. | BA (#1), Sample system | P0 | P1 |
| REQ-ORD-05 | Product image per row | 128px thumbnail, click for full image. | MP (#2, #10) | P0 | P1 |
| REQ-ORD-06 | Inline-edit operational columns | BA edits inline: Tracking, Carrier, Label state, Order status, Note. | BA, MP | P1 | P1 |
| REQ-ORD-07 | Row-color rules | qty ≥ 2 → orange; duplicate order code → purple; Push → red; Amazon → red. | PD | P1 | P1 |
| REQ-ORD-08 | Push button for priority | MP clicks Push → row marked + colored red; history logs who/when. Amazon orders placed same day as Etsy auto-PUSH. | MP (#4) | P1 | P1 |
| REQ-ORD-09 | Approval-overdue badge (>2 days) | Orders unapproved >2 days → warning + yellow row. | MP (#7) | P2 | P1 |
| REQ-ORD-10 | Ship-by deadline column | Show 'Tracking deadline' from Etsy. Overdue → red. | MP (#3) | P1 | P1 |
| REQ-ORD-11 | Store-manager avatar | Avatar/icon of the store owner per row. | MP (#8) | P2 | P1 |
| REQ-ORD-12 | Special-event popups | Push, hold, address-change → popup to right person within 10s. | MP (#9) | P2 | P1 |
| REQ-ORD-13 | 'MP Note' field on order | Separate from 'Sale note'; MP records customer custom requests. | BA (#6) | P1 | P1 |
| REQ-ORD-14 | Order-status change history | History tab: who changed, when, from what to what. (Backed by `order.pipeline.transition.log` per ADR-010.) | BA (#4), MP (#5) | P1 | P1 |
| REQ-ORD-15 | Product name + manual BA classification | BA can override automatic classification. | BA (#9) | P2 | P1 |
| **REQ-ORD-16** *(NEW v2.2)* | **Design-file status badge** | Per ADR-009: each row shows pending/approved/needs-revision badge for the order's design file(s). Click → opens `design.file` form. | BA, MP | P1 | P1 |

---

## 6. Tracking Dashboard (BA)

(unchanged in v2.2)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-TRK-01 | Dedicated Tracking page | 'Tracking' menu opens a dedicated page (not a filter on Order Dashboard). | BA (#2) | P0 | P1 |
| REQ-TRK-02 | 13 tracking columns | Order ID, Tracking, Carrier, Status, Product type, Quantity, Name, Address 1-2, City, State, Zip, Country. | BA, Sample system | P0 | P1 |
| REQ-TRK-03 | Excel export | Download Excel by current filter. | BA (#2) | P1 | P1 |
| REQ-TRK-04 | Bulk label-state transition | Select many orders → move 'Awaiting label' → 'Buying label' in one click. | BA (#2) | P1 | P1 |
| REQ-TRK-05 | Search by tracking / Order ID / customer name | Quick search bar on top. | BA (#2) | P1 | P1 |
| REQ-TRK-06 | Sync to Order Dashboard | Updates reflect within 5 seconds. | BA (#2) | P0 | P1 |
| REQ-TRK-07 | Block label-buy when address-change pending | Disable Buy Label + warning. | BA (#5 — safety) | P0 | P1 |
| REQ-TRK-08 *(rev v2.2)* | Show tracking state (in-transit, delivered, returned) | Carrier webhooks (USPS/UniUni/YunExpress where available) → write to `stock.picking.x_tracking_state`; live update via `bus.bus`. Pain #16. | MP | P1 | P2 |

---

## 7. Process Dashboard (PD + BA)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-PRO-01 | Name 'Process Dashboard' | BA and PD co-operate; covers VN and US orders. | BA (#10) | P1 | P1 |
| REQ-PRO-02 | Production columns per PD proposal | Approval date, File download, Status, Note, Image, Gift message, Personalisation, Product type, Option, Quantity, Order ID, Shop, Customer name, Address, Shipping service, Order date, Ship date, Scan, Auto-stats. | PD | P0 | P1 |
| **REQ-PRO-03** *(rev v2.2)* | **Pipeline-state column (configurable)** | The dashboard shows the current `x_pipeline_state_id` per order with the stage's color. Stage definitions are managed via REQ-PIP-* (see §10.5). The default seed pipeline ships with the 17 Vietnamese stages from E2 §6 (CHỜ FILE → … → VN-Fulfilled), but admin can edit, add, remove, or replace. **Stage semantics ("VN-Packed 1 means what?", "[Fix]VN-Dish triggered when?") are user-configured at runtime, not hardcoded** — see ADR-010 §9. | PD, Owner red-pen | P0 | P1 |
| **REQ-PRO-04** *(rev v2.2)* | **Resource assignment per stage** | Each pipeline stage carries an optional default `responsible_team_id` (`pipeline.team` model). The dashboard groups by team or filters by team. Per-order override allowed for admin/PD-lead. See ADR-010 §6. | PD, Owner red-pen | P0 | P1 |
| REQ-PRO-05 | Show design and preview images | 2 thumbnails per row: original design + preview. | MP (#2) | P1 | P1 |
| REQ-PRO-06 | Statistic widget | Counts by: pipeline state, option, product type, quantity. | PD | P2 | P1 |
| REQ-PRO-07 | Scan → Fulfilled | Barcode scan → advances pipeline state to terminal stage marked as "fulfilled" in pipeline definition; ship date auto-set, who/when logged. | PD, BA (#1) | P1 | P1 |
| REQ-PRO-08 | (deprecated v2.2 — folded into REQ-PIP-*) | Was: "4 internal production sub-states." Now: any pipeline can declare these via stage definitions. No separate enum. | — | n/a | n/a |
| **REQ-PRO-09** *(rev v2.2)* | **Audit log + governance for pipeline changes** | All pipeline structure edits, stage renames, resource reassignments, and per-order transitions are logged in `order.pipeline.transition.log` (single audit table; `change_type` enum). Pipelines auto-version on first-use edit (see ADR-010 §5); in-flight orders snapshot the version at confirmation time. Stage's resource reassignment never affects orders already in that stage (snapshot on entry per ADR-010 §6). | Devil's advocate N3 | P0 | P1 |

---

## 8. Approval flows (design file / address / ticket)

(unchanged in v2.2; design-file approval mechanics now backed by ADR-009)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-DUY-01 | Upload large print file, delete and re-upload | Designer uploads large file (e.g. 150MB to GDrive); can delete and re-upload; old versions retained for audit (per ADR-009 §1: `parent_file_id` chain). | BA (#8) | P0 | P1 |
| REQ-DUY-02 | Design-file approval flow | Awaiting → Approved / Needs revision (reason required). Records who approved when. (Per ADR-009 §2 lifecycle.) | PD | P0 | P1 |
| REQ-DUY-03 | Kanban design queue | 3 columns; drag-drop or click to advance. (Backed by `design.file.state` per ADR-009.) | Designer, BA | P1 | P1 |
| REQ-DUY-04 | Address-change approval | MP cannot edit address directly. Submit request → BA approves/rejects → only then can MP set new address. | BA (#5 — safety) | P0 | P1 |
| REQ-DUY-05 | Lock label-buy during pending address change | Disable label-buy actions; warning badge on Tracking. | BA (#5 — safety) | P0 | P1 |
| REQ-DUY-06 | Create replace/refund ticket from order detail | 'Create ticket' button on order; MP enters reason + image; choose replace/refund/discount; submit to BA. | BA (#3) | P1 | P2 |
| REQ-DUY-07 | BA approves ticket → auto-process | Refund → credit note; Replace → new order linked to original; Discount → record discount. | BA (#3) | P1 | P2 |
| REQ-DUY-08 | Ticket history in order | History tab shows all ticket actions. | BA (#4) | P2 | P2 |

---

## 9. Tracking import & production handoff

(unchanged in v2.2)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-TRF-01 | Import tracking from GKE Logistics Excel | Upload standard GKE Excel; match by Order ID → auto-fill tracking + carrier. Unmatched rows logged for BA manual fix. | BA (#2), Logistics | P0 | P1 |
| REQ-TRF-02 | Auto-detect carrier from tracking | 20-22 digits → USPS; 'UU' → UniUni; 'YT' → YunExpress; else 'Other'. | Logistics | P0 | P1 |
| REQ-TRF-03 | Process '-replace' orders + store label/QR URLs | Orders with '-replace' suffix link to original. Label URL + QR URL stored on the order. | BA, Logistics | P1 | P1 |
| REQ-TRF-04 | Import report (matched / unmatched) | Wizard summary; click for per-row error detail. | BA | P1 | P1 |
| REQ-TRF-05 | Connect Gearment + push orders | Configure Gearment once. BA clicks 'Push to Gearment' to send order + design file (per ADR-009 routing policy). | Owner, BA | P0 | P2 |
| REQ-TRF-06 | 4-step Gearment flow | Draft → quote → BA/operator approves → confirm. | BA | P0 | P2 |
| REQ-TRF-07 | Receive Gearment tracking and state | Webhook or cron pull → update order → push to Etsy (if MP enabled auto-push). | BA, MP | P0 | P2 |
| REQ-TRF-08 | Error handling and retry | Up to 3 retries; on failure log + alert admin. | Owner | P1 | P2 |
| REQ-TRF-09 | Gearment orphan policy on rework | When MP triggers a rework that supersedes a Gearment draft (e.g., the seed pipeline's "[Fix]" stage), the old Gearment draft/quote must be canceled or auto-expire. Policy to be confirmed with Gearment support (D-21 OPEN). | Devil's advocate N5 | P0 | P2 |

---

## 10. File lifecycle, auto-transition & customer-message hub

(NEW family v2.1; expanded v2.2 — REQ-FIL-* now backed by ADR-009; REQ-MSG-01 rewritten)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| **REQ-FIL-01** *(rev v2.2)* | **`design.file` model — single upload, multi-route** | BA uploads once; system creates `design.file` record with GDrive primary URL + checksum + version. Per ADR-009 §1. | MP, BA, PD (#11, #18) | P0 | P1 |
| **REQ-FIL-02** *(rev v2.2)* | **`design.file.route` — per-recipient delivery state** | Each `design.file` linked to N routes: `recipient_type` (MP/BA/PD/partner), `state` (pending/sent/acknowledged/failed), `delivery_method`, audit timestamps. Per ADR-009 §1+§4. | BA (#11) | P0 | P1 |
| **REQ-FIL-03** *(rev v2.2)* | **`design.print.batch` — bulk-download A4 layout wizard** | PD ticks approved files → wizard generates A4 PDF → 24h cache. Per ADR-009 §1. | PD (#12) | P1 | P1 |
| **REQ-FIL-04** *(rev v2.2)* | **GDrive failover + Discord as permanent escape hatch** | Per ADR-012: service account, alert+queue+backoff on auth failure, **NO auto-fallback to Discord**. Discord stays as permanent **manual** escape hatch (no sunset). | Devil's advocate N4 | P1 | P1 |
| **REQ-FIL-05** *(NEW v2.2)* | **Re-upload creates a new `design.file` row (immutable history)** | Per ADR-009 §2: rejected file stays in `state='needs_revision'`; new upload creates new row with `parent_file_id` set + `version+1`. Enables KPI on first-pass approval rate. | BA, PD | P1 | P1 |
| **REQ-FIL-06** *(NEW v2.2)* | **Route delivery via queued jobs with warning badge on stuck routes** | Per ADR-009 §4: route delivery actions (GDrive permission grant, Gearment API push, etc.) run as queued jobs. Routes pending/failed >2h surface a warning badge on the order's Process Dashboard row. | PD, BA | P1 | P1 |
| **REQ-AUT-01** *(rev v2.2)* | **Auto-transition triggers (Phase 2 layer)** | Per ADR-010 §8: Phase 1 ships `auto_advance_trigger='none'` only. Phase 2+ adds built-in triggers (`on_payment`, `on_design_approved`, `on_tracking_imported`) via the pipeline-stage configuration UI. | MP, BA, PD (#13) | P2 | P2 |
| **REQ-AUT-02** *(rev v2.2)* | **Route file design on `sale.order.action_confirm()`** | When BA confirms an order with an approved `design.file`, the order's pipeline routing policy creates `design.file.route` records per ADR-009 §4. State=pending → queued job runs → state=sent or failed. | BA | P1 | P1 |
| **REQ-MSG-01** *(rev v2.2)* | **Customer Message Hub — `buyer_message` ingestion** | Cron pulls `buyer_message` field on `GET /v3/application/shops/:shop_id/receipts` (already in scope under `transactions_r`). Stores in new model `etsy.buyer.message` (one row per receipt with non-empty buyer message). Surfaced (a) on the order form as a tab and (b) on a top-level "Customer Message Hub" view (search + filter across shops). Read access: MP + BA + Owner. **Does NOT ingest Etsy Conversations content** (scope rejected). | MP (#17) | P1 | P2 |

---

## 10.5. Configurable order pipeline (NEW v2.2)

(Backed by ADR-010. Resolves D-11, D-12, D-16. Replaces the would-be hardcoded `mrp.production.x_substate` enum.)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| **REQ-PIP-01** | **`order.pipeline` model** | Named, versioned pipeline definitions. Per ADR-010 §1. | Owner direction | P0 | P1 |
| **REQ-PIP-02** | **`order.pipeline.state` model** | Stage within a pipeline: name, sequence, is_initial, is_terminal, color, optional `next_stage_ids` (DAG), optional `responsible_team_id`. Per ADR-010 §1. | Owner direction | P0 | P1 |
| **REQ-PIP-03** | **`pipeline.team` model + team assignment** | Lightweight custom team model (decoupled from MRP and CRM). Per ADR-010 §6. | Owner direction | P0 | P1 |
| **REQ-PIP-04** | **`order.pipeline.transition.log` — single audit table** | All pipeline structure edits, stage renames, resource reassignments, and order transitions logged here (`change_type` enum). Per ADR-010 §1. | Devil's advocate N3 | P0 | P1 |
| **REQ-PIP-05** | **Pipeline assignment scope: per-product with category default** | `product.template.x_default_pipeline_id`, fallback `product.category.x_default_pipeline_id`, fallback system parameter. Per ADR-010 §2. | Owner direction (Q1=C) | P0 | P1 |
| **REQ-PIP-06** | **Mixed-pipeline order handling: manual with default** | When line items resolve to different pipelines, default to the first line item's pipeline; UI flags for BA confirmation. Per ADR-010 §3 (Q2=D). | Owner direction | P1 | P1 |
| **REQ-PIP-07** | **Pipeline auto-versioning on first-use edit** | Editing a pipeline that has any in-flight orders creates a new `order.pipeline` row with `parent_pipeline_id` set + `version+1`. Existing orders continue using the old version. Per ADR-010 §5 (Q5=A). | Owner direction | P0 | P1 |
| **REQ-PIP-08** | **Transition policy per pipeline** | Per-pipeline `transition_policy` field with values `dag_strict` / `dag_with_admin_override` (default) / `free_form`. Backward jumps and rework loops are explicit `next_stage_ids` cycles. Per ADR-010 §7 (Q7=C). | Owner direction | P0 | P1 |
| **REQ-PIP-09** | **Default seed pipelines** | `data/order_pipeline_seed.xml` ships with: (a) "Vietnam Internal Production" (the 17 stages from E2 §6), (b) "Gearment POD" (4-stage), (c) "Multi-Technique Hybrid" (template). Per ADR-010 §9 (Q9=A). | Owner direction | P0 | P1 |

---

## 11. Module map (per ADR-001)

(NEW v2.2 — confirms ADR-001 4-module split; D-20 pending one-line Owner confirmation; default assumption: in force)

| Module | Owns these REQs | Depends on |
|---|---|---|
| **`multichannel_hub_core`** | REQ-PIP-01..09 (configurable pipeline + teams + audit log), REQ-FIL-01..06 (file lifecycle), REQ-DUY-01..08 (approval flows), REQ-PRO-01..09 (process dashboard mechanics shared across channels), REQ-ORD-01..16 (order dashboard mechanics shared across channels), REQ-TRK-01..08 (tracking dashboard) | `sale_management`, `stock`, `mail`, `contacts` |
| **`etsy_channel_api`** | REQ-SYN-01..06 (Etsy account / API sync / push-back), REQ-SRC-01..04 (canonical payload + active-source field + health-check + recovery-probe), REQ-MSG-01 (`buyer_message` ingestion via API), REQ-MIG-01..07 (legacy normalization tooling that pulls from API for verification) | `multichannel_hub_core` |
| **`etsy_channel_email`** *(renamed from `etsy_channel_legacy` per ADR-008a)* | Email parser (continues operating as failover behind REQ-SRC-02..04), Gmail cron, parser-template-drift health metric | `multichannel_hub_core` |
| **`gearment_partner`** | REQ-TRF-05..09 (Gearment integration — push orders, receive tracking, error handling, orphan-policy) | `multichannel_hub_core` |

The 4 modules install independently. `multichannel_hub_core` provides the abstractions; channel/partner modules implement the upstream/downstream adapters.

---

## 12. Extension features (Phase 2-3)

(was §11 in v2.1; renumbered to §12 in v2.2)

| Req ID | Title | Description | Requested by | Priority | Phase |
|---|---|---|---|---|---|
| REQ-EXT-01 | Pricing Audit Dashboard | 25 cols; A-F manual, G-T auto from orders. Multi-currency. | RD | P1 | P2 |
| REQ-EXT-02 | EUR conversion | Auto-convert USD/VND/CAD to EUR by order date. Show 'Total (EUR)'. | RD | P1 | P2 |
| REQ-EXT-03 | Color price-vs-catalog variance | Red (low) / yellow (par) / purple (high). | RD | P1 | P2 |
| REQ-EXT-03b | Daily auto-flag mis-priced orders | Cron each morning lists orders exceeding threshold; pings RD + colors dashboard. | RD, devil's advocate N7 | P1 | P2 |
| REQ-EXT-04 | Upload raw-material inventory from Excel | PD uploads Excel → system creates initial inventory. | PD | P1 | P3 |
| REQ-EXT-05 | Auto-deduct raw materials on terminal pipeline state | When the order's `x_pipeline_state_id` reaches a stage flagged `is_terminal_for_inventory`, deduct per BoM. | PD | P1 | P3 |
| REQ-EXT-06 | Forecast 1 / 3 / 12 months | Dashboard: how many months current stock covers. | PD | P2 | P3 |
| REQ-EXT-07 | Alert raw materials <2 months | PD Lead notified + dashboard red. | PD | P2 | P3 |
| REQ-EXT-08 | Catalog Dashboard per product | Product form: design template, mockup, sales history. Per ADR-009 §3 (sample/mockup `design.file` records). | BA (#7) | P2 | P3 |
| REQ-EXT-09 | Store template + mockup on product | 2 file fields: original template + mockup. | BA (#7) | P2 | P3 |
| REQ-EXT-10 | PD barcode scan sheet | Simple scan page: auto-focus, enter to confirm. | BA (#11), PD | P2 | P3 |
| REQ-EXT-11 | Scan synced across all dashboards | Update within 5 seconds. | BA, PD | P2 | P3 |
| REQ-EXT-12 | Amazon channel integration | Amazon Seller Central → orders into shared Dashboard. New module `amazon_channel` per ADR-001 pattern. | PD | P2 | P3 |
| REQ-EXT-13 | Open Odoo Website channel | Use Odoo Website module; orders into shared Dashboard. New module `website_channel`. | Owner | P2 | P3 |
| REQ-EXT-14 | AI analytics — schema export contract | Defer build to Phase 3+. In Phase 1, lock schema export for `sale.order`, `order.pipeline*`, `design.file*`, `etsy.shop.source.change.log`, etc. so a BI tool can read later. | MP, BA, PD (#19) | P2 | P3 |
| REQ-EXT-15 | (deprecated v2.2 — superseded by REQ-PIP-09) | Was: "Multi-technique routing." Now: handled by configuring a "Multi-Technique Hybrid" pipeline per ADR-010 §9. No new model needed. | — | n/a | n/a |

---

## 13. Sign-off

(was §12 in v2.1; renumbered to §13 in v2.2)

| # | Role | Name | Signature date | Signature | Notes / Conditions |
|---|---|---|---|---|---|
| 1 | Project Owner | | | | |
| 2 | BA Lead | | | | |
| 3 | Marketing Lead | | | | |
| 4 | Production Lead (PD) | | | | |
| 5 | Pricing Audit Lead (Sales Audit) | | | | |

> **Sign-off conditions for v2.2:**
> - REQ-SYN-00 RESOLVED in `decision-log.md` D-13 (no separate Owner memo needed; Stage-1 synthesis recorded the decision).
> - D-20 (ADR-001 module split confirmation) is the one outstanding critical-path decision; default assumption is "in force" pending one-line Owner confirmation.
> - REQ-PIP-* / REQ-FIL-* / REQ-SRC-* are accepted via Stage-2 ADRs (009, 010, 008a, 012) signed off in `decision-log.md`.
> - Phase 2 entry depends on D-21 (Gearment orphan policy) being closed before REQ-TRF-05 implementation.

---

*End of SRS v2.2 (EN). Vietnamese mirror update pending (`SRS_Multichannel_Hub_VN.md` v2.2). Excel: rebuild via `build_srs.py` after VN markdown is updated.*
