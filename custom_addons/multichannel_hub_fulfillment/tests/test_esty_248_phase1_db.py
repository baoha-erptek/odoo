"""
Phase 1: Database verification tests for ESTY-248 — Surface Gearment
order-processing status on the dropship picking form.

Tests verify at the database level:
- ir.model.fields rows exist for x_gearment_tracking_state /
  x_gearment_production_blocked / x_gearment_block_reason on stock.picking,
  each with the correct `related` path (these are non-stored related
  fields, so no physical stock_picking column is expected — they resolve
  via SQL join at read time)
- Each field is a related field pointing at the correct sale_id.<field> path
  (ORM field registry)
- The stock.view_picking_form inheritance record is registered

Tests use direct SQL/env.ref() queries against ir.model.fields and the ORM
field registry for verification.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockPickingGearmentStatusPhase1DB(TransactionCase):
    """Phase 1: Verify ESTY-248 database schema and field definitions."""

    def _assert_model_field_related(self, field_name, expected_related):
        self.env.cr.execute("""
            SELECT related FROM ir_model_fields
            WHERE model = 'stock.picking' AND name = %s
        """, (field_name,))
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row, f"ir.model.fields row for stock.picking.{field_name} should exist"
        )
        self.assertEqual(row[0], expected_related)

    def test_x_gearment_tracking_state_ir_model_fields_row(self):
        self._assert_model_field_related(
            'x_gearment_tracking_state', 'sale_id.tracking_state')

    def test_x_gearment_production_blocked_ir_model_fields_row(self):
        self._assert_model_field_related(
            'x_gearment_production_blocked', 'sale_id.production_blocked')

    def test_x_gearment_block_reason_ir_model_fields_row(self):
        self._assert_model_field_related(
            'x_gearment_block_reason', 'sale_id.block_reason')

    def test_x_gearment_tracking_state_is_related_to_sale_id_tracking_state(self):
        field = self.env['stock.picking']._fields['x_gearment_tracking_state']
        self.assertEqual(field.type, 'selection')
        self.assertEqual(field.related, 'sale_id.tracking_state')

    def test_x_gearment_production_blocked_is_related_to_sale_id_production_blocked(self):
        field = self.env['stock.picking']._fields['x_gearment_production_blocked']
        self.assertEqual(field.type, 'boolean')
        self.assertEqual(field.related, 'sale_id.production_blocked')

    def test_x_gearment_block_reason_is_related_to_sale_id_block_reason(self):
        field = self.env['stock.picking']._fields['x_gearment_block_reason']
        self.assertEqual(field.type, 'text')
        self.assertEqual(field.related, 'sale_id.block_reason')

    def test_view_picking_form_gearment_status_registered(self):
        view = self.env.ref(
            'multichannel_hub_fulfillment.view_picking_form_gearment_status',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(
            view, "View 'view_picking_form_gearment_status' should be registered"
        )
        self.assertEqual(view.inherit_id, self.env.ref('stock.view_picking_form'))
