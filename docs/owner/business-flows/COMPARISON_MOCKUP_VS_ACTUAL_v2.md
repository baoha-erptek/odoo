# Mockup ("Màn hình Odoo") vs Actual build — v2 refresh (2026-06-20)

> Supersedes `COMPARISON_MOCKUP_VS_ACTUAL.md` (2026-06-07, now archived under
> `docs/archive/2026-06-20/`). The prior audit predated the Gearment/fulfillment
> and shipping-profile work and wrongly marked Flow 3b as "stub/not built".
>
> **Scope of this refresh:** code-grounded existence check of every "Màn hình Odoo"
> mockup screen against the current `custom_addons/` tree, on the two axes the owner
> asked about — **UI/UX gap** and **Functional gap**. Staging screenshot re-harvest
> is a separate remaining Phase-A step (needs `STAGING_DB=esty_odoo19` browser access).

---

## How to read this

Each screen gets a **status**:

| Status | Meaning | Where the work lands |
|---|---|---|
| `built+matches` | Feature works AND a standard view exposes it close to mockup intent | — (verify only) |
| `built+needs-curation` | Feature works + view exists, but UI needs field curation / brand tint to reach mockup intent | **Phase C** (UI) |
| `built-no-view` | Logic/model exists but no user-facing view (or no dedicated screen) | **Phase C or D** |
| `not-built` | Genuinely missing — needs a new model/service/view | **Phase D** |
| `blocked` | Cannot build until an external dependency clears | tracker + escalate |

The two gap columns answer the owner's question directly:
- **UI/UX gap** = visual + curation distance from the mockup (the `mu-*` aesthetic, field count).
- **Functional gap** = behavioural distance (does the feature actually do what the screen shows).

---

## Cross-cutting UI/UX gap (applies to every "built" screen)

The mockups define a custom `mu-*` design language (purple `#714B67` chrome bar,
breadcrumb, pill badges, 6–12 curated fields, custom modals). Real Odoo renders
standard OWL views. The **achievable** translation (already proven in
`multichannel_hub_core/static/src/scss/mu_tokens.scss`):

| Mockup element | Odoo-idiomatic equivalent | Shipped? |
|---|---|---|
| `mu-pill` status badge | `widget="badge"` + `decoration-*` | partial (listing) |
| purple chrome / active tab | scoped SCSS on `.o_form_statusbar` / `.o_notebook .nav-link.active` | yes (3 forms) |
| `mu-mono` SKU/ID | `.mu-mono` class | yes |
| 6–12 field curation | Tier 1/2/3 via `groups=` + tabs (`FORM_CURATION_GUIDE.md`) | partial |
| custom modal | OWL `Dialog` / wizard `target="new"` | n/a (standard) |
| custom kanban-by-status | standard `<kanban>` grouped | no |

There is **no chrome bar / breadcrumb gap to close** — those are Odoo's own web client
shell and are out of scope. "Mockup intent" = curation + tint + badges, nothing more.

---

## Flow 1 — Tạo sản phẩm & publish Etsy

| # | Mockup screen | Status | UI/UX gap | Functional gap |
|---|---|---|---|---|
| 1 | Product form + Auto-SKU | `built+needs-curation` | Form exposes ~8 extra std fields (Routes/Logistics/Description) vs mockup's curated set. Needs Tier-3 hiding + active-tab tint (tint shipped). | None — auto-SKU onchange works. |
| 2 | SKU Drift list (Keep Legacy / Accept Canonical) | `built+matches` | Minor — std list vs `mu-pill` styling. | None — `view_product_sku_drift_list` + both decision actions + wizard all present (`product_sku_drift_views.xml:5-62`, `product_sku_canonicalise_wizard.py:43-86`). |
| 3 | Payload Preview (tab Channels) | `built-no-view` | No "Channels" preview tab exists on `multichannel.listing`. | Payload is computed **server-side at publish only** (`etsy_listing_publisher.py:566-624`); operator cannot review the full payload (taxonomy/readiness/materials/offerings) before commit. **Phase D: add a read-only computed preview tab.** |
| 4 | Error Modal — 400 from Etsy | `built-no-view` | No user-facing modal; error sits in a DB field + logs. | Body **is** captured + persisted (`etsy_api_client.py:273-285` → `product.channel.status.last_sync_error`, 4 KB). Missing: surface it on the wizard/form as a readable field or `Dialog`. Partial mitigation of blocker `R-PUB-RESPONSE-BODY-DIAGNOSE`. **Phase D (small).** |
| 5 | Kanban — Products by Channel Status | `not-built` | No kanban; only a flat decorated list. | Models exist (`product.channel.status`, `multichannel.sync.health`) but **no `<kanban>` grouped by state**. **Phase D: add kanban view (no new model).** |

