# Hatafa Etsy ERP — Delivery Contract v1.0 (DRAFT — not yet for sign-off)

**Prepared:** 2026-06-20 · **Branch:** `feature/006-master-plan-coding` · **Staging:** `esty_odoo19` (129.150.63.207)

This document is the binding acceptance record for **Hatafa Etsy ERP v1.0** (Odoo 19 CE +
`multichannel_hub_core` / `multichannel_hub_fulfillment` / `etsy_integration`). It ties together
the two halves of the contract — the **UI** the system is promised to look like, and the
**system-functionals** it is promised to do — modelled on the openeducat/TFV delivery contract.

**Status: DRAFT.** It is published now as the scoping spine for the remaining work; the
per-flow verdicts below are the **code-grounded** state from `COMPARISON_MOCKUP_VS_ACTUAL_v2.md`
(2026-06-20). It becomes sign-off-ready when the §3 UAT gates pass and the §2 UI verdicts reach
`✓ match` or an owner-accepted drift.

---

## 1. What is being accepted

A single Odoo 19 CE deployment covering the Hatafa Etsy operation end-to-end across **5 business
flows** (+ 5 role personas in `docs/owner/business-flows/`):

1. **Flow 1** — Tạo sản phẩm & publish Etsy (product → auto-SKU → Etsy listing)
2. **Flow 2** — Tiếp nhận đơn hàng Etsy (API webhook + email fallback ingestion)
3. **Flow 3a** — Giao hàng / In nội bộ (MTO manufacturing)
4. **Flow 3b** — Giao hàng / Gearment dropship (POD vendor)
5. **Flow 4** — Hậu mãi (đổi/trả/refund, address change, reprint)

**Promise:** the delivered screens look and behave like the "Màn hình Odoo" mockups embedded in
`docs/owner/business-flows/flow-*.html`, anchored to the design tokens in
`docs/design/HATAFA.design.md` (primary `#714B67`), delivered through **standard Odoo views**
(mockup _intent_, not pixel reproduction — owner decision 2026-06-20).

---

## 2. UI contract — promised vs delivered (per the v2 audit)

Verdicts are code-grounded (`COMPARISON_MOCKUP_VS_ACTUAL_v2.md`). Staging screenshots are a
pending Phase-A step; this table is the source of truth until they land.

| Flow | Screens | ✓ match | needs-curation (Phase C) | no-view/not-built (Phase D) | blocked |
|---|---|---|---|---|---|
| 1 — Tạo sản phẩm | 5 | 1 (SKU drift) | 1 (product form) | 3 (payload preview, error modal, kanban) | — |
| 2 — Nhận đơn | 4 | 3 | 1 (ops dashboard KPI cards) | — | — |
| 3a — In nội bộ | 6 | 1 (design kanban) | 2 (mark-shipped, pipeline kanban) | 3 (pipeline tab, QC, scan) | — |
| 3b — Gearment | 5 | 0 | 2 (fulfillment tab, quote wizard) | 3 (api-log view, webhook view, tracking detail) | — |
| 4 — Hậu mãi | 5 | 1 (address change) | — | 3 (chatter post, pipeline tab, refund) | 1 (conversations) |

**Headline correction vs the archived v1 audit:** Flow 3b (Gearment) is **not** a stub — quote
wizard, webhook controller, adapter, and dispatcher are all built (`multichannel_hub_fulfillment`).
The gap there is **missing views over working models**, not missing logic.

**Shipped since this snapshot (2026-06-21), all local-screenshot-verified:**
- Flow 1 product form — **curated** (Phase C `c0fdfbb`): Routes/MTO, Responsible, receipt/delivery
  notes hidden; Weight/Volume/Lead Time kept. Moves from `needs-curation` → `✓ match`.
- Flow 3a pipeline tab + transition wizard — **fully working** (D#3 `a818449` + wizard fix
  `b02af9d`). Moves from `no-view` → `✓ match`.
