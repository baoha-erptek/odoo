# Spec 013 — Listing Currency Display

**Slice ID**: `P-ENH-ESTY-195`
**Jira**: ESTY-195 (7.7)
**Wave**: 3 (enhancement, post Wave-2 listing-parity)
**Status**: spec authored 2026-06-06; code slice not yet dispatched
**Foundation**: P-BUG-ESTY-188 iter2 (`etsy_integration` 19.0.2.34.0)
**ADR**: ADR-016 (new, this slice)

## 1. Problem

Operators in Marketing see Etsy listing prices in raw USD (Odoo company currency) when previewing a `multichannel.listing`. The Etsy storefront serves the listing in the shop's local currency (e.g. JaHandmadeArt = VND). When Marketing changes `product.template.list_price` or a per-listing override, the on-form preview gives no signal about what number the buyer actually sees on Etsy. This causes silent pricing surprises — owner reported one publish where USD 0.50 mapped to VND 12,700 below Etsy's min-price floor (root-cause of P-BUG-ESTY-188 iter3).

The publisher already converts at payload time via `EtsyListingPublisher._convert_to_shop_currency` (added in P-BUG-ESTY-188 iter2). What's missing is a **read-only display surface on the listing form** so Marketing previews the converted figure WITHOUT running publish.

## 2. Scope

### In scope

- A non-stored Monetary computed field on `multichannel.listing` showing converted price in the shop's listing currency.
- A new `multichannel.listing.etsy_shop_id` M2O→`etsy.shop` (via `_inherit` in `etsy_integration` per ADR-003) so the computed field can resolve the shop without parsing `shop_ref`. Backfilled from `shop_ref` name-lookup on migration.
- A daily `ir.cron` skeleton method `etsy.shop._cron_refresh_currency_rates()` that today logs WARNING ("manual provider — configure currency rate provider") and no-ops. ECB / OpenExchangeRates / Yahoo provider plug-in is **deferred to follow-up slice**.
- A shop-level `ir.config_parameter` `etsy_integration.currency_rate_provider` (default `'manual'`) wired into the cron skeleton.
- Owner docs update + UAT walkthrough row.

### Out of scope

- Provider implementation (ECB fetch, API key handling, retry/backoff). Deferred to follow-up.
- Historical rate tracking on the listing record. Display is always at *current* `res.currency.rate`.
- Currency-rate refresh from inside Etsy's `GET /shops/{id}` response (the migration in P-BUG-ESTY-188 iter2 already reads `currency_code` once at OAuth-bootstrap; this slice doesn't re-poll it).
- Multi-shop aggregate view. Each listing shows ONE shop's converted price (the FK target).
- Editing the displayed converted price. It's readonly; `product.template.list_price` (or per-channel override later in P-ENH-ESTY-190) is canonical.

### Standard-Odoo-First gate

Odoo 19 CE ships **no** `currency_rate_live` module, no rate-refresh `ir.cron`, no ECB/Yahoo provider class. CE base provides `res.currency._convert()` + `res.currency.rate` model only. Verdict: cron scaffolding is custom-but-thin; the conversion math itself reuses `res.currency._convert()`. No new currency model needed (per tracker row).

## 3. User stories

### US1 — Marketing previews converted price

**As** a Marketing user
**I want** to see the listing's price in the Etsy shop's local currency directly on the `multichannel.listing` form
**So that** I can spot pricing errors before clicking Publish.

**Acceptance**:
- Form view shows a readonly Monetary field `display_price_in_shop_currency` near the existing `title`/`product_tmpl_id` block.
- Value = `_convert_to_shop_currency(product_tmpl_id.list_price, etsy_shop_id)` at current rate.
- When `etsy_shop_id.listing_currency_id` is NULL: field returns 0.0 and form shows tooltip "Shop currency not configured" (no crash).
- When current rate is missing for today: returns 0.0 + WARNING logged.

### US2 — Admin configures rate refresh cadence

**As** a system admin
**I want** a daily cron that refreshes shop currency rates against the chosen provider
**So that** display values track market moves without manual psql.

