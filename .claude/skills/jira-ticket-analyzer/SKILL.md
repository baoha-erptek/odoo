---
name: jira-ticket-analyzer
description: Classify ESTY JIRA tickets and determine optimal resolution approach before work begins. Runs FIRST in the /jira-to-task workflow to select skills, testing strategy, and environment needs.
---

# JIRA Ticket Analyzer Skill (ESTY)

Pre-work analysis that classifies tickets and recommends the optimal approach before any
code changes begin. Ported for the **ESTY** project (`erptek.atlassian.net`); credentials
come from the project `.env` (`JIRA_SERVER_URL`, `JIRA_PROJECT_KEY`, `JIRA_USER_EMAIL`,
`JIRA_API_KEY`) — same contract as the `jira-create` skill.

## Quick Start

```bash
# Invoked automatically by /jira-to-task (Step 4)
# Or manually:
# 1. Fetch ticket data
# 2. Apply ticket-types.yaml classification
# 3. Apply approach-matrix.yaml recommendations
# 4. Generate .docs/tasks/ESTY-XXXX/ticket-analysis.md
```

## Workflow

### Step 1: Fetch Ticket Data

```bash
set -a; source "$(git rev-parse --show-toplevel)/.env"; set +a
curl -s -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
  "${JIRA_SERVER_URL%/}/rest/api/3/issue/ESTY-XXXX"
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
2. **Remote investigation first** - Query staging DB before local work?
3. **Testing phases** - Phase 1 DB / Phase 2 ORM / E2E - which apply?
4. **Approach sequence** - Ordered resolution steps
5. **Plan sections** - Which sections the `ESTY-XXXX-plan.md` should carry

Implementation always goes through `/plan` (planner agent) then `/tdd` (tdd-guide) —
esty does not use Devin/opencode routing.

### Step 4: Detect Environment

Check JIRA description for server/environment references:

| Pattern | Environment | DB |
|---------|-------------|-----|
| `129.150.63.207`, `staging`, `hatafa`, `docs.hatafa.erptek.net` | Staging | `esty_odoo19` (memory `reference_staging_db_name`) |
| `localhost:8169`, `local`, `dev`, `namco` | Local Dev | `namco_odoo19` (port 8169) |
| No server reference | Default to local | `namco_odoo19` |

Staging access: `ubuntu@129.150.63.207` (memory `reference_staging_ssh_deploy`).

### Step 5: Identify Affected Components

Scan ticket text for model/module references (esty domain):

| Pattern | Component |
|---------|-----------|
| `order`, `sale`, `receipt`, `don hang` | `sale.order`, `sale.order.line` |
| `product`, `listing`, `variant`, `san pham` | `product.template`, `product.product`, `product.attribute` |
| `image`, `design`, `mockup`, `anh`, `thiet ke` | `product.image`, `ir.attachment`, `design.file` |
| `etsy`, `shop`, `channel` | `etsy.shop`, `etsy.email.log`, `multichannel.listing` |
| `gearment`, `fulfil`, `dropship`, `tracking`, `van chuyen` | `gearment.*`, `stock.picking`, delivery/tracking |
| `partner`, `customer`, `khach hang` | `res.partner` |
| `email`, `gmail`, `import` | `etsy.email.log`, import wizard |
| `dashboard`, `report`, `bao cao` | `multichannel_hub` dashboard tiles |

### Step 6: Generate Output

Write `.docs/tasks/ESTY-XXXX/ticket-analysis.md` using the template from `templates/analysis-output.md`.

---

## Decision Matrix Summary

| Type | DB Analyze | Fresh Env | Phase 1 | Phase 2 | E2E |
|------|-----------|-----------|---------|---------|-----|
| gui-only | - | - | - | Yes | **Yes** |
| backend-only | **Yes** | Conditional | **Yes** | **Yes** | - |
| full-stack | **Yes** | Conditional | **Yes** | **Yes** | **Yes** |
| data-fix | **Yes** | - | **Yes** | - | - |
| investigation | **Yes** | - | **Yes** | Cond. | Cond. |
| performance | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| configuration | **Yes** | - | **Yes** | **Yes** | Cond. |

**Conditional** = Only if complexity >= Medium or involves multiple modules.

---

## Vietnamese Keyword Reference

Tickets are often written in Vietnamese. Key mappings (esty domain):

| Vietnamese | English | Domain |
|------------|---------|--------|
| don hang | order | Sales |
| san pham | product | Product |
| thiet ke / mau | design / mockup | Design files |
| khach hang | customer | Partner |
| van chuyen | shipping / fulfilment | Gearment / Stock |
| ma van don | tracking number | Fulfilment |
| giao dien | UI | GUI |
| khong hien thi | not displayed | GUI |
| tinh toan / tinh lai | compute / recalculate | Backend |
| phan quyen | access rights | Security |
| cham / treo | slow / freeze | Performance |
| loi | error | Bug |
| sai | wrong/incorrect | Data |
| mat du lieu | data loss | Data |
| bao cao | report | Reporting |

**Note**: Vietnamese text in JIRA often lacks diacritics. Match both with and without accents
(e.g. `đơn hàng` / `don hang`, `sản phẩm` / `san pham`, `phân quyền` / `phan quyen`).

---

## Risk Assessment Matrix

| Factor | Low Risk | Medium Risk | High Risk |
|--------|----------|-------------|-----------|
| Data scope | Single record | Batch / one shop | All shops / company-wide |
| Module coupling | Single module | 2-3 modules | Cross-module chain |
| User impact | Admin only | One team | All users |
| Reversibility | Easy rollback | Needs migration | Irreversible |
| Production data | No prod data | Read-only staging | Writes to staging/live |

---

## Plan Section Recommendations

Based on ticket type, recommend which sections the `ESTY-XXXX-plan.md` should carry (beyond the standard Context / Approach / Steps / Risks / Acceptance Criteria):

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

- **Input from**: `/jira-to-task` command (Step 1 fetches the JIRA data)
- **Output to**: `.docs/tasks/ESTY-XXXX/ticket-analysis.md`, then `/plan`
- **Config files**: `config/ticket-types.yaml`, `config/approach-matrix.yaml`
- **Template**: `templates/analysis-output.md`
- **Standard-Odoo-First**: for any ticket implying a new field/model, route through the
  `odoo-standard-first` decision before proposing custom work (project CLAUDE.md rule).