- Flow 3b fulfillment tracking detail — **built** (D#8 `6c10014`). Moves from `no-view` → `✓ match`.

**Proof:** 17 live staging renders harvested 2026-06-20 via gstack `/browse`
(`screenshots/flow-*/v2-*.png`), catalogued in `COMPARISON_MOCKUP_VS_ACTUAL_v2.md`
§"Staging screenshot harvest". They corroborate every code-grounded verdict; the real top bar
is already the purple `#714B67` chrome, and the `sale.order` Etsy tab renders close to mockup
intent. Record-level shots for listings/enquiries/design-files await a populated staging seed
(those tables are empty on staging today).

---

## 3. System-functional contract — capability + acceptance

**Promise:** every flow traces to working code, and the five UAT gates pass.

**Functional coverage matrix** (flow → key requirement/slice → shipped code → verdict):

| Flow | Requirement | Shipped code (evidence) | Verdict |
|---|---|---|---|
| 1 | Auto-SKU on category/variant onchange | `mhc.sku.family` + product onchange | ✓ working |
| 1 | Publish draft to Etsy (createListing) | `etsy_listing_publisher.py:566-624` | ✓ working |
| 1 | Capture + **surface** Etsy error body | `etsy_api_client.py` → `last_sync_error`; listing form alert (**D#6** `c66ba56`) | ✓ working |
| 1 | Products-by-channel-status kanban | `product.channel.status` kanban (**D#4** `54225446`) | ✓ working |
| 1 | Curated product form (Tier-3 hide) | `groups=base.group_no_one` on Routes/MTO + notes + Responsible (**Phase C** `c0fdfbb`) | ✓ working |
| 2 | API ingestion (cron) + dedupe | `etsy.api.log`, order syncer cron | ✓ working |
| 2 | Email fallback parse | `services/email_parser.py`, `etsy.email.log` | ✓ working |
| 3a | Pipeline state machine + audit + **UI** | `_write_pipeline_state()`; Pipeline tab + transition wizard + "In Lại" (**D#3** `a818449`); wizard New-State seed fix (`b02af9d`) | ✓ working (verified live) |
| 3a | Tracking push to Etsy | `EtsyTrackingPusher` | ✓ working |
| 3b | Gearment quote (/draft + /price) | `gearment_adapter.py`, `gearment_quote_wizard.py` | ✓ working |
| 3b | Gearment webhook (HMAC + nonce) + **views** | dispatcher + API Log / Webhook Log views (**D#2** `3d4f42e`) | ✓ working |
| 3b | Fulfillment Tracking Detail + provenance | `sale.order.fulfillment` form/list + Gearment/Etsy-pushed fields + dispatcher wiring (**D#8** `6c10014`) | ✓ working |
| 4 | Address change approval (FR-017 gate) | `etsy_address_change_request.py:26-153` | ✓ working |
| 4 | Buyer message → chatter | auto-posted on create (**D#1** `b41c0f3`) | ✓ working |
| 4 | Refund (`etsy.order.ticket`) | after-sales ticket + BA-lead state machine (**D#7** `5d8c5e6`) | ✓ working |
| 4 | Conversations ingestion | `etsy_conversation_id` field only | ⛔ blocked (`conversations_r`) |

> **Verification:** Phase-2 ORM sweep across the session's changed classes — **28 tests, 0 failed,
> 0 error** (pipeline wizard 4 + product curation 4 + fulfillment detail 8 + webhook dispatcher 12),
> on top of the earlier 12-test functional sweep; full stack installs
> `-u …core,…fulfillment,…etsy_integration --stop-after-init` exit 0. Developed + screenshot-verified
> local-first on `namco_odoo19`. **Full regression sweep DONE (2026-06-21):** combined
> `-u …core,…fulfillment,…etsy_integration --test-enable` = **1879 tests, 0 failed, 0 error**.
> The sweep surfaced ~46 PRE-EXISTING latent failures (none caused by this session's Phase C /
> D#3 / D#8 changes) — repaired across 3 commits (etsy_integration 27, multichannel_hub_core 13,
> multichannel_hub_fulfillment 6): C-ESY-003 shop fixtures missing `etsy_api_shop_id`, test-isolation
> hardening for ambient dev-DB data, stale Selection/seed assertions, plus two real code fixes
> (wizard double-create UniqueViolation; gearment audit-log fresh-cursor fallback). One open finding:
> the listing-backfill wizard leaves a *matched* (live) listing's channel status `draft` (its
> `state='published'` create path is dead because `_sync_channel_statuses` seeds a draft first) —
> published-vs-draft intent gap, flagged for owner review, not changed.

**UAT gates (one per flow) — to pass before sign-off:**

| Gate | What | Result |
|---|---|---|
| UAT-1 | Create product → auto-SKU → publish draft to Etsy → listing live | ☐ pending re-run |
| UAT-2 | Etsy order ingested (API) → dedupe → sale.order created | ☐ pending re-run |
| UAT-3 | MTO order → pipeline states → tracking pushed to Etsy | ☐ pending walkthrough (pipeline tab + Change State wizard verified live — D#3 + fix `b02af9d`) |
| UAT-4 | Dropship order → Gearment quote → confirm → webhook → tracking to Etsy | ☐ pending walkthrough (Gearment + fulfillment-detail views now built — D#2/D#8) |
| UAT-5 | After-sales: address change approved + reprint; refund path | ☐ pending walkthrough (refund ticket now built — D#7) |

---

## 4. Deferrals / blocked (v2 or external dependency)

- **Refund / `etsy.order.ticket`** (Flow 4 #4) — ✅ **now built** (D#7 `5d8c5e6`); no longer a
  deferral. After-sales return/refund/reship ticket with BA-lead-gated state machine + chatter.
- **Payload preview tab** (Flow 1 #3) — **DEFERRED to v2 (owner decision 2026-06-21)**. Low-ROI
  diagnostic; resolved fields already visible across the listing tabs.
- **QC checklist + production scan view** (Flow 3a #4/#5) — **DEFERRED to v2 (owner decision
  2026-06-21)**. In-house-production extras; no shipped slice depends on them.
- **Conversations ingestion** (Flow 4) — **blocked** on Etsy `conversations_r` OAuth scope, which
  is explicitly forbidden in `etsy_oauth.py:37-39` pending E1 approval (see memory
  `project_external_deps_2026_04_27`). Tracker row only; do not build.
- **Error-body modal** (Flow 1 #4) — ✅ surfaced on the listing form (D#6 `c66ba56`); full
  response-body diagnosis still depends on `R-PUB-RESPONSE-BODY-DIAGNOSE`.

---

## 5. Evidence index

- `docs/owner/business-flows/COMPARISON_MOCKUP_VS_ACTUAL_v2.md` — code-grounded gap matrix (this contract's spine).
- `docs/owner/business-flows/flow-*.html` — the **UI contract** mockups (intent reference).
- `docs/design/HATAFA.design.md` — design-token contract.
- `docs/owner/design-system/{MU_SYSTEM.md, FORM_CURATION_GUIDE.md, PHASE_3_SCOPE.md, findings.md}` — design-system backport record.
- `screenshots/flow-*/` — staging screenshots (pending re-harvest).
- `docs/archive/2026-06-20/COMPARISON_MOCKUP_VS_ACTUAL.md` — superseded v1 audit.

---

## 6. Owner sign-off (gated)

> **Not yet signable.** Prerequisites: §3 UAT-1..5 green, §2 verdicts at `✓ match`/accepted-drift,
> staging screenshots harvested. The Phase C (UI) + Phase D (functional) slices in the v2 audit
> close the remaining items.

By signing, the owner will accept that Hatafa Etsy ERP v1.0 delivers **one dual contract**:
- **UI contract** — the `flow-*.html` mockups, frozen at sign-off.
- **System-functional contract** — the §3 coverage matrix + UAT-1..5 gates.

| Field | Value |
|---|---|
| Reviewed promised-vs-delivered screenshots | ☐ |
| Walkthrough: Flow 1 · 2 · 3a · 3b · 4 | ☐ |
| Refund deferral to v2 confirmed | ☐ |
| Conversations (conversations_r) block acknowledged | ☐ |
| QC/scan scope decision recorded | ☐ |
| **Owner name / title** | __________________________ |
| **Signature** | __________________________ |
| **Date** | __________________________ |
