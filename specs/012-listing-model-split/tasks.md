# Spec 012 — Tasks (Wave 2 + model-split parent)

**Parent slice**: `P-SPEC-LISTING-MODEL-SPLIT` — author ADR-015 + this spec (doc-only, no code).
**Wave 2 children**: 7 listing-parity slices below; each runs the standard 9-phase playbook with this tasks.md as its home.

Marker key: `[ ]` todo · `[~]` in progress / deferred · `[X]` done.

---

## P-SPEC-LISTING-MODEL-SPLIT — model-split parent (doc-only)

- [X] T001 [P-SPEC-LISTING-MODEL-SPLIT] Author `specs/006-master-plan/adrs/ADR-015-listing-model-split.md` — Option C, model name, fields migration plan, ACL surface, module ownership, backfill plan.
- [X] T002 [P-SPEC-LISTING-MODEL-SPLIT] Create `specs/012-listing-model-split/spec.md` — 10 user stories + per-slice acceptance.
- [X] T003 [P-SPEC-LISTING-MODEL-SPLIT] Create `specs/012-listing-model-split/tasks.md` (this file).
- [ ] T004 [P-SPEC-LISTING-MODEL-SPLIT] Owner sign-off on ADR-015 before first Wave-2 implementation slice begins. (Telegram async OK.)

---

## P-LIST-MODEL — model creation + backfill (foundational, must land before any Wave-2 implementation)

Standalone slice that implements ADR-015 §1 §2 §4 §5 §6: ships `multichannel.listing` model + backfill, no Etsy-specific fields yet.

- [X] T010 [P-LIST-MODEL] `multichannel.listing` model (commit `696c4068a99`).
- [X] T011 [P-LIST-MODEL] ACL CSV — 4 rows + record rule blocking unlink-of-published (security-reviewer HIGH applied).
- [X] T012 [P-LIST-MODEL] List + form + search views.
- [X] T013 [P-LIST-MODEL] Menu under Operations → Listings.
- [X] T014 [P-LIST-MODEL] Phase 1 DB tests — 7 tests.
- [X] T015 [P-LIST-MODEL] Phase 2 ORM tests — 9 tests. Combined 16/16 GREEN.
- [X] T016 [P-LIST-MODEL] post-migrate backfill in `_19_0_1_0_65/__init__.py` + Odoo-discovery shim. Idempotent.
- [X] T017 [P-LIST-MODEL] Publisher wiring — `_resolve_listing_intent` helper + title/description fallback in `_build_create_draft_payload`.
- [X] T018 [P-LIST-MODEL] HUONG_DAN_TAO_SAN_PHAM_VN.md §6.5 "Sản phẩm vs Listing" landed.
- [X] T019 [P-LIST-MODEL] UAT TC-015 6-part walkthrough landed.
- [X] T020 [P-LIST-MODEL] Phase 9 staging deploy 2026-06-06 09:25 UTC — `multichannel_hub_core` `latest_version='19.0.1.0.65'` confirmed; `SELECT COUNT(*) FROM multichannel_listing` = **43** stub rows backfilled from live `product.channel.status` data. Container restarted clean.

Exit criterion: existing publish chain on JaHandmadeArt continues to work unchanged; every existing template with an active `etsy.listing` has a corresponding `multichannel.listing` stub row.

---

## P-LIST-VIDEO — Wave 2 / Jira ESTY-199 (Etsy step: video)

- [ ] T101 [P-LIST-VIDEO] Add `multichannel.listing.video_attachment_id` M2O→ir.attachment (private domain).
- [ ] T102 [P-LIST-VIDEO] Add `EtsyListingPublisher.push_video(tmpl, listing_id, shop)` calling `POST /shops/{shop_id}/listings/{listing_id}/videos` (Etsy `uploadListingVideo`, multipart). One video per listing per Etsy cap.
- [ ] T103 [P-LIST-VIDEO] Wire `push_video` into `EtsyListingPublisher.run()` after `push_inventory`. Best-effort (try/except WARNING; non-fatal).
- [ ] T104 [P-LIST-VIDEO] Phase 1 DB tests — field exists; attachment access ACL.
- [ ] T105 [P-LIST-VIDEO] Phase 2 ORM tests — publisher calls multipart endpoint when video attached; skip + WARNING when no video; multi-video upload returns first listing_video_id.
- [ ] T106 [P-LIST-VIDEO] Update views: video upload widget on `multichannel.listing` form.
- [ ] T107 [P-LIST-VIDEO] Update `HUONG_DAN_TAO_SAN_PHAM_VN.md` §6.5 with video upload step.
- [ ] T108 [P-LIST-VIDEO] Add TC-016 to UAT walkthrough (manual upload + publish + verify on Etsy).
- [ ] T109 [P-LIST-VIDEO] Phase 9 staging deploy + owner verify.

