"""P0-17 Phase 2 — ORM unit tests for etsy.api.log model + retention cron.

Tests the model structure, field validation, ACL enforcement, and the
retention cron job that deletes logs older than the configured threshold.

Phase 2 tests exercise business logic through Odoo ORM methods.

Reference: Master Plan 006, P0-17 planner OQ1-OQ7.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEtsyApiLog_Model(TransactionCase):
    """ORM tests for etsy.api.log model structure and field validation."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop',
            'sync_mode': 'api_only',
        })

    def _create_api_log(self, **kwargs):
        """Factory method for test api.log records."""
        defaults = {
            'shop_id': self.shop.id,
            'endpoint': 'GET /v3/application/shops/{shop_id}/receipts',
            'source': 'sync',
        }
        defaults.update(kwargs)
        return self.env['etsy.api.log'].create(defaults)

    def test_create_minimal_row(self):
        """Create with required fields; verify defaults."""
        log = self._create_api_log()

        self.assertTrue(log.id, "Log record should be created")
        self.assertEqual(log.shop_id, self.shop)
        self.assertEqual(
            log.source, 'sync',
            "Source should be set to the provided value"
        )
        # request_started_at should be auto-set to current time
        self.assertIsNotNone(
            log.request_started_at,
            "request_started_at should be auto-set"
        )
        now = datetime.now()
        delta = (now - log.request_started_at).total_seconds()
        self.assertLess(
            abs(delta), 5,
            "request_started_at should be within ~5s of now"
        )

    def test_source_selection_includes_all_values(self):
        """Source field Selection includes all 8 required values."""
        field = self.env['etsy.api.log']._fields['source']
        selection = field.selection

        # Extract selection keys (first element of each tuple)
        selection_keys = [s[0] for s in selection]

        required_sources = [
            'audit', 'sync', 'tracking_push', 'webhook_register',
            'listing_push', 'listing_pull', 'buyer_message_sync',
            'health_check'
        ]

        for source in required_sources:
            self.assertIn(
                source, selection_keys,
                f"Source '{source}' missing from selection"
            )
        self.assertEqual(
            len(selection_keys), 8,
            f"Selection should have exactly 8 values, got {len(selection_keys)}"
        )

    def test_source_selection_rejects_invalid_value(self):
        """Invalid source value raises validation error."""
        with self.assertRaises(Exception):  # ValueError or ValidationError
            self._create_api_log(source='not_a_valid_source')

    def test_no_message_ids_field(self):
        """etsy.api.log does NOT have mail.thread fields."""
        fields = self.env['etsy.api.log']._fields
        self.assertNotIn(
            'message_ids', fields,
            "etsy.api.log should not inherit mail.thread"
        )


