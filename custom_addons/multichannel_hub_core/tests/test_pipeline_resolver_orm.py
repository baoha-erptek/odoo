"""P1-PIPELINE-MIN Phase 2 — ORM tests for pipeline_resolver + sale.order.x_pipeline_id."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPipelineResolver(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Pipeline = self.env['order.pipeline']
        self.vn = self.env.ref('multichannel_hub_core.order_pipeline_vn_internal_production')
        self.gearment = self.env.ref('multichannel_hub_core.order_pipeline_gearment_pod')
        self.partner = self.env['res.partner'].create({'name': 'Test Buyer'})
        self.cat_default = self.env.ref('product.product_category_goods')

    def _make_product(self, *, template_pipeline=None, category=None):
        cat = category or self.cat_default
        product_vals = {
            'name': 'P-%s' % (template_pipeline.code if template_pipeline else 'default'),
            'list_price': 1.0,
            'categ_id': cat.id,
        }
        if template_pipeline is not None:
            product_vals['x_default_pipeline_id'] = template_pipeline.id
        product = self.env['product.product'].create(product_vals)
        return product

    def _make_order(self, products):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': p.id, 'product_uom_qty': 1.0})
                for p in products
            ],
        })
        return order

    def test_resolver_uses_template_pipeline_when_set(self):
        product = self._make_product(template_pipeline=self.gearment)
        order = self._make_order([product])
        self.assertEqual(order.x_pipeline_id, self.gearment)

    def test_resolver_falls_back_to_category(self):
        cat = self.env['product.category'].create({
            'name': 'Cat-with-pipeline',
            'x_default_pipeline_id': self.gearment.id,
        })
        product = self._make_product(category=cat)
        order = self._make_order([product])
        self.assertEqual(order.x_pipeline_id, self.gearment)

    def test_resolver_falls_back_to_icp_default(self):
        product = self._make_product()
        order = self._make_order([product])
        self.assertEqual(order.x_pipeline_id, self.vn)

    def test_majority_wins_across_lines(self):
        p1 = self._make_product(template_pipeline=self.gearment)
        p2 = self._make_product(template_pipeline=self.gearment)
        p3 = self._make_product(template_pipeline=self.vn)
        order = self._make_order([p1, p2, p3])
        self.assertEqual(order.x_pipeline_id, self.gearment)

    def test_channel_hint_related_field(self):
        product = self._make_product(template_pipeline=self.gearment)
        order = self._make_order([product])
        self.assertEqual(order.x_pipeline_channel_hint, 'gearment')

    def test_recompute_on_line_change(self):
        product1 = self._make_product(template_pipeline=self.gearment)
        order = self._make_order([product1])
        self.assertEqual(order.x_pipeline_id, self.gearment)
        product2 = self._make_product(template_pipeline=self.vn)
        order.order_line = [(5, 0, 0), (0, 0, {'product_id': product2.id, 'product_uom_qty': 1})]
        order.invalidate_recordset()
        self.assertEqual(order.x_pipeline_id, self.vn)
