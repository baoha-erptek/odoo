> **SUPERSEDED 2026-07-04 EOD** — MF-E2E-0/1/2/3a/3b all closed in the
> 2026-07-04 session (commits `1bfaecf`…`855b247`). Use
> `docs/NEXT_SESSION_PROMPT_CLOSEOUT.md` for the next session.

# Next Session Prompt — Main-Flow E2E Gate: MF-E2E-1 → 2 → 3a

**Created**: 2026-07-04 · **Owner directive**: flows 1–3 first, flow-4 later.
**Paste into a fresh session**: `dispatch MF-E2E-1` (or copy the Mission below).

---

## Mission

Execute the Main-Flow E2E Gate items in owner order: **MF-E2E-1 (tạo sản phẩm → publish) → MF-E2E-2 (nhận đơn) → MF-E2E-3a (in nội bộ)**. MF-E2E-3b stays blocked on E2 Gearment keys; **MF-E2E-4 is deliberately last** — do not start it. Each item = extend the sectioned python runner + one Playwright UAT spec + staging pass + evidence doc. T073 (BA sign-off umbrella) closes only when all five pass.

## Read first (in order)

1. `specs/015-project-completion/spec.md` — §"2026-07-04 Alignment Update" + MF-E2E gate table (dispatch order + per-item scope). 23 items are `shipped*` — code exists; the gate's job is to VERIFY them and flip to `done`.
2. `specs/015-project-completion/tasks.md` — MF-E2E-1/2/3a dispatch blocks (scope, deps, exit criteria).
3. `specs/015-project-completion/findings.md` — MF-E2E-0 staging traps (all still apply).
4. `.claude/plans/006-implementation-playbook.md` — 9-phase loop; runner/Playwright work counts as the RED/GREEN phases for gate items.
5. Memories: `staging-e2e-runner-traps` (env recipe + 4 traps), `srs-evidence-fabrication-audit` (verify claims by grep), `reference_staging_ssh_deploy`, `reference_etsy_shops_w_scope_gap` (shop-write APIs 403), `reference_etsy_createlisting_2025_readiness` (readiness_state_id).

## Baseline (verified 2026-07-04)

- Drop-ship runner **12/12 PASS** on staging `esty_odoo19`: `docs/engineering/uats/E2E_DEMO_DROP_SHIP_ORDERTEST2_2026-07-04.md`.
- Staging GDrive re-provisioned (SA json + env + libs); **pip installs in `esty19_odoo` are wiped on container recreate** — re-run the pip step if §5 starts failing (findings.md item 1).
- nginx webhook header fixed to `esty_odoo19`; 5 `demo_*@hatafax.demo` users seeded (pw `demo1234`).
- Runner waits are selector-based (`_settle()`); never reintroduce `networkidle`.

## Runner env recipe (local)

```bash
cd /home/odoo/odoo_dev/other_projects/odoo19_esty
uv venv --system-site-packages /tmp/e2e-venv && \
  uv pip install --python /tmp/e2e-venv/bin/python \
    playwright xlrd openpyxl requests python-dotenv && \
  /tmp/e2e-venv/bin/playwright install chromium
# run (drop-ship baseline example):
/tmp/e2e-venv/bin/python scripts/e2e_demo_drop_ship_ordertest2.py \
  --db esty_odoo19 --gke-xls .0temp/raw/sample_bc_don_hang2026_04_08.xls
```
System pip is broken (OpenSSL) — always use the uv venv. Staging SSH: key `secrets/ssh-key-2023-02-24.key`, `ubuntu@129.150.63.207`, container `esty19_odoo`, DB `esty_odoo19` (NEVER `demo_esty`).

## Per-flow marching orders

### MF-E2E-1 — flow-1 tạo sản phẩm → publish (L, do first)
- New sectioned runner `scripts/e2e_flow1_publish.py` (mirror drop-ship runner shape): product create → categ → SKU auto-derive (MUG → MUG-CR → MUG-CR-F11) → variants → `etsy_publish_wizard` draft-only (create_draft → upload_images → push_inventory) → **verify draft via Etsy GET** → `action_run_publish` → active → inventory-only re-push → listing-drift report check.
- Playwright: reuse/extend `tests/e2e/uat_huong_dan_tao_san_pham.spec.ts` + `uat_real_apron_publish.spec.ts`.
- **Etsy hygiene**: staging shop JaHandmadeArt (`etsy_api_shop_id` on etsy.shop, memory `reference_etsy_shop_id_mapping`); DELETE test listings after run; watch `readiness_state_id` (ESTY-188) and 400s — capture response body first (memory `capture_response_body_before_blackbox_probe`).
- Exit: runner sections PASS ×2 consecutive; Playwright green ×2; **flip the 13 `shipped*` publish/hub/XLS items → `done` in spec 015**; decide SKU-drift-job question (ADR note if dropped).

### MF-E2E-2 — flow-2 nhận đơn (M)
- Runner: API receipt sync → order + partner dedupe + pipeline classification; duplicate idempotency; **manual email-fallback switch** (admin toggles `etsy.shop.active_source`→email, email cron parses fixture, order created, toggle back). Reuse drop-ship runner §1–3 bodies.
- Playwright: extend `uat_huong_dan_don_hang_etsy.spec.ts` with the fallback walk.
- Staging portion runs now; production-shop assertions wait for P1-11 (do not block on it).
- Exit: both paths PASS ×2; sync-health rows written for both.

### MF-E2E-3a — flow-3a in nội bộ (M)
- **Precondition: ENV-FIX-MRP (owner MRP routes on staging)** — check first (`mrp.route` / MTO route on a Route-A product); if absent, ping owner via AskUserQuestion/Telegram and continue prep with fixtures.
- Runner: Route A order → design approve → MO auto-created → complete → Delivery Order validated → drop GKE tracking Excel **with matching order refs** into GDrive inbox (fix MF-E2E-0 residue: sample file matched 0/9) → poller import (≤15 min) → carrier detect → Etsy tracking push flags.
- Playwright: extend `uat_huong_dan_giao_hang.spec.ts` (picking + tracking screens).
- Exit: end-to-end PASS ×2; `etsy_tracking_pushed_at` set; tracking on unified dashboard.

## Rules

- One gate item per slice; 9-phase loop; commit per item on `feature/006-master-plan-coding` (ff `main` after each — branch currently == main @ `5df0674`+).
- Evidence: report per run under `docs/engineering/uats/`, screenshots under `docs/screenshots/<date>/`.
- Update per item: spec 015 gate row state, findings.md surprises, /learn memory.
- STOP conditions: Etsy API refuses createListing on staging creds; ENV-FIX-MRP absent and owner unreachable; anything contradicting an ADR. Escalate, don't improvise.
- **Do NOT start MF-E2E-4** (owner: later) and MF-E2E-3b (blocked E2).
