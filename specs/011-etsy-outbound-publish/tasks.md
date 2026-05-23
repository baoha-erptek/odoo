# Tasks: Etsy Outbound Publish (Spec 011)

Dependency-ordered, slice-specific. Five implementation slices, all in `etsy_integration`. Each runs the MP006 9-phase loop and Two-Phase Testing.

Status legend: `[ ]` todo · `[~]` doing · `[X]` done.

**All slices depend on Spec 009 P-HUB-PROD-MODEL landing.**

---

## Slice P-PUB-CLIENT — API Client Write Methods + Shop Defaults

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T001 | [X] Extend `services/etsy_api_client.py` with `post()` / `put()` / `patch()` / `post_multipart()` — same auth + rate-limit + 401-refresh + audit + 4xx body capture as `get()` (all route through existing `_request`) | Spec 009 ✓, Spec 005 P0-15 ✓ | GREEN | |
| T002 | [X] Extend `etsy.api.log.source` Selection — added 7 values (listing_create / listing_image_upload / listing_image_delete / listing_inventory_push / listing_publish / catalog_import_run / catalog_image_download) | T001 | GREEN | Single source-list extension; Spec 010 reuses catalog_* values |
| T003 | [X] Extend `etsy.shop` with 6 default fields — `default_taxonomy_id` / `default_shipping_profile_id` / `default_return_policy_id` (Integer, `groups='base.group_system'`) + `default_who_made` (Selection) + `default_when_made` (Char) + `default_is_supply` (Boolean) | T001 | GREEN | |
| T004 | [X] `etsy.shop` form view extension — new "Publisher Defaults" notebook page, group_ba_user-visible, IDs gated to base.group_system | T003 | GREEN | |
| T005 | [X] RED Phase 1 (DB): all 7 new Selection values + all 6 new shop columns | T002,T003 | RED | |
| T006 | [X] RED Phase 2 (ORM): post/put/patch route via `_request` with correct method + body kwargs; post_multipart passes `files=`; shop defaults read/write by sudo; Selection options include `i_did/someone_else/collective` | T001,T002,T003 | RED | mock `_read_credentials` at module scope so EtsyApiClient construction works in tests without /opt/odoo/secrets file |
| T007 | [X] GREEN + Review + Verify + Commit | T005,T006 | GREEN→Land | review skipped per playbook small-slice exception — pure-additive (4 thin wrappers around existing _request; 6 fields w/ ACL parity to existing OAuth-token fields; +7 Selection values + 1 form-page xpath); no new business logic; FR-017 N/A (no action methods); etsy_integration 540 tests 0 NEW failures |

---

## Slice P-PUB-DRAFT — createDraftListing

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T008 | `services/etsy_listing_publisher.py` — `EtsyListingPublisher` class + `create_draft(product, shop)` method; builds payload with SKU per ADR-014 §4; refuses NULL shop defaults | P-PUB-CLIENT ✓ | GREEN | Single class, single channel — no abstract base (YAGNI) |
| T009 | On success: write `etsy.listing` row (state=`draft`, immutable url/created_at filled when Etsy returns them) + `product.channel.status` row (state=`draft`, external_ref=listing_id) | T008 | GREEN | |
| T010 | On 4xx: capture vendor body, write `product.channel.status.state='error'` + `last_sync_error`, rollback local writes | T008 | GREEN | `feedback_capture_response_body_before_blackbox_probe` pattern |
| T011 | RED Phase 2 (ORM): payload shape (mocked HTTP); SKU policy branches (v2-canonical / legacy / ba_approved_legacy); shop-defaults-missing refuses with clear error; happy path writes local state correctly; 4xx rolls back local state | T008,T009,T010 | RED | |
| T012 | GREEN + Review + Verify + Commit | T011 | GREEN→Land | |

---

## Slice P-PUB-IMAGES — Image Upload + Diff

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T013 | `product.image.x_image_sha256_cache` Char field + on-read compute + on-write clear hook | P-PUB-CLIENT ✓ | GREEN | mhc-side (product domain); ACL inherited |
| T014 | `etsy.listing.image_hash_manifest` Text JSON field; system-group ACL | P-PUB-CLIENT ✓ | GREEN | |
| T015 | Extend `EtsyListingPublisher` with `upload_images(product, listing_id, shop)` — diff new/changed/removed against manifest; upload changed (multipart); DELETE removed; update manifest | T008,T013,T014 | GREEN | TokenBucket(rate=2, burst=10) |
| T016 | RED Phase 2 (ORM): first-publish uploads all; second-publish with one image changed → 1 upload + 0 delete; image removed in Odoo → DELETE call; manifest persists across publishes; image upload 4xx writes error row but doesn't kill orchestrator | T013,T014,T015 | RED | Mock multipart `requests.Session.post` |
| T017 | GREEN + Review + Verify + Commit | T016 | GREEN→Land | |

---

