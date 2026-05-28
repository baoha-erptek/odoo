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

## P-UAT-TAOSP-V12-RERUN — 2026-05-28 (v1.2 standard-form UAT + fixes)

Live UAT of the v1.2 standard-form flow on staging `esty_odoo19`. Surfaced + fixed
three product defects (the standard form replaced the wizards in P-HUB-SKU-AUTODERIVE,
but the wizard's side-effects weren't fully migrated to the model layer):

- **Auto-SKU froze after first variant.** `_onchange_auto_fill_default_code` guard compared
  `default_code` to the name-only `x_sku_v2_suggested`; once it diverged (`MUG-CR`) later
  attribute additions stopped re-deriving. Fix: dirty-flag `x_sku_auto_value` declared
  `invisible` in the form arch so it round-trips across onchange calls (a non-arch helper
  field reads empty on each onchange — that was the real trap). mhc → 19.0.1.0.62, commit `dfd5209d274`.
- **`evaluate()` segment order was alphabetical by attribute name**, not grammar role.
  "11 oz" is on the **Fluid oz** attribute (not "Size"); `sorted(['Fluid oz','Material'])`
  yielded `MUG-F11-CR`. Fix: `_ATTR_ROLE_ORDER` (Material→MAT, Shape/Size/Fluid oz/Apparel
  Size→SIZE, Color→VAR2). The SKU builder wizard always had explicit roles; the auto-derive
  dict path never did.
- **`product.template` never created `product.channel.status` rows** — only the wizard's
  `action_create` did. Fix: `_sync_channel_statuses()` on `create()`/`write()` (additive,
  idempotent, never clobbers Published/Error).

Live-publish 400s (follow-up `R-PUB-RESPONSE-BODY-DIAGNOSE`): TC-005+TC-011 created real
drafts (path proven); TC-009/013/014 → createListing 400, TC-015 → inventory 400. The Etsy
client raises `raise_for_status()` without capturing the response body (anti-pattern per
`feedback_capture_response_body_before_blackbox_probe`) — capture body first, then per-feature fix.

## R-PUB-RESPONSE-BODY-DIAGNOSE — 2026-05-28 (Stage A landed)

**Stage A (body capture, commit `8ffdc992046`):** `EtsyApiClient._request()` now logs the
Etsy response body at WARNING (`"Etsy HTTP %d url=%s body=%r"`, truncated 500 chars) for any
status ≥ 400 that is not already handled. Order preserved: 401 refresh → 403 (ValueError +
body) → generic 4xx/5xx (body + `raise_for_status`). Previously `raise_for_status()` discarded
the body, so the validator message was lost. Tests: new `TestEtsyApiClient4xxBodyCapture`
(400/422 logged, 500-char truncation guard, empty-body no-crash, 403 regression). Two
pre-existing ping tests (403/500) had to set `mock_response.text` — the 403 test was **already
erroring on HEAD** (the earlier 403-capture block read `.text`, which an unset Mock can't
slice); the 500 test entered the new block. 25/25 client tests green; reviewers 0 CRITICAL,
security APPROVED (header auth → no token in body/url; `%r` repr safe).

**Stage B (per-feature payload fixes) — BLOCKED on live capture.** The exact fixes for
TC-009/013/014 (createListing 400) + TC-015 (PUT inventory 400) are unknowable until a live
staging run with Stage A deployed prints the real Etsy bodies. TC→feature diagnostic checklist
(payload builders in `services/etsy_listing_publisher.py`):

| TC | Endpoint | Feature | Suspect payload area |
| --- | --- | --- | --- |
| TC-009 | POST listings | Personalization | `is_personalizable` / `personalization_is_required` / `personalization_char_count_max` / `personalization_instructions` |
| TC-013 | POST listings | Taxonomy override | `taxonomy_id` (from `x_taxonomy_id` Char) |
| TC-014 | POST listings | Weight + dimensions | `item_weight*` / `item_length/width/height*` unit+value |
| TC-015 | PUT inventory | Variant property_values | `property_values: [{property_id, value_ids|values}]` shape |

Live run needs owner go-ahead — it creates real JaHandmadeArt drafts
(`RUN_ETSY_PUBLISH=1`, `LIVE_PRICE=250000`, staging `esty_odoo19`).

### Stage B live capture — 2026-05-28 (owner-approved live run)

Deployed Stage A to staging (etsy_integration upgraded, `esty19_odoo` restarted), ran the
four live TCs with `RUN_ETSY_PUBLISH=1` (workers=1). The captured 4xx bodies **revise the
scope**: only **two** of the four TCs are publisher-payload bugs. Verbatim bodies:

