---
name: run-uat
description: Run the full browser-UAT loop against the Etsy staging Odoo end to end — reset staging products, deploy/upgrade the custom modules, seed UAT data, run the Playwright suite, and report results. Use whenever the owner wants to "run the UAT", "re-run tao-san-pham", "do a UAT pass", "publish a smoke draft to Etsy", or verify the HUONG_DAN_*_VN guides on staging, even if they don't name the individual scripts. Orchestrates the existing repo building blocks (scripts/reset_staging_products.py, tests/e2e/fixtures/seed_uat_data.py, the rsync+docker staging deploy, npm run test:*) with all the documented gotchas baked in.
---

# run-uat

Reusable orchestration of the product-creation UAT loop (ESTY-183,
`tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts`) and its siblings.
It chains five stages that already exist as separate scripts/commands:

```
reset staging  →  deploy/upgrade modules  →  seed UAT data  →  run Playwright  →  report
```

This skill is a **procedure**, not new code — every step below maps to a
building block that already lives in the repo. The skill's value is sequencing
them correctly and carrying the gotchas that cost prior runs hours.

## When to use

- Owner asks to run / re-run the UAT (any of the 4 `HUONG_DAN_*_VN` suites).
- After landing a slice that touches `multichannel_hub_core`,
  `etsy_integration`, or `multichannel_hub_fulfillment` and you want a staging
  verification pass.
- For a fee-free Etsy draft smoke (form-only by default; live drafts only when
  explicitly opted in).

## Blast radius — read before running

This loop touches a **shared staging host** and can create **real Etsy drafts**.
Treat it like the careful-action checklist:

| Stage | Reversible? | Guard |
|---|---|---|
| Reset products | Destructive on staging DB | DRY-RUN by default; `--apply` only after reviewing the DELETE list; never deletes confirmed orders |
| Deploy modules | rsync overwrites staging code | per-module rsync, **NEVER `--delete`** (a prior run destroyed mhf on staging with `--delete`) |
| Seed | Idempotent | safe to re-run |
| Run Playwright | Form-only = offline-of-Etsy | live Etsy drafts ONLY when `RUN_ETSY_PUBLISH=1` |
| Report | Read-only | — |

Default to the **form-only, dry-run-reset** path. Escalate to `--apply` /
`RUN_ETSY_PUBLISH=1` only when the owner asks for a destructive reset or a live
Etsy publish window.

## Prerequisites

Env (read from repo `.env` or exported; defaults in parentheses):

| Var | Purpose | Default |
|---|---|---|
| `STAGING_BASE_URL` | staging Odoo | `https://odoo.hatafax.com` |
| `STAGING_DB` | DB to target | `esty_odoo19` |
| `STAGING_ADMIN_LOGIN` / `STAGING_ADMIN_PASSWORD` | admin XML-RPC + BA-user seed | — (password required) |
| `STAGING_BA_LEAD_LOGIN` (or `STAGING_BA_LOGIN`) / `STAGING_BA_LEAD_PASSWORD` | BA-lead login for TC-006/007 | — |
| `RUN_ETSY_PUBLISH` | `1` enables live Etsy draft TCs | unset (form-only) |
| `E2E_LISTING_PRICE` | VND price floor for live publish | `250000` |

> The canonical staging DB is **`esty_odoo19`** (older notes say `demo_esty` —
> that is stale).

SSH to staging (deploy stage only):
```bash
SSHKEY=/home/odoo/odoo_dev/other_projects/odoo19_esty/secrets/ssh-key-2023-02-24.key
SSHOPTS="-i $SSHKEY -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o IdentitiesOnly=yes"
# host: ubuntu@129.150.63.207  (nwf-oracle); container: esty19_odoo; bind-mount: /mnt/extra-addons
```

## The loop

All `npm` commands run from `tests/e2e/`. First time only:
`npm install && npx playwright install chromium`.

### Stage 1 — Reset staging products (optional)

Clears leftover test artifacts + pulled Etsy listings so the DB starts clean.
Keeps system products (delivery, MTO phantom, gift card, eWallet).

```bash
cd tests/e2e
npm run reset:products            # DRY-RUN — prints KEEP/DELETE plan, no writes
# Review the DELETE list, then if the owner approved a destructive reset:
npm run reset:products:apply      # --apply --delete-orders (DRAFT orders only)
```

Skip this stage for a quick verification pass on an already-clean DB.

### Stage 2 — Deploy / upgrade modules to staging

Only when local module code is ahead of staging. Per-module rsync, then update,
then **restart** (Python field metadata is in-memory until restart).

