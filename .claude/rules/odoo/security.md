---
paths:
  - "addons/**/security/**"
  - "addons/**/__manifest__.py"
  - "addons/**/models/**/*.py"
---

# Odoo Security Rules

Extends: `common/security.md`

## Access Control Lists (ir.model.access.csv)
- Every new model MUST have ACL entries
- Define access for relevant groups (base.group_user, group_manager, etc.)
- Format: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`

```csv
access_my_model_user,my.model.user,model_my_model,base.group_user,1,0,0,0
access_my_model_manager,my.model.manager,model_my_model,my_module.group_manager,1,1,1,1
```

## Record Rules
- Define for multi-company isolation
- Define for department/team data segregation
- Use domain filters, not code-based checks

```xml
<record id="rule_my_model_company" model="ir.rule">
    <field name="name">My Model: Company Rule</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="domain_force">[('company_id','in',company_ids)]</field>
</record>
```

## sudo() Guidelines
- Always document WHY sudo is needed (inline comment)
- Minimize scope: sudo only the specific operation, not the whole method
- Never use sudo to bypass legitimate access restrictions

```python
# sudo required: System cron needs to update all records regardless of user permissions
# Security: Only updates computed status field, no sensitive data modified
records.sudo().write({'status': 'processed'})
```

## Raw SQL
- Prefer ORM methods over raw SQL
- When SQL is necessary, ALWAYS use parameterized queries
- Document why ORM couldn't be used

```python
# Raw SQL required: Complex aggregation not expressible via ORM groupby
self.env.cr.execute("""
    SELECT department_id, COUNT(*), SUM(amount)
    FROM hr_expense WHERE state = %s
    GROUP BY department_id
""", ('approved',))
```
