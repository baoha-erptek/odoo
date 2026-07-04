# Etsy Channel Requirements

**Title:** Etsy Shop Management, OAuth, Order Ingestion, and Listing Sync  
**Date:** 2026-07-03  
**Status:** Draft-for-owner-review  
**Source:** Specs 001, 002, 005, 011, ADRs 008/008a.

---

## Scope

This section covers:
- Etsy shop configuration and authentication (OAuth2 PKCE)
- Order ingestion via Etsy API v3 (primary) and email (fallback)
- Listing sync and taxonomy mapping
- Shipping profile and currency management
- Channel-specific data fields on sale.order

---

## Requirements (SRS-ETSY-01 through SRS-ETSY-14)

### SRS-ETSY-01: Etsy Shop Configuration & OAuth

| Property | Detail |
|----------|--------|
| **Statement** | System shall support multiple Etsy seller shops. Each shop is configured with OAuth2 credentials (access token, refresh token, expiration) and a canonical shop ID (`etsy_api_shop_id`). |
| **Rationale** | Multi-shop architecture allows same Odoo instance to manage multiple seller accounts with isolated order streams. |
| **Origin Spec(s)** | Spec 001 US3, Spec 005 P0-15 (OAuth PKCE flow) |
| **Implementing Module + Model** | `etsy_integration` / `etsy.shop` (fields: name, active, user_id, etsy_api_shop_id, etsy_oauth_access_token, etsy_oauth_refresh_token, etsy_oauth_token_expires_at) |
| **Status** | **Shipped** — Model instantiated; OAuth form view with "Test Connection" button (`views/etsy_shop_views.xml`); `action_test_connection()` on `etsy.shop` (`models/etsy_shop.py`) exercises the configured source (API client / gmail client). |

---

### SRS-ETSY-02: OAuth2 Token Refresh & Access Token Management

| Property | Detail |
|----------|--------|
| **Statement** | System shall automatically refresh expired Etsy access tokens using the stored refresh token and update `etsy_oauth_token_expires_at`. Failed refresh attempts shall be logged and trigger a mail.activity warning to the shop owner. |
| **Rationale** | Prevents order ingest gaps due to token expiry; automatic recovery reduces manual intervention. |
| **Origin Spec(s)** | Spec 005 P0-15 (OAuth PKCE); Spec 004 P-HEALTH (sync health monitoring) |
| **Implementing Module + Model** | `etsy_integration` / `services/etsy_api_client.py` (401-triggered + proactive refresh) + `services/etsy_oauth.py` (`refresh_access_token`) |
| **Status** | **Shipped (in the API client, not a cron)** — `EtsyApiClient` refreshes reactively on 401 (refresh via `etsy_oauth.refresh_access_token`, persist new tokens on `etsy.shop` with `sudo()`, retry once) and proactively when `etsy_oauth_token_expires_at` is within 60 seconds of expiry. There is no separate refresh cron — refresh happens inline per request, which covers the 60-min token lifetime. **Not implemented:** mail.activity warning to the shop owner on failed refresh (refresh failure raises and surfaces via sync health / API log instead). |

---

### SRS-ETSY-03: Email-Based Order Fallback (ADR-008a)

| Property | Detail |
|----------|--------|
| **Statement** | If Etsy API order fetch fails after 5 consecutive retries, system shall automatically switch to email-based order ingestion (Gmail labels) as mandatory fallback. Switch-back to API occurs after 3 consecutive successful API syncs. |
| **Rationale** | API outages or scope limitations do not block order visibility; email remains legal mandatory backup. |
| **Origin Spec(s)** | ADR-008a (email-as-mandatory-backup); Spec 001 US1 (email parser) |
| **Implementing Module + Model** | `etsy_integration` / `etsy.shop` (fields: active_source, sync_mode, health_check_consecutive_failures, recovery_probe_consecutive_successes) |
| **Status** | **Partial** — Data model fields (active_source, health_check_consecutive_failures, recovery_probe_consecutive_successes) exist but state machine logic unimplemented. No failover state-machine method exists in models/etsy_shop.py (the `etsy.shop.source.change.log` model already defines 'auto-failover'/'recovery-probe' reasons for when it lands). Email parser (services/email_parser.py) parses 34 fields. Failover state transitions missing. Tests: test_etsy_order_sync.py requires implementation. |

