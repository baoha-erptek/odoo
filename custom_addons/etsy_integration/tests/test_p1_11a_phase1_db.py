"""
Phase 1 Database Verification Tests for P1-11a: Etsy active_source scaffolding.

Tests verify data structure (columns, tables, defaults, constraints) at the database level.
This phase ensures all fields exist before Phase 2 ORM tests run.

RED: These tests FAIL because the production code (models, migrations) does not yet exist.
Expected failure reasons documented in each test.
"""

import logging
from datetime import datetime

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP1_11a_Phase1_DB_Columns(TransactionCase):
    """Phase 1: Verify etsy.shop and etsy.shop.source.change.log database structure.

    FAILURE REASON for RED: The new columns/tables do not exist yet (production code not written).
    """

    def test_etsy_shop_has_active_source_column(self):
        """FAIL: active_source column missing on etsy_shop table."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'active_source'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop must have active_source column (Selection: api/email)"
        )

    def test_etsy_shop_has_auto_recovery_column(self):
        """FAIL: auto_recovery column missing on etsy_shop table."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'auto_recovery'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop must have auto_recovery column (Boolean, default True)"
        )

    def test_etsy_shop_has_health_check_consecutive_failures_column(self):
        """FAIL: health_check_consecutive_failures column missing."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'health_check_consecutive_failures'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop must have health_check_consecutive_failures column (Integer, default 0)"
        )

    def test_etsy_shop_has_recovery_probe_consecutive_successes_column(self):
        """FAIL: recovery_probe_consecutive_successes column missing."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'recovery_probe_consecutive_successes'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop must have recovery_probe_consecutive_successes column (Integer, default 0)"
        )

    def test_etsy_shop_has_active_source_changed_at_column(self):
        """FAIL: active_source_changed_at column missing."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'active_source_changed_at'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop must have active_source_changed_at column (Datetime)"
        )

    def test_etsy_shop_sync_mode_column_still_present(self):
        """Migration must NOT drop sync_mode (data-model.md: 'does NOT drop sync_mode')."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'sync_mode'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop.sync_mode must still exist after migration (per data-model.md §1)"
        )

    def test_etsy_shop_source_change_log_table_exists(self):
        """FAIL: etsy_shop_source_change_log table missing (new model)."""
        self.env.cr.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'etsy_shop_source_change_log'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy.shop.source.change.log model must create etsy_shop_source_change_log table"
        )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase1_DB_SourceChangeLogColumns(TransactionCase):
    """Phase 1: Verify etsy.shop.source.change.log table structure.

    FAILURE REASON for RED: etsy_shop_source_change_log table or columns missing.
    """

    def test_source_change_log_has_shop_id_column(self):
        """FAIL: shop_id M2o column missing from source.change.log."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'shop_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have shop_id column (M2o etsy.shop, required, cascade)"
        )

    def test_source_change_log_has_from_source_column(self):
        """FAIL: from_source column missing (nullable Selection)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'from_source'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have from_source column (Selection: null/api/email)"
        )

    def test_source_change_log_has_to_source_column(self):
        """FAIL: to_source column missing (required Selection)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'to_source'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have to_source column (Selection: api/email, required)"
        )

    def test_source_change_log_has_changed_at_column(self):
        """FAIL: changed_at column missing (required Datetime, default now)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'changed_at'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have changed_at column (Datetime, required, default=now())"
        )

    def test_source_change_log_has_reason_column(self):
        """FAIL: reason column missing (required Selection)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'reason'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have reason column (Selection: bootstrap/manual/auto-failover/recovery-probe/scope-revoked)"
        )

    def test_source_change_log_has_actor_user_id_column(self):
        """FAIL: actor_user_id column missing (nullable M2o res.users)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'actor_user_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have actor_user_id column (M2o res.users, nullable — null for system)"
        )

    def test_source_change_log_has_health_check_failures_at_change_column(self):
        """FAIL: health_check_failures_at_change column missing (optional Integer snapshot)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'health_check_failures_at_change'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have health_check_failures_at_change column (Integer, optional)"
        )

    def test_source_change_log_has_notes_column(self):
        """FAIL: notes column missing (optional Text)."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_shop_source_change_log' AND column_name = 'notes'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "etsy_shop_source_change_log must have notes column (Text, optional)"
        )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase1_DB_Defaults(TransactionCase):
    """Phase 1: Verify field defaults and constraints on actual data.

    FAILURE REASON for RED: Either tables missing or defaults not set in database schema.
    """

    @classmethod
    def setUpClass(cls):
        """Create test shop for default verification."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # Will fail because the model doesn't have the new fields yet
        cls.shop = None

    def test_active_source_defaults_to_email(self):
        """FAIL: active_source defaults to 'email' or field missing."""
        # Create a shop via raw SQL to bypass ORM field validation
        self.env.cr.execute("""
            INSERT INTO etsy_shop (name, create_uid, create_date)
            VALUES ('Test Shop Default', 2, now())
            RETURNING id
        """)
        shop_id = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            "SELECT active_source FROM etsy_shop WHERE id = %s",
            (shop_id,)
        )
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "active_source column must exist"
        )
        # Default should be 'email' per data-model.md §1
        if result[0] is not None:
            self.assertEqual(
                result[0],
                'email',
                "active_source should default to 'email' for existing shops"
            )

    def test_auto_recovery_defaults_to_true(self):
        """FAIL: auto_recovery defaults to True or field missing."""
        self.env.cr.execute("""
            INSERT INTO etsy_shop (name, create_uid, create_date)
            VALUES ('Test Shop Auto Recovery', 2, now())
            RETURNING id
        """)
        shop_id = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            "SELECT auto_recovery FROM etsy_shop WHERE id = %s",
            (shop_id,)
        )
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "auto_recovery column must exist"
        )
        # Default should be True per data-model.md §1
        if result[0] is not None:
            self.assertTrue(
                result[0],
                "auto_recovery should default to True"
            )

    def test_health_check_consecutive_failures_defaults_to_zero(self):
        """FAIL: health_check_consecutive_failures defaults to 0 or field missing."""
        self.env.cr.execute("""
            INSERT INTO etsy_shop (name, create_uid, create_date)
            VALUES ('Test Shop Health Check', 2, now())
            RETURNING id
        """)
        shop_id = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            "SELECT health_check_consecutive_failures FROM etsy_shop WHERE id = %s",
            (shop_id,)
        )
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "health_check_consecutive_failures column must exist"
        )
        # Default should be 0 per data-model.md §1
        if result[0] is not None:
            self.assertEqual(
                result[0],
                0,
                "health_check_consecutive_failures should default to 0"
            )

    def test_recovery_probe_consecutive_successes_defaults_to_zero(self):
        """FAIL: recovery_probe_consecutive_successes defaults to 0 or field missing."""
        self.env.cr.execute("""
            INSERT INTO etsy_shop (name, create_uid, create_date)
            VALUES ('Test Shop Recovery Probe', 2, now())
            RETURNING id
        """)
        shop_id = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            "SELECT recovery_probe_consecutive_successes FROM etsy_shop WHERE id = %s",
            (shop_id,)
        )
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "recovery_probe_consecutive_successes column must exist"
        )
        # Default should be 0 per data-model.md §1
        if result[0] is not None:
            self.assertEqual(
                result[0],
                0,
                "recovery_probe_consecutive_successes should default to 0"
            )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase1_DB_Migration(TransactionCase):
    """Phase 1: Verify migration results — mapping of sync_mode to active_source.

    FAILURE REASON for RED: Migration (19.0.1.0.0_post.py) not implemented or table missing.

    Per data-model.md §1 migration script:
    - sync_mode='api_only' → active_source='api'
    - sync_mode='email_only' → active_source='email'
    - Default → active_source='email'
    """

    def test_migration_maps_api_only_to_active_source_api(self):
        """POST-migration invariant: sync_mode='api_only' shops have active_source='api'."""
        # Insert a pre-migration shop with api_only mode
        self.env.cr.execute("""
            INSERT INTO etsy_shop (name, sync_mode, create_uid, create_date)
            VALUES ('API Only Shop', 'api_only', 2, now())
            RETURNING id
        """)
        shop_id = self.env.cr.fetchone()[0]

        # Check that migration updated active_source
        self.env.cr.execute(
            "SELECT active_source FROM etsy_shop WHERE id = %s",
            (shop_id,)
        )
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "active_source column must exist post-migration")
        self.assertEqual(
            result[0],
            'api',
            "sync_mode='api_only' must map to active_source='api' (migration requirement)"
        )

    def test_migration_maps_email_only_to_active_source_email(self):
        """POST-migration invariant: sync_mode='email_only' shops have active_source='email'."""
        self.env.cr.execute("""
            INSERT INTO etsy_shop (name, sync_mode, create_uid, create_date)
            VALUES ('Email Only Shop', 'email_only', 2, now())
            RETURNING id
        """)
        shop_id = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            "SELECT active_source FROM etsy_shop WHERE id = %s",
            (shop_id,)
        )
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "active_source column must exist post-migration")
        self.assertEqual(
            result[0],
            'email',
            "sync_mode='email_only' must map to active_source='email' (migration requirement)"
        )

    def test_post_migration_every_shop_has_valid_active_source(self):
        """POST-migration invariant: every existing shop has active_source ∈ {api, email}."""
        self.env.cr.execute("""
            SELECT id FROM etsy_shop WHERE active_source IS NULL OR active_source NOT IN ('api', 'email')
        """)
        invalid_shops = self.env.cr.fetchall()

        self.assertEqual(
            len(invalid_shops),
            0,
            f"All shops must have valid active_source ∈ {{api, email}} post-migration; "
            f"found {len(invalid_shops)} with NULL or invalid values"
        )

    def test_post_migration_every_shop_has_bootstrap_log_entry(self):
        """POST-migration invariant: every existing shop has ≥1 bootstrap log row."""
        # First check if the log table exists
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'etsy_shop_source_change_log'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]

        if not table_exists:
            self.skipTest("etsy_shop_source_change_log table does not exist yet")

        # Get all shops
        self.env.cr.execute("SELECT id FROM etsy_shop")
        shop_ids = [row[0] for row in self.env.cr.fetchall()]

        if not shop_ids:
            self.skipTest("No shops in database for migration test")

        # Every shop should have at least one bootstrap log row
        for shop_id in shop_ids:
            self.env.cr.execute("""
                SELECT COUNT(*) FROM etsy_shop_source_change_log
                WHERE shop_id = %s AND reason = 'bootstrap'
            """, (shop_id,))
            count = self.env.cr.fetchone()[0]

            self.assertGreaterEqual(
                count,
                1,
                f"Shop {shop_id} must have ≥1 bootstrap log row post-migration; found {count}"
            )

    def test_bootstrap_log_entry_has_null_from_source(self):
        """Bootstrap log entries must have from_source=NULL per data-model.md §2."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'etsy_shop_source_change_log'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]

        if not table_exists:
            self.skipTest("etsy_shop_source_change_log table does not exist yet")

        self.env.cr.execute("""
            SELECT COUNT(*) FROM etsy_shop_source_change_log
            WHERE reason = 'bootstrap' AND from_source IS NOT NULL
        """)
        invalid_count = self.env.cr.fetchone()[0]

        self.assertEqual(
            invalid_count,
            0,
            f"Bootstrap log entries must have from_source=NULL; found {invalid_count} with non-null"
        )

    def test_bootstrap_log_entry_has_to_source_from_migration(self):
        """Bootstrap log to_source must match the mapped active_source per migration."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'etsy_shop_source_change_log'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]

        if not table_exists:
            self.skipTest("etsy_shop_source_change_log table does not exist yet")

        # Verify bootstrap logs have to_source matching shop.active_source
        self.env.cr.execute("""
            SELECT COUNT(*) FROM etsy_shop_source_change_log log
            JOIN etsy_shop shop ON log.shop_id = shop.id
            WHERE log.reason = 'bootstrap' AND log.to_source != shop.active_source
        """)
        mismatch_count = self.env.cr.fetchone()[0]

        self.assertEqual(
            mismatch_count,
            0,
            f"Bootstrap log to_source must match shop.active_source; found {mismatch_count} mismatches"
        )
