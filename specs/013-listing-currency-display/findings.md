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
| 2 RED | tdd-guide used `product.template.type='product'` (legacy Odoo ≤16 value). Odoo 19 selection is `consu / service / combo` only. 5 Phase-2 tests errored before any field check. | sed-replaced all 7 occurrences to `'consu'`. | Captured in auto-memory item 155 candidate (see `/learn`). |
| 2 RED | tdd-guide created channel via `multichannel.channel` (non-existent) with field `platform` (non-existent). Real model is `multichannel.sales.channel` and mhc ships a `multichannel_hub_core.channel_etsy` ref. | Replaced factory with `env.ref('multichannel_hub_core.channel_etsy')`. | No (project-specific knowledge already in CLAUDE.md for module structure.) |
| 2 RED | tdd-guide used `name=` on multichannel.listing create. Listing has `title` not `name` (no `_rec_name='title'` either — `display_name` is computed). | Replaced `name` → `title`. | No (one-shot fixture noise.) |
| 3 GREEN | Initial discovery shim `from ...post_migrate import post_migrate` imported the submodule (callable to module-not-function), Odoo raised `TypeError: 'module' object is not callable` at upgrade. | Fixed import to `from ...post_migrate import post_migrate` after re-pointing to the post_migrate.py file inside the package. Verified by full -u of etsy_integration. | Worth capturing as item 156 candidate — repeats anytime we shape the underscore-package/dotted-dir pair. |
| 3 GREEN | `nextcall` field in cron XML defaulted to install-time-now (PG local time = UTC+7) instead of 05:00 UTC. Phase-1 test assertion `cron.nextcall.hour == 5` failed (17 != 5). | Switched eval to `DateTime.utcnow().replace(hour=5,...)`. Since data file is `noupdate=1` (preserves operator nextcall tuning), pre-existing stale row had to be deleted via odoo-shell + a clean `-u`. | Worth capturing — `noupdate=1` + nextcall combo trap. |
| 3 GREEN | Odoo silently falls back to **rate=1** when `res.currency.rate` row missing for a non-company target currency. `_convert(amount, …)` returned 0.0 in some cases / passed through amount in others, never raised → SOFT-FAIL WARNING never fired. | Added defensive `res.currency.rate` existence check BEFORE calling `_convert()`. If domain `(currency_id, company_id ∈ [self, ⌀], name <= today)` returns empty → log WARNING + 0.0. | Yes — item 157 candidate: rate-fallback-to-1 is a SILENT mispricing trap. |
| 5 verify | ruff `BLE001` on `except Exception as exc:` in the SOFT-FAIL compute. Intentional broad catch per ADR-016 D4. | Added `# noqa: BLE001 — SOFT-FAIL per ADR-016 D4`. | No (pattern already covered by ADR-016.) |
| 5 verify | Container had stray Odoo test processes (PIDs 106, 9398) holding registry locks; new install hit `ERROR: canceling statement due to lock timeout`. | `kill -9` the stragglers in the namco_odoo19 container, retry succeeded. | Yes — item 158 candidate: long-running CLAUDE.md test commands can orphan in-container processes that block later upgrades; first symptom is opaque `ir_module_module UPDATE … lock timeout`. |
