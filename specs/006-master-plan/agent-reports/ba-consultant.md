# BA / Odoo Consultant Review — Multichannel E-commerce Hub

**Lens**: Business process fit, user adoption, Odoo-native leverage, MVP framing
**Date**: 2026-04-10
**Source reports**: End-user feedback (BA, Marketing, PD, Sales/Pricing Audit) + specs 001–005

---

## 1. End-user needs vs. current spec coverage

### BA Department (15 numbered requests)

| # | Request | Covered by | Coverage |
|---|---|---|---|
| 1 | Drop "ship date" col, auto-set on PD scan; reorder cols; shorter rows | 003 US1 (operational list) | **Partial** — list view exists, column policy and auto-date-on-scan not specified |
| 2 | Merge Tracking + Label status + Carrier into single state col | 003 US6/US7 | **Partial** — both exist but as separate fields; merge not explicit |
| 3 | Move "Note from Sales" into order detail | 003 US1 | **Missing** — not called out |
| 4 | Remove price/ship/discount cols, keep final total only | 003 US1 | **Missing** — column policy unspecified |
| 5 | Drop "Người phụ trách" col (redundant) | — | **Missing** |
| 6 | Dedicated **Tracking page** with export/import/bulk-edit | 004 US8 (tracking import) | **Partial** — import covered, dedicated page UX + bulk edit missing |
| 7 | **Ticket system** per order (replace/refund, BA approves) | 004 US7 (returns/refunds) | **Partial** — returns model exists, ticket UX + BA approval loop missing |
| 8 | **Audit log** per order | 003 edge case mentions chatter; 004 FR-018 | **Partial** — chatter implied but no explicit user story |
| 9 | **Address-change approval workflow** | — | **Missing entirely** |
| 10 | MP note field inside order | — | **Missing** |
| 11 | **Catalog Dashboard** (per-product template + mockup) | — | **Missing entirely** |
| 12 | Large print-file upload + delete/re-upload | 003 US2 | **Full** for upload; re-upload is "new version record" by design |
| 13 | Per-order product name display + BA classify | 003 US1 | **Partial** — display yes, classify/tick missing |
| 14 | Rename "PD page" -> **Process Dashboard** (VN+US) | 003 US1 + 004 US4 | **Partial** — two separate dashboards, not unified |
| 15 | **Scan sheet** barcode interface | — | **Missing entirely** |

### Marketing

| Request | Covered by | Coverage |
|---|---|---|
| Per-MP toggle for tracking push to Etsy | 005 US3 | **Partial** — per-shop only, not per-MP |
| **Product images in list** | — | **Missing** — critical, repeated request |
| "Add-tracking deadline" column (ship-by) | 005 (receipt sync) | **Missing** — field not mapped |
| Push (priority) button | 003 US5 | **Full** |
| Status change history per order | 003/004 via chatter | **Partial** |
| Export full message history | — | **Missing** (Etsy messaging deferred in 005 US7) |
| Overdue-approval marker (>2 days) | — | **Missing** |
| Store-manager icon on order | — | **Missing** |
| Popup notifications (push/hold/address) | — | **Missing** |

### Production (PD)

| Request | Covered by | Coverage |
|---|---|---|
| Process detail table | 004 US4 | **Full** |
| **Raw material inventory** + Excel seed upload | 004 US5 | **Partial** — visibility only, no seed wizard |
| **Auto-decrement on "Đã sản xuất"** | — | **Missing** — 004 US5 explicitly scopes out |
| **Material forecasting 1/3/12 months** | — | **Missing entirely** |
| PD column set (18 columns) | 003 US1 + 004 US4 | **Partial** — not all fields mapped |
| Status enum with Vietnamese labels + colors | 003 US3/US6 | **Partial** — 3-state design only, not the 10 PD states |
| Row tags: qty>=2, duplicate, Push, Amazon | 003 US5 (push only) | **Partial** |
| Product type master list + size variants | — | **Missing** (likely just `product.template` config but no story) |

