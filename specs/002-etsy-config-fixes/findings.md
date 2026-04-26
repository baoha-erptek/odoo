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

---
