---
name: jira-create
description: Create JIRA issues (epic, story, bug, task) in the ESTY project on erptek.atlassian.net via local-first .md workflow plus Direct API push. Reads credentials from project .env.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# JIRA Issue Creator (ESTY)

Project-local skill for creating JIRA issues in the **ESTY** project on
`erptek.atlassian.net`. Supports a **local-first** workflow: write structured
`.md` files under `.docs/tasks/`, review, then push to JIRA via the Direct API.

## Configuration

All four values live in the project `.env` (gitignored):

```
JIRA_PROJECT_KEY='ESTY'
JIRA_SERVER_URL='https://erptek.atlassian.net/'
JIRA_USER_EMAIL='bao.ha@erptek.net'
JIRA_API_KEY='ATCTT3xF...'
```

The push script auto-discovers `.env` from `git rev-parse --show-toplevel`.
Override with `ENV_FILE=/path/to/other.env bash push_to_jira.sh ...`.

## Two Workflows

### Workflow 1: Draft-First (Recommended)

Stage a `.md` file in a `ESTY-DRAFT-<slug>/` directory, review/edit, then push.

```
User request -> write .md from template -> save under .docs/tasks/ESTY-DRAFT-<slug>/
              -> push_to_jira.sh -> returns ESTY-XXX -> rename dir to ESTY-XXX/
```

### Workflow 2: Direct Push

Skip the local file entirely; create the issue directly in JIRA via API.

## Issue Types

| Type | Template | When to Use |
|------|----------|-------------|
| **Epic** | `templates/epic.md` | Body of work spanning multiple sprints; per-spec container |
| **Story** | `templates/story.md` | User-facing functionality (US1..USn from spec) |
| **Bug** | `templates/bug.md` | Defect with reproduction steps |
| **Task** | `templates/task.md` | Technical/operational work; one per `tasks.md` row |

## Local .md File Format

YAML frontmatter + markdown body.

```yaml
---
type: story          # epic | story | bug | task
project: ESTY
summary: "Short title here"
status: draft        # draft | ready | pushed
jira_key:            # filled after push (e.g., ESTY-123)
parent:              # parent issue key for sub-issues (Epic key for a Story)
labels: []
priority: Medium     # Low | Medium | High | Highest
assignee:            # optional Atlassian email
created: 2026-04-26
---
```

**File-location rule (critical):**

```
.docs/tasks/ESTY-123/progress-tracker.md               <- CORRECT (after push)
.docs/tasks/ESTY-DRAFT-oauth-pkce/progress-tracker.md  <- CORRECT (before push)
.docs/tasks/oauth-pkce.md                              <- WRONG
```

After a successful push, rename the draft directory to use the returned key:
```bash
mv .docs/tasks/ESTY-DRAFT-oauth-pkce .docs/tasks/ESTY-123
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/push_to_jira.sh <file>` | Push a single `.md` to JIRA. Updates frontmatter with `jira_key` and `status: pushed`. |
| `scripts/discover_issue_types.sh` | One-shot env+API smoke test. Lists issue types and the Epic Link custom-field id. |
| `scripts/push_batch.sh [epics\|stories\|tasks\|all]` | Iterate over `.docs/tasks/ESTY-DRAFT-*/progress-tracker.md` and push in dependency order. |

### Manual API reference

```bash
set -a; source .env; set +a
curl -s -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
  "${JIRA_SERVER_URL%/}/rest/api/3/issue/createmeta?projectKeys=${JIRA_PROJECT_KEY}" \
  | python3 -m json.tool
```

## Field Validation

### Required (all types)
- `summary` -- concise, action-oriented, <72 chars
- Description body -- structured per template

### Per-type

| Type | Required | Recommended |
|------|----------|-------------|
| Epic | summary, objective, scope, acceptance criteria | timeline, dependencies |
| Story | summary, user story (who/what/why), acceptance criteria (2+) | context, dependencies |
| Bug | summary, problem, steps to reproduce, actual/expected | environment, logs |
| Task | summary, description, motivation | acceptance criteria, files to modify |

### Security check before push
- No credentials, API keys, tokens in any field
- No passwords or connection strings
- Logs sanitized of sensitive data
- Never paste contents of `.env` into a Jira description

## Error Handling

| HTTP | Solution |
|------|----------|
| 401 | Token in `.env` invalid or expired -- regenerate at id.atlassian.com -> API tokens |
| 403 | Account doesn't have permission to create in `ESTY` |
| 404 | `JIRA_PROJECT_KEY` not visible to this account |
| 400 | Required field missing -- read body of error response |
| 429 | Rate limited -- wait and retry |

| Local | Solution |
|-------|----------|
| Missing frontmatter | Add YAML with `type`, `project`, `summary` |
| Invalid type | One of: `epic`, `story`, `bug`, `task` |
| Already pushed | `jira_key` non-empty -- clear it to force re-push (creates duplicate!) |

## Workflow Summary

```
1. Pick issue type (epic/story/bug/task)
2. Copy template -> fill summary, description, acceptance criteria
3. Save to .docs/tasks/ESTY-DRAFT-<slug>/progress-tracker.md
4. (Optional) review/edit; rerun for related issues
5. Push: bash .claude/skills/jira-create/scripts/push_to_jira.sh <file>
6. Rename: mv .docs/tasks/ESTY-DRAFT-<slug> .docs/tasks/ESTY-<key>
```

For batch pushes (e.g., a whole spec at once):
```bash
bash .claude/skills/jira-create/scripts/push_batch.sh epics
bash .claude/skills/jira-create/scripts/push_batch.sh stories
bash .claude/skills/jira-create/scripts/push_batch.sh tasks
```

`push_batch.sh` runs in dependency order so Epic Links resolve before Stories,
and Stories resolve before their Tasks.

## Examples

### Story (drafted, then pushed)

`.docs/tasks/ESTY-DRAFT-oauth-pkce/progress-tracker.md`:
```yaml
---
type: story
project: ESTY
summary: "OAuth2 PKCE flow for Etsy shop authorization"
status: draft
jira_key:
parent:                  # filled with Epic key after epic push
labels: [oauth, etsy-api]
priority: High
created: 2026-04-26
---

# OAuth2 PKCE flow for Etsy shop authorization

As an **Etsy shop owner**, I want to **authorize the integration via the
official OAuth2 PKCE flow**, so that **my access token is scoped, refreshable,
and can be revoked without sharing credentials**.

## Acceptance Criteria

- [ ] PKCE code_verifier + code_challenge generated per session
- [ ] Authorize redirect lands on Odoo `/etsy/oauth/callback`
- [ ] Token stored encrypted on `etsy.shop` record
- [ ] Refresh-token flow runs before access-token expiry
```

After `push_to_jira.sh` succeeds, frontmatter is updated:
```yaml
status: pushed
jira_key: ESTY-42
```

...and the file is moved to `.docs/tasks/ESTY-42/progress-tracker.md`.
