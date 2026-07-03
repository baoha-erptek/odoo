# Sync to JIRA

## Description
Manually sync progress to the **ESTY** JIRA project. Posts a summary comment drawn from `progress-tracker.md` and (optionally) the current plan revision. Transitions are explicit. No automatic sync ever.

Credentials come from the project `.env` (gitignored): `JIRA_SERVER_URL`, `JIRA_USER_EMAIL`, `JIRA_API_KEY`.

## Usage
```
/sync-to-jira ESTY-1234
```

## Workflow

### 1. Load progress

Read these files from `.docs/tasks/ESTY-1234/`:
- `progress-tracker.md` — checked/unchecked steps, last updated timestamp, notes
- `ESTY-1234-plan.md` — Acceptance Criteria section, Revised line at top

### 2. Draft comment

Default template — edit before sending if context calls for it.

```markdown
## Progress update — ESTY-1234

**Plan**: `ESTY-1234-plan.md` (revised YYYY-MM-DD)

**Done**
- ✅ <step 1>
- ✅ <step 2>

**In progress**
- 🔄 <step 3>

**Pending**
- ⏳ <step 4>
- ⏳ <step 5>

**Files touched**
- `custom_addons/.../path.py`
- `custom_addons/.../views/...xml`

**Tests**: <status / coverage %>

**Risks / blockers**: <from plan's Risks section, if any>

---
*Synced manually by developer.*
```

### 3. Post to JIRA (Direct API)

```bash
set -a; source "$(git rev-parse --show-toplevel)/.env"; set +a

# Build comment body (ADF-wrapped)
body_json=$(jq -Rs '{"body":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":.}]}]}}' < /tmp/comment.md)

curl -s -X POST -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data "$body_json" \
  "${JIRA_SERVER_URL%/}/rest/api/3/issue/ESTY-1234/comment"
```

**Do NOT use MCP Atlassian tools.** Use Direct API only.

### 4. Optional status transition

Only when the user explicitly asks. List transitions first:

```bash
curl -s -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
  "${JIRA_SERVER_URL%/}/rest/api/3/issue/ESTY-1234/transitions"
```

Then POST the transition id to the same endpoint.

### 5. Update tracker

Append a sync note to `progress-tracker.md`:

```markdown
## JIRA Sync Log
- YYYY-MM-DD HH:MM — synced progress (3/5 done)
```

## Output

```
✅ Synced ESTY-1234
   Commented: progress (3/5)
   Plan revision: 2026-04-17
   Transition: <unchanged | In Review | ...>
```

## Error handling

- 401 / 403 → check `.env` (`JIRA_USER_EMAIL` / `JIRA_API_KEY`); token may be expired
- 404 → verify ticket ID
- Task dir missing → suggest `/jira-to-task ESTY-1234`
- Plan file missing → comment with tracker-only content, warn "plan not drafted yet"
