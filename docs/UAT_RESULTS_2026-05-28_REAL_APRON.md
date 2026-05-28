# UAT Results — Real Catalog Product (Apron) → Etsy Draft

**Date:** 2026-05-28
**Flow:** "tao san pham" product-creation → publish-to-Etsy, end-to-end with a REAL
catalog product, real variants, and >1 real image.
**Environment:** staging `esty_odoo19` (https://odoo.hatafax.com) — mhc `19.0.1.0.63`,
etsy_integration `19.0.2.27.0` (fix landed this run).
**Spec:** `tests/e2e/tests/uat_real_apron_publish.spec.ts` (TC-R01),
`npm run test:real-apron` (gated `RUN_ETSY_PUBLISH=1`).

## Scope

Owner request: take a real product from `.0temp/raw/[2025] Product Catalog.xlsx`,
create it in Odoo via the genuine standard-form flow with variants + multiple images,
then publish to Etsy (JaHandmadeArt) as a complete, sellable **draft** — verifying it
carries everything Etsy's create-listing flow requires.

- **Product:** Black/White Apron `APF` (Apparel sheet, row 5).
- **Images:** 2 real catalog photos embedded in the xlsx (`image163.png` Spider-Man
  apron + `image15.png` cat-print apron with adult/kid size chart), extracted via
  `tests/e2e/fixtures/extract_catalog_images.py`.
- **Create method:** hybrid — standard Odoo form (Playwright) for name/category/variants/
  price/weight/channel; images injected via JSON-RPC (`image_1920` + `x_extra_image_ids`);
  publish via the real "Publish to Etsy → Run Publish Draft Only" wizard.
- **Publish depth:** draft only (no activation, no listing fee).

## Result: PASS (with one defect fixed mid-run + one known limitation)

TC-R01 green. Auto-SKU derived **`APR-TX-AM-BK`** (Apron + Textile + Apparel-Size Medium
+ Black) from the seeded APR family — confirms SKU auto-derive works for a real catalog
product. Final verified draft: **listing_id `4512579307`**.

### Etsy create-listing checklist (verified live via Etsy API)

| Etsy requirement | Result |
|---|---|
| Photos (≥1) | **2** (after fix) ✓ |
| Title | "UAT Real Apron APF-A0JD1" ✓ |
| State | draft ✓ |
| Price | 250000 VND (≥ shop floor) ✓ |
| Quantity | 1 ✓ |
| who_made | `i_did` (shop default) ✓ |
| when_made | `made_to_order` (shop default) ✓ |
| Category / taxonomy | `2172` (shop default) ✓ |
| Materials | `['Textile']` (derived from variant Material) ✓ |
| Variations / property_values | **not pushed** — see limitation below ✗ |

## Defect found & fixed: listing-image upload 404 (silent)

**Symptom:** first run created the draft but the Etsy listing had **0 photos** despite both
images being present on the Odoo product.

**Root cause:** `EtsyListingPublisher.upload_images` posted to `listings/{id}/images`, but
Etsy's `uploadListingImage` endpoint is **shop-scoped**: `shops/{shop_id}/listings/{id}/images`.
Every upload 404'd and was swallowed by the per-image `except ... WARNING; continue` guard.
(`create_draft` and `push_personalization` were already shop-scoped; only `upload_images`
was missed.)

**Fix** (`etsy_integration` `19.0.2.26.0 → 19.0.2.27.0`):
- `upload_images` now resolves `shop.sudo().etsy_api_shop_id` (raises if missing, mirroring
  `create_draft`) and posts to `shops/{shop_id}/listings/{id}/images`.
- Test `test_upload_images_posts_multipart_with_image_bytes` assertion updated to the
  shop-scoped path; new `test_upload_images_raises_when_shop_id_missing`.
- Verified: 9/9 Phase-2 image tests pass; live re-run draft `4512579307` has **2 photos**.

Reviewers (code + security, parallel): **APPROVE, 0 CRITICAL / 0 HIGH**.

## Known limitation (not fixed — owner decision): variant properties not pushed

The apron used **Color** as a variant axis, which is a *dynamic* `create_variant` attribute
in the seed. Dynamic-only axes do not materialise `product.product` variants, so
`push_inventory` emitted the **no-variants fallback offering** (single offering, bare SKU
`APR`, empty `property_values`) instead of per-color Etsy variations. This is the documented
fallback (memory #152) that keeps publish from 400-ing; it is not a regression.

To get true Etsy variations (Color/Size/Material as `property_values` with per-variant SKUs),
the product needs **materialised variants** — i.e. an `always`-create axis, or a step that
materialises dynamic variants before publish. Recommend a follow-up slice
(`R-PUB-VARIANT-MATERIALIZE` or similar) if per-variant Etsy listings are required.

## Artifacts

- Spec: `tests/e2e/tests/uat_real_apron_publish.spec.ts`
- Image extractor: `tests/e2e/fixtures/extract_catalog_images.py`
- Fixtures: `tests/e2e/fixtures/assets/apf_main.b64`, `apf_extra1.b64`
- Live drafts created (no fee): `4512576595` (pre-fix, 0→2 imgs after manual patch),
  `4512579307` (post-fix, 2 imgs). Delete from Shop Manager when no longer needed.

## How to re-run

```
# deploy (if staging behind HEAD): rsync 3 modules, odoo -u, restart  (see run-uat skill)
cd tests/e2e
python3 fixtures/extract_catalog_images.py --sheet Apparel --row 5 --prefix apf  # if assets absent
RUN_ETSY_PUBLISH=1 E2E_LISTING_PRICE=250000 npm run test:real-apron
```
