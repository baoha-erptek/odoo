---
title: "Execution Playbook — Spec 006 family"
date: "2026-04-26"
status: in-force
purpose: "ONE chosen skill chain for this project. Stops the buffet-of-options pattern. When in doubt about which tool to invoke for what task, this is the answer."
audience: "Future-Claude, future-Architect, anyone driving spec evolution"
---

# Why this playbook exists

The synthesis review (2026-04-26) and Stage-1 driver presented multiple tool options for almost every task: `/sc:design` *or* manual; `/plan-eng-review` + `/plan-ceo-review` + `/sc:analyze` + `/codex` for review; "Path A vs Path B" for clarification. The Owner pushed back: **pick one and apply it; add to playbook if needed; don't go with many options like this.**

This file is the answer. One chosen tool per task category. Use it. Don't open the menu again unless this playbook is wrong (in which case, edit it, don't add an alternative path).

---

# The chain

| Stage | Task | Chosen tool | Why this one |
|---|---|---|---|
| **Clarify** | Owner / PD answers needed before architecture can lock | **Offline question pack** (markdown file in `specs/006-master-plan/clarifications/`) | We work on `main` (per memory note 2026-04-26); `/speckit-clarify` requires a feature branch and caps at 5 questions. Offline packs are richer, parallelizable across owners, and feed multiple ADRs at once. |
| **Architect** | Write ADR / SRS section / data-model | **Manual authoring** by architect or Claude | ADRs are short focused docs (~200–500 lines). Tooling (`/sc:design`) adds overhead with no proven value. Manual authoring matches the existing ADR-001..ADR-008 style. |
| **Plan refresh** | Spec-level plan needs regeneration after ADRs land | **`/speckit-plan`** | Already proven by commit `bfda694`. Operates on the active feature spec; works fine on `main` (only `/speckit-clarify` has the branch requirement). |
| **Tasks refresh** | Spec task list needs regeneration after plan update | **`/speckit-tasks`** | Same reason as `/speckit-plan`. Native to spec-kit; commit `bfda694` shows it generated 110 tasks for spec 005. |
| **Build (TDD)** | Implement code against tasks | **`/tdd`** (project command in `.claude/commands/tdd.md`) | Native project command. Enforces RED→GREEN→REFACTOR + 80% coverage. Already integrated with project's two-phase testing rules. |
| **Pre-merge review** | Code review before commit | **`/code-review`** (project command in `.claude/commands/code-review.md`) | Native project command. Calls the project's code-reviewer + security-reviewer agents. Don't fan out to gstack `/plan-eng-review` + `/plan-ceo-review` + `/sc:analyze` + `/codex` for routine review. |
| **Track** | Progress on the master plan | **TaskCreate / TaskUpdate** + `.claude/plans/006-master-plan-tracking.md` | Already in use. TaskCreate for in-conversation work; tracking file for cross-session status. |
| **Owner sign-off log** | Persist Owner decisions | **`specs/006-master-plan/decision-log.md`** | Single source of truth. ADRs link to it; SRS REQ-IDs link to it; agent reports link to it. |

---

# Anti-patterns to avoid

| Don't | Reason |
|---|---|
| Don't dump multiple skill options on the user when one will do | Wasted attention; the Owner explicitly said no |
| Don't invoke `/sc:design`, `/sc:analyze`, `/sc:document`, `/sc:improve`, `/sc:workflow`, etc. | SuperClaude isn't part of this project's proven workflow; adds ceremony without value |
| Don't invoke `/plan-ceo-review` + `/plan-eng-review` + `/plan-design-review` for routine review | Gstack heavyweight skills; reserved for critical-path locks (Phase-0 → Phase-1 transition, post-MVP review). NOT for per-PR or per-spec-update review. |
| Don't invoke `/document-release` to refresh MASTER_PLAN | Manual edit is faster for the changes we typically need; gstack ceremony has no benefit at this scale |
| Don't invoke `/codex` for routine review | Independent diff review is for critical PRs (e.g., first PR using a new ADR), not every commit |
| Don't run `/speckit-clarify` from `main` | It requires a feature branch and won't run; use the offline question pack pattern instead |
| Don't write code before the corresponding ADR is signed off in `decision-log.md` | Avoids rework; protects against locking in a wrong design |
| Don't edit Accepted ADRs in place after the same day they were authored | Write a new ADR (`ADR-XXXa`) that supersedes specific clauses |

---

# When the heavyweight reviews ARE warranted

Only at these gates:

1. **Phase-0 → Phase-1 transition** — before the first production code lands, run `/plan-eng-review` (architecture lock) + `/plan-ceo-review` (scope challenge). One time per major-phase boundary.
2. **First PR using a new ADR** — run `/codex` (independent diff review) on the first PR that implements a new architectural pattern (new model family, new service, new module). Once the pattern is proven, fall back to `/code-review` for follow-on PRs.
3. **Quarterly retro** — `/retro` (gstack) every quarter to identify pattern drift.

Outside these three triggers: `/code-review` only.

---

# When in doubt

If a task doesn't fit cleanly into the chain above:

1. Check whether it falls under "anti-patterns to avoid" — if yes, refuse the cleaner-but-overkill option.
2. Ask the user: "I think the right tool is X — confirm?"
3. If the user picks something not in this playbook: that's a signal to update the playbook. Edit this file with the new choice and the reason.

The playbook should evolve, but only by replacement (one chosen tool per category), not by addition (no menu growth).

---

# Per-task quick reference

| You need to... | Use |
|---|---|
| Get the Owner to make a decision | Write a question pack in `specs/006-master-plan/clarifications/`. Owner answers offline. |
| Write a new ADR | Manual. Save to `specs/006-master-plan/adrs/ADR-XXX-<slug>.md`. |
| Amend an existing Accepted ADR | Manual. Write `ADR-XXXa-<slug>.md` that supersedes specific clauses. |
| Update SRS requirements | Manual edit `specs/006-master-plan/SRS_Multichannel_Hub_EN.md`. Mirror to `_VN.md`. Bump version in header. |
| Update owner-facing E2 doc | Manual edit `.0temp/deliverables/E2_Quy_trinh_san_xuat.md`. Bump version. Regenerate PDF. |
| Refresh a spec's plan | `/speckit-plan` against the spec's directory. |
| Refresh a spec's tasks | `/speckit-tasks` against the spec's directory. |
| Generate a checklist | `/speckit-checklist` (it's installed; use it for entry-gate checklists). |
| Implement code | `/tdd`. |
| Review code before commit | `/code-review`. |
| Track open work in the conversation | TaskCreate / TaskUpdate. |
| Track open work across sessions | `.claude/plans/006-master-plan-tracking.md`. |
| Record an Owner decision | Add a row in `specs/006-master-plan/decision-log.md`. |
| Lock architecture before Phase-1 | `/plan-eng-review` (one time). |
| Challenge scope before Phase-1 | `/plan-ceo-review` (one time). |
| Independent review on a critical first PR | `/codex` (sparingly). |
| Quarterly look-back | `/retro` (sparingly). |

---

# Revision history

- **2026-04-26**: Initial authoring. Owner direction: "select the best one (or the most fit for this project) and apply, add to playbook if needed, don't go with many options like this."
