# Feature Specification: Etsy Listings & Inventory Sync

- **Feature Branch**: work lands on `feature/006-master-plan-coding` (Master Plan 006)
- **Created**: 2026-05-16
- **Status**: PLANNED — Phase 1 planning slice (P-LIST-SPEC) complete; implementation slices `todo`
- **Authority**: [ADR-013](../006-master-plan/adrs/ADR-013-etsy-listing-architecture.md)
- **Input**: MP006 tracker P-LIST-SPEC; roadmap `check-for-claude-plans-006-master-plan-t-serene-wreath.md` §"Wave 2 — Listings / inventory sync", decision D-C

## Overview

Read-only ingestion of Etsy shop **listings** (metadata) and **variant inventory** (the `products[]` matrix), plus **drift detection** against the Odoo product catalog. No writeback to Etsy in this spec — that is the deferred Phase 3 (P-LIST-INV-PUSH).

Enables:
- A queryable mirror of what Etsy currently lists per shop.
- A timestamped variant-inventory snapshot (prerequisite for the entire-array-resubmit write path).
- Drift detection: unlinked variants, qty/price mismatch, orphan Odoo products.

Out of scope (deferred):
- Listing inventory writeback (`PUT .../listings/{id}/inventory`) → P-LIST-INV-PUSH.
- Listing create/delete/deactivation from Odoo → later phase (ADR-013 owner Q-b: defer; read-only for now).
- Bulk SKU-linking wizard → follow-up (P-LIST-SKU-LINK-WIZARD).

## User Scenarios & Acceptance Criteria

### US1 — Etsy Listing Metadata Ingestion (P1)

As a shop operator, I want all active Etsy listings for my shop fetched and stored with their metadata, so I can see what Etsy currently lists.

**Acceptance Criteria**
1. Given a shop with valid API tokens, When `cron_etsy_listing_sync` runs, Then listings from `GET /v3/application/shops/{shop_id}/listings` are stored in `etsy.listing`.
2. Given a listing already stored, When re-fetched, Then status/title/price are updated; `created_at`/`url` are never overwritten.
3. Given a listing deleted on Etsy, When the cron runs, Then `etsy.listing.state='deleted'` and `is_active=False` (soft delete, no hard unlink).
4. Given 100+ listings, When the cron runs, Then pagination is used (Etsy limit ~100/page) without timeout.
5. Given an API error, When the sync fails, Then it is logged to `etsy.api.log` (`source='listing_pull'`) and retried next cycle.

### US2 — Listing Variant Inventory Snapshot (P1)

As a fulfillment coordinator, I want each listing's variant matrix (sku, qty, price, properties) stored as a timestamped table, so drift detection and the future push have a local source of truth.

**Acceptance Criteria**
1. Given a listing with N variants from `GET /v3/application/listings/{listing_id}/inventory`, When the cron runs, Then each variant is a row in `etsy.listing.product` (sku, quantity, price, `property_values` JSON).
2. Given a variant qty changed on Etsy, When re-synced, Then `etsy.listing.product.quantity` is updated and `last_synced_at` is refreshed.
3. Given a variant added on Etsy, When the cron runs, Then a new `etsy.listing.product` row is created.
4. Given a variant removed on Etsy, When the cron runs, Then the row is marked `is_active=False` (soft delete).

### US3 — Listing↔Product Link via SKU (P2)

As a BA, I want listing variants auto-matched to Odoo products by SKU, so unlinked variants are surfaced for review.

**Acceptance Criteria**
1. Given a variant `sku='HAT-RED-M'`, When ingest runs, Then `product.product` is searched by `(company_id, default_code='HAT-RED-M')`; if found, `product.product.etsy_listing_variant_id` is set.
2. Given a match, When the drift report runs, Then the variant is NOT flagged unlinked.
3. Given no SKU match (or empty SKU), When ingest completes, Then the FK stays NULL and the variant appears in the "unlinked" drift category (ADR-013 owner Q-a: do not auto-create products).
4. Given a manually-linked product, When ingest re-runs, Then the existing FK is not overwritten.
5. Given a multi-variant listing vs. a single non-variant Odoo product, Then only the closest SKU match is linked (ADR-013 owner Q-c); the rest stay unlinked.

### US4 — Drift Detection Report (P1)

As a BA, I want a report of Etsy↔Odoo drift so I can reconcile before any writeback.

**Acceptance Criteria**
1. The report surfaces: (a) variants with NULL FK = `unlinked`; (b) Etsy qty ≠ Odoo qty = `qty_drift`; (c) Odoo products with no Etsy variant = `orphan_product`.
2. Filtering by category returns only that category.
3. With 500+ variants, the report completes in < 2 s (indexed queries per `data-model.md`).

## Channel Scope

Etsy only (E1 grant includes `listings_r/w`). Future channels reuse the standalone-model pattern per ADR-013 — no architectural blocker.

## Dependencies

- Spec 005 landed (Etsy API client + per-shop OAuth working).
- E1 scope review approved 2026-05-12 (`listings_r/w`).
- No new external dependency (endpoints are existing Etsy API v3).

## Non-Functional Requirements

- 100-listing shop syncs within the 5-min cron window.
- Drift report scales to 500+ variants (< 2 s).
- No chatter/audit retention on listing rows (ephemeral mirror); API calls audited via `etsy.api.log`.
