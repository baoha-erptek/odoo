---
name: jira-create
description: Create JIRA issues (epic, story, bug, task) with local-first .md workflow and Direct API push to JIRA. Supports creating .md files locally first, then optionally pushing to JIRA later.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# JIRA Issue Creator

Unified skill for creating JIRA issues in the $JIRA_KEY project. Supports **local-first** workflow: create structured `.md` files locally, then optionally push to JIRA via Direct API.

## Configuration

```
Project: $JIRA_KEY
Site: https://$JIRA_SITE
Credentials: $ATLASSIAN_CREDS
API: Direct API (curl) — NOT MCP tools
```

## Two Workflows

### Workflow 1: Local-First (Recommended)

Create a `.md` file locally, review/edit, then push to JIRA when ready.

```
User request → Create .md from template → Save to .docs/tasks/ → [Optional] Push to JIRA
```

**Steps:**
1. Collect issue information interactively
2. Push to JIRA via API to get the issue key (e.g., $JIRA_KEY-1299)
3. Create task directory: `.docs/tasks/$JIRA_KEY-1299/`
4. Save `.md` file as `.docs/tasks/$JIRA_KEY-1299/progress-tracker.md`

### Workflow 2: Direct JIRA Creation

Create the issue directly in JIRA via API (skip local `.md`).

```
User request → Collect info → Create via API → Return issue key
```

## Issue Types

| Type | Template | When to Use |
|------|----------|-------------|
| **Epic** | `templates/epic.md` | Body of work spanning multiple sprints, contains stories/tasks |
| **Story** | `templates/story.md` | User-facing functionality, "As a... I want... So that..." |
| **Bug** | `templates/bug.md` | Defect report with reproduction steps |
| **Task** | `templates/task.md` | Technical/operational work, not user-facing |

## Local .md File Format

All local `.md` files use YAML frontmatter for metadata + markdown body for description.

```yaml
---
type: story          # epic | story | bug | task
project: $JIRA_KEY
summary: "Short title here"
status: draft        # draft | ready | pushed
jira_key:            # Filled after push (e.g., $JIRA_KEY-1234)
parent:              # Parent issue key (optional)
labels: []           # Optional labels
priority: Medium     # Low | Medium | High | Highest
assignee:            # Optional email
created: 2026-03-03
---
```

**CRITICAL — File location convention:**

Files MUST be saved inside a JIRA-key subdirectory, NOT directly in `.docs/tasks/`.

```
.docs/tasks/$JIRA_KEY-1299/progress-tracker.md    ← CORRECT
.docs/tasks/bug-some-issue.md                 ← WRONG
```

**Directory structure:** `.docs/tasks/$JIRA_KEY-XXXX/progress-tracker.md`
- Create directory `.docs/tasks/$JIRA_KEY-XXXX/` first (using the JIRA key from push)
- Save the issue `.md` as `progress-tracker.md` inside that directory
- If pushing to JIRA first (recommended), use the returned key for the directory name
- If creating as draft before push, use a placeholder like `$JIRA_KEY-DRAFT-<slug>/` and rename after push

**Default location:** `.docs/tasks/` (shared across worktrees via symlink)

## Interactive Collection Workflow

### For Stories

1. **Who benefits?** → Role/user (e.g., "HR manager")
2. **What action?** → What they want to do
3. **What value?** → Why (business value)
4. **Acceptance criteria** → Testable conditions (minimum 2)
5. **Additional context** → Dependencies, constraints (optional)

### For Epics

1. **Objective** → What capability will be delivered
2. **Scope** → In scope / out of scope
3. **Acceptance criteria** → High-level outcomes (3-6)
4. **Timeline** → Target quarter/sprint count

### For Bugs

1. **Problem description** → What is broken
2. **Environment** → Odoo version, module, browser
3. **Reproducibility** → Always / Sometimes / Rarely
4. **Steps to reproduce** → Numbered steps
5. **Actual vs expected results** → What happens vs what should happen
6. **Additional info** → Logs, screenshots (optional)

### For Tasks

1. **What needs to be done** → Clear description
2. **Why** → Context/motivation
3. **Acceptance criteria** → How to know it's done (optional)
4. **Technical details** → Files, approach (optional)

## Push to JIRA (Direct API)

### Create Issue

```bash
bash .claude/skills/jira-create/scripts/push_to_jira.sh <path-to-md-file>
```

### Manual API (Reference)

