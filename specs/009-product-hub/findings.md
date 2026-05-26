# Findings — Spec 009 (Central Product Hub)

## P-HUB-V2-VALIDATE-ON-CREATE — 2026-05-26

**Status**: landed on `feature/006-master-plan-coding`. mhc 19.0.1.0.52 → **19.0.1.0.53**. Tasks T061–T069 all `[X]`.

**Scope delivered**:
- `services/sku_grammar_v2.py`: module-level `ICP_ENFORCE_MODE_KEY` constant, compile-once `_VALIDATOR_REGEX`, pure `validate_v2_sku(default_code) -> bool` (length 8-14 fast-fail, then regex match).
- `data/sku_v2_enforce_mode_seed.xml` (`noupdate=1`): `ir.config_parameter` row `multichannel_hub.sku_v2_enforce_mode` = `'soft'` (D-V2-2 default).
- `wizards/product_creation_wizard.py` (legacy): `_validate()` runs v2 grammar check **before** existing field checks; returns `bool` soft-warn flag; `action_create()` consumes flag and pins `x_sku_v2_status='ba_approved_legacy'` in the `Template.create({...})` payload so the compute bypass at `product_template.py:151` leaves the new template alone.
- `wizards/product_sku_builder_wizard.py` (builder): same pattern as defense-in-depth — even though the wizard composes SKUs from controlled taxonomy segments, the validator catches future broken family seeds.
- `tests/test_phase1_hub_v2_validator_db.py` (1 case) + `tests/test_phase2_hub_v2_validator_orm.py` (8 cases) — RED→GREEN. Full mhc suite 574 tests, 0 NEW failures (5 baseline errors in `test_design_file_upload_wizard_multi` unchanged).
- `tests/test_phase2_hub_wizard_orm.py`: 1 assertion updated (`test_action_create_non_canonical_sku_passes_through`) from `non_canonical` → `ba_approved_legacy` to reflect the slice's contract change for legacy-wizard non-v2 SKUs under soft mode.

**Decisions exercised**: D-V2-2 (soft default — operator pins legacy), D-V2-3 (legacy + builder coexist, same contract).

**Reviews**: code-reviewer APPROVE 0 CRITICAL/HIGH; security-reviewer APPROVE 0 CRITICAL/HIGH (2 LOW: ReDoS residual capped by 14-char fast-fail; ICP read sudo justified). Both verified against `git diff --stat HEAD` per `feedback_reviewer_agent_diff_hallucination`.

**Surprises / memory hits**:
- `feedback_fr017_write_defense_in_depth` — 25th confirmation. The v2 validator sits inside `_validate()` (called AFTER the method-top `_check_ba_or_raise()` gate but BEFORE any `Template.create()`). Phase 2 case 6 asserts `product.template.search_count` unchanged after hard-mode UserError — the canonical FR-017 assertion.
- **Slice-contract test fallout**: P-HUB-WIZARD's `test_action_create_non_canonical_sku_passes_through` asserted `x_sku_v2_status='non_canonical'` for legacy SKUs. Slice changed that to `ba_approved_legacy` under soft mode (the new contract). The test update is part of the slice scope, not a regression mask — docstring updated to call out D-V2-2 contract.
- **Empty-SKU builder short-circuit**: builder's v2 check is gated `if assembled and not validate_v2_sku(assembled)` — without the `assembled` truthiness guard the validator returns False on empty string and triggers a false soft-warn for incomplete wizard state (caught at code-design time by reasoning).

**No new patterns** worth a global memory file beyond the FR-017 25th tick. ICP gating for behavioural toggles is now common enough across mhc (`multichannel_hub.large_file_threshold_bytes`, `multichannel_hub.sku_v2_enforce_mode`) that it's no longer surprising — it's the standard "feature-flag without a feature-flag library" idiom.

**Unblocks**: P-HUB-MISSING-INFO-WIZARD can build on the soft/hard contract; `P-UAT-V2-VALIDATE-EXTEND` (browser rerun + add TC-013/014 for soft/hard mode behaviour) is the natural follow-up but is deferred.

---

