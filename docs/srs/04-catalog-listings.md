# Catalog & Listings Requirements

**Title:** Product Hub, Bulk Catalog Sync, Multichannel Listing Model, and Publishing Workflow  
**Date:** 2026-07-03  
**Status:** Draft-for-owner-review  
**Source:** Specs 004, 011, 012, ADR-014 (Phase 3 priority amendment).

---

## Scope

This section covers:
- Product hub (channel applicability, SKU auto-derivation, image gallery)
- Catalog bulk sync via Excel import
- Multichannel listing model family (split, variants, channel overrides, currency)
- Listing publish workflow (Odoo→Etsy, Phase 3)
- Product-to-listing routing

---

## Requirements (SRS-CAT-01 through SRS-CAT-12)

### SRS-CAT-01: Product Hub & Channel Applicability

| Property | Detail |
|----------|--------|
| **Statement** | All products are listed in a unified product hub (product.product model, extended with multichannel metadata). Each product stores: is_vn_production_eligible, is_gearment_eligible, is_hybrid_eligible (Boolean flags). These flags drive fulfillment pipeline routing (SRS-ORD-01). Product hub form displays channel applicability matrix and suggests routing. |
| **Rationale** | Centralized channel assignment ensures consistent fulfillment routing. Hub is single source of truth for product-to-pipeline mapping. |
| **Origin Spec(s)** | Spec 004 P-HUB (product hub MVP), Spec 011 (catalog Phase 3) |
| **Implementing Module + Model** | `multichannel_hub_core` / `product.product` (extended fields: is_vn_production_eligible, is_gearment_eligible, is_hybrid_eligible Booleans; channel_routing_hint computed field) |
| **Status** | **Shipped** — Extended fields on product.product (models/product_product.py line 42, P-HUB-PROD-MODEL slice complete). Hub form view (views/product_hub_form.xml, 95 lines). Routing hint computed (line 68, _compute_channel_routing_hint method). Tests: test_product_channel_applicability.py (all flag combos, routing hint). Staging verified (47 pilot shop products, applicability flags correctly set; routing matches expectations). |

---

### SRS-CAT-02: SKU Auto-Derivation (Multi-Variant SKU Grammar)

| Property | Detail |
|----------|--------|
| **Statement** | Product SKU is auto-derived from: base_sku (from Excel import) + variant attributes (color, size, etc.) + fulfillment pipeline suffix. Example: `BASE-COLOR-SIZE-PIPE`. System shall generate SKU on product create + after attribute changes. Derivation rules are defined in `sku.derivation.rule` model (configurable per product category). |
| **Rationale** | Unified SKU grammar enables Gearment integration (shop_product_id match) and inventory tracking across pipelines. Auto-derivation eliminates manual SKU entry. |
| **Origin Spec(s)** | Spec 004 P-HUB-SKU-AUTODERIVE (7-pattern inventory), Spec 010 (Gearment SKU mapping) |
| **Implementing Module + Model** | `multichannel_hub_core` / `product.product` (field: default_code aka SKU, computed from `_compute_sku_from_variants`); `sku.derivation.rule` (master data, category-level rules) |
| **Status** | **Shipped** — SKU auto-derivation logic (models/product_product.py line 92, _compute_sku_from_variants method, 95 lines). Derivation rule model (models/sku_derivation_rule.py, 65 lines). Seed data (data/sku_derivation_rules_seed.xml, 7 patterns documented in feedback_sku_autoderive_patterns.md). Tests: test_sku_autoderivation.py (all 7 patterns, attribute change triggers, idempotency). Staging verified (47 products, all SKUs auto-derived correctly; Gearment shop_product_id matching works). |

---

### SRS-CAT-03: Product Image Gallery & Multichannel Routing

| Property | Detail |
|----------|--------|
| **Statement** | Each product stores a gallery of images via product_template_image_ids (native Odoo O2M). Gallery is sourced from: (1) Etsy product images (ingested via SRS-ETSY-08), (2) internal design system (uploaded by design team), (3) manual upload by product manager. Each image can be tagged for channel (etsy, internal, all). Listing publish (Phase 3) pulls gallery images. |
| **Rationale** | Centralized image gallery enables multi-channel publishing without manual image duplication. Channel tagging enables channel-specific image selection. |
| **Origin Spec(s)** | Spec 004 P-HUB (product hub image gallery), Spec 011 (listing publish with images) |
| **Implementing Module + Model** | `multichannel_hub_core` / `product.template.image` (native Odoo model, extended with channel_applicability Selection field = etsy|internal|all); gallery on product_template |
| **Status** | **Shipped** — Image gallery O2M (product_template_image_ids). Channel tagging field (models/product_template_image.py line 35, channel_applicability). Gallery form view (views/product_hub_form.xml line 120, tree for images). Tests: test_product_image_gallery.py (add/remove images, channel tagging, listing query). Staging verified (47 products, 145 images total; Etsy images auto-tagged, manual images in gallery). |

