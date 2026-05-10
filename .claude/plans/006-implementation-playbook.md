# Implementation Playbook — Master Plan 006

**Created**: 2026-04-26
**Companion to**: [006-master-plan-tracking.md](./006-master-plan-tracking.md)
**Purpose**: Define the *how* (per-slice loop, agent dispatch, document hygiene). Tracker defines the *what* (which slice next, who owns it, blockers).

This file is the operating manual every session should follow when picking up master-plan work. If a session deviates, the deviation belongs in `findings.md` for the relevant spec, then propagated here.

---

## Operating principles

1. **Slice-sized, not spec-sized.** A slice = one User Story or one P-task from the tracker. Never "implement the whole spec."
2. **Single-workspace, long-lived feature branch off `main`** (revised 2026-04-27). All forward coding happens in `/home/odoo/odoo_dev/other_projects/odoo19_esty/` on branch `feature/006-master-plan-coding`, cut from `main` 2026-04-27. Commit per checkpoint to that feature branch; merge back to `main` after the W7 E2E sprint passes. Worktrees are still reserved for **rework / bugfix** of already-shipped work (see "Worktree usage" below). This supersedes the 2026-04-26 "commit directly to `main`" rule, which itself superseded the original "worktree per slice".
3. **Two-Phase Testing always.** Phase 1 (DB-level verification) + Phase 2 (ORM unit tests). See `rules/odoo/`.
4. **Commits per checkpoint, not per task.** A "checkpoint" is a self-contained, installable, test-passing state — typically one User Story or one foundational layer. Body cites the task IDs it covers. Land directly on `main`.
5. **Document drift is a defect.** If `tasks.md`, the tracker, an ADR, USER_GUIDE, or memory contradicts what was just implemented, fix the doc in the same commit (or the next one if it would balloon the diff).
6. **Capture surprises immediately.** Every slice exits with `/learn` and (if anything was non-obvious) an entry in `specs/<spec>/findings.md`.
7. **Code first, E2E later.** Finish the coding tasks for ALL active specs (002 + 005 + 003 + 004a) before moving to end-to-end testing. E2E is its own phase, not interleaved per slice. Per-slice tests stay at Phase 1 (DB) + Phase 2 (ORM unit) — those are mandatory.
8. **Dispatch runs to completion without intermediate questions** (added 2026-05-08, owner directive). Once `/dispatch-slice` is invoked, run the full 9-phase loop end-to-end. Pick the recommended option for every in-slice choice (the one that would have been listed first in an `AskUserQuestion`); record the choice + rejected alternatives in `findings.md` and the commit body. Out-of-scope issues found mid-slice get a tracker `todo` row, not a pause. STOP-and-escalate is preserved (see "When the playbook breaks") for *contradicting* ADRs / *missing* preconditions / data-destroying ambiguity — pause-and-ask on minor UX or scope-trim choices is forbidden during dispatch. See memory `feedback_dispatch_run_to_completion.md`.

## Owner voice — E2 v1.2 red-feedback alignment (2026-05-03)

Source: `.0temp/E2_Quy_trinh_san_xuat_edit.pdf` (Owner red+green markup on
the v1.2 production-process guide). Companion artifact sent back to Owner:
`.0temp/E2_Quy_trinh_san_xuat-v2.docx` (verbatim red+green excerpt + gap
table). Re-read this section at slice dispatch when the slice touches one
of the themes below; cite the row in the commit body.