## P-UAT-SKU-BUILDER-EXTEND — 2026-05-26

**Slice goal**: Deploy mhc 19.0.1.0.52 to staging + rerun existing UAT (TC-001..TC-007) + extend with TC-008..TC-012 covering the new 4-step `product.sku.builder.wizard`. Decoupled from blocked P-HUB-V2-VALIDATE-ON-CREATE per owner D8.

**Final result**: 8 PASS / 4 SKIP / 0 FAIL (12 total). Cleanup archived 17 UAT product templates + the auto-seeded BA User. Run time: 1m12s end-to-end. No regression from SKU-BUILDER landing on the legacy `product.creation.wizard` flow.

**Per-TC outcomes**:

| TC | Outcome | Notes |
|---|---|---|
| TC-001 | PASS | Legacy wizard, BA Lead, Mug + Etsy channel |
| TC-002 | PASS | Legacy wizard, Gearment SKU → Dropship flag |
| TC-003 | SKIP | Pre-existing — needs seeded non_canonical product |
| TC-004 | SKIP | Pre-existing — needs Etsy API + published product |
| TC-005 | SKIP | Pre-existing — Etsy draft creation chained from TC-001 |
| TC-006 | PASS | BA User can see Publish-to-Etsy button (designed behaviour; doc mismatch F1 deferred) |
| TC-007 | PASS | Legacy wizard zero-price → "Listing Price must be greater than 0" |
| TC-008 | PASS | NEW — MUG-CR-F11 happy path (mug 11oz, Ceramic + Chrome) |
| TC-009 | PASS | NEW — MUG-CR-F15-BK (mug 15oz + VAR2 Black color) |
| TC-010 | PASS | NEW — APR-TX-AM (Apron, Textile, Medium apparel size, family-gated) |
| TC-011 | PASS | NEW — DMT-TX-R30X18 (Doormat, Textile, 30×18 rectangular) |
| TC-012 | SKIP | NEW — FR-017 24th browser stub. Negative path covered at correct layer by `tests/test_phase2_hub_sku_builder_orm.py::test_non_ba_user_blocked_before_template_create`. Browser promotion deferred to P-UAT-FR017-BUILDER-BROWSER (needs plain-user fixture). |

**Memory-worthy surprises** (added during this slice):

