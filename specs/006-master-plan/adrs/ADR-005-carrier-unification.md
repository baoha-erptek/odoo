# ADR-005: Unified Carrier Model via `shipping.carrier`

- **Status**: Proposed (awaiting owner sign-off)
- **Date**: 2026-04-10
- **Deciders**: Owner, architect
- **Affects**: Spec 003 (sale.order fields), Spec 004a (shipping.carrier), Spec 005 (Etsy tracking push)
- **Related**: [tech-architect.md §1 CONFLICT-1](../agent-reports/tech-architect.md)

## Context

Across specs 003, 004, and 005, **shipping carrier identity is represented in three different ways** by three different features:

1. **Spec 003** adds `sale.order.shipping_carrier` as a `Char` (free-text string).
2. **Spec 004** introduces a `shipping.carrier` model with prefix/regex detection (USPS `9214`, UniUni `UUS`, YunExpress, etc.) and `tracking.import.line.carrier_id -> shipping.carrier` FK.
3. **Spec 005** introduces a third model, `etsy.carrier.mapping`, to translate internal carrier names (`USPS`, `UniUni`) into Etsy's fixed-enum carrier names (`usps`, `ups`, `fedex`, `dhl`, `other`) for the tracking-push API.

The three were authored at different times. Each was reasonable in isolation. Together they are:

- **Duplicative**: the same carrier concept exists in three places.
- **Lossy**: Spec 003's Char field cannot be joined against Spec 004's model, so tracking imports (which write the FK) and manual label entry (which writes the string) produce inconsistent data.
- **Brittle**: Spec 005's separate mapping model means carrier name normalization happens twice — once in Spec 004's detector, once in Spec 005's mapper.
- **Expensive to search**: searching "all orders shipped via USPS" requires an OR across Char + M2O.

**Devil's advocate point** (§4.1): Etsy's API rejects tracking pushes with carrier names that don't match its enum. Today's plan would map 90% of GKE-supplied carriers to `other`, disabling Etsy's buyer-facing tracking page. A unified carrier table with explicit Etsy-name mapping is the only clean way to handle this.

## Decision

Consolidate carrier identity into **one model**: `shipping.carrier`.

### Model definition (owned by `multichannel_hub_core` per [ADR-003](ADR-003-module-decomposition.md))

```
shipping.carrier
  name                   Char, required           # Internal display name ("USPS", "UniUni", "YunExpress", "GKE Local")
  code                   Char, required, unique   # Stable machine identifier ("usps", "uniuni", "yunexpress", "gke_local")
  is_active              Boolean, default=True
  tracking_url_template  Char                     # e.g. "https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}"
  tracking_prefix_regex  Char                     # For tracking auto-detection, e.g. "^9214[0-9]{18}$"
  etsy_carrier_name      Selection([
                           ('usps','USPS'), ('ups','UPS'), ('fedex','FedEx'),
                           ('dhl','DHL'), ('4px','4PX'), ('other','Other'),
                           ...  # from Etsy API docs
                         ])                       # Maps to Etsy API's carrier enum for tracking push
  gearment_carrier_name  Char                     # Maps to Gearment's carrier name (for future Spec 004b)
  notes                  Text
```

Seed data ships with `multichannel_hub_core` covering at minimum: USPS, UniUni, YunExpress, 4PX, DHL eCommerce, FedEx SmartPost, GKE Local. Each seed row includes the correct `etsy_carrier_name` mapping.

### `sale.order` changes

- **Before** (Spec 003 draft): `shipping_carrier = fields.Char()`
- **After**: `shipping_carrier_id = fields.Many2one('shipping.carrier', string='Shipping Carrier', index=True)`

The old Char field is renamed via migration hook to `shipping_carrier_legacy_name` (readonly, for audit only) and the new FK is populated by matching the string against `shipping.carrier.name`. Unmatched carriers are created as new `shipping.carrier` records with `is_active=False` and flagged for BA review.

### `tracking.import.line.carrier_id` (Spec 004a)

