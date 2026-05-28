# ADR-013: Etsy Listing Model Architecture & Product Mapping Strategy

- **Status**: Accepted
- **Date**: 2026-05-16
- **Sign-off**: 2026-05-16 (owner, via Telegram — "go with architect recommendations")
- **Deciders**: Owner, architect
- **Affects**: Spec 008 (listings & inventory sync), future Spec 009/010 (catalog dashboard, Amazon channel)
- **Related**: [ADR-007 fulfillment delegation mixin](ADR-007-fulfillment-delegation-mixin.md) (standalone-model precedent), [ADR-003 module decomposition](ADR-003-module-decomposition.md) (which module owns the model), [ADR-005 carrier unification](ADR-005-carrier-unification.md) (one-time 1:N modelling), [Spec 005 research.md](../../005-etsy-api-channel/research.md) (incremental-sync pattern reused by P-LIST-PULL)

> **Numbering note**: the Master Plan 006 tracker row for P-LIST-SPEC referenced "ADR-012" for this decision. ADR-012 was already taken by `ADR-012-gdrive-failover.md`. This decision is therefore recorded as **ADR-013**. The tracker text is stale only on the number; the design intent it points to is captured here.

## Context

Etsy API v3 surfaces a shop's catalog through two read endpoints (both covered by the E1-approved `listings_r` scope, approved 2026-05-12):

- `GET /v3/application/shops/{shop_id}/listings` — listing metadata (title, state, url, price, timestamps)
- `GET /v3/application/listings/{listing_id}/inventory` — the per-listing **variant matrix** (`products[]`: each with `product_id`, `sku`, `property_values`, `quantity`, `price`)

The eventual write path (`PUT /v3/application/listings/{listing_id}/inventory`, `listings_w`) has a hard constraint: **the entire `products[]` array must be re-submitted on every write**. A partial array means "delete the variants not included." This forces a read-before-write discipline and makes a queryable, timestamped snapshot of the variant matrix a hard requirement, not a convenience.

Three structural facts shape the model decision:

1. **An Etsy listing is not an Odoo product.** A listing has 1+ variants; an Odoo `product.template` has N `product.product` variants; only `product.product` carries inventory. The relationship between an Etsy listing and the Odoo catalog is N:1-ish and frequently *absent* (a listing may have no Odoo counterpart yet; an Odoo product may not be on Etsy yet).
2. **Drift detection is the near-term goal.** Phase 1 (P-LIST-PULL) is read-only metadata ingest; Phase 2 (P-LIST-INV-PULL) snapshots variants and detects drift vs. the Odoo catalog; Phase 3 (P-LIST-INV-PUSH) is the deferred writeback. Nothing in Phases 1–2 requires a listing to *be* a product.
3. **Multi-channel is on the roadmap.** A future Amazon channel (Spec 010) will need the same shape. Channel identity must not be welded onto `product.template`.

Two decisions must be made now so the Spec 008 data model is stable: (1) how `etsy.listing` is modelled, and (2) how a listing variant maps to an Odoo product.

## Decision

### 1. `etsy.listing` is a standalone Model — NOT `_inherits('product.template')`

`etsy.listing` is defined with its own `_name = 'etsy.listing'`, a plain Many2one FK to `etsy.shop`, and **no delegation inheritance** to `product.template`. Its variant matrix is a One2many child model `etsy.listing.product`.

Rationale:

- **Channel identity ≠ product identity.** An Etsy listing has a channel-specific lifecycle (`active`/`inactive`/`suspended`/`deleted`), Etsy-scoped IDs, and Etsy timestamps. Forcing it into `product.template` via `_inherits` would create an orphan product for every listing that has no Odoo counterpart, and would not survive the multi-channel future (an Amazon listing would need a parallel inheritance path or duplicated rows).
- **The N:1 mismatch.** `_inherits` models a 1:1 sibling. Etsy listing → Odoo is not 1:1; it is "1+ variants, sometimes matched to product.product, sometimes not." A standalone model with an explicit, *optional* link expresses this honestly; a delegation sibling would force a link that often does not exist.
- **Precedent (ADR-007).** ADR-007 chose `_inherits` for `sale.order.fulfillment` precisely because fulfillment **is a 1:1 facet of every order that must exist**. The opposite is true here: an Etsy listing is an independent channel entity that *may* relate to a product. The two ADRs reach opposite conclusions from the same decision framework — and that is the correct, intentional outcome.
- **Read-only-first and testability.** Drift reports query `etsy.listing` / `etsy.listing.product` directly with no JOIN to `product.template`. Listing tests run without loading the product catalog.

### 2. Listing↔product mapping: FK on `product.product` + SKU-based fallback (dual-index)

Two parallel join mechanisms:

