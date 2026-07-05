# P-KPI-01 — Operations Dashboard KPI band (mockup-v3 plan).
# Phase 2 ORM tests for sale.order.get_operations_dashboard_kpis().
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOperationsDashboardKpi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'KPI Buyer'})
        cls.product = cls.env['product.product'].create({
            'name': 'KPI Product', 'type': 'consu', 'list_price': 10.0,
        })

    def _make_order(self, **vals):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1,
            })],
            **vals,
        })
        return order

    def test_kpi_shape(self):
        kpis = self.env['sale.order'].get_operations_dashboard_kpis()
        self.assertIsInstance(kpis, list)
        self.assertEqual(
            [k['key'] for k in kpis],
            ['orders_today', 'to_fulfill', 'designs_pending', 'channel_errors'],
        )
        for kpi in kpis:
            self.assertIn('label', kpi)
            self.assertIsInstance(kpi['value'], int)

    def test_orders_today_counts_todays_orders(self):
        before = self._kpi('orders_today')
        self._make_order(date_order=fields.Datetime.now())
        self.assertEqual(self._kpi('orders_today'), before + 1)

    def test_to_fulfill_counts_confirmed_undelivered(self):
        before = self._kpi('to_fulfill')
        order = self._make_order()
        order.action_confirm()
        self.assertEqual(self._kpi('to_fulfill'), before + 1)

    def test_designs_pending_counts_pending_design_files(self):
        before = self._kpi('designs_pending')
        order = self._make_order()
        self.env['design.file'].create({
            'name': 'kpi-test-design',
            'order_id': order.id,
            'storage_mode': 'url',
            'file_url': 'https://example.com/kpi-test-design.tiff',
        })
        self.assertEqual(self._kpi('designs_pending'), before + 1)

    def test_channel_errors_counts_error_statuses(self):
        before = self._kpi('channel_errors')
        template = self.product.product_tmpl_id
        channel = self.env['multichannel.sales.channel'].search([], limit=1)
        if not channel:
            channel = self.env['multichannel.sales.channel'].create({
                'name': 'KPI Channel', 'code': 'kpi_test',
            })
        self.env['product.channel.status'].create({
            'product_tmpl_id': template.id,
            'channel_id': channel.id,
            'state': 'error',
        })
        self.assertEqual(self._kpi('channel_errors'), before + 1)

    def _kpi(self, key):
        kpis = self.env['sale.order'].get_operations_dashboard_kpis()
        return next(k['value'] for k in kpis if k['key'] == key)

    def test_restricted_user_gets_kpis_without_access_error(self):
        # A user who can open the dashboard but cannot read side models
        # (design.file etc.) must still get the full KPI list — restricted
        # counts degrade to 0 instead of raising AccessError.
        restricted = self.env['res.users'].create({
            'name': 'KPI Restricted',
            'login': 'kpi_restricted_user',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })
        kpis = (
            self.env['sale.order']
            .with_user(restricted)
            .get_operations_dashboard_kpis()
        )
        self.assertEqual(len(kpis), 4)
        for kpi in kpis:
            self.assertIsInstance(kpi['value'], int)
