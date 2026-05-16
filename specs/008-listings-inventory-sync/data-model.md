# Data Model: Etsy Listings & Inventory Sync (Spec 008)

- **Date**: 2026-05-16 | **Spec**: [spec.md](spec.md) | **ADR**: [ADR-013](../006-master-plan/adrs/ADR-013-etsy-listing-architecture.md)

## Entity Overview

| Entity | Status | Module | Description |
|---|---|---|---|
| `etsy.listing` | NEW | `etsy_channel_api` (`etsy_integration` pre-decomposition) | Etsy shop listing metadata |
| `etsy.listing.product` | NEW | same | Variant snapshot (One2many child of `etsy.listing`) |
| `product.product` | EXTENDED | same | Add optional FK to `etsy.listing.product` |

---

## 1. `etsy.listing` (NEW)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `shop_id` | Many2one(`etsy.shop`) | Yes | — | `ondelete='cascade'`; indexed |
| `etsy_listing_id` | Char | Yes | — | Etsy listing ID; indexed |
| `title` | Char | Yes | — | Listing title (mutable) |
| `state` | Selection | Yes | — | `active` / `inactive` / `suspended` / `deleted` |
| `description` | Text | No | — | Optional |
| `url` | Char | No | — | Etsy URL; **immutable after first ingest** |
| `price` | Float | No | — | Base price, shop currency (mutable) |
| `quantity` | Integer | compute | — | Sum of active child `quantity` |
| `created_at` | Datetime | No | — | From Etsy; **immutable after first ingest** |
| `last_modified` | Datetime | No | — | Etsy mtime; indexed for incremental pull |
| `last_synced_at` | Datetime | Yes | `now()` | Last successful sync of this row |
| `is_active` | Boolean | Yes | `True` | Soft-delete flag |
| `product_ids` | One2many(`etsy.listing.product`) | — | — | Variant snapshot children |
| `variant_count` | Integer | compute | — | `len(product_ids filtered is_active)` |
| `unlinked_variant_count` | Integer | compute | — | active children with NULL `product_id` |
| `drift_status` | Selection | compute | — | `synced` / `qty_drift` / `price_drift` / `orphan` |

**Constraints**
- C-LIST-001: UNIQUE `(shop_id, etsy_listing_id)`. Mirror via `init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check (see `project_sql_constraints_drift` canonical template — `_sql_constraints` is never deployed across this codebase's addons).
- C-LIST-002: `state` ∈ {active, inactive, suspended, deleted}.

**Indexes**: `(shop_id, last_modified DESC)` incremental pull; `(shop_id, is_active)` drift filter; `(state, is_active)` dashboard counts.

**ACL**: read `base.group_user`; write `base.group_system` (cron only).

---

## 2. `etsy.listing.product` (NEW — One2many child)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `listing_id` | Many2one(`etsy.listing`) | Yes | — | `ondelete='cascade'`; indexed |
| `etsy_product_id` | Char | Yes | — | Etsy variant ID; indexed |
| `sku` | Char | No | — | Variant SKU; indexed (may be empty per Etsy) |
| `property_values` | Text (JSON) | No | — | Etsy `property_values[]` serialized JSON |
| `quantity` | Integer | No | — | Etsy-side qty snapshot |
| `price` | Float | No | — | Etsy-side variant price |
| `product_id` | Many2one(`product.product`) | No | — | Odoo link; `ondelete='set null'`; set by SKU match |
| `is_active` | Boolean | Yes | `True` | Soft-delete flag |
| `last_synced_at` | Datetime | Yes | `now()` | Snapshot timestamp |
| `odoo_qty` | Integer | compute | — | `product_id.qty_available` or 0 |
| `qty_drift` | Integer | compute | — | `quantity - odoo_qty` |

`property_values` example:
```json
[{"property_id":100,"property_name":"Color","value_ids":[200],"values":["Red"]},
 {"property_id":101,"property_name":"Size","value_ids":[201],"values":["Medium"]}]
```

**Constraints**
- C-LPROD-001: UNIQUE `(listing_id, etsy_product_id)` — one snapshot row per Etsy variant per listing. Mirror via `init()` raw SQL `pg_constraint IF NOT EXISTS` pre-check (per `project_sql_constraints_drift`).
- C-LPROD-002 (data-integrity, `@api.constrains`): if `product_id` set, `product_id.default_code == sku`.

**Indexes**: `(listing_id, sku)` drift-by-SKU; `(listing_id, is_active)`; `(product_id)` reverse lookup.

**ACL**: read `base.group_user`; write `base.group_system`.

---

## 3. `product.product` (EXTENDED)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `etsy_listing_variant_id` | Many2one(`etsy.listing.product`) | No | — | **NEW**; `ondelete='set null'`; populated by SKU match (P-LIST-INV-PULL) or manual wizard (later). |

No change to existing `product.product` ACLs.

---

## 4. Computed Fields

```python
@api.depends('product_ids', 'product_ids.is_active')
def _compute_variant_count(self):
    for rec in self:
        rec.variant_count = len(rec.product_ids.filtered('is_active'))

@api.depends('product_ids.product_id', 'product_ids.is_active')
def _compute_unlinked_variant_count(self):
    for rec in self:
        rec.unlinked_variant_count = len(
            rec.product_ids.filtered(lambda p: p.is_active and not p.product_id))

@api.depends('product_ids.qty_drift', 'product_ids.is_active', 'unlinked_variant_count')
def _compute_drift_status(self):
    for rec in self:
        actives = rec.product_ids.filtered('is_active')
        if rec.unlinked_variant_count:
            rec.drift_status = 'orphan'
        elif any(p.qty_drift for p in actives):
            rec.drift_status = 'qty_drift'
        elif any(p.price != (p.product_id.lst_price if p.product_id else p.price)
                 for p in actives):
            rec.drift_status = 'price_drift'
        else:
            rec.drift_status = 'synced'

@api.depends('product_id.qty_available')
def _compute_odoo_qty(self):
    for rec in self:
        rec.odoo_qty = rec.product_id.qty_available if rec.product_id else 0

@api.depends('quantity', 'odoo_qty')
def _compute_qty_drift(self):
    for rec in self:
        rec.qty_drift = rec.quantity - rec.odoo_qty
```

(`drift_status` is computed-not-stored in Slice 2; if the 500-variant report exceeds the 2 s NFR, promote to stored + cron-recompute as a Slice-2 optimization task — see plan.md R-L2.)

## 5. Rationale Notes

- No `mail.thread` on `etsy.listing` — it is an ephemeral mirror, not a transactional record; chatter overhead unjustified.
- `property_values` as JSON text avoids a third table + migration when shop-custom properties change.
- Soft delete keeps removed listings/variants visible to drift reports and audit.
- No direct `sale.order` ↔ `etsy.listing` link: order line → `product.product` → `etsy_listing_variant_id` → listing is already traversable.
- SKU uniqueness per company is an expectation, not a DB constraint on `product.product` (Odoo does not enforce it); duplicates are warn-logged at match time (plan.md R-L1).
