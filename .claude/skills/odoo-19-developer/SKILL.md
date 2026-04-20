# Odoo 19 Developer Skill

**Priority**: 1 (Highest - Auto-enabled for all sessions)
**Version**: 19.0
**Framework**: Odoo 19 Community Edition

## Overview

Comprehensive Odoo 19 CE development guidelines covering TDD, ORM patterns, security, testing, and best practices. This skill is **automatically enabled** for all Claude Code sessions in this workspace.

## Activation

- **Default**: Always active (1st priority)
- **Triggers**: Any Odoo-related work, Python files in custom_addons/, model/view/controller modifications
- **Context**: Odoo 19 + Python 3.12+ + PostgreSQL 15+

## Quick Reference

### Core Principles
- **TDD is NON-NEGOTIABLE** - Every line of production code responds to a failing test
- **Evidence-based** - Show file:line references for code, table:column for data
- **ORM-first** - Use ORM for regular CRUD; direct SQL for bulk operations (1000+ records)
- **Security-first** - Always consider access rights and record rules
- **Multi-company** - Use `company_ids` pattern (standard Odoo), always include NULL fallback

### Two-Phase Testing (MANDATORY)
1. **Phase 1**: Direct Database Testing with real data during development
2. **Phase 2**: Odoo Standard Tests in `module/tests/` after implementation

### Key Commands
```bash
# Update module
docker exec namco_odoo19 odoo -d namco_odoo19 -u MODULE_NAME --stop-after-init

# Run tests
docker exec namco_odoo19 python3 -m odoo.tests.loader MODULE_NAME.tests

# Access container
docker exec -it namco_odoo19 bash
```

## Module Structure

```
my_module/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── my_model.py
├── views/
│   └── my_model_views.xml
├── data/
│   └── ir_cron_data.xml
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
├── tests/
│   ├── __init__.py
│   └── test_my_model.py
├── static/src/
│   ├── js/
│   ├── css/
│   └── xml/
├── wizards/
│   ├── __init__.py
│   └── my_wizard.py
└── services/
    ├── __init__.py
    └── my_service.py
```

## ORM Quick Reference (Odoo 19)

### Field Types
```python
from odoo import models, fields, api

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _order = 'name asc'

    # Basic fields
    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    amount = fields.Float(digits=(16, 2))
    date = fields.Date()
    datetime = fields.Datetime()
    
    # Selection
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], default='draft', tracking=True)
    
    # Relational
    partner_id = fields.Many2one('res.partner', ondelete='restrict')
    line_ids = fields.One2many('my.model.line', 'parent_id')
    tag_ids = fields.Many2many('my.model.tag')
    
    # Computed
    total = fields.Float(compute='_compute_total', store=True)
    
    @api.depends('line_ids.amount')
    def _compute_total(self):
        for record in self:
            record.total = sum(record.line_ids.mapped('amount'))
```

### API Decorators
- `@api.depends('field1', 'field2')` — computed field dependencies (REQUIRED)
- `@api.constrains('field1')` — data validation constraints
- `@api.onchange('field1')` — UI-only onchange (not triggered by ORM writes)
- `@api.model` — class-level method (no recordset)
- `@api.model_create_multi` — batch create optimization

### CRUD Operations
```python
# Create
record = self.env['my.model'].create({'name': 'Test'})

# Read
records = self.env['my.model'].search([('state', '=', 'draft')])
record = self.env['my.model'].browse(record_id)

# Update
record.write({'state': 'confirmed'})

# Delete
record.unlink()

# Search with domain
records = self.env['my.model'].search([
    ('date', '>=', fields.Date.today()),
    ('partner_id.is_company', '=', True),
], limit=100, order='date desc')
```

## JavaScript Development (Odoo 19)

Odoo 19 uses **OWL 2.0** (Odoo Web Library) — a modern reactive component framework.

### OWL Component Pattern
```javascript
/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class MyComponent extends Component {
    static template = "my_module.MyComponent";
    static props = {
        record: Object,
    };

    setup() {
        this.state = useState({ count: 0 });
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async onButtonClick() {
        const result = await this.orm.call(
            "my.model", "action_confirm", [this.props.record.id]
        );
        this.notification.add("Confirmed!", { type: "success" });
    }
}

// Register as a field widget, action, etc.
registry.category("fields").add("my_widget", {
    component: MyComponent,
});
```

### Asset Registration (Odoo 19)
```python
# __manifest__.py
{
    'assets': {
        'web.assets_backend': [
            'my_module/static/src/js/**/*',
            'my_module/static/src/xml/**/*',
            'my_module/static/src/css/**/*',
        ],
    },
}
```

### Key Differences from Odoo 15
| Odoo 15 | Odoo 19 |
|---------|---------|
| `Class.extend({})` / `Class.include({})` | OWL 2.0 `Component` classes |
| `require('module')` AMD | `import {} from "@module"` ES modules |
| jQuery DOM manipulation | Reactive `useState`, `useRef` |
| `qweb` key in manifest | `assets` key in manifest |
| `this._rpc({model, method})` | `useService("orm").call()` |
| `AbstractAction` | `Component` + action registry |
| `this._super.apply()` | Standard `super.method()` |

## Security Checklist

- [ ] `security/ir.model.access.csv` defined for all new models
- [ ] Record rules for sensitive data (multi-company, ownership)
- [ ] `sudo()` usage documented with inline comment
- [ ] No raw SQL without parameterization
- [ ] No hardcoded credentials

## Performance Quick Reference

| Operation | Records | Approach |
|-----------|---------|----------|
| CRUD | < 100 | **ORM** (security, triggers, cache) |
| Bulk DELETE | 1,000+ | **SQL** with SAVEPOINT |
| Bulk INSERT | 1,000+ | **SQL** with SAVEPOINT |
| Bulk UPDATE | 1,000+ | **SQL** with SAVEPOINT |
| Complex aggregation | Large dataset | **SQL** or `read_group()` |

## Code Review Checklist

- [ ] **Phase 1**: Direct Database Testing with real data
- [ ] **Phase 2**: Unit tests in `module/tests/` folder
- [ ] Type hints for method signatures
- [ ] Security considerations addressed
- [ ] ORM for regular CRUD; SQL with SAVEPOINT for bulk (1000+) ops
- [ ] Proper Odoo exceptions used (`UserError`, `ValidationError`)
- [ ] Access rights defined
- [ ] Performance implications considered
- [ ] Code follows Odoo conventions
- [ ] Tests and code committed together

## Official Documentation

- [Odoo 19 Developer Documentation](https://www.odoo.com/documentation/19.0/developer.html)
- [ORM API Reference](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html)
- [Views Reference](https://www.odoo.com/documentation/19.0/developer/reference/backend/views.html)
- [Testing Framework](https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html)
- [OWL Documentation](https://www.odoo.com/documentation/19.0/developer/reference/frontend/owl.html)
