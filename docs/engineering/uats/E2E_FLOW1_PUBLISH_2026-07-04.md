# MF-E2E-1 — Flow-1 tạo sản phẩm → publish (2026-07-04)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 7888e427b38
- **Driver**: scripts/e2e_flow1_publish.py
- **Etsy shop**: JaHandmadeArt (60752333)
- **Listing**: 4532514202
- **Result**: 10/10 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; shop id=10 defaults OK; archived 0 stale test product(s) (6 total historical) | — |
| 1 | PASS | categ only→MUG; + Material→MUG-CR; + Fluid oz→MUG-CR-F11 | — |
| 2 | PASS | tmpl 524 'E2E-F1 Mug 0704-122054' 2 variants ['MUG-CR-F11', 'MUG-CR-F15'] price=19.99 | docs/screenshots/2026-07-04/f1_s2_product_form.png |
| 3 | PASS | listing_id=4532514202 channel.status state=draft external_ref=4532514202 | — |
| 4 | PASS | {'state': 'draft', 'title': 'E2E-F1 Mug 0704-122054', 'quantity': 5, 'taxonomy_id': 2172, 'n_images': 1, 'n_products': 2, 'skus': ['MUG-CR-F11', 'MUG-CR-F15']} | — |
| 5 | PASS | channel.status state=published external_ref=4532514202 | docs/screenshots/2026-07-04/f1_s5_published_form.png |
| 6 | PASS | {'state': 'active', 'title': 'E2E-F1 Mug 0704-122054', 'quantity': 5, 'taxonomy_id': 2172, 'n_images': 2, 'n_products': 2, 'skus': ['MUG-CR-F11', 'MUG-CR-F15']} | — |
| 7 | PASS | idempotent re-push OK: {'state': 'active', 'title': 'E2E-F1 Mug 0704-122054', 'quantity': 5, 'taxonomy_id': 2172, 'n_images': 2, 'n_products': 2, 'skus': ['MUG-CR-F11', 'MUG-CR-F15']} | — |
| 8 | PASS | drift rows total=216; test-SKU rows=none | — |
| 9 | PASS | listing 4532514202 PATCH=200 state_after=edit; product archived. True DELETE needs listings_d scope (not granted — owner item). | — |

## Notes

- §9 deactivates (PATCH state=inactive) instead of deleting: Etsy `deleteListing` requires the `listings_d` OAuth scope, which the current grant (transactions_r/w, listings_r/w, shops_r/w, email_r) does not include. Owner decision: add `listings_d` to DEFAULT_SCOPES + re-authorize, or keep manual Shop-Manager deletes.
- `publisher.publish()` PATCH path fixed to the shop-scoped updateListing route in etsy_integration 19.0.3.16.0 (pre-fix it targeted bare listings/{id}, which 404s — never exercised live before this gate).

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow1_publish.py --db esty_odoo19
```

## Gate summary (MF-E2E-1 exit criteria)

- Runner **10/10 PASS ×2 consecutive** (listings 4532500875, 4532514202 —
  created → draft-verified → activated → active-verified → inventory
  re-pushed → drift-clean → deactivated).
- Playwright `uat_huong_dan_tao_san_pham.spec.ts`: **11 passed ×2**
  (4 skipped by design: TC-003/004/008 need seeds; TC-014 n/a), serial
  workers=1, live publish TCs included (`RUN_ETSY_PUBLISH=1`,
  `E2E_LISTING_PRICE=19.99`).
- Playwright `uat_real_apron_publish.spec.ts` (TC-R01, real catalog images):
  **1 passed ×2**.
- Product fixes shipped in `etsy_integration 19.0.3.16.0`:
  1. `publish()` → shop-scoped `updateListing` PATCH (was bare
     `listings/{id}`, 404 — first live activation ever).
  2. `push_inventory` variant↔combo match now includes single-value
     NON-publishable variant axes (Material) so per-variant `default_code`
     wins (was silently synthesizing `MUG-11OZ`).
  Unit: `TestPubPublishORM` 6/6, `TestPushInventoryPerVariant` 5/5 (new RED
  test for the Material-axis case).
- Test-side fixes: `channelStatus` newest-first lookup; `uniq()` lowercase
  (Etsy `all_caps` title 400); price 19.99 USD (company currency; shop
  converts to VND).
- Full findings: `specs/015-project-completion/findings.md` (2026-07-04
  MF-E2E-1 block).

### Owner items

1. **`listings_d` scope**: true listing DELETE impossible with current OAuth
   grant. Test listings are deactivated (PATCH state=inactive) instead;
   Playwright TCs additionally leave a handful of Etsy *drafts* (no fee, not
   buyer-visible) named `UAT-TAOSP*` / `E2E-F1*` on JaHandmadeArt. Either add
   `listings_d` to DEFAULT_SCOPES + re-authorize the shop, or bulk-delete the
   test drafts in Shop Manager.
2. **SKU-drift job**: decided NOT needed (dirty-flag + wizard + on-demand
   reporter cover it) — veto within a week if a scheduled report was expected.
