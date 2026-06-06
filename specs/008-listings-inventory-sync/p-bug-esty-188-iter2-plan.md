# P-BUG-ESTY-188 Iteration 2 — Currency Conversion Implementation Plan

**Slice**: `P-BUG-ESTY-188-iter2` (Sub-phase 3h, Wave 1, continuation)
**Jira**: ESTY-188 (6.11b — "Lỗi Bug ko publish listing lên Etsy được")
**Branch**: `feature/006-master-plan-coding`
**Planner**: opus (planner agent, 2026-06-05)
**Manifest bump**: `19.0.2.33.0 → 19.0.2.34.0`
**Status**: Phase 0 — Planning. Owner approved Option A (currency-convert at publisher boundary) per `findings.md` "Phase 9 follow-up part 2" section.

---

## Root cause (confirmed via staging 400 body)

Iteration 1 (`297fc717b04`, `19.0.2.33.0`) shipped defensive `default_readiness_state_id` bootstrap after psql discovery on staging showed the field was already populated on JaHandmadeArt. The 400 persisted because the actual cause is different.

**Captured 400 body on staging (2026-06-03, three identical reproductions 09:07/09:11/09:17)**:

```json
[{"path":"/price","type":"price_too_low","message":"must be above min price ₫5,040 VND","transformed":false}]
```

**Root cause**: outbound currency mismatch at publisher boundary.

- Odoo company currency: **USD**
- Etsy shop JaHandmadeArt listing currency: **VND** (per error; verified via `GET /shops/{id}` audit returning `price=250000/1 VND` on the one surviving prior-success listing)
- `etsy_listing_publisher.py:221` (createListing) and `:379` (push_inventory) emit `'price': float(s.list_price or 0.0)` with **zero** currency conversion
- Recursive grep of `services/` for `currency|_convert|to_currency` returns ZERO outbound conversion sites (inbound order receipts only)
- `etsy.shop` model has NO field to cache the shop's listing currency

Failed publishes carry USD-shaped list_prices (12.99, 19.99, 0.00). The earlier UAT batch succeeded only because its `list_price=250000` happened to be VND-shaped, passing the threshold by accident.

---

## Fix scope (Standard-Odoo-First, owner approved)

Option A from the candidate matrix: currency-convert at the publisher boundary using standard `res.currency._convert`.

| Change | File | What | Why |
|---|---|---|---|
| New field | `models/etsy_shop.py` | `listing_currency_id = fields.Many2one('res.currency', ...)` (view-level system-group, NOT field-level — memory entry 151) | Store Etsy shop's listing currency for outbound conversion |
| Bootstrap on OAuth callback | `services/etsy_oauth.py` (grep `_validate_scope_grant` or token-exchange completion) | After token grant: `GET /users/me` → discover `shop_id` → `GET /shops/{shop_id}` and map `currency_code` to `res.currency` | First-time setup |
| Migration `19.0.2.34.0` | new `migrations/19.0.2.34.0/post-migrate.py` + new `migrations/_19_0_2_34_0/__init__.py` | For each shop where `active_source='api'` AND `listing_currency_id IS NULL` AND `etsy_api_shop_id IS NOT NULL`, call `GET /shops/{id}`, write currency. Per-shop try/except + WARNING. Mirror exactly the `_19_0_2_33_0` pattern. | Backfill existing shops |
| Publisher conversion site 1 | `services/etsy_listing_publisher.py:221` | Replace `'price': float(s.list_price or 0.0)` with `'price': self._convert_to_shop_currency(s.list_price, sh)` (sh = shop.sudo(), already in scope) | The actual fix for createListing |
| Publisher conversion site 2 | `services/etsy_listing_publisher.py:379` | Replace `price = float(t.list_price or 0.0)` with `price = self._convert_to_shop_currency(t.list_price, shop)` | Inventory offerings carry same price |
| Helper method | `services/etsy_listing_publisher.py` (new in class) | `_convert_to_shop_currency(amount, shop)` — see signature below | Encapsulate conversion |
| Defensive validation | `_check_shop_defaults` in publisher | Add `if not shop.listing_currency_id: raise ValueError(...)` | Fail early with explicit message |
| Manifest | `__manifest__.py` | Bump version to `19.0.2.34.0` | Standard pattern |

---

## Helper method signature

