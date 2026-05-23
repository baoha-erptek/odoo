# Tasks: Central Product Hub (Spec 009)

Dependency-ordered, slice-specific. Five implementation slices. Each runs the MP006 9-phase loop and Two-Phase Testing.

Status legend: `[ ]` todo · `[~]` doing · `[X]` done.

---

## Slice P-HUB-PROD-MODEL — Models + ACL + Seed

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T001 | [X] Finalize `multichannel.sales.channel` + `product.channel.status` + `product.template` extensions in data-model.md | — | plan | Source of truth = data-model.md §1–4 |
| T002 | [X] `models/multichannel_sales_channel.py` + `init()` C-CH-001 raw-SQL UNIQUE mirror | T001 | GREEN | `pg_constraint IF NOT EXISTS` pre-check |
| T003 | [X] `models/product_channel_status.py` + `init()` C-PCS-001 raw-SQL UNIQUE mirror | T001 | GREEN | Same pattern |
| T004 | [X] `models/product_template.py` extensions: 6 fields + `x_unit_margin` compute + `x_sku_v2_*` compute (skips `ba_approved_legacy`) | T002,T003 | GREEN | Stored computed indexed where flagged |
| T005 | [X] `services/sku_grammar_v2.py` — frozen `family_rules` tuple + `evaluate(name) -> (suggested, family_code)` | T001 | GREEN | Tuple regenerated from `A3_grammar_v2_frozen.md §1`; module-load precompile; DSGN registry deferred |
| T006 | [X] `data/multichannel_sales_channel_seed.xml` — 3 channels (etsy active; amazon/website inactive); `noupdate=1` | T002 | GREEN | Admin edits persist |
| T007 | [X] `security/ir.model.access.csv` — 4 rows (read group_user / write group_system on both new models) | T002,T003 | GREEN | ACL mandatory for new models |
| T008 | [X] RED Phase 1 (DB): tables, columns, UNIQUE mirrors enforced, indexes present | T001 | RED | Register file in `tests/__init__.py` |
| T009 | [X] RED Phase 2 (ORM): M2M write, One2many channel-status, `x_unit_margin` recompute, grammar v2 truth table (`matches`/`non_canonical`/`msc_catchall` for representative names), `ba_approved_legacy` not overwritten | T002–T007 | RED | `--http-port=8175` (8170 collided on local; baseline pattern) |
| T010 | [X] GREEN: make T008/T009 pass | T008,T009 | GREEN | 33/33 tests green |
| T011 | [X] Review: code-reviewer + security-reviewer parallel | T010 | Review | 0 CRITICAL/HIGH; 1 MEDIUM (`readonly=False` on `x_sku_v2_status`) accepted — wizard gate lands in P-HUB-SKU-DRIFT |
| T012 | [X] Verify: `-u multichannel_hub_core --stop-after-init` exit 0; `--test-tags` green; ruff not installed locally; grep `_logger.info`/`print(` clean | T011 | Verify | 5 pre-existing baseline errors in test_design_file_upload_wizard_multi (confirmed via stash) — NOT regressions |
| T013 | [X] Commit (conventional, cite T001–T012); tracker P-HUB-PROD-MODEL → done | T012 | Land | |

**Exit (P-HUB-PROD-MODEL)**: all `[X]`; tests ≥ 80 % changed lines; module installs clean; constraints mirrored in `init()`.

---

## Slice P-HUB-WIZARD — Product Creation Wizard

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T014 | [X] `wizards/product_creation_wizard.py` — TransientModel + fields mirror of product.template essentials + `_check_ba_or_raise()` + `action_create()` | P-HUB-PROD-MODEL ✓ | GREEN | FR-017 21st confirmation landed: method-top gate before any side effect; sudo() bounded with inline justification |
| T015 | [X] `wizards/product_creation_wizard_views.xml` — form view with grouped sections (Identity / Pricing / Channels / Production mode preview) | T014 | GREEN | Production mode preview reads `x_gearment_sku` per ADR-010 |
| T016 | [X] RED Phase 1 (DB): wizard tt-model exists, transient | T014 | RED | |
| T017 | [X] RED Phase 2 (ORM): validation gate (empty name/code/categ/price refused), happy path creates template + channel status rows, non-canonical SKU passes through, non-BA AccessError before create | T014,T015 | RED | port `8175` (8170 collided locally) |
| T018 | [X] GREEN | T016,T017 | GREEN | 13/13 GREEN; M2M domain `active=True` filtered amazon during read — test uses a fresh active second channel instead of relying on the seed's inactive amazon |
| T019 | [X] Review: code-reviewer + security-reviewer | T018 | Review | both APPROVED 0 CRITICAL/HIGH |
| T020 | [X] Verify | T019 | Verify | -u clean; full mhc 0 NEW regressions (5 baseline errors in test_design_file_upload_wizard_multi pre-existing); debug grep clean |
| T021 | [X] Commit; tracker → done | T020 | Land | |

---

