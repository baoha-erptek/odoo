# Findings — Spec 011 (Etsy Outbound Publish)

## P-HUB-SPEC (planning slice) — 2026-05-23

- **Spec 008 P-LIST-INV-PUSH supersession.** The deferred Slice 3 of Spec 008 (entire-array-resubmit inventory writeback) is absorbed into Spec 011 P-PUB-INVENTORY. Reasons: (a) the publisher state machine needs the same PUT path; (b) the canonicalisation wizard (Spec 009 P-HUB-SKU-DRIFT) needs the same; (c) a single owner avoids duplicate retry/audit/rollback code. Spec 008 tracker row stays in place with `superseded by P-PUB-INVENTORY` annotation; the planned `wizards/etsy_listing_push_wizard.py` is not built — its intent is split between `EtsyInventoryPusher.push` (service) and `etsy.publish.wizard` (UI).
- **Owner SKU policy fully resolved by ADR-014 §4.** Two questions answered in-session 2026-05-23: new publishes use v2-canonical; canonicalisation of live listings auto-pushes. Both encoded in P-PUB-DRAFT (SKU resolution at payload-build time) and P-PUB-INVENTORY (entry point reused from canonicalisation wizard).
- **Per-shop Etsy defaults are minimal in MVP.** Only taxonomy / shipping-profile / return-policy IDs are mandatory + `who_made` / `when_made` / `is_supply` enums. Other Etsy fields (`materials`, `tags`, `style`) default to NULL and are accepted by Etsy. Expansion is per-product or per-shop overrides if data shows variation post-MVP.
- **Resumability uses `product.channel.status` state, not a new model.** State machine: `draft` → `published` → `archived` / `error`. The `external_ref` field carries the Etsy listing ID across steps; the `last_sync_error` field carries the last 4xx body for operator triage. Avoids over-engineering a separate `publish.job` model.
- **One concrete publisher, no abstract base.** YAGNI: there's no second channel today. When Amazon arrives, we'll refactor (or not) based on actual shared shape, not anticipated shape.
- **Image diff via SHA-256 manifest on `etsy.listing` (JSON Text).** Listing-side manifest (channel scope), not product-side (would conflate channels). Future Amazon will have its own manifest on `amazon.listing`.
- **No webhook handling for Etsy-side listing edits.** Out of scope. Drift detection (Spec 008 P-LIST-INV-PULL) already surfaces qty drift; title/description drift surface is a future enhancement, not a publish-blocker.
- **Coordination point with Spec 010**: new `etsy.api.log` `source` values are added in a single Selection extension (Spec 011 P-PUB-CLIENT T002) that covers both spec families' new values, so we don't run two migrations.
- **Pure-doc slice (this planning artifact).** No code/tests; Two-Phase Testing N/A for P-HUB-SPEC.
- **Reused codebase invariants pre-loaded into tasks.md**: FR-017 method-top gates (memory `feedback_fr017_write_defense_in_depth` 20+ confirmations); 4xx vendor-body capture with durable cursor (memory `feedback_capture_response_body_before_blackbox_probe`); SKU policy from ADR-014 §4; `etsy_api_shop_id` field for URL construction per memory `reference_etsy_shop_id_mapping`.

## P-PUB-CLIENT — 2026-05-23

- Landed cleanly. 4 thin wrappers (`post/put/patch/post_multipart`) route through the existing `_request` helper, inheriting auth + rate-limit + 401-refresh + 429-retry + 4xx-body-capture. No surprises.
- `_read_credentials` patching pattern at module scope (used in P-PUB-DRAFT + P-PUB-INVENTORY tests too) — `cls.addClassCleanup(cls._creds_patcher.stop)` is the idiom; works around the constructor reading `/opt/odoo/secrets/credentials.json` in test runs.

## P-PUB-DRAFT — 2026-05-23

- Landed. Single service file `etsy_listing_publisher.py` with `EtsyListingPublisher.create_draft`. SKU resolution per ADR-014 §4. 4xx → ValueError → caller transaction rolls back; durable error-status row deferred to **P-PUB-PUBLISH** orchestrator (T026) which owns the resumable state machine.

## P-PUB-INVENTORY — 2026-05-23