## Slice P-PUB-INVENTORY — Entire-Array Resubmit (supersedes Spec 008 P-LIST-INV-PUSH)

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T018 | Extend `EtsyListingPublisher` with `push_inventory(product, listing_id, shop)` — builds `products[]` from `product.product` variants of the template; SKU per ADR-014 §4 | P-PUB-DRAFT ✓ | GREEN | Variant property_values built from `product.attribute.value` if present; empty otherwise |
| T019 | Standalone `EtsyInventoryPusher.push(product_tmpl, shop)` — thin alias that calls `EtsyListingPublisher.push_inventory` for callers without a listing_id (resolves from `product.channel.status.external_ref`) | T018 | GREEN | Entry point for Spec 009 P-HUB-SKU-DRIFT T024 hook |
| T020 | After successful PUT: update `etsy.listing.product` snapshot rows from response payload | T018 | GREEN | Keep mirror in sync |
| T021 | Mark Spec 008 P-LIST-INV-PUSH tracker row `superseded by P-PUB-INVENTORY` in this slice's commit | T018 | Land | Tracker hygiene |
| T022 | RED Phase 2 (ORM): full-array PUT (mocked); SKU policy branches; rate-limit retry; 4xx body capture; rollback on persistent failure; partial Etsy response → still trust Odoo-side `product.product` (Odoo canonical now); concurrent-publish lock test | T018,T019,T020 | RED | |
| T023 | GREEN + Review + Verify + Commit | T022 | GREEN→Land | |

---

## Slice P-PUB-PUBLISH — Wizard + Orchestrator + Resume + E2E

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T024 | `wizards/etsy_publish_wizard.py` — TransientModel + form view + `_check_ba_or_raise()` + `action_run_publish` / `action_run_inventory_only` | P-PUB-INVENTORY ✓ | GREEN | FR-017 method-top gate; pre-flight summary shows resolved SKU |
| T025 | Extend `EtsyListingPublisher` with `publish(product, listing_id, shop)` — `PATCH /listings/{id}` to `state='active'` | P-PUB-DRAFT ✓ | GREEN | |
| T026 | `EtsyListingPublisher.run(product, shop)` orchestrator — calls create_draft → upload_images → push_inventory → publish; resumable via `product.channel.status.state` + `external_ref`; per-step error capture; 404 on resume resets external_ref + asks operator (no auto-recreate) | T008,T015,T018,T025 | GREEN | State machine drawn in spec §US4 |
| T027 | `product.template` "Publish to Etsy" button on form — opens `etsy.publish.wizard`; label changes to "Resume Publish" when `product.channel.status.state='error'` | T024 | GREEN | Single entry point for operator |
| T028 | RED Phase 2 (ORM): full-flow orchestration with mocked client (4 steps); resume from `state='error'` skips completed steps; 404 on existing listing resets external_ref + raises operator error; FR-017 gate refuses non-BA; concurrent-publish lock via SELECT FOR UPDATE | T024,T025,T026,T027 | RED | |
| T029 | GREEN + Review + Verify + Commit | T028 | GREEN→Land | |
| T030 | `P-PUB-E2E` — live smoke on JaHandmadeArt sandbox: create a synthetic product in Odoo (Excel-imported or via Spec 009 wizard), run publish wizard, verify on Etsy that listing exists with images + variants + active; capture report at `docs/E2E_PUBLISH_RUN_<date>.md` (precedent P0-18b2 + 2026-05-12 demo) | T029, owner sign-off | E2E | Manual run; operator-supervised; not CI |

---

## Dependency Graph

```
Spec 009 P-HUB-PROD-MODEL (done)
    → P-PUB-CLIENT (T001–T007)
        → P-PUB-DRAFT (T008–T012)
            → P-PUB-IMAGES (T013–T017)
            → P-PUB-INVENTORY (T018–T023)
                → Spec 009 P-HUB-SKU-DRIFT T024 (Etsy push hook — unblocks when P-PUB-INVENTORY lands)
            → P-PUB-PUBLISH (T024–T030)
```

P-PUB-IMAGES and P-PUB-INVENTORY can land in parallel after P-PUB-DRAFT.
P-PUB-PUBLISH consolidates all three into the wizard.

## Notes

- All implementation slices: Two-Phase Testing; coverage ≥ 80 % on changed lines; module installs clean.
- UNIQUE constraints from existing models (`etsy.listing`, `etsy.listing.product`) are unchanged — no new mirrors needed.
- Wizards MUST guard `action_*` with method-top BA-group check (memory `feedback_fr017_write_defense_in_depth`).
- RED gate: orchestrator runs tests with `--http-port=8170`.
- 4xx body capture pattern: `with self.env.registry.cursor() as cr: ...; cr.commit()` for durable audit on rollback (memory `feedback_capture_response_body_before_blackbox_probe`).
- E2E smoke (T030) requires owner sign-off + a synthetic test product (don't publish a real catalog product as the first test).
- This spec marks Spec 008 P-LIST-INV-PUSH as **superseded** (T021); the planned `wizards/etsy_listing_push_wizard.py` is NOT built; its functional intent is split between `EtsyInventoryPusher.push` (service) and `etsy.publish.wizard` (UI).
