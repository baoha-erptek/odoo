# Feature Specification: Central Product Hub (Spec 009)

- **Feature Branch**: work lands on `feature/006-master-plan-coding` (Master Plan 006 Phase 3)
- **Created**: 2026-05-23
- **Status**: PLANNED — planning slice (P-HUB-SPEC) authoring; implementation slices `todo`
- **Authority**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md)
- **Input**: MP006 tracker Phase 3 (new); plan file `.claude/plans/actually-need-to-check-polymorphic-crayon.md`

## Overview

Make Odoo the system of record for the multichannel catalog. Add channel applicability + pricing-bookkeeping + SKU drift fields to `product.template`. Introduce the channel-agnostic `multichannel.sales.channel` reference model and the per-(product, channel) `product.channel.status` mirror. Ship a product-creation wizard that validates new entries against the SKU grammar v2, category, prices, and production mode. Ship a non-destructive backfill from the existing `etsy.listing` mirror.

**This spec is the foundation**. Spec 010 (catalog Excel recurring sync) and Spec 011 (Etsy outbound publish) build on top of it.

Out of scope (deferred to other specs):
- Excel parser / ingestor / cron / image download → Spec 010
- Etsy outbound API writes (createDraftListing, image upload, inventory PUT, publish) → Spec 011
- Amazon + ecommerce channel publishers → future MP / Phase 5
- BA-side Odoo authoring UI (replace Excel) → post-MP006 evolution per ADR-014 §evolution

## User Scenarios & Acceptance Criteria

### US1 — Channel Applicability on a Product (P1)

As a BA, I want to mark a product as "publishable on Etsy" (and later Amazon, website) so the system knows where to push it.

**Acceptance Criteria**
1. Given a `product.template`, When I tick "Etsy" in `x_channel_applicability_ids`, Then the product becomes eligible for the Etsy publisher.
2. Given a product with empty `x_channel_applicability_ids`, When the publisher cron runs, Then the product is skipped (no draft listing created).
3. Given a product on Etsy already, When `x_channel_applicability_ids` removes Etsy, Then no automatic archive happens (operator decides); `product.channel.status` row stays so re-tick restores linkage.
4. Given a `multichannel.sales.channel` record is `active=False`, Then it doesn't appear in the M2M picker.

### US2 — Pricing & Cost Bookkeeping (P1)

As a BA, I want the Excel-sourced price + shipping + additional-cost values reflected on the product so margin reporting works.

**Acceptance Criteria**
1. Given Excel has Price USD = 24.00, Shipping = 5.00, Other costs = 2.00 for a SKU, When import lands (Spec 010), Then `product.template.x_listing_price = 24.00`, `x_shipping_price_internal = 5.00`, `x_additional_cost = 2.00`.
2. Given a product with these fields, When I open its form, Then a computed `x_unit_margin = x_listing_price - standard_price - x_shipping_price_internal - x_additional_cost` is visible.
3. Given a sale order is created, Then pricing comes from `product.pricelist` (channel-keyed), NOT from `x_listing_price` (ADR-014 §2).

### US3 — Product Creation Wizard (P1)

As a BA, I want a guided creation wizard that refuses to save half-configured products.

**Acceptance Criteria**
1. The wizard requires: `name`, `default_code` (SKU), `categ_id`, `x_listing_price > 0`, `x_shipping_price_internal >= 0`, and at least one channel in `x_channel_applicability_ids`.
2. Production mode is auto-derived: if `x_gearment_sku` is non-empty → Dropship; else → MTO (ADR-010 invariant; `x_gearment_sku` already auto-applies route + Gearment seller).
3. The wizard computes and displays `x_sku_v2_suggested` from the entered `name` next to the entered `default_code`; non-canonical entries show `x_sku_v2_status = 'non_canonical'` but do NOT block save (ADR-014 §4).
4. Saving via the wizard creates the `product.template` + the `product.channel.status` rows for each ticked channel (initial state `draft`).
5. The wizard is system-gated to BA group(s); non-BA users can edit existing products but cannot launch the create wizard (FR-017 method-top gate at the action level).