- **Container path ≠ host bind-mount source.** Memory `reference_staging_ssh_deploy` line 22 *does* state `/odoo/esty19/custom_addons/` is bind-mounted to `/mnt/extra-addons` inside the container — but the deploy-verify SSH probe used the host path against `docker exec` and got `No such file or directory`. Quick fix once spotted; flagging here so the deploy runbook explicitly contrasts the two paths.
- **Staging public URL not previously recorded in memory.** `https://odoo.hatafax.com` → HTTP 200 in 0.4s; default `STAGING_BASE_URL` in `tests/e2e/fixtures/env.ts` already pointed at it correctly, but nginx vhost grep against `8169` / `esty19` / hostname returned empty (vhost is in `default` site, no greppable `server_name`). Adding to `reference_staging_server.md`.
- **UAT credential model** confirmed for this slice: `STAGING_ADMIN_LOGIN=admin / STAGING_ADMIN_PASSWORD=admin` (owner directive 2026-05-26), `STAGING_BA_LEAD_LOGIN=STAGING_BA_LEAD_PASSWORD=admin` as substitute, BA_USER auto-seeded fresh each run via `seed_ba_user.py`. Real BA_LEAD seeding deferred to operator-manual UAT.
- **Seed display-name ≠ code drift** caused 3 RED iterations on the first browser run. Display names in `data/sku_attribute_seed.xml` differ from the canonical x_code strings used in SKU previews and docs:
  - `F11` ↔ display **"11 oz"** (not "11 fl oz")
  - `F15` ↔ display **"15 oz"** (not "15 fl oz")
  - `AM` ↔ display **"Medium"** (not "M" — autocomplete on "M" alone matches any record containing M)
  - `CR` ↔ display **"Ceramic + Chrome"** (NOT plain "Ceramic" — that's CE). SKU_GRAMMAR.md row 30 confirms canonical mug material is "ceramic+chrome combo". Easy mistake: doc abbreviation hides the seed long-form.

  Test fix: search by full display name, never abbreviation. Pattern applies to all M2O autocompletes against product.attribute.value, since the field has no domain restriction and the unsegmented dropdown fuzzy-matches across all attributes.

- **Color m2o needs explicit blur after pick** to settle the `preview_sku` compute. Without `await press('Tab') + waitForTimeout(300)`, the next `getPreviewSku()` read returned `MUG-CR-F15` (no `-BK` suffix) despite the autocomplete suggestion being clicked. Fix landed in `page-objects/product_sku_builder_wizard.ts::fillStep4Color`. The other M2O fields (family/material/size) don't need this because the explicit `clickNext()` already blurs them as part of the step transition — color is in the last step so there's no Next to trigger the blur.
- **JSON-RPC > XML-RPC for Playwright cross-checks.** The new TC verify the `default_code` actually landed in the DB by POSTing to `/web/session/authenticate` then `/web/dataset/call_kw/product.template/search_count`. Cleaner than mixing Python `xmlrpc.client` shell-outs into the JS test runner. Pattern is reusable for future Playwright slices that need to inspect DB state.

**Doc constraint honoured** (per D7): owner-facing `docs/owner/FLOW_TAO_SAN_PHAM_VN.md` + `HUONG_DAN_TAO_SAN_PHAM_VN.md` deliberately NOT updated this slice — refresh happens in a single clean pass after P-HUB-V2-VALIDATE-ON-CREATE + P-HUB-MISSING-INFO-WIZARD also ship.

**Bonus deploy verification** captured: mhc `19.0.1.0.52` running in container `esty19_odoo` on staging, all 103 modules loaded clean in 4.79s on `-u multichannel_hub_core --stop-after-init`. Pre-existing warnings (sql_constraints deprecation in Odoo 19, duplicate-label across etsy_integration + multichannel_hub_core) unchanged — consistent with memory item 138.

## P-HUB-SKU-BUILDER — 2026-05-26

- **Odoo 19 index naming uses double underscore.** `index=True` on `mhc.sku.family.code` produces `mhc_sku_family__code_index` (double underscore between table and column), not `mhc_sku_family_code_index` as one would guess from older Odoo conventions. Phase-1 DB test originally asserted the single-underscore name and failed. Fix: tighten the assertion to a regex-tolerant `pg_indexes` lookup that just proves *some* btree index covers the `code` column. Memory candidate — same trap will recur on every new `index=True` field. Cheapest verification: `docker exec ... psql ... -c "SELECT indexname FROM pg_indexes WHERE tablename = ..."`.

- **Family-gating needs two layers, not one.** SKU_GRAMMAR §4 says "MUG family → only F* sizes allowed". First attempt implemented this via `x_applicable_family_ids` M2M on each size value: F11 → [MUG, TUM]; AM → [APP, APR]; SQ → empty (applies to all). Phase-2 test `test_size_step_for_mug_only_allows_fluid_oz_values` failed because SQ has empty applicable list → "applies to all" → MUG with SQ size passed. Fix required adding a second layer: hardcoded `_FAMILY_NAMESPACE_MAP` in the wizard module mapping family code → set of allowed size namespaces (`fluid_oz` / `apparel` / `rect` for restrictive families; default {shape, dim, rect} for dish-like families). Both layers cooperate — explicit allowlist plus namespace rule. Future slice could promote the namespace map to a field on `mhc.sku.family`; for v1 the hardcode is fine because SKU_GRAMMAR §4 is owner-locked.

- **Per-cursor compile cache for DB-driven regex.** The frozen tuple was a module-load constant — one compile per process. The DB-driven version risks recompiling on every `evaluate()` call. Solution: stash a `{(family.id, write_date_ts): FamilyRule}` dict on `env.cr._sku_grammar_v2_cache` (set via setattr fallback for cursor proxies in test contexts). Negative-cache malformed regex (cache `False`) so we don't re-log warnings on every call. Cursor-local naturally isolates multi-worker deployments; `write_date` movement invalidates entries on the next call after a BA edit. ~30 LOC added to the service; no measurable perf hit observed in tests.

- **TransientModel ACL is broadly readable + writable; auth is the method gate.** The builder wizard's ir.model.access.csv row is `base.group_user,1,1,1,1`. Security-reviewer flagged this as HIGH on first glance — but it's the canonical FR-017 pattern: the gate inside `action_create()` is the auth boundary, not the ACL. Non-BA users can instantiate the wizard (so the menu doesn't 403 on render) but cannot call `action_create()`. Confirmed safe because (a) the gate is the FIRST executable statement and (b) the test asserts `product.template.search_count` is unchanged after a non-BA attempt.

- **§8 attribute taxonomy spec was wisely pre-written.** SKU_GRAMMAR §8 already mandated `product.attribute` reuse for Material/Shape/Size/Fluid oz/Apparel size/Color. When the user asked "any Odoo default models we can reuse?", the spec answer was already there — we just executed it. Family stayed as a dedicated `mhc.sku.family` model because it carries regex + route + default-material metadata that doesn't fit a generic attribute-value. Hybrid architecture (D-V2-6) documented in §2.5.

## P-HUB-SPEC (planning slice) — 2026-05-23

- **Spec number.** Phase 5 of MASTER_PLAN §4 historically reserved spec numbers 007 (raw-material inventory), 008 (catalog dashboard), 009 (barcode scan), 010 (Amazon channel), 011 (website channel). Spec 008 was actually filled by Listings & Inventory Sync (2026-05-16), shifting the Phase-5 placeholder usage. Owner directive 2026-05-23 absorbs the Phase-5 "catalog/Amazon/website" intent into MP006 Phase 3 (new), so reusing 009/010/011 for Phase-3 specs is consistent with the new charter — the original Phase-5 placeholders are retired (see MASTER_PLAN amendment + tracker change-log entry).
- **ADR-014 builds on ADR-013's mutual-consistency framing.** ADR-013 chose `etsy.listing` as a *standalone Model* (channel-side mirror, optional FK to product). ADR-014 chooses Many2many channel applicability on `product.template` (canonical hub, channel as tag). The two decisions are symmetric: channel-side records are standalone; channel-identity on the product is a flag. Both followed the same decision framework (ADR-007's "is this a 1:1 facet of the host record?") and reached opposite conclusions for opposite-side records. Documented in ADR-014 §1 rationale.
- **Owner SKU-drift policy.** Two questions resolved in-session 2026-05-23 (plan file `/home/odoo/.claude/plans/actually-need-to-check-polymorphic-crayon.md`):
  1. New Etsy publishes use v2-canonical SKU when present (legacy SKU only persists on Etsy through backfill or explicit `ba_approved_legacy`).
  2. Canonicalisation of a live listing auto-pushes `PUT /listings/{id}/inventory` synchronously; rollback on push failure.
- **Pricing reuse.** `product.pricelist` (stock Odoo) is the canonical sell-price mechanism for per-channel / per-currency pricing. The three new `product.template` Float fields (`x_listing_price`, `x_shipping_price_internal`, `x_additional_cost`) are bookkeeping for the Excel round-trip and margin reporting — they are **NOT** read by the Etsy publisher or by sale-order pricing logic (ADR-014 §2). This guardrail must survive into Spec 010 (parser must not be tempted to also write the pricelist; pricelist seed is a one-time first-import action). Recorded here so implementation slices don't re-litigate.
- **Module ownership decided up-front (ADR-014 §5).** All channel-agnostic surfaces (`multichannel.sales.channel`, `product.channel.status`, product.template extensions, creation wizard, SKU drift wizard, Excel parser/cron) live in `multichannel_hub_core` per memory `feedback_channel_agnostic_groups_in_mhc`. Etsy-specific surfaces (publisher service, publish wizard, backfill wizard, SKU canonicalisation Etsy push hook) live in `etsy_integration`. Recorded here so neither spec splits modules incorrectly.
- **Pure-doc slice.** No code/tests; Two-Phase Testing N/A for P-HUB-SPEC. Implementation slices (P-HUB-PROD-MODEL etc.) carry the testing burden; tasks.md encodes RED/GREEN/Review/Verify/Land phases.
- **Reused codebase invariants pre-loaded into tasks.md** to spare implementation slices from re-discovering: (a) `_sql_constraints` is inert in Odoo 19 — `init()` raw-SQL mirror with `pg_constraint IF NOT EXISTS` pre-check is the sole enforcement (memory `project_sql_constraints_drift`, 8+ confirmations; vindicated again in Spec 008 P-LIST-PULL); (b) FR-017 method-top gate before side effects on every `action_*` (memory `feedback_fr017_write_defense_in_depth`, 20+ confirmations); (c) register new test files in `tests/__init__.py` and run with `--http-port=8170` in container (memory `feedback_odoo19_test_gotchas`, `feedback_tdd_guide_init_py_imports`); (d) verify reviewer-diff findings with `git diff --stat HEAD` before applying (memory `feedback_reviewer_agent_diff_hallucination`).

## P-HUB-PROD-MODEL — 2026-05-23

- **`_sql_constraints` is NOT silently inert in Odoo 19 — it logs WARNING.** Confirmed during initial GREEN run: every model with `_sql_constraints` defined emits `WARNING ... Model attribute '_sql_constraints' is no longer supported, please define model.Constraint on the model.` The previously "inert" attribute is now an active diagnostic warning. For Spec 009 we kept models clean — no declarative `_sql_constraints` leftover, just the `init()` raw-SQL mirror. Memory `project_sql_constraints_drift` upgraded from "inert" framing to "warning-noisy" framing for future slices.
- **Seed-leak after RED test installs.** First `--test-enable -u multichannel_hub_core` run failed at `setUpClass` (models didn't exist yet) but had already loaded `data/multichannel_sales_channel_seed.xml` enough to INSERT 3 channel rows. The `ir_model_data` xmlid mappings did NOT persist (transaction abort on test-failure), leaving 3 ownerless rows. The subsequent `-u` install then re-attempted the seed INSERT and hit `uniq_multichannel_sales_channel_code`. Resolution: one-time `DELETE FROM multichannel_sales_channel;` then a clean `-u` re-populated rows AND `ir_model_data` correctly. Worth noting for any spec that combines new seed data with RED tests on the same DB.
- **Port 8170 collided.** Memory item #134 says "container test runs need `--http-port=8170`" — but here `--http-port=8170` raised "Address already in use". Switched to `--http-port=8175` for all RED/GREEN test runs. Port number is incidental; only requirement is "not 8069 nor a port mapped by docker-compose".
- **Two re-confirmed test traps from memory:**
  - `Channel.search([('code','=','amazon')])` returns empty for inactive seed without `.with_context(active_test=False)`. Fixed by switching to `Channel.with_context(active_test=False).search(...)` in setUpClass + the seed-loaded assertion.
  - `assertRaises((ValidationError, ValueError))` tuple breaks `TransactionCase._assertRaises` issubclass check (`TypeError: issubclass() arg 1 must be a class`). Workaround: wrap in `self.env.cr.savepoint()` + try/except + assert `raised` flag.
- **Grammar v2 `evaluate()` MVP scope.** Returns `family_code` as `suggested_sku` (e.g. `("RDS", "RDS")`). Full SKU string (`RDS-CE-S35-D####`) requires MAT2 detection + SIZE encoding + DSGN registry, none in this slice. Test truth-table assertions use the family-code-as-suggested form. When DSGN registry lands (separate slice), `evaluate()` signature stays `(suggested, family_code)` but `suggested` becomes the full structured string; tests will need adjusting. Documented in service docstring.
- **Decisions deferred to next slices** (NOT this slice's bug):
  - FR-017 gate on `x_sku_v2_status` writes — accepted MEDIUM finding; gate lands in **P-HUB-SKU-DRIFT** wizard (T022).
  - N+1 review on compute functions — not flagged (standard `for rec in self` idiom; no relational reads).
  - Smart button + Channels tab on product form — **P-HUB-STATUS-VIEW** (T034–T037).

## E2E surfacing (live)

_(none yet — implementation not started)_
