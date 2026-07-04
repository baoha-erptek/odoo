# JIRA to Task

## Description
Bootstrap a task directory from an **ESTY** JIRA ticket. Creates `.docs/tasks/ESTY-XXXX/` with `progress-tracker.md`, downloads attachments, and writes `ticket-analysis.md`. Does NOT generate mission files — planning happens later via `/plan`, which produces `ESTY-XXXX-plan.md`.

> **When to use this vs `/dispatch-slice`.** This is the **secondary** entry point, for
> ad-hoc ESTY JIRA tickets (bugs, UAT defects, one-off tasks). Master Plan 006 **feature
> slices** still go through `/dispatch-slice` on `feature/006-master-plan-coding` (see
> `.claude/plans/006-master-plan-tracking.md`). Both write task dirs under
> `.docs/tasks/ESTY-XXX/`, matching the layout the `jira-create` skill already uses.

Credentials come from the project `.env` (gitignored) — same contract as `jira-create`:
`JIRA_SERVER_URL`, `JIRA_PROJECT_KEY` (`ESTY`), `JIRA_USER_EMAIL`, `JIRA_API_KEY`.

## Usage
```
/jira-to-task ESTY-1234
```

## Workflow

### Step 1 — Fetch ticket (Direct API)

```bash
set -a; source "$(git rev-parse --show-toplevel)/.env"; set +a
curl -s -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
  "${JIRA_SERVER_URL%/}/rest/api/3/issue/ESTY-1234" > /tmp/esty1234.json
```

Extract: summary, issue type, description, attachments, subtasks, components.

### Step 2 — Create task directory

```
.docs/tasks/ESTY-1234/
├── progress-tracker.md
├── ticket-analysis.md
├── attachments/
└── sub-agents-outputs/
```

If `.docs/tasks/ESTY-1234/` already exists, stop and suggest `/resume-task ESTY-1234` instead.

### Step 2.5 — Ensure ticket worktree (using-git-worktrees skill)

**Invoke the `using-git-worktrees` skill** (detect existing isolation → reuse-check → create).
For a bug/rework ticket, use a worktree branched from `main` (esty's trunk). Forward MP006
feature work stays on `feature/006-master-plan-coding` and does not need a per-ticket worktree
(memory `feedback_use_worktree_for_new_work.md`).

```bash
# Reuse-check: existing worktree OR existing branch for this ticket
EXISTING_WT=$(git worktree list --porcelain | awk '/^worktree /{wt=$2} /^branch / && $2~/ESTY-1234/{print wt}')
EXISTING_BR=$(git branch --list '*ESTY-1234*' --format='%(refname:short)')

if [ -n "$EXISTING_WT" ]; then
    echo "Reusing worktree: $EXISTING_WT (branch: $EXISTING_BR)"
    echo "Run: cd $EXISTING_WT"
elif [ -n "$EXISTING_BR" ]; then
    # Branch exists but no worktree (rare — orphaned). Attach a new worktree to the existing branch.
    git worktree add .claude/worktrees/ESTY-1234 "$EXISTING_BR"
else
    # New ticket: branch from main (esty trunk — see project_main_branch_promoted memory).
    git fetch origin main
    git worktree add .claude/worktrees/ESTY-1234 -b worktree-ESTY-1234 origin/main
fi

echo "Next: cd .claude/worktrees/ESTY-1234 and re-run /jira-to-task ESTY-1234 from there (if not already)."
```

Notes:
- Initial branch name is `worktree-ESTY-1234` (placeholder). Rename to the canonical
  `fix/ESTY-1234-<slug>` (or `feature/`, `bugfix/`) before opening the PR — see git-workflow rule.
- This step should run before Step 3+ so attachments and analysis land in the right working copy.

### Step 3 — Download attachments

```bash
mkdir -p .docs/tasks/ESTY-1234/attachments
curl -L -H "Accept: */*" -H "X-Atlassian-Token: no-check" \
  -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
  -o ".docs/tasks/ESTY-1234/attachments/<filename>" "<attachment_url>"
```

Note: both `Accept: */*` AND `X-Atlassian-Token: no-check` are required — without them you get a 0-byte file.

### Step 4 — Run ticket analysis

Invoke `jira-ticket-analyzer` skill (`.claude/skills/jira-ticket-analyzer/SKILL.md`):

1. Classify against `config/ticket-types.yaml` (gui-only / backend-only / full-stack / data-fix / investigation / performance / configuration).
2. Apply `config/approach-matrix.yaml` to select skills, testing phases, env needs.
3. Detect environment (staging / local).
4. Identify affected models/views/modules.
5. Write output to `.docs/tasks/ESTY-1234/ticket-analysis.md` using `templates/analysis-output.md`.

Then **launch the `product-owner` agent via the Task tool** (`subagent_type: product-owner`)
to triage scope and acceptance-criteria gaps from a user + Odoo-developer perspective.
This is an explicit Task-tool dispatch — do not rely on the agent self-triggering. Write
its output to `.docs/tasks/ESTY-1234/sub-agents-outputs/product-owner-triage.md` and
summarise any CRITICAL/HIGH gaps into `ticket-analysis.md`. Advisory only — never blocks.

### Step 5 — Create progress-tracker.md

```markdown
# Task: ESTY-1234 — [summary from JIRA]

## Source
- **JIRA**: [ESTY-1234](${JIRA_SERVER_URL}/browse/ESTY-1234)
- **Type**: [Story/Bug/Task]
- **Created**: [ISO date]

## Problem Statement
[Description from JIRA]

## Attachments
- [list]

## Classification
See `ticket-analysis.md` for full details.
- **Type**: [classification]
- **Env**: [staging/local]
- **Affected**: [models/views/modules]

## Plan
Plan file: `ESTY-1234-plan.md` (created by `/plan`)
- [ ] Plan drafted
- [ ] Plan approved
- [ ] Plan reflects latest scope (update when replanning)

## Progress
_Updated as work happens. Each item should trace back to an acceptance criterion in the plan._

- [ ] (step 1) [description]
- [ ] (step 2) [description]

## JIRA Sync
- **Last synced**: Never
- **Auto-sync**: Disabled — use `/sync-to-jira ESTY-1234` when ready
```

### Step 6 — Output

```
✅ ESTY-1234 fetched: [summary]
✅ Task dir: .docs/tasks/ESTY-1234/
   - progress-tracker.md
   - ticket-analysis.md
   - attachments/ (N files)

Next: /plan to draft the implementation plan.
```

## JIRA Sync Behavior
- No automatic sync during work
- Sync is explicit only: `/sync-to-jira ESTY-1234`

## Error Handling
- Ticket not found → check ID and credentials in `.env` (`JIRA_USER_EMAIL` / `JIRA_API_KEY`)
- Existing task dir → suggest `/resume-task ESTY-1234`
- 0-byte attachment → retry with both required headers
