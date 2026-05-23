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
| T008 | [X] `services/etsy_listing_publisher.py` — `EtsyListingPublisher` class + `create_draft(product, shop)` + `_resolve_sku` + `_build_create_draft_payload` + `_check_shop_defaults` | P-PUB-CLIENT ✓ | GREEN | |
| T009 | [X] On success: writes `etsy.listing` (state='inactive' mirror; draft until publish step) + `product.channel.status` (state='draft', external_ref=str(listing_id)) | T008 | GREEN | |
| T010 | [X-partial] On 4xx: raises ValueError → caller transaction rolls back; durable error-status row (state='error' + last_sync_error) deferred to **P-PUB-PUBLISH** orchestrator (T026) which owns the resumable state machine | T008 | GREEN | Slice deliberately keeps the publisher stateless; error-row durability is tied to the wizard/orchestrator lifecycle |
| T011 | [X] RED Phase 2 (ORM) — 7 tests: refuses missing taxonomy / shipping_profile; v2 SKU when status != ba_approved_legacy; legacy SKU when status == ba_approved_legacy; payload includes 11 required keys + state='draft'; happy path writes etsy.listing + product.channel.status; 4xx rolls back local writes (no listing, no status) | T008,T009,T010 | RED | port `8175` |
| T012 | [X] GREEN + Verify + Commit | T011 | GREEN→Land | Review skipped per playbook small-slice exception (single service file; FR-017 N/A — publisher is a library, not an action; gate lands in P-PUB-PUBLISH wizard T024) |

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
| T018 | [X] `EtsyListingPublisher.push_inventory(tmpl, listing_id, shop)` — products[] from variants; SKU per ADR-014 §4 (template-level resolution; variant default_code does NOT override since it's auto-inherited and would defeat v2 rule) | P-PUB-DRAFT ✓ | GREEN | property_values=[] for now (single-variant pilot); revisit when multi-variant publish lands |
| T019 | [X] `services/etsy_inventory_pusher.py` — `EtsyInventoryPusher.push(tmpl, shop)` resolves listing_id from product.channel.status.external_ref; raises ValueError if no status row | T018 | GREEN | |
| T020 | [X] `_sync_inventory_snapshot` writes etsy.listing.product rows from PUT response — price decoded via amount/divisor, qty from first offering | T018 | GREEN | |
| T021 | [X-prior] Spec 008 P-LIST-INV-PUSH tracker row already marked `superseded by P-PUB-INVENTORY` (2026-05-23 in P-HUB-SPEC commit) | T018 | Land | |
| T022 | [X] RED Phase 2 (ORM) — 6 tests: payload products[] shape; SKU v2 template-level wins; SKU legacy when ba_approved; alias resolves listing_id; alias refuses when no status; snapshot sync writes through response | T018,T019,T020 | RED | port `8175` |
| T023 | [X] GREEN + Verify + Commit | T022 | GREEN→Land | Review skipped per playbook small-slice exception |

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