Etsy refs: `~/.cache/etsy-developer-docs/documentation_tutorials_listings.md` (video section); OAS `POST /v3/application/shops/{shop_id}/listings/{listing_id}/videos`.

---

## P-LIST-CATEGORY — Wave 2 / Jira ESTY-189 (Etsy step: category / taxonomy)

- [ ] T201 [P-LIST-CATEGORY] New cache model `etsy.taxonomy.node` (id, name, parent_id, level, full_path) in `etsy_integration/models/etsy_taxonomy_node.py`.
- [ ] T202 [P-LIST-CATEGORY] New `multichannel.listing.etsy_taxonomy_id` M2O→`etsy.taxonomy.node`.
- [ ] T203 [P-LIST-CATEGORY] Cron job `cron_sync_etsy_taxonomy` — `GET /seller-taxonomy/nodes` (paginated); upsert cache rows; refresh weekly.
- [ ] T204 [P-LIST-CATEGORY] Publisher: `_resolve_taxonomy_id` = listing override → `etsy.shop.default_taxonomy_id` → raise `UserError` if neither.
- [ ] T205 [P-LIST-CATEGORY] Phase 1 DB + Phase 2 ORM tests.
- [ ] T206 [P-LIST-CATEGORY] Form view: searchable Many2one dropdown for `etsy_taxonomy_id`.
- [ ] T207 [P-LIST-CATEGORY] Owner docs + TC.
- [ ] T208 [P-LIST-CATEGORY] Phase 9 staging deploy.

Standard-Odoo-First check: nothing in CE or Enterprise stores Etsy taxonomy. New cache model justified.

Etsy refs: `~/.cache/etsy-developer-docs/documentation_reference.md` (taxonomy section).

---

## P-LIST-SHIPPING — Wave 2 / Jira ESTY-191 (Etsy step: shipping profile)

- [ ] T301 [P-LIST-SHIPPING] New cache model `etsy.shipping.profile` (per-shop; id, name, processing_min_days, processing_max_days, currency, origin_country).
- [ ] T302 [P-LIST-SHIPPING] `multichannel.listing.etsy_shipping_profile_id` M2O→cache.
- [ ] T303 [P-LIST-SHIPPING] Cron `cron_sync_etsy_shipping_profiles` — `GET /shops/{shop_id}/shipping-profiles` per active shop; upsert.
- [ ] T304 [P-LIST-SHIPPING] Publisher: read listing override → shop default → UserError.
- [ ] T305 [P-LIST-SHIPPING] Phase 1 DB + Phase 2 ORM tests.
- [ ] T306 [P-LIST-SHIPPING] Form view + searchable dropdown.
- [ ] T307 [P-LIST-SHIPPING] Owner docs + TC.
- [ ] T308 [P-LIST-SHIPPING] Phase 9 staging deploy.

---

## P-LIST-HOW-ITS-MADE — Wave 2 / Jira ESTY-193 (Etsy step: who_made / when_made / is_supply)

- [ ] T401 [P-LIST-HOW-ITS-MADE] Add `multichannel.listing.etsy_who_made` / `_when_made` / `_is_supply` Selection / Boolean fields.
- [ ] T402 [P-LIST-HOW-ITS-MADE] Publisher: resolve listing override → product.template fallback (existing fields from Spec 011 P-PUB-PER-PRODUCT-DEFAULTS) → `etsy.shop.default_*`.
- [ ] T403 [P-LIST-HOW-ITS-MADE] Phase 1 DB + Phase 2 ORM tests covering the 3-tier fallback chain.
- [ ] T404 [P-LIST-HOW-ITS-MADE] Form view: 3 widgets in the Listing form's Etsy tab.
- [ ] T405 [P-LIST-HOW-ITS-MADE] Owner docs + TC.
- [ ] T406 [P-LIST-HOW-ITS-MADE] Phase 9 staging deploy.

---

## P-LIST-ATTRIBUTES — Wave 2 / Jira ESTY-192 (Etsy step: matching attributes)

