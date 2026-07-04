# Plan — Spec 013 / P-ENH-ESTY-195 (Listing Currency Display) — code slice

**Authored by**: orchestrator (planner agent has no Write tool per `feedback_planner_agent_no_write.md`)
**Inputs**: `spec.md`, `tasks.md` T101–T904, `findings.md` Steps 1–4, `ADR-016`
**Tier**: Sonnet (in-spec, ~150–320 LOC, no architectural novelty)
**Branch**: `feature/006-master-plan-coding`

## 1. File-by-file diff outline

| File | Change shape | ~LOC | Notes |
|---|---|---|---|
| `custom_addons/etsy_integration/models/multichannel_listing.py` | `_inherit` extension of existing class at line 11 | +30 | Add `etsy_shop_id`, `display_currency_id`, `display_price_in_shop_currency`. Existing class already has `attribute_mapping` O2M etc. — add fields below existing field block; SOFT-FAIL compute inline (do NOT call publisher service). |
| `custom_addons/etsy_integration/models/etsy_shop.py` | Method addition on existing `etsy.shop` class (already holds `listing_currency_id` at line 102 per findings) | +25 | New `_cron_refresh_currency_rates(self)`. Reads `self.env['ir.config_parameter'].sudo().get_param('etsy_integration.currency_rate_provider', 'manual')`. Manual → WARNING + return; other → WARNING placeholder + return. Never raises. |
| `custom_addons/etsy_integration/views/multichannel_listing_etsy_views.xml` | View inherit extension (existing file already extends mhc form) | +15 | Add `etsy_shop_id` + `display_price_in_shop_currency` (monetary widget, `options="{'currency_field': 'display_currency_id'}"`) + invisible `display_currency_id`. Tooltip via `help=` attr; readonly. |
| `custom_addons/etsy_integration/data/ir_cron_currency_rates.xml` | NEW file | +18 | `<record id="ir_cron_etsy_refresh_currency_rates" model="ir.cron">` daily 05:00 UTC, `model_id` → `etsy.shop`, `state='code'`, `code='model._cron_refresh_currency_rates()'`. |
| `custom_addons/etsy_integration/data/ir_config_parameter_currency.xml` | NEW file | +8 | One `<record model="ir.config_parameter">` row: key `etsy_integration.currency_rate_provider`, value `manual`. |
| `custom_addons/etsy_integration/__manifest__.py` | Version bump + data list extension | +2 | `19.0.3.7.0 → 19.0.3.8.0`; add two new data file paths. |
| `custom_addons/etsy_integration/migrations/_19_0_3_8_0/__init__.py` | NEW package | +1 | `from . import post_migrate` (underscore form per memory item c). |
| `custom_addons/etsy_integration/migrations/_19_0_3_8_0/post_migrate.py` | NEW | +35 | Backfill `multichannel.listing.etsy_shop_id` via `shop_ref` name-lookup. WARNING on ambiguous/missing. |
| `custom_addons/etsy_integration/migrations/19.0.3.8.0/post-migrate.py` | NEW shim (Odoo's actual discovery target — dotted dir) | +3 | One-line `from odoo.addons.etsy_integration.migrations._19_0_3_8_0.post_migrate import migrate` (or copy the migrate def directly; check existing `19.0.2.34.0/post-migrate.py` for shape). |
| `custom_addons/etsy_integration/tests/test_p_enh_esty_195_phase1_db.py` | NEW | +50 | 4 DB assertions per spec §6. `@tagged('post_install', '-at_install')` — needs ir_cron row written by data file. |
| `custom_addons/etsy_integration/tests/test_p_enh_esty_195_phase2_orm.py` | NEW | +150 | 8 ORM cases. `@tagged('post_install', '-at_install')` — relies on seeded shops + cron + config_parameter. |

**Total estimate**: ~340 LOC (matches planner's ~320; original tasks.md said ~150 but spec §5 scope grew to include the migration package + the cron + the config_parameter file). Document the LOC delta in commit body — no scope change, just more accurate accounting.

## 2. Phase 2 RED test scaffolding

### `tests/test_p_enh_esty_195_phase1_db.py`

```python
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPEnhEsty195Phase1DB(TransactionCase):
    def test_etsy_shop_id_column_exists(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'multichannel_listing' AND column_name = 'etsy_shop_id'
        """)
        self.assertEqual(self.env.cr.fetchone()[0], 'etsy_shop_id')

    def test_display_columns_are_not_stored(self):
        # Non-stored computed fields → no physical column
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'multichannel_listing'
              AND column_name IN ('display_price_in_shop_currency', 'display_currency_id')
        """)
        self.assertEqual(self.env.cr.fetchall(), [])

    def test_cron_record_exists(self):
        cron = self.env.ref('etsy_integration.ir_cron_etsy_refresh_currency_rates')
        self.assertEqual(cron.interval_number, 1)
        self.assertEqual(cron.interval_type, 'days')
        self.assertTrue(cron.active)

    def test_config_parameter_default_manual(self):
        val = self.env['ir.config_parameter'].sudo().get_param('etsy_integration.currency_rate_provider')
        self.assertEqual(val, 'manual')
```

### `tests/test_p_enh_esty_195_phase2_orm.py`

Decorator: `@tagged('post_install', '-at_install')` — these tests touch newly seeded ir.cron + config_parameter from data files, which only exist after the module's data layer has loaded. Phase-1 baseline (`feedback_odoo19_test_gotchas.md` item 153) confirms this is the safe default.

8 cases mirroring spec §6 bullet list. Each test creates the minimum shop + listing fixture; `assertLogs(level='WARNING')` for SOFT-FAIL cases (memory item 148: Odoo runtime logger uses WARNING not INFO).

```python
# Sketch:
def test_display_price_computes_for_vnd_shop(self):
    # rate USD→VND = 25400; list_price 19.99 → 507,746
    ...
def test_display_price_zero_when_no_shop(self):
    with self.assertLogs(level='WARNING') as cm:
        self.assertEqual(listing.display_price_in_shop_currency, 0.0)
    self.assertTrue(any('shop not configured' in m for m in cm.output))
# ... 6 more cases ...
```

## 3. Phase 3 GREEN dispatch order

Land in this order to avoid the "migration backfills a column that doesn't exist yet" trap:

1. **Model changes first** (`multichannel_listing.py`, `etsy_shop.py`) — field declarations create the DB column on `-u`.
2. **Data files** (`ir_cron_currency_rates.xml`, `ir_config_parameter_currency.xml`) — seed the cron + config param. Phase-1 DB tests 3 & 4 GREEN here.
3. **View** (`multichannel_listing_etsy_views.xml`) — Marketing-facing surface. Tests don't probe view XML directly, but the install regression check (Phase 5 T501) catches XML syntax errors.
4. **Manifest bump** (`__manifest__.py`) — wires the 2 new data files + bumps version so the migration package fires on `-u`.
5. **Migration package** (`_19_0_3_8_0/__init__.py` + `19.0.3.8.0/post-migrate.py`) — backfills `etsy_shop_id` from `shop_ref`. Phase-2 ORM test 8 `test_etsy_shop_id_backfilled_from_shop_ref` GREEN here.
6. **Run tests** — all 12 GREEN.

## 4. Risks discovered during planning

| Risk | Source | Handling |
|---|---|---|
| **Publisher's `_convert_to_shop_currency` raises UserError on missing rate** (verified at `etsy_listing_publisher.py:542+`) | Direct read of source | Computed field must NOT call publisher. Inline `try: company.currency_id._convert(...) except Exception: WARNING + return 0.0`. SOFT-FAIL semantics differ from publisher's hard-fail. |
| **Migration dotted-dir vs underscore-package trap** (`feedback_odoo19_test_gotchas.md` item c) | Memory | Two artifacts: underscore-package `_19_0_3_8_0/` for stable Python import + dotted-dir `19.0.3.8.0/post-migrate.py` for Odoo's discovery. Mirror existing `_19_0_2_34_0/` + `19.0.2.34.0/` pair. |
| **`multichannel.listing` already `_inherit`ed in etsy_integration** | `grep -n class` in models/multichannel_listing.py:11 | Extend the existing class block; do NOT create a second `_inherit` (Odoo merges but it's noisy). New fields slot under existing `attribute_mapping` declaration. |
| **`shop_ref` Char ambiguity** (spec §9) | Spec Risk-1 | Migration name-lookup with `limit=1`; WARNING on no-match. Does NOT fail the migration. |
| **WARNING repetition per compute re-trigger** (spec US3 acceptance) | Spec acceptance | Use a class-level set or env context flag to dedupe per (listing.id, transaction). Simplest: log once per recordset via `_origin` check; alternative is unconditional log + accept noise. Recommend unconditional log for spec correctness — operators care about the signal, not the volume. Note in commit body. |
| **`display_currency_id` driving Monetary widget** | Odoo Monetary convention | Field must be M2O→`res.currency`, non-stored computed. Returns `etsy_shop_id.listing_currency_id` or False. View references it via `options="{'currency_field': 'display_currency_id'}"`. |
| **LOC under-estimate in tasks.md** | Diff outline above | Note ~340 actual vs ~150 estimated. Not a scope change — just accounting (the migration + cron + config_parameter were under-counted). Mention in commit body so reviewer doesn't think we scope-crept. |
| **Cron WARNING is "outbound-gating Boolean" false positive** (`feedback_odoo19_test_gotchas.md` item 151) | Memory | Item 151 applies to fail-open outbound emission. Our cron's WARNING-only manual default does NOT emit data — it explicitly NO-OPs. Flag this in plan to forestall security-reviewer concern. |

## 5. Exit-criteria pre-flight (spec §10)

| # | Check | Phase | Delivered by |
|---|---|---|---|
| 1 | All tasks in `tasks.md` `[X]` | Phase 7 | Manual checklist tick on update |
| 2 | Phase-1 DB + Phase-2 ORM tests GREEN | Phase 3 T308 | `--test-tags /etsy_integration` run |
| 3 | `--test-tags /etsy_integration` baseline `18 fail / 5 error` preserved | Phase 5 T502 | Full suite run, compare counts |
| 4 | Module installs cleanly | Phase 5 T501 | `-u etsy_integration --stop-after-init` exit 0 |
| 5 | code-reviewer + security-reviewer APPROVE | Phase 4 | Parallel dispatch in single message |
| 6 | Owner docs + UAT TC-023 | Phase 7 T701/T702 | HUONG_DAN §7.5b + UAT TC-023 |
| 7 | Tracker row P-ENH-ESTY-195 `todo → done` | Phase 7 T703 | Edit `.claude/plans/006-master-plan-tracking.md` |
| 8 | Conventional commit on `feature/006-master-plan-coding` | Phase 6 T601 | Single commit, body cites slice ID + LOC delta note |

## 6. Agent dispatch sequence

```
Phase 2 (RED)  → tdd-guide (Sonnet)
Phase 3 (GREEN) → orchestrator inline (no agent — tight loop with the tests)
Phase 4 (review) → code-reviewer + security-reviewer (Sonnet, PARALLEL single-message)
Phase 5 (verify) → orchestrator inline (Bash for odoo + ruff + grep)
Phase 6 (commit) → orchestrator inline
Phase 7 (docs)  → doc-updater (Haiku — owner docs are mechanical edits)
Phase 8 (learn) → /learn skill
Phase 9 (deploy) → orchestrator inline (rsync + ssh)
```

**Hand-off note**: The Phase-3 inline loop is justified because the test scaffold is small (12 cases) and the GREEN order is deterministic (1-6 above). Spawning a tdd-guide for Phase 3 would just round-trip context for no benefit. The Phase-2 RED tdd-guide is justified because writing the test fixtures (especially the rate-table seeding for `test_display_price_computes_for_vnd_shop`) benefits from tdd-guide's `assertLogs` / `TransactionCase` patterns.
