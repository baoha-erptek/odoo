# Implementation Plan: Etsy Outbound Publish (Spec 011)

- **Branch**: `feature/006-master-plan-coding` | **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md)
- **Authority**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md); ADR-008 (API-first); [ADR-013](../006-master-plan/adrs/ADR-013-etsy-listing-architecture.md)

## Summary

Five implementation slices in `etsy_integration`:

| Slice | Delivers |
|---|---|
| **P-PUB-CLIENT** | `EtsyApiClient.post()` / `.put()` / `.patch()` / `.post_multipart()` + new `etsy.api.log` `source` values + per-shop Etsy default IDs (taxonomy / shipping profile / return policy) on `etsy.shop` |
| **P-PUB-DRAFT** | `EtsyListingPublisher.create_draft(product, shop)` — `POST /shops/{id}/listings`; writes `etsy.listing.state='draft'`; SKU resolution per ADR-014 §4 |
| **P-PUB-IMAGES** | Image upload + content-hash idempotency + image diff (re-upload / DELETE) |
| **P-PUB-INVENTORY** | Entire-array-resubmit `PUT` — also exposed as `EtsyInventoryPusher.push()` for the SKU canonicalisation wizard hook (Spec 009 T024) |
| **P-PUB-PUBLISH** | `PATCH /listings/{id}` to active + `etsy.publish.wizard` operator UI + resumable-failure state machine + `P-PUB-E2E` jahandmadeart smoke test |

## Technical Context

- Module: `etsy_integration`.
- Reuses: `EtsyApiClient` (Spec 005 P0-15); `TokenBucket` rate limiter; `etsy.api.log` (Spec 005 P0-17, audit-source extension here); `etsy.listing` + `etsy.listing.product` (Spec 008); `product.channel.status` (Spec 009 P-HUB-PROD-MODEL); PII scrub helper from `gearment_adapter` (P0-18b1) pattern.
- Etsy v3 base URL: already configured via `etsy.api.base_url` ICP and per-shop OAuth token.
- Coordinates with: Spec 009 P-HUB-SKU-DRIFT (canonicalisation wizard calls `EtsyInventoryPusher.push` via the `_push_sku_to_channel` extension point); Spec 010 audit-source coordination.

## Design Decisions

1. **One concrete publisher service, not an abstract base.** YAGNI per behavioral-guardrails: no second channel exists today. Amazon publisher (when it lands) will reveal whether `EtsyListingPublisher` and `AmazonListingPublisher` share enough shape to factor out.
2. **State machine lives in `product.channel.status`, not in a new model.** `state ∈ {draft, published, archived, error}` is sufficient; `external_ref` carries the listing_id; `last_sync_error` captures the last failure for resume.
3. **Resumable, not transactional.** Etsy provides no transaction across the 4-step flow. The publisher records progress on `product.channel.status` after each successful step; a resume reads the last successful step and skips to the next.
4. **Image content hash on `product.image`** — adds a non-stored `x_image_sha256_cache` Char field (computed from `image_1920` bytes on read; persisted opportunistically on first publish). Drives the diff logic. Avoids re-uploading images on every publish.
5. **Per-shop Etsy defaults are stored on `etsy.shop`** as `default_taxonomy_id` (Integer), `default_shipping_profile_id` (Integer), `default_return_policy_id` (Integer). All system-group ACL like the OAuth fields. The publisher refuses to start if any are NULL.
6. **No bulk publish in MVP.** Per-product wizard only. Bulk slice `P-PUB-BULK` deferred until ≥3 shops have been through manual publish flow and the operator workflow is settled.
7. **SKU resolution at publish time** (ADR-014 §4): `x_sku_v2_suggested` when non-empty AND `x_sku_v2_status != 'ba_approved_legacy'`, else `default_code`.

## Implementation Phases

### Slice P-PUB-CLIENT — API Client Write Methods + Shop Defaults (~1–2 weeks)

