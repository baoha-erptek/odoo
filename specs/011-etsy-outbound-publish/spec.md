# Feature Specification: Etsy Outbound Publish (Spec 011)

- **Feature Branch**: work lands on `feature/006-master-plan-coding` (Master Plan 006 Phase 3)
- **Created**: 2026-05-23
- **Status**: PLANNED — planning slice (P-HUB-SPEC) authoring; implementation slices `todo`. **Supersedes deferred Spec 008 Slice 3 P-LIST-INV-PUSH** — inventory writeback becomes one task inside the publish state machine.
- **Authority**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md) §3 (Odoo→Etsy direction rules); ADR-008 (API-first pivot); [ADR-013](../006-master-plan/adrs/ADR-013-etsy-listing-architecture.md) (channel mirror surface)
- **Input**: MP006 tracker Phase 3 (new); plan file `.claude/plans/actually-need-to-check-polymorphic-crayon.md`; Etsy tutorial https://developer.etsy.com/documentation/tutorials/listings/

## Overview

First outbound `listings_w` usage. Walk an Odoo `product.template` through Etsy's create→images→inventory→publish flow:

1. `POST /v3/application/shops/{shop_id}/listings` (createDraftListing) → `etsy.listing` row with `state='draft'`
2. `POST /v3/application/shops/{shop_id}/listings/{listing_id}/images` (uploadListingImage) per `product.image`
3. `PUT /v3/application/listings/{listing_id}/inventory` (entire-array-resubmit) — builds variant matrix from Odoo `product.product` set
4. `PATCH /v3/application/listings/{listing_id}` to set `state='active'` (publish)

Plus a separate inventory-only PUT path for the canonicalisation wizard (Spec 009 P-HUB-SKU-DRIFT) and for ongoing qty pushes.

**This spec depends on Spec 009 P-HUB-PROD-MODEL landing** (channel applicability + product.channel.status) and writes back into those models.

Out of scope:
- Amazon publisher (future MP / Phase 5)
- Bulk-publish wizard (operator-driven, per-product publish is the MVP; bulk-publish slice raised as `P-PUB-BULK` deferred)
- Listing delete (`DELETE /listings/{id}`) — deferred per ADR-013 owner Q-b
- Edit-after-publish (mutate title/description on an active listing) — out of scope; canonicalisation wizard is the only inventory mutation path in this spec

## User Scenarios & Acceptance Criteria

### US1 — Operator Publishes a Product to Etsy (P1)

As a BA, I want to click "Publish to Etsy" on a product and see it appear on the shop, with all variants + images + inventory in place.

**Acceptance Criteria**
1. Given a `product.template` with `etsy` in `x_channel_applicability_ids`, a valid `default_code` (or `x_sku_v2_suggested` when applicable per ADR-014 §4), category, prices, and ≥1 image, When operator clicks the "Publish to Etsy" button, Then `etsy.publish.wizard` opens with target shop picker + pre-flight summary.
2. The wizard's pre-flight validates required Etsy fields exist on `etsy.shop` (`default_taxonomy_id`, `default_shipping_profile_id`, `default_return_policy_id`); missing values block publish with a clear error.
3. On confirm, the publisher service: (a) creates the draft listing, (b) uploads each `product.image` as a listing image with ordered rank, (c) PUTs the variant inventory matrix, (d) patches `state='active'`.
4. On success: `product.channel.status` for (this product, Etsy channel) reaches `state='published'` with `external_ref = listing_id`; `etsy.listing` exists with the listing_id and `state='active'`; `etsy.listing.product` rows exist for each variant; `etsy.api.log` rows exist for each of the 4+ API calls.
5. On failure at any step: rollback to the prior state (no orphan draft listings on Etsy when possible — Etsy provides no transaction; we record the partial state in `product.channel.status.state='error'` + `last_sync_error` for operator action).
6. Operator may re-run the wizard on a `state='error'` product; the publisher detects the existing draft (via `product.channel.status.external_ref`) and resumes from the failed step.

### US2 — Inventory Update on an Existing Listing (P1)

As a BA or as the canonicalisation wizard (Spec 009 P-HUB-SKU-DRIFT), I want to push inventory changes (qty + SKU + property values + price) to an existing Etsy listing.