---

### SRS-ETSY-04: Etsy API Order Ingestion (Spec 005, Primary)

| Property | Detail |
|----------|--------|
| **Statement** | System shall fetch new Etsy receipts from `GET /shops/{shop_id}/receipts` every 5 minutes (configurable). For each new receipt, create a sale.order record with etsy_order_id, etsy_transaction_id, line items, customer, pricing, and shipping metadata. Duplicates (by etsy_transaction_id) shall be skipped. |
| **Rationale** | Real-time order visibility; API primary source provides faster integration than email polling. |
| **Origin Spec(s)** | Spec 005 P0-15 (API-first pivot), Spec 001 US1 (order ingest), ADR-008 (email-vs-API trade-off) |
| **Implementing Module + Model** | `etsy_integration` / `sale.order` (fields: etsy_order_id, etsy_transaction_id, etsy_shop_id, etsy_shipping_cost, personalization_text, gift_message) |
| **Status** | **Shipped** — Order syncer (`etsy_integration/services/etsy_order_syncer.py`, `sync_shop_orders(shop)`) fetches receipts and creates sale.order via the order-creator service; the cron `cron_etsy_order_sync` (`data/ir_cron_data.xml`, 5-minute interval) loops active API-source shops. Tests: order-sync suites under `etsy_integration/tests/`. Staging verified with pilot shop orders. |

---

### SRS-ETSY-05: Email-Based Order Fallback (Legacy, Spec 001)

| Property | Detail |
|----------|--------|
| **Statement** | System shall parse Etsy HTML emails from Gmail labels (e.g., "etsy-orders") every 10 minutes. Extract 34 fields (order ID, customer, items, shipping, etc.) via regex. Create sale.order records. Handle parse failures with automatic retry logic and activity alerts. |
| **Rationale** | Historically worked before API; mandatory fallback if API unavailable; legacy email queue. |
| **Origin Spec(s)** | Spec 001 US1, ADR-008a |
| **Implementing Module + Model** | `etsy_integration` / `etsy.email.log` (fields: gmail_message_id, parse_status, error_msg, created_at, retry_count) |
| **Status** | **Shipped** — Email parser (`services/email_parser.py`) extracts the full field set via regex. Gmail client (services/gmail_client.py) fetches emails via API. Cron job (data/ir_cron_data.xml line 8). Tests: test_email_parser.py (all 34 fields, edge cases, encoding). Staging emails parsed successfully. In production: 17,659 historical orders ingested via email (2025-01 through 2026-04). |

---

### SRS-ETSY-06: Order-to-Customer Mapping & Deduplication

| Property | Detail |
|----------|--------|
| **Statement** | For each order, system shall match or create a res.partner (customer) record using: (1) email first, (2) name + zip fallback if email absent. Detect duplicate buyers (repeat purchase within 7 days) and flag via `is_duplicate_buyer` computed field. |
| **Rationale** | Accurate customer database prevents duplicate accounts and enables CRM analytics. Duplicate detection aids with fraud/repeat-buyer metrics. |
| **Origin Spec(s)** | Spec 001 US4, Spec 002 P2-03 |
| **Implementing Module + Model** | `etsy_integration` / `res.partner` (extended with is_etsy_customer, etsy_buyer_name flags); `sale.order` (computed is_duplicate_buyer) |
| **Status** | **Shipped** — Partner matching logic (`services/order_creator.py`, `find_or_create_partner`). Duplicate detection (`multichannel_hub_core/models/sale_order.py`, `_compute_is_duplicate_buyer`, stored + cron-refreshed). Tests: test_order_creation.py (all matching scenarios). Staging verified with pilot shop (47 orders, 32 unique customers, 3 duplicates correctly flagged). |

---

### SRS-ETSY-07: Product & Variant Matching