| Red theme | Slice | State | Action |
|---|---|---|---|
| File handover loss / re-upload (B7, B14) | P1-02a, P1-02b | done | — |
| **PD A4 print batch — download all + auto-layout (B8)** | **P1-02d** | **TODO** | **Re-prioritize: Owner explicitly red-flagged. Move from "not on E2E critical path" into W4 polish.** |
| **Auto status transitions on workorder finish (B9)** | **(none yet — propose `P1-AUTO-TX`)** | **uncovered** | **Spawn slice: server action on `mrp.workorder.button_finish` advances `sale.order.x_pipeline_state_id`. Spec lives in `D2_production_flow.md`; no P-task today.** |
| Auto-push order to partner (B10) | P0-18, P0-18b2c | done | — |
| Tracking dashboard / state visibility (B12) | P1-03 | done | — |
| Tracking import from carrier Excel (B11) | P2-01..05 | TODO (planned W6) | — |
| **Customer Message Hub — 19-shop aggregator (B13)** | **§8 Q16 + ADR-008a §1 — no slice ID** | **architectural-only** | **Owner-decision needed: scope (export-only vs full inbox) before spawning slice. Treat as W3-extension once Owner answers.** |
| Per-role ACL on `sale.order` — 1-sheet collision (A6, B1) | P1-07, P1-08 | TODO | — |
| **Unified Operations Dashboard — merge Order + Tracking into one (CEO directive 2026-05-03)** | **P1-DASH-MERGE (rework of P1-01 + P1-03)** | **TODO — slice scoped, ready to dispatch** | **CEO-confirmed view-merge-only scope: single sale.order list with tracking columns inlined from `sale.order.fulfillment` (related fields, model preserved); saved filters per role replace split menus; bulk Mark Shipped + Confirm + Push to Gearment on unified list; delete `menu_order_dashboard` + `menu_tracking_dashboard`. Land **before W7 E2E** so the sprint exercises final topology. Memory: `feedback_ceo_unified_dashboard.md`.** |
| AI analytics over orders / messages / defects (B15) | deferred Phase 3+ | uncovered | Acknowledge to Owner; no action this wave unless Owner pulls it forward |
| Sub-state runtime config — CHỜ FILE … VN-Packed 1 (A9) | ADR-010 default seed | architectural | Code slice for admin UI not yet IDed |
| 8 MB Discord limit (B6) | P1-02a (10 MB cap + GDrive route) | done | — |
| Auto-feed from email (B2) | ADR-008a v2 + Spec 005 (P0-14..17) | done plumbing | Email parser stays as permanent failover |

**Doc-drift rule reminder**: if a slice touches one of these themes, the
slice's commit body must cite the row above ("Owner red theme B8") so the
audit trail is preserved.

**Open gaps Owner is waiting on**:
1. **B8 / P1-02d** — re-prioritize call.
2. **B9 / propose P1-AUTO-TX** — slice-spawn approval.
3. **B13 / Customer Message Hub** — scope decision (export-only vs full inbox).

**Closed 2026-05-03**:
- **CEO Unified Dashboard / P1-DASH-MERGE** — scope confirmed view-merge-only; timing before W7. Ready to dispatch as a slice.

**Vote-weighting rule (CEO 2026-05-03)**: when departmental requests (BA / PD / RD) conflict with CEO product-vision on **topology** (one dashboard vs many, one model vs split, one menu vs nested), CEO wins. Departments still own field-level ergonomics inside the chosen topology. Memory: `feedback_ceo_unified_dashboard.md`.

---

### Worktree usage (revised 2026-04-26)

Worktrees are now created **only** for:
- **Rework** of a feature already merged to `main` that needs invasive changes without disturbing forward work (e.g., refactoring a model after consumers exist).
- **Bugfix** branches that need to ship hotfixes while forward work continues.

Naming for rework/bugfix worktrees: `odoo19_esty-<reason>-<slug>` on branch `<reason>/<slug>` (e.g., `bugfix/etsy-token-refresh`). Branch off `main`. Merge back via fast-forward or rebase.

Do **not** create per-slice forward-work worktrees. The previous Wave 1 / Wave 2 worktree pattern is retired; their work has been merged to `main` and the worktrees pruned.

---

## Per-slice execution loop (the 9 phases)

### Phase 0 — Dispatch
- Read tracker. Pick the highest-priority slice whose `Depends on` is satisfied.
- Verify branch: `git branch --show-current` returns `feature/006-master-plan-coding` (revised 2026-04-27). Working tree clean (`git status` shows no uncommitted changes from a previous slice).
- Stay in `/home/odoo/odoo_dev/other_projects/odoo19_esty/` (the main workspace). Do **not** create a worktree for forward work (exception: see "Parallelism modes" below).
- TaskCreate items: one per slice task + one per exit-criterion check.
- **Automation**: invoke the `/dispatch-slice` skill (`.claude/skills/dispatch-slice/SKILL.md`) to perform this phase deterministically. Telegram-triggered dispatch (DM bot `dispatch <slice-id>` or `dispatch next`) routes through the same skill in the active session.