### US4 — SKU Drift Review (P1)

As a BA, I want a list view of products whose SKU doesn't match grammar v2, so I can reconcile on my own schedule.

**Acceptance Criteria**
1. Tree view filtered to `x_sku_v2_status in ('non_canonical', 'msc_catchall')` shows: `name`, `default_code`, `x_sku_v2_suggested`, `categ_id`, channel applicability.
2. Per-row wizard `product.sku.canonicalise.wizard` exposes **Keep legacy** (writes `x_sku_v2_status = 'ba_approved_legacy'`) and **Accept canonical** (moves `default_code` → `x_sku_legacy`, writes `x_sku_v2_suggested` → `default_code`).
3. When **Accept canonical** runs on a product with a linked active Etsy listing, the wizard synchronously fires the Etsy SKU update path (Spec 011 P-PUB-INVENTORY surface); if the push fails, the canonicalisation rolls back and a durable audit row stays.
4. Audit: each transition posts a chatter message on the product and an `etsy.api.log` row when the Etsy push fires.

### US5 — Etsy Backfill (P1)

As a BA, I want existing live Etsy listings to gain Odoo `product.template` twins so I can manage them from the hub.

**Acceptance Criteria**
1. Wizard `etsy.listing.backfill.wizard` reads `etsy.listing` + `etsy.listing.product` per shop.
2. For each variant with a matched `product.product.etsy_listing_variant_id` (already populated by P-LIST-INV-PULL), the wizard ensures the parent `product.template` exists and has `x_channel_applicability_ids` containing the listing's shop's channel.
3. For each variant whose FK is NULL (unmatched), the wizard either:
   - Creates a new `product.template` with `default_code = variant.sku` and links the variant, OR
   - Flags the variant as "Etsy-only — needs BA decision" in a follow-up report (BA chooses per-variant in the wizard).
4. No re-publish to Etsy, no archive, no inventory writeback during backfill — the wizard is read-only against Etsy.
5. Backfill is idempotent: running twice produces no duplicates and no extra chatter spam.

### US6 — Channel Status Visibility (P2)

As an operator, I want to see at a glance which channels a product is published on.

**Acceptance Criteria**
1. Product form has a "Channels" tab listing `product.channel.status` rows: channel, state (draft / published / archived), linked channel-side record (e.g. `etsy.listing` ID), last sync timestamp.
2. Smart button on product form shows count of channels where state = `published`.
3. Per-channel state transitions are written by the publisher service (Spec 011 for Etsy); the product form is read-only for state.

## Channel Scope

Etsy first (Spec 011 implements the Etsy half). The model is channel-agnostic so future Amazon + ecommerce publishers reuse `multichannel.sales.channel` + `product.channel.status` without `product.template` schema change.

## Dependencies

- ADR-014 accepted (this slice's authority).
- ADR-013 + Spec 008 already shipped (`etsy.listing`, `etsy.listing.product`, `product.product.etsy_listing_variant_id`) — backfill US5 reads from these.
- ADR-010 already shipped (`x_gearment_sku` → MTO/Dropship route auto-apply; product_mto_bom_wizard) — US3 wizard reuses, does not replace.
- SKU grammar v2 frozen at `.0temp/deliverables/A3_grammar_v2_frozen.md` + `D1_product_taxonomy_SKU.xlsx` (machine-readable `family_rules` sheet).
- No new external dependency.

## Non-Functional Requirements

- New `multichannel.sales.channel` rows: ≤ 10 channels lifetime (Etsy, Amazon, website, + few). No volume concern.
- `product.channel.status` row count = (active products) × (channels they're on). Catalog at ~500–2000 products × ~3 channels max → bounded.
- SKU-drift list view + grammar v2 regex compute: ≤ 200 ms for catalog of 2000 products on form open.
- Backfill wizard run time: ≤ 30 s for JaHandmadeArt (1 listing × 5 variants); should scale linearly for larger shops.
