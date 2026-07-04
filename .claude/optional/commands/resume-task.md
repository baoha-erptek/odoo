# Resume Task

## Description
Resume work on an existing task by reading its `progress-tracker.md` and `NCNB-XXXX-plan.md`, then continuing from the first unchecked step.

## Usage
```
/resume-task NCNB-1234
```

If the ticket ID is omitted, the command extracts it from the current git branch (`feature/NCNB-1234-*`). If no ticket can be inferred, it lists recently-touched task directories under `.docs/tasks/` and asks which to resume.

## Workflow

0. **Worktree assertion (using-git-worktrees Step 0)**:
   ```bash
   GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
   GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
   CWD=$(pwd -P)
   EXPECTED="$GIT_COMMON/../.claude/worktrees/NCNB-XXXX"  # resolved below
   ```
   - If cwd is **not** inside `.claude/worktrees/NCNB-XXXX/` and a worktree exists for this ticket, refuse with: `"This ticket has worktree at <path>. Run: cd <path>"`.
   - If no worktree exists for this ticket, refuse with: `"No worktree for NCNB-XXXX. Run /jira-to-task NCNB-XXXX first (creates worktree + task dir)."`.
   - If cwd is already inside the ticket's worktree, proceed.

1. **Locate**: `.docs/tasks/NCNB-XXXX/`. If missing → suggest `/jira-to-task NCNB-XXXX`.
2. **Read**:
   - `progress-tracker.md` — current status and unchecked steps
   - `NCNB-XXXX-plan.md` — full plan (approach, steps, acceptance criteria, risks)
   - `ticket-analysis.md` — classification and env hints (if present)
3. **Summarize** to the user: what's done, what's next, any blockers noted in the plan.
3.5. **Ensure env (if needed)**: if `ticket-analysis.md` set `fresh_environment.needed`
   and the worktree env is not already up (`utils/worktree-env.sh status`), bring it up
   on the recommended template: `utils/worktree-env.sh up --template <recommended_template>`
   (clones in ~15s). Skip for `gui-only` / `data-fix` / `investigation`.
4. **Continue**: start from the first unchecked step in `progress-tracker.md`. Update the tracker as each step completes. If assumptions have shifted, update the plan file and note the revision date/reason at the top.

## What this replaces

The previous per-mission resume flow (`/resume-mission`) is retired. All continuation happens via the single plan + tracker pair.

## Examples

```
/resume-task NCNB-1360
→ Reads .docs/tasks/NCNB-1360/progress-tracker.md + NCNB-1360-plan.md
→ Reports: "3/5 steps done. Next: cascade plan to commands. Blockers: none."
→ Starts step 4.
```
