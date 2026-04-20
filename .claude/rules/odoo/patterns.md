---
paths:
  - "custom_addons/**/*.py"
  - "custom_addons/**/*.xml"
---

# Odoo Development Patterns

## Inheritance Patterns

### Classical Inheritance (_inherit without _name)
```python
class HrEmployeeExtension(models.Model):
    _inherit = 'hr.employee'
    # Adds fields/methods to existing model
    custom_field = fields.Char(string="Custom Field")
```

### Delegation Inheritance (_inherits)
```python
class CustomModel(models.Model):
    _name = 'custom.model'
    _inherits = {'res.partner': 'partner_id'}
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
```

### Abstract Models
```python
class CommonMixin(models.AbstractModel):
    _name = 'common.mixin'
    _description = 'Common Mixin'
    # Shared fields/methods, no database table
```

## Wizard Pattern
```python
class MyWizard(models.TransientModel):
    _name = 'my.module.wizard'
    _description = 'My Wizard'

    def action_confirm(self):
        active_ids = self.env.context.get('active_ids', [])
        records = self.env['target.model'].browse(active_ids)
        # Process records
        return {'type': 'ir.actions.act_window_close'}
```

## State Machine Pattern
```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('done', 'Done'),
    ('cancelled', 'Cancelled'),
], default='draft', tracking=True)

def action_confirm(self):
    self.filtered(lambda r: r.state == 'draft').write({'state': 'confirmed'})

def action_cancel(self):
    self.filtered(lambda r: r.state != 'done').write({'state': 'cancelled'})
```

## Cron Job Pattern
```xml
<record id="ir_cron_my_task" model="ir.cron">
    <field name="name">My Scheduled Task</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="state">code</field>
    <field name="code">model._cron_my_task()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
</record>
```

## Manifest Dependencies
- List ALL direct dependencies in `__manifest__.py`
- Order: Odoo core modules first, then custom modules
- Include `'installable': True` and `'application': False` (unless standalone app)
