# Data Model: Central Product Hub (Spec 009)

- **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md) | **ADR**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md)

## Entity Overview

| Entity | Status | Module | Description |
|---|---|---|---|
| `multichannel.sales.channel` | NEW | `multichannel_hub_core` | Reference list of sales channels (Etsy, Amazon, website, ...) |
| `product.channel.status` | NEW | `multichannel_hub_core` | Per-(product_template, channel) state + channel-side back-ref |
| `product.template` | EXTENDED | `multichannel_hub_core` | 6 new fields (M2M + pricing bookkeeping + SKU drift trio) + 1 computed |

---

## 1. `multichannel.sales.channel` (NEW)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `code` | Char | Yes | — | `etsy` / `amazon` / `website` / ...; lowercase ASCII; indexed |
| `name` | Char | Yes | — | Display label (translatable) |
| `sequence` | Integer | Yes | 10 | M2M picker ordering |
| `active` | Boolean | Yes | True | Soft-disable flag |
| `description` | Text | No | — | Operator help |

**Constraints**
- C-CH-001: UNIQUE `(code)`. Mirror via `init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check (per memory `project_sql_constraints_drift`).

**Indexes**: `(active, sequence)` for picker; `(code)` for code-based lookups in publisher services.

**ACL**: read `base.group_user`; write `base.group_system` (channel reference data, not BA-editable).

**Seed** (`data/multichannel_sales_channel_seed.xml`, `noupdate=1` so admin edits persist):
| code | name | active |
|---|---|---|
| `etsy` | Etsy | True |
| `amazon` | Amazon | False (activated when Phase 5 lands) |
| `website` | Website / Ecommerce | False (same) |

---

## 2. `product.channel.status` (NEW)

Per-(product, channel) state. Created when a product is first added to a channel; updated by the publisher service.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `product_tmpl_id` | Many2one(`product.template`) | Yes | — | `ondelete='cascade'`; indexed |
| `channel_id` | Many2one(`multichannel.sales.channel`) | Yes | — | `ondelete='restrict'`; indexed |
| `state` | Selection | Yes | `draft` | `draft` / `published` / `archived` / `error` |
| `external_ref` | Char | No | — | Channel-side ID (e.g. Etsy listing ID); indexed |
| `last_sync_at` | Datetime | No | — | Last write/read to channel |
| `last_sync_error` | Text | No | — | Last publisher error message (truncated 4 KB) |

**Constraints**
- C-PCS-001: UNIQUE `(product_tmpl_id, channel_id)` — one status per (product, channel). Mirror via `init()`.
- C-PCS-002: `state ∈ {draft, published, archived, error}` (enforced by Selection).

**Indexes**: `(channel_id, state)` for publisher dispatch; `(product_tmpl_id)` for product form One2many; `(external_ref)` for reverse lookup from channel webhook.

**ACL**: read `base.group_user`; write `base.group_system` (publisher service writes via sudo).

---

## 3. `product.template` (EXTENDED)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `x_channel_applicability_ids` | Many2many(`multichannel.sales.channel`) | No | empty | Picker filters to `active=True` |
| `x_sales_channel_status_ids` | One2many(`product.channel.status`, `product_tmpl_id`) | — | — | Per-channel state rows |
| `x_listing_price` | Float (digits=Product Price) | No | 0.0 | Excel "Price USD" bookkeeping; **NOT** sale-order pricing source |
| `x_shipping_price_internal` | Float (digits=Product Price) | No | 0.0 | Excel "Shipping Fees" bookkeeping |
| `x_additional_cost` | Float (digits=Product Price) | No | 0.0 | Excel "Other costs" bookkeeping |
| `x_unit_margin` | Float (computed, stored, digits=Product Price) | — | — | `x_listing_price - standard_price - x_shipping_price_internal - x_additional_cost`; depends on those 4 |
| `x_sku_v2_suggested` | Char (computed, stored, indexed) | — | — | Grammar v2 regex output against `name`; recomputed when `name` changes |
| `x_sku_v2_status` | Selection (computed, stored, indexed) | — | — | `matches` / `non_canonical` / `msc_catchall` / `ba_approved_legacy`; `ba_approved_legacy` is write-set by canonicalisation wizard, not computed; computation skips that case |
| `x_sku_legacy` | Char | No | — | Archive of prior `default_code` after canonicalisation wizard run |

**ACL**: existing `product.template` ACLs preserved; the new fields inherit them. Writes to `x_sku_v2_status='ba_approved_legacy'` and to `x_sku_legacy` go via the canonicalisation wizard (which is BA-gated, not group_system).

**No new constraint** on `product.template` — the SKU drift fields are advisory, not enforced.

---

## 4. Computed Fields

```python
# Spec 009 P-HUB-PROD-MODEL