**Acceptance Criteria**
1. Service `EtsyInventoryPusher.push(product_tmpl, shop)` builds the entire `products[]` array from current Odoo state (`product.product.qty_available` for qty, `product.product.default_code` for sku, listing-level `price` for price).
2. PUT call sends the full array; partial arrays would delete variants per Etsy contract (ADR-013).
3. On 429 / rate limit, retries with `Retry-After` honored (existing `TokenBucket` + 1/2/4 backoff pattern from `EtsyApiClient`).
4. On 4xx other than 429, captures vendor body in raised `ValueError` + warn-log per memory `feedback_capture_response_body_before_blackbox_probe`.
5. `etsy.api.log` row with `source='listing_inventory_push'`.
6. **This supersedes Spec 008 Slice 3 P-LIST-INV-PUSH.** That slice's planned wizard (`wizards/etsy_listing_push_wizard.py`) is replaced by this service-level push + the canonicalisation wizard (Spec 009) + the publish wizard (US1) as the two operator entry points.

### US3 — Image Re-Upload on Edit (P2)

As a BA, I want to re-upload product images when I update the Odoo product.

**Acceptance Criteria**
1. The publisher service tracks image content hashes (SHA-256) per `product.image`.
2. On a re-publish or re-sync, only images whose hash changed are re-uploaded.
3. New images go to the next available rank; deleted images get a DELETE call (`DELETE /shops/{id}/listings/{lid}/images/{iid}`).
4. Image diff is reported in the run audit + `product.channel.status.last_sync_at`.

### US4 — Resumable Failures (P1)

As an operator, I want to retry a failed publish without manual cleanup on Etsy.

**Acceptance Criteria**
1. When `product.channel.status.state='error'`, the wizard "Publish to Etsy" button label becomes "Resume Publish".
2. Publisher reads `product.channel.status.external_ref` (set after step 1 succeeds) and skips already-completed steps.
3. Steps are idempotent where Etsy allows; createDraftListing is NOT idempotent — so the publisher only creates a draft when `external_ref` is empty.
4. If Etsy says the listing is gone (404 on subsequent steps), publisher resets `external_ref` and asks operator whether to retry from scratch (no auto-recreate — avoids orphan-publish on bizarre states).

### US5 — Audit Trail (P1)

As an admin, I want full traceability of every outbound Etsy write.

**Acceptance Criteria**
1. Every API call writes an `etsy.api.log` row with new `source` values: `listing_create`, `listing_image_upload`, `listing_inventory_push`, `listing_publish`, `listing_image_delete`.
2. Per memory `feedback_capture_response_body_before_blackbox_probe`: 4xx response bodies are captured (truncated 4 KB) and persist via the durable-cursor pattern when the outer transaction may roll back.
3. PII scrubbing on payloads: stripped before audit-log write (mirror P0-18b1 helper).

## Channel Scope

Etsy only. The publisher service is purpose-built; future Amazon / website publishers are separate services with their own ADRs. No abstract "channel publisher" base class is introduced in this spec — the Etsy publisher is concrete first, abstracted later only if a second channel reveals shared shape (avoid premature abstraction per behavioral-guardrails §2).

## Dependencies

- ADR-014 accepted.
- Spec 009 P-HUB-PROD-MODEL landed (`x_channel_applicability_ids`, `product.channel.status`).
- Spec 008 P-LIST-PULL + P-LIST-INV-PULL landed (`etsy.listing`, `etsy.listing.product`, `EtsyApiClient.get()`).
- E1 scope grant `listings_w` ✓ approved 2026-05-12.
- Each shop has been configured with `default_taxonomy_id`, `default_shipping_profile_id`, `default_return_policy_id` (new fields added by this spec; one-time per-shop setup before first publish).

## Non-Functional Requirements

- Per-publish call sequence completes within 60 s for a product with ≤ 10 images and ≤ 50 variants (Etsy rate limit honored).
- 4xx capture: vendor body persists via `with self.env.registry.cursor() as cr: ...; cr.commit()` (memory `feedback_capture_response_body_before_blackbox_probe` durable-audit pattern).
- Idempotency: re-running a successful publish is a no-op (no spurious extra API calls).
- Audit retention: `etsy.api.log` rows for outbound writes retain ≥ 90 days (default retention is 30 — extend via ICP override for `_cron_purge_etsy_api_log`).