```bash
SRC=/home/odoo/odoo_dev/other_projects/odoo19_esty/custom_addons
for m in multichannel_hub_core etsy_integration multichannel_hub_fulfillment; do
  rsync -az --no-perms --no-owner --no-group --exclude '__pycache__' --exclude '*.pyc' \
    -e "ssh $SSHOPTS" "$SRC/$m/" "ubuntu@129.150.63.207:/odoo/esty19/custom_addons/$m/"
done
# Module update on a throwaway port so it doesn't fight the live 8069/8169:
ssh $SSHOPTS ubuntu@129.150.63.207 \
  "sudo docker exec esty19_odoo odoo -d esty_odoo19 \
   -u multichannel_hub_core,etsy_integration,multichannel_hub_fulfillment \
   --stop-after-init --no-http --http-port 9999"
ssh $SSHOPTS ubuntu@129.150.63.207 "sudo docker restart esty19_odoo"
```

If a slice added a new field/migration that staging never had, expect the
update to ALTER the column on first `-u`. Tail logs on doubt:
`ssh $SSHOPTS ubuntu@129.150.63.207 "sudo docker logs --tail 80 esty19_odoo"`.

### Stage 3 — Seed UAT data

`globalSetup` runs this automatically before the suite (BA user + categories +
legacy SKU product + tags). Run manually only to pre-seed or debug:

```bash
npm run seed:ba-user      # uat_ba_user@hatafax.demo, group_ba_user only
npm run seed:uat-data     # Mug/Apron/Doormat family-wired categories, legacy SKU, tags
```

### Stage 4 — Run the Playwright suite

```bash
# Form-only (fast, no Etsy fees) — the default:
npm run test:tao-san-pham
# Live Etsy draft TCs (creates real JaHandmadeArt drafts — owner window only):
RUN_ETSY_PUBLISH=1 E2E_LISTING_PRICE=250000 npm run test:tao-san-pham
# Other guides (ESTY-184/185/186, currently TBD):
npm run test:don-hang-etsy   # npm run test:giao-hang   # npm run test:hau-mai
npm run test:all
```

Suite runs sequentially (`workers=1`). Live TCs `test.skip` themselves unless
`RUN_ETSY_PUBLISH=1`.

### Stage 5 — Report

```bash
npm run report               # opens reports/html
# JSON for CI/triage: tests/e2e/reports/results.json
# Failure artifacts (screenshot + trace + video): tests/e2e/artifacts/
```

## Gotchas (carried from prior runs)

- **DB is `esty_odoo19`**, not `demo_esty`.
- **rsync NEVER `--delete`** — it once wiped mhf on staging.
- **Restart the container after `-u`** or Python field-metadata changes
  (e.g. readonly flips) silently don't take.
- **Use `--http-port 9999`** (any free port) on the staging `-u` so it doesn't
  collide with the live web port; locally the in-container test trap is 8169 →
  use `--http-port 8170`.
- **JaHandmadeArt is a VND shop** — live publish needs `E2E_LISTING_PRICE=250000`
  (or higher) or createListing 400s "price too low".
- **Standard product form lazy-renders notebook tabs** — weight (Inventory tab)
  and other off-General fields need the tab opened + visible before fill; the
  POM handles this, but a new field on a new tab needs the same treatment.
- **Bare-family SKU** ("MUG") trips Odoo's "Internal Reference already exists"
  dialog — the spec auto-dismisses via `addLocatorHandler`.
- **Post-publish RPC reads** (`product.channel.status.external_ref`) need a
  poll-until-truthy, not a single read (propagation race).
- **Reset is DRY-RUN by default** — `--apply` writes; double-check the target DB.

## When a test fails — bug-fix loop

Per the e2e README owner directive (2026-05-26):

1. Inspect `tests/e2e/artifacts/` (screenshot + trace + video).
2. Classify root cause:
   - **A — code defect** → create MP006 slice `P-UAT-FIX-TC<NNN>`, dispatch via
     `/dispatch-slice`, fix lands on `feature/006-master-plan-coding`, rerun the TC.
   - **B — test infra bug** → fix the spec/POM under `tests/e2e/`; no MP006 slice.
   - **C — data/seed gap** → extend `fixtures/seed_uat_data.py`; no MP006 slice.
3. STOP triggers: same TC fails 3× → escalate; diff > 200 LOC outside
   `custom_addons/` → escalate; schema migration needed in a `done` slice → escalate.

## Building blocks (source of truth)

| Stage | Building block |
|---|---|
| Reset | `scripts/reset_staging_products.py` (`npm run reset:products[:apply]`) |
| Deploy | rsync + `sudo docker exec ... odoo -u ...` + restart (memory `reference_staging_ssh_deploy`) |
| Seed | `tests/e2e/fixtures/seed_ba_user.py`, `seed_uat_data.py` (run by `global-setup.ts`) |
| Run | `tests/e2e/package.json` `test:*` scripts; specs in `tests/e2e/tests/` |
| Report | `playwright.config.ts` reporters → `tests/e2e/reports/` + `artifacts/` |