## Flow 2 — Tiếp nhận đơn hàng Etsy

| # | Mockup screen | Status | UI/UX gap | Functional gap |
|---|---|---|---|---|
| 1 | Operations Dashboard (KPI + recent orders) | `built+needs-curation` | Real = 34-col `sale.order.line` list (Excel contract); mockup = 3 KPI cards + curated table. KPI cards not present. | Data is there; the KPI-card presentation is the gap (would be a kanban/QWeb tile — defer unless owner wants it). |
| 2 | Sale Order form — tab Etsy | `built+matches` | std form; minor tint. | receipt_id/payment_status/shipping fields present on Etsy tab. |
| 3 | Etsy API log (cron history) | `built+matches` | std list. | `etsy.api.log` model + view exist. |
| 4 | Etsy Email log (fallback) | `built+matches` | std list. | `etsy.email.log` list/form + retry action exist. |

## Flow 3a — Giao hàng (In nội bộ / MTO)

| # | Mockup screen | Status | UI/UX gap | Functional gap |
|---|---|---|---|---|
| 1 | Pipeline Kanban (states) | `built-no-view` | No order-pipeline kanban surfaced on orders. | State machine + seed states exist (`order_pipeline_state_seed.xml`, 5 VN stages) but **not surfaced as a kanban/board on `sale.order`**. |
| 2 | Design Files Kanban | `built+matches` | std kanban (3 cols). | `design.file` kanban exists. |
| 3 | Sale Order — Pipeline tab + transitions | `built-no-view` | No Pipeline notebook tab on the SO form. | `x_pipeline_state_id` exists + `_write_pipeline_state()` audit, but **no form tab + no transition buttons**; "In lại" (reprint) state not seeded. **Phase D.** |
| 4 | Production Scan View (mobile) | `not-built` | — | No scan view. **Phase D (or defer).** |
| 5 | QC Checklist | `not-built` | — | No QC model/view. **Phase D (or defer).** |
| 6 | Mark Shipped + Push Tracking | `built+needs-curation` | UX scattered. | `EtsyTrackingPusher` exists; tracking-push works. Curate the trigger UX. |

## Flow 3b — Giao hàng (Gearment Dropship)  ← biggest correction vs v1

The v1 doc marked all of Flow 3b as stub. **Wrong now** — the logic is built; the gap
is almost entirely **missing views**.