| TC | Endpoint | HTTP | Captured body | Verdict |
| --- | --- | --- | --- | --- |
| TC-009 | `POST shops/60752333/listings` | 400 | `Legacy personalization fields (is_personalizable, personalization_instructions, personalization_is_required, personalization_char_count_max) are deprecated. Use the dedicated personalization endpoints instead. See .../personalization-migration/` | **Real bug — Etsy API deprecation.** Publisher emits the 4 inline fields at `etsy_listing_publisher.py:220-224`. Etsy now rejects them on createListing. |
| TC-013 | createListing | — | (no Etsy 4xx) draft `4512532828` created, wizard returned `act_window_close listing_id=4512532828` | **NOT a payload bug.** Publish succeeded. Playwright failure is test-side (`external_ref` assertion / timing), not Etsy. |
| TC-014 | createListing | — | (no Etsy 4xx) draft `4512532970` created | **NOT a payload bug.** Publish succeeded; same test-side failure class as TC-013. |
| TC-015 | `PUT listings/{id}/inventory` | 400 | `No products supplied` (listings `4512531293`, `4512531621` — createDraft succeeded first) | **Real bug.** `push_inventory` (`:338-350`) iterates `product_variant_ids`, which is **empty** for this template: TC-015 mixes Material (`create_variant=always`) + **Color (`create_variant=dynamic`)**, so Odoo does not materialize variants → empty `products[]`. |

DB check confirms attribute variant modes: `Material=always`, `Fluid oz=always`, `Color=dynamic`.

**Revised Stage B work:**
1. **TC-015 (mechanical, in-scope):** `push_inventory` must emit ≥1 product offering even when
   `product_variant_ids` is empty (dynamic-variant templates) — build a fallback single product
   entry (template SKU + offering, `property_values=[]`) so Etsy gets a non-empty `products[]`.
2. **TC-009 (DECISION — escalated to owner):** Etsy deprecated inline personalization. Options:
   (a) stop emitting the 4 fields → draft publishes but personalization feature regresses;
   (b) implement Etsy's dedicated personalization endpoints → new feature, own slice;
   (c) gate emission off behind a flag until (b) ships. Shipped feature is P-PUB-PERSONALIZATION,
   so this is the owner's call, not a unilateral drop.
3. **TC-013 / TC-014 (out of payload scope):** publishes succeeded; route the `external_ref`
   test-side failure to a separate test-fix/investigation follow-up — not an Etsy payload edge.

### Stage B fixes + batched live re-run — 2026-05-28 (GREEN)

Both genuine payload bugs fixed (commit `643370c9837`):
- **TC-009 personalization gate-off** — `_build_create_draft_payload` no longer emits the 4
  deprecated keys; logs a WARNING when the feature is on; Odoo fields/UI preserved. mhc field
  help text updated (mhc 19.0.1.0.63). etsy_integration → 19.0.2.25.0.
- **TC-015 inventory fallback** — `push_inventory` emits one fallback product offering (template
  SKU, `property_values=[]`) when `product_variant_ids` is empty (dynamic-variant template).

Phase-2 tests: personalization payload tests inverted (keys always absent + Odoo fields persist);
new dynamic-variant `push_inventory` test. 49 publisher-suite tests green; reviewers 0
CRITICAL/HIGH; security APPROVED.

**Live re-run (`RUN_ETSY_PUBLISH=1`, staging, workers=1): 3 passed / 1 failed.** Staging logs show
**zero** Etsy 4xx (no "Legacy personalization", no "No products supplied"); 3 real drafts created
(listing_ids `4512535947`, `4512536539`, `4512538286`):
- TC-009 personalization → **PASS** (draft published)
- TC-013 taxonomy → **PASS**
- TC-015 variant property_values → **PASS** (inventory pushed)
- TC-014 weight → **FAIL** but on `locator.fill timeout` at `fillWeight(0.35)` — a **test-side UI
  timeout**, never reached the Etsy publish. Confirms TC-014 is the test-side class, not a payload bug.

**Follow-up slices opened (tracker):**
- `R-PUB-PERSONALIZATION-ENDPOINTS` — integrate Etsy's dedicated personalization-migration
  endpoints so the preserved Odoo personalization data reaches Etsy again.
- `R-UAT-TAOSP-TC013-014-TESTSIDE` — fix the TC-013/TC-014 test-side flakiness (TC-013 `external_ref`
  assertion timing; TC-014 `fillWeight` weight-field locator timeout). Publish path itself is proven.

## P-UAT-TAOSP-V12-RERUN operability notes (cont.)

Operability: JaHandmadeArt is a **VND** shop (Etsy min ~5,043 VND) — live TCs use
`LIVE_PRICE=250000`; standard form lazy-renders notebook pages (re-open General tab before
reading `default_code`); bare-family SKU triggers Odoo's "Internal Reference already exists"
Note dialog (auto-dismissed). Owner UAT findings: `docs/owner/UAT_FINDINGS_2026-05-28.md`.