- [ ] T501 [P-LIST-ATTRIBUTES] New `multichannel.listing.attribute.mapping` model: `(listing_id, product_attribute_id, etsy_property_id)`.
- [ ] T502 [P-LIST-ATTRIBUTES] `multichannel.listing.attribute_mapping_ids` O2M → mapping rows.
- [ ] T503 [P-LIST-ATTRIBUTES] Publisher `_property_value_for` reads override map → falls back to `product.attribute.x_etsy_property_id`.
- [ ] T504 [P-LIST-ATTRIBUTES] Phase 1 DB + Phase 2 ORM tests for the override path.
- [ ] T505 [P-LIST-ATTRIBUTES] Form view: editable inline list of mapping rows on the Listing form.
- [ ] T506 [P-LIST-ATTRIBUTES] Owner docs + TC.
- [ ] T507 [P-LIST-ATTRIBUTES] Phase 9 staging deploy.

Pairs with P-LIST-ATTR-CONFIG for the shop-level layer.

---

## P-LIST-ATTR-CONFIG — Wave 2 / Jira ESTY-194 (Etsy step: shop & product attribute config)

- [ ] T601 [P-LIST-ATTR-CONFIG] Add `etsy.shop.default_attribute_mapping_ids` O2M → reuse `multichannel.listing.attribute.mapping` model with `(shop_id)` discriminator OR a new sibling model — decide in plan phase based on schema cleanliness.
- [ ] T602 [P-LIST-ATTR-CONFIG] Resolver: `_property_value_for` falls back through listing override → shop default mapping → global `x_etsy_property_id`.
- [ ] T603 [P-LIST-ATTR-CONFIG] Phase 1 DB + Phase 2 ORM tests cover 3-tier chain.
- [ ] T604 [P-LIST-ATTR-CONFIG] Form view: shop config tab "Attribute Defaults".
- [ ] T605 [P-LIST-ATTR-CONFIG] Owner docs + TC.
- [ ] T606 [P-LIST-ATTR-CONFIG] Phase 9 staging deploy.

---

## P-LIST-SHOP-BULK — Wave 2 / Jira ESTY-197 (Etsy step: inventory / shop scope bulk ops)

- [ ] T701 [P-LIST-SHOP-BULK] Add list-view filter on `multichannel.listing.shop_ref` (saved-search per shop) + search panel.
- [ ] T702 [P-LIST-SHOP-BULK] Server action: "Mark Ready for Publish" — bulk-edit `state: draft → ready` (FR-017 BA-gate).
- [ ] T703 [P-LIST-SHOP-BULK] Server action: "Publish to Etsy" — bulk-trigger `EtsyListingPublisher.run()` per row.
- [ ] T704 [P-LIST-SHOP-BULK] Phase 1 DB + Phase 2 ORM tests for both server actions.
- [ ] T705 [P-LIST-SHOP-BULK] Owner docs + TC.
- [ ] T706 [P-LIST-SHOP-BULK] Phase 9 staging deploy.

Pairs with the marketing bulk-edit workflow per US3.

---

## Dispatch order (recommended)

1. `P-SPEC-LISTING-MODEL-SPLIT` — T001-T004 (this slice; doc-only).
2. `P-LIST-MODEL` — T010-T020 (model + backfill foundation).
3. Wave-2 slices in Etsy "How to Create a Listing" article order:
   - `P-LIST-VIDEO` (or any order from here, after T020).
   - `P-LIST-CATEGORY`.
   - `P-LIST-SHIPPING`.
   - `P-LIST-HOW-ITS-MADE`.
   - `P-LIST-ATTRIBUTES`.
   - `P-LIST-ATTR-CONFIG`.
   - `P-LIST-SHOP-BULK`.

Each slice runs the full 9-phase playbook (see `.claude/plans/006-implementation-playbook.md`).

## References

- ADR-015 (decision)
- `docs/jira/in-progress-2026-06-04.md` (Wave classification + Jira tickets)
- ADR-013 (etsy.listing read-only mirror)
- ADR-014 (Odoo as central product hub)
- ADR-003 (channel-agnostic models live in `multichannel_hub_core`)
- `~/.cache/etsy-developer-docs/` (Etsy v3 endpoint docs)
- `/tmp/etsy_oas.json` (Etsy OpenAPI 3.0.2 spec — search for `videos`, `seller-taxonomy`, `shipping-profiles`, `properties`, `variation-images`)
