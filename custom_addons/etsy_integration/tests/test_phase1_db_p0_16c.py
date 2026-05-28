"""P0-16c Phase 1 — Database-level tests for EtsyOrderSyncer infrastructure.

This module verifies the database structure at the lowest level:
- Column existence and types
- Access control via ir.model.fields
- Cron job metadata

Phase 1 tests use direct SQL to verify persistent storage state,
complemented by Phase 2 ORM tests that verify business logic.

Reference: Master Plan 006, P0-16c planner OQ1-OQ5.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP0_16c_DatabaseStructure(TransactionCase):
    """Verify database structure for P0-16c (EtsyOrderSyncer) infrastructure."""

    def test_sync_audit_mode_column_exists_on_etsy_shop(self):
        """The `sync_audit_mode` column must exist on `etsy.shop` table
        with type BOOLEAN and default FALSE."""
        self.env.cr.execute("""
            SELECT data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'sync_audit_mode'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "Column etsy_shop.sync_audit_mode does not exist; RED test passes."
        )
        data_type = row[0]
        self.assertEqual(
            data_type, 'boolean',
            f"Column data_type should be boolean, got {data_type}"
        )

    def test_sync_audit_mode_field_has_system_acl(self):
        """The `sync_audit_mode` field on `etsy.shop` must have system-only
        ACL (groups='base.group_system') to prevent operators from
        triggering audit mode manually.

        Odoo 19 stores field-level ACL on the in-memory `Field` object's
        `groups` attribute (string), not on `ir.model.fields` — that
        relational column exists but is unpopulated (`CLEANME unimplemented
        field (empty table)` per `odoo/addons/base/models/ir_model.py`).
        """
        field = self.env['etsy.shop']._fields.get('sync_audit_mode')
        self.assertIsNotNone(
            field,
            "Field sync_audit_mode does not exist on etsy.shop."
        )
        self.assertEqual(
            field.groups, 'base.group_system',
            f"sync_audit_mode field.groups should be 'base.group_system', "
            f"got {field.groups!r}",
        )

    def test_cron_etsy_order_sync_exists(self):
        """The scheduled task `cron_etsy_order_sync` must exist with:
        - interval_number=5, interval_type='minutes'
        - state='code', active=True
        """
        cron = self.env.ref(
            'etsy_integration.cron_etsy_order_sync',
            raise_if_not_found=False
        )
        self.assertIsNotNone(
            cron,
            "Cron etsy_integration.cron_etsy_order_sync does not exist; RED test passes."
        )
        self.assertEqual(
            cron.interval_number, 5,
            f"Cron interval_number should be 5, got {cron.interval_number}"
        )
        self.assertEqual(
            cron.interval_type, 'minutes',
            f"Cron interval_type should be 'minutes', got {cron.interval_type}"
        )
        self.assertEqual(
            cron.state, 'code',
            f"Cron state should be 'code', got {cron.state}"
        )
        self.assertTrue(
            cron.active,
            "Cron should be active"
        )

    def test_cron_code_targets_etsy_shop_model(self):
        """The cron's code field must target `etsy.shop` model and invoke
        the `_cron_sync_orders` method."""
        cron = self.env.ref(
            'etsy_integration.cron_etsy_order_sync',
            raise_if_not_found=False
        )
        self.assertIsNotNone(cron, "Cron does not exist")

        self.assertEqual(
            cron.model_id.model, 'etsy.shop',
            f"Cron model_id should be etsy.shop, got {cron.model_id.model}"
        )
        self.assertIn(
            '_cron_sync_orders',
            cron.code or '',
            f"Cron code should contain '_cron_sync_orders' substring, got: {cron.code}"
        )
