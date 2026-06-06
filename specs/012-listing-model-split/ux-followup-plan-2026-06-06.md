# UX Pattern Adherence Plan for Remaining Wave-2 Slices

**Date**: 2026-06-06
**Trigger**: Owner directive after P-LIST-UX-FIXES shipped — "recheck for remaining slices flow UI what have just fixed before continue"
**Status**: planning artifact — no code change
**Companion docs**: [`ux-review-2026-06-06.md`](./ux-review-2026-06-06.md), [`ux-review-2026-06-06.html`](./ux-review-2026-06-06.html)

---

## Confirmed UX patterns now live on every Listing form

| Pattern | Where in view arch | Count of occurrences |
|---|---|---|
| **R1** — `action_open_in_etsy_shop_manager` button | mhc form header | 1 |
| **R2** — `Publishing workflow:` alert | mhc form sheet | 1 |
| **R3** — `readonly="state != 'draft'"` on every editable field | mhc + etsy_integration | **13 fields total** (7 in mhc base, 6 in etsy_integration extension) |
| **R4** — `last_synced_at` related-field mirrors next to cache-backed dropdowns | etsy_integration extension | 2 (taxonomy + shipping) |
| **Finding-5** — Scope group collapsed under "Advanced settings" outer group | mhc form sheet | 1 |

These patterns are now load-bearing. Every NEW field added by a remaining slice MUST inherit them at view-inherit time.

---

## Per-slice instructions

### P-LIST-ATTRIBUTES (T501–T507) — next up

**New fields landing on the form**
- `multichannel.listing.attribute_mapping_ids` — One2many to a new `multichannel.listing.attribute.mapping` model with `(product_attribute_id, etsy_property_id_override)` rows.

**UX adherence checklist** (R/UX rule → what to do in the slice)

| Rule | Action in P-LIST-ATTRIBUTES |
|---|---|
| R3 readonly | Add `readonly="state != 'draft'"` to the One2many widget on the form view; the inner list editable rows inherit via Odoo's widget-level readonly cascade. Phase 2 ORM test: create listing, publish, attempt to write a mapping row, expect AccessError or silent no-op. |
| HIGH #2 tab reorg | Land the new field inside a notebook page named **"Shipping & Variations"** (NEW name). Move the existing `etsy_shipping_profile_id` field into the same page. Add at the bottom of the page. Rename existing "Etsy" tab to **"How It's Made"** at the same time (it'll only contain who_made/when_made/is_supply by then). |
| HIGH #4 fallback help | Add a blue help box ABOVE the One2many widget:<br>`💡 Priority: Listing override (this list) → Shop default (Etsy Shop > Attribute Defaults) → Product global (Product > x_etsy_property_id). Leave empty rows to use the next tier.` |
| Phase 2 tests | Three-tier ORM tests: (a) listing row exists → use it; (b) listing empty + shop default exists → use shop; (c) both empty → use global. Locks the fallback chain mentioned in HIGH #4. |
| R1 / R2 / R4 / Finding-5 | Inherited from base — no action needed in the slice. |

**Wireframe sketch** (ASCII)

