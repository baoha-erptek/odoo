# Tasks — Spec 013 / P-ENH-ESTY-195 (Listing Currency Display)

Phase numbering follows `.claude/plans/006-implementation-playbook.md` per-slice 9-phase loop. Each task is atomic and Phase-tagged.

## Parent spec-authoring slice (THIS commit)

- [X] T001 Standard-Odoo-First gate — grep CE for `currency_rate_live` / `_run_currency_rate_update` / cron records on `res.currency.rate`. Verdict: CE 19 ships nothing.
- [X] T002 Existing FX surface inventory — `etsy.shop.listing_currency_id` (M2O→res.currency, `etsy_shop.py:102`), `EtsyListingPublisher._convert_to_shop_currency` (`etsy_listing_publisher.py:542`), migration `_19_0_2_34_0/post-migrate.py`.
- [X] T003 ADR scope decision — new ADR-016 (free; only ADR-015 occupies range).
- [X] T004 Listing-to-shop linkage analysis — `multichannel.listing.shop_ref` is Char matched in publisher `_resolve_listing_intent` (`etsy_listing_publisher.py:443`); typed `etsy_shop_id` FK needed for clean compute.
- [X] T005 Write `specs/013-listing-currency-display/spec.md`.
- [X] T006 Write `specs/013-listing-currency-display/tasks.md` (this file).
- [X] T007 Write `specs/013-listing-currency-display/findings.md` skeleton with T001/T002/T003/T004 evidence pre-filled.
- [X] T008 Write `specs/006-master-plan/adrs/ADR-016-listing-currency-display.md`.
- [X] T009 Update tracker row P-ENH-ESTY-195 — link to spec 013 + ADR-016; state stays `todo` (code slice not yet dispatched).
- [X] T010 Conventional commit on `feature/006-master-plan-coding`: `[docs] docs(P-ENH-ESTY-195): author spec 013 + ADR-016 — Wave-3 listing currency display`.

## Child code slice (NEXT `/dispatch-slice` invocation)

Estimated LOC: **~150 LOC** total (50 models, 25 views, 15 data, 60 tests). Model tier: **Sonnet** (default; not trivial enough for Haiku given the migration + soft-fail patterns, not architecturally novel enough for Opus).

### Phase 1 — Plan

- [X] T101 Dispatch `planner` agent (Sonnet) with spec 013 + ADR-016 as input. Output: file-by-file diff outline.

### Phase 2 — RED

- [X] T201 `tests/test_p_enh_esty_195_phase1_db.py` — 4 Phase-1 DB assertions per spec §6.
- [X] T202 `tests/test_p_enh_esty_195_phase2_orm.py` — 8 Phase-2 ORM tests per spec §6.
- [X] T203 Verify all 12 tests RED before any code.

### Phase 3 — GREEN

- [X] T301 Extend `custom_addons/etsy_integration/models/multichannel_listing.py` `_inherit` class:
  - Add `etsy_shop_id` M2O→`etsy.shop`, `ondelete='set null'`, indexed.
  - Add `display_currency_id` Monetary-driver computed field.
  - Add `display_price_in_shop_currency` Monetary computed field with `@api.depends('product_tmpl_id.list_price', 'etsy_shop_id.listing_currency_id')`. SOFT-FAIL → 0.0 + WARNING.
- [X] T302 Extend `custom_addons/etsy_integration/models/etsy_shop.py`:
  - Add `_cron_refresh_currency_rates(self)` method reading `etsy_integration.currency_rate_provider` (default `'manual'`); WARNING + no-op on every non-implemented branch.
- [X] T303 Add view inherit in `custom_addons/etsy_integration/views/multichannel_listing_etsy_views.xml`:
  - Add `etsy_shop_id` widget on existing Etsy tab.
  - Add `display_price_in_shop_currency` Monetary widget (readonly, `widget="monetary"`, options="{'currency_field': 'display_currency_id'}").
  - Tooltip: "Shop currency not configured" when `etsy_shop_id.listing_currency_id` is False.
