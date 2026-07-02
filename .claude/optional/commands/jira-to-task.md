> **OPTIONAL / DISABLED BY DEFAULT.** Ported from hr_project and genericized. Before
> using, set the tokens `${JIRA_SITE}` (e.g. `yourco.atlassian.net`), `${JIRA_KEY}`
> (e.g. `PROJ`), and `${ATLASSIAN_CREDS}` (path to a file exporting `ATLASSIAN_EMAIL`
> + `ATLASSIAN_API_TOKEN`), and move this file to `.claude/commands/`. See
> `.claude/optional/README.md`.
>
> **hr-project-only steps to ignore or replace** (kept for reference, not required):
> Step 3.5 `human-mcp` attachment extraction (only if you configure human-mcp),
> Step 3.6 superpowers `brainstorming` (optional), Step 4.6 `utils/worktree-env.sh`
> (project-specific Docker templating — reuse the `using-git-worktrees` skill instead),
> and Step 5.5 gbrain seeding (**dropped** — the filesystem `progress-tracker.md` is the
> canonical record).

# JIRA to Task

## Description
Bootstrap a task directory from a JIRA ticket. Creates `.docs/tasks/${JIRA_KEY}-XXXX/` with `progress-tracker.md`, downloads attachments, and writes `ticket-analysis.md`. Does NOT generate mission files — planning happens later via `/plan`, which produces `${JIRA_KEY}-XXXX-plan.md`.

## Usage
```
/jira-to-task ${JIRA_KEY}-1234
```

## Workflow

### Step 1 — Fetch ticket (Direct API)

```bash
source ${ATLASSIAN_CREDS}
curl -s -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  "https://${JIRA_SITE}/rest/api/3/issue/${JIRA_KEY}-1234" > /tmp/ncnb1234.json
```

Extract: summary, issue type, description, attachments, subtasks, components.

### Step 2 — Create task directory

```
.docs/tasks/${JIRA_KEY}-1234/
├── progress-tracker.md
├── ticket-analysis.md
├── attachments/
└── sub-agents-outputs/
```

If `.docs/tasks/${JIRA_KEY}-1234/` already exists, stop and suggest `/resume-task ${JIRA_KEY}-1234` instead.

### Step 2.5 — Ensure ticket worktree (using-git-worktrees skill)

**Invoke the `using-git-worktrees` skill** (Step 0 detect → reuse-check → Step 1b create). Hard rule from `CLAUDE.md`: worktree per ticket, branched from `master`.

```bash
# Reuse-check: existing worktree OR existing branch for this ticket
EXISTING_WT=$(git worktree list --porcelain | awk '/^worktree /{wt=$2} /^branch / && $2~/${JIRA_KEY}-1234/{print wt}')
EXISTING_BR=$(git branch --list '*${JIRA_KEY}-1234*' --format='%(refname:short)')

if [ -n "$EXISTING_WT" ]; then
    echo "Reusing worktree: $EXISTING_WT (branch: $EXISTING_BR)"
    echo "Run: cd $EXISTING_WT"
elif [ -n "$EXISTING_BR" ]; then
    # Branch exists but no worktree (rare — orphaned). Attach a new worktree to the existing branch.
    git worktree add .claude/worktrees/${JIRA_KEY}-1234 "$EXISTING_BR"
else
    # New ticket: branch from master (NEVER develop — see CLAUDE.md "Critical Gotchas").
    git fetch origin master
    git worktree add .claude/worktrees/${JIRA_KEY}-1234 -b worktree-${JIRA_KEY}-1234 origin/master
fi

echo "Next: cd .claude/worktrees/${JIRA_KEY}-1234 and re-run /jira-to-task ${JIRA_KEY}-1234 from there (if not already)."
```

Notes:
- Initial branch name is `worktree-${JIRA_KEY}-1234` (placeholder). Rename to the canonical `feature/${JIRA_KEY}-1234-<slug>` (or `fix/`, `bugfix/`) before opening the PR — see git-workflow rule.
- `.docs/tasks/${JIRA_KEY}-1234/` is automatically visible inside the new worktree via the `.docs/tasks` symlink (set up by `.claude/git-hooks/post-checkout`).
- For a per-worktree Docker env, bring it up from inside the worktree after `cd` (see Step 4.6 — it clones a template in ~15s instead of a full install). Not required if you're only editing code.
- This step **must run before Step 3+** so attachments and analysis land in the right working copy. If cwd is still the main repo, the rest of the pipeline writes to `.docs/tasks/` (symlinked target) but expects to continue from the worktree.

### Step 3 — Download attachments

```bash
mkdir -p .docs/tasks/${JIRA_KEY}-1234/attachments
curl -L -H "Accept: */*" -H "X-Atlassian-Token: no-check" \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  -o ".docs/tasks/${JIRA_KEY}-1234/attachments/<filename>" "<attachment_url>"
```

Note: both `Accept: */*` AND `X-Atlassian-Token: no-check` are required — without them you get a 0-byte file.

### Step 3.5 — Extract attachment content (human-mcp)

After download, run `human-mcp` (Gemini-backed, configured in `.mcp.json`) on each binary attachment so the analyzer reads what's *inside*, not just filenames:

