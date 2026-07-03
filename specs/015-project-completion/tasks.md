# Spec 015: Project Completion — Prioritized Execution Order & Exit Criteria

**Date**: 2026-07-03  
**Status**: Draft for Owner Review  
**Scope**: 51 non-done items grouped into P1/P2/P3 buckets with sequential dispatch order and machine-checkable exit criteria

---

## Execution Strategy

**Critical Path**: P1 items gate production release; P2 items gate full E2E validation; P3 items are deferred post-E2E polish.

**Parallel Execution**: Within each priority bucket, some items can run in parallel (noted in dependencies).

**Blocking Relationships**: See dependency chart at end of this document.

---

## P1: Production Cutover Critical Path (18 items)

### Dispatch Sequence: P1.1 → P1.2 → P1.3 → P1.4

---

### P1.1: Foundation Specs & APIs (Weeks 1–2)

**Goal**: Unblock all Phase 3 implementation slices by completing architecture specification and foundational client library.

#### P1.1.1 — P-HUB-SPEC (Central Product Hub Architecture)

**Owner**: Planner (spec authoring)  
**Estimated Duration**: 5–7 days  
**Dependencies**: None  
**Blocking**: All 15 Phase 3 implementation slices

**Scope**:
- Document central product hub models and their relationships
- Specify SKU derivation logic and drift detection algorithm
- Define Excel sync workflow (ingest + cron schedule)
- Define Etsy outbound publish workflow (draft → quote → confirm state machine)
- Document inventory writeback rules

**Exit Criteria**:
- [ ] P-HUB-SPEC authoring complete; spec merged to main
- [ ] 15 implementation slices have task breakdown (tasks.md in specs/009/010/011)
- [ ] All models documented in `docs/sds/models.md` with field cardinality
- [ ] Sequence diagrams for publish workflow in `docs/sds/sequence-diagrams.drawio`
- [ ] Code evidence: No implementation started (spec only)

**Test Plan**: N/A (spec-only; no code to test)

---

#### P1.1.2 — P-PUB-CLIENT (EtsyApiClient Write Methods)

**Owner**: Dev (API wrapper implementation)  
**Estimated Duration**: 5 days  
**Dependencies**: P-HUB-SPEC completion (for payload schema confirmation)  
**Blocking**: P-PUB-DRAFT, P-PUB-IMAGES, P-PUB-INVENTORY, P-PUB-PUBLISH

**Scope**:
- Implement `EtsyApiClient.post()` for draft listing creation
- Implement `EtsyApiClient.put()` for listing updates
- Implement `EtsyApiClient.patch()` for partial updates
- Implement `EtsyApiClient.post_multipart()` for image uploads (multipart/form-data)
- Add auth headers, retry logic (exponential backoff for 429/503), rate limiting (100 req/10 sec)
- Add request/response logging to `gearment.api.log`-equivalent model

**Exit Criteria**:
- [ ] `EtsyApiClient` class in `custom_addons/multichannel_hub_catalog/services/etsy_api_client.py`
- [ ] Phase 1 (DB tests): 40+ tests GREEN (auth, rate limit, retry, multipart, error handling)
- [ ] Phase 2 (ORM tests): 30+ tests GREEN (logging, payload validation)
- [ ] All write methods signed and versioned for Etsy v3 API contract
- [ ] Payload schema matches Spec 011 contract; XSD/OAS validation in place
- [ ] Module install: `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_catalog --stop-after-init` → exit 0
- [ ] ruff check passes with 0 errors

**Test Plan**:
1. Unit test auth header injection (X-API-Key format)
2. Unit test rate-limit token bucket (verify 100/10-sec throttle)
3. Unit test retry loop (verify exp backoff for 429/503, 3 attempts max)
4. Integration test multipart upload (mock Etsy, verify Content-Type + boundary)
5. Integration test error payload logging (verify `api.log` record created on 4xx/5xx)

---

### P1.2: Etsy Pilot Cutover & Email-to-API Transition (Weeks 2–4)

**Goal**: Flip JaHandmadeArt to API-only ingest; gate production release on successful pilot.

#### P1.2.1 — P1-11 (Pilot-Shop Cutover: JaHandmadeArt OAuth → API Ingest)

**Owner**: Dev + Owner (API cutover + ops confirmation)  
**Estimated Duration**: 3–5 days  
**Dependencies**: E2 keys obtained (Gearment), P1-11-SHOPID-BOOTSTRAP complete (Phase 0)  
**Blocking**: P1-13, P2-07, P2-08

**Scope**:
- Verify JaHandmadeArt shop is bound to `etsy.shop` record with `api_only=True` flag
- Verify Gmail cron still polls as fallback (email parser active, no writes)
- Confirm Etsy API v3 orders ingest for JaHandmadeArt (track ingest lag <5 min)
- Verify E2E demo runner (P0-E2E-DROP-SHIP-RUNNER) passes all 12 sections on staging
- Owner sign-off: "cutover approved, live on production"

**Exit Criteria**:
- [ ] `etsy.shop.api_only = True` for JaHandmadeArt
- [ ] Cron `_cron_sync_etsy_orders_api` logs to `multichannel.sync.health` (ingest count ≥ 1 per cycle)
- [ ] No duplicate orders created during cutover (idempotent ingest via `etsy_order_id` dedup)
- [ ] Email fallback active (no orders lost if API fails)
- [ ] E2E demo runner (gearment drop-ship pipeline): 12/12 sections PASS on staging
- [ ] Production validation: ≥5 real orders ingested via API on live JaHandmadeArt shop
- [ ] Owner sign-off captured in `findings.md` + `006-master-plan-tracking.md` state→done

**Test Plan**:
1. Staging: Ingest 10 test orders via Etsy sandbox API; verify dedupe on re-ingest
2. Staging: Kill API, verify email fallback creates orders within 10 min
3. Staging: Verify order fields (etsy_order_id, shipping address, price, currency) populated correctly
4. Production: Monitor ingest lag for 24 hours; capture metrics in sync.health
5. Production: Verify shipping notifications route correctly (carrier detection)

---

#### P1.2.2 — P2-07 (Gmail Cron Rebind: Email → API Cutover)

**Owner**: Dev + Ops  
**Estimated Duration**: 2 days  
**Dependencies**: P1-11 pilot success (confirmed live)  
**Blocking**: P2-08

