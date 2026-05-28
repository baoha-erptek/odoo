---
name: dispatch-slice
description: Run Master Plan 006 Phase 0 (Dispatch) deterministically. Reads .claude/plans/006-master-plan-tracking.md, picks next unblocked slice (or accepts an explicit slice ID), verifies branch + clean tree, creates per-slice tasks, hands off to Phase 1 planner. Use when starting a new slice — manually (`/dispatch-slice next`, `/dispatch-slice P1-02b`) or via Telegram DM (`dispatch next`, `dispatch <slice-id>`).
---

# dispatch-slice

Stateless Phase 0 ritual. Replaces the manual "/clear, read tracker, decide next slice" startup. Owner's only input is one of:

- `/dispatch-slice next` — auto-pick highest-priority unblocked slice
- `/dispatch-slice <slice-id>` — explicit slice (e.g. `P1-02b`, `P0-18b`)
- Telegram DM to bot: `dispatch next` / `dispatch <slice-id>` — same routing through the active session

This skill is the embodiment of the "Why no persistent PM agent" rationale in `.claude/plans/006-implementation-playbook.md`. It runs once per slice, produces no daemon state, and exits to the 9-phase loop.

## Procedure

### Step 1 — Read tracker
- Open `.claude/plans/006-master-plan-tracking.md`.
- Note: external dependencies table, "Active prioritization" section, current Wave status.

### Step 2 — Pick the slice
**If owner gave explicit slice ID**:
- Locate that row in the tracker. Confirm `state ∈ {todo, doing}`. If `done` / `blocked` / `dropped`, abort with explanation.

**If `next`**:
- Apply ordering: tracker §"🎯 Active prioritization — coding-first to reach end-to-end pipeline test" critical-path order is authoritative.
- Filter: `state == todo`, `Depends on` all `done` (or external dep satisfied per E1/E2/E3 table).
- Pick the first survivor.

If no candidate: report "no eligible slice" with the highest-priority blocker so owner can act on the dependency.

### Step 3 — Verify environment
Run in parallel (`Bash` tool, single message):
- `git -C /home/odoo/odoo_dev/other_projects/odoo19_esty branch --show-current` → must equal `feature/006-master-plan-coding`.
- `git -C /home/odoo/odoo_dev/other_projects/odoo19_esty status --porcelain` → must be empty (working tree clean).

If branch mismatch: refuse to dispatch. Tell owner to `git checkout feature/006-master-plan-coding` (or branch off `main` if forward branch missing).

If tree dirty: refuse to dispatch. Tell owner to either commit (Phase 6 conventional or WIP-checkpoint per playbook Phase 6 mid-slice rule) or stash before kicking off a new slice.

### Step 4 — Set up tasks
Use `TaskCreate` to add:
- One task per slice task as listed in `specs/<spec>/tasks.md` for the slice.
- One task per slice exit-criterion (machine-checkable list from playbook §"Slice exit criteria").

If `tasks.md` for the spec has no slice-specific entries: STOP, escalate per playbook §"When the playbook breaks" — do not improvise.

### Step 5 — Hand off to Phase 1
Spawn `planner` agent (Sonnet for in-spec, Opus for cross-spec or new ADR).
Inputs:
- Slice ID + tracker row
- Spec docs: `spec.md`, `plan.md`, `tasks.md` (slice subset), `data-model.md`
- Relevant ADRs in `specs/006-master-plan/adrs/`
- Recent `findings.md` for the spec
Output expected: tactical plan (file list, agent dispatch order, risks, exit-criteria check).

After planner returns, the regular 9-phase loop owns the rest. This skill is done.

## Telegram trigger flow

The active Claude session is the executor. The bot is just a transport.

1. Owner DMs the bot: `dispatch next` or `dispatch P1-02b`.
2. Telegram MCP delivers `<channel source="telegram" chat_id="..." user="...">dispatch next</channel>` to the active session.
3. Verify sender per `reference_telegram_routing.md` memory — only owner DM IDs (`1013317517`, `8560005895`). Reject group `-5233783589`.
4. Active session invokes this skill.
5. Skill returns acknowledgement via `telegram.reply` with: chosen slice ID, tracker row summary, planner agent dispatch confirmation.

If no active session is listening, the message queues — owner sees no immediate response and must start a Claude session before dispatch executes. Building a daemon to fix this is out of scope (see playbook §"Why no persistent PM agent").

## Out of scope

- Auto-execute Phases 1–9 without owner present. Skill stops at Phase 1 hand-off.
- Spawn parallel slices. If owner wants Mode 2 (disjoint-module worktree pair), they ask explicitly with both slice IDs and current session sets up the secondary worktree manually.
- Modify tracker rows. Only the developer-session at Phase 7 updates tracker.
- Skip exit-criterion check at end of slice. Phase 5/6/7 in the 9-phase loop handle that.

## Anti-patterns to refuse

- Dispatching when working tree is dirty → leads to mixed-slice commits.
- Dispatching while a previous slice is mid-flight without an explicit Phase 6 WIP-commit → loses uncommitted work.
- Dispatching a `blocked` slice → blocker hasn't moved; loop will re-block.
- Dispatching a `done` slice → silent doc-drift, wasted context.

In any of these, abort with a short explanation and the corrective action. Do not improvise.
