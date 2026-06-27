# Gap Matrix — Promised (contract) vs Built (code) — refreshed 2026-06-27

Source of truth feeding `mismatch-report.html` + `jira-sprint-draft.md`.
Independently re-verified against current `custom_addons/` (HEAD `d3961fc1a5d`), resolving
two agent discrepancies by direct grep. Supersedes the 2026-06-20 snapshot in
`docs/owner/business-flows/COMPARISON_MOCKUP_VS_ACTUAL_v2.md` (which is itself accurate but a
week stale; D#1–D#8 + Phase C all confirmed still in place, plus post-snapshot ESTY-205/206/207).

Status legend: **KEPT** (code+entry-point confirmed) · **PARTIAL** (works but a promised piece
missing) · **UNWIRED** (backend exists, no usable view/board) · **MISSING** (not built) ·
**BLOCKED** (external dep) · **DEFERRED** (owner moved to v2) · **DOC-DRIFT** (doc promises
something changed/absent).

UI evidence column: `browse:<screen>` = confirmed live on `namco_odoo19` (localhost:8169) this
pass; `staging-2026-06-20` = from prior 17-shot harvest; `pending` = not yet re-shot.

---

## A. FEATURE / FUNCTIONAL matrix

### Flow 1 — Tạo sản phẩm & publish Etsy
| Promise (source) | Status | Code evidence | UI entry | Sev |
|---|---|---|---|---|
| Auto-SKU on category/variant onchange | KEPT | `multichannel_hub_core/models/product_template.py:248-300` (`_onchange_auto_fill_default_code` + `sku_grammar_v2`) | product form | — |
| Publish draft to Etsy (createListing) | KEPT | `product_product.py:55-69` + `multichannel_listing.py:231-253` buttons `action_open_etsy_publish_wizard` → `wizards/etsy_publish_wizard.py:41` → `services/etsy_listing_publisher.py` | "Publish to Etsy" button on product + listing form | — |
| SKU Drift list + Keep-Legacy / Accept-Canonical | KEPT | `views/product_sku_drift_views.xml:5-53` + `wizards/product_sku_canonicalise_wizard.py:59-86` | SKU Drift list | — |
| Capture + **surface** Etsy error body (D#6) | KEPT | computed `last_sync_error` `multichannel_listing.py:137-142`; danger alert `multichannel_listing_views.xml:75-83` | listing form (state=error) | — |
| Products-by-Channel-Status kanban (D#4) | KEPT | `<kanban default_group_by="state">` `product_channel_status_views.xml:30-96` + menu | Operations > Channel Status | — |
| FX VND→shop-currency preview | KEPT | `multichannel_listing.py:44-127` (`display_price_in_shop_currency`, `_convert`) | listing form | — |
| 3-tier Etsy defaults (taxonomy/shipping/who-when) | KEPT | `product_template.py:97-135`, `etsy_shop.py:87-129`, `multichannel_listing.py:128-181` | product/listing/shop forms | — |
| **Payload preview tab** (Flow 1 #3) | DEFERRED | none (confirmed absent) | none | Low — owner deferred to v2 (CONTRACT §4) |

### Flow 2 — Tiếp nhận đơn hàng Etsy
| Promise | Status | Code evidence | UI entry | Sev |
|---|---|---|---|---|
| API ingestion cron + dedupe | KEPT | `data/ir_cron_data.xml:13-21` (`cron_etsy_order_sync`, 5 min) + `etsy.api.log` | cron | — |
| Email fallback parse cron | KEPT | `data/ir_cron_data.xml:4-11` (10 min) + `services/email_parser.py` + `etsy.email.log` | cron | — |
| Etsy API Log + Email Log views | KEPT | `etsy_api_log_views.xml`, `etsy_email_log_views.xml` + menus | Etsy > API Log / Email Log | — |
| sale.order Etsy tab (receipt/payment/shipping) | KEPT | `etsy_integration/views/sale_order_views.xml:54-107` | Etsy tab | — |
| Manual "Pull Etsy Orders" button (ESTY-207) | KEPT | OWL CP patch `static/src/views/etsy_pull_list/*` + `sale_order_views.xml:138-153` | quotation list control panel | — |
| Per-user Etsy shop scoping (ESTY-205) | KEPT | `security/etsy_security.xml:28-37` ir.rule + `etsy_shop.py:17-23` `user_id` | record rule | — |
| **Operations Dashboard KPI summary cards** | **PARTIAL** | data present; `operations_dashboard_views.xml:21-125` is a plain 34-col `<list>` — **zero KPI/tile markup** | Operations > Operations Dashboard | **High** — promised in mockup + every role doc; most-seen screen |

### Flow 3a — Giao hàng / In nội bộ (MTO)
| Promise | Status | Code evidence | UI entry | Sev |
|---|---|---|---|---|
| Pipeline state machine + audit | KEPT | `multichannel_hub_core/models/sale_order.py:221-307` (`_write_pipeline_state`, write-guard); 13 states `order_pipeline_state_seed.xml` | — | — |
| Pipeline tab + transition wizard + "In Lại" reprint (D#3) | KEPT | tab `sale_order_form.xml:58-87`; wizard `order_pipeline_transition_wizard.py` (default_get seeds pipeline_id, fix `b02af9d`); reprint state `order_pipeline_state_seed.xml:69-72` | Pipeline tab > Change State | — |
| Design Files kanban (3 cols) | KEPT | `design_file_views.xml` `<kanban default_group_by="state">` | Design Files | — |
| Tracking push to Etsy | KEPT | `services/etsy_tracking_pusher.py` + `ir_cron_etsy_tracking_push` | cron | — |
| GKE tracking import + carrier auto-detect | KEPT | `multichannel_hub_fulfillment/views/tracking_import_views.xml` + `services/carrier_detector.py` + `shipping_carrier_data.xml` | Operations > Tracking Import | — |
| Mark-Shipped + push tracking | KEPT (curation) | `sale_order.py:520-529` `action_bulk_mark_shipped` (server action) | dashboard bulk action | Low — UX scattered |
| **Pipeline KANBAN board (grouped by state)** | **UNWIRED** | states + machine + tab exist; **no `<kanban>` grouped by pipeline state on orders** | none | **Med-High** — Production role doc promises kanban transitions |
| **QC checklist + production scan** | DEFERRED | none (confirmed absent) | none | Low — owner deferred to v2 |

### Flow 3b — Giao hàng / Gearment dropship
| Promise | Status | Code evidence | UI entry | Sev |
|---|---|---|---|---|
| Gearment quote (/draft + /price) + confirm gate | KEPT | `services/gearment_adapter.py:119-365`; wizard + `action_confirm` gated `group_ba_shipping` | Gearment tab > Review Quote | — |
| Gearment webhook (HMAC+nonce) + dispatcher | KEPT | `controllers/gearment_webhook.py` + `services/gearment_webhook_dispatcher.py` | `/gearment/webhook` | — |
| Gearment API Log + Webhook (inbound) view (D#2) | KEPT | `gearment_api_log_views.xml:1-143` (incl. `direction=inbound` filter) | Operations > Gearment | — |
| Fulfillment Tracking Detail + provenance (D#8) | KEPT | `sale_order_fulfillment_views.xml:3-106`; fields `gearment_order_ref`, `gearment_last_webhook_at/_topic`, `etsy_tracking_pushed/_at` | Operations > Gearment > Fulfillment Tracking | — |
| Gearment tab naming/structure | KEPT (curation) | `multichannel_hub_fulfillment/views/sale_order_views.xml:10-54` tab "Gearment" + Sync/Review buttons | Gearment tab | Low-Med — mockup wants "Fulfillment" tab + "Request Gearment Quote" label |
| Quote wizard recipient/address block | KEPT (curation) | `gearment_quote_wizard_views.xml:8-20` shows order_id + totals only | wizard | Low-Med — add read-only recipient/address |

### Flow 4 — Hậu mãi
| Promise | Status | Code evidence | UI entry | Sev |
|---|---|---|---|---|
| Buyer note → chatter auto-post (D#1) | KEPT | `etsy_integration/models/sale_order.py:195-201` `message_post` (both email + API paths) | order chatter | — |
| Address change request + approve/reject + FR-017 gate + lock | KEPT | `etsy_address_change_request.py:26-228`; views `:1-73`; header btn `sale_order_views.xml:30-34`; `_ADDRESS_LOCK_FIELDS` | header "Request address change" | — |
| Reprint ("In Lại") transition | KEPT | reprint state seeded + reachable via D#3 wizard (see Flow 3a) | Pipeline tab | — |
| Refund ticket `etsy.order.ticket` (D#7) | PARTIAL | `etsy_order_ticket.py:20-91` model + state machine (draft/approved/rejected/refunded) + BA-lead gate + menu; **no Etsy refund API call — manual only** | Etsy > After-Sales | Med — automation deferred; refund still done by hand on Etsy |
| **Conversations ingestion** | BLOCKED | `etsy_oauth.py:53` `_FORBIDDEN_SCOPES={'conversations_r'}`; `etsy_conversation_id` field only, no poller | none | External (E1) — do not build |

---

## B. UI / UX matrix

| Area | Promise / mockup intent | Status | Evidence | Sev |
|---|---|---|---|---|
| Operations Dashboard | 3 KPI cards + curated ~10-col table | PARTIAL | 34-col plain list, no KPI band `operations_dashboard_views.xml:21-125` | **High** |
| Dashboard density | curated 6–12 fields per screen | PARTIAL | dashboard 34 cols; product form curated via Tier-3 (Phase C `c0fdfbb`) | Med |
| Pipeline board | kanban by fulfillment state | UNWIRED | no board view | Med-High |
| Brand tint `#714B67` | purple chrome + active-tab tint | KEPT (partial) | Odoo navbar already purple; scoped SCSS on 3 forms `mu_tokens.scss`; **reuse `muk_web_colors` to finish** | Low |
| Status badges (`mu-pill`) | pill badges + `decoration-*` | PARTIAL | listing only | Low |
| Navigation / role landing | per-role home | DOC-DRIFT | menu split Etsy vs Operations; **no role landing**; `muk_web_appsbar` sidebar would fix | Med |
| Gearment tab / quote wizard | "Fulfillment" tab + recipient block | KEPT (curation) | see Flow 3b | Low-Med |
| Wizards polish | clean modals | KEPT | standard; `muk_web_dialog` optional polish | Low |

---

## C. Cross-cutting / roles / reporting

| Item | Status | Evidence | Sev |
|---|---|---|---|
| Roles BA Lead / BA User / BA Manager / Marketing / Production / Shipping | KEPT | `multichannel_hub_security.xml:10-53` + `multichannel_hub_fulfillment` `group_ba_shipping` | — |
| **RD role group** (`group_rd`) | MISSING | role doc `role-4-rd.html` exists; **no `group_rd`** | Low-Med — RD has no group/landing |
| **PD role group** (`group_pd`) | MISSING | role doc `role-5-pd.html` exists; **no `group_pd`** (PD work maps to production/marketing today) | Low-Med |
| **Price-Control / anomaly dashboard** (RD, Story 6.5) | MISSING | not built; `role-4-rd.html` marks "🟥 Trong thiết kế" | Med — RD role has no functional landing |
| Sync-health KPI tile | PARTIAL | models + list views exist (`etsy_sync_health_views.xml`, `multichannel_sync_health_views.xml`); **no dashboard tile** | Low |
| **Listing-backfill published-vs-draft bug** | BUG | `etsy_listing_backfill_wizard.py:79-92` sets `state='published'` but `product_template.py:370-373` `_sync_channel_statuses` seeds a draft row first; idempotent check then skips → matched live listing stays `draft` | Med — real defect, flagged in CONTRACT §3 footnote |

---

## D. Reuse opportunity (Standard-Odoo-First) — muk_web bundle

Found in `openeducat_erp19/custom_addons/` — all **19.0.x, LGPL-3, CE, no Enterprise dep**:
`muk_web_theme` (umbrella) ← `muk_web_appsbar` (sidebar nav), `muk_web_colors` (brand palette),
`muk_web_chatter`, `muk_web_dialog`, `muk_web_group`, `muk_web_refresh` (auto/manual view refresh).
Reuse path: copy into `odoo19_esty/custom_addons/` (or share addons-path). Directly closes the
brand-tint, role-nav, and live-dashboard-refresh gaps without custom SCSS — see UI/UX proposal.

---

## E. Headline summary (counts)

- KEPT: ~30 capabilities (all 5 flows trace to working, entry-pointed code).
- PARTIAL: 4 (Ops Dashboard KPI cards · refund API · sync-health tile · dashboard density).
- UNWIRED: 1 (pipeline kanban board).
- MISSING: 3 (RD price dashboard · group_rd · group_pd).
- BUG: 1 (listing-backfill draft clobber).
- DEFERRED (owner→v2): 2 (payload preview · QC/scan).
- BLOCKED (external E1): 1 (conversations ingestion).

**Verdict:** the system keeps the large majority of the functional contract end-to-end. The
*felt* gap is concentrated in **UI/UX presentation** (no KPI band, no pipeline board, nav/role
landing) — high daily visibility, low build cost — plus a handful of small functional items
(refund automation, RD dashboard, one backfill bug) and one external block.
