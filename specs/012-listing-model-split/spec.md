# Spec 012 — Listing Model Split (`multichannel.listing`)

**Created**: 2026-06-06
**Owner**: Bao Ha
**Slice**: `P-SPEC-LISTING-MODEL-SPLIT` (parent) + 7 Wave-2 listing-parity slices
**Master Plan**: MP006 Phase 3 Sub-phase 3i (Wave 2)
**Status**: Draft — architecture frozen in ADR-015; Wave-2 slices author their own tasks here
**Decision artifact**: [`ADR-015`](../006-master-plan/adrs/ADR-015-listing-model-split.md)
**Jira parent**: ESTY-187 (6.11 — "Listing module from Odoo to Etsy/Amazon" feedback umbrella)

## Goal

Create the `multichannel.listing` model that holds per-channel/per-shop **listing intent** (taxonomy, who_made, when_made, shipping profile, video, attribute mapping, optional title/description/image overrides), keeping `product.template` as the source of truth for *the product* and `etsy.listing` as the read-only mirror of *what currently exists on Etsy*.

This split is the home for the 7 Wave-2 listing-parity slices from `docs/jira/in-progress-2026-06-04.md`.

## Out of scope

- Per-channel pricing override (handled by ADR-010 +  Spec 009 SKU drift policy).
- Amazon / website channel listings (Amazon `multichannel.listing` rows ship later when the Amazon connector lands; the model is built channel-agnostic so they slot in without re-design).
- Migration of the Excel catalog into Odoo as a write-surface (still recurring import per ADR-014 §3).

## User stories

### US1 — Marketing edits per-listing intent without touching the product master
**As a** Marketing operator on JaHandmadeArt
**I want to** edit the Etsy taxonomy, who_made, when_made and shipping profile for a specific shop
**Without** affecting how the same product publishes on NamcoHome or appears in PD/BA's product master
**So that** each shop can have its own Etsy positioning without forks or duplicated products.

### US2 — Publisher reads the listing layer first, falls back to template
**As a** publisher (system)
**I want to** read overrides from `multichannel.listing` per `(product_tmpl_id, channel_id, shop_ref)` and fall back to `product.template.x_*` or `etsy.shop.default_*` when the override is null
**So that** old products without explicit listing intent still publish identically to today (zero-regression backfill).

### US3 — BA reviews/approves listings before publish
**As a** BA Lead
**I want to** see all `multichannel.listing` rows in state `draft` or `ready` filtered by shop
**So that** I can bulk-approve a release of new listings (the home for `P-LIST-SHOP-BULK`).

### US4 — Etsy taxonomy node cache + lookup
**As a** Marketing operator
**I want to** search Etsy taxonomy nodes by name when picking a category for a listing
**So that** I don't have to remember Etsy's 4-billion taxonomy IDs.

### US5 — Etsy shipping profile cache + per-shop default
**As a** Marketing operator
**I want to** pick a shipping profile from a dropdown that's already synced from the shop
**So that** I never type a shipping profile ID by hand and never publish with the wrong one.

### US6 — Attribute matching configurable per shop AND per listing
**As a** Marketing operator
**I want to** override the global `product.attribute → Etsy property_id` mapping for a specific listing
**So that** an edge-case product can map "Color" to a different Etsy property than the company default.

### US7 — One video per Etsy listing
**As a** Marketing operator
**I want to** upload one video to `multichannel.listing.video_attachment_id`
**So that** the publisher pushes it via `POST /shops/{id}/listings/{id}/videos` after the listing exists on Etsy.

### US8 — Backfill existing live listings non-destructively
**As an** Admin running the upgrade
**I want** the model-split migration to create a stub `multichannel.listing` row for every existing template that has an active `etsy.listing` or `product.channel.status` row
**So that** existing publish chain continues to work unchanged on day 1 of the upgrade.

### US9 — ACL respects the BA / Marketing split
**As a** BA Lead I should be able to see (read-only) the listing intent rows attached to my products, but not edit them.
**As** Marketing I should have RW on listing intent but read-only on the underlying product master.
**So that** each role owns its surface without territory wars.

### US10 — Owner docs make the split obvious
**As a** new operator
**I want to** read in `HUONG_DAN_TAO_SAN_PHAM_VN.md` the difference between "Sản phẩm" (product master) and "Listing" (per-shop listing intent)
**So that** I know where to set the Etsy category, shipping profile, or per-shop title.

## Acceptance criteria (per slice)

The 7 Wave-2 slices each satisfy a slice-scoped acceptance criterion that builds on US1-US10:

| Slice | US covered | Acceptance criterion |
|---|---|---|
| `P-SPEC-LISTING-MODEL-SPLIT` (this slice) | US1, US2, US8, US9 | `multichannel.listing` model exists; backfill creates 1 stub row per existing template with an active `etsy.listing`; ACLs gated per ADR-015 §4; publisher reads via the new layer with fallback. Zero behavior change for existing publish. |
| `P-LIST-CATEGORY` | US4 | `etsy.taxonomy.node` cache populated from `GET /seller-taxonomy/nodes`; `multichannel.listing.etsy_taxonomy_id` M2O→cache; publisher pulls from listing override → falls back to `etsy.shop.default_taxonomy_id`. |
| `P-LIST-SHIPPING` | US5 | `etsy.shipping.profile` cache populated from `GET /shops/{id}/shipping-profiles`; `multichannel.listing.etsy_shipping_profile_id` M2O→cache; publisher uses listing override → shop default. |
| `P-LIST-HOW-ITS-MADE` | US1 | `multichannel.listing.etsy_who_made` / `_when_made` / `_is_supply` fields + form view; publisher reads listing override → product.template fallback → shop default. |
| `P-LIST-ATTRIBUTES` | US6 | Publisher resolves `product.attribute → Etsy property_id` via `multichannel.listing.attribute_mapping_ids` override before falling back to the existing `product.attribute.x_etsy_property_id` global. |
| `P-LIST-ATTR-CONFIG` | US6 | New shop config view + form for `etsy.shop.default_attribute_mapping_ids` (shop-wide defaults); Wave-2 ATTRIBUTES slice falls back to this layer when no listing override. |
| `P-LIST-VIDEO` | US7 | `multichannel.listing.video_attachment_id` Binary/M2O; new `push_video(listing)` method in publisher; orchestrator wires it after `push_inventory`; one-video-per-listing Etsy cap enforced. |
| `P-LIST-SHOP-BULK` | US3 | `multichannel.listing` list view has filter "Shop = X"; server-action bulk-edit `multichannel.listing.state` from draft → ready. |

## Module ownership

Per ADR-003 + ADR-015 §5:

- `multichannel.listing` + sub-models + base views → `multichannel_hub_core`
- Etsy-specific overrides on `etsy.shop.default_*` → `etsy_integration`
- Wave-2 slices ship migrations under both modules as needed; backfill of stub rows for existing templates ships in `multichannel_hub_core/migrations/<version>/post-migrate.py`.

## Cross-cuts

- **ADR-013** stays intact: `etsy.listing` remains the read-only mirror. After successful `create_draft`, the publisher writes `multichannel.listing.external_ref = etsy.listing.etsy_listing_id` so the join is queryable.
- **ADR-014 §1** unchanged: `product.template.multichannel_sales_channel_ids` M2M is the channel applicability flag; `multichannel.listing` rows can only exist for channels listed there.
- **Memory `feedback_standard_odoo_first.md`**: every new field added by a Wave-2 slice MUST run the standard-Odoo check before adding.
