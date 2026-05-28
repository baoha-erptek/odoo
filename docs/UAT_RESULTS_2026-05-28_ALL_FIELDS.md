# UAT Round 2 — Full Etsy Listing-Field Coverage

**Date:** 2026-05-28
**Goal:** exercise every attribute Etsy's "How to Create a Listing" flow supports,
verified against the **live** Etsy draft (not just Odoo state).
**Environment:** staging `esty_odoo19` — mhc `19.0.1.0.64`, etsy_integration `19.0.2.30.0`.
**Specs:** `tests/e2e/tests/uat_all_fields.spec.ts` (TC-ALL-01/02), `npm run test:all-fields`
(gated `RUN_ETSY_PUBLISH=1`). **Live readback engine:** `tests/e2e/fixtures/verify_etsy_listing.py`.

## Result: PASS

Two products published as JaHandmadeArt drafts and read back from the Etsy API:

- **TC-ALL-01 Apron** (`listing_id 4512614292`): **2 real Etsy variations** ✓
  - `Apparel size: Medium` (fixed) + `Primary color: Black` / `Primary color: White` (varying)
  - 2 photos, materials `['Textile']`, weight 14.11 oz, who_made `i_did`, when_made
    `made_to_order`, taxonomy 2172, shipping profile `285149016922` (origin **VN**),
    return policy `1397855793400`, price 250000 VND, state draft.
- **TC-ALL-02 Doormat** (`listing_id 4512614444`): **item_height=2** (+ length 30, width 18) ✓
  - from the 3D rect Size `R30X18X2`; weight 17.64 oz; all core fields present.

Both `VERIFY_RESULT: PASS`.

## What this round delivered (code)

This was a feature+UAT bundle — three slices landed to make full coverage real:

### Slice A — `P-PUB-ITEM-HEIGHT` (etsy 19.0.2.28.0)
`_RECT_PATTERN` extended to an optional 3rd dimension; `_collect_weight_and_dimensions`
emits `item_height`. A 3D Size value is seeded with **name `R30X18X2`** (→ dimensions) and
**x_code `R30X18`** (→ canonical 2D SKU, ≤14 chars) — so the SKU grammar is untouched.

### Slice B — `R-PUB-VARIANT-MATERIALIZE` (etsy 19.0.2.29.0 → 30.0)
`push_inventory` now builds the Etsy products[] grid from the **cartesian product of
publishable variant-creating attribute lines**, not from `product.product` — so a dynamic
Color axis (which materializes 0 Odoo variants) still produces real Etsy variations. Two
empirically-discovered Etsy requirements were fixed:
1. **`property_name` is mandatory** — the inventory PUT 400s "Expected string value for
   property_name (got NULL)". Variant properties had **never worked** (the old helper omitted
   it). New `_property_value_for` emits `{property_id, property_name, values}`.
2. **SKU must be consistent across products** — kept the template-level SKU for all offerings.

Property IDs discovered via the seller-taxonomy endpoint + verified live: **Primary color =
200** (free-text value names), size-slot axes → **Custom1 = 513**. Material is materials[]-only
(`x_publish_as_property=False`). New field `x_etsy_property_name` on `product.attribute`.
≤2-varying-property guard added (Etsy's variation cap).

### Migration `19.0.2.30.0/post-migrate.py`
The `noupdate="1"` seed in `etsy_attribute_defaults.xml` had **never applied** on staging
(skipped on `-u` because the attribute rows pre-existed → every axis `publish=False`, so
variations were silently impossible). The migration writes the property id/name/publish config
idempotently for existing DBs; the seed still covers fresh installs.

Reviewers (code + security, parallel): **APPROVE, 0 CRITICAL / 0 HIGH**.

## Etsy field coverage matrix (verified live unless noted)

| Field | Status |
|---|---|
| title / description / price / quantity | ✓ |
| who_made / when_made / taxonomy_id | ✓ |
| shipping_profile_id (+ origin country VN) / return_policy_id | ✓ |
| processing time (readiness_state_id) | ✓ (shop default) |
| materials | ✓ `['Textile']` |
| item_weight (+unit) | ✓ |
| item_length / item_width / **item_height** | ✓ (Doormat) |
| photos (≥2) | ✓ (Apron) |
| personalization (enable/required/char/instructions) | ✓ set on product; dedicated endpoint |
| **variations** (property_values + property_name, per-variant) | ✓ 2 variations (Apron) |
| tags | ⚠ **test-side gap** — see below |

## Known gaps

- **Tags (test-side):** the e2e `addTags` form helper did not attach tags on the standard
  product form (`product_tag_ids` stayed empty → Etsy `tags=[]`). The publisher tag payload
  itself is correct and covered by `test_phase2_pub_tags_payload_orm`. Fix `ProductFormPage.addTags`
  for the standard form in a follow-up; tags are not a publisher defect.
- **Not supported on the Etsy listing API (documented, not built):**
  listing **video**; category **attributes** (primary/secondary color, occasion, holiday as
  taxonomy attributes — distinct from variations); **production partners**; shop **section**;
  per-listing **country of origin** (lives on the shipping profile — origin VN verified);
  **is_supply** per-product (shop-wide only). Each is a candidate future slice.

## Artifacts

- Specs: `tests/e2e/tests/uat_all_fields.spec.ts`; readback `tests/e2e/fixtures/verify_etsy_listing.py`
- Live drafts (no fee): Apron `4512614292`, Doormat `4512614444` (plus earlier pre-migration
  `4512610795` / `4512611025`). Delete from Shop Manager when no longer needed.

## How to re-run

```
# deploy etsy+mhc to staging (rsync, odoo -u — runs the migration —, restart)
cd tests/e2e
python3 fixtures/extract_catalog_images.py --sheet Apparel --row 5 --prefix apf   # if assets absent
RUN_ETSY_PUBLISH=1 E2E_LISTING_PRICE=250000 npm run test:all-fields
# then live readback (server-side), per product:
cat fixtures/verify_etsy_listing.py | ssh <staging> "sudo docker exec \
  -e VERIFY_NAMES='<apron name>' -e VERIFY_MIN_IMAGES=2 -e VERIFY_MIN_VARIATIONS=2 \
  -i esty19_odoo odoo shell -d esty_odoo19 --no-http"
```
