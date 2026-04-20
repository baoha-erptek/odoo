---
paths:
  - "custom_addons/**/*.py"
---

# Odoo Python Coding Style

Extends: `common/coding-style.md`

## PEP 8 + Odoo Conventions
- Line length: 120 characters max
- Import order: stdlib, odoo core, odoo addons, project modules
- Use `_logger = logging.getLogger(__name__)` (not `logging.getLogger('module_name')`)

## Model Definitions
- Always include `_description` on models
- Specify `_order` for consistent query results
- Use `_rec_name` when display field is not `name`
- Specify `ondelete` on all Many2one fields

## Field Ordering in Models
1. `_name`, `_description`, `_inherit`, `_order`, `_rec_name`
2. Fields (grouped by type: Char, Text, Integer, Float, Boolean, Date, Selection, Many2one, One2many, Many2many)
3. Computed field definitions
4. Constraint methods (`_check_*`)
5. Compute methods (`_compute_*`)
6. Onchange methods (`_onchange_*`)
7. CRUD overrides (`create`, `write`, `unlink`)
8. Action methods (`action_*`)
9. Private methods (`_*`)

## Logging
- `_logger.debug()` for investigation and debugging
- `_logger.warning()` for recoverable issues
- `_logger.error()` for failures needing attention
- **Never** use `_logger.info()` for debugging — only for significant operational events
- **Never** use `print()` — always use `_logger`

## API Decorators
- `@api.depends` required on all compute methods
- `@api.constrains` for data validation
- `@api.onchange` for UI-only updates
- Never use `@api.one` (deprecated) or `@api.multi` (removed)
