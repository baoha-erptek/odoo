# P-BUG-ESTY-188 Iteration 3 — Per-variant SKU/qty/price/image Plan

**Slice**: `P-BUG-ESTY-188-iter3` (Sub-phase 3h, Wave 1, continuation)
**Jira**: ESTY-188 (6.11b — "Lỗi Bug ko publish listing lên Etsy được")
**Branch**: `feature/006-master-plan-coding`
**Planner**: orchestrator inline (2026-06-06)
**Manifest bump**: `19.0.2.34.0 → 19.0.3.0.0` (minor — payload-shape change)
**Status**: Phase 1 — Planning. Owner directive 2026-06-06: implement Etsy's native per-variant model end-to-end (SKU, qty, price, image per variant), grounded in OAS + ADR-014 §4.a amendment.

---

## Root cause (confirmed via staging 400 body)

iter2 (`d660afd7c4b`, `19.0.2.34.0`) shipped currency conversion. Owner re-published 2026-06-06 06:57 UTC against JaHandmadeArt for `product.template id=456` "Personalized Coordinates Leather Tray". 400 body:

```
[{"path":"/price","type":"empty","message":"cannot be empty","transformed":false}]
```

psql evidence:

```
SELECT id, list_price FROM product_template WHERE id=456;
 id  | list_price
-----+------------
 456 |        0.0

SELECT ptav.price_extra, pav.name->>'en_US'
FROM product_template_attribute_value ptav
LEFT JOIN product_attribute_value pav ON pav.id = ptav.product_attribute_value_id
WHERE ptav.product_tmpl_id = 456;
 price_extra | value
-------------+--------
        20.0 | 6"
        30.0 | 8"
        10.0 | 4''
```

Template `list_price=0`; all real prices are in per-variant `price_extra`. The publisher's `_build_create_draft_payload` calls `_convert_to_shop_currency(s.list_price, shop)` → `0` → Etsy 400 "empty". A second structural defect — already documented but worth re-asserting — is `push_inventory` emitting **one SKU** across every `products[]` entry (Etsy requires the SKU to vary when other variant attributes vary; otherwise the consistency rule prevents per-variant inventory).

Together these two defects show the publisher's price/SKU model is **template-level**, but Etsy's native model is **per-variant**. iter3 fixes both at once.

---

## OAS evidence (pulled from `/tmp/etsy_oas.json` per findings.md Phase 0)

- `POST /shops/{shop_id}/listings` (createListing): `price` is a top-level field; cannot be empty/zero.
- `PUT /listings/{listing_id}/inventory` (updateListingInventory): `products[]` carries `sku`, `property_values[]`, `offerings[]` (qty/price/readiness_state_id); optional sibling arrays `sku_on_property[]`/`quantity_on_property[]`/`price_on_property[]` list the `property_id` of every variation-creating axis whose values drive distinct SKUs/qty/price respectively.
- `POST /shops/{shop_id}/listings/{listing_id}/variation-images`: body `{"variation_images": [{"property_id": int, "value_id": int, "image_id": int}, ...]}`. One image per (property_id × value_id), not per variant. `image_id` is the `listing_image_id` returned by a prior `uploadListingImage`.

---

## Fix scope (per ADR-014 §4.a amendment — uncommitted, will be committed in this slice)