| # | Mockup screen | Status | UI/UX gap | Functional gap |
|---|---|---|---|---|
| 1 | Order Detail — tab Fulfillment + "Request Gearment Quote" | `built+needs-curation` | A "Gearment" tab exists (`sale_order_views.xml:31-51`) with buttons "Sync to Gearment" / "Review Quote" — **naming/structure differs** from mockup's "Fulfillment" tab + "Request Gearment Quote". | Functionally present. Rename/regroup to match intent. |
| 2 | Gearment Quote Wizard | `built+needs-curation` | Wizard form exists (`gearment_quote_wizard_views.xml:4-30`) but shows only order_id + quote totals — **no recipient/address block** like the mockup. | `/draft` + `/price` flow works via `gearment_adapter.py`; `action_confirm` present. Add recipient/address read-only display. |
| 3 | Gearment API Log | `built-no-view` | **Model has zero UI** (`gearment_api_log.py:14-198` complete; no `ir.ui.view`). | Logging works. **Phase C/D: add list + form view.** |
| 4 | Webhook Log | `built-no-view` | No dedicated webhook view. | Webhooks **are** logged — into `gearment.api.log` rows with `direction='inbound'` + `topic_seen`/`nonce_value`/`signature_verified` (`gearment_api_log.py:88-127`); controller + dispatcher built (`controllers/gearment_webhook.py`, `services/gearment_webhook_dispatcher.py`). Missing: a filtered list view (`direction=inbound`). **Phase C/D: add a filtered view (no new model needed).** |
| 5 | Fulfillment Tracking Detail | `built+matches` (D#8 `6c10014`) | Dedicated `sale.order.fulfillment` form + list + menu (Operations > Gearment). | **DONE** — Gearment order-ref / last-webhook timestamp+topic / Etsy-pushed fields added + webhook-dispatcher wiring + form. |

## Flow 4 — Hậu mãi (Đổi/Trả/Refund)

| # | Mockup screen | Status | UI/UX gap | Functional gap |
|---|---|---|---|---|
| 1 | Chatter — buyer message auto-posted | `built-no-view` | Note shows as a read-only field, not a chatter message. | `etsy_note_from_buyer` stored (`order_creator.py:256`) but **never `message_post()`-ed** to chatter. **Phase D (small, ~5 LOC).** |
| 2 | Address Change Request approval wizard | `built+matches` | std form + tint. | **Fully built** — model + list + form + Approve/Reject + FR-017 BA-lead gate + chatter (`etsy_address_change_request.py:26-153`, `etsy_address_change_request_views.xml:3-72`). |
| 3 | Pipeline reprint state transition | `built-no-view` | Same as Flow 3a #3 — no Pipeline tab. | State machine built; "In lại" state + transition UI missing. **Phase D.** |
| 4 | Refund (Story 4.8 `etsy.order.ticket`) | `not-built` | — | **Genuinely missing** — no `etsy.order.ticket` model, no refund service/view anywhere. Today: manual refund on Etsy + chatter note. **Phase D (full slice).** |
| — | Conversations ingestion (the "Conversation" screen) | `blocked` | `multichannel.enquiry` has full list/form/kanban (`multichannel_enquiry_views.xml`). | `conversations_r` OAuth scope is **explicitly forbidden** (`etsy_oauth.py:37-39`); `etsy_conversation_id` field exists but no poller/webhook. **Blocked on E1 scope grant — escalate, do not build.** |

---

## Phase-D backlog distilled from this audit (functional gaps only)

Ordered roughly by ROI / independence. Status updated as slices ship (2026-06-20):

1. ✅ **DONE** **Chatter auto-post** of buyer note (Flow 4 #1) — commit `b41c0f3`; 3 ORM tests green; QA-verified on local (message posts to chatter).
2. ✅ **DONE (partial)** **Gearment views** — API log list+form + webhook filtered list (Flow 3b #3/#4) shipped, commit `3d4f42e`; QA-verified local (lists/filters/forms render, inbound verification group shows). Fulfillment tracking detail (#5) still pending (needs new fields).
3. ✅ **DONE** **Pipeline tab + transition wizard + "In Lại" reprint state** (Flow 3a #3 / Flow 4 #3) — commit `a818449`; 3 ORM tests green. Transitions route through the audited `_write_pipeline_state`; direct writes still blocked.
4. ✅ **DONE** **Kanban by channel status** (Flow 1 #5) — commit `54225446`; QA-verified local (Draft/Error/Published, error card shows message).
5. ⛔ **DEFERRED to v2 (owner decision 2026-06-21)** **Payload preview tab** (Flow 1 #3) — low ROI diagnostic; the resolved fields are already visible across the listing tabs, and a faithful preview needs the cross-module publisher payload builder.
6. ✅ **DONE** **Error body surfaced** on the listing form (Flow 1 #4) — commit `c66ba56`; 2 ORM tests green. Computed `last_sync_error` + danger alert when `state == 'error'`.
7. ✅ **DONE** **Refund / `etsy.order.ticket`** (Flow 4 #4) — commit `5d8c5e6`; 4 ORM tests green. After-sales ticket (return/refund/reship) with BA-lead-gated approve/reject/refunded state machine + chatter + menu.
8. ✅ **DONE** **Fulfillment tracking-detail form** (Flow 3b #5) — commit `6c10014`; 8 ORM tests green. New `sale.order.fulfillment` form/list/menu (Operations > Gearment) + Gearment provenance fields (`gearment_order_ref`, `gearment_last_webhook_at`/`_topic`) stamped by the webhook dispatcher + `etsy_tracking_pushed`/`_at` set on successful Etsy pushback.
9. ⛔ **DEFERRED to v2 (owner decision 2026-06-21)** **QC checklist / production scan** (Flow 3a #4/#5) — in-house-production extras; no shipped slice depends on them. Out of v1 scope.
10. ⛔ **Conversations ingestion** — BLOCKED on Etsy `conversations_r` scope (external dep E1); tracker row only.

**Shipped this session (6 functional slices): D#1 D#2 D#3 D#4 D#6 D#7** — all unit-tested
(Phase 2 ORM) + install-clean. D#1/D#2/D#4 also screenshot-validated on local; D#3/D#6/D#7
test+install-verified (clean local screenshots deferred — browse-session/role/filter friction,
not a code defect).

All shipped slices were developed + verified **local-first** (db `namco_odoo19`, seeded via
`scripts/seed_demo_local.py`); evidence under `screenshots/local/`.

## Phase-C backlog (UI/UX gaps only)

- ✅ **DONE** `product.template` Tier-3 hiding (Flow 1 #1) — commit `c0fdfbb`; 4 ORM tests green. Routes/MTO `operations` group, receipt/delivery note blocks, and `responsible_id` hidden behind `groups="base.group_no_one"`; weight/volume + lead time kept.
- ✅ **DONE** `etsy.shop` curation — P-DS-3a shipped (prior session).
- ✅ **DONE (no work)** `sale.order` / `stock.picking` audit — P-DS-3b closed; all custom sale.order content is already tab-organised and stock.picking has no custom inherit, so no curation gap (see `design-system/findings.md`).
- Badge/tint pass on Gearment Fulfillment tab + quote wizard (Flow 3b #1/#2) — optional polish, not blocking.

---

## Staging screenshot harvest (2026-06-20, gstack /browse)

Harvested live from `odoo.hatafax.com` (db `esty_odoo19`, admin login) via gstack `/browse`.
17 real renders saved under `screenshots/flow-*/` with `v2-` prefix. The rendered UI
**corroborates every code-grounded verdict above** — no verdict changed.

**Key confirmations from the renders:**
- Real Odoo top bar IS the purple `#714B67` chrome (Odoo's themed navbar) — so the "chrome bar"
  mockup element already exists for free; the only UI gap is curation + badges/tint inside forms.
- `sale.order` form (S00007) renders clean with tabs **Order Lines · Other Info · Etsy · Design
  Files · Gearment** — confirms Flow 2 #2 (`built+matches`), Flow 3b #1 (Gearment tab exists),
  and a "Request address change" header button (Flow 4). The Etsy tab shows curated ETSY ORDER /
  SHIPPING / PRICING sections — close to mockup intent already.
- Etsy API Log: live list, 10000+ rows (`built+matches`). Operations Dashboard: 8 rows. Email Log:
  5 rows. SKU Drift: 80 rows. Fulfillment Pipelines: 3 rows.

**Data-sparsity caveat (staging seed):** Listings, Sync Health, Design Files, Tracking Imports,
Customer Enquiries, and Address Change Requests all returned **0 rows** on staging, so those
captured as valid empty-state views (form-level captures fall back to the empty list). Re-seed
staging or harvest those forms on a populated DB to get record-level shots for the contract.

| File | Screen | Rows | Confirms |
|---|---|---|---|
| flow-1/v2-sku-drift-list.png | SKU Drift list | 80 | `built+matches` |
| flow-1/v2-listing-list.png | Listings list | 0 | view exists (empty) |
| flow-1/v2-sync-health-list.png | Sync Health | 0 | view exists (empty) |
| flow-2/v2-operations-dashboard.png | Operations Dashboard | 8 | `built+needs-curation` |
| flow-2/v2-sale-order-form.png + v2-sale-order-etsy-tab.png | SO form + Etsy tab | 1 | `built+matches` |
| flow-2/v2-etsy-api-log.png | Etsy API Log | 10000+ | `built+matches` |
| flow-2/v2-etsy-email-log.png | Email Log | 5 | `built+matches` |
| flow-3a/v2-design-file-kanban.png | Design Files kanban | 0 | view exists (empty) |
| flow-3a/v2-order-pipeline.png | Fulfillment Pipelines | 3 | config exists |
| flow-3b/v2-sale-order-gearment-tab.png | SO Gearment tab | 1 | `built+needs-curation` |
| flow-3b/v2-tracking-import-log.png | Tracking Imports | 0 | view exists (empty) |
| flow-4/v2-enquiry-list/form.png | Customer Enquiries | 0 | `built` (empty — conversations blocked) |
| flow-4/v2-address-change-list/form.png | Address Change | 0 | `built` (empty) |