**Scope**:
- Rebind `_cron_fetch_etsy_emails()` to check `api_only` flag first; skip email for api_only shops
- Ensure email parser remains active for non-api shops as mandatory fallback
- Update `ir_cron_data.xml` cron interval documentation (email now fallback-only)
- Verify no race condition between API + email ingest (dedup by etsy_order_id prevents duplicates)

**Exit Criteria**:
- [ ] Cron code: `if shop.api_only: return` branch added to email parser entry point
- [ ] `_cron_fetch_etsy_emails()` remains active (fallback enabled)
- [ ] Tests: 10+ tests GREEN (api_only flag honored, fallback on API failure, dedup across channels)
- [ ] Documentation: Updated in `ir_cron_data.xml` comment + CLAUDE.md
- [ ] Staging validation: JaHandmadeArt (api_only) receives 0 emails; non-api shop receives emails
- [ ] Module update: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` → exit 0

**Test Plan**:
1. Unit test: `api_only=True` → email skip
2. Unit test: `api_only=False` → email fetch active
3. Integration test: Ingest via API + email simultaneously; verify 1 order created (dedup)
4. Integration test: API fails; fallback to email within 10 min timeout

---

#### P1.2.3 — P1-13 (Additional 2–4 Shops Cutover)

**Owner**: Dev + Owner  
**Estimated Duration**: 3–5 days  
**Dependencies**: P1-11 + P2-07 complete  
**Blocking**: P2-08

**Scope**:
- Identify 2–4 additional pilot shops (owner selection)
- Follow same cutover flow as P1-11 (api_only flag, E2E validation, owner approval)
- Batch API cutover (same cron cycle handles all api_only shops)

**Exit Criteria**:
- [ ] 2–4 additional shops have `api_only=True`
- [ ] E2E validation for each: ≥5 real orders ingested, carrier detection working
- [ ] Owner approval documented per shop
- [ ] No regression in JaHandmadeArt (still live on API)
- [ ] Staging snapshot updated with full multi-shop dataset

**Test Plan**:
1. Per-shop: Ingest 5+ orders; verify all key fields populated
2. Per-shop: Verify carrier tracking for fulfillment (carrier detection + label routing)
3. Cross-shop: Verify dashboard filters by shop (no data leakage)

---

#### P1.2.4 — P2-08 (Remaining 15 Shops Cutover to api_only)

**Owner**: Ops (bulk cutover)  
**Estimated Duration**: 1 day (bulk operation; sequential validation 5 days)  
**Dependencies**: P1-11 + P2-07 + P1-13 complete (pilot success documented)  
**Blocking**: Production release

**Scope**:
- Bulk set `api_only=True` for remaining 15 shops (shops 4–19, excluding pilot 1–3)
- Monitor ingest health for 24 hours per shop cohort (batch of 5 shops at a time)
- Verify no order loss; track late-arriving orders

**Exit Criteria**:
- [ ] All 19 shops have `api_only=True` in production
- [ ] Ingest health dashboard (multichannel.sync.health) shows 0 errors for 24 hours
- [ ] Late-order window (orders arriving 1–12 hours after Etsy timestamp): ≤5 orders identified, audited
- [ ] Email fallback still active (passive, not primary)
- [ ] Staging snapshot reflects full 19-shop live state

**Test Plan**:
1. Monitor sync.health for 24 hours; verify ingest_count ≥ shop_avg_daily_orders
2. Audit late-order window; manual reconciliation if needed
3. Spot-check 3–5 random shops for order completeness

---

### P1.3: Phase 3 Foundation Models (Weeks 4–6)

**Goal**: Ship foundational models for central product hub; unblock publish pipeline.

#### P1.3.1 — P-HUB-PROD-MODEL (Product Hub Models)

**Owner**: Dev  
**Estimated Duration**: 5–7 days  
**Dependencies**: P-HUB-SPEC complete  
**Blocking**: P-HUB-WIZARD, P-HUB-SKU-DRIFT, P-PUB-DRAFT, P-PUB-INVENTORY

**Scope**:
- Create `multichannel.sales.channel` model (name, code, active, order_prefix for etsy_order_id format)
- Extend `product.template` with channel-specific fields (sku per channel, price per channel)
- Create `product.channel.status` model (product_id, channel_id, publish_status, inventory_status, sync_status, last_sync_date)
- Create data migration: backfill `multichannel.sales.channel` with 'etsy' (master + future amazon/website)
- Create ACLs in `ir.model.access.csv` (base group access)
- Create views: `product.channel.status` form/list, search filters by channel + publish_status

**Exit Criteria**:
- [ ] 3 new models implemented in `custom_addons/multichannel_hub_core/models/`
- [ ] Phase 1 (DB tests): 50+ tests GREEN (model creation, field validation, migration idempotency)
- [ ] Phase 2 (ORM tests): 40+ tests GREEN (computed fields, constraints, ACL checks)
- [ ] All new models inherit `mail.thread` + `mail.activity.mixin`; tracking=True on user-visible fields
- [ ] `i18n/vi_VN.po` includes all new field labels + status values
- [ ] Module update: exit 0
- [ ] Data migration creates 1 'etsy' channel; idempotent on re-run
- [ ] ruff check: 0 errors

**Test Plan**:
1. Create `multichannel.sales.channel` 'etsy'; verify 1 record created
2. Extend `product.template` with etsy_sku; verify field stored + retrieved
3. Create `product.channel.status` for Etsy channel; verify published/draft status tracked
4. Migration re-run; verify no duplicate channel created
5. ACL test: non-group user cannot write `product.channel.status` (if group-restricted)

---

#### P1.3.2 — P-HUB-WIZARD (SKU Derivation Wizard)

**Owner**: Dev  
**Estimated Duration**: 5 days  
**Dependencies**: P-HUB-PROD-MODEL complete  
**Blocking**: P-HUB-SKU-DRIFT, publish slices

**Scope**:
- Create transient wizard model `multichannel.sku.derivation.wizard` (one-shot per product)
- Wizard displays SKU precedence logic: `[product.default_code]` + `[channel_sku]` fallback + `[auto_generated_sku]`
- Operator selects which SKU to use; confirm overwrites channel SKU
- Wizard updates `product.template` + `product.channel.status.sku`
- Wizard logs action to `multichannel.sync.health` (for audit)

**Exit Criteria**:
- [ ] Transient wizard in `custom_addons/multichannel_hub_core/wizards/`
- [ ] Phase 1 (DB tests): 20+ tests GREEN (wizard state transitions, SKU precedence logic)
- [ ] Phase 2 (ORM tests): 15+ tests GREEN (write operations, audit logging)
- [ ] Wizard form view with 3 SKU options visible (read-only display + radio button select)
- [ ] Wizard action registered in product form view (button "Derive SKU")
- [ ] Module update: exit 0

**Test Plan**:
1. Open wizard for product with default_code='PROD-001' + channel_sku='ETSY-PROD-001'
2. Verify both options shown in wizard form
3. Select one; confirm updates product.template.default_code
4. Verify sync.health audit log created
5. Re-open wizard; verify previous selection is default

---

#### P1.3.3 — P-HUB-SKU-DRIFT (Drift Detection)

**Owner**: Dev  
**Estimated Duration**: 3–5 days  
**Dependencies**: P-HUB-PROD-MODEL complete  
**Blocking**: P-PUB-INVENTORY

**Scope**:
- Create `multichannel.sku.drift.detector` model (cron job, daily)
- Detect when Etsy listing SKU ≠ Odoo product SKU; flag in `product.channel.status` for resolution
- Store drift detection results in `multichannel.sync.health` (drift_count, resolution_count)
- Operator resolves via P-HUB-WIZARD

**Exit Criteria**:
- [ ] `multichannel.sku.drift.detector` model (or standalone job class) in `custom_addons/multichannel_hub_core/`
- [ ] `ir_cron_data.xml` entry: `sku_drift_detection` cron (daily, 02:00 UTC)
- [ ] Phase 1 (DB tests): 15+ tests GREEN (drift detection logic, flagging, cron execution)
- [ ] Phase 2 (ORM tests): 10+ tests GREEN (result logging, sync.health audit)
- [ ] Drift flag appears in `product.channel.status` form (decoration-warning if drift detected)
- [ ] Module update: exit 0

**Test Plan**:
1. Create product with default_code='TEST-SKU'
2. Manually update Etsy listing SKU to 'ETSY-TEST-SKU' (simulate drift)
3. Run drift detection cron
4. Verify drift flagged in product.channel.status
5. Resolve via P-HUB-WIZARD; verify drift cleared

---

### P1.4: Etsy Publish Pipeline (Weeks 6–10)

**Goal**: Implement complete Etsy outbound publish flow; enable Odoo → Etsy catalog sync.

#### P1.4.1 — P-PUB-DRAFT (Draft Listing Creation)

**Owner**: Dev  
**Estimated Duration**: 5 days  
**Dependencies**: P-PUB-CLIENT complete  
**Blocking**: P-PUB-IMAGES

**Scope**:
- Create `multichannel.listing.draft.wizard` transient model (multi-step)
- Wizard step 1: Select product (with SKU/variant preview)
- Wizard step 2: Confirm metadata (title, description, category, tags, price, quantity)
- Wizard step 3: POST draft listing to Etsy API; receive listing_id + quote
- Wizard result: Create `multichannel.listing` record (state='draft', etsy_listing_id set)
- Wizard logs to `multichannel.sync.health` (draft_count, quote_amount)

**Exit Criteria**:
- [ ] Wizard in `custom_addons/multichannel_hub_listing/wizards/`
- [ ] Phase 1 (DB tests): 30+ tests GREEN (wizard flow, metadata validation, API call)
- [ ] Phase 2 (ORM tests): 20+ tests GREEN (model creation, logging)
- [ ] Wizard form view: 3-step flow with progress indicator
- [ ] API POST to `/listings` includes all required fields per Etsy v3 spec
- [ ] Received `etsy_listing_id` stored in `multichannel.listing.etsy_listing_id`
- [ ] Quote received + logged in response (captured for Phase 3 quote review)
- [ ] Module update: exit 0

**Test Plan**:
1. Select product; verify metadata pre-filled from product.template
2. Modify title/description; confirm updates wizard
3. Submit wizard; verify Etsy API POST called
4. Verify multichannel.listing created with draft state
5. Verify sync.health log includes quote amount

---

#### P1.4.2 — P-PUB-IMAGES (Image Upload & Variant Assignment)

**Owner**: Dev  
**Estimated Duration**: 5 days  
**Dependencies**: P-PUB-DRAFT complete  
**Blocking**: P-PUB-INVENTORY

**Scope**:
- Extend `multichannel.listing` with image upload UI (ir.attachment M2M)
- Operator uploads 1+ images to listing
- Wizard step: map each image to variant (if multi-variant listing)
- Wizard: POST multipart image upload to `/listings/{id}/images`
- Wizard: PUT variant image assignments to `/listings/{id}/inventory`
- Wizard logs to sync.health (image_upload_count, variant_image_links)

**Exit Criteria**:
- [ ] `multichannel.listing.image_ids` M2M to ir.attachment
- [ ] Image upload form with drag-drop UI (standard Odoo attachment widget)
- [ ] Phase 1 (DB tests): 20+ tests GREEN (image attachment, multipart POST)
- [ ] Phase 2 (ORM tests): 15+ tests GREEN (variant image mapping)
- [ ] API multipart POST verified (Content-Type: multipart/form-data, file chunk size)
- [ ] Variant image PUT updates etsy_variant.image_index
- [ ] Module update: exit 0

**Test Plan**:
1. Create listing; attach 1 image file (PNG, <5 MB)
2. Upload to Etsy API; verify 200 response + image_url received
3. For multi-variant listing: map image to variant; verify PUT to inventory endpoint
4. Verify image_ids stored in multichannel.listing
5. Re-open listing; verify image attachments persistent

---

#### P1.4.3 — P-PUB-INVENTORY (Inventory Writeback)

**Owner**: Dev  
**Estimated Duration**: 4 days  
**Dependencies**: P-HUB-SKU-DRIFT complete, P-PUB-DRAFT complete  
**Blocking**: P-PUB-PUBLISH

**Scope**:
- Create `multichannel.listing.inventory.sync` wizard
- Wizard: Read stock levels from `stock.quant` for product
- Wizard: Apply `multichannel.listing.available_qty_override` if set (operator override)
- Wizard: PUT inventory to Etsy API (`/listings/{id}/inventory`)
- Wizard logs to sync.health (qty_synced, override_applied)
- Idempotent: Re-running wizard updates inventory without creating duplicates

**Exit Criteria**:
- [ ] Wizard in `custom_addons/multichannel_hub_listing/wizards/`
- [ ] Phase 1 (DB tests): 25+ tests GREEN (stock.quant lookup, override logic, idempotency)
- [ ] Phase 2 (ORM tests): 15+ tests GREEN (API PUT, sync.health logging)
- [ ] `multichannel.listing.available_qty_override` field (Integer, nullable) for manual override
- [ ] Wizard displays current stock + override; allows operator to confirm
- [ ] API PUT includes SKU (from product.default_code) + quantity
- [ ] Module update: exit 0

**Test Plan**:
1. Create stock.quant: product_id=P1, location_id=Warehouse, qty=100
2. Run inventory sync wizard; verify 100 pushed to Etsy API
3. Set available_qty_override=75; re-run wizard; verify 75 pushed (not 100)
4. Clear override; re-run; verify 100 restored
5. Verify idempotent (no error on re-run)

---

#### P1.4.4 — P-PUB-PUBLISH (Publish State Transition)

**Owner**: Dev  
**Estimated Duration**: 2 days  
**Dependencies**: P-PUB-INVENTORY complete  
**Blocking**: P-PUB-E2E

**Scope**:
- Extend `multichannel.listing` state machine: `draft` → `active` (publish button)
- Publish button: Call Etsy API state-transition endpoint (mark listing as active)
- Publish: Update `multichannel.listing.publication_state='active'`, `published_date=now()`
- Publish: Update `product.channel.status.publish_status='active'`
- Log to sync.health (publish_count, published_listing_ids)

**Exit Criteria**:
- [ ] State machine on `multichannel.listing.state` (draft → active transitions)
- [ ] Publish button in listing form view (only enabled if state='draft')
- [ ] Phase 1 (DB tests): 10+ tests GREEN (state transition, date stamp)
- [ ] Phase 2 (ORM tests): 10+ tests GREEN (channel status update)
- [ ] API call to publish endpoint (exact endpoint TBD in Etsy v3 spec)
- [ ] Module update: exit 0

**Test Plan**:
1. Create draft listing; verify state='draft'
2. Click publish button; verify Etsy API called
3. Verify multichannel.listing.state='active' + published_date set
4. Verify product.channel.status.publish_status='active'
5. Verify sync.health log includes published listing_id

---

#### P1.4.5 — P-PUB-E2E (End-to-End Publish Pipeline Validation)

**Owner**: Dev (E2E test runner)  
**Estimated Duration**: 5–7 days  
**Dependencies**: P-PUB-PUBLISH complete  
**Blocking**: Production release

**Scope**:
- Author Playwright E2E script: `scripts/e2e_etsy_publish_pipeline.py` (or similar)
- Full workflow: Create product → Create listing → Draft → Images → Inventory → Publish → Verify on Etsy
- E2E runs on staging against sandbox shop
- All 5 publish steps must complete successfully; timing <5 min end-to-end
- Verify published listing visible on Etsy Sandbox (manual spot-check)

**Exit Criteria**:
- [ ] E2E script written in `scripts/e2e_etsy_publish_pipeline.py` (or Python test runner)
- [ ] Phase 1 (Script infrastructure): All 5 steps execute without errors
- [ ] Phase 2 (Validation): Verify listing title/description/price/images match Odoo input
- [ ] All 5 sections PASS on staging
- [ ] Timing logged; average <5 min end-to-end
- [ ] Error paths tested (API 4xx/5xx responses, timeout recovery)
- [ ] Script documented for ops use (manual re-run capability)

**Test Plan**:
1. Staging: Create product with 2 variants
2. Run E2E script start-to-finish
3. Verify all steps complete in <5 min
4. Verify final listing visible on Etsy Sandbox (manual check via browser)
5. Test error recovery: Simulate API timeout at each step; verify retry logic
6. Test rollback: Failed publish should leave listing in draft state (not orphaned)

---

### P1.5: Excel Catalog Sync Foundation (Weeks 8–10, Parallel with P1.4)

**Goal**: Implement daily catalog sync from shop Excel export; unblock inventory writeback loop.

#### P1.5.1 — P-HUB-XLS-PARSE (Excel Parser)

**Owner**: Dev  
**Estimated Duration**: 4 days  
**Dependencies**: P-HUB-PROD-MODEL complete  
**Blocking**: P-HUB-XLS-INGEST

**Scope**:
- Create Excel parser service (ORM-free) in `services/excel_parser.py`
- Parser reads shop Excel export (format: Etsy Shop Manager export)
- Extract rows: product_id, sku, title, description, price, quantity, category, tags, images, variants
- Validate required fields; collect errors/warnings
- Return structured JSON: `{products: [{id, sku, title, ...}], errors: [...], warnings: [...]}`
- Parser handles format drift: column reordering, missing columns, empty rows

**Exit Criteria**:
- [ ] `services/excel_parser.py` (100+ lines, ORM-free)
- [ ] Phase 1 (Unit tests): 50+ tests GREEN (parsing, validation, error recovery)
- [ ] Parser handles 5K+ rows without timeout (<10 sec per 1K rows)
- [ ] All 50 Etsy export columns mapped to Odoo fields (or ignored with warning)
- [ ] Error messages clear for operators (column name + row number + reason)
- [ ] Supports variant rows (child rows linked to parent via indentation/reference)

**Test Plan**:
1. Parse valid Excel; verify all products extracted
2. Parse with missing required column; verify error message
3. Parse with reordered columns; verify correct mapping
4. Parse 5K rows; verify <10 sec completion time
5. Parse with variant rows; verify parent/child structure preserved

---

#### P1.5.2 — P-HUB-XLS-INGEST (Excel Ingest)

**Owner**: Dev  
**Estimated Duration**: 5 days  
**Dependencies**: P-HUB-XLS-PARSE complete  
**Blocking**: P-HUB-XLS-CRON, P-HUB-IMAGES

**Scope**:
- Create ingest wizard `multichannel.listing.ingest.wizard` (transient)
- Wizard step 1: Upload Excel file
- Wizard step 2: P-HUB-XLS-PARSE (preview errors)
- Wizard step 3: Confirm ingest (preview first 10 products)
- Ingest logic: For each product row:
  - Match etsy_listing_id (from `multichannel.listing` existing records)
  - Create new `multichannel.listing` if not found
  - Create/update `multichannel.listing.variant` records (idempotent via SKU)
  - Store sync metadata (imported_source='excel', import_date, import_session_id)
- Idempotent: Re-running same Excel creates 0 duplicates (SKU match prevents doubles)
- Log to sync.health (import_count, update_count, error_count)

**Exit Criteria**:
- [ ] Wizard in `custom_addons/multichannel_hub_listing/wizards/`
- [ ] Phase 1 (DB tests): 40+ tests GREEN (ingest logic, idempotency, duplicate handling)
- [ ] Phase 2 (ORM tests): 30+ tests GREEN (sync.health logging, parent/child hierarchy)
- [ ] Wizard form: 3-step flow with progress
- [ ] Preview step shows first 10 products (with thumbnail images if available)
- [ ] Ingest logs sync metadata (`imported_source`, `import_date`, `import_session_id`)
- [ ] Idempotent: Re-ingest same Excel file creates 0 new records
- [ ] Module update: exit 0

**Test Plan**:
1. Upload Excel with 100 products; verify all created as multichannel.listing
2. Modify 5 products (change price/qty); re-upload; verify 5 updated, 0 new created
3. Add 10 new products; re-upload; verify 10 created, 95 unchanged
4. Verify all listings linked to correct variants (SKU match)
5. Verify sync.health shows import_count=100 (first ingest), update_count=5 (second ingest)

---

#### P1.5.3 — P-HUB-XLS-CRON (Scheduled Catalog Sync)

**Owner**: Dev  
**Estimated Duration**: 2 days  
**Dependencies**: P-HUB-XLS-INGEST complete  
**Blocking**: P-HUB-IMAGES

**Scope**:
- Create cron job `_cron_sync_etsy_catalog_from_excel()` in `models/multichannel_listing.py`
- Cron schedule: Daily (14:00 UTC, non-peak Etsy hours)
- Cron polls GDrive folder for latest Excel export (Spec 010 + GDrive polling P1-09)
- Download Excel → Parse → Ingest (using P-HUB-XLS-PARSE + P-HUB-XLS-INGEST)
- Log results to sync.health (imported_products, updated_products, errors)
- Error handling: Mail notification to admin if import fails

**Exit Criteria**:
- [ ] Cron method in `models/multichannel_listing.py`
- [ ] `ir_cron_data.xml` entry: `etsy_catalog_sync_from_excel` (daily, 14:00 UTC)
- [ ] Phase 1 (Unit tests): 15+ tests GREEN (cron execution, GDrive download, parse + ingest)
- [ ] Phase 2 (Integration tests): 10+ tests GREEN (error handling, mail notification)
- [ ] Cron logs to sync.health (import_count, update_count, error_count)
- [ ] Module update: exit 0

**Test Plan**:
1. Mock GDrive download; trigger cron manually; verify parse + ingest
2. Simulate GDrive failure; verify mail notification sent to admin
3. Simulate parse error; verify error logged, cron continues
4. Verify sync.health log after cron completion

---

#### P1.5.4 — P-HUB-IMAGES (Image Download from Etsy)

**Owner**: Dev  
**Estimated Duration**: 4 days  
**Dependencies**: P-HUB-XLS-INGEST complete  
**Blocking**: P-PUB-IMAGES

**Scope**:
- Extend Excel ingest to download listing images from Etsy CDN
- For each listing row in Excel: Extract image URLs (if provided)
- Batch download images in parallel (asyncio or threading, max 10 concurrent)
- Store images as ir.attachment (linked to multichannel.listing.image_ids)
- Idempotent: Re-download same image skips if checksum matches
- Log to sync.health (images_downloaded, images_skipped, download_errors)

**Exit Criteria**:
- [ ] Image download logic in `services/image_downloader.py` (extended from Spec 001)
- [ ] Phase 1 (Unit tests): 25+ tests GREEN (download, checksum, idempotency, error recovery)
- [ ] Phase 2 (Integration tests): 15+ tests GREEN (ir.attachment linkage, batch downloads)
- [ ] Download timeout: 30 sec per image (skip on timeout, log warning)
- [ ] Checksum validation: SHA-256 hash prevents duplicate downloads
- [ ] Batch parallelism: Max 10 concurrent downloads (configurable ICP)
- [ ] Module update: exit 0

**Test Plan**:
1. Excel with 5 product images; run ingest; verify all downloaded and attached
2. Re-run ingest with same Excel; verify 0 new downloads (checksum match)
3. Change 1 image URL; re-run; verify 1 new download
4. Simulate CDN timeout; verify timeout logged, other images still downloaded
5. Verify image_ids linked to multichannel.listing records

---

## P2: Operational Hardening (22 items)

### Dispatch Sequence: P2.1 → P2.2 → P2.3 (Parallel Tracks)

---

### P2.1: Phase 1 Polish & Exit Criteria (10 items)

**Goal**: Complete Phase 1 exit criteria; stabilize dashboards and design workflows.

#### P2.1.1 — P1-07 (Vietnamese i18n Completion)

**Owner**: Dev + Owner (i18n translations)  
**Estimated Duration**: 5 days  
**Dependencies**: None (parallel with other P2 items)  
**Blocking**: Phase 1 exit gate

**Scope**:
- Complete Vietnamese translation (`i18n/vi_VN.po`) for all new Phase 1 models + views
- Translate all dashboard labels, column headers, status values, error messages
- Translate address-change approval workflow (state machine values, mail templates)
- Translate design file kanban columns + approval workflow labels
- Verify UTF-8 preservation in Excel round-trip (diacritics)

**Exit Criteria**:
- [ ] `i18n/vi_VN.po` line count ≥500 (complete coverage)
- [ ] All new models have Vietnamese field labels + view labels
- [ ] All status values (design states, address-change states, pipeline states) translated
- [ ] Error messages translated (constraint violations, validation errors)
- [ ] Mail templates translated (address-change approval, design rejection)
- [ ] CI check passes: `ruff check` + `odoo -d namco_odoo19 --test-tags=-at_install -i 18n --stop-after-init`
- [ ] Manual QA: Dashboard + design workflow render correctly in Vietnamese

**Test Plan**:
1. Set Odoo locale to Vietnamese
2. Load dashboard; verify all labels Vietnamese
3. Trigger address-change workflow; verify all messages Vietnamese
4. Upload Excel with Vietnamese text; verify round-trip preserves diacritics
5. Trigger design rejection; verify mail template Vietnamese

---

#### P2.1.2 — P1-01b (Order-Line Dashboard Refactor)

**Owner**: Dev  
**Estimated Duration**: 4 days  
**Dependencies**: P4-01-D complete (Gearment adapter requires line-level bulk actions)  
**Blocking**: None (polish, not critical path)

**Scope**:
- Refactor Order Dashboard granularity from `sale.order` to `sale.order.line`
- Add bulk action "Mark as Priority" on order lines
- Add bulk action "Route to Gearment" (links to Gearment fulfillment workflow)
- Update dashboard view: group-by order, expand lines inline
- Update chatter: field tracking at line level (qty, design_status, fulfillment_route)

**Exit Criteria**:
- [ ] Order Dashboard view refactored to `sale.order.line` granularity
- [ ] Bulk action "Mark Priority" implemented; updates `sale.order.line.x_priority_flag`
- [ ] Bulk action "Route to Gearment" implemented; updates fulfillment_route
- [ ] Phase 1 (DB tests): 20+ tests GREEN (line granularity, bulk actions)
- [ ] Phase 2 (ORM tests): 15+ tests GREEN (chatter tracking, field updates)
- [ ] Dashboard rendering: <3 sec for 17K lines (performance test)
- [ ] Module update: exit 0

**Test Plan**:
1. Load Order Dashboard; verify lines visible (grouped by order)
2. Select 5 lines; bulk mark as priority; verify x_priority_flag set
3. Select 5 lines; bulk route to Gearment; verify fulfillment_route set
4. Verify chatter logs line-level updates (qty, priority, route changes)
5. Performance test: Load 17K lines; verify <3 sec render time

---

#### P2.1.3 — P1-02d (A4 Batch Print Layout)

**Owner**: Design + Dev (template creation)  
**Estimated Duration**: 3 days  
**Dependencies**: None  
**Blocking**: None (polish, not critical)

**Scope**:
- Create A4 batch print template for design files (QWeb report)
- Template: 4-up layout (4 designs per A4 page)
- Template fields: Product image thumbnail, design_file.file_url (preview), personalization text, order_id, customer name
- Template output: PDF, can batch-print via "Print > Batch Print Designs"

**Exit Criteria**:
- [ ] QWeb report template in `custom_addons/design/reports/design_batch_print_a4.xml`
- [ ] Report registration: `ir.actions.report` with report_name='design.batch_print_a4'
- [ ] Phase 1 (Report tests): 10+ tests GREEN (PDF generation, 4-up layout)
- [ ] Manual QA: Print 20 designs; verify 5 pages, correct 4-up layout
- [ ] Module update: exit 0

**Test Plan**:
1. Create 4 design.file records
2. Select all 4; run batch print action
3. Verify PDF generated with 4-up layout (1 page)
4. Create 9 design.file records
5. Run batch print; verify PDF with 3 pages (4+4+1 layout)

---

#### P2.1.4 — P1-DESIGN-AUTO-ARCHIVE (Auto-Archive Design Files)

**Owner**: Dev  
**Estimated Duration**: 3 days  
**Dependencies**: P-PUB-PUBLISH complete (trigger: listing published)  
**Blocking**: None (polish)

**Scope**:
- Extend `order.design.file` state machine: add `archived` state
- On listing publish (P-PUB-PUBLISH), automatically transition design files to `archived`
- Operator can manually archive via "Archive" button (state: approved → archived)
- Archived designs hidden from queue by default (searchable but filtered out)

**Exit Criteria**:
- [ ] State machine on `order.design.file.state`: approved → archived
- [ ] Trigger on `multichannel.listing.state` publish (draft → active)
- [ ] Phase 1 (DB tests): 15+ tests GREEN (state transition, trigger)
- [ ] Phase 2 (ORM tests): 10+ tests GREEN (archive flag, search filter)
- [ ] Design queue view: Filter excludes archived by default (but can be toggled)
- [ ] Module update: exit 0

**Test Plan**:
1. Create design file; approve state
2. Publish related listing; verify design auto-archived
3. Verify archived design hidden from default queue view
4. Toggle filter to show archived; verify design appears
5. Manually archive design via button; verify state transition

---

#### P2.1.5 — P-DOCS-FLOW-VN (Vietnamese Operator Flow Documentation)

**Owner**: Owner (documentation + process photography)  
**Estimated Duration**: 5–7 days (can run in parallel through E2E)  
**Dependencies**: None (start in parallel; finalize after P-PUB-E2E)  
**Blocking**: None (training, not code)

**Scope**:
- Document complete order ingest → fulfillment → shipment tracking flow for VN team
- Include 6 workflow sections:
  1. Order ingestion from Etsy (API + email fallback)
  2. Design file approval workflow (kanban, batch review)
  3. Address-change approval gate (when to flag, approval flow)
  4. Fulfillment routing (Gearment POD vs internal production)
  5. Shipment tracking update (GKE Excel import, label status)
  6. Reconciliation (daily/weekly/monthly checklist)
- Included: Screenshots, video walkthrough links, troubleshooting FAQ

**Exit Criteria**:
- [ ] `docs/owner/operator-flows/vietnamese-flow-guide.md` (500+ lines, formatted markdown)
- [ ] 10+ screenshots embedded (with alt text)
- [ ] Video walkthrough links (or embedded YouTube)
- [ ] Troubleshooting section: 10+ common issues + resolutions
- [ ] Glossary: Vietnamese + English terms side-by-side
- [ ] Owner approval captured (e.g., Telegram message "Approved, guides ready")

**Test Plan** (UAT walkthrough):
1. New operator reads guide without prior experience
2. Operator navigates dashboard following guide screenshots
3. Operator completes sample order ingest → fulfillment → shipment loop
4. Operator resolves 3 troubleshooting scenarios from guide

---

#### P2.1.6 — T067 (Reconciliation Report)

**Owner**: Dev + BA Lead (reconciliation)  
**Estimated Duration**: 3–5 days  
**Dependencies**: None  
**Blocking**: Staging deploy, T073

**Scope**:
- Create reconciliation wizard `etsy.data.reconciliation.wizard` (transient)
- Wizard: Compare Odoo `SUM(sale.order.amount_total)` per shop vs source Excel totals
- Export CSV: shop name, odoo_sum, excel_sum, difference, % diff, status (pass/review/fail)
- Operator reviews discrepancies; flags for manual investigation if >0.5% drift
- Wizard output: CSV export + mail summary to BA lead

**Exit Criteria**:
- [ ] Wizard in `custom_addons/etsy_integration/wizards/reconciliation_wizard.py`
- [ ] Phase 1 (Unit tests): 20+ tests GREEN (sum calculation, CSV export)
- [ ] Phase 2 (Integration tests): 10+ tests GREEN (mail notification)
- [ ] CSV format: shop, odoo_sum, excel_sum, difference, pct_diff, review_status
- [ ] Wizard detects >0.5% drift; flags for manual review
- [ ] Module update: exit 0
- [ ] BA lead sign-off documented (Telegram or findings.md entry)

**Test Plan**:
1. Create 10 orders with known totals; run reconciliation
2. Verify Odoo sum matches manual calculation
3. Verify CSV export with correct formatting
4. Simulate <0.1% drift; verify pass status
5. Simulate >0.5% drift; verify review status + mail notification

---

#### P2.1.7 — T070 (Module Install Test)

**Owner**: Dev  
**Estimated Duration**: 2 days  
**Dependencies**: T067 complete  
**Blocking**: T073

**Scope**:
- Run fresh DB install: `docker-compose down -v && docker-compose build && docker-compose up`
- Install all modules from scratch (etsy_integration, design, multichannel_hub_*; omit optional modules)
- Verify all modules install cleanly (exit 0)
- Verify all master data loaded (etsy.shop records, shipping.carriers, etc.)
- Verify all views render without errors (dashboards, wizards, forms)

**Exit Criteria**:
- [ ] Fresh DB install: `docker exec namco_odoo19 odoo -d namco_odoo19 -i etsy_integration,design,multichannel_hub_core,multichannel_hub_fulfillment --stop-after-init` → exit 0
- [ ] All master data loaded (≥5 etsy.shop records, ≥3 shipping.carriers)
- [ ] All views accessible via browser (dashboard, wizard, form views load without JS errors)
- [ ] No migration errors or SQL warnings in logs

**Test Plan**:
1. Spin down docker-compose (purge DB volume)
2. Rebuild images
3. Start containers
4. Install modules via Odoo -i flag
5. Access dashboard via browser; verify render
6. Access wizard via form action; verify form loads

---

#### P2.1.8 — T073 (Staging E2E + BA Sign-Off)

**Owner**: Dev + Owner  
**Estimated Duration**: 3 days  
**Dependencies**: T067 + T070 complete  
**Blocking**: Production cutover

**Scope**:
- Full end-to-end on staging environment (19 shops, pilot + additional cutover shops)
- Test complete workflow: Email ingest → design approval → fulfillment routing → tracking → shipment state
- Run E2E demo runner (P0-E2E-DROP-SHIP-RUNNER) on staging; verify 12/12 sections PASS
- BA lead validates reconciliation report (T067)
- Owner approves readiness for production

**Exit Criteria**:
- [ ] E2E demo runner: 12/12 sections PASS on staging
- [ ] Reconciliation report: <0.5% drift on all 19 shops
- [ ] BA lead sign-off: Captured in Telegram or findings.md ("Staging validation passed, approved for production")
- [ ] No regressions from baseline (compare metrics to previous staging snapshot)

**Test Plan**:
1. Restore staging DB from production snapshot
2. Run E2E demo runner (full inbound + fulfillment + tracking loop)
3. Verify all 12 sections PASS
4. Run reconciliation report for all 19 shops
5. BA lead reviews report; approves if <0.5% drift
6. Owner approves production cutover

---

#### P2.1.9 — P3-LEAD-MAIL-ALIAS (Email Alias → Lead Routing)

**Owner**: Dev  
**Estimated Duration**: 3 days  
**Dependencies**: None (off critical path)  
**Blocking**: None

**Scope** (Spec 007, CRM mini):
- Create mail alias configuration (e.g., `leads@hatafax.com` → Odoo lead)
- Implement mail router: Route inbound emails to Odoo leads based on subject/body matching
- Wizard: Operator maps email alias → lead category (product inquiry, return request, etc.)
- Test: Send test email; verify lead created

**Exit Criteria**:
- [ ] Mail alias integration in `multichannel_hub_core` (or new `crm_integration` module)
- [ ] Phase 1 (Unit tests): 15+ tests GREEN (alias routing, lead creation)
- [ ] Phase 2 (Integration tests): 10+ tests GREEN (mail parsing, field extraction)
- [ ] Wizard for alias configuration (UI to map aliases to lead categories)
- [ ] Module update: exit 0

**Test Plan**:
1. Configure mail alias `leads@hatafax.com` → Odoo
2. Send test email with subject "Product Inquiry"
3. Verify lead created with category from alias config
4. Verify lead chatter includes email content

---

#### P2.1.10 — P3-LEAD-API-ROUTING (Etsy Messages → Lead Routing)

**Owner**: Dev  
**Estimated Duration**: 5 days  
**Dependencies**: P1-MSG-API-PULL complete (blocked on conversations_r)  
**Blocking**: None (off critical path)

**Scope** (Spec 007):
- Implement message poller: Fetch Etsy messages via conversations_r API (Spec 005)
- Parse message type (product inquiry, order question, return request)
- Auto-create `crm.lead` records from messages
- Operator workflow: Review leads, follow up, create support ticket if needed

**Exit Criteria**:
- [ ] Message poller in `etsy_integration/services/message_poller.py`
- [ ] Phase 1 (Unit tests): 20+ tests GREEN (API call, message parsing, lead creation)
- [ ] Phase 2 (Integration tests): 15+ tests GREEN (lead assignment, categorization)
- [ ] Cron job: `_cron_sync_etsy_messages()` (hourly after conversations_r approved)
- [ ] Module update: exit 0
- [ ] **BLOCKED ON**: P1-MSG-SCOPE (conversations_r re-submission approval)

**Test Plan**:
1. Fetch test messages from Etsy sandbox API
2. Parse message type; verify categorization
3. Create lead from message; verify fields populated (customer name, message content, order reference)
4. Run cron job; verify messages processed

---

### P2.2: Spec 004a Tracking Import (6 items)

#### P2.2.1 through P2.2.6

[Detailed tasks for P2-01-MODELS, P2-01-WIZARD, P2-01-CARRIER, P2-02-CARRIER-DETECT, P2-03-GKE-SCHEMA, P2-04-SYNC-HEALTH — see spec.md table; flow similar to above]

---

### P2.3: Spec 004b + Supporting Items (6 items)

#### P2.3.1 through P2.3.6

[Detailed tasks for P0-18b2, P4-02, P4-03, T055, T058, ENV-FIX-MRP]

---

## P3: Polish & Reporting (18 items)

**Status**: Deferred post-E2E validation. Dispatch after Phase 1 + 2 exit criteria verified.

[Details for P3 items: T024, T030, T036, T038, T040–T044, T052–T059, P1-MSG-SCOPE, P1-MSG-API-PULL, T060–T064, T065–T066, P5-01–P5-05, P0-20-DOCS, SRS/SDS-REBUILD]

---

## Exit Criteria Summary

### P1 Exit Criteria (Production Cutover Ready)

- [ ] P-HUB-SPEC: Spec authoring complete; 15 implementation slices have detailed tasks
- [ ] P1-11 + P2-07: Pilot shop live on API; email→API cutover proven
- [ ] P2-08: All 19 shops on api_only; 24-hour ingest health > baseline
- [ ] P-HUB-PROD-MODEL: 3 foundation models shipped; 90+ tests GREEN
- [ ] P-PUB-DRAFT through P-PUB-E2E: Complete publish pipeline validated; E2E 5/5 sections PASS
- [ ] P-HUB-XLS-PARSE through P-HUB-IMAGES: Excel sync cron running daily; images downloading
- [ ] All modules: `docker -u <module> --stop-after-init` → exit 0
- [ ] All ruff checks: 0 errors
- [ ] Staging snapshot: Full 19-shop, multi-variant, end-to-end validated

### P2 Exit Criteria (Hardening)

- [ ] P1-07: i18n complete; dashboards render in Vietnamese
- [ ] T067 + T073: Reconciliation report approved by BA lead; staging E2E 12/12 PASS
- [ ] P2-01–P2-04: Tracking import wizard + carrier detection complete; 90+ tests GREEN
- [ ] All P2 modules: exit 0; no regressions vs baseline
- [ ] Monitoring: Sync.health dashboard shows 0 errors for 24+ hours

### P3 Acceptance Criteria (Polish)

- [ ] All P3 items resolved (or explicitly deferred with owner sign-off)
- [ ] Documentation complete: SRS, SDS, architecture diagrams, sequence flows, deployment guide
- [ ] Security: .env secrets redacted; `docs/ENVIRONMENT_VARIABLES.md` authored with credential names only
- [ ] Owner sign-off: "Project complete, ready for handoff"

---

## Dependency Graph

```
P-HUB-SPEC (foundation)
  ├─→ P-HUB-PROD-MODEL (foundation models)
  │     ├─→ P-HUB-WIZARD
  │     ├─→ P-HUB-SKU-DRIFT
  │     └─→ P-PUB-CLIENT (unblocks all publish)
  │
  ├─→ P-HUB-XLS-PARSE
  │     ├─→ P-HUB-XLS-INGEST
  │     │     ├─→ P-HUB-XLS-CRON
  │     │     └─→ P-HUB-IMAGES
  │     │
  │     └─→ (parallel to P-PUB-DRAFT)
  │
  └─→ P-PUB-CLIENT
        ├─→ P-PUB-DRAFT
        │     ├─→ P-PUB-IMAGES
        │     │     ├─→ P-PUB-INVENTORY (depends on P-HUB-SKU-DRIFT)
        │     │     │     └─→ P-PUB-PUBLISH
        │     │     │           └─→ P-PUB-E2E (production gate)
        │     │     │
        │     │     └─→ (image upload parallel to inventory)
        │     │
        │     └─→ (quote received in draft step)