### Sales / Pricing Audit ("Feedback phòng RD" — mislabeled file)

| Request | Covered by | Coverage |
|---|---|---|
| **Multi-currency with EUR conversion** | 002 US1 | **Partial** — keeps original currency, no EUR conversion view |
| **Price delta vs catalogue** + red/yellow/purple | — | **Missing entirely** |
| Auto-populate cols G–T from orders | 003 US1 | **Partial** |

### System sample proposal (`Đề xuất hệ thống mẫu`)

Order Dashboard / Tracking Dashboard / Processing Dashboard — **three distinct dashboards**. Current specs assume one (003 US1) plus production queue (004 US4). **This is the biggest structural gap**: end users want three specialised dashboards, specs deliver 1.5.

---

## 2. Alignment gaps

**2.1 One dashboard vs. three.** BA, PD, and the owner's sample all describe three separate dashboards: Order Dashboard (commercial view), Tracking Dashboard (shipping/logistics view), Process Dashboard (production view). Spec 003 conflates the first with a generic "operational dashboard"; Spec 004 US4 adds production queue as a fourth. The Tracking Dashboard (BA #6) has no dedicated story — it is an afterthought of 004 US8.

**2.2 Process Dashboard != 003 dashboard.** BA #14 asks for a **unified VN+US Process Dashboard** where BA and PD co-operate. Spec 003's dashboard is commercial/operational. Spec 004 US4 is a production queue. Neither is the cross-team collaboration view BA asked for.

**2.3 Material forecasting is homeless.** PD explicitly requested 1/3/12-month projections and alerts when stock < 2 months. Spec 004 US5 limits itself to "visibility, not full inventory management" and defers MRP. There is no spec slot for forecasting today.

**2.4 Sales Pricing Audit is homeless.** The multi-currency, delta-vs-catalogue dashboard with red/yellow/purple is a full dashboard and a business control — not inside 001–005. This needs its own user story.