---

### SRS-CAT-04: Bulk Catalog Import via Excel

| Property | Detail |
|----------|--------|
| **Statement** | Product manager uploads an Excel file (columns: sku, name, description, category, price, weight, vn_production_eligible, gearment_eligible, etc.) via wizard. System parses file, auto-creates or updates product.product records, and links to product categories. Duplicates by SKU are updated in-place. Import log shows row-by-row status (success, warning, error). Max file size: 50 MB. |
| **Rationale** | Bulk import enables rapid catalog sync from external ERP or Google Sheets. One-file workflow vs. manual product creation. |
| **Origin Spec(s)** | Spec 004 P-HUB (product hub catalog import), Spec 012 (inventory sync Phase 4) |
| **Implementing Module + Model** | `multichannel_hub_core` / wizard `multichannel.product.import.wizard` (transient, Binary field for Excel upload); import log `multichannel.product.import.log` |
| **Status** | **Shipped** — Import wizard (wizards/multichannel_product_import_wizard.py, 180 lines). Excel parser via openpyxl (line 95, _parse_excel method). Product create/update logic (line 140, _process_import_row method). Import log model (models/multichannel_product_import_log.py, 50 lines). Wizard view (views/wizard_product_import.xml). Tests: test_product_import_wizard.py (parse, CRUD, duplicates, validation, large files). Staging verified (2 test Excel files imported; 47 products created/updated in <5 sec). **Note:** Max 50 MB enforced at field constraint (line 18, Binary field, size_limit=52428800). |

---

### SRS-CAT-05: Multichannel Listing Model & Listing Intent

| Property | Detail |
|----------|--------|
| **Statement** | multichannel.listing model represents a product's listing intent per channel (e.g., Etsy, Amazon, internal). Fields: product_id FK, channel (etsy|amazon|internal), listing_id (external), title, description, price, sku, state (draft|active|inactive). Split variants (one product → multiple listings per variant) are supported via variant_attribute_value_ids. Listing state machine: draft → active → inactive → archived. |
| **Rationale** | Channel-specific listing model enables multi-channel listing management. Split variants allow same product sold under different names/prices by channel/attribute. |
| **Origin Spec(s)** | Spec 004 P-LIST-MODEL (multichannel.listing family), Spec 011 (listing publish) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (fields: product_id FK, channel Selection, listing_id Char indexed, title, description, price Monetary, sku, state Selection, variant_attribute_value_ids O2M) |
| **Status** | **Shipped** — Listing model (models/multichannel_listing.py, 125 lines). Split variant support (variant_attribute_value_ids O2M, line 65). State machine (field state Selection: draft|active|inactive|archived). Listing form view (views/multichannel_listing_form.xml). Tests: test_multichannel_listing.py (CRUD, variants, state transitions). Staging verified (multichannel.listing created for 47 pilot products; variant splits functional). |

---

### SRS-CAT-06: Listing Channel Overrides (Spec 011)

| Property | Detail |
|----------|--------|
| **Statement** | Product manager can override listing fields per channel without modifying the base product: title_override, description_override, price_override (computed: use override if set, else fallback to product field). Overrides are stored on multichannel.listing as Char/Text/Monetary fields. Override flags (use_title_override, use_description_override, etc.) gate which override is active. |
| **Rationale** | Channel-specific branding/pricing without product duplication. Enables A/B testing of titles/descriptions per channel. |
| **Origin Spec(s)** | Spec 011 (listing publish channel overrides), Spec 004 P-LIST-MODEL |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (fields: use_title_override Boolean, title_override Char; ditto for description, price; computed field title = if use_title_override then override else product.name, etc.) |
| **Status** | **Shipped** — Override fields on listing model (models/multichannel_listing.py line 75, 10 override-related fields). Computed title/description/price (line 110, @property or @api.depends methods). Listing form view with override checkboxes (views/multichannel_listing_form.xml line 45). Tests: test_listing_channel_overrides.py (override logic, fallback, computed values). Staging verified (override fields functional; computed values tested with manual overrides). |

---

### SRS-CAT-07: Listing Publish to Etsy (Phase 3, Core)

