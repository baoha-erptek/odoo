---
name: jira-ticket-analyzer
description: Classify JIRA tickets and determine optimal resolution approach before work begins. Runs FIRST in the /jira-to-task workflow to select skills, testing strategy, and environment needs.
---

# JIRA Ticket Analyzer Skill

Pre-work analysis that classifies tickets and recommends the optimal approach before any code changes begin.

## Quick Start

```bash
# Invoked automatically by /jira-to-task (Step 1.5)
# Or manually:
# 1. Fetch ticket data
# 2. Apply ticket-types.yaml classification
# 3. Apply approach-matrix.yaml recommendations
# 4. Generate .docs/tasks/NCNB-XXXX/ticket-analysis.md
```

## Workflow

### Step 1: Fetch Ticket Data

Use the `atlassian-jira-confluence` skill patterns:

```bash
bash -c 'source ~/.atlassian_credentials && curl -s -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
    "https://newworldfashion.atlassian.net/rest/api/3/issue/NCNB-XXXX"'
```

Extract:
- `fields.summary` - Title
- `fields.description` - Full description (ADF format, extract text)
- `fields.issuetype.name` - Bug/Story/Task/Epic
- `fields.priority.name` - Priority level
- `fields.labels` - Labels
- `fields.components` - Components
- `fields.subtasks` - Subtask count
- `fields.attachment` - Attachment list (screenshots indicate GUI issues)
- `fields.comment.comments` - Comments (may contain technical details)

**Attachment content extraction**: when attachments exist, after download call `mcp__human-mcp__eyes_analyze` (images/screenshots/video) or `mcp__human-mcp__eyes_read_document` (PDF / DOCX / XLSX / PPTX) on the local files. Fold the extracted text/observations into the classification keywords below — a screenshot showing a Python traceback shifts the ticket from `gui-only` toward `backend-only`; a spec doc with model field names points to `full-stack`.

### Step 2: Classify Ticket Type

Apply keyword detection from `config/ticket-types.yaml` against ALL text fields (summary + description + comments).

**Classification Algorithm**:
1. Score each type by counting keyword matches (EN + VN)
2. Apply weight multipliers per keyword category
3. Highest score with confidence >= 60% wins
4. If no type reaches 60%, default to `investigation`

**7 Ticket Types**:

| Type | Detection Focus |
|------|----------------|
| `gui-only` | CSS/JS/XML, screenshots, layout/display keywords |
| `backend-only` | Python models, compute/constraint, ORM methods |
| `full-stack` | Both model + view references, form/tree + business logic |
| `data-fix` | Orphaned records, migration, wrong values, specific IDs |
| `investigation` | Unclear root cause, intermittent, no clear fix path |
| `performance` | Slow/freeze, N+1, heavy queries, browser hang |
| `configuration` | Access rights, permissions, groups, cron, settings |

See `config/ticket-types.yaml` for full keyword lists.

### Step 3: Determine Approach

Apply `config/approach-matrix.yaml` to map the classified type to:

1. **Skills to activate** - Which existing skills are needed
2. **Remote investigation first** - Query test/production DB before local work?
3. **Fresh environment needed** - Does this need an isolated test DB?
4. **Testing phases** - Phase 1 DB / Phase 2 ORM / E2E - which apply?
5. **Approach sequence** - Ordered resolution steps
6. **Module installation level** - For fresh-test-env (Level 1-4)
7. **Devin eligibility** - `yes` / `maybe` / `no` verdict from the matrix, plus the human-readable `devin_eligibility_reason`. This decides whether `/devin-implement` will accept the ticket:
   - `yes` → /devin-implement runs without prompt
   - `maybe` → /devin-implement prints the reason and asks `proceed? (y/N)`
   - `no` → /devin-implement refuses; planner falls back to manual `/tdd`

   The verdict is a heuristic — `/devin-implement --force-eligibility yes` can override after the planner has resolved the maybe/no in the plan body.

### Step 4: Detect Environment

Check JIRA description for server/environment references:

| Pattern | Environment | DB Profile |
|---------|-------------|------------|
| `192.168.1.240`, `192.168.1.241`, `production` | Production | `remote_nwf_production` |
| `192.168.1.243`, `192.168.1.244`, `test server` | Test Server | `remote_nwf_test_server_database` |
| `localhost:8079`, `local`, `dev` | Local Dev | `local` (port 5436) |
| No server reference | Default to test | `remote_nwf_test_server_database` |

Reference: `.claude/skills/postgresql-db-analyze/SKILL.md` for DB profile details.

### Step 5: Identify Affected Components

Scan ticket text for model/module references:

