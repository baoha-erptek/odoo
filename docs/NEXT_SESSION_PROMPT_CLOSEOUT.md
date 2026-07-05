# Next Session Prompt — Post-Gate Closeout: P1-11 cutover, XLS verify, MF-E2E-4 (when owner unblocks)

**Created**: 2026-07-04 EOD · **Supersedes**: `NEXT_SESSION_PROMPT_MF_E2E_FLOWS.md` (all its gates closed).
**Paste into a fresh session**: copy the Mission below.

---

## State at handoff (verified 2026-07-04 EOD, commit `855b247a52b`, main == feature branch)

- **MF-E2E gates 0/1/2/3a/3b: DONE** ×2 consecutive each, evidence in
  `docs/engineering/uats/E2E_FLOW{1,2,3A,3B}_*_2026-07-04.md` + `E2E_DEMO_DROP_SHIP_ORDERTEST2_2026-07-04.md`.
  9 product defects found+fixed this pass (etsy_integration **19.0.3.18.0**, mhf **19.0.1.0.27**, mhc **19.0.1.0.76** — all deployed to staging `esty_odoo19`).
- Gearment E2 keys LIVE in `.env` (owner: develop account, actual tests blessed). Etsy staging shop JaHandmadeArt fully wired.
- `.docs/tasks/` tickets cross-referenced in spec 015 §"JIRA ticket alignment".

## Mission (priority order)

1. **P1-11 — pilot-shop cutover** (spec 015 row, state todo, blocker cleared: E2 done).
   JaHandmadeArt OAuth→API cutover per `P1-11-RUNBOOK`. Then P2-07 (Gmail cron rebind) → P1-13/P2-08 (remaining shops) as owner schedules.
   After P1-11: re-run flow-3a §8 / flow-3b §6 against a REAL receipt → live `pushed` confirmation → close the tracking-push loop.
2. **XLS catalog mini-verification** — flip the last honest `shipped*` rows:
   P-HUB-XLS-PARSE / INGEST / CRON, P-HUB-IMAGES, P1-01b (+T058, T065–66 if touched).
   Small sectioned runner (pattern: `scripts/e2e_flow1_publish.py`): catalog xlsx → import run wizard → products created → image cron → dashboard row visible. Evidence + flips like the other gates.
3. **MF-E2E-4 — flow-4 hậu mãi** — ONLY when owner explicitly starts it (still owner-held).
   Scope per spec 015 gate row: address-change approve→apply; reprint (new MO + second tracking push); `etsy.order.ticket` draft→approve→refunded. Reuse drop-ship runner §3/§10 + address-change page-object + `scripts/e2e_flow3a_fulfillment.py` section skeleton.
4. **T067 → T070 → T073**: reconciliation CSV, clean-DB install test, then the umbrella BA sign-off (needs MF-E2E-4 too).

## Blocked on OWNER / VENDOR (do not burn cycles; ping owner instead)

| Item | Action |
|---|---|
| ~~**Gearment printing_options validator** (Defect-2026-05-10-05)~~ | **CLOSED 2026-07-05 — no owner/vendor action needed.** Cracked via live probes (not vendor support): full draft+quote schema corrected, both proven live 200. flow-3b + demo pass live ×2. See `specs/004-fulfillment-routing/findings.md` 2026-07-05. Remaining owner action: discard the test DRAFT orders in the Gearment dashboard. |
| **Etsy `listings_d` scope** | Owner decision: add to DEFAULT_SCOPES + re-authorize shop (enables true test-listing DELETE), or periodically purge `UAT-TAOSP*`/`E2E-F1*` drafts in Shop Manager. |
| **`active_source` UI toggle vs flow-2 doc** | Owner decision: fix doc ("backend/admin write") or request a system-gated UI toggle (badge is deliberate P-DS-3a design). |
| **P1-MSG-SCOPE** | Owner re-submits `conversations_r` to Etsy (blocks P3 lead routing only). |
| ESTY-244 (design module split) + ESTY-246 (PO Gearment quote) | In-process tickets; when they land, re-run flow-3a §3 / add 3b PO-quote leg + re-baseline `test_pipeline_state_db` (its `design_ready` seeds caused the 3 known local test failures). |

## Read first (in order)

1. `specs/015-project-completion/spec.md` — gate table (all states current as of 2026-07-04 EOD) + §"JIRA ticket alignment" + remaining backlog (6 AUD/P-item todos are P2+).
2. `specs/015-project-completion/findings.md` — four 2026-07-04 blocks (one per gate; every trap + fix of this pass).
3. Memories: `mf-e2e-gate-day-learnings` (Playwright drift classes, webhook-env sudo, odoo-shell-over-SSH seams), `etsy-live-publish-traps`, `staging-e2e-runner-traps`.
4. `.claude/plans/006-implementation-playbook.md` — 9-phase loop still binding.

## Env recipe (unchanged)

```bash
cd /home/odoo/odoo_dev/other_projects/odoo19_esty
uv venv --system-site-packages /tmp/e2e-venv && \
  uv pip install --python /tmp/e2e-venv/bin/python \
    playwright xlrd openpyxl requests python-dotenv google-api-python-client google-auth && \
  /tmp/e2e-venv/bin/playwright install chromium
```
System pip broken (OpenSSL). Staging: key `secrets/ssh-key-2023-02-24.key`, `ubuntu@129.150.63.207`,
container `esty19_odoo`, DB `esty_odoo19` (NEVER `demo_esty`). mhf/mhc dirs need `--rsync-path="sudo rsync"`.
Playwright UAT specs: run from `tests/e2e/`, `--workers=1`, export `.env` (`set -a; . ./.env; set +a`) for Gearment TCs; `RUN_ETSY_PUBLISH=1 E2E_LISTING_PRICE=19.99` for live publish TCs (price = company USD).

## Rules

- One item per slice; 9-phase loop; commit per item on `feature/006-master-plan-coding`, ff `main` after each.
- Evidence per run under `docs/engineering/uats/`; screenshots `docs/screenshots/<date>/`; findings.md per surprise; /learn per slice.
- Honest flips only: a spec row goes `done` only on evidence from a run that exercised it.
- STOP conditions: anything contradicting an ADR; new Gearment probing beyond the support escalation; Etsy createListing refusals (capture body first).
- MF-E2E-4 stays untouched until the owner says start.