## R-PUB-PERSONALIZATION-ENDPOINTS — endpoint contract research (2026-05-28)

Source: https://developers.etsy.com/documentation/tutorials/personalization-migration/ +
.../personalization/endpoint-migration. Inline createListing fields deprecated 2026-02-06,
removed 2026-04-09. Replacement is a dedicated per-listing personalization endpoint suite.

**Endpoints (migration period):**
- `GET /v3/application/listings/{listing_id}/personalization` — read; returns
  `personalization_questions[]` (empty when none).
- `POST /v3/application/shops/{shop_id}/listings/{listing_id}/personalization` — create/update;
  **fully replaces** existing personalization. Body `personalization_questions[]` must contain
  **exactly one** question object during the migration period (multi-question + dropdown +
  file-upload types come later in 2026).
- `DELETE /v3/application/shops/{shop_id}/listings/{listing_id}/personalization` — removes
  personalization and sets `is_personalizable=false`.

**POST body (single text_input, migration period):**
```json
{"personalization_questions": [{
  "question_type": "text_input",
  "question_text": "Personalization",
  "instructions": "<=256 chars",
  "required": true,
  "max_allowed_characters": 256   // int, valid 1-1024
}]}
```

**Sequencing:** POST/DELETE need a `listing_id` → must run AFTER `create_draft` in the publisher
`run()` chain (same lifecycle slot as `push_inventory`). Uses `shop.etsy_api_shop_id` for the
`{shop_id}` path segment (same field the other publisher calls use).

**Odoo → Etsy field mapping** (fields on `product.template`, defined in `multichannel_hub_core`):

| Odoo field (mhc) | type / default | → Etsy POST key |
|---|---|---|
| `x_is_personalizable` | Boolean / False | gate: True → POST one question; False → DELETE (or no-op on fresh draft) |
| `x_personalization_required` | Boolean / False | `required` |
| `x_personalization_char_count` | Integer / 256 | `max_allowed_characters` (clamp to 1-1024) |
| `x_personalization_instructions` | Text / — | `instructions` (truncate to ≤256 chars) |

No Odoo field maps to `question_text`/`question_type` → constants `"Personalization"` / `"text_input"`.
Scopes: `listings_w` (write listings) — same scope set already used by createListing/inventory.

### Implementation outcome (landed)
`EtsyListingPublisher.push_personalization(tmpl, listing_id, shop)` — no-op returns `{}` when
`x_is_personalizable` is False; otherwise POSTs one `text_input` question. Wired into `run()`
**after** create_draft/resume, **before** `upload_images`, in a **non-fatal** `try/except` (a
personalization failure logs a WARNING and the listing still publishes). createListing payload
no longer emits the deprecated inline keys (and the obsolete "pending slice" WARNING is removed).

**Design correction vs. the research note above** (caught at RED, the planner could not know it):
`max_allowed_characters` is **NOT clamped** in the publisher — `product.template` already carries
`@api.constrains _check_personalization_char_count` (mhc `product_template.py`) pinning
`x_personalization_char_count` to 1-1024 whenever personalization is on, so out-of-range is an
impossible state at the ORM boundary; clamping would be dead code (dropped per "no validation for
impossible scenarios"). `instructions` IS truncated to 256 (the Text field is unbounded — genuine
API-boundary validation). The `etsy.api.log` source enum was deliberately NOT extended: the sibling
publisher source values are unemitted vocabulary, so a new one would be dead too.

Tests: `test_phase2_pub_personalization_endpoints_orm.py` — 8 Phase 2 ORM cases, GREEN; full
publish+personalization suites 17/17. Module installs clean. etsy_integration → 19.0.2.26.0.
DELETE-on-toggle-off is out of scope (no-op when False); revisit if operators need stale-removal.

## R-UAT-TAOSP-TC013-014-TESTSIDE — 2026-05-28 (Playwright test-side fixes)

Both failures from the 2026-05-28 batched live re-run were **test-side**, not Etsy payload bugs
(the publish path created real drafts for both — see Stage B above). Root causes:

- **TC-014 (`fillWeight` 15s timeout):** `weight` lives on the standard product form's **Inventory
  tab** (Logistics group), which Odoo 19 **lazy-renders**. `ProductFormPage.fillWeight` filled
  `[name="weight"] input` without first activating that tab, so the locator was never
  visible/actionable → `locator.fill` timed out before publish. Fix: `fillWeight` now `openTab(/Inventory|Tồn kho|Logistics|Hậu cần/)`
  + `waitFor({state:'visible'})` before fill (mirrors the `openGeneralTab` pattern the other
  field helpers already use).