| Pattern | Component |
|---------|-----------|
| `attendance`, `bang cong`, `cham cong` | `rm.hr.attendance.sheet`, `hr.attendance` |
| `leave`, `nghi phep` | `hr.leave`, `hr.leave.allocation` |
| `payroll`, `luong`, `payslip` | `hr.payslip`, `nwf.hr.payroll` |
| `contract`, `hop dong` | `hr.contract` |
| `employee`, `nhan vien` | `hr.employee` |
| `audit`, `kiem toan` | `nc.hr.audit.*` |
| `mrp`, `manufacturing`, `san xuat` | `mrp.production`, `nwf.wfx.*` |
| `excel`, `report`, `bao cao` | `nwf.excel.*` |

### Step 6: Generate Output

Write `.docs/tasks/NCNB-XXXX/ticket-analysis.md` using the template from `templates/analysis-output.md`.

Fill the **## Implementor** section from the chosen ticket type's `implementor:` block in
`config/approach-matrix.yaml`:
- `{implementor_default}` ← `implementor.default` (opencode / claude-manual)
- `{implementor_opencode_model}` ← `implementor.opencode_model` (null for claude-manual)
- `{implementor_devin_fallback}` ← `implementor.devin_fallback`

This is what `/opencode-implement` reads to route the build (Claude plans, opencode implements;
`data-fix` / `investigation` stay manual). Model tier follows `estimated_complexity`
(simple → glm-5, medium → kimi-k2.6, complex → qwen3.7-max) per performance.md "Implementor Routing".

---

## Decision Matrix Summary

| Type | DB Analyze | Fresh Env | Phase 1 | Phase 2 | E2E | Issue Reproducer |
|------|-----------|-----------|---------|---------|-----|------------------|
| gui-only | - | - | - | Yes | **Yes** | - |
| backend-only | **Yes** | Conditional | **Yes** | **Yes** | - | Conditional |
| full-stack | **Yes** | Conditional | **Yes** | **Yes** | **Yes** | **Yes** |
| data-fix | **Yes** | - | **Yes** | - | - | - |
| investigation | **Yes** | - | **Yes** | Cond. | Cond. | Conditional |
| performance | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | - |
| configuration | **Yes** | - | **Yes** | **Yes** | Cond. | - |

**Conditional** = Only if complexity >= Medium or involves multiple modules.

---

## Vietnamese Keyword Reference

Many JIRA tickets have Vietnamese descriptions. Key mappings:

| Vietnamese | English | Domain |
|------------|---------|--------|
| bang cong | attendance sheet | HR Attendance |
| cham cong | attendance/check-in | HR Attendance |
| nghi phep | leave | HR Leave |
| luong | salary/payroll | HR Payroll |
| hop dong | contract | HR Contract |
| nhan vien | employee | HR Employee |
| phong ban | department | HR Department |
| phan quyen | access rights | Security |
| cham / treo | slow / freeze | Performance |
| loi | error | Bug |
| khong hien thi | not displayed | GUI |
| sai | wrong/incorrect | Data |
| mat du lieu | data loss | Data |
| bao cao | report | Reporting |
| san xuat | manufacturing | MRP |
| kiem toan | audit | Audit |
| tinh lai | recalculate | Compute |
| cap nhat | update | General |

**Note**: Vietnamese text in JIRA often lacks diacritics. Match both with and without accents:
- `bảng công` / `bang cong`
- `nghỉ phép` / `nghi phep`
- `chấm công` / `cham cong`
- `lương` / `luong`
- `phân quyền` / `phan quyen`
- `chậm` / `cham` (context: speed)

---

## Risk Assessment Matrix

| Factor | Low Risk | Medium Risk | High Risk |
|--------|----------|-------------|-----------|
| Data scope | Single record | Department/batch | Company-wide |
| Module coupling | Single module | 2-3 modules | Cross-module chain |
| User impact | Admin only | Department users | All employees |
| Reversibility | Easy rollback | Needs migration | Irreversible |
| Production data | No prod data | Read-only prod | Writes to prod |

---

## Plan Section Recommendations

Based on ticket type, recommend which sections the `NCNB-XXXX-plan.md` should carry (beyond the standard Context / Approach / Steps / Risks / Acceptance Criteria):

| Type | Plan must cover |
|------|-----------------|
| gui-only | view changes, Phase 2 tests |
| backend-only | model design, business-logic steps, Phase 1+2 tests |
| full-stack | planning, model, security, views, logic, tests |
| data-fix | investigation, SQL/ORM fix, verification query, rollback |
| investigation | investigation section only (plan stays open-ended until root cause found) |
| performance | baseline measurement, optimization steps, benchmark criteria, tests |
| configuration | ACL/rule change, Phase 2 test confirming behavior |

---

## Integration Points

- **Input from**: `atlassian-jira-confluence` skill (JIRA data fetching)
- **Output to**: `/jira-to-task` command (Step 1.5), `progress-tracker.md`
- **References**: `postgresql-db-analyze` (DB profiles), `fresh-test-env` (environment levels)
- **Config files**: `config/ticket-types.yaml`, `config/approach-matrix.yaml`
- **Template**: `templates/analysis-output.md`