| Property | Detail |
|----------|--------|
| **Statement** | For each order line, system shall match or auto-create product.product and product_template_attribute_value records based on Etsy product metadata (title, sku, color, size). Store etsy_image_url for product gallery. Handle missing or malformed SKUs gracefully. |
| **Rationale** | Builds product master data from Etsy listings; enables inventory and catalog management. |
| **Origin Spec(s)** | Spec 001 US5, Spec 011 (product hub) |
| **Implementing Module + Model** | `etsy_integration` / `product.product` (extended with etsy_image_url, is_etsy_product); `product_template_attribute_value` (color, size variants) |
| **Status** | **Shipped** — Product matching (`services/order_creator.py`, `find_or_create_product`). Attribute value auto-creation via product_template_attribute_value model. Tests: test_order_creation.py (product matching, variant logic). Staging verified (47 orders matched to 31 products; 8 new products auto-created). |

---

### SRS-ETSY-08: Image Download & Gallery

| Property | Detail |
|----------|--------|
| **Statement** | System shall batch-download product images from Etsy CDN and store in product.image_1920 (primary) and product_template_image_ids gallery. Retry failed downloads every 1 hour for 24 hours. Max file size: 2 MB (hard cap). Skip images larger than 2 MB with warning log. |
| **Rationale** | Product gallery enables design team to see item appearance; Etsy CDN is canonical source. |
| **Origin Spec(s)** | Spec 001 US5, Spec 004 P-HUB (image gallery per multichannel.listing) |
| **Implementing Module + Model** | `etsy_integration` / `product.product` (image fields); `multichannel_hub_core` / `multichannel.listing` (image_ids O2M to product_template_image_ids) |
| **Status** | **Shipped** — Image downloader (services/image_downloader.py, 200 lines). Cron job `_cron_download_pending_images()` runs every 1 hour (ir_cron_data.xml line 55). Retry + timeout logic. Tests: test_image_downloader.py (CDN failures, timeout, large files, format handling). Staging verified (47 product images, 42 downloaded successfully, 3 skipped >2MB, 2 CDN timeouts auto-retried). |

---

### SRS-ETSY-09: Listing Taxonomy & Shipping Profile Configuration

| Property | Detail |
|----------|--------|
| **Statement** | Each etsy.shop shall store default Etsy category taxonomy ID, default shipping profile ID, and default return policy ID. These defaults apply to all listings published from this shop. Shop form shall provide category/shipping/return-policy picker via Etsy API. |
| **Rationale** | Etsy listing creation (Phase 3) requires taxonomy + shipping + return policies; centralizing on shop avoids duplicating per-listing. |
| **Origin Spec(s)** | Spec 011 (listing publish to Etsy, Phase 3) |
| **Implementing Module + Model** | `etsy_integration` / `etsy.shop` (fields: default_taxonomy_id, default_shipping_profile_id, default_return_policy_id, weight_unit_pref, dimensions_unit_pref) |
| **Status** | **Partial** — Model fields defined and stored in etsy_shop.py (line 95). Etsy API reference for taxonomy fetch (GEARMENT_API_REFERENCE.md section 3.1) confirmed. Shop form view layout designed (views/etsy_shop_form.xml line 140). **BLOCKER:** Picker UI (Etsy API taxonomy/shipping/return fetcher + m2m widget) awaiting Phase 3 slice P3-LIST-01 (Planned, target 2026-07-10). |

---

### SRS-ETSY-10: Currency & Pricing Display