| # | Change | File | What | Why |
|---|---|---|---|---|
| 1 | New method | `services/etsy_listing_publisher.py` | `_resolve_starting_price(tmpl, shop) → float` | Returns `_convert_to_shop_currency(min positive variant.lst_price, shop)`; falls back to template list_price when no variants; raises `UserError` when both are 0. |
| 2 | New method | `services/etsy_listing_publisher.py` | `_resolve_variant_sku(tmpl, variant)` AND `_synthesize_variant_sku_from_combo(base, combo)` | variant.default_code wins; else slug-synthesized `f"{base}-{slug}"` with 32-char clamp; UserError if base empty and no slug. |
| 3 | Edit | `_build_create_draft_payload` | Replace `'price': self._convert_to_shop_currency(s.list_price, shop)` with `'price': self._resolve_starting_price(s, shop)` | Listing's "starts at" price is the cheapest variant. |
| 4 | Rewrite | `push_inventory` | Inside `for combo` loop: lookup matching `product.product` variant, emit `{sku: per-variant, property_values, offerings: [{quantity: per-variant qty, price: converted per-variant lst_price}]}`. Single-variant branch unchanged in semantics but routes through new helpers. Compute `sku_on_property[]`/`quantity_on_property[]`/`price_on_property[]` from varying axes when any two products[] differ on that dimension. | Etsy's native per-variant model + fixes "consistency" 400. |
| 5 | New method | `services/etsy_listing_publisher.py` | `push_variation_images(tmpl, listing_id, shop)` | Upload `variant.image_variant_1920` per variant via `uploadListingImage` (capture returned `listing_image_id`), then POST `/listings/{id}/variation-images` with `{property_id, value_id, image_id}` triples. Best-effort — partial failure logs WARNING and continues. Skip when no variant carries `image_variant_1920`. |
| 6 | Edit | `run()` orchestrator | Add `self.push_variation_images(tmpl, listing_id, shop)` after `upload_images` and before `publish()`. Wrap in try/except WARNING (non-fatal — listing publishes without variant binding). | Wire new step into chain. |
| 7 | Manifest | `__manifest__.py` | Bump to `19.0.3.0.0` | Minor — payload shape change. |
| 8 | Owner docs | `docs/owner/HUONG_DAN_DANG_SAN_PHAM_VN.md` + `docs/owner/UAT_WALKTHROUGH_DANG_SAN_PHAM_VN.md` | Add new step: "Đăng sản phẩm có nhiều biến thể (size/màu)" with TC-014. | Phase 7 binding rule. |
| 9 | Commit ADR | `specs/006-master-plan/adrs/ADR-014-central-product-hub.md` | Commit the uncommitted §4.a amendment in iter3 GREEN commit. | Decision belongs with code that implements it. |

---

## Helper signatures

```python
def _resolve_starting_price(self, tmpl, shop):
    """Return the listing's 'starts at' price in shop currency.

    Strategy:
      1. Walk publishable variants. Collect `lst_price` (template list_price
         + price_extra per variant); positive values only.
      2. If any positive variant prices found → use min(positives).
      3. Else fall back to template.list_price.
      4. If the result is still 0 → raise UserError with a clear
         operator-facing message ("Set list_price on the product or
         price_extra on at least one variant axis").
      5. Convert via _convert_to_shop_currency before returning.
    """

@staticmethod
def _resolve_variant_sku(tmpl, variant):
    """Per-variant SKU. variant.default_code if non-empty; else synth."""

@staticmethod
def _synthesize_variant_sku(base, value_names):
    """`{base}-{SLUG}` with 32-char clamp from suffix-end + WARNING on truncate."""
```

---

## Test surface (Phase 2 RED — strengthen existing `tests/test_p_bug_esty_188_phase2_orm_iter3.py`)

Existing iter3 tests are weak (method-existence only). Strengthen to fail-for-right-reason on the actual fix:

| TC | Category | Setup | Assert |
|---|---|---|---|
| R1 | starting-price | template list_price=0, three ptav.price_extra = 10/20/30 | `_resolve_starting_price` returns 10.0 (after FX) — NOT 0 — NOT 20 |
| R2 | starting-price | template list_price=0, no variants | UserError raised |
| R3 | starting-price | template list_price=15, no variants | 15.0 (after FX) |
| R4 | starting-price | template list_price=0, three variants with lst_price=0/10/20 | 10.0 (skip zero variants) |
| R5 | sku | variant.default_code="ABC-XL" | "ABC-XL" |
| R6 | sku | variant.default_code empty, base="LEATHER", combo=["6\""] | "LEATHER-6IN" |
| R7 | sku | base="X", 40-char synthetic suffix | truncated to 32, WARNING logged |
| R8 | sku | base empty, no variants | UserError raised |
| R9 | push_inventory | 3-variant Size template, list_price=0, price_extra=10/20/30 | products[] has 3 entries with distinct sku, distinct price, distinct qty (use variant.qty_available); `price_on_property` lists Size axis property_id |
| R10 | push_inventory | single-variant template (regression) | products[] has 1 entry; no sku_on_property/qty_on_property/price_on_property; SKU equals base |
| R11 | push_inventory | variant.lst_price=0, fallback to tmpl.list_price=15 | offering price = 15.0 (after FX) |
| R12 | variation-images | 3 variants, 2 carry image_variant_1920 | uploadListingImage called 2x; updateVariationImages POST with 2 triples; missing variant skipped (WARNING) |
| R13 | variation-images | no variant has image_variant_1920 | push_variation_images returns []; no POST to variation-images |
| R14 | createDraft price | iter3 wired through; template list_price=0 + price_extra=10/20/30 | payload['price'] = 10.0 (after FX), not 0 |
| R15 | createDraft baseline | template list_price=15 (no variants) | payload['price'] = 15.0 (after FX) — regression check from iter2 |

Existing 4 weak tests (method-exists shape) retire; replaced by R1-R15.

---

## Exit criteria

- Module installs cleanly (`-u etsy_integration --stop-after-init` exit 0).
- All R1-R15 GREEN under `--test-tags /etsy_integration`.
- iter2 baseline (18 fail / 5 error of 691) stays exactly that — zero new regressions.
- `ruff check custom_addons/etsy_integration/` clean.
- No `_logger.info(` / `print(` in the diff.
- code-reviewer + security-reviewer APPROVE on 0 CRITICAL / 0 HIGH.
- `docs/owner/HUONG_DAN_DANG_SAN_PHAM_VN.md` step revised; `docs/owner/UAT_WALKTHROUGH_DANG_SAN_PHAM_VN.md` TC-014 row added.
- Tracker P-BUG-ESTY-188 row updated with iter3 ship note.
- ADR-014 §4.a amendment committed (already drafted, uncommitted).
- Staging deploy via rsync + `-u etsy_integration` + restart; owner pinged via Telegram with re-publish instructions for product.template id=456.

---

## Owner-gated decision points (decided inline per dispatch-runs-to-completion rule)

| Question | Decision | Rationale |
|---|---|---|
| Starting price when both template list_price=0 AND variants all 0 | UserError at wizard boundary | Standard-Odoo-First: would otherwise emit 0 → 400; better to fail fast with actionable message. |
| Variant SKU synthesis when both default_code and variation names empty (impossible in practice but defensive) | UserError | No silent empty-string SKU. |
| variation-images failure mode | Best-effort, WARNING, listing still publishes | Mirrors `upload_images` per-image failure semantics; consistent with existing personalization push pattern. |
| Manifest bump | `19.0.2.34.0 → 19.0.3.0.0` (minor) | Payload shape change; warrants minor bump per existing precedent (R-PUB-PERSONALIZATION-ENDPOINTS bumped 19.0.2.x → 19.0.2.y when shape changed; this is a bigger shape change). |

---

## References

- ADR-014 §4.a amendment (in this iter3 commit)
- specs/008-listings-inventory-sync/findings.md "iter3 RCA evidence" + "iter3 Phase 0" sections
- /tmp/etsy_oas.json — Etsy v3 OpenAPI 3.0.2 spec (895 KB) — search for `updateListingInventory`, `updateVariationImages`, `createListing`
- memory `reference_etsy_createlisting_2025_readiness.md`
- memory `feedback_capture_response_body_before_blackbox_probe.md`
- memory `feedback_standard_odoo_first.md`
