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

## Slice P-HUB-SKU-BUILDER — Multi-step v2.1 SKU Builder Wizard + Managed Taxonomy

Added 2026-05-26 per v2.1 amendment (D7 in MP006 tracker) + Decisions D-V2-3 / D-V2-4 / D-V2-6 (DECIDED 2026-05-26, see `docs/owner/SKU_GRAMMAR.md` §12).

This slice has two intertwined deliverables:
1. **Managed taxonomy layer** (`mhc.sku.family` + `product.attribute.value` inherit + seeds) — replaces the frozen Python tuple in `services/sku_grammar_v2.py` with DB-managed CRUD per SKU_GRAMMAR §2.5.
2. **`product.sku.builder.wizard`** — 4-step BA-facing wizard that consumes the taxonomy layer and creates a `product.template` with a canonical v2.1 SKU.

Coexists with `product.creation.wizard` for one sprint (D-V2-3); legacy sunsets in a follow-up slice. ~250 LOC (≈ 100 data layer + 150 wizard).

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T038 | [X] `models/sku_family.py` — `mhc.sku.family` Model (code Char(3) UNIQUE+indexed, name, priority Integer, regex_pattern Char, default_route Selection, default_material_id Many2one `product.attribute.value`, active) + `init()` raw-SQL UNIQUE mirror on `code` with `pg_constraint IF NOT EXISTS` pre-check (C-SKU-FAM-001) | P-HUB-PROD-MODEL ✓ | GREEN | Follow `project_sql_constraints_drift` template from `design_file.py`. `_order = 'priority, code'`. `default_material_id` domain via context — values where `attribute_id.name = 'Material'`. |
| T039 | [X] `models/product_attribute_value.py` — inherit `product.attribute.value` and add `x_code` Char(6) indexed, `x_namespace` Selection [shape/dim/rect/fluid_oz/apparel] (nullable), `x_applicable_family_ids` Many2many `mhc.sku.family` (nullable) | T038 | GREEN | Additive only; no constraint changes on stock model. `x_namespace` + `x_applicable_family_ids` populated only for Size-family attribute values. |
| T040 | [X] `data/sku_family_seed.xml` (`noupdate=1`) — 22 family rows from SKU_GRAMMAR §2 table verbatim (RDS … WDS), priorities 1–22 | T038 | GREEN | Seed only; admin edits in UI persist. Patterns identical to current frozen tuple. |
| T041 | [X] `data/sku_attribute_seed.xml` (`noupdate=1`) — 7 `product.attribute` rows (Family-tag, Material, Shape, Size, Fluid oz, Apparel size, Color) + ~55 `product.attribute.value` rows with `x_code` populated per SKU_GRAMMAR §3/§4/§5. Size values carry `x_namespace` + `x_applicable_family_ids` xml-id refs. | T038,T039 | GREEN | Family-tag `create_variant='no_variant'`; Material/Shape/Size/Fluid oz/Apparel size `create_variant='always'`; Color `create_variant='dynamic'`. |
| T042 | [X] `security/ir.model.access.csv` — 3 new rows for `mhc.sku.family` (read group_user / write group_ba_user / write group_system); no new rows needed for `product.attribute.value` (stock ACL applies; `x_code` writable when value is writable) | T038 | GREEN | BA-writable per `feedback_channel_agnostic_groups_in_mhc.md` — taxonomy is operational, not engineering. |
| T043 | [X] Refactor `services/sku_grammar_v2.py` — `evaluate(name, env)` reads `mhc.sku.family` ordered by priority, compiles regex lazily, falls back to `('MSC','MSC')`. Per-cursor compiled-regex cache keyed by `(family.id, family.write_date.timestamp())`. Update all call sites in `product_template.py` (`x_sku_v2_*` computes) to pass `env`. | T038,T040 | GREEN | Keep `FAMILY_RULES` tuple as **commented seed reference**, NOT runtime source. evaluate() signature change is breaking — grep `evaluate(` repo-wide and adjust. |
| T044 | [X] `views/sku_family_views.xml` — list view (code / name / priority / default_route / default_material_id / active toggle) + form view (notebook with Identity tab + Regex tab + Defaults tab) + `ir.actions.act_window` + menu under Settings → SKU → Families | T038 | GREEN | Form has live "Test pattern" widget? — defer; just plain Char input on regex_pattern this slice. |
| T045 | [X] `wizards/product_sku_builder_wizard.py` — TransientModel `product.sku.builder.wizard` with `_check_ba_or_raise()` method-top gate (24th FR-017 confirmation expected). Fields: `step` Selection [1/2/3/4], `product_name` Char, `family_id` M2O `mhc.sku.family`, `family_id_auto` M2O (read-only — what evaluate() suggested), `material_id` M2O `product.attribute.value` (Material domain), `size_id` M2O `product.attribute.value` (family-gated via x_applicable_family_ids), `rect_w` / `rect_h` Integer (for rectangular sizes), `var2_color_id` M2O `product.attribute.value` (Color domain, optional), `preview_sku` Char compute. Action methods: `action_next()` (step++ with per-step validation), `action_prev()`, `action_create()` (FR-017 gate → builds default_code from segments → invokes existing `product.creation.wizard` create path via bounded `.sudo()`). | T038–T044 | GREEN | D-V2-3 coexist: builder produces same product.template as legacy wizard; internally delegates the actual create so we have one create code path. |
| T046 | [X] `wizards/product_sku_builder_wizard_views.xml` — wizard form using `widget="statusbar"` on `step` field for step navigation; per-step content via `invisible="step != '1'"` etc.; Cancel always visible; Back hidden when step=1; Next changes to "Create product" on step=4. Create button `groups="multichannel_hub_core.group_ba_user"` defense-in-depth (FR-017 mirror). | T045 | GREEN | Standard Odoo statusbar pattern; no JS. |
| T047 | [X] Menu binding — add menuitem "Build SKU & Create Product" under existing Sales menu near current `product.creation.wizard` action; action opens builder wizard in `target="new"` mode | T045,T046 | GREEN | Keep legacy creation wizard menu live in same parent — coexist per D-V2-3. Both menus group-gated to `group_ba_user`. |
| T048 | [X] RED Phase 1 (DB): `mhc_sku_family` table + UNIQUE on code + indexes; `product_attribute_value.x_code` / `x_namespace` / `x_applicable_family_ids` rel-table columns; 22 family rows seeded; ≥55 attribute-value rows seeded; wizard TransientModel registered | T038–T044 | RED | Register in `tests/__init__.py` per `feedback_tdd_guide_init_py_imports`. |
| T049 | [X] RED Phase 2 (ORM): truth-table for `evaluate(env)` (matches → returns family code; no match → MSC; priority ordering — a name matching both `mug` and `wooden bowl` returns MUG because priority 7 < 22); deactivate a seed family → no match for it; add a new family in test → evaluate finds it (DB-driven proved); compiled-regex cache invalidates on write_date change. Builder wizard happy paths: Mug 11oz → `MUG-CR-F11`; Mug 15oz + black → `MUG-CR-F15-BK`; Apron M → `APR-TX-AM`; Doormat 30×18 → `DMT-TX-R30X18`. Family override step: name says "mug" but BA picks RDS → preview reflects RDS-CE-SQ. Size step family-gating: MUG family only shows Fluid oz attribute values. Empty material → step 2 validation refuses next. FR-017 gate: non-BA AccessError BEFORE any product.template create (assert `product.template.search_count` unchanged after attempted create — pattern from `feedback_fr017_write_defense_in_depth`). | T038–T047 | RED | Use `--http-port=8175` (8170 collides per memory item 134). Wrap `assertRaises((AccessError, UserError))` in savepoint + try/except per memory item 140. |
| T050 | [X] GREEN — make T048/T049 pass | T048,T049 | GREEN | Orchestrator runs `--test-tags /multichannel_hub_core --http-port=8175 --stop-after-init` and reads tail per `feedback_tdd_guide_init_py_imports` 2nd bullet. |
| T051 | [X] Review — code-reviewer + security-reviewer parallel (single message, two Agent calls per `agents.md`) | T050 | Review | Block on CRITICAL/HIGH. Verify reviewer findings against `git diff --stat HEAD` per `feedback_reviewer_agent_diff_hallucination`. |
| T052 | [X] Verify — `-u multichannel_hub_core --stop-after-init` exit 0; full mhc `--test-tags` 0 NEW failures (5 baseline errors in `test_design_file_upload_wizard_multi` are pre-existing — see P-HUB-PROD-MODEL log); ruff if available; grep `_logger.info` / `print(` clean | T051 | Verify | |
| T053 | [X] Commit (conventional, cite T038–T053); tracker P-HUB-SKU-BUILDER → done; LEARN insight to memory (DB-driven family classifier pattern; product.attribute.value extension for code mapping) | T052 | Land | One commit if review clean; multiple per checkpoint if mid-slice WIP. |

