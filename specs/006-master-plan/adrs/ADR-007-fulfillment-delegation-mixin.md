# ADR-007: `sale.order.fulfillment` Delegation Mixin

- **Status**: Accepted
- **Date**: 2026-04-10
- **Sign-off**: 2026-04-13 (owner)
- **Deciders**: Owner, architect
- **Affects**: Spec 003 (dashboard + channel fields), Spec 004 (fulfillment routing + partner + tracking)
- **Related**: [tech-architect.md §1 "Is sale.order becoming a god object?"](../agent-reports/tech-architect.md)

## Context

Across specs 001–005, `sale.order` accumulates approximately **40 new fields**:

| Spec | Field count | Examples |
|---|---|---|
| 001 (shipped) | 11 | `is_etsy_order`, `etsy_order_id`, `etsy_shop_id`, `etsy_order_status`, `etsy_shipping_cost`, `etsy_discount_code`, `etsy_transaction_ids`... |
| 002 | 1 (draft) | `etsy_has_discount`, and now `etsy_price_anomaly` from ADR-002-adjacent work |
| 003 | 9 | `sales_channel`, `channel_order_ref`, `shipping_date`, `tracking_number`, `shipping_carrier` (now `shipping_carrier_id` per [ADR-005](ADR-005-carrier-unification.md)), `shipping_label_status`, `fulfillment_status`, `fulfillment_note`, `pic_user_id`, `order_priority` |
| 004 | 13 | `fulfillment_route`, `fulfillment_partner_id`, `routed_by`, `routed_date`, `production_stage`, `production_blocked`, `production_block_reason`, `partner_sync_status`, `partner_sync_date`, `partner_ref`, `gearment_order_id`, `gearment_price_quote`, `label_url`, `qrcode_url`, `gke_shipping_cost_vnd`, `tracking_import_date`, `original_order_id`, `is_replacement_order` |
| 005 | 6 | `etsy_sync_source`, `etsy_last_modified`, `etsy_tracking_push_status`, `etsy_tracking_push_date`, `etsy_tracking_push_error`, `etsy_receipt_status` |

The standard Odoo `sale.order` model already has ~80 fields. After specs 001–005, the team will be looking at a `sale.order` form with **~120 fields** across all domains (sales, logistics, fulfillment, design, channels, audit).

Technical architect review flagged this as a **god-object risk**: cognitive load for contributors, messy form views, slow form rendering (Odoo loads all tracked-field computations on form open), and a brittle base for future channels (Amazon, Website).

At the same time, **many of these fields are conceptually separate from the "this is a sales order" identity**. They describe the order's **fulfillment lifecycle**, not its commercial essence. A clean architectural boundary exists.

## Decision

Introduce a **delegation mixin** `sale.order.fulfillment` via Odoo's `_inherits` mechanism. The fulfillment row is a sibling of the sale order, not a child, with a 1:1 relationship. Heavyweight operational fields migrate to this sibling model. Lightweight identity and channel fields stay on `sale.order`.

### Model definition (in `multichannel_hub_core` per [ADR-003](ADR-003-module-decomposition.md))

```
sale.order.fulfillment
  _name       = 'sale.order.fulfillment'
  _inherits   = {'sale.order': 'order_id'}
  _description = 'Fulfillment lifecycle for a sale order'

  order_id                 Many2one('sale.order'), required, ondelete='cascade'

  # Operational routing & production (was Spec 004)
  fulfillment_route        Selection([('internal','Internal'),('partner','Partner')])
  fulfillment_partner_id   Many2one('fulfillment.partner')
  routed_by                Many2one('res.users')
  routed_date              Datetime
  production_stage         Selection(...)  # pending, in_progress, produced, on_hold, rejected, etc.
  production_blocked       Boolean
  production_block_reason  Text

  # Partner sync bookkeeping (was Spec 004)
  partner_sync_status      Selection([...])
  partner_sync_date        Datetime
  partner_ref              Char         # Gearment order ref, etc.
  gearment_order_id        Char
  gearment_price_quote     Float
  label_url                Char
  qrcode_url               Char

  # Tracking + logistics (was Spec 003 + 004)
  shipping_date            Date
  tracking_number          Char, index=True
  shipping_carrier_id      Many2one('shipping.carrier')  # per ADR-005
  shipping_label_status    Selection([...])
  gke_shipping_cost_vnd    Float
  tracking_import_date     Datetime

  # Operational UI (was Spec 003)
  fulfillment_status       Selection(...)  # the 7-stage state machine
  fulfillment_note         Text
  pic_user_id              Many2one('res.users')
  order_priority           Selection([('normal','Normal'),('push','Push'),('urgent','Urgent')])

  # Replacement lineage (was Spec 004)
  original_order_id        Many2one('sale.order')
  is_replacement_order     Boolean, compute, store
```

The `_inherits` mechanism means:
- `sale.order` automatically gains read/write access to all fulfillment fields as if they were its own (Odoo follows the delegation).
- But in the database, the fulfillment fields are stored in `sale_order_fulfillment`, not in `sale_order`. Smaller row width on the hot `sale_order` table.
- Creating a sale.order automatically creates the fulfillment record (lazy on first field write, or eagerly via `@api.model_create_multi` override).
- Accessing `order.fulfillment_status` Just Works.

### What stays on `sale.order`

