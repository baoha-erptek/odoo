# Findings — Spec 002 Etsy Config Fixes

Per `.claude/plans/006-implementation-playbook.md` Phase 7. Surprises, blockers, and deferred decisions discovered during implementation.

---

## 2026-04-26 — Wave 1 (US3+US4) RED phase complete

**Slice**: T025–T030 (US3 product config + US4 partner dedup + geo).

**Test files written** (worktree `002-us3-us4`):
- `tests/test_product_categorizer.py` (156 lines, 6 methods, 1 Phase-1 DB test) — T027
- `tests/test_us3_product_creation.py` (134 lines, 7 methods) — T025/T026
- `tests/test_us4_partner_dedup_geo.py` (337 lines, 17 methods) — T028/T029/T030

Total: 30 test methods, ~627 lines. Python compilation passes.

**Status**: RED expected — but execution blocked, see next finding.

---

## 2026-04-26 — BLOCKER: docker-compose mount is single-worktree

**Symptom**: Running `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --test-tags /etsy_integration` from any wave worktree reports "0 failed, 0 error(s) of 0 tests" — because the new test files don't exist inside the container.

**Root cause**: `docker-compose.yml` bind-mounts the main worktree path:
```
volumes:
  - ./custom_addons:/opt/odoo/custom_addons
```
which resolves to `/home/odoo/odoo_dev/other_projects/odoo19_esty/custom_addons` regardless of where you `docker exec` from. Wave worktrees (`-002-us3-us4`, `-005-sandbox`) are invisible to the container.

**Impact**: Playbook Phase 5 (Verify) cannot run from wave worktrees. RED tests can be authored but not executed against a real Odoo registry. GREEN phase needs this resolved before TDD enforcement is possible.

**Options for Owner**:
1. **Per-worktree docker-compose** (cleanest): copy `docker-compose.yml` into each wave worktree with a unique container name (e.g., `namco_odoo19_us3us4`), DB volume, and external port. Cost: extra disk, extra Postgres processes, port management.
2. **Test-only container** (lightest): one shared `namco_odoo19_test` container that mounts `/home/odoo/odoo_dev/other_projects/` (parent dir) and runs against an ephemeral DB. The test command picks the worktree path at runtime via `-v` or env. Cost: docker-compose template change, slight CI rewrite.
3. **Path-swap dance** (worst): rsync wave worktree's `custom_addons/` over the main worktree before tests, restore after. Fragile, races, breaks the worktree isolation memory rule.

**Recommendation**: Option 2. Add a `docker-compose.test.yml` overlay with a dedicated test container that accepts `WORKTREE_PATH` env var. Land before W1 GREEN starts.

**Workaround for current slice**: Author RED tests in wave worktree (done), commit them, then validate execution from main worktree by temporarily checking out `002-us3-us4` there OR after merge to main. Not ideal but unblocks the loop.

**Not blocking the planner / architect / RED-author phases** — only blocks Phase 5 verification.

**Resolution (2026-04-26)**: Workflow pivoted to single-workspace-on-main (per playbook revision 1). The docker-compose mount now points at the main workspace where forward work happens, so the blocker is moot. W1 GREEN executed cleanly from main workspace.

---

## 2026-04-26 — Wave 1 GREEN complete + 4 pre-existing failures from 002 MVP

**Slice exit**: T025–T030 implementation landed across two commits on main:
- `5a2b9591d60` [etsy_integration] feat(US3): product configuration with categorizer (T025/T026/T027 + tax_group_id/country_id install fix)
- `6d357cca651` [etsy_integration] feat(US4): partner dedup tiers + state/country resolution (T028/T029/T030 with German transliteration)

All 6 W1 tests now GREEN. Ruff clean. No `_logger.info(` for debugging. Module installs cleanly.

**Install-blocker fix (collateral)**: `etsy_fiscal_data.xml`'s `account.tax` record was missing both `tax_group_id` and `country_id` (NOT NULL constraints in Odoo 19). Added a new `tax_group_etsy` record and pinned country to `base.us` (cosmetic — the 0% tax never bills). Fresh install now succeeds.

**Test fix (collateral)**: `test_create_full_order` was outdated since 002 MVP's T016 added a shipping order line; assertion updated from `len == 1` to `len == 2` with shipping-line verification.

**Inherited blockers from 002 MVP slice (`874e06ada5f`)** — 4 pre-existing failures, all sharing the same root cause:

| Test | Root cause | Resolution |
|---|---|---|
| `TestImportWizard.test_import_creates_order` | `wizards/import_orders_wizard.py:185` calls `self.env.cr.commit()` inside test (forbidden by Odoo 19: "Cannot commit or rollback a cursor from inside a test") | T032 (US5): replace `cr.commit()` with `cr.savepoint()` per 500-order batch. Same fix unblocks the next 2 rows. |
| `TestImportWizard.test_import_multiple_lines_same_order` | same `cr.commit()` issue | T032 (US5) |
| `TestImportWizard.test_import_skips_duplicate` | same `cr.commit()` issue | T032 (US5) |
| `TestDeduplication.test_email_log_unique_constraint` | `assertRaises(Exception)` not triggered — likely the same `cr.commit()` rollback breaking savepoint setup. Investigate during T032. | T032 (US5) probable; investigate to confirm. |

**Recommendation**: Take W3 next (Spec 002 US5 dedup + US6 migration). T032 falls inside W3 and naturally clears 3–4 of the 4 pre-existing failures. Residual investigation cost for `test_email_log_unique_constraint` is small and bundles in.

---