**Exit (P-HUB-SKU-BUILDER)**: all `[X]`; tests ≥ 80% changed lines; module installs clean; UNIQUE constraint mirrored in `init()`; `mhc.sku.family` ACL defined; FR-017 24th confirmation captured.

**Out of scope (deferred to sibling slices)**:
- v2.1 regex validator on `default_code` write → `P-HUB-V2-VALIDATE-ON-CREATE` (T061–T069 enumerated 2026-05-26 below; D-V2-2 = soft-warn DECIDED)
- Step 1 family-classifier-misclassified + Step 3 size-unparseable fallbacks → `P-HUB-MISSING-INFO-WIZARD`
- Sunset of legacy `product.creation.wizard` → follow-up after one sprint UAT (per D-V2-3)

---

### Slice — P-UAT-SKU-BUILDER-EXTEND  (UAT-only; no Odoo code)

UAT extension after `P-HUB-SKU-BUILDER` (mhc 19.0.1.0.52) shipped. Decoupled from blocked `P-HUB-V2-VALIDATE-ON-CREATE` per owner D8 (2026-05-26). Respects D7 end-user doc-refresh constraint (no FLOW/HUONG_DAN updates this slice).

| Task | Status | Description | Depends on | Phase | Notes |
|---|---|---|---|---|---|
| T054 | [X] | Deploy mhc `19.0.1.0.52` to staging: rsync `custom_addons/multichannel_hub_core/` → `ubuntu@129.150.63.207:/odoo/esty19/custom_addons/`; `sudo docker exec esty19_odoo odoo -d esty_odoo19 -u multichannel_hub_core --stop-after-init`; `sudo docker restart esty19_odoo`; verify in-container manifest version reads `19.0.1.0.52` | — | Deploy | Per `reference_staging_ssh_deploy` — NEVER `--delete`; secrets bind-mount already configured; staging DB = `esty_odoo19` per `reference_staging_db_name`. |
| T055 | [X] | Rerun existing `tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts` against staging; capture results to `tests/e2e/reports/uat-2026-05-26-rerun/`; baseline vs morning run (4 PASS / 3 SKIP / 1 finding F1 resolved); document any regressions in `specs/009-product-hub/findings.md` | T054 | Verify | If TC-001/002/007 now fail → triage as P-UAT-REGRESSION; SKU-BUILDER landed should NOT regress legacy wizard (D-V2-3 coexist policy). |
| T056 | [X] | Author `tests/e2e/page-objects/product_sku_builder_wizard.ts` — page object for new 4-step builder wizard: step navigation via statusbar, `fillStep1Name(name)`, `assertAutoSuggestedFamily(code)`, `overrideFamily(code)`, `fillStep2Material(matCode)`, `fillStep3Size({namespace, value, rectW, rectH})`, `fillStep4Color(colorCode)`, `assertPreviewSku(expected)`, `submitCreate()`, `assertAccessDeniedBefore`/`After` patterns | T054 | Implement | Mirror style of existing `product_creation_wizard.ts`; selectors per `wizards/product_sku_builder_wizard_views.xml` (statusbar widget). |
| T057 | [X] | Extend `uat_huong_dan_tao_san_pham.spec.ts` with 5 new test cases — TC-008 BA Lead builds MUG-CR-F11 happy path (mug 11oz → `default_code='MUG-CR-F11'`); TC-009 BA Lead builds MUG-CR-F15-BK (mug 15oz + VAR2 color black → suffix `-BK`); TC-010 BA Lead builds APR-TX-AM (apparel size M → step 3 family-gates to apparel-size namespace only); TC-011 BA Lead builds DMT-TX-R30X18 (doormat 30×18 rectangular → rect_w/rect_h drive `R30X18` segment); TC-012 BA User attempts builder → AccessError BEFORE product.template create (assert `product.template.search_count` unchanged via separate ORM xmlrpc probe — FR-017 24th browser-side confirmation) | T056 | Implement | Reuse `loginAsBaLead` / `loginAsBaUser` from `fixtures/odoo-auth`; cleanup via existing `cleanup_uat_data.py` extended for `mhc.sku.builder.wizard` test artifacts (if any persist — wizard is TransientModel so should not). |
| T058 | [X] | Run new TC-008..TC-012 against staging; capture pass/fail/screenshots to `tests/e2e/reports/`; triage failures (fix simple selectors inline; escalate functional failures as new P-UAT-DEFECT slices) | T057 | Verify | Soft gate: 5/5 GREEN = best case; 4/5 acceptable with defect logged; ≤3/5 = STOP and escalate per playbook "When the playbook breaks". |
| T059 | [X] | Document outcomes in `specs/009-product-hub/findings.md` §"P-UAT-SKU-BUILDER-EXTEND" (last-run results + any regressions or defects + memory-worthy surprises); create companion artifact `docs/UAT_RESULTS_2026-05-26_SKU_BUILDER.md` (engineering, not owner-facing — D7 constraint) | T058 | Document | Owner-facing doc refresh waits for P-HUB-V2-VALIDATE-ON-CREATE + P-HUB-MISSING-INFO-WIZARD ship per D7. |
| T060 | [X] | Commits: (a) `[multichannel_hub_core] test(P-UAT-SKU-BUILDER-EXTEND): Playwright TC-008..TC-012 + page object` for Playwright additions; (b) `docs(P-UAT-SKU-BUILDER-EXTEND): findings + tracker state→done` for docs. Update tracker P-UAT-SKU-BUILDER-EXTEND state→done with results summary | T059 | Land | Two commits per scope split (test vs docs). LEARN insight: capture any new browser-side selector patterns or staging deploy gotchas. |

