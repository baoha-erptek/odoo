"""FLW-06 — MTO delivery validation advances the SO pipeline to 'shipped'
(spec 015, product-flow audit 2026-07-06).

`stock_picking._action_done` advanced the pipeline only for
`picking_type_id.code == 'dropship'` — validating the delivery order of a
VN-internal (MTO) sale left the pipeline stuck on a mid-stage until an
operator moved it by hand. Outgoing pickings now advance the linked SO to
its pipeline's 'shipped' state via the same idempotent
`_advance_pipeline_to` helper (no-op when already at/past shipped, or when
the pipeline has no such state).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'flw06_mto_picking_shipped')
class TestMtoPickingShipped(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.pipeline_vn = cls.env.ref(
            'multichannel_hub_core.order_pipeline_vn_internal_production')
        cls.state_vn_shipped = cls.env.ref(
            'multichannel_hub_core.state_vn_shipped')
        cls.state_vn_done = cls.env.ref('multichannel_hub_core.state_vn_done')
        cls.partner = cls.env['res.partner'].create({
            'name': 'MTO Ship Customer',
            'street': '9 Kiln Rd', 'city': 'Hanoi', 'zip': '10000',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'FLW06 Poster', 'type': 'consu', 'list_price': 5.0,
        })
        cls.product.product_tmpl_id.x_default_pipeline_id = cls.pipeline_vn.id

    def _order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1,
            })],
        })
        order.invalidate_recordset(['x_pipeline_id', 'x_pipeline_state_id'])
        self.assertEqual(order.x_pipeline_id, self.pipeline_vn)
        return order

    def _outgoing_picking(self, order):
        src = self.env.ref('stock.stock_location_stock')
        dest = self.env.ref('stock.stock_location_customers')
        return self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'sale_id': order.id,
            'move_ids': [(0, 0, {
                # Odoo 19: stock.move has no 'name' field anymore.
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'location_id': src.id,
                'location_dest_id': dest.id,
            })],
        })

    def test_outgoing_picking_done_advances_mto_order_to_shipped(self):
        order = self._order()
        picking = self._outgoing_picking(order)
        picking.action_confirm()
        picking._action_done()
        self.assertEqual(order.x_pipeline_state_id, self.state_vn_shipped)

    def test_idempotent_when_order_already_done(self):
        order = self._order()
        order._write_pipeline_state(self.state_vn_shipped,
                                    change_type='manual')
        picking = self._outgoing_picking(order)
        picking.action_confirm()
        picking._action_done()
        self.assertEqual(
            order.x_pipeline_state_id, self.state_vn_shipped,
            'already-shipped order must not regress or error',
        )

    def test_picking_without_sale_order_is_ignored(self):
        picking = self._outgoing_picking(self._order())
        picking.sale_id = False
        picking.action_confirm()
        picking._action_done()  # must not raise