```python
def _convert_to_shop_currency(self, amount, shop):
    """Convert amount from company currency to shop listing currency.

    Raises ValueError if shop.listing_currency_id is NULL (defensive — prevents
    silent USD-as-VND mis-emission that caused P-BUG-ESTY-188).
    """
    if not shop.listing_currency_id:
        raise ValueError(
            f"Shop '{shop.name}' (id={shop.id}) missing listing_currency_id. "
            f"Cannot convert price. Use Etsy OAuth callback to auto-discover."
        )
    company = self.env.company
    if shop.listing_currency_id == company.currency_id:
        return float(amount or 0.0)
    converted = company.currency_id._convert(
        amount or 0.0,
        shop.listing_currency_id,
        company,
        fields.Date.context_today(self),
    )
    return float(converted)
```

---

## Field definition (etsy_shop.py)

Add after the existing `default_readiness_state_id` block (~lines 95–101):

```python
listing_currency_id = fields.Many2one(
    'res.currency',
    string='Etsy Listing Currency',
    help='Etsy shop listing currency (e.g., VND, USD). Discovered via '
         'GET /shops/{shop_id}; used to convert outbound listing prices '
         'from company currency. Required for price emission to Etsy.',
    ondelete='restrict',
)
```

- NO `groups=` on the field (would block publisher sudo reads per memory entry 151).
- NOT `required=True` — existing shops have NULL until migration writes the value.
- View-level `groups="base.group_system"` to be added on the form view XML if owner wants admin-only edit; deferred (not blocking the bug fix).

---

## Migration directory structure

```
migrations/
  __init__.py                      (already exists from iter1)
  _19_0_2_33_0/                    (already exists from iter1)
  19.0.2.33.0/                     (already exists from iter1)
  _19_0_2_34_0/__init__.py         NEW — testable Python package
  19.0.2.34.0/post-migrate.py      NEW — Odoo discovery shim
```

### `_19_0_2_34_0/__init__.py` (testable entry point)

Mirror `_19_0_2_33_0/__init__.py`. Key shape:

```python
def post_migrate(cr, env):
    shops = env["etsy.shop"].sudo().search([
        ("active_source", "=", "api"),
        ("listing_currency_id", "in", (False, None)),
    ])
    if not shops:
        return
    from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient
    for shop in shops:
        if not shop.etsy_api_shop_id:
            _logger.warning(...); continue
        try:
            client = EtsyApiClient(shop)
            shop_data = client.get("/shops/%s" % shop.etsy_api_shop_id)
        except Exception as exc:
            _logger.warning(...); continue
        currency_code = shop_data.get("currency_code")
        if not currency_code:
            _logger.warning(...); continue
        currency = env["res.currency"].sudo().search([("name", "=", currency_code)], limit=1)
        if not currency:
            _logger.warning(...); continue
        shop.sudo().write({"listing_currency_id": currency.id})
        _logger.info("bootstrapped shop=%s currency=%s", shop.id, currency_code)
```

### `19.0.2.34.0/post-migrate.py` (Odoo discovery shim)

```python
def post_migrate(cr, env):
    from odoo.addons.etsy_integration.migrations._19_0_2_34_0 import post_migrate
    return post_migrate(cr, env)
```

---

## Two-phase test plan

### Phase 1 — DB verification (`tests/test_p_bug_esty_188_phase1_db_iter2.py`)

1. `test_listing_currency_id_column_exists` — `information_schema.columns` lookup
2. `test_listing_currency_id_fk_constraint_exists` — FK to `res_currency(id)` exists
3. `test_migration_19_0_2_34_0_files_exist` — both dotted dir and underscored package present

### Phase 2 — ORM unit tests (`tests/test_p_bug_esty_188_phase2_orm_iter2.py`)