**Acceptance**:
- A new `ir.cron` "Etsy: Refresh Shop Currency Rates" runs daily at 05:00 UTC (offset from existing email-sync cron at 07:00).
- Method body checks `ir.config_parameter etsy_integration.currency_rate_provider`:
  - `'manual'` (default) → log WARNING "Manual currency rate provider — set `etsy_integration.currency_rate_provider` to enable auto-refresh"; return.
  - Any other value → log WARNING "Provider X not yet implemented; manual psql required" (placeholder until follow-up slice).
- Cron does not crash on any provider value.
- Test asserts the WARNING is logged AND no rates are written.

### US3 — Soft-fail when currency unconfigured

**As** a Marketing user opening a listing whose shop has never been OAuth-bootstrapped
**I want** the form to load gracefully instead of erroring
**So that** I can configure the shop currency and reload without losing my work.

**Acceptance**:
- `display_price_in_shop_currency` returns 0.0 when `etsy_shop_id` is False OR `etsy_shop_id.listing_currency_id` is False.
- WARNING logged exactly once per (listing, transaction) — not repeated on each compute re-trigger.
- Form does not raise.

## 4. Design decisions

| Q | Decision | Rationale |
|---|---|---|
| Q1: Does CE 19 ship a rate-refresh cron? | No. | Grep `odoo/addons/` for `currency_rate_live` / `_run_currency_rate_update` / cron records referencing `res.currency.rate` returns zero matches. |
| Q2: Where does the widget live? | `multichannel.listing` form (Marketing surface). | Listing is the Etsy-facing document; Marketing owns RW. ADR-003 respected via `_inherit` in `etsy_integration` (the FK to `etsy.shop` lives in etsy module, not mhc). |
| Q3: New ADR or amend ADR-015? | **New ADR-016**. | Display tier is orthogonal to ADR-015's source-resolution chain. Independent deprecation if Wave-4 reshapes listing model. |
| Q4: Cron scope? | Skeleton + manual-provider WARNING. Provider plug-in deferred. | Keeps Wave-3 velocity. Production currently uses manual psql per P-BUG-ESTY-188 iter2 Phase 9 — no operational regression. |
| Q5: Listing-to-shop linkage? | Add `multichannel.listing.etsy_shop_id` M2O→`etsy.shop` via `_inherit` in etsy_integration. Backfill from `shop_ref` Char by name match. | Existing `shop_ref` is a Char matched in publisher (`_resolve_listing_intent` at `etsy_listing_publisher.py:443`). A typed FK is cleaner for the computed field and for future per-channel-shop overrides (P-ENH-ESTY-190). |

## 5. Field surface

| Field | Module | Type | Notes |
|---|---|---|---|
| `multichannel.listing.etsy_shop_id` | etsy_integration (`_inherit`) | M2O→`etsy.shop`, `ondelete='set null'` | Backfilled from `shop_ref` name-lookup in `_19_0_3_X_0/post-migrate.py`. NULL when no matching shop or backfill ambiguous. |
| `multichannel.listing.display_price_in_shop_currency` | etsy_integration (`_inherit`) | Monetary, computed, non-stored | `@api.depends('product_tmpl_id.list_price', 'etsy_shop_id', 'etsy_shop_id.listing_currency_id')`. SOFT-FAIL → 0.0. |
| `multichannel.listing.display_currency_id` | etsy_integration (`_inherit`) | M2O→`res.currency`, computed, non-stored | Sibling field driving the Monetary widget's currency display. Returns `etsy_shop_id.listing_currency_id` or False. |
| `ir.cron` "Etsy: Refresh Shop Currency Rates" | etsy_integration `data/ir_cron_currency_rates.xml` | XML record | Daily 05:00 UTC, calls `etsy.shop._cron_refresh_currency_rates()`. |
| `ir.config_parameter` `etsy_integration.currency_rate_provider` | etsy_integration `data/` | str, default `'manual'` | Future values: `'ecb'`, `'openexchangerates'`. |

ACL surface unchanged (multichannel.listing already has Marketing RW + BA read-only from P-LIST-MODEL).

## 6. Test plan

