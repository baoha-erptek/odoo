# ADR-014: Odoo as the Central Product Hub & Multi-Channel Publish Architecture

- **Status**: Accepted
- **Date**: 2026-05-23
- **Sign-off**: 2026-05-23 (owner, in-session — answered 4 scoping questions + 2 SKU-policy questions)
- **Deciders**: Owner, architect (Opus)
- **Affects**: Spec 009 (product hub foundation), Spec 010 (catalog Excel recurring sync), Spec 011 (Etsy outbound publish), Master Plan 006 §4 (final-target amendment + new Phase 3)
- **Related**: [ADR-008](ADR-008-api-first-pivot.md) (API-first pivot, current MP006 final target), [ADR-010](ADR-010-configurable-order-pipeline.md) (hybrid dropship + MTO pipeline), [ADR-013](ADR-013-etsy-listing-architecture.md) (Etsy listing standalone model; this ADR builds on its read-side mirror), [ADR-007](ADR-007-fulfillment-delegation-mixin.md) (delegation precedent — this ADR follows the same "facet of a 1:1" decision framework but reaches the opposite conclusion for channel-applicability), [ADR-003](ADR-003-module-decomposition.md) (module ownership — channel-agnostic groups + product model live in `multichannel_hub_core`)

## Context

Master Plan 006 has ridden a strict **inbound-and-fulfill** posture since ADR-008 (2026-04-13): Etsy → Odoo → Gearment, with `etsy.listing` as a read-only mirror (ADR-013). All product authoring happens **outside** Odoo today — BA edits `.0temp/raw/[2025] Product Catalog.xlsx` (109 MB, 7 sheets: Accessories / Pet / Apparel / Drinkware / Home Decor / Combo / Other costs) and publishes new listings directly on Etsy via Etsy's own web UI. Odoo never knows about a product until an order arrives. JaHandmadeArt (live pilot, 2026-05-22) is at this state: 1 listing + 5 variants ingested, but no upstream Odoo `product.template`.

Owner directive 2026-05-23 inverts the posture:

1. **Odoo becomes the system of record for the multichannel catalog.** Channels (Etsy now; Amazon + ecommerce later) subscribe; they do not own.
2. **The product-creation workflow must validate**: SKU (against the v2 grammar already frozen in `.0temp/deliverables/A3_grammar_v2_frozen.md`), category, listing/shipping/additional costs, and production mode (MTO vs Dropship — `x_gearment_sku`-driven, ADR-010).
3. **Excel stays canonical for now** (owner answer 2/4): BA workflow doesn't move into Odoo overnight. Excel is the operator entry surface; Odoo is the system of record that talks to channels. A recurring import bridges the two until BA is ready to author in Odoo's UI.
4. **Existing live Etsy listings get a non-destructive backfill** (owner answer 3/4): pull `etsy.listing` / `etsy.listing.product` rows → match-or-create `product.template` → cross-link. No re-publish, no archive, no edits pushed back without explicit BA action.
5. **First write-out channel = Etsy.** Amazon + ecommerce are explicitly later; the architecture must not bake Etsy assumptions into shared infrastructure.

Three structural questions must be resolved before Spec 009/010/011 can be drafted: (1) **how is "channel applicability" modelled** on a product, (2) **where does pricing live per channel**, and (3) **what is the source-of-truth/sync-direction contract** so Excel↔Odoo↔Etsy doesn't develop silent split-brain. The owner-confirmed SKU-drift policy from the planning session (2026-05-23) is a fourth structural item that crosses all three specs and is pinned here so each spec inherits it without re-deciding.

## Decision

### 1. Channel applicability is a Many2many on `product.template`, not a channel-typed model

`product.template` gains a Many2many to a new reference model `multichannel.sales.channel` (channel-agnostic, lives in `multichannel_hub_core` per ADR-003 + memory `feedback_channel_agnostic_groups_in_mhc`). Each channel record carries a `code` (`etsy` / `amazon` / `website`), `name`, and an `active` flag. **No** `_inherits` to `product.template`; **no** per-channel listing model overlaid on the product (that's `etsy.listing`'s job — the channel-side mirror).

Field shape on `product.template`:

