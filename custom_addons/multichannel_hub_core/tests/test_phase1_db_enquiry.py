"""Phase 1: Database-level verification for multichannel.enquiry model.

Tests verify that the underlying PostgreSQL schema is correctly set up:
- multichannel_enquiry table exists with all required columns
- Partial UNIQUE index on (etsy_shop_id, etsy_conversation_id) exists
- Composite index on (partner_email, state) exists
- Foreign key constraints are properly configured with correct ondelete actions

Tests use direct SQL via self.env.cr.execute to verify the database state
at the lowest level, independent of ORM machinery.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'p3_lead_model')
class TestEnquiryPhase1(TransactionCase):
    """Direct PostgreSQL verification for multichannel.enquiry schema."""

    def test_table_exists(self):
        """Verify multichannel_enquiry table exists in the database."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'multichannel_enquiry'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]
        self.assertTrue(table_exists, "multichannel_enquiry table must exist")

    def test_columns_match_spec(self):
        """Verify all required columns exist with correct data types."""
        self.env.cr.execute("""
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'multichannel_enquiry'
            ORDER BY column_name
        """)
        columns = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Verify required fields per data-model.md §1
        expected_fields = {
            'name': 'varchar',
            'partner_id': 'int4',
            'partner_email': 'varchar',
            'subject': 'varchar',
            'source': 'varchar',
            'etsy_shop_id': 'int4',
            'etsy_conversation_id': 'varchar',
            'state': 'varchar',
            'assigned_user_id': 'int4',
            'converted_order_id': 'int4',
            'converted_at': 'timestamp',
            'closed_reason': 'varchar',
            'notes': 'text',
            'active': 'bool',
        }

        for field_name, expected_type in expected_fields.items():
            self.assertIn(
                field_name, columns,
                f"Field '{field_name}' must exist on multichannel_enquiry"
            )
            self.assertEqual(
                columns[field_name], expected_type,
                f"Field '{field_name}' type must be '{expected_type}', "
                f"got '{columns[field_name]}'"
            )

    def test_partial_unique_index_exists(self):
        """Verify partial UNIQUE index idx_mhe_etsy_conv exists.

        PG normalizes WHERE clause to ((col)::text = ...) form.
        Assert substring presence, not byte-exact match (memory gotcha #74).
        """
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname = 'idx_mhe_etsy_conv'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "Partial UNIQUE index 'idx_mhe_etsy_conv' must exist"
        )
        indexdef = result[0].upper()
        self.assertIn(
            'ETSY_CONVERSATION_ID',
            indexdef,
            "Index must include etsy_conversation_id column"
        )
        self.assertIn(
            'IS NOT NULL',
            indexdef,
            "Partial UNIQUE index must have 'IS NOT NULL' WHERE clause"
        )
        self.assertIn(
            'UNIQUE',
            indexdef,
            "Index must be UNIQUE"
        )

    def test_composite_index_exists(self):
        """Verify composite non-unique index idx_mhe_partner_email_state."""
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname = 'idx_mhe_partner_email_state'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "Composite index 'idx_mhe_partner_email_state' must exist"
        )
        indexdef = result[0].upper()
        self.assertIn(
            'PARTNER_EMAIL',
            indexdef,
            "Index must include partner_email column"
        )
        self.assertIn(
            'STATE',
            indexdef,
            "Index must include state column"
        )

    def test_fk_ondelete_specs(self):
        """Verify FK constraints have correct ondelete actions.

        Per data-model.md §1:
        - partner_id: RESTRICT
        - etsy_shop_id: RESTRICT
        - assigned_user_id: SET NULL
        - converted_order_id: SET NULL
        """
        # Query FK constraints + their column info.
        # Memory gotcha: information_schema.referential_constraints lacks
        # table_name/column_name — JOIN on constraint_name only and filter
        # via key_column_usage.table_name.
        self.env.cr.execute("""
            SELECT
                kcu.column_name,
                rc.delete_rule
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu
                ON rc.constraint_name = kcu.constraint_name
            WHERE kcu.table_schema = 'public'
            AND kcu.table_name = 'multichannel_enquiry'
            ORDER BY kcu.column_name
        """)
        fks = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Verify RESTRICT FKs
        for fk_col in ['partner_id', 'etsy_shop_id']:
            self.assertIn(
                fk_col, fks,
                f"FK constraint on {fk_col} must exist"
            )
            self.assertEqual(
                fks[fk_col], 'RESTRICT',
                f"FK {fk_col} must have RESTRICT delete rule, "
                f"got {fks[fk_col]}"
            )

        # Verify SET NULL FKs
        for fk_col in ['assigned_user_id', 'converted_order_id']:
            self.assertIn(
                fk_col, fks,
                f"FK constraint on {fk_col} must exist"
            )
            self.assertEqual(
                fks[fk_col], 'SET NULL',
                f"FK {fk_col} must have SET NULL delete rule, "
                f"got {fks[fk_col]}"
            )