Phase-1 DB (`tests/test_p_enh_esty_195_phase1_db.py`):
- New columns `etsy_shop_id` (`int4`) and `display_price_in_shop_currency`/`display_currency_id` do NOT exist in `multichannel_listing` table (non-stored computed fields → no column).
- New column `etsy_shop_id` DOES exist (the M2O IS stored).
- `ir_cron` row "Etsy: Refresh Shop Currency Rates" exists, `interval_number=1`, `interval_type='days'`, `active=True`.
- `ir_config_parameter` row `etsy_integration.currency_rate_provider` defaults to `'manual'`.

Phase-2 ORM (`tests/test_p_enh_esty_195_phase2_orm.py`):
- `test_display_price_computes_for_vnd_shop` — USD 19.99 × rate 25400 → VND 507,746.
- `test_display_price_zero_when_no_shop` — `etsy_shop_id` False → 0.0 + WARNING.
- `test_display_price_zero_when_currency_unset` — `etsy_shop_id.listing_currency_id` False → 0.0 + WARNING.
- `test_display_price_handles_missing_rate` — currency set but `res.currency.rate` row absent → 0.0 + WARNING.
- `test_display_currency_id_matches_shop` — `display_currency_id` equals `etsy_shop_id.listing_currency_id`.
- `test_cron_skeleton_manual_provider_logs_warning` — cron runs, WARNING about "manual provider" logged, zero rates written.
- `test_cron_skeleton_unknown_provider_warns` — `etsy_integration.currency_rate_provider='ecb'` (not implemented) → WARNING + no crash.
- `test_etsy_shop_id_backfilled_from_shop_ref` — migration creates listing with `shop_ref='JaHandmadeArt'` → after migration `etsy_shop_id` points to that shop.

## 7. Migration

`migrations/19.0.3.X.0/post-migrate.py` + sibling `_19_0_3_X_0/__init__.py` package (per memory `feedback_odoo19_test_gotchas.md` (c) on dotted-version dirs):

```python
def post_migrate(cr, env):
    """Backfill multichannel.listing.etsy_shop_id from shop_ref."""
    listings = env['multichannel.listing'].search([
        ('etsy_shop_id', '=', False),
        ('shop_ref', '!=', False),
    ])
    for listing in listings:
        shop = env['etsy.shop'].search([('name', '=', listing.shop_ref)], limit=1)
        if shop:
            listing.etsy_shop_id = shop
        else:
            _logger.warning("Could not backfill etsy_shop_id for listing %s (shop_ref=%s)", listing.id, listing.shop_ref)
```

## 8. Owner docs

- `docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md` §7.5b (new) — "Xem giá quy đổi sang tiền tệ shop" walkthrough.
- `docs/owner/UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md` TC-023 (new row).

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `shop_ref` name-lookup ambiguous (two shops share a display name) | Low | Migration logs WARNING and leaves NULL. Operator can fix via UI. |
| `res.currency._convert()` raises on inactive currency | Low | SOFT-FAIL try/except → 0.0 + WARNING. Test covers. |
| Adding `etsy_shop_id` M2O conflicts with future per-channel-shop M2M for ENH-190 | Medium | Document explicit "one primary shop per listing" rule in ADR-016. ENH-190 can layer an O2M sibling without breaking ENH-195. |
| `display_price_in_shop_currency` recomputes on every form load (no store) | Low | Acceptable — cheap math; no DB round-trip per listing thanks to recordset prefetch of shop + currency. |
| Operators forget to enable VND active flag (P-BUG-ESTY-188 iter2 declined to auto-activate per security review) | Medium | Migration WARNING when `listing_currency_id.active=False`. Tooltip on widget. |

## 10. Exit criteria (machine-checkable, for the code slice)

- [ ] All tasks in `tasks.md` marked `[X]`
- [ ] Phase-1 DB + Phase-2 ORM tests GREEN
- [ ] `--test-tags /etsy_integration` baseline `18 fail / 5 error` preserved (zero new regressions)
- [ ] Module installs cleanly (`-u etsy_integration --stop-after-init` exit 0)
- [ ] `code-reviewer` + `security-reviewer` APPROVE (Phase 4 parallel)
- [ ] Owner docs updated; UAT TC-023 added
- [ ] Tracker row P-ENH-ESTY-195 state flipped `todo → done`
- [ ] Conventional commit on `feature/006-master-plan-coding`
