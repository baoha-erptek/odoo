# Implementation Playbook — Master Plan 006

**Created**: 2026-04-26
**Companion to**: [006-master-plan-tracking.md](./006-master-plan-tracking.md)
**Purpose**: Define the *how* (per-slice loop, agent dispatch, document hygiene). Tracker defines the *what* (which slice next, who owns it, blockers).

This file is the operating manual every session should follow when picking up master-plan work. If a session deviates, the deviation belongs in `findings.md` for the relevant spec, then propagated here.

---

## Operating principles

1. **Slice-sized, not spec-sized.** A slice = one User Story or one P-task from the tracker. Never "implement the whole spec."
2. **Worktree per slice.** Memory rule: branch off `main`, never reuse a checked-out branch. Slug aligns with spec id (`002-us3-us4`, `005-oauth-sandbox`).
3. **Two-Phase Testing always.** Phase 1 (DB-level verification) + Phase 2 (ORM unit tests). See `rules/odoo/`.
4. **Commits per checkpoint, not per task.** A "checkpoint" is a self-contained, installable, test-passing state — typically one User Story or one foundational layer. Body cites the task IDs it covers.
5. **Document drift is a defect.** If `tasks.md`, the tracker, an ADR, USER_GUIDE, or memory contradicts what was just implemented, fix the doc in the same commit (or the next one if it would balloon the diff).
6. **Capture surprises immediately.** Every slice exits with `/learn` and (if anything was non-obvious) an entry in `specs/<spec>/findings.md`.

---

## Per-slice execution loop (the 9 phases)

### Phase 0 — Dispatch
- Read tracker. Pick the highest-priority slice whose `Depends on` is satisfied.
- Verify base: `git branch --show-current` on a clean worktree off `main`.
- Create worktree if missing:
  ```bash
  cd /home/odoo/odoo_dev/other_projects/
  git -C odoo19_esty worktree add ../odoo19_esty-<spec>-<slug> -b <spec>-<slug> main
  ```
- TaskCreate items: one per slice task + one per exit-criterion check.

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

### Phase 7 — Document
Update in the same checkpoint commit (or the next one if it would balloon):
- `specs/<spec>/tasks.md` — `[X]` marks
- `.claude/plans/006-master-plan-tracking.md` — task `state`, `last reviewed` date, blocker rows
- ADRs in `specs/006-master-plan/adrs/` — only if architecture diverged
- `specs/<spec>/quickstart.md` — only if env vars / setup steps changed
- `custom_addons/<module>/static/description/USER_GUIDE.md` — only if user-facing flow changed
- `specs/<spec>/findings.md` — append surprises, blockers, deferred decisions (create file if absent)

### Phase 8 — Learn
- Run `/learn` to extract reusable patterns into memory.
- Threshold: at least one explicit insight, or a deliberate "no new patterns" note.
- Memory entries follow the auto-memory rules (`feedback`/`project`/`reference`/`user`).

### Phase 9 — Land
- `/review` skill against base branch — gate before push.
- `/ship` to push + open PR with VERSION/CHANGELOG bump (when the spec slice is user-visible).
- If trunk merges every slice, run `/retro` weekly.

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

## Parallel execution

When two slices touch disjoint modules / files:

1. Worktrees in **separate directories** (already enforced by memory rule).
2. Spawn both planners in **one message, two Agent calls** — they execute concurrently.
3. Each slice runs the full 9-phase loop independently.
4. Synchronize at landing: `/ship` PRs in sequence, not parallel, to avoid CI conflicts on `main`.

Disjoint examples (safe to parallelize):
- Spec 002 US3 (product config) + Spec 005 sandbox (OAuth client) — different modules, different files.
- Spec 003 dashboard XML + Spec 004a tracking import — different views, different services.

Conflicting examples (must serialize):
- Two slices both editing `services/order_creator.py`.
- ADR-changing slices with overlapping module decomposition (ADR-003) impact.

---

## Document update matrix

| Change type | Touch |
|---|---|
| New behavior visible to user | tasks.md `[X]`, USER_GUIDE.md, CHANGELOG via `/ship` |
| Plan deviation | tracker Notes column + spec `findings.md` |
| Architecture decision | new ADR in `specs/006-master-plan/adrs/` (numbered next), tracker Decision-log pointer updated |
| Surprise / pattern worth re-using | `/learn` → memory |
| Blocker discovered | tracker State→`blocked`, dependency row updated, escalate to user |
| Module decomposition (ADR-003) | new module dir, manifest, security/, tracker P0-20 progress |

---

## Wave plan (rolling 4 weeks from 2026-04-26)

| Wave | Slices | Worktree | Tier | Why |
|---|---|---|---|---|
| **W1** (current) | Spec 002 US3 product config (T025–T027) + US4 customer/partner (T028–T031) | `odoo19_esty-002-us3-us4` on `002-us3-us4` | Executor | Small, independent, unblocks US6 migration |
| **W2** (parallel with W1) | Spec 005 sandbox bootstrap: `/speckit-tasks` → tasks.md, then OAuth/PKCE + `EtsyApiClient` + `etsy.api.log` (P0-14..17) | `odoo19_esty-005-sandbox` on `005-etsy-sandbox` (off `main`) | Executor + Advisor for OAuth design | No prod risk (dev token); parallelizable |
| **W3** (after W1) | Spec 002 US5 dedup wizard (CSV-only, no auto-merge per DA #9) + US6 migration wizard (batch-resumable, DA #3) | `odoo19_esty-002-migration` | Advisor for batching strategy | Critical path — 17K orders backlog |
| **W4** | Spec 002 US7–US10 + polish | `odoo19_esty-002-polish` | Executor | Cleanup before Phase 1 cutover |
| **W5+** | Phase 1 work (Spec 003 dashboards, Spec 005 production cutover when E1 approved) | per-slice | Executor + Advisor | Blocked on E1 + W4 exit |

---

## When the playbook breaks

If a slice cannot follow this loop (e.g., spec is missing tasks.md, scope is ambiguous, blocker emerges mid-implementation):

1. **Stop.** Do not improvise.
2. Update tracker: state→`blocked`, name the blocker.
3. Append to `specs/<spec>/findings.md`.
4. Decide: regenerate tasks.md (`/speckit-tasks`), open ADR, or escalate to user.
5. Resume only when the blocker has a documented resolution.

---

## Change log

- **2026-04-26**: File created. Wave 1 + Wave 2 launched in parallel under this playbook.