- Landed. `push_inventory(tmpl, listing_id, shop)` + standalone `EtsyInventoryPusher.push(tmpl, shop)` alias (for the Spec 009 P-HUB-SKU-DRIFT checkpoint b hook).
- **SKU resolution at template level, not variant level** — initial implementation tried `variant.default_code or _resolve_sku(tmpl)` but Odoo auto-inherits template default_code onto variants, so variant.default_code is non-empty even when there's no explicit per-variant override. That defeats ADR-014 §4 v2 rule. Corrected to always use `_resolve_sku(tmpl)` for now; per-variant override left for a future slice when a real multi-variant publish surfaces a divergence. (RED test flagged this on first GREEN attempt.)
- `_sync_inventory_snapshot` decodes Etsy's `{amount, divisor}` price format on PUT response.

## P-PUB-IMAGES — STOP-and-escalate 2026-05-23

- **Blocker**: Spec 011 tasks.md T013 specifies `product.image.x_image_sha256_cache` Char field. The `product.image` model **does not exist in Odoo 19 CE** — checked `/opt/odoo/addons/product/models/`: no image-prefixed file, no `_name = 'product.image'` declaration anywhere. Odoo 19 CE products use `image_1920` / `image_128` Binary fields directly on `product.template` and `product.product`.
- This appears to be a planning-doc artifact from a different Odoo edition (Enterprise has `product.image`, CE does not) or an older Odoo version.
- **Options** to unblock (need owner decision):
  - **A.** Re-scope T013 to `product.template.x_image_sha256_cache` (single hash per template image_1920). Drops multi-image-per-product support; JaHandmadeArt pilot is single-image so fine for MVP.
  - **B.** Drop manifest diff entirely — re-upload the template image on every publish. Simplest; trade-off is wasted bandwidth on un-changed publishes. Etsy throttling (TokenBucket(2, 10)) absorbs the cost for the pilot.
  - **C.** Bring in `image` addon if it provides `product.image` (need to verify; this would be a manifest dep change).
- **Recommended**: B for now (drop manifest diff); revisit if multi-image-per-listing surfaces as a real need. Cleanest minimum-change.
- Slice frozen here pending owner choice; tracker P-PUB-IMAGES row stays `todo`.

## E2E surfacing (live)

_(none yet — implementation not started)_

## P-DOCS-HUONG-DAN-V12 — 2026-05-28

Doc-only slice rewriting `docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md` v1.1 → v1.2 (and syncing `FLOW_TAO_SAN_PHAM_VN.md`). Phase 3 pre-flight locks the spec-drift facts below against the 9 code commits landed 2026-05-27/28 so the new prose matches shipped behavior (memory `feedback_phase1_spec_drift_check`).

