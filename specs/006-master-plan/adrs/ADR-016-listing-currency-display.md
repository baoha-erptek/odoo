# ADR-016: Listing currency display lives on `multichannel.listing`, computed non-stored

- **Status**: Accepted
- **Date**: 2026-06-06
- **Sign-off**: pending (spec mini-slice doc — owner ratifies via code-slice dispatch approval)
- **Deciders**: Owner, orchestrator (Sonnet inline)
- **Affects**: `P-ENH-ESTY-195` (this slice's code child), future per-channel pricing variants
- **Related**: [ADR-015](ADR-015-listing-model-split.md) (listing-model split — sets the surface this ADR layers on), [ADR-014](ADR-014-central-product-hub.md) (per-variant SKU §4.a — also added at iter3 to fix payload shape), [ADR-013](ADR-013-etsy-listing-architecture.md) (channel-side read-only mirror), [ADR-003](ADR-003-module-decomposition.md) (channel-agnostic models live in `multichannel_hub_core`)

## Context

P-BUG-ESTY-188 iter2 (commit `d660afd7c4b`, etsy_integration `19.0.2.34.0`) shipped per-shop currency conversion at the publish boundary:

- `etsy.shop.listing_currency_id` M2O→`res.currency`, bootstrapped from Etsy `GET /shops/{id}` `currency_code` at OAuth.
- `EtsyListingPublisher._convert_to_shop_currency(amount, shop)` wraps `res.currency._convert()` with a SOFT-FAIL → returns `amount` unchanged + WARNING when `listing_currency_id` is NULL.

The remaining gap is **operator UX**: Marketing edits a `multichannel.listing` and sees `product.template.list_price` in raw USD on the form. The Etsy storefront serves the listing in the shop's local currency (VND for JaHandmadeArt). Without a converted-display preview, Marketing has no visual signal about what number the buyer sees — root cause of one staging incident where USD 0.50 mapped to VND 12,700, below Etsy's min-price floor (P-BUG-ESTY-188 iter3 surfaced and fixed the variant case; the display gap remains for single-variant listings).

Standard-Odoo-First check (per `feedback_standard_odoo_first.md`): Odoo 19 CE ships `res.currency._convert()` + `res.currency.rate` but **no** auto-refresh cron and no provider classes. Conversion math reuses standard; rate refresh is custom-but-thin.

## Decision

### D1 — Display surface lives on `multichannel.listing`, not `product.template`

A non-stored Monetary computed field `display_price_in_shop_currency` on `multichannel.listing`. Display tier sits ABOVE the ADR-015 §3 source resolution chain (listing override → product.template fallback → etsy.shop default) — it consumes the resolved `list_price` and converts it.

**Rationale**: listing is the Etsy-facing document; one listing = one shop = one display currency. Product.template is canonical and currency-agnostic. Placing the widget on the template would multiply widgets per active shop and pollute the BA surface with channel-specific information, contradicting ADR-015 §2 (BA owns product.template; Marketing owns multichannel.listing).

### D2 — Non-stored, computed

Field is `store=False`, `compute='_compute_display_price_in_shop_currency'`, `@api.depends('product_tmpl_id.list_price', 'etsy_shop_id.listing_currency_id')`.

**Rationale**: zero migration cost; recomputes on each form load against the current `res.currency.rate` (which we want — operators preview the live rate, not a stale snapshot). Cheap math; no DB round-trip per listing thanks to recordset prefetch of shop + currency.

**Trade-off accepted**: rate changes don't trigger a write — kanban filters / list views can't filter by "listings above N VND". If that surfaces as a real need, a follow-up ADR adds a stored snapshot field. Not anticipated.

### D3 — Linkage via new typed FK `multichannel.listing.etsy_shop_id`

`multichannel.listing` ships with `shop_ref` Char only (matched by name equality in publisher `_resolve_listing_intent` at `etsy_listing_publisher.py:443`). To make the `@api.depends` chain readable and refactor-safe, this slice adds `etsy_shop_id` M2O→`etsy.shop` via `_inherit` in `etsy_integration` (NOT in mhc-core, per ADR-003 one-way dependency).

Migration backfills the FK from `shop_ref` name-lookup; ambiguous / missing → NULL + WARNING.

**Rationale**: typed FK eliminates the stringly-matched lookup in the compute path. Publisher already does the same join; this slice elevates the implicit join to an explicit FK. Side benefit: `P-ENH-ESTY-190` (per-channel marketing overrides) will need the same linkage — pre-paying the cost here.

**Boundary check**: the FK target lives in etsy_integration; the M2O column lands on the mhc table via `_inherit`. Same pattern as P-LIST-CATEGORY (`etsy_taxonomy_id`), P-LIST-SHIPPING (`etsy_shipping_profile_id`). ADR-003 respected.

### D4 — SOFT-FAIL on missing currency / missing rate

Compute method returns `0.0` (not raises) when:
- `etsy_shop_id` is False,
- `etsy_shop_id.listing_currency_id` is False, OR
- `res.currency._convert()` raises (no active rate for today; inactive currency; etc.).

WARNING logged on each fall-through; no UI raise.

**Rationale**: matches the publisher's iter2 pattern (SOFT-FAIL → unconverted amount + WARNING). Form must load even on partially-configured shops; operator-fixable later. A loud raise here would block Marketing during shop onboarding — unacceptable UX.

**Sibling computed field** `display_currency_id` (M2O→`res.currency`, also non-stored) drives the Monetary widget's currency-symbol display via `options="{'currency_field': 'display_currency_id'}"`. Returns `etsy_shop_id.listing_currency_id` or False.

### D5 — Rate-refresh cron skeleton

A daily `ir.cron` "Etsy: Refresh Shop Currency Rates" at 05:00 UTC calls `etsy.shop._cron_refresh_currency_rates()`. The method reads `ir.config_parameter etsy_integration.currency_rate_provider`:

- `'manual'` (default) → WARNING "Configure currency rate provider in settings" + return.
- Any other value → WARNING "Provider X not yet implemented; manual psql required" + return.

Provider implementations (ECB, OpenExchangeRates, Yahoo, etc.) deferred to follow-up slice.

**Rationale**: keeps Wave-3 velocity. Production today uses manual psql per P-BUG-ESTY-188 iter2 Phase 9 — no operational regression. Skeleton makes the extension point explicit. The cron `ir.cron` row + the config_parameter row land now so a future provider slice is a pure addition.

### D6 — Provider configuration via `ir.config_parameter`, not new model

Single key `etsy_integration.currency_rate_provider`. No new model. Values are string enum (`'manual'`, future: `'ecb'`, `'openexchangerates'`).

**Rationale**: per-system (not per-shop) setting; one provider applies to all shops in this Odoo instance. `ir.config_parameter` is Odoo-standard for global single-value config. New model is overkill.

## Consequences

### Positive

- Marketing previews converted price without running publish; pricing surprises surface at form time.
- Reuses existing FX helpers — zero duplication of conversion math.
- Future per-channel-shop overrides (`P-ENH-ESTY-190`) inherit the `etsy_shop_id` FK for free.
- Rate refresh has a published extension point; adding a provider is a pure-additive slice.

### Negative

- One extra M2O column on `multichannel_listing` table — minor schema cost.
- Backfill from `shop_ref` is best-effort; operators with non-unique shop names see NULL rows requiring manual fixup.
- Non-stored field can't be used in list-view sorting or kanban grouping. If operators ask, a follow-up ADR adds a stored snapshot.

### Neutral

- `_cron_refresh_currency_rates` ships as a no-op. Operators continue manual psql until the provider slice lands. **Not a regression** — this matches today's production behavior.

## Compliance check

| Constraint | Status |
|---|---|
| Standard-Odoo-First | ✅ Reuses `res.currency._convert()`, `res.currency.rate`, `ir.config_parameter`. New cron is custom because CE ships none. |
| ADR-003 (mhc-core boundary) | ✅ FK + computed fields land in etsy_integration via `_inherit`; mhc-core untouched. |
| ADR-013 (etsy.listing read-only) | ✅ This ADR governs `multichannel.listing`, not `etsy.listing`. No write to the channel-side mirror. |
| ADR-014 (per-variant SKU) | ✅ Display is template-level (operator preview at the listing level). Per-variant `price_extra` already reflected in publisher's payload shape. |
| ADR-015 (listing model split) | ✅ Display tier layers ABOVE the source resolution chain. No conflict. |
| Soft-fail pattern | ✅ Matches iter2 publisher behavior. |

## Open questions for the code slice

- Should the WARNING be rate-limited (one per shop per transaction) to avoid log spam on list-view loads? **Provisional answer**: yes — track per-shop seen-set in transaction context. To revisit in Phase 4 review.
- Tooltip text on the Monetary widget — final i18n string. To resolve at view authoring time with the linter's `_()` wrap.