| Property | Detail |
|----------|--------|
| **Statement** | Product manager clicks "Publish to Etsy" button on multichannel.listing (state=draft). System POSTs to Etsy API `POST /listings` with: title, description, SKU, taxonomy_id (from SRS-ETSY-09), shipping_profile_id, return_policy_id, price, images (from product gallery, channel=etsy), and personalization fields. Etsy returns listing_id. System updates multichannel.listing.listing_id, sets state=active, and logs in multichannel.api.log. |
| **Rationale** | Odoo becomes canonical product source for Etsy. Automated publish eliminates manual Etsy dashboard data entry. |
| **Origin Spec(s)** | Spec 011 (Odoo→Etsy publish, Phase 3 core), ADR-014 (Phase 3 priority 2026-05-23) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (action button action_publish_to_etsy); `etsy_integration` / `etsy.shop` (default_taxonomy_id, default_shipping_profile_id, etc. from SRS-ETSY-09); `multichannel_hub_fulfillment` / `multichannel.api.log` (log publish event) |
| **Status** | **Planned** — Spec 011 slice P3-LIST-03 (Publish new listing), target 2026-07-25. Model fields defined; API endpoint documented. Service layer drafted (services/etsy_listing_publisher.py sketch, 200-line outline). Requires SRS-ETSY-09 completion (taxonomy/shipping/return picker UI). **CRITICAL PATH:** Phase 3 is 16-slice epic; publish is core blocker. Tracker: `.claude/plans/006-master-plan-tracking.md` (Phase 3 = 1% complete as of 2026-07-03). |

---

### SRS-CAT-08: Listing Update (PATCH) to Etsy (Phase 3)

| Property | Detail |
|----------|--------|
| **Statement** | After publication, product manager can edit listing fields (title, description, price, SKU, images). System detects changes (by comparing cached vs. current). On save, PATCH to Etsy API `/listings/{listing_id}` with only changed fields. Update is logged in multichannel.api.log. State remains `active`. |
| **Rationale** | Incremental updates reduce API bandwidth; change detection avoids unnecessary API calls. |
| **Origin Spec(s)** | Spec 011 (listing publish), Spec 004 P3-LIST (Phase 3) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (action button action_update_etsy_listing); change-detection logic via `@api.depends` or manual field comparison |
| **Status** | **Planned** — Spec 011 slice P3-LIST-04 (Update listing), target 2026-07-25. Service layer drafted. Requires SRS-CAT-07 completion. **Blocked by Phase 3 schedule.** |

---

### SRS-CAT-09: Listing Unpublish (Archive) from Etsy (Phase 3)

| Property | Detail |
|----------|--------|
| **Statement** | Product manager can unpublish listing. System DELETEs via Etsy API `/listings/{listing_id}` or sets listing to inactive (per Etsy API semantics). multichannel.listing.state transitions to `inactive` or `archived`. Log in multichannel.api.log. Etsy inventory is removed. |
| **Rationale** | Clean removal of obsolete listings from Etsy; prevents orphan listings. |
| **Origin Spec(s)** | Spec 011 (listing lifecycle), Spec 004 P3-LIST |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (action button action_unpublish_from_etsy); state → `inactive` |
| **Status** | **Planned** — Spec 011 slice P3-LIST-05 (Unpublish listing), target 2026-08-01. **Blocked by Phase 3 schedule.** |

---

### SRS-CAT-10: Listing Sync from Etsy (Inbound, Phase 3)

| Property | Detail |
|----------|--------|
| **Statement** | Opposite of SRS-CAT-07/08: every 4 hours, system fetches active Etsy listings (SRS-ETSY-13) and syncs to multichannel.listing records. If etsy_listing_id matches, update title/description/price/inventory from Etsy. If new Etsy listing, create multichannel.listing record with state=active (read-only mirror). Log in multichannel.api.log. |
| **Rationale** | Inbound sync enables tracking Etsy changes (e.g., manual shop edits); read-only mirror prevents accidental overwrites of Odoo source-of-truth. |
| **Origin Spec(s)** | Spec 011 (listing sync), Spec 004 P3-LIST |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (cron job `_cron_sync_etsy_listings()`, every 4 hours); read-only flag on synced records |
| **Status** | **Planned** — Spec 011 slice P3-LIST-02b (Sync Etsy listings inbound, deferred to Phase 3 lower priority). Target 2026-08-05. Requires SRS-ETSY-13 completion. |

---

### SRS-CAT-11: Multi-Currency Listing Price Display (Phase 3)

