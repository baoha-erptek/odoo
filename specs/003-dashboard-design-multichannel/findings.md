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

---

## 2026-04-27 — P1-06 shipping.carrier slice notes

**Slice scope shaved vs ADR-005**:

- ADR-005's Etsy carrier enum was open-ended ("...from Etsy API docs"); we
  shipped a conservative subset (`usps`/`ups`/`fedex`/`dhl`/`4px`/`other`)
  with a TODO comment in the Selection. Expand once Etsy app scope review
  is approved (E1 dependency) and we can hit the live API. Carriers not in
  the enum (UniUni, YunExpress, GKE Local) seed with `etsy_carrier_name='other'`
  per ADR-005's documented push-time fallback.
- `etsy.carrier.mapping` deletion deferred — it lives in Spec 005 territory
  and will be cleaned up when Spec 005 production cutover slices land.

**Open items flagged to downstream slices**:

- **P1-01 Order Dashboard / P2-01 Tracking Dashboard**: `tracking_url_template`
  uses `{tracking_number}` placeholder. When dashboards render the URL, the
  tracking_number must be sanitized (alphanumeric-only validation before
  substitution) — XSS via `<script>` in the tracking field is the obvious
  vector. The model layer in P1-06 does not render anything; this is a UI
  concern for the consumer slice.
- **`@api.constrains('code')` uniqueness** uses `self.search()` per record,
  i.e. O(n) on bulk create. Master data is low-cardinality (7 seed + maybe
  20 manual) so this is fine — but if a future slice does bulk-import of
  carriers (e.g., from a partner CSV), revisit with a set-based check.

**Odoo 19 specifics confirmed in this slice**:

- `noupdate="0"` on seed XML is the right default for master data we want
  to extend in future releases (BAs can edit individual rows; new releases
  push new rows). `noupdate="1"` would have made future expansion painful.
- `required=True` does NOT enforce non-empty strings; it only blocks NULL.
  Use `@api.constrains` to also reject empty/whitespace-only strings (we
  did this for `name` and `code`).
- Seed XML IDs should be code-based (`shipping_carrier_<code>`) so
  `env.ref()` lookups in tests are stable across re-seeds.
