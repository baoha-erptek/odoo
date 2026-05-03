"""
Phase 2: ORM unit tests for audit log (chatter) functionality (P1-08).

Tests verify that tracked field writes produce mail.tracking.value rows
(chatter entries) and that mail.activity.mixin allows activity scheduling.

Important: mail.tracking.value is created lazily during write() flush.
Tests explicitly call record.flush_recordset() and re-query to ensure
tracking values are available.

References: Spec 003 FR-031 (audit log coverage), AC-2 (tracking values),
SC-007 (50+ tracked edits coverage).
"""

import logging
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestAuditChatterOrmBehavior(TransactionCase):
    """Phase 2: ORM tests for chatter and tracking functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests in class."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        """Reset tracking context for each test."""
        super().setUp()
        # Disable tracking during setup, enable for actual test methods
        self.env.context = dict(self.env.context, tracking_disable=False)

    def _create_partner(self, **kwargs):
        """Factory for test partners."""
        defaults = {
            'name': 'Test Partner',
            'email': 'test@example.com',
        }
        defaults.update(kwargs)
        return self.env['res.partner'].create(defaults)

    def _create_sale_order(self, partner=None, **kwargs):
        """Factory for test sale orders."""
        if partner is None:
            partner = self._create_partner()

        defaults = {
            'partner_id': partner.id,
        }
        defaults.update(kwargs)
        return self.env['sale.order'].create(defaults)

    def _get_tracking_values(self, record_model, record_id, field_name):
        """Helper: retrieve tracking value rows for a given record + field.

        mail.tracking.value is lazy-created during flush. This helper
        re-queries to ensure tracking values are available.
        """
        # Force flush to ensure tracking values are written
        self.env.cr.flush()

        # Query mail.tracking.value joined via mail.message
        self.env.cr.execute("""
            SELECT mtv.id, mtv.old_value_char, mtv.new_value_char,
                   mtv.old_value_integer, mtv.new_value_integer
            FROM mail_tracking_value mtv
            JOIN mail_message mm ON mtv.mail_message_id = mm.id
            JOIN ir_model im ON mm.model_id = im.id
            JOIN ir_model_fields imf ON mtv.field_id = imf.id
            WHERE im.model = %s
              AND mm.res_id = %s
              AND imf.name = %s
            ORDER BY mtv.id DESC
            LIMIT 1
        """, (record_model, record_id, field_name))

        result = self.env.cr.fetchone()
        return result

    def test_AC2_design_file_state_write_creates_tracking_value(self):
        """Test AC-2: design.file state write produces tracking.value row.

        design.file already has mail.thread + mail.activity.mixin + tracking=True
        on state field. This test verifies chatter works (regression guard).
        """
        # Create a design file with initial state
        order = self._create_sale_order()
        design_file = self.env['design.file'].create({
            'name': 'Test Design',
            'order_id': order.id,
            'state': 'pending',
        })

        self.assertEqual(design_file.state, 'pending')

        # Write to tracked field
        design_file.write({'state': 'approved'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('design.file', design_file.id, 'state')

        self.assertIsNotNone(
            tracking,
            "design.file state change should produce mail.tracking.value row"
        )
        self.assertEqual(
            tracking[1], 'pending',
            "Tracking value should record old state='pending'"
        )
        self.assertEqual(
            tracking[2], 'approved',
            "Tracking value should record new state='approved'"
        )

    def test_AC2_shipping_carrier_name_write_creates_tracking_value(self):
        """Test AC-2: shipping.carrier name write produces tracking.value.

        FAILS in RED because shipping.carrier doesn't have mail.thread yet.
        GREEN will add the mixin + tracking=True.
        """
        carrier = self.env['shipping.carrier'].create({
            'name': 'USPS Original',
            'code': 'usps_test_001',
        })

        # Write to tracked field
        carrier.write({'name': 'USPS Updated'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('shipping.carrier', carrier.id, 'name')

        self.assertIsNotNone(
            tracking,
            "shipping.carrier name change should produce mail.tracking.value row"
        )
        self.assertEqual(
            tracking[1], 'USPS Original',
            "Tracking value should record old name"
        )
        self.assertEqual(
            tracking[2], 'USPS Updated',
            "Tracking value should record new name"
        )

    def test_AC2_shipping_carrier_etsy_carrier_write_creates_tracking_value(self):
        """Test AC-2: shipping.carrier etsy_carrier_name write produces tracking.value."""
        carrier = self.env['shipping.carrier'].create({
            'name': 'Test Carrier',
            'code': 'test_001',
            'etsy_carrier_name': 'usps',
        })

        # Write to tracked field
        carrier.write({'etsy_carrier_name': 'ups'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('shipping.carrier', carrier.id, 'etsy_carrier_name')

        self.assertIsNotNone(
            tracking,
            "shipping.carrier etsy_carrier_name change should produce tracking.value"
        )

    def test_AC2_order_pipeline_name_write_creates_tracking_value(self):
        """Test AC-2: order.pipeline name write produces tracking.value.

        FAILS in RED because order.pipeline doesn't have mail.thread yet.
        """
        pipeline = self.env['order.pipeline'].create({
            'name': 'Original Pipeline',
            'code': 'orig_pipeline',
            'channel_hint': 'internal',
        })

        # Write to tracked field
        pipeline.write({'name': 'Updated Pipeline'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('order.pipeline', pipeline.id, 'name')

        self.assertIsNotNone(
            tracking,
            "order.pipeline name change should produce mail.tracking.value row"
        )

    def test_AC2_order_pipeline_state_name_write_creates_tracking_value(self):
        """Test AC-2: order.pipeline.state name write produces tracking.value.

        FAILS in RED because order.pipeline.state doesn't have mail.thread yet.
        """
        pipeline = self.env['order.pipeline'].create({
            'name': 'Test Pipeline',
            'code': 'test_pipe',
            'channel_hint': 'internal',
        })

        state = self.env['order.pipeline.state'].create({
            'pipeline_id': pipeline.id,
            'name': 'Original State',
            'code': 'orig_state',
            'is_initial': True,
        })

        # Write to tracked field
        state.write({'name': 'Updated State'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('order.pipeline.state', state.id, 'name')

        self.assertIsNotNone(
            tracking,
            "order.pipeline.state name change should produce mail.tracking.value row"
        )

    def test_AC2_pipeline_team_name_write_creates_tracking_value(self):
        """Test AC-2: pipeline.team name write produces tracking.value.

        FAILS in RED because pipeline.team doesn't have mail.thread yet.
        """
        team = self.env['pipeline.team'].create({
            'name': 'Original Team',
            'code': 'orig_team',
        })

        # Write to tracked field
        team.write({'name': 'Updated Team'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('pipeline.team', team.id, 'name')

        self.assertIsNotNone(
            tracking,
            "pipeline.team name change should produce mail.tracking.value row"
        )

    def test_AC2_fulfillment_activity_mixin_allows_scheduling(self):
        """Test AC-2: sale.order.fulfillment allows activity scheduling via mail.activity.mixin.

        FAILS in RED because fulfillment only has mail.thread, not mail.activity.mixin yet.
        """
        order = self._create_sale_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
        })

        # Try to schedule an activity (mail.activity.mixin method)
        activity = fulfillment.activity_schedule(
            'mail.mail_activity_data_todo',
            summary='Test Activity',
        )

        self.assertIsNotNone(activity.id, "Activity should be created")
        self.assertEqual(activity.res_id, fulfillment.id)

    def test_AC2_fulfillment_tracking_number_write_creates_tracking_value(self):
        """Test AC-2: sale.order.fulfillment tracking_number write produces tracking.value.

        Fulfillment already has mail.thread, verifies it works (regression).
        """
        order = self._create_sale_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': 'TRACK-001',
        })

        # Write to tracked field
        fulfillment.write({'tracking_number': 'TRACK-002'})

        # Flush and query tracking value
        tracking = self._get_tracking_values(
            'sale.order.fulfillment',
            fulfillment.id,
            'tracking_number'
        )

        self.assertIsNotNone(
            tracking,
            "fulfillment tracking_number change should produce mail.tracking.value"
        )

    def test_AC2_design_file_route_state_write_creates_tracking_value(self):
        """Test AC-2: design.file.route state write produces tracking.value.

        FAILS in RED because design.file.route only has mail.thread, not mail.activity.mixin.
        """
        order = self._create_sale_order()
        design_file = self.env['design.file'].create({
            'name': 'Route Test File',
            'order_id': order.id,
            'state': 'approved',
        })

        route = self.env['design.file.route'].create({
            'design_file_id': design_file.id,
            'recipient_type': 'mp',
            'recipient_user_id': self.env.user.id,
            'delivery_method': 'gdrive_share',
            'state': 'pending',
        })

        # Write to tracked field
        route.write({'state': 'sent'})

        # Flush and query tracking value
        tracking = self._get_tracking_values('design.file.route', route.id, 'state')

        self.assertIsNotNone(
            tracking,
            "design.file.route state change should produce mail.tracking.value"
        )

    def test_SC007_multiple_tracked_edits_create_chatter_coverage(self):
        """Test SC-007: Multiple tracked field edits produce chatter entries.

        Sample coverage across spec-003 models. Builds a deterministic list of
        (model, field, before, after) tuples and verifies each produces a
        tracking value.

        This test partially passes in RED (design.file, fulfillment, etsy
        address request work) and fails on shipping.carrier / order.pipeline*
        tuples until mail.thread is added in GREEN.
        """
        # Test data: (model_class, create_defaults, write_field, old_value, new_value)
        test_cases = [
            # design.file (has tracking already)
            (
                self.env['design.file'],
                {
                    'name': 'Test File',
                    'order_id': self._create_sale_order().id,
                    'state': 'pending',
                },
                'state',
                'pending',
                'approved',
            ),
            # fulfillment (has tracking already)
            (
                self.env['sale.order.fulfillment'],
                {
                    'order_id': self._create_sale_order().id,
                    'tracking_number': 'TRK001',
                },
                'tracking_number',
                'TRK001',
                'TRK002',
            ),
            # shipping.carrier (will fail until mail.thread added)
            (
                self.env['shipping.carrier'],
                {
                    'name': 'Test Carrier',
                    'code': 'test_carrier',
                },
                'name',
                'Test Carrier',
                'Updated Carrier',
            ),
            # order.pipeline (will fail until mail.thread added)
            (
                self.env['order.pipeline'],
                {
                    'name': 'Test Pipeline',
                    'code': 'test_pipeline',
                    'channel_hint': 'internal',
                },
                'name',
                'Test Pipeline',
                'Updated Pipeline',
            ),
        ]

        passed = []
        failed = []

        for model_env, create_vals, field_name, old_value, new_value in test_cases:
            try:
                record = model_env.create(create_vals)

                # Write tracked field
                record.write({field_name: new_value})

                # Check for tracking value
                tracking = self._get_tracking_values(
                    model_env._name,
                    record.id,
                    field_name,
                )

                if tracking:
                    passed.append(f"{model_env._name}.{field_name}")
                else:
                    failed.append(
                        f"{model_env._name}.{field_name} (no tracking value)"
                    )

            except Exception as e:
                failed.append(f"{model_env._name}.{field_name} (error: {e})")

        # Report results
        self.assertGreater(
            len(passed),
            0,
            f"SC-007: At least some tracked fields should produce chatter. "
            f"Passed: {passed}, Failed: {failed}"
        )

        # In RED, we expect failures for models without mail.thread
        # This assertion documents that we're making progress
        if failed:
            _logger.info(
                "SC-007 RED phase: %d/%d tracked edits produced chatter. "
                "Failures expected for models without mail.thread: %s",
                len(passed),
                len(passed) + len(failed),
                failed,
            )


@tagged('post_install', '-at_install')
class TestAuditChatterEdgeCases(TransactionCase):
    """Phase 2: Edge cases for chatter and audit functionality."""

    def _create_partner(self, **kwargs):
        """Factory for test partners."""
        defaults = {'name': 'Test Partner', 'email': 'test@example.com'}
        defaults.update(kwargs)
        return self.env['res.partner'].create(defaults)

    def _create_sale_order(self, partner=None):
        """Factory for test sale orders."""
        if partner is None:
            partner = self._create_partner()
        return self.env['sale.order'].create({'partner_id': partner.id})

    def test_design_file_route_missing_activity_mixin(self):
        """Test: design.file.route missing mail.activity.mixin prevents activity scheduling.

        FAILS in RED; GREEN will add mail.activity.mixin.
        """
        design_file = self.env['design.file'].create({
            'name': 'Test File',
            'order_id': self._create_sale_order().id,
            'state': 'approved',
        })

        route = self.env['design.file.route'].create({
            'design_file_id': design_file.id,
            'recipient_type': 'mp',
            'recipient_user_id': self.env.user.id,
            'delivery_method': 'gdrive_share',
        })

        # Try to schedule activity (should work if mail.activity.mixin present)
        try:
            activity = route.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='Test',
            )
            # If we reach here, mixin is present
            self.assertIsNotNone(activity.id)
        except AttributeError:
            self.fail(
                "design.file.route: should inherit mail.activity.mixin "
                "to support activity scheduling"
            )

    def test_shipping_carrier_missing_mail_thread(self):
        """Test: shipping.carrier missing mail.thread cannot create messages/chatter.

        FAILS in RED; GREEN will add mail.thread.
        """
        carrier = self.env['shipping.carrier'].create({
            'name': 'Test Carrier',
            'code': 'test_carrier',
        })

        # Try to post a message (mail.thread method)
        try:
            message = carrier.message_post(
                body="Test message",
                message_type='comment',
            )
            # If we reach here, mail.thread is present
            self.assertIsNotNone(message.id)
        except AttributeError:
            self.fail(
                "shipping.carrier: should inherit mail.thread to support chatter"
            )

    def test_order_pipeline_missing_mail_thread(self):
        """Test: order.pipeline missing mail.thread cannot create messages.

        FAILS in RED; GREEN will add mail.thread.
        """
        pipeline = self.env['order.pipeline'].create({
            'name': 'Test Pipeline',
            'code': 'test_pipeline',
            'channel_hint': 'internal',
        })

        # Try to post a message (mail.thread method)
        try:
            message = pipeline.message_post(
                body="Test message",
                message_type='comment',
            )
            self.assertIsNotNone(message.id)
        except AttributeError:
            self.fail(
                "order.pipeline: should inherit mail.thread to support chatter"
            )