1. **Primary (explicit link):** a Many2one on the variant snapshot, `product.product.etsy_listing_variant_id` → `etsy.listing.product` (`ondelete='set null'`). Populated by SKU matching in P-LIST-INV-PULL, or by a manual wizard in a later phase.
2. **Secondary (discovery):** at ingest time, P-LIST-INV-PULL searches `product.product` by `(company_id, default_code == variant.sku)` to auto-populate the FK and to surface *unlinked* variants as drift.

Rationale:

- **Serves the entire-array-resubmit constraint.** P-LIST-INV-PUSH (Phase 3) reconstructs the full `products[]` array from `etsy.listing.product` rows. With the FK, the pusher reads authoritative qty/price from the linked `product.product`; with no FK it falls back to the stored snapshot — no extra Etsy GET round-trip per unlinked variant.
- **SKU is the natural loose coupling.** Etsy best practice is SKU ≡ variant within a shop; Odoo's `product.product.default_code` is the SKU. SKU matching makes drift detection work for variants that have *not* been explicitly linked — which is the entire point of P-LIST-INV-PULL.
- **Multi-channel safe.** The FK is the per-variant preferred link; SKU discovery scales if one product is later listed on multiple channels.

### Owner-confirmed open questions (2026-05-16, "go with architect recommendations")

| # | Question | Decision |
|---|---|---|
| a | Etsy variant SKU with no matching Odoo product | **Leave unlinked + flag in drift report.** Do NOT auto-create `product.product` (would pollute the catalog). Manual linking via a follow-up wizard. |
| b | Listing deactivation from the Odoo UI | **Defer.** Spec 008 is read-only ingest + drift. Deactivation is a later phase. |
| c | Multi-variant Etsy listing vs. a single non-variant Odoo product | **Link the closest SKU match only** (the variant whose SKU equals the product `default_code`); others stay unlinked and surface as drift. |

## Consequences

### Positive

- `etsy.listing` is reusable as a template for `amazon.listing` / `website.listing` with zero coupling to `product.template`.
- Drift reports are plain indexed ORM queries; no delegation join overhead.
- Phase 1/2 ship without any product-catalog migration.
- Phase 3 writeback has a local source of truth for the full variant array (no per-variant Etsy GET).

### Negative

- A new `product.product` field (`etsy_listing_variant_id`) is added DB-wide (cheap nullable FK; mirrors the ADR-007 cost-of-foundation reasoning, but far smaller — single FK, no auto-created sibling).
- SKU-collision risk if a shop has duplicate `default_code` values (bad data hygiene). Mitigated by logging a warning per collision and documenting the SKU-uniqueness expectation in `data-model.md`.
- Snapshot rows accumulate (soft-delete, not hard unlink) — bounded by listing count × variant count; revisit retention if a shop exceeds ~5k variants.

### Neutral

- Standalone channel-entity models joined to the catalog by an optional FK is a conventional Odoo connector pattern (cf. `delivery.carrier` ↔ `product.product`), not experimental.

## Alternatives considered

1. **`etsy.listing` via `_inherits('product.template')`** — rejected. Forces orphan products for unmatched listings; breaks the multi-channel future; models a 1:1 relationship that does not exist.
2. **SKU-only matching, no FK** — rejected. Per-variant SKU search on every Phase-3 push is O(N) and ambiguous under multi-channel duplicate SKUs.
3. **FK-only, no SKU discovery** — rejected. Unlinked variants would never surface; defeats the purpose of P-LIST-INV-PULL drift detection.
4. **Join at `product.template.default_code`** — rejected. Loses variant-level granularity (template SKU is a grouping, not a variant SKU).
5. **Store the variant matrix as a JSON blob on `product.product`** — rejected. Unindexable for drift queries, un-auditable, error-prone to mutate.

## Implementation notes

- Models live in the Etsy channel module per [ADR-003](ADR-003-module-decomposition.md) (`etsy_channel_api`; until module decomposition lands, `etsy_integration`).
- `etsy.listing` and `etsy.listing.product` use soft deletes (`is_active=False`) — never hard `unlink()` — to preserve the drift/audit trail.
- `etsy.api.log` already carries `listing_pull` / `listing_push` in its `source` Selection (`custom_addons/etsy_integration/models/etsy_api_log.py`); no schema change needed for audit.
- Reuse the Spec 005 incremental-sync pattern (pagination + `min_last_modified`) for P-LIST-PULL.
- ACLs: read `base.group_user`, write `base.group_system` (cron only) on both new models; no change to existing `product.product` ACLs for the added FK.
- Two-Phase Testing applies to the implementation slices (P-LIST-PULL, P-LIST-INV-PULL), not to this planning ADR.
- Escape hatch if reversed later: drop `etsy.listing*` tables + the `product.product.etsy_listing_variant_id` column; no cross-table data copy required (snapshots are derived, not authoritative).