- [X] T304 Create `custom_addons/etsy_integration/data/ir_cron_currency_rates.xml`:
  - `ir.cron` "Etsy: Refresh Shop Currency Rates", daily 05:00 UTC, calls `model.etsy.shop _cron_refresh_currency_rates`.
- [X] T305 Create `custom_addons/etsy_integration/data/ir_config_parameter_currency.xml` (or extend existing config_parameter file):
  - `etsy_integration.currency_rate_provider` default `'manual'`.
- [X] T306 Add files to `__manifest__.py` `data` list. Bump etsy_integration version `19.0.3.7.0 → 19.0.3.8.0` (point release — no schema break beyond optional new M2O column).
- [X] T307 Migration package `custom_addons/etsy_integration/migrations/19.0.3.8.0/post-migrate.py` + sibling `_19_0_3_8_0/__init__.py` (dotted-version dir trap per `feedback_odoo19_test_gotchas.md` (c)):
  - Backfill `multichannel.listing.etsy_shop_id` from `shop_ref` name-lookup.
  - WARNING per ambiguous/missing match.
- [X] T308 Run tests: all 12 GREEN under `--test-tags /etsy_integration`.

### Phase 4 — Review (parallel)

- [X] T401 `code-reviewer` agent (Sonnet) — single Agent call.
- [X] T402 `security-reviewer` agent (Sonnet) — single Agent call (parallel with T401).
- [X] T403 Apply all CRITICAL/HIGH findings; document accept/decline on MEDIUM/LOW.

### Phase 5 — Verify

- [X] T501 `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exit 0.
- [X] T502 Full suite regression: `--test-tags /etsy_integration` matches baseline 18 fail / 5 error of (704 + 12 new) — zero new regressions.
- [X] T503 Grep new code for `_logger.info(` / `print(` — must return zero hits per project rules.
- [X] T504 Run `ruff check custom_addons/etsy_integration/` — zero new lint hits.

### Phase 6 — Commit

- [X] T601 Single conventional commit on `feature/006-master-plan-coding`:
  `[etsy_integration] feat(P-ENH-ESTY-195): listing currency display widget + rate-refresh cron skeleton`

### Phase 7 — Document

- [X] T701 Update `docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md` §7.5b (new) — "Xem giá quy đổi sang tiền tệ shop".
- [X] T702 Update `docs/owner/UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md` TC-023 (new row).
- [X] T703 Update `.claude/plans/006-master-plan-tracking.md` row P-ENH-ESTY-195: `todo → done`, ship note matching the existing Wave-2 row format.
- [X] T704 Append Phase 3-9 surprises to `specs/013-listing-currency-display/findings.md`.

### Phase 8 — Learn

- [ ] T801 Invoke `/learn` to capture surprises into auto-memory (e.g. `feedback_*` slugs for any new gotcha — soft-fail on `_convert()`, depend-on-related-field rules, etc.). Or explicit "no new patterns" note.

### Phase 9 — Land (staging)

- [ ] T901 `rsync` etsy_integration to staging (`secrets/ssh-key-2023-02-24.key`).
- [ ] T902 `sudo docker exec esty19_odoo odoo -u etsy_integration --stop-after-init` on staging.
- [ ] T903 Container restart healthy. psql confirms `latest_version='19.0.3.8.0'`.
- [ ] T904 Owner pinged via Telegram with re-publish instructions if cosmetic display change should be verified on a real listing.

## Exit criteria check (spec mini-slice — THIS commit)

- [X] Spec authored
- [X] ADR-016 authored
- [X] Tasks file authored
- [X] Findings skeleton authored
- [X] Tracker row updated to point at spec
- [X] Conventional commit lands

## Exit criteria check (child code slice — future commit)

Re-check at Phase 9 of the code slice. List in `spec.md §10`.