Unchanged — already an FK to `shipping.carrier`. This becomes the authoritative writer during tracking imports.

### `etsy.carrier.mapping` (Spec 005 draft)

**Deleted.** Its single responsibility (mapping internal names to Etsy enum) becomes the `etsy_carrier_name` field on `shipping.carrier`. Spec 005's tracking pusher reads directly from `order.shipping_carrier_id.etsy_carrier_name` when calling the Etsy API.

If Etsy's carrier enum is missing our carrier (e.g. GKE Local), the pusher falls back to `other` and logs a warning to `etsy.api.log` (so BA can see it). This is better than silent fallback.

## Consequences

### Positive
- **Single source of truth** for carrier identity across the whole system.
- **Searchable**: "all orders shipped via USPS" is a clean `search([('shipping_carrier_id.code','=','usps')])`.
- **Etsy push works correctly** for the majority of orders because the mapping is explicit and easy to maintain — adding a new carrier is one row in the seed XML.
- **Eliminates one model** (`etsy.carrier.mapping`) and one duplicate field.
- **Future-proof**: adding `gearment_carrier_name` (Spec 004b) and eventually `amazon_carrier_code` (Spec 010) is just a new field on `shipping.carrier`.
- **BA visibility**: the Carrier admin UI makes it obvious which carriers are mapped to which Etsy enum.

### Negative
- **Migration work for Spec 003**: the Char-to-M2O rename + data backfill needs an Odoo upgrade script (`migrations/19.0.1.0.1/post-migrate.py`). Modest (~50 LOC) but must be tested on staging first.
- **Seed data maintenance**: the Etsy carrier enum changes over time. Whenever Etsy adds a new supported carrier, the `shipping.carrier.etsy_carrier_name` Selection must be updated. Mitigation: keep a link to Etsy's API docs in a comment, and revisit annually.
- **Slight coupling** between `multichannel_hub_core` and Etsy's enum. Acceptable because the field is just a Selection — the core module doesn't call Etsy APIs.

### Neutral
- The `shipping.carrier` model replaces what would have been three separate concepts. Net model count is unchanged (Spec 003 didn't have a model, Spec 004 contributed it, Spec 005's `etsy.carrier.mapping` is deleted).

## Alternatives considered

1. **Keep three separate representations** — rejected. See context above.
2. **`shipping.carrier` without `etsy_carrier_name`, use a separate `ir.config_parameter` JSON for mapping** — rejected. Harder to audit, no FK-level integrity, seed XML is already standard pattern for master data.
3. **Use Odoo's built-in `delivery.carrier` model** — rejected. `delivery.carrier` is tightly coupled to the Delivery method workflow (pricing, shipping provider integrations) and would drag in `delivery` module logic we don't need. Our `shipping.carrier` is specifically about post-fulfillment tracking and channel reporting, a separate concern.
4. **Namespace the field `shipping_carrier_id` under `sale.order.fulfillment` mixin instead of `sale.order`** — accepted partially; see [ADR-007](ADR-007-fulfillment-delegation-mixin.md). The field lives on the delegation mixin once that lands.

## Implementation notes

- Land `shipping.carrier` model during the Spec 003 rewrite (Phase 1). This is before Spec 004a (tracking import) needs it.
- Seed XML lives at `multichannel_hub_core/data/shipping_carrier_data.xml`.
- Spec 003 data-model.md must be updated: `sale.order.shipping_carrier` Char → `shipping_carrier_id` M2O.
- Spec 005 data-model.md must be updated: delete `etsy.carrier.mapping`; `etsy_tracking_pusher.py` reads from `shipping.carrier.etsy_carrier_name`.
- Migration script in `multichannel_hub_core/migrations/19.0.1.0.1/post-migrate.py`: on first install, if `etsy_integration` is present with the old Char field, backfill `shipping_carrier_id` from the string.
- Add unit tests for the `etsy_carrier_name` mapping: every seeded carrier should either have a valid enum value or explicitly `other` with a comment.
