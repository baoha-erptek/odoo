# Spec 014 — Listing Channel Overrides (Title / Description / Image)

**Slice ID**: `P-ENH-ESTY-190`
**Jira**: ESTY-190 (7.2)
**Wave**: 3 (enhancement, post Wave-2 listing-parity)
**Status**: spec authored 2026-06-07; code slice not yet dispatched
**Foundation**: P-BUG-ESTY-188 ✓; P-SPEC-LISTING-MODEL-SPLIT ✓
**ADR**: ADR-017 (new, this slice)

## 1. Problem

Marketing operates different Etsy shops (e.g. JaHandmadeArt, namcohome) selling overlapping product catalogs. A single product (e.g. "Ceramic Mug") needs different marketing narratives per shop — one shop targets gift-buyers (emphasize artisan craftsmanship), another targets home-office resellers (emphasize durability). When Marketing pushes the product to both shops via `multichannel.listing`, they cannot currently express per-shop title/description variations. The product row carries ONE canonical description; the publisher today uses that single row for all Etsy shops.

The result: silent surprises when a listing publishes with mismatched marketing copy (e.g. "Handmade Gift" messaging on a bulk-reseller shop, or vice versa). Operators work around by duplicating the product row per shop, which creates a one-to-many mapping nightmare during SKU changes.

## 2. Scope

### In scope

- Extend `etsy.shop` with three new fields: `default_title`, `default_description`, `default_image_1920` (to serve as per-shop fallbacks when no listing-level override exists).
- Document the three-layer field resolution chain in the publisher:
  1. `multichannel.listing.title` / `.description` / `.image_1920` (per-listing override, already shipped in P-LIST-MODEL)
  2. `product.template.name` / `.description_sale` / `.image_1920` (per-product fallback)
  3. `etsy.shop.default_title` / `.default_description` / `.default_image_1920` (per-shop fallback, **new fields**)
- Update publisher methods `EtsyListingPublisher._build_create_draft_payload()` to use the three-layer chain (already wired for listing → product; add shop-level chain as the final fallback).
- No new model. Reuse the existing `multichannel.listing` form and listing-level fields (title, description, image_1920) that ship in P-LIST-MODEL.
- Migration backfill: `etsy.shop` fields default to NULL. Seed file populates demo shops (if any) with shop-specific marketing copy.
- Owner docs update + UAT TC number.

### Out of scope

- Per-variant overrides (e.g. different image for the "Red" variant of a Ceramic Mug). Variant SKU builder has its own image gallery; this slice handles listing-level image only.
- Per-channel (non-Etsy) shop defaults. Slice is Etsy-specific (`etsy.shop` only).
- Image deletion / rotation. Operators set one hero image per shop; no image gallery per shop override.
- Per-listing-per-shop override M2M (tracker note mentioned `mhc.product.channel.copy`). **Analysis below shows this is redundant** — the three-layer chain already handles it via existing `multichannel.listing` rows scoped to (product, channel, shop).

### Standard-Odoo-First gate + key finding

**grep results**:
- `odoo/addons/product/models/product_template.py`: ships `name`, `description_sale`, `image_1920` (canonical product fields).
- `custom_addons/multichannel_hub_core/models/multichannel_listing.py:65-76`: already has `title`, `description`, `image_1920` Char/Text/Image fields as **per-listing marketing overrides** (added in P-LIST-MODEL, commit 696c4068a99).
- `custom_addons/etsy_integration/models/etsy_shop.py`: ships `default_taxonomy_id`, `default_shipping_profile_id`, `default_return_policy_id`, `default_readiness_state_id` as shop-level Etsy config. NO `default_title`, `default_description`, `default_image_1920` fields found.

**Verdict**: The tracker's note ("New `mhc.product.channel.copy` model") is **stale**. P-LIST-MODEL (spec 012, commit 696c4068a99) already established `multichannel.listing` as the per-(product_template, channel, shop) marketing-override surface. A NEW separate model is **redundant** — the existing listing model's `title`, `description`, `image_1920` fields already serve as per-shop overrides when the (product, channel, shop) tuple is unique (enforced by UNIQUE INDEX in `multichannel_listing.init()`).

**Recommended scope**: add shop-level **default** fields to `etsy.shop` only. The publisher's fallback chain becomes:

```
listing.title (empty?)
  → product.template.name (empty?)
    → etsy.shop.default_title
```

No new model, no new listing-level fields. Reuse `multichannel.listing.title` / `.description` / `.image_1920` exactly as they exist. **This is the minimal, Standard-Odoo-First solution.**

## 3. User stories

### US1 — Marketing sets per-shop default title

