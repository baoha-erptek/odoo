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
        """Source field Selection includes all 11 required values.

        Originally 8; extended to 10 in P3-LEAD-DEDUPE (T008) with
        'conversation_sync' and 'message_send'; extended to 11 in
        P1-10 (D-P1-10-05) with 'scope_validation' (OAuth scope
        assertion audit rows).
        """
        field = self.env['etsy.api.log']._fields['source']
        selection = field.selection

        # Extract selection keys (first element of each tuple)
        selection_keys = [s[0] for s in selection]

        required_sources = [
            'audit', 'sync', 'tracking_push', 'webhook_register',
            'listing_push', 'listing_pull', 'buyer_message_sync',
            'health_check', 'conversation_sync', 'message_send',
            'scope_validation',
            # P-PUB-CLIENT (2026-05-23) outbound publish
            'listing_create', 'listing_image_upload', 'listing_image_delete',
            'listing_inventory_push', 'listing_publish',
            # Spec 010 catalog import
            'catalog_import_run', 'catalog_image_download',
        ]

        for source in required_sources:
            self.assertIn(
                source, selection_keys,
                f"Source '{source}' missing from selection"
            )
        self.assertEqual(
            len(selection_keys), 18,
            f"Selection should have exactly 18 values, got {len(selection_keys)}"
        )

    def test_source_selection_rejects_invalid_value(self):
        """Invalid source value raises ValueError (Odoo Selection write)."""
        with self.assertRaises(ValueError):
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

    def _make_old_log(self, days_old):
        """Create a log row, then backdate it via UPDATE so the cron's
        DELETE WHERE request_started_at < threshold sees it as old.
        TransactionCase forbids cr.commit(), so SQL UPDATE inside the
        savepoint is the right way to set arbitrary timestamps."""
        log = self.env['etsy.api.log'].create({
            'shop_id': self.shop.id,
            'endpoint': 'GET /v3/receipts',
            'source': 'sync',
        })
        target = datetime.now() - timedelta(days=days_old)
        self.env.cr.execute(
            "UPDATE etsy_api_log SET request_started_at = %s WHERE id = %s",
            (target, log.id),
        )
        log.invalidate_recordset(['request_started_at'])
        return log

    def test_cron_deletes_rows_older_than_30_days(self):
        """Cron deletes logs older than 30 days; keeps newer ones."""
        old_log = self._make_old_log(days_old=31)
        recent_log = self._make_old_log(days_old=5)

        self.env['etsy.api.log']._cron_cleanup_old_logs()

        remaining = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
        ])
        self.assertNotIn(old_log.id, remaining.ids)
        self.assertIn(recent_log.id, remaining.ids)

    def test_cron_respects_ir_config_parameter(self):
        """Cron respects ir.config_parameter retention days setting."""
        self.env['ir.config_parameter'].sudo().set_param(
            'etsy_integration.api_log_retention_days', '7',
        )
        old_log = self._make_old_log(days_old=10)
        recent_log = self._make_old_log(days_old=3)

        self.env['etsy.api.log']._cron_cleanup_old_logs()

        remaining = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
        ])
        self.assertNotIn(old_log.id, remaining.ids)
        self.assertIn(recent_log.id, remaining.ids)

    def test_cron_uses_default_30_days_when_param_missing(self):
        """Cron uses default 30 days if ir.config_parameter is not set."""
        param = self.env['ir.config_parameter'].sudo().search([
            ('key', '=', 'etsy_integration.api_log_retention_days'),
        ])
        if param:
            param.sudo().unlink()

        old_log = self._make_old_log(days_old=35)
        recent_log = self._make_old_log(days_old=20)

        self.env['etsy.api.log']._cron_cleanup_old_logs()

        remaining = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
        ])
        self.assertNotIn(old_log.id, remaining.ids)
        self.assertIn(recent_log.id, remaining.ids)