```
┌─ Listing form — published state ──────────────────────────────────┐
│ [Open in Etsy] Status: ●●●●─ Published                            │
├───────────────────────────────────────────────────────────────────┤
│ ⚠ Read-only: this listing is no longer in Draft.                  │
├───────────────────────────────────────────────────────────────────┤
│ [Image]  Listing Title: Custom Coffee Mug 11oz                    │
│                                                                   │
│ External ref: 1234567890     Last synced: 2 hours ago             │
│                                                                   │
│ ▶ Advanced settings (collapsed)                                   │
├───────────────────────────────────────────────────────────────────┤
│ [Listing Basics] [How It's Made] [Shipping & Variations] [Video]  │
├───────────────────────────────────────────────────────────────────┤
│ NEW TAB: Shipping & Variations                                    │
│                                                                   │
│ Shipping Profile: ▼ Standard US Shipping                          │
│                   Cache last synced: 30 min ago                   │
│                                                                   │
│ 💡 Attribute Mapping — Priority: Listing → Shop → Product global. │
│                                                                   │
│ ┌──────────────────────┬─────────────────────────────────────┐    │
│ │ Product attribute    │ Etsy property override              │    │
│ ├──────────────────────┼─────────────────────────────────────┤    │
│ │ Size                 │ 514 (Etsy "size") — override        │    │
│ │ Color                │ (use shop default)                  │    │
│ │ [+ Add row]          │                                     │    │
│ └──────────────────────┴─────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

---

### P-LIST-ATTR-CONFIG (T601–T606) — Wave-2 #7

**New fields landing**
- `etsy.shop.default_attribute_mapping_ids` — One2many (sister model to the listing-level one); shop-wide defaults.

**UX adherence checklist**

| Rule | Action |
|---|---|
| HIGH #4 fallback help (shop level) | On the Etsy Shop form, in the Publisher Defaults section, add help text: `These attribute mappings are the shop-level default. Any listing that sets its own mapping overrides this. Empty mappings fall through to the product-global x_etsy_property_id.` |
| R3 readonly | Not applicable — the Etsy Shop form is admin-only; no draft/published state machine. |
| Sync indicator | Document whether the mapping is hand-curated (no cron) or autopopulated. Default plan: hand-curated. Add a note in `HUONG_DAN_TAO_SAN_PHAM_VN.md` §7.4a-attr explaining the admin workflow. |
| Other | Inherited or N/A. |

---

### P-LIST-SHOP-BULK (T701–T706) — Wave-2 #8

**New surface landing**
- List view filter on `multichannel.listing.shop_ref`.
- Server action "Mark Ready for Publish" (state draft → ready, bulk-edit).
- Server action "Publish to Etsy" (bulk-trigger `EtsyListingPublisher.run()`).

**UX adherence checklist**

| Rule | Action in P-LIST-SHOP-BULK |
|---|---|
| HIGH #2 tab reorg | N/A — this slice doesn't touch the form view; only the list view + actions. |
| R3 readonly (state lock) | **CRITICAL:** the "Mark Ready" server action MUST refuse to operate on rows where `state != 'draft'`. The "Publish" server action must refuse rows where `state != 'ready'`. Phase 2 ORM tests cover both branches. Display a user notification when the operator selects an ineligible row: `X out of Y listings are not in Draft and were skipped.` Mirrors the FR-017 defense pattern (memory `feedback_fr017_write_defense_in_depth.md`). |
| Help text on bulk-edit | Bulk actions should show a notification before firing: `You are about to mark N listings ready for publication. BA will review before they go live on Etsy.` Use `bus.bus._sendone()` if the action runs async. |
| List view: shop filter | Filter "Shop = X" pre-applied (saved search per shop). Search panel `shop_ref` group-by. Aligns with Finding-2 of UX review (operator pre-filters by shop before opening forms). |
| List view: state filter | Default to `state in ('draft', 'ready')` — Marketing rarely wants to see Published in the bulk-edit list. |

---

## Cross-cutting items deferred to a Wave-3 / polish slice

Surfaced during the audit but **NOT** required to ship Wave-2:

| Item | Why deferred | Future slice |
|---|---|---|
| Full Refresh-now CTA on taxonomy / shipping dropdowns | Requires the form to resolve a shop record from `shop_ref` Char (currently no FK). Either backfill shop_ref → etsy.shop M2O OR add a "Refresh from Etsy Shop Settings" link button. Decision postponed. | `P-LIST-CACHE-REFRESH-CTA` (W3) |
| Per-channel Title/Description/Image overrides | Already covered by `P-ENH-ESTY-190` Wave 3 | Wave 3 |
| BA approval workflow (state draft → ready transition with approval signature) | Spec 012 US3 names it; current state machine allows direct flip. Wave 3 polish. | `P-LIST-BA-APPROVAL` (W3) |

---

## Verification recipe before each remaining slice dispatches

Before authoring code for P-LIST-ATTRIBUTES / ATTR-CONFIG / SHOP-BULK:

1. **Re-grep the patterns** (this audit's command):
   ```bash
   grep -nE 'readonly="state != .draft.|action_open_in_etsy|Publishing workflow|Advanced settings|etsy_taxonomy_last_synced_at|etsy_shipping_last_synced_at' \
     custom_addons/multichannel_hub_core/views/multichannel_listing_views.xml \
     custom_addons/etsy_integration/views/multichannel_listing_etsy_views.xml
   ```
   Confirm 21+ matches (current baseline = 21).

2. **Re-run the UX-FIXES tests**:
   ```bash
   docker exec namco_odoo19 odoo -d namco_odoo19 \
     --test-tags=/multichannel_hub_core:TestOpenInEtsy,/multichannel_hub_core:TestFormReadonlyAttrs \
     --stop-after-init --http-port=8175
   ```
   Confirm 6/6 GREEN. Any new slice that breaks one of these has regressed a UX pattern and must fix before merge.

3. **Cite this plan doc** in the slice's `findings.md` / commit body so the audit trail records which UX rules the slice picked up.

---

## Recommendation for next dispatch

**Go ahead with P-LIST-ATTRIBUTES** — the UX patterns are stable, the plan above tells the next slice exactly what tab to land its fields in, where to put help text, and which ORM tests to write. Tab rename ("Marketing copy" → "Listing Basics", "Etsy" → "How It's Made", add "Shipping & Variations") happens *inside* P-LIST-ATTRIBUTES because that's the slice introducing the variations surface that justifies the new "Shipping & Variations" tab name.

Estimated cost for P-LIST-ATTRIBUTES with full UX adherence: ~250-350 LOC + ~8 ORM tests. ~45-60 min.
