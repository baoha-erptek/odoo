# Findings — Spec 003 Dashboard / Design Multichannel

Surprises, deviations, and deferred decisions encountered while implementing
Spec 003 slices. Append-only — never delete entries; supersede with a new
dated entry instead.

---

## 2026-04-27 — ADR-007 inheritance direction was inverted from prose intent

**Where surfaced**: P1-05 (`sale.order.fulfillment` delegation mixin), Phase 1
planning.

**What we found**: ADR-007's §Decision placed `_inherits` on
`sale.order.fulfillment` pointing at `sale.order`, but the §Decision prose
("`sale.order` automatically gains read/write access to all fulfillment
fields") and the §Implementation auto-create snippet (`order.fulfillment_id`
back-pointer) both assume the *opposite* direction. Odoo's `_inherits` makes
the *defining* model a subtype of the parent, not vice-versa — same pattern
as `product.product._inherits = {'product.template': ...}` where
`product.product` gains the template's fields.

**Resolution**: D-23 in `specs/006-master-plan/decision-log.md` and a banner
amendment at the top of
`specs/006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md`. Direction
inverted to:

```
sale.order._inherits = {'sale.order.fulfillment': 'fulfillment_id'}
```

Every `sale.order` (DB-wide) gets an auto-created `sale.order.fulfillment`
sibling. Accepted as a deliberate cost of `multichannel_hub_core` being a
foundation dependency — the alternative (parent-side direction) would have
required `order.fulfillment_id.tracking_number` everywhere in dashboard code,
breaking the Spec 003 abstraction that BA users see `order.tracking_number`.

**Impact on downstream slices**:

- **P1-05** (this slice): re-scoped against direction A; `multichannel_hub_core`
  ships a standalone `sale.order.fulfillment` model + a `_inherit='sale.order'`
  extension that adds `fulfillment_id` + the `_inherits` line + a
  `@api.model_create_multi` override for eager sibling creation.
- **P1-06** (`shipping.carrier`): `shipping_carrier_id` lives on
  `sale.order.fulfillment`; no change.
- **P1-01** (Order Dashboard): tree views can read `tracking_number`,
  `fulfillment_status`, `pic_user_id`, etc. directly off `sale.order` via
  delegation — no `fulfillment_id.` prefix needed.
- **`etsy_integration`**: must declare `multichannel_hub_core` as a dependency
  (added in P1-05) so the `_inherits` line on `sale.order` resolves before
  Etsy code touches `sale.order`.

**Backfill concern**: 162 existing tests + production data already have
`sale.order` rows. After P1-05 installs, every existing row needs a
`fulfillment_id` value (the M2O is `required=True`). Handled via
`post_init_hook` in `multichannel_hub_core/__init__.py` that creates a
`sale.order.fulfillment` row for each existing order in batches.

**Why this is a finding, not just a fix**: it's a teaching moment for future
ADRs — when an architecture doc shows a model definition and prose, both must
agree on inheritance direction. Spec 003 contributors should default to
checking ADR direction against an Odoo CE reference implementation
(`product.product`, `hr.employee`) before writing planner agents that inherit
the same confusion.