**Exit (P-UAT-SKU-BUILDER-EXTEND)**: all T054–T060 `[X]`; staging running mhc `19.0.1.0.52`; existing 7 TC results baselined; new TC-008..TC-012 results captured; findings.md updated; tracker state→done.

**Acceptable shortcuts applied (per playbook §"Acceptable shortcuts")**: skip Phase 1 planner (UAT-only, scope is clear), skip Phase 2 RED ORM tests (no Odoo code), skip Phase 4 code-reviewer (no Python/XML changes — Playwright TS only). Phase 5 Verify and Phase 6 Commit are NOT skipped.

**Out of scope**:
- Update `FLOW_TAO_SAN_PHAM_VN.md` / `HUONG_DAN_TAO_SAN_PHAM_VN.md` (D7 constraint — refresh after all 3 SKU-v2 features ship).
- Test `P-HUB-V2-VALIDATE-ON-CREATE` behaviour (slice not shipped yet).
- Test `P-HUB-MISSING-INFO-WIZARD` behaviour (slice not shipped yet).

---

### Slice — P-HUB-V2-VALIDATE-ON-CREATE  (~80 LOC, regex validator on both wizards)

v2.1 regex validator + soft/hard mode (D-V2-2 = soft default, DECIDED 2026-05-26). Hooks into both `product.creation.wizard._validate()` and `product.sku.builder.wizard._validate()`. Legacy SKUs preserved via existing `x_sku_v2_status='ba_approved_legacy'` opt-out path. See `docs/owner/SKU_GRAMMAR.md` §7.