P1-11 (pilot shop)
  └─→ P2-07 (email→API rebind)
        └─→ P1-13 (additional shops)
              └─→ P2-08 (remaining shops cutover)

P1-07 (i18n)
  └─→ (parallel to publish pipeline)

T067 (reconciliation) → T070 (install test) → T073 (staging E2E + BA sign-off) → Production Ready
```

---

## Resource Allocation

**Recommended Dev Team Structure** (4 developers):
- **Dev 1 (Lead)**: P-HUB-SPEC authoring + P-HUB-PROD-MODEL + oversight
- **Dev 2**: P-PUB-CLIENT through P-PUB-E2E (publish pipeline)
- **Dev 3**: P-HUB-XLS-PARSE through P-HUB-IMAGES (Excel sync)
- **Dev 4**: P2 hardening items + P2-01–P2-04 tracking + testing

**Owner + Ops**: P1-11/P1-13/P2-08 shop cutover, P-DOCS-FLOW-VN, owner-side tasks (Gearment keys request, E2 completion)

---

## Timeline Estimate

| Phase | Duration | Cumulative | Go/No-Go Gate |
|-------|----------|------------|---|
| P1.1 (Specs + APIs) | 2 weeks | Week 2 | Spec complete; API client ready |
| P1.2 (Pilot Cutover) | 2 weeks | Week 4 | Pilot live; email→API rebind proven |
| P1.3 (Foundation Models) | 2 weeks | Week 6 | Hub models shipped; tests GREEN |
| P1.4 + P1.5 (Publish + Excel) | 4 weeks | Week 10 | Publish pipeline E2E validated |
| P2 (Hardening) | 2–3 weeks | Week 12–13 | i18n complete; reconciliation approved |
| **Total to Production** | **10–13 weeks** | Late August 2026 | Full E2E + BA sign-off |

*Notes*:
- Parallel P1.4 + P1.5 (publish + Excel) reduces timeline to week 10 vs sequential week 12
- P2 items overlap with P1 final stages (no additional delay)
- P3 (polish) deferred post-production (4–6 additional weeks for Amazon/website/inventory)
- Gearment API keys (E2) must arrive by week 4 (blocks P1-11 round-trip verify)

---

## References

- **Master Plan 006 Tracker**: `.claude/plans/006-master-plan-tracking.md`
- **Implementation Playbook**: `.claude/plans/006-implementation-playbook.md`
- **Specs Directory**: `specs/001–014/` (historical; Spec 015 supersedes)
- **Module Code**: `custom_addons/etsy_integration/`, `custom_addons/multichannel_hub_*/`, `custom_addons/design/`