@api.depends('x_listing_price', 'standard_price', 'x_shipping_price_internal', 'x_additional_cost')
def _compute_unit_margin(self):
    for rec in self:
        rec.x_unit_margin = (
            (rec.x_listing_price or 0.0)
            - (rec.standard_price or 0.0)
            - (rec.x_shipping_price_internal or 0.0)
            - (rec.x_additional_cost or 0.0)
        )

@api.depends('name')
def _compute_x_sku_v2(self):
    """Evaluate grammar v2 regex from frozen family rules.

    Status semantics:
      - `matches`: a non-MSC family regex matched name
      - `non_canonical`: name matched MSC catch-all (i.e. no specific family)
      - `msc_catchall`: name matched nothing (falls through to MSC by rule)
      - `ba_approved_legacy`: write-set by canonicalisation wizard; this
        compute does NOT overwrite that status.
    """
    for rec in self:
        if rec.x_sku_v2_status == 'ba_approved_legacy':
            continue  # operator-pinned; never auto-overwrite
        suggested, family_code = sku_grammar_v2.evaluate(rec.name or '')
        rec.x_sku_v2_suggested = suggested
        if family_code == 'MSC':
            rec.x_sku_v2_status = 'msc_catchall'
        elif suggested == (rec.default_code or ''):
            rec.x_sku_v2_status = 'matches'
        else:
            rec.x_sku_v2_status = 'non_canonical'
```

`sku_grammar_v2.evaluate(name)` returns `(suggested_sku, family_code)` from the frozen `family_rules` tuple imported from `.0temp/deliverables/D1_product_taxonomy_SKU.xlsx`. The tuple is bundled at module-build time (not read from disk at runtime); regeneration of the tuple is a manual ops task documented in the SKU grammar README.

---

## 5. Rationale Notes

- **No new constraint on `product.template`.** Adding `_sql_constraints` here would conflict with the inert Odoo-19 behaviour (memory `project_sql_constraints_drift`) and the wider catalog's existing SKU non-uniqueness (R-L1 from ADR-013). Drift is *reported*, not *prevented*.
- **`x_sales_channel_status_ids` is a One2many on `product.template`, not on `product.product`.** Listing-level channel state is template-level (one listing per product per channel); variant-level state is tracked via `product.product.etsy_listing_variant_id` (already in place from ADR-013) — no schema change at the variant level.
- **`product.channel.status.external_ref` is intentionally untyped (Char).** Etsy listing IDs are numeric; Amazon SKUs are alphanumeric; Char is the lowest common denominator. The channel-side mirror table (`etsy.listing`, future `amazon.listing`) holds the strongly-typed canonical ID.
- **Pricing reuse.** `product.template.list_price` (stock Odoo) is the sell price, resolved through `product.pricelist`. The three Excel-mirror fields (`x_listing_price`, etc.) are NOT used to compute order lines. This separation prevents an Excel typo from corrupting live order pricing.
- **Backfill writes `product.template`, not `product.product`.** The variant link (`product.product.etsy_listing_variant_id`) was already populated by P-LIST-INV-PULL; backfill only ensures the template exists upstream.
