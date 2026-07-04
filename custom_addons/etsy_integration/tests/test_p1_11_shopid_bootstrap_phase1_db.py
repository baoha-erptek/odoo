"""
Phase 1 Database Verification Tests for P1-11-SHOPID-BOOTSTRAP: Etsy shop_id auto-bootstrap.

Tests verify data structure (columns, indexes, constraints) at the database level.
This phase ensures all fields exist before Phase 2 ORM tests run.

Scope:
1. etsy_api_shop_id field: Char column, indexed, groups='base.group_system'
2. Field-level ACL: verified via in-memory Field object (not DB table)
3. Database-level index validation using regex-tolerant pg_indexes lookup

RED: These tests FAIL because the production code (controller OAuth callback,
constraint C-ESY-003, migration 19.0.2.31.0) does not yet implement the bootstrap logic.
Expected failure reasons documented in each test.
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase1_DB_Column(TransactionCase):
    """Phase 1: Verify etsy_api_shop_id database structure.

    FAILURE REASON for RED: Column exists but tests verify its correctness.
    This class confirms the field is persisted correctly.
    """

    def test_etsy_api_shop_id_column_exists_and_is_varchar(self):
        """PASS (field already added in 19.0.2.8.0): etsy_api_shop_id is a Char (varchar) column."""
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'etsy_api_shop_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_api_shop_id column must exist on etsy_shop table"
        )
        # Char field in Odoo becomes character varying in PostgreSQL
        self.assertEqual(
            result[1],
            'character varying',
            "etsy_api_shop_id must be character varying (Char field)"
        )

    def test_etsy_api_shop_id_has_index(self):
        """PASS: etsy_api_shop_id has a database index for performance.

        Odoo 19 uses DOUBLE underscore naming per gotcha #146.
        Use regex-tolerant lookup: %etsy_api_shop_id% not exact match.
        """
        # Query pg_indexes with pattern matching (not exact name)
        # Index name typically: etsy_shop__etsy_api_shop_id_index (double underscore)
        self.env.cr.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'etsy_shop' AND indexname LIKE '%etsy_api_shop_id%'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_api_shop_id must have a database index (field has index=True)"
        )

    def test_etsy_api_shop_id_column_allows_null(self):
        """PASS: etsy_api_shop_id is nullable (required only when active_source='api').

        NULL is legal on email-only shops; constraints enforce it only at write time.
        """
        self.env.cr.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'etsy_api_shop_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(result, "Column must exist")
        self.assertEqual(
            result[1],
            'YES',
            "etsy_api_shop_id must be nullable at DB level "
            "(constraint C-ESY-003 enforces it only for active_source='api')"
        )


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase1_DB_FieldACL(TransactionCase):
    """Phase 1: Verify field-level access control.

    Field-level groups= is stored in the Field object (runtime), not in the DB schema.
    We introspect the in-memory Field definition.

    FAILURE REASON for RED: Field definition is missing or ACL is not set correctly.
    """

    def test_etsy_api_shop_id_field_groups_is_base_group_system(self):
        """FAIL (expected): Field.groups='base.group_system' not yet set.

        The field must be system-only since it drives API URL construction
        (shopid injection risk if readable by non-admins).
        """
        shop_model = self.env['etsy.shop']
        field = shop_model._fields['etsy_api_shop_id']

        # Field.groups is a string or comma-separated list on the Field object
        # In Odoo 19, it's typically stored as 'group_id.xml_id' or similar
        self.assertEqual(
            field.groups,
            'base.group_system',
            "etsy_api_shop_id must have groups='base.group_system' (system-only ACL)"
        )

    def test_etsy_api_shop_id_field_is_char_type(self):
        """PASS: etsy_api_shop_id is a Char field (not Integer).

        Real Etsy shop_ids are int64 (e.g., 60752333 for JaHandmadeArt),
        which overflow PG int4 by 100x. Char avoids the overflow.
        """
        shop_model = self.env['etsy.shop']
        field = shop_model._fields['etsy_api_shop_id']

        self.assertEqual(
            field.type,
            'char',
            "etsy_api_shop_id must be Char field (not Integer) to avoid int64 overflow"
        )

    def test_etsy_api_shop_id_field_has_index_true(self):
        """PASS: etsy_api_shop_id field definition has index=True."""
        shop_model = self.env['etsy.shop']
        field = shop_model._fields['etsy_api_shop_id']

        self.assertTrue(
            field.index,
            "etsy_api_shop_id must have index=True for URL lookup performance"
        )

    def test_etsy_api_shop_id_field_is_not_required(self):
        """PASS: etsy_api_shop_id is NOT required at field level.

        NULL is legal for email-only shops. The constraint C-ESY-003
        enforces it only when active_source='api'.
        """
        shop_model = self.env['etsy.shop']
        field = shop_model._fields['etsy_api_shop_id']

        self.assertFalse(
            field.required,
            "etsy_api_shop_id must be optional at field level "
            "(constraint C-ESY-003 gates it to active_source='api')"
        )