Deliverables:
- Extend `services/etsy_api_client.py` with `post()`, `put()`, `patch()`, `post_multipart()` — same rate-limit + 401 refresh + audit-log discipline as `get()`.
- New `etsy.api.log` `source` Selection values: `listing_create`, `listing_image_upload`, `listing_image_delete`, `listing_inventory_push`, `listing_publish`.
- Audit-source coordination with Spec 010: also add `catalog_import_run`, `catalog_image_download` in the same Selection extension (avoids two migrations).
- `etsy.shop` extensions: `default_taxonomy_id` / `default_shipping_profile_id` / `default_return_policy_id` (Integer, group_system, indexed). Migration: defaults NULL — operator must set per shop before first publish.
- Two-Phase tests: each method writes correct headers + retries 429 + captures 4xx body durably; multipart body encoded correctly with mocked HTTP; defaults required before publish path is exercisable.

### Slice P-PUB-DRAFT — createDraftListing (~1–2 weeks)

Deliverables:
- `services/etsy_listing_publisher.py` — `EtsyListingPublisher` with `create_draft(product, shop)`.
- Builds payload: `quantity` (sum of variants or 1), `title`, `description` (`product.template.description_sale` or fallback to `name`), `price` (`x_listing_price` per ADR-014 §2), `who_made` (default `i_did`), `when_made` (default `made_to_order`), `taxonomy_id` (from shop default), `shipping_profile_id` (from shop default), `return_policy_id` (from shop default), `state='draft'`, `sku` per ADR-014 §4.
- On success: write `etsy.listing` row + `product.channel.status` row with `external_ref=listing_id`, `state='draft'`.
- Two-Phase tests: payload structure; SKU policy branches (v2-canonical vs legacy vs ba_approved_legacy); writes correct local state on success; rolls back local state on 4xx.

### Slice P-PUB-IMAGES — Image Upload + Diff (~1–2 weeks)

Deliverables:
- Extends `EtsyListingPublisher` with `upload_images(product, listing_id, shop)`.
- Reads `product.image` One2many + `image_1920` as primary; computes/caches `x_image_sha256_cache`.
- Compare against last-known hashes (stored on `etsy.listing` JSON `image_hash_manifest` field — new field, Text JSON, system-group).
- Upload new images via `post_multipart` to `POST /shops/{id}/listings/{lid}/images` with rank.
- DELETE removed images.
- Token bucket throttle (`TokenBucket(rate=2, burst=10)`) to avoid burst.
- Two-Phase tests: first-publish uploads all; second-publish with one image changed → 1 upload + 0 delete; image removed in Odoo → DELETE call; manifest persists across publishes.

### Slice P-PUB-INVENTORY — Entire-Array Resubmit (~1 week — supersedes Spec 008 P-LIST-INV-PUSH)

Deliverables:
- Extends `EtsyListingPublisher` with `push_inventory(product, listing_id, shop)`.
- Also exposed as standalone `EtsyInventoryPusher.push(product_tmpl, shop)` — same service, alternate entry point for canonicalisation (Spec 009 T024).
- Builds `products[]` array from current `product.product` variants tied to the template's `product.template`; resolves SKU per ADR-014 §4.
- PUT call; captures 4xx body durably (`feedback_capture_response_body_before_blackbox_probe`).
- Updates `etsy.listing.product` snapshot rows from the response.
- **This slice closes the deferred Spec 008 P-LIST-INV-PUSH.** Tracker P-LIST-INV-PUSH row is marked `superseded by P-PUB-INVENTORY`.
- Two-Phase tests: full-array round-trip; partial response triggers no row-delete in Odoo (Odoo is canonical now); rate-limit retry; 4xx body capture; rollback on failure.

### Slice P-PUB-PUBLISH — PATCH Publish + Wizard + E2E (~2 weeks)

Deliverables:
- `wizards/etsy_publish_wizard.py` — TransientModel + form view + FR-017 BA-group gate.
- Resumable state machine: reads `product.channel.status.state` + `external_ref` to decide entry step.
- `EtsyListingPublisher.publish(product, listing_id, shop)` — `PATCH /listings/{id}` with `state='active'`.
- Orchestrator `EtsyListingPublisher.run(product, shop)` calls create_draft → upload_images → push_inventory → publish in sequence with per-step error capture.
- E2E smoke (`P-PUB-E2E`): on JaHandmadeArt pilot, create a synthetic test product, run the wizard, verify on Etsy that the listing exists with images + variants + active state; capture a run report at `docs/E2E_PUBLISH_RUN_<date>.md` (precedent: P0-18b2 demo run + 2026-05-12 demo).
- Two-Phase tests: full-flow orchestration with mocked client; resume from `state='error'` skips completed steps; 404 on existing listing resets external_ref + asks operator; FR-017 gate refuses non-BA.

