"""
Phase 1 Database Verification Tests for P-BUG-ESTY-188: createListing 400 fix.

Tests verify data structure (columns, data types) at the database level.
This phase ensures all fields and migrations exist before Phase 2 ORM tests run.

Scope:
1. default_readiness_state_id field: Char column (NOT Integer — Etsy IDs overflow int32)
2. Migration 19.0.2.33.0 post-migrate.py file exists

RED: These tests FAIL because:
- Test 3: migration file does not yet exist (Phase 3 GREEN writes it)
"""

import logging
import os

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP_BUG_ESTY_188_Phase1_DB(TransactionCase):
    """Phase 1: Verify default_readiness_state_id database structure."""

    def test_default_readiness_state_id_column_exists(self):
        """PASS: default_readiness_state_id column exists on etsy_shop table.

        This field was added in 19.0.2.15.0. Verify it exists in the schema.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'default_readiness_state_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "default_readiness_state_id column must exist on etsy_shop table"
        )

    def test_default_readiness_state_id_is_char_not_int(self):
        """PASS: default_readiness_state_id is Char (varchar), not Integer.

        Etsy IDs are int64; XML-RPC int32 overflow trap (memory entry 144).
        Must use Char and store as string, cast to int only in payload.
        Example: JaHandmadeArt readiness ID = 1406133708616 (exceeds int32 max).
        """
        self.env.cr.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'default_readiness_state_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(result, "Column must exist")
        data_type = result[0]
        self.assertIn(
            data_type,
            ('character varying', 'text'),
            f"default_readiness_state_id must be text-based, got {data_type}"
        )

    def test_migration_19_0_2_33_0_post_migrate_file_exists(self):
        """RED: migration file does not yet exist.

        This test confirms the post-migrate function is present.
        Will FAIL with FileNotFoundError until Phase 3 GREEN writes the migration.
        """
        migration_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'migrations',
            '19.0.2.33.0',
            'post-migrate.py'
        )
        self.assertTrue(
            os.path.exists(migration_path),
            f"Migration file must exist at {migration_path}"
        )
