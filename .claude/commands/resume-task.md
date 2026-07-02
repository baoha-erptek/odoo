# Resume Task

## Description
Resume work on an existing task by reading its `progress-tracker.md` and `ESTY-XXXX-plan.md`, then continuing from the first unchecked step.

## Usage
```
/resume-task ESTY-1234
```

If the ticket ID is omitted, the command extracts it from the current git branch (`feature/ESTY-1234-*` or `fix/ESTY-1234-*`). If no ticket can be inferred, it lists recently-touched task directories under `.docs/tasks/` and asks which to resume.

## Workflow

0. **Worktree assertion (using-git-worktrees skill)**:
   ```bash
   GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
   CWD=$(pwd -P)
   EXPECTED="$GIT_COMMON/../.claude/worktrees/ESTY-XXXX"  # resolved below
   ```
   - If cwd is **not** inside `.claude/worktrees/ESTY-XXXX/` and a worktree exists for this ticket, refuse with: `"This ticket has worktree at <path>. Run: cd <path>"`.
   - If no worktree exists for this ticket, refuse with: `"No worktree for ESTY-XXXX. Run /jira-to-task ESTY-XXXX first (creates worktree + task dir)."`.
   - If cwd is already inside the ticket's worktree, proceed.
   - (Forward MP006 work stays on `feature/006-master-plan-coding` and skips this assertion.)

1. **Locate**: `.docs/tasks/ESTY-XXXX/`. If missing → suggest `/jira-to-task ESTY-XXXX`.
2. **Read**:
   - `progress-tracker.md` — current status and unchecked steps
   - `ESTY-XXXX-plan.md` — full plan (approach, steps, acceptance criteria, risks)
   - `ticket-analysis.md` — classification and env hints (if present)
3. **Summarize** to the user: what's done, what's next, any blockers noted in the plan.
4. **Continue**: start from the first unchecked step in `progress-tracker.md`. Update the tracker as each step completes. If assumptions have shifted, update the plan file and note the revision date/reason at the top.

## Examples

```
/resume-task ESTY-1360
→ Reads .docs/tasks/ESTY-1360/progress-tracker.md + ESTY-1360-plan.md
→ Reports: "3/5 steps done. Next: cascade plan to commands. Blockers: none."
→ Starts step 4.
```
