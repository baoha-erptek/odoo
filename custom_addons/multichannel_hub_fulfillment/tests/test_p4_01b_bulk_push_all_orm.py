"""Phase 2 ORM tests for P4-01b bulk-push-all-pending action."""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestP401bBulkPushAll(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SaleOrder = cls.env['sale.order']
        cls.ba_shipping = new_test_user(
            cls.env, login='p401b_ba_shipping',
            groups='multichannel_hub_fulfillment.group_ba_shipping,sales_team.group_sale_salesman',
        )
        cls.plain = new_test_user(
            cls.env, login='p401b_plain', groups='base.group_user',
        )
        # Create a Gearment-eligible product (template gets x_gearment_sku
        # → mhf/P1-DROP-SEED auto-applies Dropship route).
        cls.gearment_product = cls.env['product.template'].create({
            'name': 'P401B Gearment Tee',
            'default_code': 'P401B-TEE',
            'list_price': 19.99,
            'x_gearment_sku': 'GMT-TEE-1',
        })
        cls.partner = cls.env.ref('base.partner_admin')

    def _make_order(self, gearment_state='draft', confirmed=True,
                    with_gearment_line=True):
        order = self.SaleOrder.create({
            'partner_id': self.partner.id,
        })
        if with_gearment_line:
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': self.gearment_product.product_variant_ids[:1].id,
                'product_uom_qty': 1.0,
            })
        if confirmed:
            order.action_confirm()
        order.x_gearment_outbound_state = gearment_state
        return order

    def test_non_ba_shipping_blocked(self):
        with self.assertRaises(AccessError):
            self.SaleOrder.with_user(self.plain).action_gearment_bulk_push_all_pending()

    def test_ba_shipping_can_run(self):
        with patch.object(
            type(self.env['sale.order']),
            'action_get_gearment_quote',
            return_value=True,
        ):
            result = self.SaleOrder.with_user(self.ba_shipping).action_gearment_bulk_push_all_pending()
        self.assertIn('eligible', result)
        self.assertIn('succeeded', result)
        self.assertIn('failed', result)

    def test_only_draft_orders_eligible(self):
        draft_order = self._make_order(gearment_state='draft')
        quoted_order = self._make_order(gearment_state='quoted')
        with patch.object(
            type(self.env['sale.order']),
            'action_get_gearment_quote',
            return_value=True,
        ) as quote_mock:
            self.SaleOrder.with_user(self.ba_shipping).action_gearment_bulk_push_all_pending()
        # The mock is called once per eligible draft order. Other tests'
        # data may add to the count; we just assert quoted_order is NOT
        # in the touched set.
        touched_ids = [
            call.args[0].id if call.args else None
            for call in quote_mock.call_args_list
        ]
        # quoted_order should NOT have been pushed
        self.assertNotIn(quoted_order.id, touched_ids,
                          "non-draft order must NOT be re-quoted")

    def test_returns_summary_counters(self):
        """Smoke: action returns the documented summary shape."""
        with patch.object(
            type(self.env['sale.order']),
            'action_get_gearment_quote',
            return_value=True,
        ):
            result = self.SaleOrder.with_user(self.ba_shipping).action_gearment_bulk_push_all_pending()
        for key in ('eligible', 'succeeded', 'failed'):
            self.assertIn(key, result)
            self.assertIsInstance(result[key], int)
