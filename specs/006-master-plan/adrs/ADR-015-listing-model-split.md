# ADR-015: Listing-level fields live on `multichannel.listing`, not `product.template`

- **Status**: Accepted
- **Date**: 2026-06-06
- **Sign-off**: 2026-06-06 (owner via Telegram — preference Option C in `docs/jira/in-progress-2026-06-04.md`, confirmed `dispatch P-LIST-VIDEO` blocked → `1` (run spec slice first))
- **Deciders**: Owner, orchestrator (Sonnet inline)
- **Affects**: All 7 Wave-2 listing-parity slices (`P-LIST-VIDEO`, `P-LIST-CATEGORY`, `P-LIST-SHIPPING`, `P-LIST-ATTRIBUTES`, `P-LIST-HOW-ITS-MADE`, `P-LIST-ATTR-CONFIG`, `P-LIST-SHOP-BULK`); future Amazon + ecommerce listing surfaces
- **Related**: [ADR-013](ADR-013-etsy-listing-architecture.md) (channel-side `etsy.listing` read-only mirror — kept), [ADR-014](ADR-014-central-product-hub.md) (Odoo as central product hub — extended here), [ADR-003](ADR-003-module-decomposition.md) (channel-agnostic models live in `multichannel_hub_core`)

## Context

The Owner publish-from-Odoo dry-run on 2026-06-03 surfaced 11 feedback items captured as Jira tickets ESTY-187..ESTY-199. Classification in `docs/jira/in-progress-2026-06-04.md` groups them into 1 bug (Wave 1 — P-BUG-ESTY-188, shipped iter1+iter2+iter3 between 2026-06-05 and 2026-06-06) + 7 listing-parity gaps (Wave 2) + 3 enhancements/spec (Wave 3).

