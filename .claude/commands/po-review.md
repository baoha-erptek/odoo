---
allowed-tools: Read, Grep, Glob, Bash, Task
description: Invoke the product-owner agent to review a spec/feature/change from user + Odoo-developer perspectives
---

# /po-review — Product Owner Review

Invoke the `product-owner` agent to review a feature request, spec, or functional change —
challenging assumptions and validating acceptance criteria from both the end-user and the
Odoo-developer perspective.

## Usage
```
/po-review specs/001-my-feature       # Review a speckit spec
/po-review --challenge "..."          # Challenge a feature request
/po-review --diff                      # Review the working diff for user impact
```

## Arguments
- `specs/NNN-*` (optional): path to a spec folder or `spec.md` to review.
- `--challenge "<text>"`: a feature description to challenge constructively.
- `--diff`: review `git diff` for user-facing impact and doc gaps.

## Workflow

### Spec review (default, with a specs/ path)
1. Read the target `spec.md` (and any `plan.md` / `tasks.md` alongside it).
2. Run the **PO Analysis Framework** (see the `product-owner` agent): clarity, scope,
   user impact, acceptance criteria, standard-Odoo fit, dependencies, risk, docs.
3. Output the **PO Review** template.

### Feature challenge (`--challenge`)
1. Parse the feature description from arguments.
2. Run the **Feature Challenge Protocol** (who benefits, alternatives incl. standard Odoo,
   MVP, what breaks).
3. Output the **PO Challenge** template with a PROCEED / SIMPLIFY / DEFER / REJECT call.

### Diff review (`--diff`)
1. `git diff --name-only` (and content) for the working changes.
2. Assess user-facing impact, regression risk, and documentation impact.
3. Output the **PO Review** template scoped to the change.

## Agent
Delegates to the `product-owner` agent (`.claude/agents/product-owner.md`). Advisory only —
does not block.
