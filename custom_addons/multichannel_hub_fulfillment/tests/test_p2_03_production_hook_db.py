"""
Phase 1: Database verification tests for P2-03 production stock-move hook.

Tests verify data integrity at the database level:
- Table stock_move has new column 'purpose' for idempotency markers
- Table stock_move has new column 'sale_order_id' linking to the order
- UNIQUE constraint on (sale_order_id, purpose) is enforced at DB level
- ICP 'multichannel_hub_fulfillment.production_locations' is initialized

Tests use direct SQL queries to verify database schema and constraints.
"""

import json

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductionMoveDB(TransactionCase):
    """Phase 1: Verify stock_move table schema for production hook."""

    def test_stock_move_purpose_column_exists(self):
        """T2-03-01: Verify stock_move.purpose column exists.

        The purpose column stores idempotency markers like 'production_completion'
        to prevent duplicate moves in concurrent writes.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'stock_move'
            AND column_name = 'purpose'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "stock_move.purpose column should exist in database"
        )
        # Verify it's a character type (Char field in Odoo)
        self.assertIn(
            result[1],
            ('character varying', 'varchar'),
            f"purpose column should be VARCHAR, got {result[1]}"
        )

    def test_stock_move_sale_order_id_column_exists(self):
        """T2-03-02a: Verify stock_move.sale_order_id column exists.

        Direct M2O link to the sale order for cleaner idempotency checks
        and join performance.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'stock_move'
            AND column_name = 'sale_order_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "stock_move.sale_order_id column should exist in database"
        )
        # Verify it's an integer (Many2one storage)
        self.assertEqual(
            result[1],
            'integer',
            f"sale_order_id should be INTEGER, got {result[1]}"
        )

    def test_stock_move_purpose_unique_constraint(self):
        """T2-03-02: Verify UNIQUE constraint on (sale_order_id, purpose).

        The UNIQUE constraint enforces idempotency: at most one move per
        order with purpose='production_completion'.
        """
        self.env.cr.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'stock_move'
            AND constraint_name = 'stock_move_order_purpose_uniq'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "UNIQUE constraint 'stock_move_order_purpose_uniq' should exist"
        )
        self.assertEqual(
            result[1],
            'UNIQUE',
            "Constraint should be of type UNIQUE"
        )

    def test_production_locations_icp_optional(self):
        """T2-03-03: ICP 'multichannel_hub_fulfillment.production_locations' is optional.

        The ICP may be empty (fail-open) after install, allowing the operator
        to configure warehouse zone → location mappings later via Settings.
        """
        icp_value = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub_fulfillment.production_locations',
            default=False
        )
        # Should not raise; may be False (not set) or empty JSON dict
        if icp_value:
            # If set, must be parseable JSON
            try:
                parsed = json.loads(icp_value)
                self.assertIsInstance(parsed, dict,
                    "ICP value, if set, must be valid JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                self.fail(f"ICP value must be valid JSON: {e}")
