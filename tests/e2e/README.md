# Browser UAT — Playwright

Browser-driven UAT for the 4 Vietnamese user guides at `docs/owner/HUONG_DAN_*_VN.md`,
mapped to JIRA sub-tasks ESTY-183 / 184 / 185 / 186 under parent Story ESTY-182.

## Quick start

```bash
cd tests/e2e
npm install
npx playwright install chromium

# Required env (set in repo .env or export):
#   STAGING_BASE_URL=https://odoo.hatafax.com    (default)
#   STAGING_DB=esty_odoo19                       (default)
#   STAGING_ADMIN_LOGIN=...                      (for seed_ba_user.py)
#   STAGING_ADMIN_PASSWORD=...
#   STAGING_BA_LEAD_LOGIN=...                    (or STAGING_BA_LOGIN)
#   STAGING_BA_LEAD_PASSWORD=...

# Run a single sub-task suite:
npm run test:tao-san-pham      # ESTY-183
npm run test:don-hang-etsy     # ESTY-184 (TBD)
npm run test:giao-hang         # ESTY-185 (TBD)
npm run test:hau-mai           # ESTY-186 (TBD)

# View HTML report:
npm run report
```

## How it works

1. **globalSetup** (`fixtures/global-setup.ts`):
   - Preflight curl to staging
   - Calls `python3 fixtures/seed_ba_user.py` to seed or rotate `uat_ba_user@hatafax.demo`
     with only `multichannel_hub_core.group_ba_user` membership
   - Captures the generated password into `process.env.STAGING_BA_USER_PASSWORD`
2. **Specs** (`tests/uat_*.spec.ts`) run sequentially (workers=1)
3. **globalTeardown**: archives UAT products + the BA User (idempotent)

## Bug-fix loop (owner directive 2026-05-26)

When a test fails:

1. Inspect `artifacts/` for screenshot + trace + video
2. Classify root cause:
   - **A — Code defect** → Create MP006 slice `P-UAT-FIX-TC<NNN>` in
     `.claude/plans/006-master-plan-tracking.md`, dispatch via
     `/dispatch-slice P-UAT-FIX-TC<NNN>`, commit lands on
     `feature/006-master-plan-coding`, rerun the single TC.
   - **B — Test infra bug** → Fix the spec or POM under `tests/e2e/`; no MP006 slice.
   - **C — Data/seed gap** → Extend `fixtures/seed_uat_data.py`; no MP006 slice.
3. STOP triggers (per playbook):
   - Same TC fails 3 times → escalate
   - Slice diff > 200 LOC outside `custom_addons/` → escalate
   - Schema migration required in a `done` slice → escalate

## Files

```
tests/e2e/
├── playwright.config.ts          # Playwright config (Vietnamese locale, 1 worker)
├── tsconfig.json
├── package.json                  # Pinned to @playwright/test 1.48.0
├── fixtures/
│   ├── env.ts                    # Reads STAGING_* from repo .env
│   ├── odoo-auth.ts              # loginAsBaLead / loginAsBaUser / loginAsAdmin
│   ├── global-setup.ts           # Preflight + seed BA User
│   ├── global-teardown.ts        # Cleanup
│   ├── _xmlrpc_session.py        # Shared XML-RPC helper (Python)
│   ├── seed_ba_user.py           # Idempotent BA User seed via XML-RPC
│   └── cleanup_uat_data.py       # Archive UAT products + BA User
├── page-objects/
│   └── product_creation_wizard.ts
├── tests/
│   └── uat_huong_dan_tao_san_pham.spec.ts   # TC-001..007 (ESTY-183)
└── reports/                      # gitignored: HTML + JSON reports
```

## Cross-references

- Plan: `/home/odoo/.claude/plans/commit-this-and-start-imperative-moore.md`
- Agent reference: `.claude/agents/e2e-runner.md` (Playwright selector patterns)
- Skill: `~/.claude/skills/e2e-testing/SKILL.md` (POM pattern)
- Source script (XML-RPC sibling, NOT browser): `scripts/e2e_product_listing.py`
