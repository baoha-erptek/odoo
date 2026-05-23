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
| T022 | [X] (mhc-half) `wizards/product_sku_canonicalise_wizard.py` — `action_keep_legacy` + `action_accept_canonical` + service hook `_push_sku_to_channel(channel_code)` (no-op default on product.template; Etsy override in T024 later) | P-HUB-PROD-MODEL ✓ | GREEN | Bounded sudo() after FR-017 gate; 22nd FR-017 confirmation |
| T023 | [X] `views/product_sku_drift_views.xml` — tree view filtered to non-canonical + msc_catchall + wizard form + server-action binding via binding_model_id | T022 | GREEN | |
| T024 | [X] (checkpoint b) etsy_integration override of `product.template._push_sku_to_channel('etsy')` — routes through `EtsyInventoryPusher.push(self, shop)`; shop derived from `etsy.listing` row backing `product.channel.status.external_ref`; rollback inherited from EtsyApiClient.put 4xx body-capture | T022 ✓, P-PUB-INVENTORY ✓ | GREEN | Landed 2026-05-23. 2 Phase-2 tests (etsy path calls inventory pusher; non-etsy channel is no-op via super()). etsy_integration 19.0.2.11.0 → 19.0.2.12.0. |
| T025 | [X] RED Phase 1 (DB): wizard transient registered + x_sku_legacy settable via SQL | T022 | RED | |
| T026 | [X] (mhc-half) RED Phase 2 (ORM): Keep-legacy transition + status pin against name change; Accept-canonical SKU swap + legacy archive + status recompute to matches; no-channel no-push; with-channel push hook called; rollback on push failure; FR-017 gate blocks non-BA on both actions | T022 | RED | Etsy-push success / failure with real vendor body deferred to T024 |
| T027 | [X] GREEN — 11/11 mhc-half tests | T025,T026 | GREEN | |
| T028 | [X] (mhc-half) Review + Verify + Commit | T027 | Review→Land | code-reviewer + security-reviewer both APPROVED 0 CRITICAL/HIGH; -u clean; full mhc 480 tests 0 NEW failures (5 pre-existing baseline) |

**Note on inter-spec dep**: T024 depends on Spec 011 P-PUB-CLIENT (Etsy write methods). To preserve slice independence, P-HUB-SKU-DRIFT can land in two checkpoints: (a) mhc wizard + no-op fallback (T022, T023, T025–T028 minus the Etsy push test) lands first; (b) Etsy push hook (T024 + the relevant Phase-2 test cases) lands after Spec 011 P-PUB-CLIENT. Tracker row carries the two-checkpoint plan.

---

## Slice P-HUB-BACKFILL — Etsy Listing Backfill Wizard

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T029 | [X] `etsy_integration/wizards/etsy_listing_backfill_wizard.py` — read `etsy.listing` + `etsy.listing.product`; ensure parent `product.template`; create `product.channel.status` rows; idempotent | P-HUB-PROD-MODEL ✓ | GREEN | Read-only against local etsy.listing mirror (no outbound) |
| T030 | [X-partial] Unmatched-SKU surfaced as `unmatched_count` + `unmatched_skus` text on result form | T029 | GREEN | Per-row Create-product / Skip-flag-Etsy-only deferred to follow-up (R-HUB-BACKFILL-1); first JaHandmadeArt pilot has SKU-discovery-matched variants already, so unmatched count is expected 0 |
| T031 | [X] RED Phase 1 (DB): wizard transient registered | T029 | RED | |
| T032 | [X] RED Phase 2 (ORM): matched → channel.status + applicability; idempotency; never overwrites BA-edited applicability; unmatched reported (not auto-created); FR-017 23rd confirmation (non-BA blocked BEFORE any write) | T029 | RED | port `8175` |
| T033 | [X] GREEN + Review + Verify + Commit | T031,T032 | GREEN→Land | security-reviewer flagged HIGH (missing FR-017 test) + 3 MEDIUM (sudo comments) — all addressed inline; 8/8 GREEN; etsy_integration 538 tests 0 NEW failures vs 531 baseline (25 pre-existing) |

---

## Slice P-HUB-STATUS-VIEW — Product Form Channels Tab

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T034 | [X] `views/product_template_views.xml` extension — Channels tab + SKU Drift tab + smart button (count of `state='published'` channel statuses) + `action_open_channel_statuses` (read-only) | P-HUB-PROD-MODEL ✓ | GREEN | Read-only view; state writes are from Spec 011 publisher |
| T035 | [X] RED Phase 1 (DB/view): inheriting view registered + `x_published_channel_count` column exists | T034 | RED | |
| T036 | [X] RED Phase 2 (ORM): count=0 no-status; count excludes draft; count includes published; recompute on state transition | T034 | RED | |
| T037 | [X] GREEN + Verify + Commit | T035,T036 | GREEN→Land | Review skipped per playbook trivial-slice exception (view inherit + 1 stored compute + read-only action; no business logic, no security surface, no new model) — self-review noted in commit body |

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