## Testing Strategy (Two-Phase)

- **Phase 1 (DB)**: `etsy.api.log.source` Selection values, `etsy.shop` new fields, `etsy.listing.image_hash_manifest`, view + wizard structure.
- **Phase 2 (ORM)**: per-method client tests with mocked `requests`; per-step publisher tests; full-flow orchestration; FR-017 gates; resumability; 4xx body durability (Defect-05 pattern).
- Mock at `requests.Session.{post,put,patch}` level; never hit real Etsy in CI.
- E2E smoke is live against JaHandmadeArt sandbox listing (not CI; manual run with operator sign-off).
- Run with `--http-port=8170`; register all test files in `tests/__init__.py`.
- Coverage ≥ 80 % on changed lines.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-011-1 | createDraftListing requires fields we haven't anticipated (e.g. `materials[]`, `tags[]`) | High | High | Per-shop defaults on `etsy.shop` (taxonomy / shipping profile / return policy); capture-response-body precedent on first 4xx; expand mandatory shop config based on actual Etsy responses |
| R-011-2 | Image upload 4xx without clear body | Med | Med | `post_multipart` captures `r.text[:2000]`; durable audit row; manual operator triage from `etsy.api.log` |
| R-011-3 | Mid-flow failure leaves orphan draft on Etsy | Med | Med | Resume logic skips create-draft when external_ref is set; operator can archive an orphan via Etsy UI; no auto-cleanup (avoid double-archive on retry) |
| R-011-4 | Token expiry during 4-step flow | Low | Low | `EtsyApiClient` already refreshes proactively + retries on 401 (P0-15) |
| R-011-5 | Inventory push race with concurrent order (qty changes during the PUT round-trip) | Low | Med | Entire-array-resubmit is one transaction at Etsy's side; if a buyer adds-to-cart between our PUT and their queue read, Etsy resolves at their side; we accept eventual consistency |
| R-011-6 | Etsy rate limit hit mid-publish | Med | Med | TokenBucket + Retry-After + 1/2/4 backoff already wired in P0-15; per-step retries up to 3; on persistent 429 the orchestrator stops and writes `state='error'` so resume kicks in |
| R-011-7 | SKU resolution chooses canonical when BA actually wanted legacy on this product | Low | Med | The `ba_approved_legacy` status (Spec 009 §4) is the operator escape hatch; publish wizard pre-flight summary shows which SKU will be written and lets operator inline-flip to `ba_approved_legacy` before publish |
| R-011-8 | `EtsyInventoryPusher.push` called from canonicalisation wizard while another publish is in flight for same product | Low | Low | `product.channel.status` SELECT FOR UPDATE during publisher entry; second caller waits/aborts cleanly |

## Exit Criteria — P-HUB-SPEC (planning) cross-references

This spec's exit criteria are tracked under Spec 009 P-HUB-SPEC since they're all-or-nothing on the planning slice. Per-slice exits in tasks.md.

## Cross-References

- ADR-014 (this spec implements the §3 Odoo→Etsy direction)
- ADR-013 (channel mirror surface — this spec writes back into it)
- ADR-008 (API-first pivot — this spec is the first outbound write under it)
- Spec 008 plan.md (deferred Slice 3 P-LIST-INV-PUSH is superseded here)
- Spec 009 plan.md (provides `product.channel.status`; consumes our `_push_sku_to_channel` hook for canonicalisation)
- Spec 010 plan.md (audit-source extensions coordinated here)
- Memory `feedback_capture_response_body_before_blackbox_probe` (durable audit pattern)
- Memory `feedback_fr017_write_defense_in_depth` (wizard gates)
- Memory `reference_etsy_api_credentials` (auth + base URL)
- Memory `reference_etsy_shop_id_mapping` (`etsy_api_shop_id` field for URL construction; per P1-11-WIRE-LIVE)