| Task | Status | Description | Depends on | Phase | Notes |
|---|---|---|---|---|---|
| T061 | [ ] | `data/sku_v2_enforce_mode_seed.xml` (`noupdate=1`) — single `ir.config_parameter` row `multichannel_hub.sku_v2_enforce_mode` = `'soft'`. Manifest bump 19.0.1.0.52 → **19.0.1.0.53** + add data file to `data` list. | — | Implement | ICP only; no model changes. |
| T062 | [ ] | `services/sku_grammar_v2.py` — add `_VALIDATOR_REGEX = re.compile(r'^[A-Z]{3}-[A-Z]{2}-(SQ|HT|OV|LSQ|WV|AR|BW|RD|S\d+|F\d+|A[A-Z]+|R\d+X\d+)(-[A-Z]{2})?$')` + `validate_v2_sku(default_code: str) -> bool` (compile-once module-level constant + length 8–14 check before regex). Add module-level docstring linking to SKU_GRAMMAR.md §7.1. | — | Implement | Pure function; no env needed. Length check first (cheaper fail). |
| T063 | [ ] | `wizards/product_creation_wizard.py` — extend `_validate()` to call helper BEFORE existing field checks. Pseudo: `mode = env['ir.config_parameter'].sudo().get_param('multichannel_hub.sku_v2_enforce_mode', 'soft'); ok = sku_grammar_v2.validate_v2_sku(self.default_code); if not ok: if mode == 'hard': raise UserError(_("SKU does not match v2.1 grammar...")); else: _logger.warning(...) + flag `_v2_validation_soft_warning = True` so action_create can set x_sku_v2_status='ba_approved_legacy' on the created template.` | T062 | Implement | Legacy SKUs that already have x_sku_v2_status='ba_approved_legacy' are NEVER touched (they bypass via existing compute logic in product_template.py:151). |
| T064 | [ ] | `wizards/product_sku_builder_wizard.py` — extend `_validate()` to call helper BEFORE existing field checks. Same soft/hard branching as T063. Note: builder wizard *constructs* SKUs from controlled segments (FAM3-MAT2-SIZE[-VAR2]), so it should NEVER produce a non-v2 SKU. The validate call is defense-in-depth — guards against a future broken seed or DB corruption producing an invalid family code etc. | T062 | Implement | Same pattern as T063. |
| T065 | [ ] | RED Phase 1 (DB): assert `ir.config_parameter` row with key `multichannel_hub.sku_v2_enforce_mode` exists post-install AND has value `'soft'`. | T061 | RED | Register in `tests/__init__.py` per `feedback_tdd_guide_init_py_imports`. |
| T066 | [ ] | RED Phase 2 (ORM): 8 cases — (1) `validate_v2_sku('MUG-CR-F11')` returns True; (2) `validate_v2_sku('mug-cr-f11')` returns False (lowercase); (3) `validate_v2_sku('MUG-CR-X99')` returns False (bad size token); (4) `validate_v2_sku('M')` returns False (too short); (5) legacy wizard soft mode + non-v2 SKU → product created + `x_sku_v2_status='ba_approved_legacy'` + warning logged; (6) legacy wizard hard mode + non-v2 SKU → UserError before any side effect; (7) builder wizard soft mode + canonical SKU → no warning, normal `non_canonical`→`matches` compute path; (8) BOTH modes: existing product with `x_sku_v2_status='ba_approved_legacy'` is preserved through validate (compute logic in `product_template.py:151` skips ba_approved_legacy — re-verify via O.M.C. `product.template.x_sku_v2_status` after a write). | T063,T064 | RED | Use `--http-port=8175` (8170 collides per memory item 134). Tests parametrise mode via `env['ir.config_parameter'].sudo().set_param('multichannel_hub.sku_v2_enforce_mode', 'hard')` then `.set_param('soft')` in `tearDown` to restore. |
| T067 | [ ] | GREEN — make T065/T066 pass | T065,T066 | GREEN | Orchestrator runs `--test-tags /multichannel_hub_core --http-port=8175 --stop-after-init` and reads tail. |
| T068 | [ ] | Review — code-reviewer + security-reviewer parallel (single message, two Agent calls per `agents.md`) | T067 | Review | Block on CRITICAL/HIGH. Verify reviewer findings against `git diff --stat HEAD` per `feedback_reviewer_agent_diff_hallucination`. Security-reviewer specifically: confirm ICP read path uses `.sudo()` (BA may not have read access on ir.config_parameter), confirm UserError message doesn't leak ICP value to non-system users. |
| T069 | [ ] | Verify — `-u multichannel_hub_core --stop-after-init` exit 0; full mhc `--test-tags` 0 NEW failures (5 pre-existing baseline confirmed via P-HUB-PROD-MODEL log); ruff if available; grep `_logger.info` / `print(` clean. Then commit (conventional, cite T061–T069); tracker P-HUB-V2-VALIDATE-ON-CREATE → done; LEARN insight to memory (ICP gating pattern for behavioural toggles + service-layer regex helper reuse across multiple wizards). | T068 | Land/Verify | One commit if review clean; multiple per checkpoint if mid-slice WIP. |

