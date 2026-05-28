# Data Model: Etsy Outbound Publish (Spec 011)

- **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md) | **ADR**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md)

## Entity Overview

| Entity | Status | Module | Description |
|---|---|---|---|
| `etsy.api.log` | EXTENDED | `etsy_integration` | Selection `source` gains 5 outbound + 2 catalog values |
| `etsy.shop` | EXTENDED | `etsy_integration` | Per-shop Etsy publish defaults (taxonomy / shipping / return policy IDs) |
| `etsy.listing` | EXTENDED | `etsy_integration` | `image_hash_manifest` JSON for image-diff idempotency |
| `product.channel.status` | EXTENDED via state writes (Spec 009 owns the model) | `multichannel_hub_core` | Publisher writes `state` / `external_ref` / `last_sync_*` |
| `product.image` | EXTENDED (light) | `multichannel_hub_core` | Non-stored cache field `x_image_sha256_cache` (compute-on-read) |
| `etsy.publish.wizard` | NEW | `etsy_integration` | TransientModel for operator flow |

---

## 1. `etsy.api.log` `source` Selection extension

Existing values (Spec 005 P0-17): `order_pull`, `tracking_push`, `oauth_callback`, `health_ping`, `manual_diagnostic`, `audit`, `listing_pull`. Plus `listing_inventory_push` (was reserved by Spec 008 P-LIST-INV-PUSH — keep the same value name for backward compatibility).

Adds:

| Value | Used by |
|---|---|
| `listing_create` | Spec 011 P-PUB-DRAFT |
| `listing_image_upload` | Spec 011 P-PUB-IMAGES |
| `listing_image_delete` | Spec 011 P-PUB-IMAGES |
| `listing_publish` | Spec 011 P-PUB-PUBLISH (PATCH to active) |
| `catalog_import_run` | Spec 010 P-HUB-XLS-CRON (cron + wizard) |
| `catalog_image_download` | Spec 010 P-HUB-IMAGES (catalog image downloader) |

Total source values after extension: 14.

---

## 2. `etsy.shop` (EXTENDED)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `default_taxonomy_id` | Integer | No (until publish) | NULL | Etsy taxonomy ID for new listings; system-group ACL like OAuth tokens |
| `default_shipping_profile_id` | Integer | No (until publish) | NULL | Same |
| `default_return_policy_id` | Integer | No (until publish) | NULL | Same |
| `default_who_made` | Selection | Yes | `i_did` | `i_did` / `someone_else` / `collective` |
| `default_when_made` | Selection | Yes | `made_to_order` | Common Etsy values |
| `default_is_supply` | Boolean | Yes | False | Etsy "is supply" flag |

**ACL**: existing `etsy.shop` ACLs preserved; the three Integer defaults follow the OAuth-token system-group pattern.

**Behaviour**: `EtsyListingPublisher.create_draft` refuses to start when any of `default_taxonomy_id` / `default_shipping_profile_id` / `default_return_policy_id` is NULL. The wizard pre-flight surfaces this with a clear error and links to the shop form.

---

## 3. `etsy.listing` (EXTENDED)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `image_hash_manifest` | Text (JSON) | No | NULL | `{"<etsy_image_id>": "<sha256>", ...}`; written by P-PUB-IMAGES on each upload/delete; system-group |

**Rationale**: keeping the manifest on the listing (channel-side mirror) rather than on `product.template` (canonical hub) means a channel-specific concern stays in channel scope. Future Amazon publisher will have its own image-hash manifest on `amazon.listing`.

---

## 4. `product.image` (EXTENDED — light)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `x_image_sha256_cache` | Char (indexed) | No | NULL | SHA-256 of `image_1920` bytes; non-stored compute backed by an opportunistic persist on first read; cleared on `image_1920` write |

**Why on `product.image` and not on `product.template`?** Multi-image diff needs per-image hashes; one hash per template can't tell which image changed.

**Implementation hint**: ORM hook on `write` clears the cache; the next read recomputes. Storage is one Char column; cost is minimal.

---

## 5. `etsy.publish.wizard` (NEW TransientModel)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `product_tmpl_id` | Many2one(`product.template`) | Yes | from context | Source product |
| `shop_id` | Many2one(`etsy.shop`) | Yes | — | Target shop; domain = shops with `active_source='api'` AND has valid OAuth tokens |
| `mode` | Selection | Yes | `publish` | `publish` / `resume` / `inventory_only` |
| `pre_flight_summary` | Text | No (computed) | — | Human-readable summary of what will happen + warnings |
| `sku_to_publish` | Char | No (computed) | — | Either `x_sku_v2_suggested` or `default_code`, resolved per ADR-014 §4; visible in summary so operator can flip `ba_approved_legacy` before confirm |
| `mark_ba_approved_legacy` | Boolean | No | False | If ticked, set product's `x_sku_v2_status='ba_approved_legacy'` before publish so legacy SKU goes to Etsy |

**ACL**: write `multichannel_hub_core.group_ba_*` (BA roles); FR-017 method-top gate before any publisher invocation.

**Actions**:
- `action_run_publish` — orchestrates create→images→inventory→publish.
- `action_run_inventory_only` — calls `EtsyInventoryPusher.push` only (for the canonicalisation wizard re-entry).

---

## 6. Constraints & Indexes (additive only)

No new UNIQUE constraints. Existing C-LIST-001 on `etsy.listing` (UNIQUE shop_id, etsy_listing_id) covers the create path — `external_ref` collision is detected by Etsy itself (createDraftListing returns the new ID).

Indexes added:
- `etsy.api.log (source, create_date DESC)` — for the run report and audit retention scan (already exists from Spec 005, no change).
- `etsy.shop (active_source, id)` — already exists.

---

## 7. Rationale Notes

- **Per-shop publish defaults are minimal.** Etsy v3 `createDraftListing` requires taxonomy/shipping/return-policy IDs but allows nulls for `materials`, `tags`, `style` — those are optional in MVP; future enhancement can add them as per-product or per-shop defaults.
- **`who_made` / `when_made` / `is_supply` are per-shop defaults**, not per-product, because they almost never vary within a shop. Per-product override is a future enhancement if data shows variation.
- **No new state model for the publish process.** `product.channel.status.state` is sufficient: `draft` (Etsy ID exists, not yet active) / `published` (active on Etsy) / `archived` (no longer active) / `error` (last attempt failed; resume entry point). The transition graph is enforced by the publisher service, not by `@api.constrains`.
- **`image_hash_manifest` on `etsy.listing` is JSON Text, not a related model.** Image count per listing is ≤ 10 (Etsy limit); a third table would be over-engineering. JSON is queryable enough for the diff (`json_object_keys` on rare ops).
- **No webhook for Etsy listing edits (BA editing on Etsy UI breaks our manifest).** Out of scope; the drift report from Spec 008 P-LIST-INV-PULL already surfaces qty drift; a future enhancement can do title/description drift.