**As** a Marketing user
**I want** to configure a shop-specific default title (e.g. "JaHandmadeArt" gets "Handmade Ceramic", namcohome gets "Durable Office Ceramic")
**So that** listings published without an explicit title override inherit the shop's brand voice instead of the raw product name.

**Acceptance**:
- Form to edit an Etsy shop shows a new field "Default Title" (Char, max 140 to fit Etsy's typical constraint).
- When a listing publishes and `multichannel.listing.title` is empty, publisher falls back to `product.template.name`, then to `etsy.shop.default_title`.
- Empty `etsy.shop.default_title` continues the chain → uses `product.template.name`.

### US2 — Marketing sets per-shop default description

**As** a Marketing user
**I want** to configure a shop-specific default description (e.g. gift-buyer messaging vs bulk-buyer messaging)
**So that** listings inherit the appropriate shop voice when no listing-level override exists.

**Acceptance**:
- Form to edit an Etsy shop shows a new field "Default Description" (Text).
- When a listing publishes and `multichannel.listing.description` is empty, publisher falls back to `product.template.description_sale`, then to `etsy.shop.default_description`.
- Empty `etsy.shop.default_description` continues the chain → uses `product.template.description_sale`.

### US3 — Marketing sets per-shop default image

**As** a Marketing user
**I want** to configure a shop-specific default hero image (e.g. white background for one shop, lifestyle shot for another)
**So that** listings show the right image context per sales channel without re-uploading.

**Acceptance**:
- Form to edit an Etsy shop shows a new field "Default Image" (Image, same max-width/max-height as listing-level image).
- When a listing publishes and `multichannel.listing.image_1920` is empty, publisher falls back to `product.template.image_1920`, then to `etsy.shop.default_image_1920`.
- Empty `etsy.shop.default_image_1920` continues the chain → uses `product.template.image_1920`.

### US4 — Publisher resolves and logs the fallback chain

**As** a system operator
**I want** the publisher to log which level (listing / product / shop) the final value came from
**So that** I can debug why a specific listing used unexpected marketing copy.

**Acceptance**:
- Publisher methods emit DEBUG log entries like "multichannel.listing 42: resolved title from shop default; etsy_listing_id=4510454735".
- Log is only when the final value differs from the listing-level override (i.e. we fell back).
- No crash or retry when a fallback step is empty.

## 4. Design decisions

| Q | Decision | Rationale |
|---|---|---|
| Q1: New model or reuse `multichannel.listing`? | **Reuse existing `multichannel.listing` fields**. NO new model. | The tracker's `mhc.product.channel.copy` note pre-dates P-LIST-MODEL (spec 012). `multichannel.listing.title`/`.description`/`.image_1920` already exist and are keyed by (product_tmpl_id, channel_id, shop_ref) with UNIQUE INDEX. One listing per (product, channel, shop) = one override row per shop per product. New model would duplicate this structure. Standard-Odoo-First rejects redundancy. |
| Q2: Where do shop-level defaults live? | `etsy.shop.default_title`, `.default_description`, `.default_image_1920` fields (new, this slice). | Shop-level fields follow the existing pattern (`default_taxonomy_id`, `default_shipping_profile_id`). Odoo-standard location for per-entity config. |
| Q3: Three-layer or two-layer fallback? | **Three-layer**: listing → product → shop. | (a) Listing-level overrides are the highest-priority marketing decision (per-channel per-shop customization). (b) Product-level is the canonical fallback (BA-owned). (c) Shop-level is the "brand voice" fallback (Marketing-owned, shop-global). Matches ADR-015 §3 resolution chain. |
| Q4: New ADR or amend ADR-015? | **New ADR-017**. | ADR-015 covers the listing-model split and the two-layer chain (listing → product). Adding a third shop-level layer is orthogonal and deserves its own record. Separate deprecation point if shop-level fallback logic moves elsewhere in Wave 4. |
| Q5: Image field on `etsy.shop` — Binary or M2O to ir.attachment? | **Binary Image field** (like `multichannel.listing.image_1920`). | Consistency with listing-level. `ir.attachment` M2O is overkill for a single hero image (would require manual record linking in UI). Binary field is simpler and mirrors the pattern already on listing. |
| Q6: Operator control — UI edit or seed data only? | **UI edit on etsy.shop form** (not seed-only). | Marketing must be able to change shop voice dynamically without re-importing data. Forms go in a shop-management view in the Operations menu (Operations → Channels → Etsy Shops, existing). |

## 5. Field surface

| Field | Module | Type | Notes |
|---|---|---|---|
| `etsy.shop.default_title` | etsy_integration | Char(140), nullable | Fallback when listing + product title both empty. Seed file can pre-populate. UI edit via shop form. |
| `etsy.shop.default_description` | etsy_integration | Text, nullable | Fallback when listing + product description both empty. Seed file can pre-populate. UI edit via shop form. |
| `etsy.shop.default_image_1920` | etsy_integration | Image (max_width=1920, max_height=1920), nullable | Fallback when listing + product image both empty. Seed file can pre-populate. UI edit via shop form. |

**Publisher changes** (existing files, no new files):
- `etsy_listing_publisher.py::_build_create_draft_payload()` — extend title/description/image resolution to add shop fallback after product fallback.
- `etsy_listing_publisher.py::_resolve_listing_intent()` — add resolve_title_with_shop_fallback() / resolve_description_with_shop_fallback() / resolve_image_with_shop_fallback() methods (or inline the logic if simpler).

ACL surface unchanged (shop form already editable by Marketing via Operations menu per existing ACLs on etsy.shop).

## 6. Test plan

Phase-1 DB (`tests/test_p_enh_esty_190_phase1_db.py`):
- New columns `default_title`, `default_description`, `default_image_1920` exist in `etsy_shop` table.
- Column widths / nullability correct.

Phase-2 ORM (`tests/test_p_enh_esty_190_phase2_orm.py`):
- `test_title_fallback_listing_present` — listing.title set → resolve_title() returns listing value.
- `test_title_fallback_listing_empty_product_present` — listing.title empty, product.name set → returns product value.
- `test_title_fallback_listing_product_empty_shop_set` — both empty, shop.default_title set → returns shop value.
- `test_title_fallback_all_empty` — all three empty → returns empty string (no crash).
- `test_description_fallback_chain` — mirrors title chain for description.
- `test_image_fallback_chain` — mirrors title chain for image_1920 binary.
- `test_publisher_emits_debug_log_on_fallback` — publisher logs DEBUG entry naming the fallback level when it triggers.
- `test_etsy_listing_creation_uses_shop_default_when_listing_empty` — end-to-end: create a draft listing without title, publish, verify payload carries shop.default_title. (Integration test.)

Estimated 4 Phase-1 + 8 Phase-2 = 12 tests.

## 7. Migration

**NO database migration required**. Adding nullable columns to `etsy.shop` is a forward-compatible schema change. Existing rows get NULL for the new fields.

**Seed data** (optional, per-demo setup):
- `custom_addons/etsy_integration/data/etsy_shop_defaults_demo.xml` — if using demo data, seed the demo shops with example shop-level defaults.

No post-migrate.py needed (unlike ADR-016 which required backfill).

## 8. Owner docs

- `docs/owner/HUONG_DAN_QUAN_LY_KENH_BAN.md` §5 (new or extend) — "Cài đặt mặc định tiêu đề/mô tả/hình ảnh cho mỗi cửa hàng Etsy".
- `docs/owner/UAT_WALKTHROUGH_QUAN_LY_KENH_BAN.md` TC-025 (new row) — walkthrough: edit shop defaults, publish a listing without title, verify payload carries shop default.

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Marketing forgets to set `default_title` on a new shop, list publishes with raw product name (mismatched voice) | Medium | Tooltip on the shop form: "Leave empty to inherit from product master.". Pre-populated seed data for launch shops. |
| Operators set conflicting title/description (e.g. "Handmade" title + "Bulk resale" description) brand-wise | Low | Operator responsibility — no validation rule. Brief owner-docs note on brand consistency best practices. |
| Image upload to `etsy.shop.default_image_1920` fails or is forgotten | Low | UI field is prominent on shop form. Error handling same as listing-level image (graceful fallback if binary missing). |
| Three-layer fallback is confusing (operators don't know which level resolved) | Low | Mitigation US4: publisher logs DEBUG entry naming the resolved level. DEBUG logs available in server logs per P-BUG-ESTY-188 iter2 audit-trail pattern. |

## 10. Exit criteria (machine-checkable)

- [ ] All 12 Phase-1 DB + Phase-2 ORM tests pass.
- [ ] Module installs cleanly: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exit 0.
- [ ] Publisher methods `_resolve_title_with_fallback` / `_resolve_description_with_fallback` / `_resolve_image_with_fallback` exist and are called by `_build_create_draft_payload`.
- [ ] Full etsy_integration test suite runs with zero new regressions (baseline 18 fail / 5 error of 716 tests, now 728).
- [ ] No `_logger.info()` / `print()` in changed files.
- [ ] `ruff check custom_addons/etsy_integration/` zero new lint violations.
- [ ] Tracker row P-ENH-ESTY-190 state → `done`; Phase 9 staging confirmed `latest_version='19.0.3.X.0'`.
- [ ] Owner docs updated per §8.
- [ ] ADR-017 authored and linked in spec.