| File type | Tool |
|-----------|------|
| `*.png`, `*.jpg`, `*.gif`, `*.mp4` (screenshots, screen recordings) | `mcp__human-mcp__eyes_analyze` |
| Two related screenshots (before/after, expected/actual) | `mcp__human-mcp__eyes_compare` |
| `*.pdf`, `*.docx`, `*.xlsx`, `*.pptx` | `mcp__human-mcp__eyes_read_document` |
| Long doc → quick gist before drilling in | `mcp__human-mcp__eyes_summarize_document` |

Append the extracted text/observations into `ticket-analysis.md` under an "Attachment Findings" section so downstream `/plan` and Two-Phase Testing can use them.

### Step 3.6 — Optional brainstorming handoff (superpowers)

If the user signals exploratory spec refinement before `/plan` (vague ticket, multiple plausible interpretations, design ambiguity), suggest invoking the superpowers `brainstorming` skill. Per the adapter rule in `CLAUDE.md` (Superpowers Integration §1), design notes land in `.docs/tasks/${JIRA_KEY}-XXXX/design-notes.md`. Terminal handoff is `/plan` (not superpowers' `writing-plans` directly — `/plan` will call it as a sub-step).

### Step 4 — Run ticket analysis

Invoke `jira-ticket-analyzer` skill (`.claude/skills/jira-ticket-analyzer/SKILL.md`):

1. Classify against `config/ticket-types.yaml` (gui-only / backend-only / full-stack / data-fix / investigation / performance / configuration).
2. Apply `config/approach-matrix.yaml` to select skills, testing phases, env needs.
3. Detect environment (prod / test / local).
4. Identify affected models/views/modules.
5. Write output to `.docs/tasks/${JIRA_KEY}-1234/ticket-analysis.md` using `templates/analysis-output.md`.

Then **launch the `product-owner` agent via the Task tool** (`subagent_type: product-owner`)
to triage scope and acceptance-criteria gaps from a user + Odoo-developer perspective.
This is an explicit Task-tool dispatch — do not rely on the agent self-triggering. Write
its output to `.docs/tasks/${JIRA_KEY}-1234/sub-agents-outputs/product-owner-triage.md` and
summarise any CRITICAL/HIGH gaps into `ticket-analysis.md`. Advisory only — never blocks.

### Step 4.6 — Bring up the worktree env (template fast path)

If the analysis set `fresh_environment.needed` (not `false`), bring up a data-ready env
from inside the worktree using the `recommended_template` from `ticket-analysis.md`:

```bash
cd .claude/worktrees/${JIRA_KEY}-1234
# recommended_template comes from ticket-analysis.md (e.g. test_tpl_l3_attendance);
# fall back to the level if no template line is present.
utils/worktree-env.sh up --template "$RECOMMENDED_TEMPLATE"
#   or:  utils/worktree-env.sh up --level 3            (modules only)
#   or:  utils/worktree-env.sh up --domain attendance  (level from default)
```

This clones the per-worktree DB from the template (~15s) and starts Odoo on the shared
Postgres + shared image — no per-worktree build, no full module install. If the chosen
template does not exist yet, the script prints the one-line build command
(`manage_template.sh create` for modules-only, `build_domain_template.sh` for domain data).
Skip this step for `gui-only` / `data-fix` / `investigation` tickets that test on
`hr_project_db`.

### Step 5 — Create progress-tracker.md

```markdown
# Task: ${JIRA_KEY}-1234 — [summary from JIRA]

## Source
- **JIRA**: [${JIRA_KEY}-1234](https://${JIRA_SITE}/browse/${JIRA_KEY}-1234)
- **Type**: [Story/Bug/Task]
- **Created**: [ISO date]

## Problem Statement
[Description from JIRA]

## Attachments
- [list]

## Classification
See `ticket-analysis.md` for full details.
- **Type**: [classification]
- **Env**: [prod/test/local]
- **Affected**: [models/views/modules]

## Plan
Plan file: `${JIRA_KEY}-1234-plan.md` (created by `/plan`)
- [ ] Plan drafted
- [ ] Plan approved
- [ ] Plan reflects latest scope (update when replanning)

## Progress
_Updated as work happens. Each item should trace back to an acceptance criterion in the plan._

- [ ] (step 1) [description]
- [ ] (step 2) [description]

## JIRA Sync
- **Last synced**: Never
- **Auto-sync**: Disabled — use `/sync-to-jira ${JIRA_KEY}-1234` when ready
```

### Step 5.5 — Seed gbrain ticket page (non-blocking)

Invoke the **gbrain-ticket-write** skill with:
- `ticket_id=${JIRA_KEY}-1234`
- `status=planning`
- `summary=<JIRA summary>`
- `domain=<route via .docs/po/domain-registry.md keywords from JIRA components/labels>`

Creates `tickets/${JIRA_KEY}-1234` in the brain so future `/plan` recalls can find it. If gbrain is unreachable, log a warning and continue — the filesystem-side `progress-tracker.md` remains the canonical record.

### Step 6 — Output

```
✅ ${JIRA_KEY}-1234 fetched: [summary]
✅ Task dir: .docs/tasks/${JIRA_KEY}-1234/
   - progress-tracker.md
   - ticket-analysis.md
   - attachments/ (N files)

Next: /plan to draft the implementation plan.
```

## JIRA Sync Behavior
- No automatic sync during work
- Sync is explicit only: `/sync-to-jira ${JIRA_KEY}-1234`

## Error Handling
- Ticket not found → check ID and credentials (`${ATLASSIAN_CREDS}`)
- Existing task dir → suggest `/resume-task ${JIRA_KEY}-1234`
- 0-byte attachment → retry with both required headers
