"""
Phase 2: ORM unit tests for sale.order.fulfillment delegation mixin.

Tests verify the business logic and delegation semantics:
- sale.order automatically creates a fulfillment_id sibling on create
- Delegated fields are transparently written/read through the sibling
- Cascade delete removes the fulfillment sibling when order is deleted
- Default values are correctly applied on sibling creation
- Constraints (e.g., block_reason required when production_blocked) are enforced
- Search queries through delegated fields work correctly
- User FK with set_null ondelete behaves correctly

Tests use TransactionCase to isolate each test in a savepoint.
Tests are tagged post_install so the full ORM registry is loaded.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase2ORM(TransactionCase):
    """ORM and business logic tests for sale.order.fulfillment delegation."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data once for all tests."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'customer@test.com',
        })

        cls.user = cls.env['res.users'].create({
            'name': 'Test PIC User',
            'login': 'pic_user@test.com',
            'email': 'pic_user@test.com',
        })

    def _create_order(self, **kwargs):
        """Factory method to create a sale.order with default test data."""
        defaults = {
            'partner_id': self.partner.id,
            'order_line': [],
        }
        defaults.update(kwargs)
        return self.env['sale.order'].create(defaults)

    def test_create_order_auto_creates_fulfillment_sibling(self):
        """Test that creating a sale.order auto-creates its fulfillment_id sibling."""
        order = self._create_order()

        self.assertTrue(order.id, "Order should be created with an ID")
        self.assertIsNotNone(
            order.fulfillment_id,
            "fulfillment_id should be created automatically"
        )
        self.assertTrue(
            order.fulfillment_id.id,
            "fulfillment_id should reference a real record"
        )
        self.assertEqual(
            order.fulfillment_id._name,
            'sale.order.fulfillment',
            "fulfillment_id should be a sale.order.fulfillment record"
        )

    def test_delegated_write_then_read_via_order(self):
        """Test that writing tracking_number via order delegates to fulfillment sibling."""
        order = self._create_order()

        order.write({'tracking_number': 'TEST123'})

        self.assertEqual(
            order.tracking_number,
            'TEST123',
            "tracking_number should be readable via order"
        )
        self.assertEqual(
            order.fulfillment_id.tracking_number,
            'TEST123',
            "tracking_number should be stored in the fulfillment sibling"
        )

    def test_delegated_write_via_sibling_visible_on_order(self):
        """Test that writing via sibling makes the value visible on the order."""
        order = self._create_order()

        order.fulfillment_id.write({'tracking_number': 'SIBLING_WRITE'})

        self.assertEqual(
            order.tracking_number,
            'SIBLING_WRITE',
            "tracking_number written to sibling should be readable via order"
        )

    def test_cascade_delete(self):
        """Test that deleting an order cascades delete to its fulfillment sibling."""
        order = self._create_order()
        fulfillment_id = order.fulfillment_id.id

        order.unlink()

        fulfillment = self.env['sale.order.fulfillment'].search(
            [('id', '=', fulfillment_id)]
        )
        self.assertFalse(
            fulfillment.exists(),
            "fulfillment sibling should be deleted when order is deleted"
        )

    def test_bulk_create(self):
        """Test that bulk create_multi assigns distinct fulfillment_ids."""
        orders = self.env['sale.order'].create([
            {
                'partner_id': self.partner.id,
                'order_line': [],
            },
            {
                'partner_id': self.partner.id,
                'order_line': [],
            },
        ])

        self.assertEqual(len(orders), 2, "Should create 2 orders")
        self.assertIsNotNone(
            orders[0].fulfillment_id,
            "First order should have fulfillment_id"
        )
        self.assertIsNotNone(
            orders[1].fulfillment_id,
            "Second order should have fulfillment_id"
        )
        self.assertNotEqual(
            orders[0].fulfillment_id.id,
            orders[1].fulfillment_id.id,
            "Each order should have a distinct fulfillment_id"
        )

    def test_search_through_delegation_rewrites(self):
        """Test that searching on delegated fields correctly rewrites the query."""
        order_a = self._create_order()
        order_b = self._create_order()

        order_a.write({'tracking_number': 'AAA'})
        order_b.write({'tracking_number': 'BBB'})

        result = self.env['sale.order'].search([
            ('tracking_number', '=', 'AAA')
        ])

        self.assertEqual(len(result), 1, "Should find exactly one order")
        self.assertEqual(
            result.id,
            order_a.id,
            "Search should return order_a"
        )

    def test_default_values_on_sibling(self):
        """Test that fulfillment sibling has correct default values."""
        order = self._create_order()

        # P1-LBL — label_status_id is a Many2one (no required=True);
        # nullable post-migration to avoid breaking _inherits auto-create.
        self.assertFalse(
            order.fulfillment_id.label_status_id,
            "label_status_id should default to False (M2O unset)"
        )
        self.assertEqual(
            order.fulfillment_id.tracking_state,
            'none',
            "tracking_state should default to 'none'"
        )
        self.assertEqual(
            order.fulfillment_id.order_priority,
            'normal',
            "order_priority should default to 'normal'"
        )
        self.assertFalse(
            order.fulfillment_id.production_blocked,
            "production_blocked should default to False"
        )
        self.assertEqual(
            order.fulfillment_id.fulfillment_status,
            'pending',
            "fulfillment_status should default to 'pending'"
        )

    def test_block_reason_required_when_blocked(self):
        """Test that block_reason is required when production_blocked is True."""
        order = self._create_order()

        with self.assertRaises(ValidationError):
            order.fulfillment_id.write({
                'production_blocked': True,
                'block_reason': False,
            })

    def test_block_reason_optional_when_not_blocked(self):
        """Test that block_reason is optional when production_blocked is False."""
        order = self._create_order()

        order.fulfillment_id.write({
            'production_blocked': False,
            'block_reason': False,
        })

        self.assertFalse(order.fulfillment_id.production_blocked)
        self.assertFalse(order.fulfillment_id.block_reason)

    def test_pic_user_id_set_null_on_user_unlink(self):
        """Test that pic_user_id is cleared when the assigned user is deleted.

        ondelete='set null' fires on unlink(), not on archive (active=False).
        Use a fresh user with no other FK references so the unlink succeeds.
        Odoo's res.partner._unlink_except_user blocks deleting the linked
        partner before the user, so the order is: unlink user (which detaches
        the partner), then unlink partner.
        """
        ephemeral_partner = self.env['res.partner'].create({'name': 'Ephemeral PIC Partner'})
        ephemeral_user = self.env['res.users'].create({
            'name': 'Ephemeral PIC',
            'login': f'ephemeral_pic_{self.env.cr.dbname}@test.com',
            'partner_id': ephemeral_partner.id,
        })
        order = self._create_order()
        order.fulfillment_id.pic_user_id = ephemeral_user.id
        self.assertEqual(order.fulfillment_id.pic_user_id, ephemeral_user)

        ephemeral_user.unlink()

        order.fulfillment_id.invalidate_recordset(['pic_user_id'])
        self.assertFalse(
            order.fulfillment_id.pic_user_id,
            "pic_user_id should be set to null when user is unlinked"
        )

    def test_sales_user_cannot_unlink_fulfillment_directly(self):
        """ACL: a sales-user without perm_unlink on sale.order.fulfillment must
        not be able to delete a fulfillment row directly. The cascade from
        sale.order.unlink() is sudo-protected (system-enforced) and is the
        only legitimate path for fulfillment deletion by non-managers.
        """
        from odoo.exceptions import AccessError

        sales_user = self.env['res.users'].create({
            'name': 'Sales User',
            'login': f'sales_user_{self.env.cr.dbname}@test.com',
            'group_ids': [(6, 0, [self.env.ref('sales_team.group_sale_salesman').id])],
        })
        order = self._create_order()
        fulfillment = order.fulfillment_id

        with self.assertRaises(AccessError):
            fulfillment.with_user(sales_user).unlink()

    def test_existing_orders_backfilled_at_install(self):
        """
        Test that existing orders (from etsy_integration) have fulfillment_id
        after post_init_hook runs.

        Note: this test assumes the post_init_hook in __init__.py backfilled
        all pre-existing sale.order rows with fulfillment_id during module
        installation.
        """
        orphaned = self.env['sale.order'].search([('fulfillment_id', '=', False)])
        self.assertFalse(
            orphaned.exists(),
            "All sale.order rows should have fulfillment_id after install"
        )