## Slice P-HUB-SKU-DRIFT — Drift Review + Canonicalisation Wizard

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T022 | `wizards/product_sku_canonicalise_wizard.py` — `action_keep_legacy` + `action_accept_canonical` + service hook `_push_sku_to_channel(product, channel_code)` (no-op fallback in mhc; Etsy implementation in T034 below) | P-HUB-PROD-MODEL ✓ | GREEN | Wizard is mhc; Etsy push hook is etsy_integration |
| T023 | `views/product_sku_drift_views.xml` — tree view filtered to non-canonical statuses + server-action binding | T022 | GREEN | Filterable by `x_sku_v2_status` |
| T024 | `etsy_integration/services/etsy_sku_pusher.py` — implements `_push_sku_to_channel(product, 'etsy')` calling `EtsyApiClient.put('/listings/{id}/inventory')` with entire-array-resubmit using existing `etsy.listing.product` snapshot; rolls back caller transaction on failure with vendor body captured (memory `feedback_capture_response_body_before_blackbox_probe`) | T022, Spec 011 P-PUB-CLIENT ✓ | GREEN | **Depends on Spec 011 P-PUB-CLIENT landing first** |
| T025 | RED Phase 1 (DB): wizards exist, tree view loads, `x_sku_legacy` is settable | T022 | RED | |
| T026 | RED Phase 2 (ORM): Keep-legacy transition; Accept-canonical without Etsy link (no push fires); Accept-canonical with mocked Etsy push success (`default_code` updated, audit row created); Accept-canonical with mocked push failure (rollback, durable audit row remains) | T022,T024 | RED | `--http-port=8170` |
| T027 | GREEN | T025,T026 | GREEN | |
| T028 | Review + Verify + Commit | T027 | Review→Land | |

**Note on inter-spec dep**: T024 depends on Spec 011 P-PUB-CLIENT (Etsy write methods). To preserve slice independence, P-HUB-SKU-DRIFT can land in two checkpoints: (a) mhc wizard + no-op fallback (T022, T023, T025–T028 minus the Etsy push test) lands first; (b) Etsy push hook (T024 + the relevant Phase-2 test cases) lands after Spec 011 P-PUB-CLIENT. Tracker row carries the two-checkpoint plan.

---

## Slice P-HUB-BACKFILL — Etsy Listing Backfill Wizard

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T029 | `etsy_integration/wizards/etsy_listing_backfill_wizard.py` — read `etsy.listing` + `etsy.listing.product`; ensure parent `product.template`; create `product.channel.status` rows; idempotent | P-HUB-PROD-MODEL ✓ | GREEN | Read-only against Etsy API (no outbound) |
| T030 | Unmatched-SKU report view — line-by-line with **Create product** / **Skip — flag Etsy-only** per row | T029 | GREEN | Wizard step 2 |
| T031 | RED Phase 1 (DB): wizard exists, `product.channel.status` row created on backfill | T029 | RED | |
| T032 | RED Phase 2 (ORM): idempotency (run twice = same state, no duplicates, no chatter spam); match-existing-product (parent template found via FK chain); unmatched-SKU + Create-product action creates new template; unmatched-SKU + Skip action flags Etsy-only; never overwrites BA-edited fields | T029 | RED | `--http-port=8170` |
| T033 | GREEN + Review + Verify + Commit | T031,T032 | GREEN→Land | |

---

## Slice P-HUB-STATUS-VIEW — Product Form Channels Tab

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T034 | `views/product_template_views.xml` extension — Channels tab + smart button (count of `state='published'` channel statuses) | P-HUB-PROD-MODEL ✓ | GREEN | Read-only view; state writes are from Spec 011 publisher |
| T035 | RED Phase 1 (DB/view): form loads with the new tab; smart button widget loads | T034 | RED | |
| T036 | RED Phase 2 (ORM): published-count compute matches; navigating into a channel status row shows the channel name + external_ref | T034 | RED | |
| T037 | GREEN + Review + Verify + Commit | T035,T036 | GREEN→Land | |

---

## Dependency Graph

```
P-HUB-SPEC (this planning slice)
    → P-HUB-PROD-MODEL (T001–T013)
        → P-HUB-WIZARD (T014–T021)
        → P-HUB-SKU-DRIFT mhc-half (T022, T023, T025–T028)
        → P-HUB-BACKFILL (T029–T033)
        → P-HUB-STATUS-VIEW (T034–T037)
    P-HUB-SKU-DRIFT etsy-half (T024 + sub-tests)
        ← waits on Spec 011 P-PUB-CLIENT
```

## Notes

- All implementation slices: Two-Phase Testing; coverage ≥ 80 % on changed lines; module installs clean.
- New models MUST ship `ir.model.access.csv` rows; UNIQUE constraints MUST be mirrored in `init()` raw SQL with a `pg_constraint IF NOT EXISTS` pre-check (memory `project_sql_constraints_drift`, 8+ confirmations).
- Wizards MUST guard `action_*` methods with a method-top BA-group check before any side effect (memory `feedback_fr017_write_defense_in_depth`, 20+ confirmations).
- RED gate: orchestrator runs `--test-tags` itself with `--http-port=8170` and reads the failure tail (tdd-guide RED-by-inspection gap; memory `feedback_tdd_guide_init_py_imports`).
- Reviewer findings about diff bloat must be verified with `git diff --stat HEAD` before acting (memory `feedback_reviewer_agent_diff_hallucination`).