- **TC-013 (`external_ref` assertion race):** the shared `channelStatus` helper read
  `product.channel.status.external_ref` **once** immediately after `publishDraftOnly()` returned;
  the listing id is not necessarily committed/propagated to the status row by then → intermittent
  `toBeTruthy()` failure despite a successful publish. Fix: new `pollExternalRef(request, code, 15000)`
  re-queries every 1s until `external_ref` is truthy (or timeout); TC-013 + TC-014 now use it.

No Odoo module code changed (test harness only): `tests/e2e/page-objects/product_form.ts`
(`fillWeight`) + `tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts` (`pollExternalRef` + the two
assertions). Verified via `playwright test --list` (clean compile + collection, 15/15 listed); no
local `tsc`/typescript dep in `tests/e2e` (Playwright transpiles at runtime). The live
`RUN_ETSY_PUBLISH=1` green re-run on JaHandmadeArt is queued for an owner-scheduled Etsy window.

---

## P-UAT-AUTOMATION-SKILL — UAT loop packaged as `run-uat` skill (2026-05-28)

Tooling/doc-only slice (no module code). Created `.claude/skills/run-uat/SKILL.md` —
a procedure skill that sequences the existing building blocks: reset staging products
→ rsync+docker module deploy+restart → seed → Playwright suite → report.

Two drifts surfaced while inventorying the building blocks (cross-checked against current code):

- **Live-price env var is `E2E_LISTING_PRICE`, not `LIVE_PRICE`.** The spec
  (`tests/uat_huong_dan_tao_san_pham.spec.ts:29`) reads
  `Number(process.env.E2E_LISTING_PRICE || 250000)` into a local const named `LIVE_PRICE`.
  Prior tracker/notes shorthand ("VND price", "LIVE_PRICE") refers to the const, not the
  env var operators must export. Skill documents `E2E_LISTING_PRICE=250000`.
- **Staging DB is `esty_odoo19`, not `demo_esty`.** The `reference_staging_ssh_deploy`
  memory (6 days old) still says `demo_esty`; the live contract (`package.json` reset scripts,
  `_xmlrpc_session.connect`, `env.ts` defaults) is `esty_odoo19`. Skill pins `esty_odoo19` and
  flags the stale name.

No RED/GREEN — verification was cross-reference resolution: 8 building-block paths + 10 npm
scripts + the SSH key all resolve; skill registers and is discoverable in the skill list.

## R-PUB-IMAGE-SHOP-SCOPED-PATH (real-product UAT, 2026-05-28)

Real-catalog-apron UAT (`tests/e2e/tests/uat_real_apron_publish.spec.ts`, TC-R01) created an
Etsy draft with **0 photos** despite both images being set on the Odoo product
(`image_1920` + one `x_extra_image_ids` row).

**Root cause:** `EtsyListingPublisher.upload_images` posted to `listings/{id}/images`. Etsy's
`uploadListingImage` endpoint is **shop-scoped** — `shops/{shop_id}/listings/{id}/images` — so
every upload returned **404**, swallowed by the per-image `except ... WARNING; continue` guard.
`create_draft` and `push_personalization` were already shop-scoped; `upload_images` was the
lone miss. Direct `post_multipart('listings/{id}/images')` → 404; `shops/{shop_id}/listings/...`
→ 200 (`listing_image_id` returned).

**Fix** (etsy 19.0.2.26.0 → 19.0.2.27.0): resolve `shop.sudo().etsy_api_shop_id` (raise if
missing, mirroring create_draft) + shop-scoped path. Phase-2 test path assertion updated +
new `test_upload_images_raises_when_shop_id_missing`. 9/9 image tests pass; live re-run draft
`4512579307` has 2 photos. The silent-404 was only catchable because the UAT verified the
listing's image count via the Etsy API — the per-image WARNING masked it from the publish flow
(matches memory `feedback_capture_response_body_before_blackbox_probe`).

## Variant property_values not pushed for dynamic-only axes (real-product UAT, 2026-05-28)

The apron used **Color** (a `create_variant='dynamic'` seed attribute) as a variant axis.
Dynamic-only axes don't materialise `product.product` variants, so `push_inventory` emitted
the **no-variants fallback offering** (single offering, bare SKU `APR`, empty `property_values`)
rather than per-color Etsy variations. This is the documented fallback (memory #152), not a
regression. `materials=['Textile']` still propagated (derived from the template attribute line,
independent of variant materialisation). For true Etsy variations with per-variant SKUs, the
product needs materialised variants (an `always`-create axis, or a materialise-before-publish
step). Candidate follow-up: a `R-PUB-VARIANT-MATERIALIZE` slice — owner decision.
