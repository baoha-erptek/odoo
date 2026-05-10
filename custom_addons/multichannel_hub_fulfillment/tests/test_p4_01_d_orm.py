"""P4-01-D Phase 2 ORM — bulk Gearment sync action behaviour.

Covers:
  - dedup via mapped('order_id') across multi-line selection
  - savepoint isolation: per-order failure does not roll back others
  - FR-017 12th confirmation: non-shipping user blocked before any sudo write
  - bus.bus.sendmany progress fired per unique order

Reference: `specs/004-fulfillment-routing/p4-01-d-plan.md` §3.
"""
from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


_TEST_ENV = {
    'GEARMENT_API_KEY': 'TEST_KEY',
    'GEARMENT_API_SECRET': 'TEST_SECRET',
    'GEARMENT_API_BASE_URL': 'https://api.gearment.test',
}


def _make_orders_with_lines(env, count=3, lines_per_order=2):
    """Create N orders with M Gearment-eligible lines each."""
    partner = env['res.partner'].create({
        'name': 'P4-01-D Customer', 'street': '1 Main',
        'city': 'Boston', 'zip': '02108',
        'country_id': env.ref('base.us').id,
    })
    product = env['product.template'].create({
        'name': 'P4D Mug', 'x_gearment_sku': '99001',
    })
    orders = []
    for _ in range(count):
        order = env['sale.order'].create({
            'partner_id': partner.id, 'sales_channel': 'etsy',
            'order_line': [
                (0, 0, {
                    'product_id': product.product_variant_ids[:1].id,
                    'product_uom_qty': 1, 'price_unit': 10.0,
                })
                for _ in range(lines_per_order)
            ],
        })
        orders.append(order)
    return orders


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DBulkSyncDedup(TransactionCase):

    def test_bulk_sync_dedupes_orders(self):
        """N lines from M orders → bulk action calls quote ONCE per order."""
        orders = _make_orders_with_lines(self.env, count=2, lines_per_order=3)
        all_lines = self.env['sale.order.line'].search([
            ('order_id', 'in', [o.id for o in orders]),
        ])
        self.assertEqual(len(all_lines), 6)
        unique_orders = all_lines.mapped('order_id')
        self.assertEqual(len(unique_orders), 2)

        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from decimal import Decimal
        stub_quote = {
            'currency': 'USD',
            'order_total': Decimal('45.99'),
            'order_sub_total': Decimal('40.00'),
            'order_shipping_fee': Decimal('5.99'),
            'order_tax': Decimal('0E-9'),
            'order_discount': Decimal('0E-9'),
            'order_handle_fee': Decimal('0E-9'),
            'order_gift_message_fee': Decimal('0E-9'),
            'order_fee': Decimal('0E-9'),
        }
        with mock.patch.dict('os.environ', _TEST_ENV, clear=False), \
             mock.patch.object(
                 GearmentApiAdapter, 'get_quote', return_value=stub_quote,
             ) as mock_quote:
            all_lines.action_gearment_bulk_sync()
        self.assertEqual(
            mock_quote.call_count, 2,
            'Quote should be called once per unique order, not per line',
        )


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DBulkSyncSavepoint(TransactionCase):

    def test_savepoint_isolates_per_order_failures(self):
        """One order failing does not roll back the others."""
        orders = _make_orders_with_lines(self.env, count=3, lines_per_order=1)
        all_lines = self.env['sale.order.line'].search([
            ('order_id', 'in', [o.id for o in orders]),
        ])

        # First order succeeds, second raises, third succeeds
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from decimal import Decimal
        stub_quote = {
            'currency': 'USD',
            'order_total': Decimal('45.99'),
            'order_sub_total': Decimal('40.00'),
            'order_shipping_fee': Decimal('5.99'),
            'order_tax': Decimal('0E-9'),
            'order_discount': Decimal('0E-9'),
            'order_handle_fee': Decimal('0E-9'),
            'order_gift_message_fee': Decimal('0E-9'),
            'order_fee': Decimal('0E-9'),
        }
        call_count = {'n': 0}

        def fake_get_quote(self_adapter, ref):
            call_count['n'] += 1
            if call_count['n'] == 2:
                raise RuntimeError('forced failure for order 2')
            return stub_quote

        with mock.patch.dict('os.environ', _TEST_ENV, clear=False), \
             mock.patch.object(
                 GearmentApiAdapter, 'get_quote', autospec=True,
                 side_effect=fake_get_quote,
             ):
            all_lines.action_gearment_bulk_sync()
        # Two orders succeeded
        succeeded = [o for o in orders if o.x_gearment_outbound_state == 'quoted']
        self.assertEqual(
            len(succeeded), 2,
            'Savepoint isolation broken: expected 2 quoted, got '
            f'{[o.x_gearment_outbound_state for o in orders]}',
        )


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DBulkSyncFR017(TransactionCase):

    def test_non_shipping_user_blocked_before_any_write(self):
        """FR-017 12th confirmation."""
        orders = _make_orders_with_lines(self.env, count=1, lines_per_order=1)
        non_shipping = self.env['res.users'].create({
            'name': 'Bob D', 'login': 'bob_p4d@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        line = orders[0].order_line[0]
        with self.assertRaises(AccessError):
            line.with_user(non_shipping).action_gearment_bulk_sync()
        # State must NOT have advanced
        self.assertEqual(orders[0].x_gearment_outbound_state, 'draft')


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DBulkSyncBusNotification(TransactionCase):

    def test_bus_notification_fired_per_unique_order(self):
        orders = _make_orders_with_lines(self.env, count=2, lines_per_order=2)
        all_lines = self.env['sale.order.line'].search([
            ('order_id', 'in', [o.id for o in orders]),
        ])
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from decimal import Decimal
        stub_quote = {
            'currency': 'USD',
            'order_total': Decimal('45.99'),
            'order_sub_total': Decimal('40.00'),
            'order_shipping_fee': Decimal('5.99'),
            'order_tax': Decimal('0E-9'),
            'order_discount': Decimal('0E-9'),
            'order_handle_fee': Decimal('0E-9'),
            'order_gift_message_fee': Decimal('0E-9'),
            'order_fee': Decimal('0E-9'),
        }
        with mock.patch.dict('os.environ', _TEST_ENV, clear=False), \
             mock.patch.object(
                 GearmentApiAdapter, 'get_quote', return_value=stub_quote,
             ), \
             mock.patch.object(
                 type(self.env['bus.bus']), '_sendone', autospec=True,
             ) as mock_bus:
            all_lines.action_gearment_bulk_sync()
        # At least 2 calls (one per unique order); summary may add one more
        self.assertGreaterEqual(mock_bus.call_count, 2)