| Code slice | Commit | Field facts the doc must reflect |
| --- | --- | --- |
| P-HUB-SKU-AUTODERIVE | 8df9b524b42 | `product.category.x_sku_family_id` (M2O → `mhc.sku.family`, parent-chain inheritance); template onchange on `categ_id` + `attribute_line_ids` auto-fills `default_code` if blank or matches prior suggestion; dirty-flag preserved via `x_sku_v2_status` ≠ `'suggested'`; legacy preserved via `'ba_approved_legacy'`; variant onchange on `product_template_attribute_value_ids` for variant SKU; create() override for last-chance autofill; Classic + SKU Builder wizard menus hidden (`active="False"`); migration 19.0.1.0.55 best-effort seeding of category family by name. |
| P-PUB-TAGS | 25bddd05418 | Standard `product.tag` M2M reused — no new model. Validator `@api.constrains` on `product_tag_ids`: ≤ 13 tags, each ≤ 20 chars, charset `[A-Za-z0-9 \-']`. View: "Listing Tags" page in Channels notebook, many2many_tags widget, no_create_edit. Publisher omits `tags` key entirely when empty. |
| P-PUB-MULTI-IMAGE | 03f763863f8 | NEW `multichannel.product.image` (custom mini-gallery — `product.image` lives in website_sale only and pulls 10 deps). Fields: name, sequence default 10, image_1920, product_tmpl_id (required, ondelete=cascade, indexed). One2many on `product.template.x_extra_image_ids`. "Extra Images" page in Channels notebook (sequence handle + image widget). Publisher caps at ETSY_MAX_IMAGES=10 (main + extras); 11th+ logs WARNING. Per-image upload failure logs WARNING and continues. |
| P-PUB-PERSONALIZATION | 39bbc2843d2 | 4 fields on `product.template`: `x_is_personalizable` Bool · `x_personalization_required` Bool · `x_personalization_char_count` Integer (default 256, validator range 1–1024 when feature on) · `x_personalization_instructions` Text. View: "Listing Options" page (collapsed via `invisible="not x_is_personalizable"`) between Tags and Extra Images. Publisher emits 4 Etsy keys (`is_personalizable`, `personalization_is_required`, `personalization_char_count_max`, `personalization_instructions`) only when feature ON; absent when OFF. |
| P-PUB-PER-PRODUCT-DEFAULTS | c637b4058ef | 3 channel-agnostic override fields on `product.template`: `x_taxonomy_id` Char (mirrors shop default — Char type to survive int4 overflow on IDs ≥ 285B) · `x_who_made` Selection (3 enums identical to shop default) · `x_when_made` Selection (19 canonical Etsy enums made_to_order → before_1700). View: "Listing Defaults" page; placeholder "Leave blank to use shop default". Publisher resolves `product → shop default → hardcoded` via Python `or`. `is_supply` intentionally NOT in product override (stays shop-wide). |
| P-PUB-MATERIALS | 80ae8a43a32 | No new field/model. Helper `_collect_materials(tmpl)` filters template attribute lines where `attribute.name == 'Material'` (or `x_namespace='MAT2'`), charset-cleans each value to Etsy whitelist (letters/numbers/whitespace), dedupes order-preserved, caps at 13. Listing-level (not per-variant) — walks template attribute lines, sidesteps dynamic-variant empty M2M trap. Empty → `materials` key omitted. |
| P-PUB-VARIANT-PROPERTIES | 9ce4e93df1d | 2 new fields on `product.attribute` (etsy_integration extension): `x_etsy_property_id` Char (not Integer — XML-RPC int32 trap) + `x_publish_as_property` Boolean default=False (opt-in gate, fail-closed per security review). Seed XML flips True for **six** known publishable axes (Material, Color, Size, Shape, Fluid oz, Apparel Size); Family stays False. View-level `groups="base.group_system"` restricts mapping config to admin. Helper `_collect_property_values(variant)` walks per-variant `product_template_attribute_value_ids`; skips axes flagged False; falls back to attribute name + WARNING when `x_etsy_property_id` empty; returns `[]` for empty M2M (dynamic-variant axis). |
| P-PUB-WEIGHT-DIMENSIONS | 8a04a7df21d | 2 system-group fields on `etsy.shop`: `weight_unit_pref` (Selection oz\|g, default 'oz') · `dimensions_unit_pref` (Selection cm\|in, default 'cm'). Weight from standard `product.template.weight` (kg base unit per Odoo) → `round(kg*35.274, 2)` for oz or `round(kg*1000, 2)` for g; weight ≤ 0 omits weight keys (Etsy treats absence as no weight). Dimensions parsed from template Size attribute value name via regex `^[Rr]?\s*(\d+)\s*[xX×]\s*(\d+)` — Rect "R30X18" → length=30, width=18; Mug "11 oz" correctly does NOT match → dimensions omitted, weight only. All-or-none dimension emit. |
| P-PUB-PRICING-STANDARDISE | eacad7a0565 + 75e5b1d51b9 | (Not in §10 directly but relevant to creation flow) — Migrated `x_listing_price` writes to standard `list_price` (Monetary). 7 missed write sites caught in Phase-4 remediation. Doc must say BA fills the standard "Sales Price" field (USD for Etsy listing). |

**Doc decisions derived**:
- Plain-view rule fix (memory `feedback_end_user_docs_plain_view`): v1.1 line 5 names `multichannel_hub_core` + `etsy_integration` — DELETED in v1.2 (cleanest, no replacement line; sibling owner docs FLOW_*VN.md don't carry it either).
- §10 new content covers 7 sub-sections (Tags / Personalization / Materials / Multi-image / Per-product overrides / Weight & Dimensions / Variant properties). "Standard `list_price`" mention woven into §3 (creation flow), not §10.
- Section numbering: deleting §3 (two-path table) + §4 (Classic Wizard) + §5 (SKU Builder) + §6 (validator deep-dive) leaves 6 remaining sections to renumber; new §10 placed right after §3 creation flow (paired contextually) — final layout §1-§10.
- Wizard mentions purged from body text. Mentioned only in §3 historical note + §11 FAQ ("đã từng có Wizard riêng — nay form chuẩn đã đủ").
- UAT TC-008..TC-012 (wizard-specific) deleted; new TC-008..TC-015 cover the 9 fields + per-product overrides.
- Validator v2 grammar deep-dive (old §6) reduced to one-line note in §3 + brief FAQ entry.
- Screenshots out of scope; sibling slice candidate noted.
- Doc-only slice → skip Phase 2 (RED), Phase 4 security-reviewer, full Phase 8 (light learn note OK).