```bash
# Create issue
bash -c 'source $ATLASSIAN_CREDS && curl -s -X POST \
    -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"fields\": {
            \"project\": {\"key\": \"$JIRA_KEY\"},
            \"summary\": \"Issue summary here\",
            \"issuetype\": {\"name\": \"Story\"},
            \"description\": {
                \"type\": \"doc\",
                \"version\": 1,
                \"content\": [{
                    \"type\": \"paragraph\",
                    \"content\": [{\"type\": \"text\", \"text\": \"Description here\"}]
                }]
            }
        }
    }" \
    "https://$JIRA_SITE/rest/api/3/issue"'
```

### Get Available Issue Types

```bash
bash -c 'source $ATLASSIAN_CREDS && curl -s \
    -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
    "https://$JIRA_SITE/rest/api/3/issue/createmeta?projectKeys=$JIRA_KEY" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); [print(t[\"name\"]) for p in d.get(\"projects\",[]) for t in p.get(\"issuetypes\",[])]"'
```

## Field Validation

### Required Fields (All Types)
- Summary: concise, action-oriented (under 72 chars)
- Description: structured per type template

### Per-Type Validation

| Type | Required | Recommended |
|------|----------|-------------|
| Epic | Summary, objective, scope, acceptance criteria | Timeline, dependencies |
| Story | Summary, user story (who/what/why), acceptance criteria (2+) | Context, dependencies |
| Bug | Summary, problem description, steps to reproduce, actual/expected | Environment, logs |
| Task | Summary, description, motivation | Acceptance criteria, files to modify |

### Security Check (Before Push)
- No credentials, API keys, or tokens in any field
- No passwords or connection strings
- Logs sanitized of sensitive data

## Error Handling

### Push Failures

| Error | Solution |
|-------|----------|
| 401 Unauthorized | Check `$ATLASSIAN_CREDS` — token may be expired |
| 404 Not Found | Verify project key `$JIRA_KEY` exists |
| 400 Bad Request | Check required fields in the API response body |
| 429 Rate Limited | Wait and retry (Atlassian Cloud rate limit) |

### Local File Issues

| Issue | Solution |
|-------|----------|
| Missing frontmatter | Add YAML frontmatter with required `type`, `project`, `summary` |
| Invalid type | Must be one of: `epic`, `story`, `bug`, `task` |
| Already pushed | Check `jira_key` in frontmatter — file was already pushed |

## Examples

### Example 1: Create Story (Push First, Then Save Locally)

```bash
# User says: "Create a story for exporting sale orders to Excel"

# Step 1: Claude pushes to JIRA via API → gets $JIRA_KEY-1300
# Step 2: Claude creates directory and saves:
#   .docs/tasks/$JIRA_KEY-1300/progress-tracker.md
```

```yaml
---
type: story
project: $JIRA_KEY
summary: "Add sale order export to Excel"
status: pushed
jira_key: $JIRA_KEY-1300
parent:
labels: [sale, export]
priority: Medium
created: 2026-03-03
---

# Add sale order export to Excel

As a **sales manager**, I want to **export sale orders to Excel format**,
so that **I can share pipeline reports without giving stakeholders JIRA access**.

## Acceptance Criteria

- [ ] Export button available on the sale order list view
- [ ] Excel file includes customer, date, salesperson, total
- [ ] Export respects the current search/filter applied on the list
- [ ] File downloads with naming format: `sale_orders_YYYY-MM.xlsx`
```

### Example 2: Create Bug

```bash
# User says: "Create a bug for a tax rounding issue on invoices"

# Claude pushes to JIRA → gets $JIRA_KEY-1301
# Creates: .docs/tasks/$JIRA_KEY-1301/progress-tracker.md
```

## Workflow Summary

```
1. Determine issue type (epic/story/bug/task)
2. Collect information interactively
3. Push to JIRA via API → get $JIRA_KEY-XXXX key
4. Create directory: .docs/tasks/$JIRA_KEY-XXXX/
5. Save .md as: .docs/tasks/$JIRA_KEY-XXXX/progress-tracker.md
   (with jira_key and status=pushed in frontmatter)
```

**IMPORTANT:** Always save to `.docs/tasks/$JIRA_KEY-XXXX/progress-tracker.md`, never directly in `.docs/tasks/`.

## See Also

- `atlassian-jira-confluence` skill — General JIRA/Confluence API operations
- `jira-to-task` command — Create AB Method task from existing JIRA ticket
- `sync-to-jira` command — Sync task progress back to JIRA
- Templates: `.claude/skills/jira-create/templates/`