**Exit (P-HUB-V2-VALIDATE-ON-CREATE)**: all T061–T069 `[X]`; tests ≥ 80% changed lines; module installs clean (mhc 19.0.1.0.53); ICP `multichannel_hub.sku_v2_enforce_mode` row present with default `'soft'`; both wizards' `_validate()` calls helper BEFORE field checks (verify via grep); legacy SKU opt-out (`x_sku_v2_status='ba_approved_legacy'`) preserved through validate.

**Out of scope (deferred)**:
- Re-run UAT TC-008..TC-012 with validator hot — separate `P-UAT-V2-VALIDATE-EXTEND` slice will rerun + add TC-013/TC-014 covering soft/hard mode behaviour visible in browser.
- Bulk re-canonicalise existing catalog legacy SKUs to v2 → `P-HUB-BULK-CANONICALISE` follow-up (not in 006 critical path).
- ICP flip from soft → hard in production → operator decision post-rollout, no code change needed.

---

## Dependency Graph

```
P-HUB-SPEC (this planning slice)
    → P-HUB-PROD-MODEL (T001–T013)
        → P-HUB-WIZARD (T014–T021)
        → P-HUB-SKU-DRIFT mhc-half (T022, T023, T025–T028)
        → P-HUB-BACKFILL (T029–T033)
        → P-HUB-STATUS-VIEW (T034–T037)
        → P-HUB-SKU-BUILDER (T038–T053) [data layer + 4-step wizard]
            → P-HUB-V2-VALIDATE-ON-CREATE (T061–T069, todo, ready 2026-05-26 — D-V2-2 DECIDED soft-warn)
            → P-UAT-SKU-BUILDER-EXTEND   (T054–T060, done 2026-05-26)
            → P-HUB-MISSING-INFO-WIZARD   (T0??–TBD, todo)  [parallel-eligible after T045 lands]
    P-HUB-SKU-DRIFT etsy-half (T024 + sub-tests)
        ← waits on Spec 011 P-PUB-CLIENT
```

## Notes

- All implementation slices: Two-Phase Testing; coverage ≥ 80 % on changed lines; module installs clean.
- New models MUST ship `ir.model.access.csv` rows; UNIQUE constraints MUST be mirrored in `init()` raw SQL with a `pg_constraint IF NOT EXISTS` pre-check (memory `project_sql_constraints_drift`, 8+ confirmations).
- Wizards MUST guard `action_*` methods with a method-top BA-group check before any side effect (memory `feedback_fr017_write_defense_in_depth`, 20+ confirmations).
- RED gate: orchestrator runs `--test-tags` itself with `--http-port=8170` and reads the failure tail (tdd-guide RED-by-inspection gap; memory `feedback_tdd_guide_init_py_imports`).
- Reviewer findings about diff bloat must be verified with `git diff --stat HEAD` before acting (memory `feedback_reviewer_agent_diff_hallucination`).
