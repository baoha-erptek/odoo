"""
Phase 2: ORM unit tests for ESTY-248 — Surface Gearment order-processing
status on the dropship picking form.

Tests verify:
- x_gearment_tracking_state / x_gearment_production_blocked /
  x_gearment_block_reason resolve through the picking's sale_id related-field
  chain (which itself reads through sale.order's `_inherits` delegation to
  sale.order.fulfillment)
- Pickings without a linked sale order read empty values
- Multiple pickings on the same SO see the same values
- A write on the SO/fulfillment side (simulating a Gearment webhook) is
  immediately visible on an already-loaded picking after cache invalidation
- The inherited view arch contains the new fields

Also verifies the ACL fix for a real gap found during security review:
related fields do not inherit the source model's read ACL, so a user with
`stock.picking` read access (any `stock.group_stock_user`) but no
`sale.order.fulfillment` read access could otherwise read `block_reason`
(internal BA/production notes) through the related field. That field is
gated with `groups=` mirroring `sale.order.fulfillment`'s own ACL; the
plain operational `tracking_state` stays ungated (legitimate warehouse
need).

Tests use TransactionCase. No real Gearment HTTP calls are made — these
tests only exercise the related-field read path, not the webhook dispatcher.
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockPickingGearmentStatusPhase2ORM(TransactionCase):
    """Phase 2 ORM tests for ESTY-248: surface Gearment status on picking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({'name': 'ESTY-248 Partner'})
        cls.dropship_picking_type = cls.env['stock.picking.type'].search(
            [('code', '=', 'dropship')], limit=1
        )

    def _create_sale_order(self, **vals):
        # fulfillment_id is auto-created via sale.order's _inherits delegation.
        defaults = {'name': 'SO-ESTY-248', 'partner_id': self.partner.id}
        defaults.update(vals)
        return self.env['sale.order'].create(defaults)

    def _create_dropship_picking(self, sale_order=None):
        vals = {
            'picking_type_id': self.dropship_picking_type.id,
            'location_id': self.dropship_picking_type.default_location_src_id.id,
            'location_dest_id': self.dropship_picking_type.default_location_dest_id.id,
        }
        if sale_order:
            vals['sale_id'] = sale_order.id
        return self.env['stock.picking'].create(vals)

    def test_tracking_state_resolves_from_linked_sale_order(self):
        so = self._create_sale_order()
        so.write({'tracking_state': 'in_transit'})
        picking = self._create_dropship_picking(so)
        self.assertEqual(picking.x_gearment_tracking_state, 'in_transit')

    def test_production_blocked_and_reason_resolve_from_linked_sale_order(self):
        so = self._create_sale_order()
        # Write on the fulfillment record directly (not through the sale.order
        # delegation) — writing both fields via sale.order triggers separate
        # per-field inverse writes, which trips the compound
        # _check_block_reason_when_blocked constraint mid-way.
        so.fulfillment_id.write({'production_blocked': True, 'block_reason': 'Out of stock'})
        picking = self._create_dropship_picking(so)
        self.assertTrue(picking.x_gearment_production_blocked)
        self.assertEqual(picking.x_gearment_block_reason, 'Out of stock')

    def test_picking_without_sale_id_reads_empty(self):
        picking = self._create_dropship_picking()
        self.assertFalse(picking.x_gearment_tracking_state)
        self.assertFalse(picking.x_gearment_production_blocked)
        self.assertFalse(picking.x_gearment_block_reason)

    def test_multiple_pickings_same_so_show_same_status(self):
        so = self._create_sale_order()
        so.write({'tracking_state': 'shipped'})
        picking1 = self._create_dropship_picking(so)
        picking2 = self._create_dropship_picking(so)
        self.assertEqual(picking1.x_gearment_tracking_state, 'shipped')
        self.assertEqual(picking2.x_gearment_tracking_state, 'shipped')

    def test_status_update_propagates_to_already_loaded_picking(self):
        so = self._create_sale_order()
        so.write({'tracking_state': 'label_ready'})
        picking = self._create_dropship_picking(so)
        self.assertEqual(picking.x_gearment_tracking_state, 'label_ready')

        so.write({'tracking_state': 'shipped'})
        picking.invalidate_recordset()
        self.assertEqual(picking.x_gearment_tracking_state, 'shipped')

    def test_block_reason_hidden_from_warehouse_only_user(self):
        # Regression test for a real ACL-bypass gap found in security review:
        # a stock.group_stock_user (warehouse-only) has no direct read access
        # to sale.order.fulfillment, and must not gain it through the picking
        # related field either.
        so = self._create_sale_order()
        so.fulfillment_id.write({'production_blocked': True, 'block_reason': 'Internal note'})
        picking = self._create_dropship_picking(so)

        warehouse_user = self.env['res.users'].create({
            'name': 'ESTY-248 Warehouse Only',
            'login': 'esty248_warehouse_only',
            'group_ids': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
                self.env.ref('base.group_user').id,
            ])],
        })

        with self.assertRaises(AccessError):
            picking.with_user(warehouse_user).x_gearment_block_reason

        # Plain operational status stays readable — legitimate warehouse need.
        self.assertEqual(
            picking.with_user(warehouse_user).x_gearment_tracking_state, 'none')

    def test_block_reason_visible_to_salesman(self):
        so = self._create_sale_order()
        so.fulfillment_id.write({'production_blocked': True, 'block_reason': 'Internal note'})
        picking = self._create_dropship_picking(so)

        sales_user = self.env['res.users'].create({
            'name': 'ESTY-248 Salesman',
            'login': 'esty248_salesman',
            'group_ids': [(6, 0, [
                self.env.ref('sales_team.group_sale_salesman').id,
                self.env.ref('base.group_user').id,
            ])],
        })

        self.assertEqual(
            picking.with_user(sales_user).x_gearment_block_reason, 'Internal note')

    def test_combined_arch_contains_new_fields(self):
        view = self.env.ref(
            'multichannel_hub_fulfillment.view_picking_form_gearment_status'
        )
        arch = self.env['stock.picking'].get_view(view_id=self.env.ref(
            'stock.view_picking_form').id, view_type='form')['arch']
        self.assertIn('x_gearment_tracking_state', arch)
        self.assertIn('x_gearment_production_blocked', arch)
        self.assertIn('x_gearment_block_reason', arch)
        self.assertTrue(view)  # view record itself resolves