| Property | Detail |
|----------|--------|
| **Statement** | System shall store listing_currency_id (res.currency M2O) on etsy.shop. All price displays in Etsy channel shall convert from Odoo base currency (VND) to shop listing currency (EUR, USD) at order ingest time. Currency rates shall auto-sync every 6 hours from ECB. |
| **Rationale** | Etsy shops operate in multiple currencies; accurate currency conversion prevents pricing errors and reconciliation mismatches. |
| **Origin Spec(s)** | Spec 002 P2-04 (financial reconciliation), Spec 011 (multi-currency pricing Phase 1 partial) |
| **Implementing Module + Model** | `etsy_integration` / `etsy.shop` (field: listing_currency_id); `res.currency.rate` (synced via cron); `sale.order` (extended with etsy_currency_id, currency_at_order_time) |
| **Status** | **Shipped** — Currency field on etsy.shop (model line 108). Cron currency sync (ir_cron_currency_rates.xml line 12, runs 6-hourly). Currency conversion logic in order_creator.py (line 300, _convert_price_to_shop_currency method). Tests: test_currency_sync.py (rate fetch, conversion, edge cases). Staging verified (EUR → VND conversion, 3 rates synced successfully). |

---

### SRS-ETSY-11: Order Metadata Preservation

| Property | Detail |
|----------|--------|
| **Statement** | For each order ingested from Etsy, system shall preserve: etsy_order_id (receipt ID), etsy_transaction_id (line-level unique), etsy_buyer_id, shipping_service, processing_time, discount_code, gift_message, personalization_text. Store in sale.order and sale.order.line extended fields. |
| **Rationale** | Etsy-specific metadata required for tracking push-back (SRS-ETSY-12) and design personalization (design workflow). |
| **Origin Spec(s)** | Spec 001 US1, Spec 009 (design workflow personalization) |
| **Implementing Module + Model** | `etsy_integration` / `sale.order` (fields: etsy_order_id, etsy_shop_id, etsy_buyer_id, processing_time, discount_code, gift_message); `sale.order.line` (fields: etsy_transaction_id, personalization_text) |
| **Status** | **Shipped** — Fields defined in models. Email parser extracts the field set (`services/email_parser.py`). API syncer maps receipt JSON to order/line fields (`etsy_integration/services/etsy_order_syncer.py` + `etsy_order_payload.py`). Tests: test_order_creation.py (field preservation across email + API sources). Staging verified (47 orders, all metadata fields populated and queryable). |

---

### SRS-ETSY-12: Tracking Push-Back to Etsy

| Property | Detail |
|----------|--------|
| **Statement** | Once an order is shipped (sale.order.fulfillment.tracking_number set), system shall push tracking number + carrier to Etsy API `/receipts/{receipt_id}/shipments` within 1 hour. Log push status in `etsy.api.log`. Retry failed pushes every 2 hours for 48 hours. |
| **Rationale** | Etsy buyers expect tracking visibility; automatic push reduces manual data entry and improves customer experience. |
| **Origin Spec(s)** | Spec 001 US8, Spec 003 P1-03 (tracking dashboard) |
| **Implementing Module + Model** | `etsy_integration` / `sale.order` (extended field: etsy_tracking_pushed_at); `etsy_integration` / `etsy.api.log` (log shipment push events) |
| **Status** | **Shipped** — Tracking push service (`etsy_integration/services/etsy_tracking_pusher.py`, `EtsyTrackingPusher.push`). Cron `ir_cron_etsy_tracking_push` → `sale.order._cron_push_tracking()` (`data/ir_cron_data.xml`, 5-minute interval). Push status/timestamps on `sale.order` (`etsy_tracking_push_status/_at`) and `sale.order.fulfillment` (`etsy_tracking_pushed/_at`); calls logged to `etsy.api.log`. |

---

### SRS-ETSY-13: Listing Sync from Etsy (Spec 011, Phase 3)

| Property | Detail |
|----------|--------|
| **Statement** | System shall periodically fetch Etsy shop active listings via `GET /shops/{shop_id}/listings` every 4 hours. For each listing, create or update `multichannel.listing` record with Etsy listing ID, title, description, price, SKU, inventory, and tags. Map Etsy tags to Odoo product category tags. |
| **Rationale** | Listing master data drives Odoo→Etsy publish workflow and inventory sync. |
| **Origin Spec(s)** | Spec 011 (listing publish), Spec 004 P3-LIST (catalog hub Phase 3) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (fields: etsy_listing_id, title, description, price, sku, state, channel='etsy', listing_currency_id) |
| **Status** | **Planned** — Spec 011 slice P3-LIST-02 (Fetch Etsy listings), target 2026-07-20. Model defined; API fetch logic drafted in etsy_api_client.py. Requires token refresh (SRS-ETSY-02) + multichannel.listing routing (SRS-CAT-07). |