**2.5 Catalog Dashboard (BA #11) is homeless.** Per-product view with template, mockup, and linked orders. Odoo-native `product.template` form + a smart button to orders gets you 70% for free, but no spec calls it out.

**2.6 Scan sheet (BA #15) is homeless.** Barcode-driven interface is a different UX mode (kiosk-style). Not in any spec.

**2.7 Ticket system (BA #7) vs. returns (004 US7).** 004 US7 is a returns data model; BA wants Dreamship-style replace/refund UX with BA approval. Models overlap but UX and approval loop are missing. Also: **Odoo CE has no helpdesk** — it is Enterprise-only. Flag as a build vs. buy decision.

**2.8 Audit log (BA #8).** Specs assume `mail.thread` chatter covers it. Works for field changes via `tracking=True`, but BA wants a **per-order full history view** as a first-class tab. Chatter does this by default — just needs to be a stated acceptance criterion.

**2.9 Address-change approval (BA #9).** Completely missing. This is a **safety-critical workflow** — BA explicitly noted it must sync to the Tracking page to prevent duplicate label purchases. High business risk, zero spec coverage.

**2.10 Etsy message export (Marketing).** 005 US7 defers customer messaging. Marketing wants message **export** for audit, not live messaging. These are different — export could be scoped to read-only fetch + CSV dump, much cheaper than full messaging.

**2.11 Row tags/colors.** PD asked for qty>=2 (orange), duplicate (purple), Push (red), **Amazon (red)**. Only Push is covered (003 US5).

**2.12 Product images in list.** Marketing asked **twice**. Completely missing from 003 US1.

---

## 3. Odoo-native leverage opportunities

| Feature | Recommended Odoo CE mechanism | Notes |
|---|---|---|
| Address-change approval (BA #9) | `mail.activity` + custom status field | CE `approvals` is Enterprise-only |
| Design approval (already in 003) | Kanban view with `group_by=approval_status` | Already planned. Good |
| Ticket system replace/refund (BA #7) | **Custom minimal** on `sale.order` (`etsy.order.ticket` one2many) | Helpdesk is Enterprise. Custom = 1 model + form + activity |
| Audit log (BA #8) | `mail.thread` + `tracking=True` + chatter tab | Free, native, declare as FR |
| Multi-currency rollup (Sales audit) | `res.currency.rate` + computed field | Native |
| Price delta vs catalogue | Computed field on `sale.order.line` comparing `price_unit` to `product.list_price` | No new models |
| Material forecasting | `stock.warehouse.orderpoint` + `stock.forecasted.product.product` report | **Odoo 19 has native forecasted inventory reports** |
| Auto-decrement on "produced" | `stock.move` triggered by state transition | Native |
| Barcode scan sheet (BA #15) | `stock_barcode` CE module OR custom `/scan` controller | Confirm CE availability |
| Inline editable dashboard | `<list editable="bottom">` | Native |
| Product images in list | `<field name="image_128" widget="image">` | Native |
| Overdue approval marker | `ir.cron` + computed `is_overdue` + list decoration | Native |
| Row color tags | `<list decoration-danger decoration-warning>` | Native |
| Store-manager icon | `avatar` widget | Native |
| Popup notifications | `mail.activity` + `bus.bus` channel | Native |
| Catalog Dashboard (BA #11) | `product.template` form + smart buttons | Native |

**Key finding**: ~70% of missing features are **already free in Odoo 19 CE**. The gap is specification discipline, not engineering capacity.

**Honest CE limits**:
- No `helpdesk`, `approvals` (beyond basic), `documents`, `marketing_automation`, `field_service`, `planning`, `documents_google_drive` in CE.
- `stock_barcode` CE — confirm.

---

## 4. User-story reprioritization

### Upgrade to MVP (ship in 6-8 weeks)

| Story | From | To | Why |
|---|---|---|---|
| 002 US6 (migration wizard) | P1 | **P0 / do first** | Without this, 17,659 orders stay unusable |
| 003 US1 (operational list) | P1 | **P1, rescoped** | Add: product image, row decorations, merged Tracking state |
| 003 US2 (design upload) | P1 | P1 | Keep |
| 003 US3 (design approval) | P1 | P1 | Keep |
| 004 US8 (tracking import) | P2 | **P1** | BA #6 — daily pain, highest value/effort |
| **NEW: Tracking Dashboard** | — | **P1** | BA #6 — dedicated page |
| **NEW: Address-change approval** | — | **P1** | BA #9 — safety-critical |
| **NEW: Product images in list** | — | **P1** | Marketing repeated request |

### Downgrade (defer past MVP)

| Story | From | To | Why |
|---|---|---|---|
| 005 US6 (bidirectional listings) | P2 | **P3** | Not a pain point |
| 005 US4 (webhooks) | P1 | **P2** | 10-min cron acceptable |
| 003 US4 (multi-channel field) | P2 | **P2** | Scaffolding only |
| 004 US9 (Google Drive sync) | P3 | **P4** | Manual import works |
| 002 US7/US8/US10 | P3/P4 | **P4** | Nice-to-have |

### Add as new stories (missing today)

1. Unified Process Dashboard (VN+US) — BA #14
2. Tracking Dashboard — BA #6
3. Address-change approval workflow — BA #9
4. Order ticket system (replace/refund) — BA #7
5. Product images in all list views — Marketing
6. Row color decoration pack — PD
7. Audit log tab per order — BA #8
8. MP note field in order detail — BA #10
9. Overdue-approval marker (>2 days) — Marketing
10. Sales Pricing Audit dashboard — multi-currency + delta bands
11. Catalog Dashboard — BA #11
12. Scan sheet — BA #15
13. Raw-material Excel seed upload — PD
14. Material forecasting 1/3/12 months — PD
15. Etsy message export (read-only, CSV) — Marketing
16. Store-manager avatar in list — Marketing

### Suggested MVP bundle (6-8 weeks)

**Phase 0 (weeks 1-2)**: 002 US1+US2+US6 migration. Unblock 17,659 orders.

**Phase 1 (weeks 3-5)**: 003 US1 rescoped + images + row decorations + audit-log AC + MP note + overdue marker. Replaces the Google Sheet for BA and Marketing.

**Phase 2 (weeks 5-6)**: 003 US2+US3 design upload and approval + address-change approval (BA #9).

**Phase 3 (weeks 6-8)**: 004 US8 tracking import + dedicated Tracking Dashboard (BA #6). Closes the biggest daily pain point.

**Explicitly out of MVP**: Gearment API (004 US3), Etsy API (all of 005), material forecasting, Amazon, website, ticket system, Catalog Dashboard, Scan sheet, Pricing Audit. These ship in phases 4+ based on real MVP usage feedback.

---

## 5. Change management & rollout

**Training order**: BA team first (they are the hub); PD team second; Marketing last.

**Cutover strategy**:
- **Parallel run for 4 weeks** on the Tracking Dashboard and Order Dashboard. Google Sheet remains source of truth until daily reconciliation shows < 1% drift for 10 consecutive days.
- **Freeze date**: end of week 4 of parallel run.
- **Daily end-of-day reconciliation** during parallel. BA lead signs off.
- Spec 002 migration wizard runs **once**, cleanly, before parallel run starts.

**Localization**:
- **Vietnamese UI is non-negotiable for PD**. Use Odoo's native `.po` files. Budget 3-5 days for a complete VN translation pass.

---

## 6. Top 10 Recommendations

**R1. Split Spec 003 into three dashboards, not one.** Order Dashboard, Tracking Dashboard, Process Dashboard (unified VN+US). Spec 003 update. Effort: **M**

**R2. Add an "Address-change approval" user story to Spec 003.** New model `etsy.address.change.request` with Requested/Approved/Rejected states, mail.activity to BA, lock on sale.order shipping fields while pending. Effort: **M**

**R3. Add product image + row decoration pack to Spec 003 US1.** `image_128` in list, computed booleans `is_qty_bulk`, `is_duplicate`, `is_amazon`, `is_push`. Effort: **S**

**R4. Rewrite Spec 004 US5 as two stories**: "Stock visibility" (P3) and "Material forecasting" (P2), using native Odoo forecasted reports. Effort: **M**

**R5. Create new Spec for "Sales Pricing Audit dashboard"**: Computed `amount_total_eur`, `price_delta_vs_catalogue`, state bands. Effort: **M**

**R6. Demote Spec 005 webhooks (US4) and listings (US6); keep only OAuth + receipt sync + tracking push + rate limiting for MVP.** Effort: **M** (scope cut)

**R7. Build ticket system as minimal custom `etsy.order.ticket` on sale.order**; do not assume helpdesk. Effort: **M**

**R8. Make audit log an explicit FR.** Add `tracking=True` across models. Effort: **S**

**R9. Run Spec 002 migration as Phase 0 with explicit reconciliation sign-off.** Effort: **M**

**R10. Commit to Vietnamese UI as cross-cutting requirement.** Add FR-i18n to each spec. Effort: **S** per spec.

---

## Summary for the owner

The current spec set is **over-indexed on API integrations (005) and under-indexed on dashboard UX (003)**. End-user feedback tells a consistent story: BA wants three specialised dashboards, one safety workflow (address changes), one approval workflow (design), one data hygiene tool (ticket system). Marketing wants images and a toggle. PD wants forecasting and a scan sheet. Sales wants a pricing audit. **None of these need Etsy API work to deliver value.**

The 6-8 week MVP should not ship a single Etsy API call. Finish 002, rebuild 003 around three dashboards with the missing BA workflows, ship 004's tracking import with a dedicated Tracking Dashboard — and you will replace the Google Sheet entirely.