| Field | Type | Purpose |
|---|---|---|
| `x_channel_applicability_ids` | Many2many(`multichannel.sales.channel`) | Which channels this product is publishable to. Empty = internal-only. |
| `x_sales_channel_status_ids` | One2many(`product.channel.status`) | Per-channel publish state (draft / published / archived) + back-ref to channel mirror row (e.g. `etsy.listing`). One row per (product, channel) once the product is on that channel. |

Rationale:

- **M2M ≠ inheritance.** A product can be on multiple channels with channel-specific state (`x_sales_channel_status_ids`), but the product itself is one record. Modelling channel as a typed inheritance hierarchy (an `etsy.product` separate from `amazon.product`) duplicates the catalog and breaks the central-hub charter on day one.
- **Symmetric to ADR-013 §1's standalone-model choice.** ADR-013 chose `etsy.listing` as a standalone Model (not `_inherits('product.template')`) precisely because the listing is a **channel-side mirror** of an underlying truth. ADR-014 confirms the underlying truth: `product.template` is canonical; channel mirrors are derived. The two ADRs are mutually consistent — channel-side: standalone; product-side: channel is a tag, not an inheritance.
- **Survives multi-channel growth.** Adding Amazon = inserting one `multichannel.sales.channel` row + adding the channel-specific publisher service. Zero `product.template` schema change.
- **The status One2many is small but load-bearing.** It tells the publisher "is this product already on Etsy for this shop?" without scanning `etsy.listing` for a SKU match every time. It also carries the channel-side foreign key (e.g. `etsy_listing_id`) so a future archive/re-publish action knows where to point.

### 2. Pricing: per-channel `product.pricelist` first; `x_listing_price` / `x_shipping_price_internal` / `x_additional_cost` on `product.template` only for catalog-import bookkeeping

`product.template` adds three Float fields:

| Field | Source | Meaning |
|---|---|---|
| `x_listing_price` | Excel "Price (USD)" column | Suggested listing price in shop currency — the BA's reference number, NOT the canonical sell price |
| `x_shipping_price_internal` | Excel "Shipping Fees" column | Internal cost to ship one unit (for margin calc); not the channel-charged shipping |
| `x_additional_cost` | Excel category "Other costs" sheet | Per-product additional cost (e.g. material cost beyond standard `standard_price`) |

For **per-channel selling price** (USD on Etsy, EUR on a future EU channel, etc.), the system uses **standard Odoo `product.pricelist`** keyed by channel + currency. The Excel multi-currency columns (USD / EU / CAD / VND) seed a default per-currency pricelist on first import; subsequent edits go through the pricelist mechanism, not the catalog import. The three new `product.template` fields are bookkeeping for the Excel round-trip and import audit; they are **not** read by the Etsy publisher or by any sale-order pricing logic. `product.pricelist` remains authoritative for the "what price is charged" question.

Rationale:

- **Reuse over invention.** Odoo's pricelist mechanism already handles multi-currency, time-bounded, customer-segment-bounded pricing. Inventing parallel `x_etsy_price` / `x_amazon_price` fields would duplicate that mechanism.
- **Excel mirror without contamination.** Owner answer #2 (Excel stays canonical) means the system has to round-trip the Excel columns *somewhere*. Storing them on `product.template` as labelled bookkeeping fields is the cheapest mirror that doesn't pollute pricing logic.
- **Margin math has one home.** `x_listing_price - standard_price - x_shipping_price_internal - x_additional_cost = unit margin`. This is computable from the bookkeeping fields without leaking into sale-order pricing.
- **Channel-specific override.** When a channel needs a different list price than Excel suggests, BA edits the channel pricelist; Excel does not need to be the only entry point.

### 3. Source-of-truth & sync direction (the canonical-flow contract)

For the **current phase** (Excel canonical, Odoo as hub, Etsy as first downstream):

```
Excel "[2025] Product Catalog.xlsx"            (canonical edit surface — BA's tool)
       │
       │  recurring sync (Spec 010 / P-HUB-XLS-CRON, default 1×/day; manual wizard available)
       ▼
Odoo `product.template` + `multichannel.sales.channel`   (system of record)
       │
       │  per-channel publisher (Spec 011 / P-PUB-* family)
       ▼
Etsy `etsy.listing` ⇆ `etsy.listing.product`   (channel mirror — already exists, ADR-013)
```

