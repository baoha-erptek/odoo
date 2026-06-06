# Findings — Spec 013 / P-ENH-ESTY-195

## Step 1 — Standard-Odoo-First gate (T001)

**Question**: Does Odoo 19 CE ship a built-in `res.currency.rate` refresh cron?

**Verdict**: NO.

**Evidence**:
- `odoo/addons/account/__manifest__.py` lists no `currency_rate_live`-style module.
- `odoo/addons/base/models/res_currency.py:280` defines `_convert()` ORM helper but ships no cron scaffolding for auto-refresh.
- `grep -rn 'ir\.cron.*currency\|currency.*rate.*cron' odoo/addons/` returns zero matches.
- `currency_rate_live` is an Enterprise / OCA module, not part of CE base.

**Implication**: This slice must add cron scaffolding. Decision (per spec §4 Q4): land a no-op skeleton driven by `ir.config_parameter etsy_integration.currency_rate_provider` (default `'manual'`); defer ECB/OpenExchangeRates provider implementation to a follow-up slice.

## Step 2 — Existing FX surface inventory (T002)

Foundation shipped by P-BUG-ESTY-188 iter2 (commit `d660afd7c4b`, etsy_integration `19.0.2.34.0`):

| Surface | Location | Notes |
|---|---|---|
| `etsy.shop.listing_currency_id` | `custom_addons/etsy_integration/models/etsy_shop.py:102` | M2O→`res.currency`, system-group, indexed. Backfilled from Etsy `GET /shops/{id}` `currency_code` at OAuth-bootstrap. |
| `EtsyListingPublisher._convert_to_shop_currency(amount, shop)` | `custom_addons/etsy_integration/services/etsy_listing_publisher.py:542` | Wraps `res.currency._convert()`. SOFT-FAIL → returns `amount` unchanged + WARNING when `listing_currency_id` is NULL. |
| Migration `_19_0_2_34_0/post-migrate.py` | `custom_addons/etsy_integration/migrations/_19_0_2_34_0/__init__.py` | Per-shop GET → write `listing_currency_id`. Idempotent. |
| Production proof | JaHandmadeArt (id=10) → `listing_currency_id=23` (VND) | USD 19.99 × rate 25400 → VND 507,746 verified on staging 2026-06-06. |

This slice **builds on top** of all four — it does not duplicate the conversion helper, doesn't re-poll Etsy for currency, doesn't reimplement bootstrap.

## Step 3 — ADR scope decision (T003)

**Verdict**: NEW ADR-016.

**Evidence**:
- `ls specs/006-master-plan/adrs/` shows `ADR-015-listing-model-split.md` as the highest-numbered ADR. ADR-016 is free per memory `feedback_adr_number_collision.md`.
- ADR-015 §3 (3-tier source resolution chain) is **orthogonal** to display: ADR-015 says where prices come from; ADR-016 will say how prices are *shown* on the listing form.
- Independent ADR enables independent deprecation if Wave-4 reshapes the listing model.

## Step 4 — Listing-to-shop linkage gap (T004)

`multichannel.listing` has NO typed FK to `etsy.shop`. It carries only:

| Field | Type | Use |
|---|---|---|
| `shop_ref` | `fields.Char` | Free-form shop name. Publisher matches via name equality at `etsy_listing_publisher.py:443` (`('shop_ref', '=', shop_name)`). |

**Implication**: A typed `multichannel.listing.etsy_shop_id` M2O is required for the computed-field `@api.depends` chain to work cleanly. Adding the FK via `_inherit` in etsy_integration respects ADR-003 (mhc-core never imports etsy module). Migration backfills the M2O from `shop_ref` via name-lookup. NULL when no match — operator fixes via UI; WARNING logged.

Side benefit: ENH-190 (per-channel marketing overrides) will need the same linkage; this slice clears the path.

## Step 5–9 — Implementation surprises

*Empty. Populated during Phase 2–9 of the code slice.*

| Phase | Surprise | Resolution | Memory? |
|---|---|---|---|
| — | — | — | — |
