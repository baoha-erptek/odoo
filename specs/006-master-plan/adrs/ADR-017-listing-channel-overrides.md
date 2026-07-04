# ADR-017: Shop-level listing defaults (Title/Description/Image) extend the three-layer fallback chain

- **Status**: Accepted
- **Date**: 2026-06-07
- **Sign-off**: pending (spec mini-slice doc — owner ratifies via code-slice dispatch approval)
- **Deciders**: Owner, orchestrator (Sonnet inline)
- **Affects**: `P-ENH-ESTY-190` (this slice's code child), per-shop marketing brand personalization
- **Related**: [ADR-015](ADR-015-listing-model-split.md) (listing-model split and two-layer fallback), [ADR-016](ADR-016-listing-currency-display.md) (per-shop currency), [ADR-003](ADR-003-module-decomposition.md) (channel-agnostic models live in `multichannel_hub_core`)

## Context

ADR-015 established the listing-model split (spec 012, P-LIST-MODEL) and defined a two-layer marketing-field fallback:

```
multichannel.listing.title (per-listing override)
  → product.template.name (per-product canonical)
```

This allows Marketing to customize the title per listing (per-channel per-shop), with fallback to the product canonical.

The remaining gap is **per-shop brand voice**: when multiple Etsy shops sell the same product, each shop may need a distinct marketing narrative without requiring Marketing to duplicate the product row per shop. The current tracker's suggestion of a new `mhc.product.channel.copy` model is **stale** — P-LIST-MODEL already supplies the per-shop override mechanism via `multichannel.listing` (uniquely keyed on (product, channel, shop)).

Standard-Odoo-First check: no CE module ships per-shop marketing defaults. Solution is custom-but-thin: add three nullable fields to `etsy.shop` as the final fallback layer.

## Decision

### D1 — Three-layer fallback chain (shop-level default is the 3rd layer)

Extend the ADR-015 two-layer chain with a third layer at the shop level:

```
Level 1 (highest priority): multichannel.listing.title        (per-listing, per-channel, per-shop)
Level 2 (middle):           product.template.name             (per-product, canonical)
Level 3 (lowest priority):  etsy.shop.default_title           (per-shop, brand voice default)
→ Empty string (when all three are empty)
```

**Rationale**: 
- Listing overrides express Marketing's highest-priority decision (specific copy for this listing in this context).
- Product defaults are the BA-canonical source (centralized product definition).
- Shop defaults are the Marketing-owned brand voice (shop-global fallback when listing and product are empty).
- Three distinct layers match the role boundaries: BA owns product, Marketing owns both listing and shop.

### D2 — Shop-level defaults live on `etsy.shop`, NOT a new model

Three new fields on `etsy.shop`:
- `default_title` (Char, max 140, nullable)
- `default_description` (Text, nullable)
- `default_image_1920` (Image, nullable)

NO new model. NO M2O or O2M relationship. Simple column additions per shop.

**Rationale**:
- The tracker's note mentioned a new `mhc.product.channel.copy` model, but that's redundant. P-LIST-MODEL already supplies a per-(product, channel, shop) row via `multichannel.listing`, uniquely indexed on that tuple. Adding a second model with the same cardinality duplicates the design.
- Shop-level config follows the existing pattern on `etsy.shop` (`default_taxonomy_id`, `default_shipping_profile_id`, `default_readiness_state_id`).
- `ir.config_parameter` is for system-global config; `etsy.shop` fields are for per-shop config. Correct choice here.

### D3 — No new listing-level fields

The existing `multichannel.listing.title`, `.description`, `.image_1920` fields (added in P-LIST-MODEL) are already the per-listing marketing overrides. They are keyed by (product, channel, shop) via the UNIQUE INDEX. No additional field layer needed — reuse them exactly as they are.

**Rationale**: P-LIST-MODEL was designed as the marketing-override surface. The docstring on those fields already names the fallback chain (empty listing → product fallback). Layering shop defaults is an extension of the chain; no new model or field.

### D4 — Publisher emits DEBUG log naming the resolved level

When publisher calls `_resolve_title_with_shop_fallback()` (or similar methods for description and image), the method:
- Returns the value from whichever layer is non-empty (listing → product → shop → '').
- Emits DEBUG log only if it fell back from listing (i.e., final value != listing.title).
- Log format: `"multichannel.listing %s: resolved title from [listing|product|shop] (shop_id=%s)"`

**Rationale**: Operators need visibility into which level the final value came from, especially when debugging mismatched copy on a live listing. DEBUG level keeps the logs quiet by default; enabled only on investigation.

### D5 — No migration required (forward-compatible nullable columns)

Adding nullable columns to `etsy.shop` requires no migration. Existing shops get NULL for the new fields.

Optional: seed data can pre-populate demo shops with example defaults.

**Rationale**: Nullable fields are forward-compatible. Back-fill would be unnecessary — NULL means "use the layer below" (product or listing).

### D6 — Field placement on etsy.shop form near existing defaults

The three new fields appear on the Etsy shop edit form in the Operations menu, positioned near the existing `default_taxonomy_id`, `default_shipping_profile_id`, etc.

Tooltips: "Optional. Used when listing and product overrides are both empty."

**Rationale**: Operators who manage shop configs are already familiar with the existing defaults block. Grouping related fields improves discoverability.

## Consequences

### Positive

- Supports distinct per-shop marketing narratives (gift-focused vs bulk-reseller brand voice) without product duplication.
- Extends ADR-015 chain minimally (one additional layer).
- No new model — reuses existing `multichannel.listing` per-shop override mechanism.
- Forward-compatible schema (nullable columns, no migration).
- Operator visibility via DEBUG logs.

### Negative

- One extra column on `etsy.shop` per field (minor schema cost, 3 columns for title/desc/image).
- If operators set conflicting shop and product defaults (e.g., "Handmade" title + "Bulk" description), there's no validation — operator responsibility.
- Three-layer fallback can be confusing to new operators without documentation.

### Neutral

- Seed data for shop defaults is optional (demo convenience only).

## Compliance check

| Constraint | Status |
|---|---|
| Standard-Odoo-First | ✅ Reuses existing `multichannel.listing` per-shop cardinality (UNIQUE INDEX on (product, channel, shop)). No new model. Shop-level fields follow the existing `default_taxonomy_id` pattern. |
| ADR-003 (one-way dependency) | ✅ Fields added to etsy_integration (channel-specific module). No dependencies on multichannel_hub_core (reversed). |
| No new models | ✅ Only field additions to `etsy.shop`; reuse `multichannel.listing` existing fields. |
| ACL unchanged | ✅ `etsy.shop` form already editable by Marketing via Operations menu per existing ACLs. |
| Migration-free | ✅ Nullable columns are forward-compatible; no post-migrate.py required. |

## Implementation notes (for code slice)

- Extend `etsy.shop.py` with three field definitions.
- Add publisher helper methods (e.g., `_resolve_title_with_shop_fallback`) to `etsy_listing_publisher.py` for clean fallback logic.
- Extend etsy shop form view to show the three new fields.
- Write 12 tests: 4 Phase-1 DB + 8 Phase-2 ORM (fallback chain, logging, integration).
- Estimated **~110 LOC** (models + views + tests).

ADR-017 END
