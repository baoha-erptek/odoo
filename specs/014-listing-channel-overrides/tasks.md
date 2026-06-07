# Tasks — Spec 014 / P-ENH-ESTY-190 (Listing Channel Overrides)

Phase numbering follows `.claude/plans/006-implementation-playbook.md` per-slice 9-phase loop. Each task is atomic and Phase-tagged.

## Parent spec-authoring slice (THIS commit)

- [X] T001 Standard-Odoo-First gate — grep CE for per-product overrides; grep custom_addons for existing listing fields. Verdict: P-LIST-MODEL already shipped `multichannel.listing.title`/`.description`/`.image_1920`. Tracker note `mhc.product.channel.copy` is stale/redundant.
- [X] T002 Existing override surface inventory — `multichannel.listing.title` (Char), `.description` (Text), `.image_1920` (Image); `product.template.name`, `.description_sale`, `.image_1920` (standard fields); `etsy.shop` ships `default_taxonomy_id`, etc., but NO `default_title`, `default_description`, `default_image_1920`.
- [X] T003 ADR scope decision — new ADR-017 (free; ADR-015/016 occupy range). Three-layer fallback chain (listing → product → shop).
- [X] T004 Model redundancy analysis — reuse `multichannel.listing.title`/`.description`/`.image_1920` exactly; add only shop-level **defaults** to `etsy.shop`; NO new model.
- [X] T005 Write `specs/014-listing-channel-overrides/spec.md`.
- [X] T006 Write `specs/014-listing-channel-overrides/tasks.md` (this file).
- [X] T007 Write `specs/014-listing-channel-overrides/findings.md` skeleton with T001/T002/T003/T004 evidence pre-filled.
- [X] T008 Write `specs/006-master-plan/adrs/ADR-017-listing-channel-overrides.md`.
- [X] T009 Update tracker row P-ENH-ESTY-190 — link to spec 014 + ADR-017; state stays `todo` (code slice not yet dispatched).
- [X] T010 Conventional commit on `feature/006-master-plan-coding`: `[docs] docs(P-ENH-ESTY-190): author spec 014 + ADR-017 — Wave-3 listing channel overrides`.

## Child code slice (NEXT `/dispatch-slice` invocation)

Estimated LOC: **~110 LOC** total (20 models, 20 views, 10 data, 60 tests). Model tier: **Haiku** (straightforward field additions; reuses existing publisher patterns from P-ENH-ESTY-195 ADR-016).

### Phase 1 — Plan

- [X] T101 Dispatch `planner` agent (Haiku) with spec 014 + ADR-017 as input. Output: file-by-file diff outline. Expected files: `etsy_shop.py` (3 fields), `multichannel_listing_etsy_views.xml` (shop form extend), `etsy_listing_publisher.py` (3 fallback methods), test files.

### Phase 2 — RED

- [X] T201 `tests/test_p_enh_esty_190_phase1_db.py` — 4 Phase-1 DB assertions per spec §6 (column existence, widths, nullability).
- [X] T202 `tests/test_p_enh_esty_190_phase2_orm.py` — 8 Phase-2 ORM tests per spec §6 (fallback chain: listing → product → shop for title/description/image; debug logging; end-to-end integration).
- [X] T203 Verify all 12 tests RED before any code.

### Phase 3 — GREEN

- [X] T301 Extend `custom_addons/etsy_integration/models/etsy_shop.py`:
  - Add `default_title` Char(140), nullable, help text "Fallback when listing and product title both empty."
  - Add `default_description` Text, nullable, help text "Fallback when listing and product description both empty."
  - Add `default_image_1920` Image(max_width=1920, max_height=1920), nullable, help text "Fallback when listing and product image both empty."
- [X] T302 Extend `custom_addons/etsy_integration/models/etsy_listing_publisher.py` (or new service file, if planner recommends):
  - Add `_resolve_title_with_shop_fallback(listing, shop)` → listing.title OR product.name OR shop.default_title OR ''.
  - Add `_resolve_description_with_shop_fallback(listing, shop)` → listing.description OR product.description_sale OR shop.default_description OR ''.
  - Add `_resolve_image_with_shop_fallback(listing, shop)` → listing.image_1920 OR product.image_1920 OR shop.default_image_1920 OR False.
  - Each method emits DEBUG log "multichannel.listing %s: resolved [title|description|image] from [listing|product|shop] (shop_id=%s)" when fallback triggers.
  - Update `_build_create_draft_payload()` to call the three resolve methods instead of inline fallback logic.