@tagged('post_install', '-at_install')
class TestEtsyApiLog_ACL(TransactionCase):
    """Access control list verification for etsy.api.log model."""

    @classmethod
    def setUpClass(cls):
        """Set up test users and groups."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.shop = cls.env['etsy.shop'].create({
            'name': 'ACL Test Shop',
            'sync_mode': 'api_only',
        })

        # Create test log as system
        cls.test_log = cls.env['etsy.api.log'].create({
            'shop_id': cls.shop.id,
            'endpoint': 'GET /v3/application/shops/{shop_id}/receipts',
            'source': 'sync',
        })

    def test_etsy_api_log_reader_group_exists(self):
        """The etsy_api_log_reader group must exist."""
        group = self.env.ref(
            'etsy_integration.group_etsy_api_log_reader',
            raise_if_not_found=False
        )
        self.assertIsNotNone(
            group,
            "Group etsy_integration.group_etsy_api_log_reader does not exist"
        )

    def test_reader_group_user_can_read(self):
        """A user in etsy_api_log_reader group can read logs."""
        reader_group = self.env.ref(
            'etsy_integration.group_etsy_api_log_reader'
        )
        reader_user = self.env['res.users'].create({
            'name': 'Reader User',
            'login': 'reader@example.com',
            'group_ids': [(6, 0, [reader_group.id])],
        })

        # Should be able to read as reader_user
        logs = self.env['etsy.api.log'].with_user(reader_user).search(
            [('id', '=', self.test_log.id)]
        )
        self.assertEqual(
            len(logs), 1,
            "Reader group user should be able to read logs"
        )

    def test_reader_group_user_cannot_create(self):
        """A user in etsy_api_log_reader group cannot create logs."""
        reader_group = self.env.ref(
            'etsy_integration.group_etsy_api_log_reader'
        )
        reader_user = self.env['res.users'].create({
            'name': 'Reader User 2',
            'login': 'reader2@example.com',
            'group_ids': [(6, 0, [reader_group.id])],
        })

        # Should NOT be able to create as reader_user
        with self.assertRaises(AccessError):
            self.env['etsy.api.log'].with_user(reader_user).create({
                'shop_id': self.shop.id,
                'endpoint': 'GET /v3/application/shops/{shop_id}/receipts',
                'source': 'sync',
            })

    def test_non_reader_user_cannot_read(self):
        """A user without etsy_api_log_reader group cannot read logs."""
        non_reader_user = self.env['res.users'].create({
            'name': 'Non-Reader User',
            'login': 'nonreader@example.com',
        })

        # Should NOT be able to read as non_reader_user
        with self.assertRaises(AccessError):
            self.env['etsy.api.log'].with_user(non_reader_user).search(
                [('id', '=', self.test_log.id)]
            )


@tagged('post_install', '-at_install')
class TestEtsyApiLog_RetentionCron(TransactionCase):
    """Retention cron job tests for etsy.api.log cleanup."""

    @classmethod
    def setUpClass(cls):
        """Set up test shop."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Retention Test Shop',
            'sync_mode': 'api_only',
        })

    def test_cron_deletes_rows_older_than_30_days(self):
        """Cron deletes logs older than 30 days; keeps newer ones."""
        # Create one row 31 days old (should be deleted)
        thirty_one_days_ago = datetime.now() - timedelta(days=31)
        self.env.cr.execute(
            """
            INSERT INTO etsy_api_log
            (shop_id, endpoint, source, request_started_at, create_date, create_uid)
            VALUES (%s, %s, %s, %s, NOW(), %s)
            """,
            (self.shop.id, 'GET /v3/...', 'sync',
             thirty_one_days_ago, self.env.user.id)
        )
        self.env.cr.commit()

        # Create one row 5 days old (should remain)
        five_days_ago = datetime.now() - timedelta(days=5)
        log_recent = self.env['etsy.api.log'].create({
            'shop_id': self.shop.id,
            'endpoint': 'GET /v3/receipts',
            'source': 'sync',
            'request_started_at': five_days_ago,
        })

        # Run cleanup cron
        self.env['etsy.api.log']._cron_cleanup_old_logs()

        # Verify old row is gone, recent row remains
        self.env.cr.execute(
            "SELECT COUNT(*) FROM etsy_api_log WHERE shop_id = %s",
            (self.shop.id,)
        )
        remaining_count = self.env.cr.fetchone()[0]
        self.assertEqual(
            remaining_count, 1,
            "Only the recent log should remain after cleanup"
        )

        # Verify recent log is still there
        logs = self.env['etsy.api.log'].search(
            [('shop_id', '=', self.shop.id)]
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].id, log_recent.id)

    def test_cron_respects_ir_config_parameter(self):
        """Cron respects ir.config_parameter retention days setting."""
        # Set retention to 7 days
        self.env['ir.config_parameter'].sudo().set_param(
            'etsy_integration.api_log_retention_days', '7'
        )

        # Create one row 10 days old (should be deleted with 7-day retention)
        ten_days_ago = datetime.now() - timedelta(days=10)
        self.env.cr.execute(
            """
            INSERT INTO etsy_api_log
            (shop_id, endpoint, source, request_started_at, create_date, create_uid)
            VALUES (%s, %s, %s, %s, NOW(), %s)
            """,
            (self.shop.id, 'GET /v3/...', 'sync',
             ten_days_ago, self.env.user.id)
        )
        self.env.cr.commit()

        # Create one row 3 days old (should remain)
        three_days_ago = datetime.now() - timedelta(days=3)
        log_recent = self.env['etsy.api.log'].create({
            'shop_id': self.shop.id,
            'endpoint': 'GET /v3/receipts',
            'source': 'sync',
            'request_started_at': three_days_ago,
        })

        # Run cleanup
        self.env['etsy.api.log']._cron_cleanup_old_logs()

        # Verify only the 3-day-old log remains
        logs = self.env['etsy.api.log'].search(
            [('shop_id', '=', self.shop.id)]
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].id, log_recent.id)

    def test_cron_uses_default_30_days_when_param_missing(self):
        """Cron uses default 30 days if ir.config_parameter is not set."""
        # Ensure param is not set (delete if exists)
        param = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'etsy_integration.api_log_retention_days')]
        )
        if param:
            param.sudo().unlink()

        # Create one row 35 days old (should be deleted with default 30)
        thirty_five_days_ago = datetime.now() - timedelta(days=35)
        self.env.cr.execute(
            """
            INSERT INTO etsy_api_log
            (shop_id, endpoint, source, request_started_at, create_date, create_uid)
            VALUES (%s, %s, %s, %s, NOW(), %s)
            """,
            (self.shop.id, 'GET /v3/...', 'sync',
             thirty_five_days_ago, self.env.user.id)
        )
        self.env.cr.commit()

        # Create one row 20 days old (should remain)
        twenty_days_ago = datetime.now() - timedelta(days=20)
        log_recent = self.env['etsy.api.log'].create({
            'shop_id': self.shop.id,
            'endpoint': 'GET /v3/receipts',
            'source': 'sync',
            'request_started_at': twenty_days_ago,
        })

        # Run cleanup
        self.env['etsy.api.log']._cron_cleanup_old_logs()

        # Verify only the 20-day-old log remains
        logs = self.env['etsy.api.log'].search(
            [('shop_id', '=', self.shop.id)]
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].id, log_recent.id)