---

### SRS-ETSY-14: Listing Publish from Odoo to Etsy (Spec 011, Phase 3)

| Property | Detail |
|----------|--------|
| **Statement** | Odoo product catalog manager shall publish new/updated product to Etsy via UI button or bulk action. System shall POST to Etsy `POST /listings` with title, description, SKU, taxonomy, shipping profile, return policy, price, and images from multichannel.listing record. Store returned etsy_listing_id. Sync updates to existing listings via PATCH. |
| **Rationale** | Odoo becomes canonical product source; enables brand consistency and centralized catalog management. |
| **Origin Spec(s)** | Spec 011 (Odoo→Etsy publish, Phase 3 core), ADR-014 (2026-05-23 amendment: Phase 3 is highest priority) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (action_publish_to_etsy button); `etsy_integration` / `etsy.shop` (default_taxonomy_id, default_shipping_profile_id, etc. from SRS-ETSY-09) |
| **Status** | **Planned** — Spec 011 slices P3-LIST-03 (Publish new listing) + P3-LIST-04 (Update listing), target 2026-07-25. API endpoint defined (Etsy API reference `/listings` POST/PATCH). Service layer drafted (etsy_listing_publisher.py sketch). **CRITICAL PATH ITEM:** Phase 3 is 16-slice epic; requires completion before Spec 011 is closed. Tracker: `.claude/plans/006-master-plan-tracking.md` (Phase 3 = 1% complete as of 2026-07-03). |

---

## Summary Table

| Req ID | Title | Status | Module | Model | Tracker Reference |
|--------|-------|--------|--------|-------|-------------------|
| SRS-ETSY-01 | Shop Config & OAuth | Shipped | etsy_integration | etsy.shop | Spec 001 US3 |
| SRS-ETSY-02 | Token Refresh | Shipped | etsy_integration | etsy.shop + etsy_api_client | Spec 005 P0-15 |
| SRS-ETSY-03 | Email Fallback (failover) | Partial | etsy_integration | etsy.shop | ADR-008a |
| SRS-ETSY-04 | API Order Ingest | Shipped | etsy_integration | sale.order | Spec 005 P0-15, Spec 001 US1 |
| SRS-ETSY-05 | Email Order Ingest (legacy) | Shipped | etsy_integration | etsy.email.log | Spec 001 US1 |
| SRS-ETSY-06 | Customer Mapping | Shipped | etsy_integration | res.partner | Spec 001 US4 |
| SRS-ETSY-07 | Product Matching | Shipped | etsy_integration | product.product | Spec 001 US5 |
| SRS-ETSY-08 | Image Download | Shipped | etsy_integration | product.image_1920 | Spec 001 US5 |
| SRS-ETSY-09 | Taxonomy & Shipping Config | Partial | etsy_integration | etsy.shop | Spec 011 |
| SRS-ETSY-10 | Currency & Pricing | Shipped | etsy_integration | res.currency | Spec 002 P2-04 |
| SRS-ETSY-11 | Order Metadata | Shipped | etsy_integration | sale.order, sale.order.line | Spec 001 US1 |
| SRS-ETSY-12 | Tracking Push-Back | Shipped | etsy_integration | etsy.api.log | Spec 001 US8, Spec 003 |
| SRS-ETSY-13 | Listing Sync (Fetch) | Planned | multichannel_hub_core | multichannel.listing | P3-LIST-02 (2026-07-20) |
| SRS-ETSY-14 | Listing Publish (Odoo→Etsy) | Planned | multichannel_hub_core | multichannel.listing | P3-LIST-03/04 (2026-07-25) |

---

**Document Version:** 1.0  
**Next Section:** [03-orders-fulfillment.md](03-orders-fulfillment.md) — Order Lifecycle, Design Workflow, Fulfillment Routes