- [X] T303 Extend view in `custom_addons/etsy_integration/views/etsy_shop_*.xml` (or create new view file):
  - Add three new fields to the etsy.shop form: `default_title` (Char widget), `default_description` (Text widget), `default_image_1920` (Image widget).
  - Tooltip on each: "Optional. Used when listing and product overrides are empty."
  - Position them near existing `default_taxonomy_id` / `default_shipping_profile_id` block.
- [X] T304 Add data file reference to `__manifest__.py` `data` list if new view file created. Bump etsy_integration version `19.0.3.8.0 → 19.0.3.9.0` (point release).
- [X] T305 Optional: Create `custom_addons/etsy_integration/data/etsy_shop_defaults_demo.xml` seed file with demo shop defaults (if demo data is used). Otherwise, skip (fields default to NULL).
- [X] T306 Run tests: all 12 GREEN under `--test-tags /etsy_integration`.

### Phase 4 — Review (parallel)

- [X] T401 `code-reviewer` agent (Haiku) — single Agent call.
- [X] T402 `security-reviewer` agent (Haiku) — single Agent call (parallel with T401).
- [X] T403 Apply all CRITICAL/HIGH findings; document accept/decline on MEDIUM/LOW.

### Phase 5 — Verify

- [X] T501 `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exit 0.
- [X] T502 Full suite regression: `--test-tags /etsy_integration` matches baseline 18 fail / 5 error of (728) — zero new regressions.
- [X] T503 Grep new code for `_logger.info(` / `print(` — must return zero hits per project rules.
- [X] T504 Run `ruff check custom_addons/etsy_integration/` — zero new lint hits.

### Phase 6 — Commit

- [X] T601 Single conventional commit on `feature/006-master-plan-coding`:
  `[etsy_integration] feat(P-ENH-ESTY-190): shop-level title/description/image defaults + 3-layer publisher fallback chain`

### Phase 7 — Document

- [X] T701 Update `docs/owner/HUONG_DAN_QUAN_LY_KENH_BAN.md` §5 (new) — "Cài đặt mặc định tiêu đề/mô tả/hình ảnh cho mỗi cửa hàng Etsy" (Vietnamese walkthrough with screenshots).
- [X] T702 Update `docs/owner/UAT_WALKTHROUGH_QUAN_LY_KENH_BAN.md` TC-025 (new row) — "Verify per-shop title default" (6-step test case).
- [X] T703 Update `.claude/plans/006-master-plan-tracking.md` row P-ENH-ESTY-190: `todo → done`, append ship note matching Wave-3 row format.
- [X] T704 Append Phase 3-9 surprises to `specs/014-listing-channel-overrides/findings.md`.

### Phase 8 — Learn

- [ ] T801 Invoke `/learn` to capture surprises into auto-memory (e.g. if fallback chain order surprises, or logging pattern differs from P-ENH-ESTY-195, etc.). Or explicit "no new patterns" note.

### Phase 9 — Land (staging)

- [ ] T901 `rsync` etsy_integration to staging (`secrets/ssh-key-2023-02-24.key`).
- [ ] T902 `sudo docker exec esty19_odoo odoo -u etsy_integration --stop-after-init` on staging.
- [ ] T903 Container restart healthy. psql confirms `latest_version='19.0.3.9.0'`.
- [ ] T904 Owner pinged via Telegram: "Wave-3 P-ENH-ESTY-190 landed on staging. Edit a shop's default title in Operations → Etsy Shops and publish a listing without title to verify fallback." (UAT step for owner discretion.)

## Exit criteria check (spec mini-slice — THIS commit)

- [X] Spec authored
- [X] ADR-017 authored
- [X] Tasks file authored
- [X] Findings skeleton authored
- [X] Tracker row updated to point at spec
- [X] Conventional commit lands

## Exit criteria check (child code slice — future commit)

Re-check at Phase 9 of the code slice. List in `spec.md §10`.
