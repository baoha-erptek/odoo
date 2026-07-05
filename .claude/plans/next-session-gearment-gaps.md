# Next session — Gearment dropship gaps (P-GEAR-PRINT-SIDES + P-GEAR-AUTOCONFIRM)

> Paste-ready prompt for a fresh session. Context: end-to-end Gearment audit 2026-07-05
> (findings: `specs/015-project-completion/findings.md`, entry 2026-07-05 (C); backlog rows
> in `specs/015-project-completion/spec.md`). Branch base: `main` (>= `f47b28836ed`).

---

## Prompt

Work the two Gearment dropship gaps from spec 015, in order. Follow the MP006 playbook
loop (plan → RED → GREEN → maker/checker review via the `loop-verification` skill →
verify → commit). Local-first on `namco_odoo19`, then deploy to staging `esty_odoo19`
(rsync per-module recipe, never `--delete`). Create a fresh feature branch off `main`.

### Slice 1 — P-GEAR-PRINT-SIDES (no owner decision needed; start immediately)

1. Add `print_location` Selection on `design.file`
   (`multichannel_hub_core/models/design_file.py`): front (default) / back — check the
   Gearment catalog location codes in `~/.claude/skills/` Gearment refs or the adapter
   (`PRINT_LOCATION_CODE_*`) before hardcoding the selection values; keep codes aligned.
2. Surface it in UI: design.file form + the order's design-files tab list (Vietnamese
   label via `i18n/vi.po` — vị trí in / mặt trước / mặt sau).
3. `multichannel_hub_fulfillment/services/gearment_payload_builder.py`: read
   `print_location` per file; fall back to the current positional default when unset
   (backward compatible). Reject duplicate same-side files per line with UserError.
4. Push guards in `sale_order.action_push_to_gearment` /
   `purchase_order.button_confirm` path:
   - Gearment-eligible line with ZERO approved design files → UserError naming the
     product (today the line silently drops from the payload).
   - Pre-push artwork URL reachability check (HEAD request, 2xx/3xx; GDrive links must
     be public). Soft option behind an ICP kill-switch if the owner worries about
     latency.
5. Tests: Two-Phase — payload builder unit tests (side mapping, fallback, dupe-side
   error, no-design error), plus an ORM test on the new field default. Re-run
   `--test-tags /multichannel_hub_fulfillment` (392 pre-existing green) +
   `/multichannel_hub_core`.
6. Update owner docs after shipping: flow-3b v3 page + HUONG_DAN_GIAO_HANG §5 gain a
   short "chọn mặt in" step; re-harvest a design-file form screenshot
   (`scripts/harvest_owner_screenshots.py --only giao-hang-design-file-form`); rebuild
   PDF (`bash docs/pdf/build-pdfs.sh`); commit (Confluence hook) + rsync v3/img to
   `ubuntu@129.150.63.207:/var/www/hatafa-docs/business-flows/` with the `../../img/` →
   `../img/` server-side sed (see memory `feedback_mockup_v3_uiux_session.md` #7).

### Slice 2 — P-GEAR-AUTOCONFIRM (BLOCKED on owner decision — ask FIRST via Telegram)

Ask the owner (DM 1013317517, bot token at
`~/.claude/channels/telegram/.env.bak.namco-*`) before coding:

- Odoo currently stops at Gearment DRAFT (`POST /orders/draft`);
  `adapter.confirm()` → `/orders/draft/labeled` is chargeable and never called.
  Production starts only after manual confirm in the Gearment dashboard.
- Options to offer: (a) explicit "Confirm at Gearment" button on the PO (BA-shipping
  gated, FR-017 method-level defense) — recommended first step; (b) auto-confirm on PO
  confirm; (c) cron with daily spend cap. Ask which, and whether a spend threshold
  needs a second approval.
- Whatever is chosen: idempotency (never confirm twice — key off
  `x_gearment_outbound_ref` + a new confirmed stamp), full request/response audit into
  `gearment.api.log`, failure → chatter + production-blocked flag, E2E runner section
  stays draft-only (never call confirm in tests — safety contract in
  `scripts/e2e_flow3b_dropship.py`).

### Traps to remember (from memory files — grep them first)

- `feedback_odoo19_test_gotchas.md` before writing tests; in-container test runs need
  `--http-port=8170+`; restart container after `-u` before browser checks.
- Gearment wire contract: `reference_gearment_draft_quote_wire_contract.md`
  (singular `address`, state_code ≤3 ASCII, nanos cents-scale on /price, read
  `response_summary` on 400).
- Reviewer/checker: verify scope against `git diff --stat HEAD`; default-REJECT
  (`~/.claude/skills/loop-verification/`).

### Exit criteria

- Slice 1: side selection visible + honored in payload; guards firing; tests green;
  docs + PDF + Confluence + hatafa updated; staging deployed.
- Slice 2: owner decision recorded in tracker + findings; if approved, confirm path
  shipped with audit + idempotency + gated trigger; if declined, backlog row updated
  to `blocked (owner)` with the written rationale.
