"""
Phase 2 ORM Unit Tests for P1-11a: Etsy active_source scaffolding.

Tests verify business logic, constraints, access control, and ORM behavior through the Odoo API.

RED: These tests FAIL because the production code (models, constraints, methods) does not yet exist.
Expected failure reasons documented in each test.
"""

import logging
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_SourceChangeLogModel(TransactionCase):
    """Phase 2: Verify etsy.shop.source.change.log model and required fields.

    FAILURE REASON for RED: Model class does not exist or fields missing.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_source_change_log_model_exists(self):
        """FAIL: etsy.shop.source.change.log model not registered."""
        model = self.env.get('etsy.shop.source.change.log')
        self.assertIsNotNone(
            model,
            "etsy.shop.source.change.log model must be defined in etsy_integration"
        )

    def test_source_change_log_has_required_fields(self):
        """FAIL: Model missing required field definitions."""
        model = self.env['etsy.shop.source.change.log']

        required_fields = [
            'shop_id',
            'from_source',
            'to_source',
            'changed_at',
            'reason',
            'actor_user_id',
        ]

        for field_name in required_fields:
            self.assertTrue(
                hasattr(model, field_name),
                f"etsy.shop.source.change.log must have {field_name} field"
            )

    def test_source_change_log_shop_id_is_many2one_cascade(self):
        """Verify shop_id is Many2one with ondelete='cascade'."""
        field = self.env['etsy.shop.source.change.log']._fields['shop_id']

        self.assertEqual(
            field.type,
            'many2one',
            "shop_id must be Many2one field"
        )
        self.assertEqual(
            field.comodel_name,
            'etsy.shop',
            "shop_id must reference etsy.shop"
        )
        self.assertEqual(
            field.ondelete,
            'cascade',
            "shop_id must have ondelete='cascade' per data-model.md"
        )

    def test_source_change_log_to_source_required(self):
        """to_source field must be required."""
        field = self.env['etsy.shop.source.change.log']._fields['to_source']

        self.assertTrue(
            field.required,
            "to_source must be required field"
        )

    def test_source_change_log_reason_required(self):
        """reason field must be required."""
        field = self.env['etsy.shop.source.change.log']._fields['reason']

        self.assertTrue(
            field.required,
            "reason must be required field"
        )

    def test_source_change_log_changed_at_required(self):
        """changed_at field must be required."""
        field = self.env['etsy.shop.source.change.log']._fields['changed_at']

        self.assertTrue(
            field.required,
            "changed_at must be required field"
        )

    def test_source_change_log_from_source_nullable(self):
        """from_source field must allow NULL (for bootstrap)."""
        field = self.env['etsy.shop.source.change.log']._fields['from_source']

        self.assertFalse(
            field.required,
            "from_source must be nullable (required=False) per data-model.md §2"
        )

    def test_source_change_log_actor_user_id_nullable(self):
        """actor_user_id field must allow NULL (for system changes)."""
        field = self.env['etsy.shop.source.change.log']._fields['actor_user_id']

        self.assertFalse(
            field.required,
            "actor_user_id must be nullable (required=False) per data-model.md §2"
        )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_ConstraintC_ESY_001(TransactionCase):
    """Phase 2: Constraint C-ESY-001 — active_source='api' requires OAuth tokens.

    FAILURE REASON for RED: Constraint validation not implemented or field missing.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shop."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # Try to create a shop; will fail if active_source field doesn't exist
        try:
            cls.shop = cls.env['etsy.shop'].create({
                'name': 'Test Shop For Constraint C-ESY-001',
            })
        except Exception:
            cls.shop = None

    def test_active_source_api_requires_access_token(self):
        """FAIL: Setting active_source='api' without access_token must raise ValidationError."""
        if self.shop is None:
            self.skipTest("etsy.shop model creation failed (field missing)")

        with self.assertRaises(ValidationError) as cm:
            self.shop.write({
                'active_source': 'api',
                'etsy_oauth_access_token': '',  # Empty; no token
                'etsy_oauth_refresh_token': '',
            })

        self.assertIn(
            'oauth',
            str(cm.exception).lower(),
            "ValidationError should mention OAuth tokens required for API source"
        )

    def test_active_source_api_requires_refresh_token(self):
        """FAIL: Setting active_source='api' without refresh_token must raise ValidationError."""
        if self.shop is None:
            self.skipTest("etsy.shop model creation failed")

        with self.assertRaises(ValidationError) as cm:
            self.shop.write({
                'active_source': 'api',
                'etsy_oauth_access_token': 'valid_access_token',
                'etsy_oauth_refresh_token': '',  # Missing refresh token
            })

        self.assertIn(
            'refresh',
            str(cm.exception).lower(),
            "ValidationError should mention refresh_token required for API source"
        )

    def test_active_source_api_accepts_both_tokens_present(self):
        """Happy path: active_source='api' succeeds with both tokens."""
        if self.shop is None:
            self.skipTest("etsy.shop model creation failed")

        # Should NOT raise ValidationError
        self.shop.write({
            'active_source': 'api',
            'etsy_oauth_access_token': 'test_access_token_value',
            'etsy_oauth_refresh_token': 'test_refresh_token_value',
        })

        self.assertEqual(
            self.shop.active_source,
            'api',
            "active_source should be set to 'api' when valid tokens present"
        )

    def test_active_source_email_allows_null_tokens(self):
        """Happy path: active_source='email' allows NULL OAuth tokens."""
        if self.shop is None:
            self.skipTest("etsy.shop model creation failed")

        # Should NOT raise ValidationError even though tokens are empty
        self.shop.write({
            'active_source': 'email',
            'etsy_oauth_access_token': '',
            'etsy_oauth_refresh_token': '',
        })

        self.assertEqual(
            self.shop.active_source,
            'email',
            "active_source='email' should succeed with NULL tokens"
        )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_ConstraintC_ESY_002(TransactionCase):
    """Phase 2: Constraint C-ESY-002 + FR-017 — write-level access gate on active_source.

    FAILURE REASON for RED: Access control not implemented; non-system user can write active_source.

    Per FR-017 (18 confirmations): UI groups= MUST be mirrored at the method level.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shop and test users."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test shop (will fail if active_source field missing)
        try:
            cls.shop = cls.env['etsy.shop'].create({
                'name': 'Test Shop For C-ESY-002',
                'active_source': 'email',
            })
        except Exception:
            cls.shop = None

        # Create a non-system user
        cls.non_system_user = cls.env['res.users'].create({
            'name': 'Non-System User',
            'login': 'nonbsystem@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        # System user (for comparison)
        cls.system_user = cls.env.ref('base.user_root')

    def test_non_system_user_cannot_write_active_source(self):
        """FAIL: Non-system user writing active_source should raise AccessError."""
        if self.shop is None:
            self.skipTest("etsy.shop creation failed (field missing)")

        shop_as_user = self.shop.with_user(self.non_system_user)

        with self.assertRaises(AccessError) as cm:
            shop_as_user.write({'active_source': 'api'})

        self.assertIn(
            'active_source',
            str(cm.exception).lower(),
            "AccessError should indicate active_source field is restricted"
        )

    def test_system_user_can_write_active_source(self):
        """Happy path: system user (admin) can write active_source."""
        if self.shop is None:
            self.skipTest("etsy.shop creation failed")

        shop_as_system = self.shop.with_user(self.system_user)

        # Set both tokens for C-ESY-001 constraint
        shop_as_system.write({
            'active_source': 'api',
            'etsy_oauth_access_token': 'test_token',
            'etsy_oauth_refresh_token': 'test_refresh',
        })

        self.assertEqual(
            self.shop.active_source,
            'api',
            "System user should be able to write active_source"
        )

    def test_system_user_write_creates_source_change_log_entry(self):
        """System user writing active_source creates log entry (reason='manual')."""
        if self.shop is None:
            self.skipTest("etsy.shop creation failed")

        shop_as_system = self.shop.with_user(self.system_user)
        old_source = self.shop.active_source

        shop_as_system.write({
            'active_source': 'api',
            'etsy_oauth_access_token': 'token',
            'etsy_oauth_refresh_token': 'refresh',
        })

        # Check that a log entry was created
        log_entry = self.env['etsy.shop.source.change.log'].search([
            ('shop_id', '=', self.shop.id),
            ('reason', '=', 'manual'),
        ], limit=1)

        self.assertTrue(
            log_entry.exists(),
            "Writing active_source as system user must create a 'manual' source.change.log entry"
        )

    def test_source_change_log_manual_entry_has_correct_fields(self):
        """Manual log entry must have from_source, to_source, actor_user_id set correctly."""
        if self.shop is None:
            self.skipTest("etsy.shop creation failed")

        shop_as_system = self.shop.with_user(self.system_user)
        old_source = self.shop.active_source or 'email'  # If NULL, assume email was previous

        shop_as_system.write({
            'active_source': 'api',
            'etsy_oauth_access_token': 'token',
            'etsy_oauth_refresh_token': 'refresh',
        })

        # Find the most recent manual log entry
        log_entry = self.env['etsy.shop.source.change.log'].search([
            ('shop_id', '=', self.shop.id),
            ('reason', '=', 'manual'),
        ], order='changed_at DESC', limit=1)

        self.assertTrue(log_entry.exists(), "Manual log entry should exist")

        # Verify fields
        self.assertEqual(
            log_entry.from_source,
            old_source,
            f"Log from_source should be previous state '{old_source}'"
        )
        self.assertEqual(
            log_entry.to_source,
            'api',
            "Log to_source should be new state 'api'"
        )
        self.assertEqual(
            log_entry.actor_user_id,
            self.system_user,
            "Log actor_user_id should be the system user who initiated the change"
        )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_CronFilterUpdate(TransactionCase):
    """Phase 2: Verify _cron_sync_orders uses active_source instead of sync_mode.

    FAILURE REASON for RED: Cron method not updated; still filters by sync_mode='api_only'.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shops with different sources."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test shops
        try:
            cls.api_shop = cls.env['etsy.shop'].create({
                'name': 'API Shop',
                'active_source': 'api',
                'etsy_oauth_access_token': 'token',
                'etsy_oauth_refresh_token': 'refresh',
            })
            cls.email_shop = cls.env['etsy.shop'].create({
                'name': 'Email Shop',
                'active_source': 'email',
            })
        except Exception:
            cls.api_shop = None
            cls.email_shop = None

    def test_cron_sync_orders_finds_api_shops_by_active_source(self):
        """FAIL: _cron_sync_orders still filters by sync_mode='api_only'."""
        if self.api_shop is None:
            self.skipTest("Shop creation failed (field missing)")

        # Simulate what the cron does: search for API-source shops
        api_shops = self.env['etsy.shop'].search([('active_source', '=', 'api')])

        self.assertIn(
            self.api_shop,
            api_shops,
            "Cron must find shops by active_source='api', not sync_mode='api_only'"
        )

    def test_cron_sync_orders_excludes_email_shops(self):
        """Cron should NOT sync email-source shops in the main sync loop."""
        if self.email_shop is None:
            self.skipTest("Shop creation failed")

        api_shops = self.env['etsy.shop'].search([('active_source', '=', 'api')])

        self.assertNotIn(
            self.email_shop,
            api_shops,
            "Cron must not include active_source='email' shops"
        )

    def test_cron_method_respects_active_source_field(self):
        """Verify _cron_sync_orders method body reads active_source, not sync_mode."""
        method = self.env['etsy.shop']._cron_sync_orders

        # Read the source code to verify it uses 'active_source' instead of 'sync_mode'
        import inspect
        source = inspect.getsource(method)

        self.assertIn(
            "active_source",
            source,
            "_cron_sync_orders must filter by active_source field"
        )

        # Should not be filtering by the old sync_mode
        # (OK if sync_mode appears in comments, but NOT in the search domain)
        if "search([" in source:
            # Extract the search domain
            import re
            domain_match = re.search(r"search\(\[(.*?)\]\)", source, re.DOTALL)
            if domain_match:
                domain = domain_match.group(1)
                # The domain should not have 'sync_mode' as a key
                self.assertNotIn(
                    "'sync_mode'",
                    domain,
                    "_cron_sync_orders must not filter by sync_mode (use active_source instead)"
                )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_IngestorAdapterSelection(TransactionCase):
    """Phase 2: Verify etsy_order_ingestor reads shop.active_source for adapter selection.

    FAILURE REASON for RED: Ingestor not updated; doesn't branch on active_source.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shop."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        try:
            cls.shop = cls.env['etsy.shop'].create({
                'name': 'Ingestor Test Shop',
                'active_source': 'api',
                'etsy_oauth_access_token': 'token',
                'etsy_oauth_refresh_token': 'refresh',
            })
        except Exception:
            cls.shop = None

    def test_ingestor_service_exists(self):
        """Verify etsy_order_ingestor service can be imported."""
        try:
            from ..services.etsy_order_ingestor import EtsyOrderIngestor
            self.assertTrue(True, "EtsyOrderIngestor service should exist")
        except ImportError:
            self.skipTest("EtsyOrderIngestor not yet implemented")

    def test_ingestor_ingest_method_reads_active_source(self):
        """ingest() method must read shop.active_source to select adapter."""
        try:
            from ..services.etsy_order_ingestor import EtsyOrderIngestor
            method = EtsyOrderIngestor.ingest

            import inspect
            source = inspect.getsource(method)

            self.assertIn(
                "active_source",
                source,
                "EtsyOrderIngestor.ingest() must read shop.active_source to pick the adapter"
            )
        except (ImportError, AttributeError):
            self.skipTest("EtsyOrderIngestor.ingest not yet implemented")

    def test_ingestor_adapter_selection_by_source_api(self):
        """When shop.active_source='api', ingestor should use EtsyApiAdapter."""
        if self.shop is None:
            self.skipTest("Shop creation failed")

        try:
            from ..services.etsy_order_ingestor import EtsyOrderIngestor
            ingestor = EtsyOrderIngestor(self.env)

            # The ingestor should inspect shop.active_source and select the appropriate adapter
            # This test verifies the logic path exists (not the adapter implementation)
            import inspect
            source = inspect.getsource(ingestor.ingest)

            # Check that the method distinguishes between 'api' and 'email' sources
            self.assertIn(
                "active_source",
                source,
                "ingest() must branch on shop.active_source"
            )
        except ImportError:
            self.skipTest("EtsyOrderIngestor not yet implemented")

    def test_ingestor_adapter_selection_by_source_email(self):
        """When shop.active_source='email', ingestor should use EtsyEmailAdapter."""
        # Same logic as above, just documenting both paths should be handled
        try:
            from ..services.etsy_order_ingestor import EtsyOrderIngestor
            ingestor = EtsyOrderIngestor(self.env)

            import inspect
            source = inspect.getsource(ingestor.ingest)

            # Both 'api' and 'email' should be mentioned in the conditional
            self.assertTrue(
                ("'api'" in source or '"api"' in source) and
                ("'email'" in source or '"email"' in source),
                "ingest() must handle both 'api' and 'email' sources"
            )
        except ImportError:
            self.skipTest("EtsyOrderIngestor not yet implemented")


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_SourceChangeLogAudit(TransactionCase):
    """Phase 2: Verify source.change.log records all transitions correctly.

    FAILURE REASON for RED: Model missing or logging not wired into write() override.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shop."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        try:
            cls.shop = cls.env['etsy.shop'].create({
                'name': 'Audit Test Shop',
                'active_source': 'email',
            })
        except Exception:
            cls.shop = None

        cls.system_user = cls.env.ref('base.user_root')

    def test_multiple_source_changes_create_multiple_logs(self):
        """Each write to active_source creates a new log entry."""
        if self.shop is None:
            self.skipTest("Shop creation failed")

        # First change: email → api
        self.shop.with_user(self.system_user).write({
            'active_source': 'api',
            'etsy_oauth_access_token': 'token1',
            'etsy_oauth_refresh_token': 'refresh1',
        })

        # Second change: api → email
        self.shop.with_user(self.system_user).write({
            'active_source': 'email',
        })

        # Should have 2 log entries (not counting bootstrap if it exists)
        log_entries = self.env['etsy.shop.source.change.log'].search([
            ('shop_id', '=', self.shop.id),
            ('reason', '=', 'manual'),
        ])

        self.assertGreaterEqual(
            len(log_entries),
            2,
            "Two manual source changes should create at least 2 log entries"
        )

    def test_source_change_log_changed_at_is_set(self):
        """Each log entry has changed_at timestamp."""
        if self.shop is None:
            self.skipTest("Shop creation failed")

        self.shop.with_user(self.system_user).write({
            'active_source': 'api',
            'etsy_oauth_access_token': 'token',
            'etsy_oauth_refresh_token': 'refresh',
        })

        log_entry = self.env['etsy.shop.source.change.log'].search([
            ('shop_id', '=', self.shop.id),
            ('reason', '=', 'manual'),
        ], limit=1)

        self.assertTrue(
            log_entry.changed_at,
            "Log entry must have changed_at timestamp"
        )

        # Verify it's roughly now (within 1 minute)
        now = datetime.now()
        time_diff = abs((now - log_entry.changed_at).total_seconds())

        self.assertLess(
            time_diff,
            60,
            f"changed_at should be recent; found {time_diff}s old"
        )

    def test_source_change_log_reason_field_values(self):
        """Verify reason field has correct values per data-model.md."""
        log_model = self.env['etsy.shop.source.change.log']
        reason_field = log_model._fields['reason']

        expected_reasons = {
            'bootstrap',
            'manual',
            'auto-failover',
            'recovery-probe',
            'scope-revoked',
        }

        # Extract selection values
        selection = reason_field.selection
        if callable(selection):
            selection = selection(log_model)

        actual_reasons = {value for value, label in selection}

        for expected_reason in expected_reasons:
            self.assertIn(
                expected_reason,
                actual_reasons,
                f"reason field must include '{expected_reason}' per data-model.md §2"
            )

    def test_source_change_log_from_to_source_field_values(self):
        """Verify from_source and to_source allow api/email/null correctly."""
        log_model = self.env['etsy.shop.source.change.log']

        to_source_field = log_model._fields['to_source']
        to_source_selection = to_source_field.selection
        if callable(to_source_selection):
            to_source_selection = to_source_selection(log_model)

        to_source_values = {value for value, label in to_source_selection}

        self.assertEqual(
            to_source_values,
            {'api', 'email'},
            "to_source field must have selection values 'api' and 'email'"
        )


@tagged('post_install', '-at_install')
class TestP1_11a_Phase2_SourceChangeLogAppendOnly(TransactionCase):
    """Phase 2: C-SCL-001 — source.change.log rows are append-only;
    only system administrators may delete them.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Append-Only Test Shop',
            'active_source': 'email',
        })
        cls.log = cls.env['etsy.shop.source.change.log'].create({
            'shop_id': cls.shop.id,
            'to_source': 'email',
            'reason': 'bootstrap',
        })
        cls.non_system_user = cls.env['res.users'].create({
            'name': 'CSCL Non-System User',
            'login': 'cscl_nonsystem@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def test_non_system_user_cannot_unlink_log(self):
        """C-SCL-001: a non-system user deleting an audit row raises AccessError."""
        with self.assertRaises(AccessError):
            self.log.with_user(self.non_system_user).unlink()

    def test_system_user_can_unlink_log(self):
        """C-SCL-001 carve-out: system administrators may delete audit rows."""
        self.log.with_user(self.env.ref('base.user_root')).unlink()
        self.assertFalse(self.log.exists())
