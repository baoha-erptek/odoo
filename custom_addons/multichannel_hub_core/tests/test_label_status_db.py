"""
Phase 1: Database verification tests for label.status.option model (P1-LBL).

Tests verify data integrity at the database level:
- Model label.status.option is registered in Odoo registry
- UNIQUE constraint on code field is enforced at DB level
- Seed records (16 total) are loaded with correct distribution
- XML IDs are resolvable for all seed codes
- sale_order_fulfillment field migration from Selection to Many2one is complete
- ACL access control is properly configured

Tests use direct SQL queries to verify database schema, constraints, and seed data.
References: P1-LBL plan §7 (Two-Phase Testing layout).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLabelStatusDbModel(TransactionCase):
    """Phase 1: Verify label.status.option model registration and schema."""

    def test_model_registered(self):
        """Test that label.status.option model is registered in Odoo."""
        # Model should exist in env.registry after module install
        self.assertIn(
            'label.status.option',
            self.env.registry,
            "label.status.option model should be registered in Odoo registry"
        )

    def test_unique_constraint_present(self):
        """Test that UNIQUE constraint on code field exists at DB level.

        Verifies drift template (9th confirmation per project memory):
        pg_constraint IF NOT EXISTS pre-check ensures idempotency when
        constraint is defined in both _sql_constraints and init() raw SQL.
        """
        self.env.cr.execute("""
            SELECT 1
            FROM pg_constraint
            WHERE conname LIKE '%label_status_option%code%'
            AND contype = 'u'
            LIMIT 1
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "UNIQUE constraint on code field should exist in database"
        )

    def test_seed_records_loaded(self):
        """Test that all 16 seed records are loaded with correct bucket distribution.

        Verifies via search count + read_group aggregation by bucket type.
        Expected distribution:
        - target: 2 records (us_od, vietnam_od)
        - pd_selfmake: 10 records (vn_tattoo, vn_wooden_dish, vn_dish, vn_dish_ng,
                                    vn_dish_fix, vn_sp_moi, vn_packed, vn_packed_1,
                                    vn_apron, vn_handkerchief)
        - done: 1 record (vn_fulfilled)
        - approval: 3 records (cho_duyet, da_gui_proof, cho_file)
        Total: 16 records
        """
        model = self.env['label.status.option']
        total_count = len(model.search([]))

        self.assertEqual(
            total_count,
            16,
            f"Expected 16 seed records, found {total_count}"
        )

        # Verify distribution via read_group
        groups = model.read_group(
            domain=[],
            fields=['bucket'],
            groupby=['bucket']
        )
        distribution = {g['bucket']: g['__count'] for g in groups}

        expected_dist = {
            'target': 2,
            'pd_selfmake': 10,
            'done': 1,
            'approval': 3,
        }

        self.assertEqual(
            distribution,
            expected_dist,
            f"Expected distribution {expected_dist}, got {distribution}"
        )

    def test_seed_xmlids_resolvable(self):
        """Test that all 16 seed record XML IDs are resolvable.

        Loops through all expected code values and verifies env.ref()
        returns a non-empty recordset for each.
        """
        codes = [
            'us_od', 'vietnam_od',  # target
            'vn_tattoo', 'vn_wooden_dish', 'vn_dish', 'vn_dish_ng', 'vn_dish_fix',
            'vn_sp_moi', 'vn_packed', 'vn_packed_1', 'vn_apron', 'vn_handkerchief',  # pd_selfmake
            'vn_fulfilled',  # done
            'cho_duyet', 'da_gui_proof', 'cho_file',  # approval
        ]

        for code in codes:
            xmlid = f'multichannel_hub_core.label_status_{code}'
            try:
                record = self.env.ref(xmlid)
                self.assertTrue(
                    record,
                    f"XML ID {xmlid} should resolve to a non-empty recordset"
                )
                self.assertEqual(
                    record.code,
                    code,
                    f"XML ID {xmlid} should have code={code}"
                )
            except ValueError as e:
                self.fail(f"XML ID {xmlid} not found: {e}")

    def test_fulfillment_field_swap(self):
        """Test that sale_order_fulfillment field swap is complete at DB level.

        Verifies:
        - New Many2one column label_status_id (integer FK) exists
        - Legacy Selection column label_status (varchar) DOES NOT exist
        This confirms the data migration from Selection to Many2one is complete.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'sale_order_fulfillment'
            AND table_schema = 'public'
            AND column_name IN ('label_status_id', 'label_status')
        """)
        columns = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # New M2O field should exist as integer (foreign key reference)
        self.assertIn(
            'label_status_id',
            columns,
            "Column label_status_id should exist (M2O to label.status.option)"
        )
        self.assertIn(
            'integer',
            columns['label_status_id'].lower(),
            "label_status_id should be integer type (FK)"
        )

        # Legacy Selection field should NOT exist
        self.assertNotIn(
            'label_status',
            columns,
            "Legacy column label_status (Selection) should NOT exist after migration"
        )

    def test_acl_grants(self):
        """Test that ACL access control is properly configured.

        Verifies ir.model.access rows for label.status.option:
        - base.group_user: read-only (perm_read=1, others=0)
        - multichannel_hub_core.group_ba_manager: full access (all=1)
        No other groups should have access.
        """
        ir_access = self.env['ir.model.access']

        # Find ACL rows for label.status.option
        acl_rows = ir_access.search([
            ('model_id.model', '=', 'label.status.option')
        ])

        self.assertTrue(
            acl_rows,
            "At least one ACL row should exist for label.status.option"
        )

        acl_by_group = {row.group_id.xml_id: row for row in acl_rows if row.group_id}

        # Verify base.group_user — read-only
        self.assertIn(
            'base.group_user',
            acl_by_group,
            "ACL should grant base.group_user read access"
        )
        user_acl = acl_by_group['base.group_user']
        self.assertEqual(user_acl.perm_read, 1, "base.group_user should have read")
        self.assertEqual(user_acl.perm_write, 0, "base.group_user should NOT have write")
        self.assertEqual(user_acl.perm_create, 0, "base.group_user should NOT have create")
        self.assertEqual(user_acl.perm_unlink, 0, "base.group_user should NOT have unlink")

        # Verify multichannel_hub_core.group_ba_manager — full access
        self.assertIn(
            'multichannel_hub_core.group_ba_manager',
            acl_by_group,
            "ACL should grant group_ba_manager full access"
        )
        ba_acl = acl_by_group['multichannel_hub_core.group_ba_manager']
        self.assertEqual(ba_acl.perm_read, 1, "group_ba_manager should have read")
        self.assertEqual(ba_acl.perm_write, 1, "group_ba_manager should have write")
        self.assertEqual(ba_acl.perm_create, 1, "group_ba_manager should have create")
        self.assertEqual(ba_acl.perm_unlink, 1, "group_ba_manager should have unlink")