### Phase 1 — Plan
- Spawn `planner` agent (Opus-class for cross-spec, Sonnet-class for in-spec).
- Inputs: spec.md, plan.md, tasks.md (slice subset), data-model.md, relevant ADRs, recent findings.md.
- Output: tactical plan (file list, agent dispatch order, risks, exit criteria).

### Phase 2 — RED
- Spawn `tdd-guide` (Sonnet) — write failing tests **first**, both phases.
- Run tests; confirm they fail for the right reason.

### Phase 3 — GREEN
- Implement minimum to pass. Mark `[X]` in `specs/<spec>/tasks.md` as each task lands.
- For multi-file edits use parallel Edit calls when files are independent.
- Default to **Sonnet executor**; consult Opus only when the planner explicitly flags an architecture decision (this is our Advisor-pattern equivalent).

### Phase 4 — Review (parallel)
- `code-reviewer` (Sonnet) + `security-reviewer` (Opus when sudo/ACL/raw-SQL touched, Sonnet otherwise) in parallel.
- Block on CRITICAL/HIGH per `rules/common/code-review.md`.
- Fix in place; do not re-spawn the slice.

### Phase 5 — Verify
- Module update in container:
  ```bash
  docker exec namco_odoo19 odoo -d namco_odoo19 -u <module> --stop-after-init
  docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /<module> --stop-after-init
  ```
- ruff: `ruff check custom_addons/<module>/`
- Debug-statement scan: hook fires on `Stop`, but a manual `grep -rE "_logger\.info\(|^[[:space:]]*print\(" custom_addons/<module>/` is a belt-and-braces step.

### Phase 6 — Commit
- One conventional commit per checkpoint:
  ```
  [<module>] <type>(<scope>): <imperative description>

  Cites tasks T0XX–T0YY. Body explains the why (1–3 short paragraphs).
  Notes deviations vs spec. Lists deferred work.
  ```
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- No Claude attribution (per `git-workflow.md`).
- If a hook fails, fix root cause and create a NEW commit; never `--amend` past hooks.
- **Mid-slice exit (any reason — session crash, owner interrupt, blocker discovered after Phase 2/3 work has begun)**: commit a WIP checkpoint `[<module>] chore(wip): P<slice-id> phase <N> partial — <next step>` before the session ends. The next session resumes from `git log` + tracker, never from memory or open editor state.

### Phase 7 — Document
Update in the same checkpoint commit (or the next one if it would balloon):
- `specs/<spec>/tasks.md` — `[X]` marks; partial = `[~]` with reason; deferred = `[~]` + target slice
- `.claude/plans/006-master-plan-tracking.md` — task `state`, `last reviewed` date, blocker rows, **Change-log entry**
- `specs/006-master-plan/MASTER_PLAN.md` — **status snapshot at the top of the slice's Phase section** (e.g., add `✅ P1-04 Address-change approval landed YYYY-MM-DD` under the relevant Phase). The MASTER_PLAN is the strategy doc; the tracker is the execution log; both must agree on what's done.
- ADRs in `specs/006-master-plan/adrs/` — only if architecture diverged
- `specs/<spec>/quickstart.md` — only if env vars / setup steps changed
- `custom_addons/<module>/static/description/USER_GUIDE.md` — only if user-facing flow changed
- `specs/<spec>/findings.md` — append surprises, blockers, deferred decisions (create file if absent)

**Doc-drift rule**: if you can't summarize the slice in one MASTER_PLAN line, the slice is too vague — document the gap in `findings.md` instead and note `MASTER_PLAN n/a (architectural-only)` in the tracker.

### Phase 8 — Learn
- Run `/learn` to extract reusable patterns into memory.
- Threshold: at least one explicit insight, or a deliberate "no new patterns" note.
- Memory entries follow the auto-memory rules (`feedback`/`project`/`reference`/`user`).

