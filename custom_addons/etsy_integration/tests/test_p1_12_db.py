"""Phase 1 DB tests for P1-12 — EtsyTrackingPusher (Spec 005 US3).

These tests verify data schema and database-level integrity without relying on
service implementation. They use direct SQL to verify:
- etsy_tracking_push_status, etsy_tracking_push_at, etsy_tracking_push_error columns exist
- etsy_tracking_push_status Selection includes 'none'/'pending'/'pushed'/'failed'
- Default value for etsy_tracking_push_status resolves to 'none'
- ir.cron record 'cron_etsy_tracking_push' exists with correct schedule

PHASE: RED (failing tests — implementation does not exist yet)
"""
import logging

from odoo.tests.common import SingleTransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p1_12')
class TestP1_12TrackingPushSchema(SingleTransactionCase):
    """Phase 1: Database schema verification for P1-12 EtsyTrackingPusher."""

    def test_etsy_tracking_push_status_column_exists(self):
        """Test that etsy_tracking_push_status column exists on sale_order table.

        Per data-model.md §6, column is Selection with values:
        'none'/'pending'/'pushed'/'failed', default='none'.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sale_order'
            AND column_name = 'etsy_tracking_push_status'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "etsy_tracking_push_status column should exist on sale_order table"
        )
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'etsy_tracking_push_status')
        self.assertEqual(
            data_type, 'character varying',
            "etsy_tracking_push_status should be VARCHAR (Selection)"
        )
        self.assertEqual(
            is_nullable, 'YES',
            "etsy_tracking_push_status should be nullable"
        )

    def test_etsy_tracking_push_at_column_exists(self):
        """Test that etsy_tracking_push_at column exists on sale_order table.

        Per data-model.md §6, column is Datetime (timestamp without time zone).
        """
        self.env.cr.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sale_order'
            AND column_name = 'etsy_tracking_push_at'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "etsy_tracking_push_at column should exist on sale_order table"
        )
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'etsy_tracking_push_at')
        self.assertEqual(
            data_type, 'timestamp without time zone',
            "etsy_tracking_push_at should be timestamp type"
        )
        self.assertEqual(
            is_nullable, 'YES',
            "etsy_tracking_push_at should be nullable"
        )

    def test_etsy_tracking_push_error_column_exists(self):
        """Test that etsy_tracking_push_error column exists on sale_order table.

        Per data-model.md §6, column is Text for error messages.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sale_order'
            AND column_name = 'etsy_tracking_push_error'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "etsy_tracking_push_error column should exist on sale_order table"
        )
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'etsy_tracking_push_error')
        self.assertIn(
            data_type, ('text', 'character varying'),
            "etsy_tracking_push_error should be text or varchar"
        )
        self.assertEqual(
            is_nullable, 'YES',
            "etsy_tracking_push_error should be nullable"
        )

    def test_etsy_tracking_push_status_selection_values(self):
        """Test that etsy_tracking_push_status Selection field includes required values.

        Per data-model.md §6, values are: 'none'/'pending'/'pushed'/'failed'.
        """
        status_field = self.env['sale.order']._fields['etsy_tracking_push_status']

        self.assertEqual(
            status_field.type, 'selection',
            "etsy_tracking_push_status must be a Selection field"
        )

        # Extract selection values
        selection_values = [choice[0] for choice in status_field.selection]

        required_values = ['none', 'pending', 'pushed', 'failed']
        for value in required_values:
            self.assertIn(
                value, selection_values,
                f"etsy_tracking_push_status Selection must include '{value}'"
            )

    def test_etsy_tracking_push_status_default_is_none(self):
        """Test that etsy_tracking_push_status default value is 'none'.

        Per data-model.md §6 and plan T026.
        """
        status_field = self.env['sale.order']._fields['etsy_tracking_push_status']

        # Odoo 19 normalizes a scalar `default=` into a callable
        # (`lambda recs: value`) during field setup, so compare the
        # resolved value, not the raw attribute.
        default = status_field.default
        resolved = (
            default(self.env['sale.order']) if callable(default) else default
        )
        self.assertEqual(
            resolved, 'none',
            "etsy_tracking_push_status default should resolve to 'none'"
        )

    def test_etsy_tracking_push_status_default_on_new_record(self):
        """Test that new sale.order records have etsy_tracking_push_status='none'.

        Verify via the ORM that default is applied at create time.
        """
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
        })

        product = self.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        })

        # Verify the default is applied
        self.assertEqual(
            order.etsy_tracking_push_status, 'none',
            "New sale.order should have etsy_tracking_push_status='none'"
        )

    def test_cron_etsy_tracking_push_record_exists(self):
        """Test that ir.cron record for tracking push exists with correct schedule.

        Per plan T035, cron runs every 5 minutes as fallback for webhook failures.
        GREEN must name the cron 'Etsy: Push Tracking to Etsy' and call
        'cron_push_tracking' or similar method.
        """
        # Search by the method name that the cron should call
        cron = self.env['ir.cron'].search(
            [('code', 'ilike', '%cron_push_tracking%')],
            limit=1
        )

        self.assertTrue(
            cron,
            "ir.cron record calling cron_push_tracking should exist"
        )

        # Verify it's active
        self.assertTrue(cron.active, "Cron should be active")

        # Verify the model is sale.order
        self.assertEqual(
            cron.model_id.model, 'sale.order',
            "Cron should target sale.order model"
        )

        # Verify the method call is correct
        # The code should call a _cron_push_tracking method
        self.assertIn(
            'cron_push_tracking',
            cron.code or '',
            "Cron code should call cron_push_tracking method"
        )

        # Verify interval: 5 minutes
        self.assertEqual(
            cron.interval_type, 'minutes',
            "Cron interval type should be 'minutes'"
        )
        self.assertEqual(
            cron.interval_number, 5,
            "Cron should run every 5 minutes"
        )
