---
paths:
  - "custom_addons/**/tests/**/*.py"
---

# Odoo Two-Phase Testing

Extends: `common/testing.md`

## Phase 1: Database Verification (Development Testing)
- Direct SQL queries to verify data state
- Use `psql` or `self.env.cr.execute()` for verification
- Test data integrity, computed field storage, constraint enforcement
- Verify record rules and access control at DB level

```python
# Phase 1 example: verify computed field stored correctly
self.env.cr.execute("""
    SELECT total_amount FROM sale_order WHERE id = %s
""", (order.id,))
result = self.env.cr.fetchone()
self.assertEqual(result[0], expected_total)
```

## Phase 2: ORM Unit Tests
- Use `TransactionCase` for isolated tests
- Use `SavepointCase` for tests sharing expensive setup
- Test through ORM methods (create, write, search, unlink)
- Verify business logic, state machines, computed fields

```python
class TestMyModel(TransactionCase):
    def setUp(self):
        super().setUp()
        self.model = self.env['my.model']

    def test_create_sets_default_state(self):
        record = self.model.create({'name': 'Test'})
        self.assertEqual(record.state, 'draft')
```

## Test Naming
- `test_<action>_<scenario>_<expected_result>`
- Example: `test_confirm_order_with_no_lines_raises_error`

## Test Data
- Create minimal test data in setUp()
- Use `self.env.ref()` for demo data references
- Never depend on production data existing

## Running Tests
```bash
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /MODULE_NAME --stop-after-init
```