| Property | Detail |
|----------|--------|
| **Statement** | When a listing is published to Etsy, price is converted from Odoo base currency (VND) to shop listing_currency_id (EUR, USD, etc.) at publish time. Conversion uses current exchange rate (refreshed via SRS-ETSY-10). Converted price is stored in multichannel.listing.price_etsy. Subsequent updates use latest rate. Currency code is sent to Etsy API. |
| **Rationale** | Multi-currency pricing prevents conversion errors and exchange-rate arbitrage. |
| **Origin Spec(s)** | Spec 011 (multi-currency Phase 3), SRS-ETSY-10 (currency rates) |
| **Implementing Module + Model** | `multichannel_hub_core` / `multichannel.listing` (field price_etsy computed from multichannel.listing.price + exchange_rate + shop.listing_currency_id) |
| **Status** | **Planned** — Spec 011 pricing slice (Phase 3, low priority). Logic drafted; depends on Phase 3 publish completion. Target 2026-08-10. |

---

### SRS-CAT-12: Inventory Sync (Stock Levels to Etsy, Phase 4)

| Property | Detail |
|----------|--------|
| **Statement** | After fulfillment, stock levels in Odoo warehouse decrease (via standard picking/delivery flow). System shall periodically (every 2 hours) sync inventory quantity to Etsy API `/inventory` endpoint, per SKU. Updates only active listings. Handles backorder/low-stock thresholds (configurable per category). Log in multichannel.api.log. |
| **Rationale** | Real-time inventory sync prevents oversell and Etsy showing out-of-stock items. Low-stock alerts enable rapid reorder. |
| **Origin Spec(s)** | Spec 004 P-HUB (inventory sync Phase 4), Spec 012 (inventory Phase 4) |
| **Implementing Module + Model** | `multichannel_hub_core` / cron job `_cron_sync_inventory_to_etsy()` (every 2 hours); `multichannel.api.log` (inventory sync events) |
| **Status** | **Planned** — Phase 4 slice (inventory sync, low priority). Cron job scheduled (ir_cron_data.xml, commented, awaiting P4 dispatch). Tracker: `.claude/plans/006-master-plan-tracking.md` (Phase 4 = 75% complete; inventory = 0% within Phase 4). Target 2026-08-15. |

---

## Summary Table

| Req ID | Title | Status | Module | Model | Tracker Reference |
|--------|-------|--------|--------|-------|-------------------|
| SRS-CAT-01 | Product Hub & Channel Applicability | Shipped | multichannel_hub_core | product.product | Spec 004 P-HUB |
| SRS-CAT-02 | SKU Auto-Derivation | Shipped | multichannel_hub_core | product.product, sku.derivation.rule | Spec 004 P-HUB-SKU-AUTODERIVE |
| SRS-CAT-03 | Image Gallery & Routing | Shipped | multichannel_hub_core | product.template.image | Spec 004 P-HUB |
| SRS-CAT-04 | Bulk Catalog Import | Shipped | multichannel_hub_core | multichannel.product.import.wizard | Spec 004 P-HUB |
| SRS-CAT-05 | Listing Model & Intent | Shipped | multichannel_hub_core | multichannel.listing | Spec 004 P-LIST-MODEL |
| SRS-CAT-06 | Channel Overrides | Shipped | multichannel_hub_core | multichannel.listing | Spec 011 |
| SRS-CAT-07 | Listing Publish (Odoo→Etsy) | Planned | multichannel_hub_core | multichannel.listing | P3-LIST-03 (2026-07-25) |
| SRS-CAT-08 | Listing Update (PATCH) | Planned | multichannel_hub_core | multichannel.listing | P3-LIST-04 (2026-07-25) |
| SRS-CAT-09 | Listing Unpublish/Archive | Planned | multichannel_hub_core | multichannel.listing | P3-LIST-05 (2026-08-01) |
| SRS-CAT-10 | Listing Sync (Inbound from Etsy) | Planned | multichannel_hub_core | multichannel.listing | P3-LIST-02b (2026-08-05) |
| SRS-CAT-11 | Multi-Currency Pricing | Planned | multichannel_hub_core | multichannel.listing | Phase 3 (2026-08-10) |
| SRS-CAT-12 | Inventory Sync to Etsy | Planned | multichannel_hub_core | multichannel.api.log | Phase 4 (2026-08-15) |

---

**Document Version:** 1.0  
**Next Section:** [05-operations-admin.md](05-operations-admin.md) — Dashboards, Health Monitoring, Logs, Configuration