The 7 Wave-2 slices all add new fields or behaviors *for the act of listing on Etsy*: `taxonomy_id` (category), `who_made` / `when_made` / `is_supply` (how it's made), `shipping_profile_id` reference, attribute matching (which Odoo `product.attribute` maps to which Etsy `property_id`), 1× video per listing, shop-level attribute defaults, per-shop bulk-action filters. Three structural questions block them:

1. **Where do these fields live?** If they hang off `product.template`, the template fattens with channel-specific concerns, contradicting ADR-014 §1 ("channels subscribe; they do not own"). The template should describe *the product* (size/material/weight/SKU/category) independent of channel.
2. **What represents a per-channel fork** (the same Tray published differently to Etsy JaHandmadeArt vs Etsy NamcoHome — different title, taxonomy, who_made defaults)? `etsy.listing` is a *read-only mirror* of what already exists on Etsy (ADR-013); it cannot hold pre-publish operator intent.
3. **Where does `P-ENH-ESTY-190` (per-channel/per-shop Title / Description / Image overrides) live**? It cannot live on `product.template` (which has one description), and cannot live on `etsy.listing` (which only exists after first publish).

`docs/jira/in-progress-2026-06-04.md` proposed three options:

- **Option A — permissions only**: keep everything on `product.template`, add view-level groups to restrict who sees what. Rejected: doesn't solve the per-channel-fork problem; fattens `product.template`; ACL gymnastics scale poorly to 3+ channels.
- **Option B — split views**: same model, different views per role. Same rejection as A plus operator confusion (which view shows truth?).
- **Option C — separate listing model** linked M2O to `product.template`. Owner's expressed preference. This ADR formalizes Option C.

## Decision

### 1. New model `multichannel.listing` in `multichannel_hub_core`

```
multichannel.listing
  _name = 'multichannel.listing'
  _description = 'Per-channel/per-shop listing intent (pre-publish source of truth)'
  _order = 'product_tmpl_id, channel_id, sequence, id'

  product_tmpl_id   M2O → product.template (required, ondelete='cascade')
  channel_id        M2O → multichannel.sales.channel (required)
  shop_ref          Char (free-text shop identifier; e.g. 'jahandmadeart',
                    'namcohome' for Etsy; SKU+ASIN later for Amazon)
  sequence          Integer (per-template ordering)

  # Listing-level marketing overrides — empty falls back to product.template
  title             Char (fallback: tmpl.name)
  description       Text (fallback: tmpl.description_sale)
  image_1920        Binary (fallback: tmpl.image_1920)

  # Etsy category / how-it's-made / shipping
  etsy_taxonomy_id            Char (Wave 2 / P-LIST-CATEGORY)
  etsy_shipping_profile_id    Char (Wave 2 / P-LIST-SHIPPING)
  etsy_who_made               Selection (Wave 2 / P-LIST-HOW-ITS-MADE)
  etsy_when_made              Selection (Wave 2 / P-LIST-HOW-ITS-MADE)
  etsy_is_supply              Boolean (Wave 2 / P-LIST-HOW-ITS-MADE)

  # Video (Wave 2 / P-LIST-VIDEO)
  video_attachment_id   M2O → ir.attachment (private; one per listing per Etsy cap)

  # Attribute mapping override (Wave 2 / P-LIST-ATTR-CONFIG)
  attribute_mapping_ids   O2M → multichannel.listing.attribute.mapping
                         (each row: product.attribute → etsy property_id override)

  state             Selection ['draft','ready','published','error'] default='draft'
  external_ref      Char (set to etsy.listing.etsy_listing_id after first publish)
  last_synced_at    Datetime
```

### 2. Relationship to `etsy.listing` (ADR-013) is preserved

`etsy.listing` stays as the **channel-side read-only mirror** of what currently lives on Etsy (the source of `state='active'` truth). `multichannel.listing` is the **pre-publish operator-side intent** on Odoo. The wiring after first publish:

```
product.template (1) ── (N) multichannel.listing ── (0..1) etsy.listing
   "the product"        "what we want on Etsy"      "what Etsy currently has"
```

`multichannel.listing.external_ref` references `etsy.listing.etsy_listing_id` after the first successful `create_draft`. The publisher reads from `multichannel.listing` (with `product.template` fallback for empty overrides) and writes the result back to both (`multichannel.listing.state='published'`, `etsy.listing` row created/updated).

### 3. Fields migration plan (incremental, one per Wave-2 slice)

The 7 Wave-2 slices each carry their own field migration. Existing `etsy.shop.default_*` fields (added during P-BUG-ESTY-188 iter1+iter2) stay as **shop-level defaults**; `multichannel.listing.etsy_*` fields override per listing.

| Field | Source today | Wave-2 slice | New location |
|---|---|---|---|
| Etsy taxonomy | `etsy.shop.default_taxonomy_id` (shop default) | `P-LIST-CATEGORY` | `multichannel.listing.etsy_taxonomy_id` (override) + new `etsy.taxonomy.node` cache model |
| Shipping profile | `etsy.shop.default_shipping_profile_id` (shop default) | `P-LIST-SHIPPING` | `multichannel.listing.etsy_shipping_profile_id` (override) + new `etsy.shipping.profile` cache model |
| who_made / when_made / is_supply | `etsy.shop.default_*` + per-product `product.template.x_who_made` / `x_when_made` (Spec 011 P-PUB-PER-PRODUCT-DEFAULTS) | `P-LIST-HOW-ITS-MADE` | `multichannel.listing.etsy_who_made` (override) — product.template fields migrate non-destructively (compute field stays as fallback) |
| Video | nowhere | `P-LIST-VIDEO` | `multichannel.listing.video_attachment_id` |
| Attribute mapping | `product.attribute.x_etsy_property_id` (template-level; one global mapping) | `P-LIST-ATTRIBUTES` + `P-LIST-ATTR-CONFIG` | `multichannel.listing.attribute_mapping_ids` (per-listing override) + per-shop config form |
| Shop bulk filter | n/a | `P-LIST-SHOP-BULK` | List view filter on `multichannel.listing.shop_ref` + server-action bulk edit |
| Per-channel Title / Description / Image | n/a (Wave 3) | `P-ENH-ESTY-190` | `multichannel.listing.title` / `.description` / `.image_1920` |

### 4. ACL surface

| Group | multichannel.listing access |
|---|---|
| `group_marketing` (existing) | full RW on `multichannel.listing` (this is the marketing surface) |
| `group_ba_lead` / `group_ba_user` | RW on `product.template`, **read-only** on `multichannel.listing` (BA owns the product; Marketing owns the listing intent) |
| `group_system` | full RW (admin) |
| Others | no access |

This is a clean separation: BA owns "what the product is", Marketing owns "how it's listed per shop". The publisher (which runs as sudo at the wizard FR-017 boundary) reads both.

### 5. Module home

`multichannel.listing` and its sub-models (`multichannel.listing.attribute.mapping`, `etsy.taxonomy.node`, `etsy.shipping.profile`) live in `multichannel_hub_core` per ADR-003 channel-agnostic rule. The Etsy-specific `etsy.shop.default_*` overrides stay in `etsy_integration`.

### 6. Backfill on existing data (non-destructive)

For every existing `product.template` that has either (a) an `etsy.listing` row or (b) a `product.channel.status` row with `channel_id == multichannel.sales.channel(code='etsy')`, the model-split slice (P-SPEC-LISTING-MODEL-SPLIT — this slice) creates one `multichannel.listing` row with:
- `product_tmpl_id` = the template
- `channel_id` = etsy
- `shop_ref` = the matching `etsy.shop.shop_ref` (or empty when ambiguous)
- All override fields **left null** so existing publish behavior continues with `product.template` fallback.

The backfill ships in a `post-migrate.py` under `multichannel_hub_core/migrations/`; **zero behavior change** until a Wave-2 slice starts writing override values.

## Consequences

### Positive

- Wave-2 slices each have a clear home: add the field to `multichannel.listing`, add the view tab, wire the publisher to read with template fallback. Each slice stays small (~100-200 LOC).
- `product.template` stops fattening with channel-specific concerns — protects ADR-014 §1.
- Multi-channel is structurally future-proof: Amazon/website join by adding a `multichannel.listing` per template + channel.
- Marketing role gets a dedicated editing surface without competing with BA on `product.template`.

### Negative

- One more model = one more form / list / search view = ~30-50 LOC of XML per Wave-2 slice for the listing fields.
- Operator mental model: "Where do I set the Etsy category?" → answer "on Multichannel Listing, not on the Product". Owner docs (`HUONG_DAN_TAO_SAN_PHAM_VN.md`) need a new §6.5 explaining the Product vs Listing split.
- Per-channel forks of the same product = one `multichannel.listing` per channel × shop. Volume: 1 product × 3 channels × 2 shops/channel = 6 rows; current catalog ~3 000 products → ~18 000 rows. Stays well inside Odoo's healthy O2M sizes.

### Neutral

- No code change ships in this ADR slice — pure architecture. The 7 Wave-2 slices each carry ~1-2 fields onto `multichannel.listing`, with their own migrations.
- ADR-013 (`etsy.listing` as read-only mirror) stays intact and unchanged.
- ADR-014 §1 (channel applicability M2M on `product.template`) stays intact; this ADR adds the *listing intent* layer alongside it.

## Rejected alternatives

### Option A (permissions only)
Pros: zero new models. Cons: doesn't solve per-channel forks; ACL gymnastics; `product.template` keeps growing channel-specific cruft.

### Option B (split views)
Pros: minimal model surface. Cons: operator confusion (which view shows the source of truth?); the same N field-growth problem as Option A.

### Variant: per-channel listing model (e.g. `etsy.listing.intent`, `amazon.listing.intent`)
Pros: typed; each channel can have its own field set without optional/nullable noise. Cons: code duplication for shared fields (title, description, image); harder to query "all my pending listings across channels"; breaks the channel-agnostic-in-`mhc` rule (ADR-003).

## Implementation notes for the Wave-2 slices

Each Wave-2 slice MUST:

1. Add the new field(s) to `multichannel.listing` (NOT to `product.template`).
2. Add the field to the listing form view (new view file under `multichannel_hub_core/views/multichannel_listing_views.xml`).
3. Wire the publisher to read `multichannel.listing.<field>` with fallback to `product.template.<field>` (when a fallback exists) or `etsy.shop.default_<field>` (shop default).
4. Cover the fallback chain in Phase 2 ORM tests.
5. Update `HUONG_DAN_TAO_SAN_PHAM_VN.md` §6.5 (the new Product-vs-Listing section authored by this slice) with the operator's workflow for that field.
6. Add a TC row to `UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md`.