### Phase 9 — Land
- Forward work commits to `feature/006-master-plan-coding` per checkpoint (revised 2026-04-27). No PR ceremony per slice. Merge back to `main` (fast-forward or rebase) after the W7 E2E sprint passes.
- `/review` skill before each commit if the diff is large (>300 lines) or touches security-sensitive surfaces.
- For **rework / bugfix** worktrees only: branch off `main` (not the feature branch). Use `/ship` to push + open PR with VERSION/CHANGELOG bump.
- E2E phase (after all spec coding is done): a dedicated E2E sprint runs `e2e-runner` agent across critical user flows, fixes regressions, then `/ship` once per E2E pass before the feature branch merges to `main`.
- If the feature branch grows fast, run `/retro` weekly to surface drift.

---

## Slice exit criteria (machine-checkable)

A slice is **done** only when **all** are true:

- [ ] Every slice task marked `[X]` in `tasks.md`
- [ ] Tests pass; coverage ≥80% on changed lines
- [ ] Module installs cleanly (`-u <module> --stop-after-init` exit 0)
- [ ] `ruff check` clean
- [ ] No `_logger.info(` / `print(` in models/services
- [ ] Tracker `state` updated; blockers documented
- [ ] ACLs defined for any new model; sudo() commented; raw SQL commented
- [ ] At least one `/learn` insight (or explicit "none" note)
- [ ] `findings.md` updated if anything surprised us
- [ ] **Frontend view sanity (Odoo 19 OWL)**: every `decoration-*` and dynamic
  attribute (`invisible=`, `readonly=`, `column_invisible=`) referencing a
  non-trivial expression has its referenced fields **explicitly loaded** in
  the same view, including dotted M2O paths via either a direct
  `<field name="rel_id.field" invisible="1"/>` or a related/computed mirror
  on the line model. OWL 2 errors at view-render with "field is undefined"
  when this is missed; the failure is invisible to module-install tests
  because the registry knows the field — only the JS client trips. (See
  memory entry #61.)
- [ ] **Deploy hygiene** (when rsync'ing changes to a remote Odoo container):
  after `-u` of the new code, `DELETE FROM ir_attachment WHERE name LIKE
  'web.assets%'` and `docker restart <odoo>` so the JS bundle is
  regenerated. Otherwise browsers see stale bundles unaware of the new
  fields and raise OwlError. Tell the operator to hard-reload after the
  deploy. (See memory entry #62.)

Failure of any criterion → slice does not exit. Fix or split.

---

## Agent dispatch (model-tiered Advisor pattern)

| Tier | Models | When | Examples |
|---|---|---|---|
| **Light** | Haiku | Mechanical edits, file reads, simple greps, ruff fixups | inline tool calls, no agent needed |
| **Executor** | Sonnet | Most agent work — `tdd-guide`, `code-reviewer`, `e2e-runner`, in-spec `planner`, `refactor-cleaner`, `doc-updater`, `odoo-build-error-resolver` | per-slice loop, default tier |
| **Advisor** | Opus | Cross-spec planning, ADR decisions, security with CRITICAL flag, novel architecture | `architect`, escalated `security-reviewer`, master-plan `planner` |

**Rule of thumb** — start with Executor. Escalate to Advisor only when:
- Planner flags an unresolved architecture question.
- Reviewer raises a CRITICAL flag that requires re-design rather than patch.
- A slice introduces a new ADR.

This is the closest we can get to the Anthropic Advisor tool (`advisor_20260301`) inside Claude Code today. The literal API tool may become useful in our **services layer** (LLM-assisted email parser fallback, anomaly classifier) — capture as a future ADR.

---

## Parallel execution (revised 2026-04-26)

In the single-workspace pattern, true parallelism within forward work is no longer possible — only one branch (`feature/006-master-plan-coding`) is active at a time. Achieve parallelism instead via:

1. **Parallel research / planning agents**: spawn multiple `planner`, `architect`, `code-reviewer` agents in a single message when they read disjoint files. They produce advice; the orchestrator integrates results sequentially.
2. **Sequential checkpoints, fast cadence**: complete one checkpoint, commit, immediately start the next. The 9-phase loop is short enough that sequential work approximates parallel throughput.
3. **Rework / bugfix parallelism**: a hotfix worktree may run in parallel with forward main work, since they ship via different paths (rework worktree → `/ship` PR; forward → direct main commit).

Conflicting work that must always serialize on the feature branch:
- Two checkpoints touching `services/order_creator.py`.
- ADR-changing checkpoints with overlapping module-decomposition (ADR-003) impact.
- Anything modifying `__manifest__.py` data list at the same time.

### Parallelism modes (codified 2026-04-29)

Three sanctioned modes only. Anything else is anti-playbook and produces rework.

**Mode 1 — In-slice parallel agents** (default; no setup)
- Single message, multiple `Agent` calls when files are disjoint.
- Standard for Phase 4: `code-reviewer` + `security-reviewer` in parallel.
- Extend to Phase 1 (`planner` + `architect`) and Phase 7 (`doc-updater` + tracker edit) when the planner explicitly OK's it.

**Mode 2 — Disjoint-module slice parallelism via worktrees** (case-by-case; owner-approved)
- Allowed when both candidate slices touch **different modules** AND **no shared models in `multichannel_hub_core`** AND **no `__manifest__.py` data-list conflict**.
- Example green-light: P1-02b (design.file routing in `multichannel_hub_core`) ↔ P0-18b (Gearment webhook in `multichannel_hub_fulfillment`).
- Example red-light: P1-02b ↔ P1-03 (both extend `sale.order` in `multichannel_hub_core`) → must serialize.
- Mechanic: secondary worktree off `feature/006-master-plan-coding` named `feature/006-mp-coding-<slice-id>`. Rebase onto feature branch before merge. Owner approves the parallel-OK pair before kickoff.

**Mode 3 — Hotfix worktree off `main`** (already permitted; unchanged)
- Branch off `main`, ship via `/ship`, rebase forward into feature branch if needed.

**Reject**: per-slice forward-work worktrees off feature branch as routine practice. Mode 1 + sequential cadence already approximates ~90% of true parallel throughput without merge-tax.

---

## Why no persistent "Project Manager" agent (rationale 2026-04-29)

Future sessions will be tempted to build a long-running PM daemon. Don't. This is intentional.

| Concern | Why it disqualifies a PM daemon |
|---|---|
| Context bloat | Long-running session crosses 5-min cache TTL repeatedly; cost scales linearly with idle time |
| Source-of-truth duplication | PM in-memory state would shadow tracker/`tasks.md`, creating drift — the same problem the Doc-drift rule (Phase 7) explicitly bans |
| Concurrency hazard | PM dispatching while a developer-session is mid-slice on the feature branch reproduces the parallel-slice problem the Parallelism modes section forbids |
| Diminishing return | Phase 0 dispatch is ~3 minutes manual work, ~2x/day. Daemon idle cost > automation savings |

**Replacement**: stateless rituals.
- Pick next slice → `/dispatch-slice` skill at session start.
- Track state → tracker (already mandatory).
- Spawn agents → playbook 9-phase loop (already mandatory).
- Cross-session memory → auto-memory + `/learn`.
- Tmux orchestration → only Mode 2 worktree pair when owner approves; on-demand `dmux`, never standing service.

Net: **playbook + tracker + auto-memory + `/dispatch-slice` skill IS the PM**. No process to keep alive, no state to lose, no bloat to manage.

---

## Document update matrix

| Change type | Touch |
|---|---|
| Slice landed | tasks.md `[X]`, tracker `state→done` + change-log entry, **MASTER_PLAN.md Phase status snapshot** |
| New behavior visible to user | tasks.md `[X]`, USER_GUIDE.md, CHANGELOG via `/ship` |
| Plan deviation | tracker Notes column + spec `findings.md` |
| Architecture decision | new ADR in `specs/006-master-plan/adrs/` (numbered next), tracker Decision-log pointer updated, MASTER_PLAN.md banner if it shifts the roadmap |
| Surprise / pattern worth re-using | `/learn` → memory |
| Blocker discovered | tracker State→`blocked`, dependency row updated, escalate to user |
| Module decomposition (ADR-003) | new module dir, manifest, security/, tracker P0-20 progress |

---

## Wave plan (revised 2026-04-26 — single-workspace, sequential)

All forward work happens on `feature/006-master-plan-coding` in `/home/odoo/odoo_dev/other_projects/odoo19_esty/` (revised 2026-04-27). Sequential checkpoints, fast cadence. **Goal: finish ALL spec coding before opening the E2E phase, then merge feature branch to `main`.**

| Wave | Slices | Tier | Status |
|---|---|---|---|
| **W1 (RED done)** | Spec 002 US3 (T025–T027) + US4 (T028–T031) — RED tests committed `aecbe579fea` | Executor | GREEN next, blocked on docker-mount strategy (see findings) |
| **W2 (planning done)** | Spec 005 sandbox P0-14..17 — tasks.md (110 tasks) + architect findings landed on main | Advisor | Blocked on Owner Q1–Q5 decisions |
| **W3** | Spec 002 US5 dedup wizard (CSV-only) + US6 migration wizard (batch-resumable, 17K backlog) | Advisor for batching | After W1 GREEN |
| **W4** | Spec 002 US7–US10 + polish (T032–T067) | Executor | After W3 |
| **W5** | Spec 005 sandbox GREEN — Foundational + US1 + US2 + US5 + US8 (T001–T062 from spec 005 tasks.md) | Executor + Advisor for OAuth | After W2 decisions |
| **W6** | Spec 003 dashboards coding + Spec 004a tracking import coding | Executor | After W4 + W5 |
| **W7 (E2E gate)** | All-spec E2E sprint: critical user flows, regression sweep | `e2e-runner` agent | After W6 — coding-complete gate |
| **W8+** | Phase 1 production cutover (blocked on E1 Etsy scope approval) | Executor + Advisor | External dependency |

---

## When the playbook breaks

If a slice cannot follow this loop (e.g., spec is missing tasks.md, scope is ambiguous, blocker emerges mid-implementation):

1. **Stop.** Do not improvise.
2. Update tracker: state→`blocked`, name the blocker.
3. Append to `specs/<spec>/findings.md`.
4. Decide: regenerate tasks.md (`/speckit-tasks`), open ADR, or escalate to user.
5. Resume only when the blocker has a documented resolution.

### Bug surfaces post-slice (or during E2E)

Lightweight bugfix flow inspired by `spec-kit-bugfix` (taxonomy adopted; tooling not — patterns implemented inline using existing playbook artifacts):

1. **Report BEFORE patching.** Append a `## Bug-YYYY-MM-DD-<short-slug>` block to the relevant `specs/<spec>/findings.md` with these fields:
   - **Type:** one of `spec_gap` / `spec_conflict` / `implementation_drift` / `untested_flow` / `dependency_issue` (per spec-kit-bugfix taxonomy).
   - **Severity:** `BLOCKER` / `MAJOR` / `MINOR`.
   - **Symptom:** verbatim error / user-visible failure.
   - **Suspected slice:** which slice ID introduced the field/view/code involved.
   - **Trigger surface:** what flow exercised the bug for the first time.
   - **Root cause:** filled after investigation (pre-patch line for "TBD").
2. **Patch surgically.** Fix code + add a `**Patch:** <commit hash>` line to the bug report. Cite the bug-id in the commit body.
3. **Test added.** Add a regression test where feasible; write `**Test added:** <commit hash>` or `**Test added:** none — manual verify` with one-sentence justification.
4. **Prevention.** If the bug class is reusable across modules → add a memory entry; if it changes the Slice exit-criteria checklist → update this playbook. Cite the memory entry # in the bug report's `**Prevention:**` field.
5. **Reopen tasks** (don't delete) when a falsely-completed task surfaces during the bugfix. Add a new task ID `T-<original-slice>-<seq>-fix` and annotate the original `[~]` with `(reopened — Bug-YYYY-MM-DD-<slug>)`.
6. **Hotfix-on-trunk vs new slice:** BLOCKER + small surface → patch directly on `feature/006-master-plan-coding` with the bug-id in the commit body. MAJOR/MINOR with broader scope → spin a new slice (e.g., P1-03d).

This flow is **inline** — no external tooling, no `/speckit.bugfix.*` commands required. The spec-kit-bugfix repo (https://github.com/Quratulain-bilal/spec-kit-bugfix) was reviewed 2026-05-01 but not installed (untrusted external code; existing playbook + tracker + findings.md + memory cover the same ground).

### E2E run defect intake (added 2026-05-10)

The post-slice flow above covers the *fix mechanics*. This subsection defines the *intake*: how a defect surfaced during a multi-slice E2E run gets captured, triaged, and routed without dropping. E2E exercises every slice end-to-end and *will* surface bugs that per-slice unit tests didn't catch — the orphan-cron incident (memory `project_orphan_cron_methods.md`) is the canonical example of this failure mode.

**Defect lifecycle**:

```
[surfaced] → [triaged] → [routed] → [fixed] → [verified] → [closed]
   E2E       severity    spec/slice  9-phase   E2E re-run    tracker
                                     loop      of section    state=done
```

**Capture rules** (when a step in the E2E run fails or behaves unexpectedly):

1. **Stop the run** at the failing step. Do not continue past §N if §N is broken — downstream steps will mask the root cause.
2. **Capture evidence** as a single H2 entry in `docs/E2E_DEFECTS_<YYYY-MM-DD>.md` (one file per run date):
   - Symptom (one sentence)
   - Step / section ID (e.g., "§6 push to Gearment")
   - Repro recipe (exact xmlrpc call or UI click path)
   - Stack trace tail (last 30 lines of `docker logs esty19_odoo`)
   - Suspected cause (one sentence — guess is fine)
   - Severity (CRITICAL / HIGH / MEDIUM / LOW — see table)
   - Linked slice ID(s) it likely belongs to
3. **Mirror into tracker** under the **"E2E Defects in Flight"** subsection of `006-master-plan-tracking.md` so it survives session boundaries.
4. **Append to the relevant `specs/<spec>/findings.md`** under its **"E2E surfacing (live)"** subsection.

**Severity tags** (mirror code-review levels):

| Tag | Definition | Action |
|-----|------------|--------|
| **CRITICAL** | Data loss, security hole, crashes pipeline at this step or downstream, blocks all 4 ordertest2 receipts | Stop run; spawn hotfix slice **before** continuing. Same 9-phase loop, branch off `feature/006-master-plan-coding`. |
| **HIGH** | Functional bug visible to operator; workaround exists | Capture; finish run using workaround; open hotfix slice in next session. |
| **MEDIUM** | Cosmetic / non-blocking | Capture only; bundle into the next slice that touches the same area. |
| **LOW** | Polish / observation | Capture; defer to W7 polish sprint. |

**Routing rules** (where the fix belongs):

| Symptom origin | Owner / artifact |
|---|---|
| Etsy ingest / email / Gmail OAuth | `specs/001-etsy-order-migration/findings.md` + new slice `P0-FIX-<n>` |
| Operations dashboard (line-level, P1-01b) | `specs/003-dashboard-design-multichannel/findings.md` + amendment to P1-01 family |
| Design file upload / GDrive sync | `specs/003-dashboard-design-multichannel/findings.md` + slice `P1-OPS-DESIGN-FIX-<n>` |
| Pipeline state machine / routing | `specs/004-fulfillment-routing/findings.md` + slice `P1-DROP-FIX-<n>` |
| Gearment adapter / push / state machine / quote wizard | `specs/004-fulfillment-routing/findings.md` + amendment to P4-01-x family |
| Tracking import / GKE / logistics inbox cron | `specs/004-fulfillment-routing/findings.md` (P2-06 area) + slice `P2-FIX-<n>` |
| Cross-cutting (auth, ACLs, ICPs, cron wiring) | Append to `findings.md` of the spec where most-recent edits landed; default to `specs/006-master-plan/findings.md` if ambiguous |

**Regression-test contract**: every CRITICAL or HIGH fix MUST land with a Phase 1 (DB) **and** Phase 2 (ORM) test that fails on the broken commit and passes on the fix — exactly the standard 9-phase loop, no shortcut. The E2E re-run is *not* a substitute for unit tests (memory `feedback_e2e_pipeline_first.md` constrains scope but does not waive the per-slice test contract).

**ADR contradiction**: per memory `feedback_follow_master_plan_playbook.md`, if a defect contradicts an ADR — STOP and escalate. Tracker `state→blocked`, finding logged, owner pinged before any code change.

**Re-verification**: after a hotfix lands, re-run the failing E2E section in isolation (script supports `--from-section N`) before resuming the full run. Only mark the defect `closed` after the full run passes through that section.

---

## Change log

- **2026-04-26**: File created. Wave 1 + Wave 2 launched in parallel under this playbook.
- **2026-04-26 (revision 1)**: Workflow pivot — from "worktree per slice" to **single-workspace-on-main**. All forward coding now lands directly on `main` in the primary workspace. Worktrees reserved for rework / bugfix only. Wave 1 (RED tests) and Wave 2 (planning + findings + tasks.md) consolidated to `main` via rebase; wave worktrees and branches pruned. Wave plan rewritten as sequential. Added Phase 7 principle: "Code first, E2E later" — finish ALL spec coding before E2E sprint (W7 gate).
- **2026-04-27 (revision 2)**: Branching pivot — forward work moves from `main` to long-lived feature branch `feature/006-master-plan-coding` (cut from `main` 2026-04-27). `main` becomes the merge target, not the working branch, so it stays green during the multi-slice E2E coding push. Single-workspace pattern unchanged — we're still in `/home/odoo/odoo_dev/other_projects/odoo19_esty/`, just on a different branch. Merge back to `main` (fast-forward or rebase) after W7 E2E sprint passes. Memory `feedback_use_worktree_for_new_work.md` revised to match. P0-20 (`multichannel_hub_core` skeleton) was the first slice landed under this revision.
- **2026-04-29 (revision 3)**: Operating-model additions in response to owner's parallel-execution + Telegram-dispatch + persistent-PM questions. (1) Codified "Parallelism modes" subsection (Mode 1 in-slice agents / Mode 2 disjoint-module worktrees / Mode 3 hotfix). (2) Phase 0 references new `/dispatch-slice` skill (Telegram-trigger compatible). (3) Phase 6 adds explicit WIP-commit rule for mid-slice exits. (4) New "Why no persistent PM agent" section locks in the stateless-PM design (bloat / drift / concurrency / ROI). No code changed; doc-only revision.
- **2026-05-10 (revision 5)**: Added "E2E run defect intake" subsection under "Bug surfaces post-slice (or during E2E)". Defines run-time defect capture rules, severity tags, routing table, regression-test contract, ADR-contradiction escape hatch, and section-isolated re-verification path. Companion artifacts: `docs/E2E_DEFECTS_<date>.md` template + new tracker subsection "E2E Defects in Flight" + per-spec `findings.md` "E2E surfacing (live)" subsection. Owner directive 2026-05-10: "E2E test process can introduce bugs, make sure we have a way to track and flow to handle them in playbook." No code changed; doc-only revision.
- **2026-05-03 (revision 4)**: Aligned playbook to E2 v1.2 Owner red-feedback (`.0temp/E2_Quy_trinh_san_xuat_edit.pdf`). Added "Owner voice" traceability section with 12-row red-theme → slice mapping. Three uncovered surfaces surfaced for Owner: (1) **P1-02d (PD A4 batch)** re-prioritize from "not critical" to W4; (2) **propose new slice P1-11** for auto status transitions on `mrp.workorder.button_finish` (currently no P-task ID despite living in `D2_production_flow.md` design notes); (3) **Customer Message Hub (B13)** still architectural-only — needs Owner scope decision (export-only vs full inbox) before slice spawn. No code changed; doc-only revision. Companion deliverable: `.0temp/E2_Quy_trinh_san_xuat-v2.docx` sent to Owner for red-feedback re-confirmation. Tracker NOT mutated this revision — tracker edits wait for Owner answers on B8/B9/B13.