- All 11 Etsy identity fields from Spec 001 (they're the primary key to Etsy)
- `sales_channel`, `channel_order_ref` from Spec 003 (channel identity, cheap Selections/Chars, heavily searched)
- Spec 005's 6 API sync bookkeeping fields (they're about the channel sync, not fulfillment)
- Spec 002's `etsy_has_discount`, `etsy_price_anomaly` (financial computation on the order itself)

### What moves to `sale.order.fulfillment`

- All 13 Spec 004 fulfillment-routing fields
- All 9 Spec 003 operational/dashboard fields
- The carrier M2O from [ADR-005](ADR-005-carrier-unification.md)

### Form view layout

- **Main `sale.order` form**: standard Odoo tabs (Order Lines, Customer, Other Info, Chatter) + a new tab **"Fulfillment"** that renders the `sale_order_fulfillment` one2one via `widget="one2many_list"` with a collapsed/expanded view.
- **Dashboards** (Order, Tracking, Process from Spec 003 rewrite): render list views on `sale.order` with fulfillment fields accessed via the delegated relation (`order.fulfillment_status`, etc.). Odoo treats these as direct fields on sale.order because of `_inherits`.

### Indexing and search

- Indexes on the fulfillment table, not on sale_order. Smaller, faster indexes.
- Composite index `(fulfillment_status, order_priority)` on `sale_order_fulfillment` speeds up dashboard queries.
- Searches like `sale.order.search([('fulfillment_status','=','produced')])` work transparently because Odoo rewrites the query through the `_inherits` join.

## Consequences

### Positive
- **sale.order row width stays manageable**: ~95 fields instead of ~120, with the operational half decoupled.
- **Cleaner code ownership**: `multichannel_hub_core` owns the fulfillment mixin. `etsy_channel` can extend `sale.order` with channel fields without conflicts.
- **Form view clarity**: the Fulfillment tab is self-contained. Designers/PD see only what they need.
- **Reusable across channels**: when Amazon (Spec 010) lands, Amazon orders automatically get the same fulfillment sibling. No per-channel duplication.
- **Performance wins**: the hot `sale_order` table has fewer columns. Dashboard tree views with 80 rows × fewer columns render faster.
- **Testability**: fulfillment logic can be tested against the sibling model directly, without setting up a full sale.order fixture.

### Negative
- **Additional join on every query**: `_inherits` adds an implicit JOIN between `sale_order` and `sale_order_fulfillment`. In practice this is fast (indexed FK, 1:1), but it's not zero.
- **Must land before Spec 004 code**: if Spec 003 fields are added directly to `sale.order` first and then moved later, the migration is painful. Retrofitting requires a data-migration script that copies column values between tables, drops the old columns, and updates all existing XML views. Strict ordering requirement.
- **Form view complexity for admins**: showing the fulfillment fields requires a sub-view, not inline fields. Minor UX overhead, easily handled.
- **`_inherits` is less common than `_inherit`**: contributors may need a pointer to the Odoo docs. Include a comment in the model file.

### Neutral
- This is a standard Odoo pattern (used by `hr.employee` via `resource.resource`, `product.product` via `product.template`, etc.). Not experimental.

## Alternatives considered

1. **Leave all fields on `sale.order`** — rejected. Tech architect's god-object concern is valid. Form views become unreadable at 120+ fields, and the hot table bloats.
2. **Create a `sale.order.fulfillment` model with a regular `Many2one` FK (not `_inherits`)** — rejected. Requires every piece of code that reads fulfillment fields to go through `order.fulfillment_id.field_name`, breaking the abstraction and adding verbose boilerplate. Also, `_inherits` specifically handles the 1:1 creation semantics automatically; an M2O would require manual create/write logic.
3. **Multiple mixins** (`sale.order.production`, `sale.order.shipping`, `sale.order.partner_sync` as separate siblings) — rejected. Too fine-grained. The boundary between "this is a sales order" and "this is being fulfilled" is clean, but finer splits create joins with marginal benefit.
4. **Use field groups in XML views to visually separate** — rejected. Solves the form-view-clutter symptom but not the underlying god-object problem. Doesn't help with table width, code ownership, or channel reuse.
5. **Defer the decision, add fields directly, refactor later** — rejected. See "must land before Spec 004 code" above. Retrofitting is strictly worse than doing it up front.

## Implementation notes

- Create `sale.order.fulfillment` in `multichannel_hub_core` during Phase 1 (Spec 003 rewrite), **before** any Spec 003 fields are added to the codebase.
- Override `sale.order` create to auto-create the fulfillment sibling:
  ```
  @api.model_create_multi
  def create(self, vals_list):
      orders = super().create(vals_list)
      # _inherits handles this automatically if the sibling model has a default record,
      # but explicit creation here guards against corner cases
      for order in orders:
          if not order.fulfillment_id:  # sanity check
              self.env['sale.order.fulfillment'].create({'order_id': order.id})
      return orders
  ```
- Existing shipped `sale.order` fields from Spec 001 are NOT migrated (they're Etsy identity, they stay).
- Dashboard tree/list views in Spec 003 use the delegated access pattern. No special syntax needed — Odoo handles it.
- Write a unit test that creates a `sale.order`, asserts the fulfillment sibling exists, writes to a fulfillment field, reads it back through both the sale.order and the sibling, and deletes the order (asserting cascade).
- Document the pattern in `specs/003-dashboard-design-multichannel/data-model.md` so future contributors understand why there's a sibling.
- If the team later decides to roll back this decision, the migration path is well-defined: ALTER TABLE sale_order ADD COLUMN for each field, copy from sibling, drop sibling. Known escape hatch.
