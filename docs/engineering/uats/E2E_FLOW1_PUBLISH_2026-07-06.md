# MF-E2E-1 — Flow-1 tạo sản phẩm → publish (2026-07-06)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 3a0b8e7f939
- **Driver**: scripts/e2e_flow1_publish.py
- **Etsy shop**: JaHandmadeArt (60752333)
- **Listing**: 4533267304
- **Result**: 12/12 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; shop id=10 defaults OK; archived 0 stale test product(s) (10 total historical) | — |
| 1 | PASS | categ only→MUG; + Material→MUG-CR; + Fluid oz→MUG-CR-F11 | — |
| 2 | PASS | tmpl 678 'E2E-F1 Mug 0706-081135' 2 variants ['MUG-CR-F11'] price=19.99 | docs/screenshots/2026-07-06/f1_s2_product_form.png |
| 3 | PASS | listing_id=4533267304 channel.status state=draft external_ref=4533267304 | — |
| 3b | PASS | variant codes=['MUG-15OZ', 'MUG-CR-F11'] linked=['MUG-15OZ', 'MUG-CR-F11'] | — |
| 4 | PASS | {'state': 'draft', 'title': 'E2E-F1 Mug 0706-081135', 'quantity': 5, 'taxonomy_id': 2172, 'n_images': 1, 'n_products': 2, 'skus': ['MUG-15OZ', 'MUG-CR-F11']} | — |
| 5 | PASS | channel.status state=published external_ref=4533267304 | docs/screenshots/2026-07-06/f1_s5_published_form.png |
| 6 | PASS | {'state': 'active', 'title': 'E2E-F1 Mug 0706-081135', 'quantity': 5, 'taxonomy_id': 2172, 'n_images': 2, 'n_products': 2, 'skus': ['MUG-15OZ', 'MUG-CR-F11']} | — |
| 7 | PASS | idempotent re-push OK: {'state': 'active', 'title': 'E2E-F1 Mug 0706-081135', 'quantity': 5, 'taxonomy_id': 2172, 'n_images': 2, 'n_products': 2, 'skus': ['MUG-15OZ', 'MUG-CR-F11']} | — |
| 8 | PASS | drift rows total=268; test-SKU rows=none | — |
| T | PASS | cron exists (id=44); ICP unset; inventory api-log rows 8859->8859 (no-op confirmed) | — |
| 9 | PASS | listing 4533267304 PATCH=200 state_after=edit; product archived. True DELETE needs listings_d scope (not granted — owner item). | — |

## Notes

- §3b asserts the FLW-02 round-trip: the 15 oz variant is created with an EMPTY default_code and the publish-time synthesized SKU must be written back to the variant + linked in etsy.listing.product (2026-07-06 fix).
- §T asserts the FLW-07 top-up cron exists and is a strict no-op while ICP etsy_integration.pod_topup_quantity is unset (owner decision — never set by this runner).
- §9 deactivates (PATCH state=inactive) instead of deleting: Etsy `deleteListing` requires the `listings_d` OAuth scope, which the current grant (transactions_r/w, listings_r/w, shops_r/w, email_r) does not include. Owner decision: add `listings_d` to DEFAULT_SCOPES + re-authorize, or keep manual Shop-Manager deletes.
- `publisher.publish()` PATCH path fixed to the shop-scoped updateListing route in etsy_integration 19.0.3.16.0 (pre-fix it targeted bare listings/{id}, which 404s — never exercised live before this gate).

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow1_publish.py --db esty_odoo19
```