Field-level direction rules (the conflict-resolution matrix, applied at every sync boundary):

| Field family | Excel→Odoo | Odoo→Etsy | Etsy→Odoo | Notes |
|---|---|---|---|---|
| `name`, `description_sale`, `categ_id`, `x_listing_price`, `x_shipping_price_internal`, `x_additional_cost`, `default_code` (legacy SKU) | **Excel wins** | Yes | No (display only) | Excel is canonical authoring surface |
| Images (`image_1920`, `product.image`) | **Excel wins** (per P-HUB-IMAGES rules — Excel Image 1/2 columns) | Yes (`uploadListingImage`) | No | Re-uploading on every Odoo→Etsy publish would burn quota; only re-upload on hash change |
| Channel applicability (`x_channel_applicability_ids`) | Excel "Availability" column derives a default; **Odoo overrides** persist | Drives whether the product is published at all | n/a | BA may toggle channels in Odoo UI even if Excel says otherwise; this is the one Excel→Odoo override allowed |
| Variant qty (`product.product.qty_available` from `stock.quant`) | n/a (Excel doesn't carry stock) | **Odoo wins** (writeback via `PUT /listings/{id}/inventory`) | Read-only mirror in `etsy.listing.product.quantity`; drift report only | Operator must explicitly run an inventory push wizard; not auto-pushed |
| SKU (`product.product.default_code`) | **Excel wins** for legacy; v2-canonical computed by Odoo (see §4) | New publishes use v2-canonical; existing listings keep legacy until BA-approved canonicalisation | Backfill imports Etsy SKU as `default_code` (Etsy reality preserved) | See §4 SKU drift policy |
| `etsy_listing_variant_id` (FK from product → etsy.listing.product) | n/a | n/a | **Odoo writes only via P-LIST-INV-PULL ingest or P-PUB-DRAFT post-create** | Cross-link is system-managed, not user-editable |
| Pricelists | Seeded from Excel multi-currency columns on first import; subsequent edits in Odoo | Per-channel pricelist resolves the sell price | n/a | Excel's USD/EU/CAD/VND columns seed once; ongoing pricing managed in Odoo |

Backfill (one-time per shop, P-HUB-BACKFILL):

```
etsy.listing + etsy.listing.product  →  match-or-create product.template
                                        + cross-link via etsy_listing_variant_id
                                        + flag unmatched as "Etsy-only — BA decision"
```

The backfill never archives a live Etsy listing, never edits Etsy via API, and never overwrites a `product.template` that already exists (it only fills in fields that are NULL in Odoo).

### 4. SKU drift policy (owner answers 2026-05-23)

The Excel column "SKU" is BA-hand-edited and does not always match grammar v2. The system **keeps both** — the historical/Etsy-visible SKU and the v2-canonical suggestion — and lets BA reconcile on their own schedule.

Field shape on `product.template`:

| Field | Type | Purpose |
|---|---|---|
| `x_sku_v2_suggested` | Char (computed, indexed) | Output of grammar v2 regex against `name`. Read-only. |
| `x_sku_v2_status` | Selection | `matches` / `non_canonical` / `msc_catchall` / `ba_approved_legacy` |
| `x_sku_legacy` | Char | Archive of the previous `default_code` after a canonicalisation wizard run; otherwise empty |

`product.product.default_code` continues to hold the Etsy-visible / live SKU.

Policy:

1. **Excel ingest never blocks on grammar drift.** Non-canonical rows ingest fine; they accumulate in a queryable backlog (`x_sku_v2_status in ('non_canonical', 'msc_catchall')`).
2. **New Etsy publishes use the v2-canonical SKU** when `x_sku_v2_suggested` is non-empty AND `x_sku_v2_status != 'ba_approved_legacy'`. Otherwise the publish uses `default_code`. Owner answer 2026-05-23: new publishes are always grammar-v2-canonical.
3. **Canonicalising a live listing auto-pushes the SKU change to Etsy** via the entire-array-resubmit `PUT /listings/{id}/inventory` path (same path as P-PUB-INVENTORY). Audit row in `etsy.api.log`. Wizard is the only entry point; no silent rewrites. Owner answer 2026-05-23.
4. **Backfill preserves Etsy reality.** Listings imported via P-HUB-BACKFILL keep their Etsy SKU as `default_code` even if non-canonical; `x_sku_v2_suggested` is computed so they surface in the drift report alongside Excel-imported products.

Wizard: `product.sku.canonicalise.wizard` exposes two actions per product:
- **Keep legacy** → writes `x_sku_v2_status = 'ba_approved_legacy'`. Row stops surfacing.
- **Accept canonical** → moves `default_code` → `x_sku_legacy`, writes `x_sku_v2_suggested` → `default_code`. If the product has a linked active Etsy listing, fires `PUT /listings/{id}/inventory` synchronously; if push fails (rate-limit, 4xx with captured response body), the canonicalisation rolls back (durable audit row remains).

### 5. Module ownership

Per ADR-003 (module decomposition) and memory `feedback_channel_agnostic_groups_in_mhc`:

| Asset | Module | Reason |
|---|---|---|
| `multichannel.sales.channel` model + ACL + seed records | `multichannel_hub_core` | Channel-agnostic reference — used by every channel module |
| `product.template` extensions (channel M2M, pricing bookkeeping, SKU drift trio) | `multichannel_hub_core` | Channel-agnostic; Amazon/website channels will reuse |
| `product.channel.status` model | `multichannel_hub_core` | Per-(product, channel) state; channel-agnostic |
| Catalog Excel parser + ingestor + cron | `multichannel_hub_core` | Channel-agnostic (catalog feeds all channels) |
| Product-creation wizard (validation pipeline) | `multichannel_hub_core` | Channel-agnostic |
| SKU canonicalisation wizard | `multichannel_hub_core` (wizard) + `etsy_integration` (push hook) | The canonicalisation itself is channel-agnostic; the Etsy push uses an extension point so future channels can register their own canonicalisation pushers |
| `EtsyListingPublisher` + `EtsyApiClient.post/put/post_multipart` | `etsy_integration` | Etsy-specific |
| Publish wizard | `etsy_integration` | Etsy-specific UI |
| VN owner-flow docs | `docs/owner/` (top-level) | Owner-facing, not module-scoped |

## Consequences

### Positive

- A single source of truth for the catalog (Odoo `product.template`), aligning the whole MP006 backend with the owner's mental model.
- Multi-channel is a Many2many flag, not a typed hierarchy — Amazon + ecommerce land without rewriting the catalog or duplicating product rows.
- BA workflow does not have to move into Odoo overnight; Excel stays canonical until natural migration.
- SKU drift becomes a *queryable backlog* with a *one-click resolve path*, not a blocking error class.
- Backfill is non-destructive — JaHandmadeArt's existing listings stay live, just get an Odoo twin.
- Per-channel pricelist reuse means currency / segment / time-bounded pricing is a stock-Odoo problem, not a custom one.

### Negative

- `product.template` adds 6 new fields (`x_channel_applicability_ids` M2M, `x_listing_price`, `x_shipping_price_internal`, `x_additional_cost`, `x_sku_v2_suggested`, `x_sku_v2_status`, `x_sku_legacy`) — schema growth is real but bounded.
- Two new mhc models (`multichannel.sales.channel`, `product.channel.status`).
- Excel-as-canonical introduces a sync direction that has to be re-policed at every Spec 010 / Spec 011 boundary; the conflict matrix (§3) is the canonical reference.
- BA needs an in-Odoo "SKU drift review" surface to reconcile non-canonical rows; that's a new operational workflow on top of catalog edits.

### Neutral

- The Excel→Odoo→Etsy direction is one of two long-term equilibria (the other being Odoo as authoring surface). ADR-014's choice supports a future evolution to Odoo-as-authoring without an architectural rewrite — when BA adopts the Odoo UI, the cron becomes "off" and the field-direction matrix degenerates to a single-source-of-truth (Odoo) with channel writes downstream. Documenting that evolution path in §evolution rather than gating ADR-014 on a future Odoo-authoring decision.

## Alternatives considered

1. **Typed channel inheritance (`etsy.product`, `amazon.product` separate models with `_inherits('product.template')`)** — rejected. Duplicates the catalog per channel; doesn't survive multi-channel growth; channel M2M solves the same problem at fraction of the cost.
2. **Channel state stored on `etsy.listing` only (no `product.channel.status` table)** — rejected. Forces a SKU search every time the publisher needs to ask "is this product on Etsy?"; doesn't scale to multi-channel without a parallel `amazon.listing` traversal.
3. **Per-channel price fields on `product.template` (`x_etsy_price`, `x_amazon_price`, ...)** — rejected. Reinvents `product.pricelist`; explodes columns per channel.
4. **Odoo as authoring surface immediately (skip Excel canonical phase)** — rejected by owner answer #2. BA tooling change is a non-trivial business decision; ADR-014's design supports both equilibria so the transition is a config flip, not a rewrite.
5. **Replace existing Etsy listings on backfill** — rejected by owner answer #3. Loses URLs, SEO history, review history; high blast radius for a one-time data move.
6. **Auto-rewrite non-canonical SKUs on import** — rejected by owner answer 2026-05-23. Mutates Etsy-visible reality without operator awareness; high blast radius.
7. **Block Excel import on grammar drift** — rejected by owner. Breaks BA's authoring workflow; treats drift as an error class rather than a backlog.

## Implementation notes

- **Spec mapping**: Spec 009 builds §1, §2, §4 (model + wizard + drift trio + backfill). Spec 010 builds §3-Excel-half (parser, ingestor, cron, image downloader). Spec 011 builds §3-Etsy-half (publisher, image upload, inventory push, publish state machine; absorbs and supersedes the deferred Spec 008 P-LIST-INV-PUSH slice).
- **Reuse**: ADR-013's `etsy.listing` / `etsy.listing.product` models are unchanged. ADR-010's MTO/Dropship routing (`x_gearment_sku` auto-route, `product_mto_bom_wizard`) is unchanged. The new creation wizard wraps these; it does not replace them.
- **Constraint discipline**: every UNIQUE on the new models (`multichannel.sales.channel.code`, `product.channel.status (product_tmpl_id, channel_id)`) must be mirrored in `init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check — Odoo 19 `_sql_constraints` is inert (per memory `project_sql_constraints_drift`, 8+ confirmations, including ADR-013 implementation).
- **ACL**: read `base.group_user` on `multichannel.sales.channel`; write restricted to `base.group_system` (channel reference data, not BA-editable). `product.channel.status` follows the same shape. Pricing / SKU-drift fields on `product.template` follow existing product ACLs; the canonicalisation wizard is gated to the BA group (`multichannel_hub_core.group_ba_*` — final group decision in Spec 009).
- **Two-Phase Testing**: applies to Spec 009/010/011 implementation slices; ADR-014 (this planning artifact) is N/A.
- **Escape hatch if reversed**: drop `multichannel.sales.channel` + `product.channel.status` tables, drop the 6 `product.template` columns, drop the Excel cron — `etsy.listing` mirror and the existing Etsy ingest stay intact. The product hub is additive over the read-only mirror.

## Evolution path (informational, not a decision)

When BA adopts the Odoo UI as the catalog authoring surface (post-MP006 timeline, owner-driven):

1. Excel cron is disabled (cron `active=False`); the parser+ingestor stay deployed for one-off re-imports.
2. The field-direction matrix in §3 degenerates: Excel→Odoo direction becomes inert; Odoo is authoritative everywhere.
3. The SKU drift report becomes empty over time as BA edits products in-Odoo with grammar-v2 validation enforced at the wizard layer.
4. No model change, no ADR supersession needed.

If a third-party PIM (Akeneo, Pimcore) is later adopted as the upstream:

1. A new parser/ingestor pair (mirror of Spec 010) lands; Excel cron is disabled.
2. The Excel sheet is archived.
3. ADR-014's structure (M2M channel applicability, per-channel pricelist, SKU drift trio, conflict matrix) is unchanged.

This evolution path is *informational*; no future ADR is required to enact it — only a configuration change + an importer swap. ADR-014's design absorbs the variability.