Mock pattern: seed `res.currency.rate` rows (don't monkeypatch `_convert` directly); mock the whole `EtsyApiClient` class (not just `.get`) per iter1 memory.

1. `test_payload_price_converted_when_shop_currency_differs` — USD company, VND shop, rate 25,000; `list_price=12.99` → `payload['price'] == 12.99 × 25000 = 324750.0` (`assertAlmostEqual`, delta=0.01)
2. `test_payload_price_unchanged_when_currencies_equal` — both USD; `list_price=12.99` → `payload['price'] == 12.99`
3. `test_payload_price_raises_when_listing_currency_null` — `shop.listing_currency_id=False`; assert `ValueError` with "listing_currency_id" in message
4. `test_push_inventory_offering_price_converted` — same conversion at line 379
5. `test_bootstrap_currency_from_get_shops_discovers_currency_code` — mock `client.get` returns `{'currency_code': 'VND', ...}`; assert `shop.listing_currency_id.name == 'VND'`
6. `test_bootstrap_skips_unknown_currency_code` — mock returns `{'currency_code': 'XXX'}`; assert WARNING + shop currency stays NULL
7. `test_bootstrap_handles_per_shop_api_failure` — first shop's `client.get` raises, second succeeds; assert second is bootstrapped
8. `test_post_migrate_iter2_idempotent` — shop with field already set; assert no API call made
9. `test_post_migrate_iter2_skips_email_only_shops` — `active_source='email'`; assert no API call
10. `test_post_migrate_iter2_skips_shops_without_etsy_api_shop_id` — active_source='api' but no shop_id; assert WARNING

Register both files in `tests/__init__.py` (tdd-guide forgets this — memory entry).

### RED-quality discipline

Per memory entries 147–154: confirm each test fails with the EXPECTED error before GREEN. Run the suite with `--http-port=8170` (memory entry 134). Inspect failure tail; do NOT accept "passed for the wrong reason".

---

## Risk register

| Risk | P | I | Mitigation |
|---|---|---|---|
| `_convert` raises `UserError` if no rate configured | Medium | High | RED tests seed rate; defensive check + clear error |
| Etsy `currency_code` absent/malformed in response | Low | Medium | Migration WARNINGs + skips; field stays NULL; publisher raises on next attempt |
| `currency_code` has no matching res.currency row (e.g., 'XXX') | Low | Medium | WARNING; admin must add manually (don't auto-create currency) |
| `EtsyApiClient.__init__` raises before `.get` is called | Medium | Low | Mock the whole class (iter1 lesson) |
| Field-level `groups='base.group_system'` blocks publisher sudo reads | High | High | Do NOT use field-level groups; view-level only (memory 151) |
| Currency conversion silently produces 0 if `_convert` failure swallowed | Low | High | Use `_convert` (raises on rate miss) not a try/except fallback |

---

## Standard-Odoo-First gate

ONE new field on EXISTING model (`etsy.shop.listing_currency_id`). Per `feedback_standard_odoo_first.md` this requires owner approval — **captured** in `findings.md` "Phase 9 follow-up part 2" section (Option A picked via AskUserQuestion 2026-06-05). Implementation uses standard `res.currency._convert` (Odoo CE base, no Enterprise dep).

---

## Exit criteria (machine-checkable)

1. All 3 Phase-1 + 8–10 Phase-2 tests pass
2. `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exit 0
3. Full `--test-tags /etsy_integration --http-port=8170` matches iter1 baseline (18 fail / 5 error / ~687 total); zero new regressions
4. `code-reviewer` + `security-reviewer` APPROVE in parallel at Phase 4 (no CRITICAL/HIGH)
5. Tracker `state` flipped `doing → done` ONLY after staging publish returns 201
6. `findings.md` gets a "Phase 9 iter2" entry with deploy outcome + actual 201 from createListing
7. No `print()`; no `_logger.info()` for debug — use `_logger.debug()` / `_logger.warning()`

---

## Gotcha cheatsheet (memory-derived)

1. Field-level `groups=` blocks sudo reads → view-level only (151).
2. Mock whole `EtsyApiClient` class, not just `.get` (iter1).
3. `_convert` raises `UserError` if no rate — seed rate row in fixture.
4. Register new test files in `tests/__init__.py` (tdd-guide forgets).
5. Run tests with `--http-port=8170` to avoid 8169 collision (134).
6. Dotted migration dir not valid Python identifier — pair with underscored sibling (iter1 gotcha c).
7. Odoo 19 recordset has no `.refresh()` — use `.invalidate_recordset()` (iter1 gotcha a).

---

## Summary

Adds `etsy.shop.listing_currency_id` + bootstrap migration + helper-method conversion at two publisher sites, fixing the systemic gap that allowed USD prices to be mis-emitted as VND on JaHandmadeArt. Standard Odoo `res.currency._convert` only; no Enterprise; owner-approved. ~120 LOC + 2 migration files + 10 tests. Manifest `19.0.2.33.0 → 19.0.2.34.0`. Exit only after staging publish returns 201.
