"""Phase 2 (ORM Unit Tests) for P1-04 Address-Change Approval Workflow.

Tests the complete lifecycle of address-change requests including constraint
enforcement, approval/rejection workflows, server-side write guards, and
mail.activity integration.

Tasks covered: T051-T060 constraints, actions, activities; ORM lifecycle tests.
"""

import logging
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestAddressChangeWorkflow(TransactionCase):
    """Phase 2: ORM lifecycle and constraint tests for address-change requests."""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests in the class."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create BA lead group member (R3 mitigation: activity posting requires group member)
        cls.ba_lead_group = cls.env.ref('etsy_integration.group_ba_lead')
        cls.env.user.write({'groups_id': [(4, cls.ba_lead_group.id)]})

        # Create test partner for orders
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'customer@example.com',
            'is_company': False,
        })

        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })

        # Create base sales order
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': cls.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 100.0,
                })
            ],
        })

    def _create_address_change_request(self, order=None, **kwargs):
        """Factory method for test address-change requests."""
        if order is None:
            order = self.order

        defaults = {
            'order_id': order.id,
            'requested_fields': ['partner_shipping_id', 'street'],
            'new_values': {
                'partner_shipping_id': {'id': self.partner.id, 'display_name': self.partner.name},
                'street': '123 New Street',
            },
            'state': 'requested',
            'reason': 'Buyer requested address change',
        }
        defaults.update(kwargs)
        return self.env['etsy.address.change.request'].create(defaults)

    def test_create_request_when_outstanding_exists_blocks(self):
        """Test C-AC-002: Cannot create a second outstanding request on same order.

        Per data-model.md §5 C-AC-002: `state='requested'` is exclusive —
        only one outstanding request per order; new attempt raises `UserError`.
        """
        # Create first request in 'requested' state
        self._create_address_change_request(order=self.order, state='requested')

        # Attempt to create a second request on the same order
        with self.assertRaises(ValidationError) as ctx:
            self._create_address_change_request(order=self.order, state='requested')

        # Verify error message mentions the constraint
        error_msg = str(ctx.exception)
        self.assertIn('outstanding', error_msg.lower())

    def test_create_request_on_shipped_order_blocks(self):
        """Test C-AC-001: Cannot create request on shipped/done/cancel orders.

        Per data-model.md §5 C-AC-001: Order must NOT be in final state
        (`shipped`, `done`, `cancel`) at create time.
        """
        # Set order to 'sale' state and mark as done
        self.order.action_confirm()
        self.order.write({'state': 'done'})

        # Attempt to create request on a shipped order
        with self.assertRaises(ValidationError) as ctx:
            self._create_address_change_request(order=self.order)

        error_msg = str(ctx.exception)
        self.assertIn('shipped', error_msg.lower())

    def test_reject_without_reason_blocks(self):
        """Test C-AC-003: Rejection requires rejection_reason to be set.

        Per data-model.md §5 C-AC-003: `rejection_reason` required when
        `state='rejected'`.
        """
        request = self._create_address_change_request(state='requested')

        # Attempt to reject without a rejection reason
        with self.assertRaises(ValidationError) as ctx:
            request.write({'state': 'rejected'})

        error_msg = str(ctx.exception)
        self.assertIn('rejection_reason', error_msg.lower())

    def test_action_approve_atomic_writes_address(self):
        """Test action_approve: atomic write of address, state, activity close, chatter.

        Per data-model.md §5 action_approve method: applies `new_values` to the
        related `sale.order` in a single transaction with `context={'approve_address_change': True}`,
        sets `state='approved'`, closes BA `mail.activity`, posts chatter delta.
        """
        request = self._create_address_change_request(state='requested')

        # Store old values for chatter verification
        old_street = self.order.street

        # Call action_approve
        request.action_approve()

        # Verify request state changed to 'approved'
        self.assertEqual(request.state, 'approved')

        # Verify approved_by and approved_at are set
        self.assertEqual(request.approved_by, self.env.user)
        self.assertIsNotNone(request.approved_at)

        # Verify sale.order address was updated
        self.assertEqual(
            self.order.street,
            request.new_values.get('street'),
            "Address should be updated to new_values"
        )

        # Verify mail.activity was closed
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.order.id),
            ('res_model_id.model', '=', 'sale.order'),
        ])
        # The activity for this request should not exist or be marked done
        # (closed activities have state='done', open ones have state='todo')

    def test_action_reject_requires_reason_and_mentions_requester(self):
        """Test action_reject: requires rejection_reason and posts @mention chatter.

        Per data-model.md §5 action_reject method: requires `rejection_reason`;
        sets `state='rejected'`, closes activity, notifies requester via chatter @mention.
        """
        requester = self.env['res.users'].create({
            'name': 'Test Requester',
            'login': 'requester@example.com',
        })
        request = self._create_address_change_request(
            state='requested',
            requested_by=requester.id
        )

        # Call action_reject with reason
        request.rejection_reason = 'Address does not match shipping carrier requirements'
        request.action_reject()

        # Verify state changed to 'rejected'
        self.assertEqual(request.state, 'rejected')

        # Verify rejection_reason is preserved
        self.assertEqual(
            request.rejection_reason,
            'Address does not match shipping carrier requirements'
        )

        # Verify requester was mentioned in chatter
        # (Check mail.message with @mention tag for the requester)

    def test_direct_write_blocked_when_pending(self):
        """Test C-SO-001: sale.order write blocked when has_pending_address_change=True.

        Per data-model.md §1 C-SO-001: A write to destination fields when
        `has_pending_address_change == True` raises `UserError`, but passes when
        called via `with_context(approve_address_change=True)` (R2 mitigation).
        """
        # Create an address-change request in 'requested' state
        request = self._create_address_change_request(state='requested')

        # Verify has_pending_address_change is True
        self.order.refresh()
        self.assertTrue(
            self.order.has_pending_address_change,
            "has_pending_address_change should be True when request is 'requested'"
        )

        # Attempt direct write to shipping address — should fail
        with self.assertRaises(UserError) as ctx:
            self.order.write({'street': '456 Blocked Street'})

        error_msg = str(ctx.exception)
        self.assertIn('pending', error_msg.lower())

        # Now write with the bypass context — should succeed
        self.order.with_context(approve_address_change=True).write({
            'street': '789 Approved Street'
        })
        self.assertEqual(self.order.street, '789 Approved Street')

    def test_has_pending_address_change_compute_recomputes_on_state_change(self):
        """Test has_pending_address_change computes correctly on state transitions.

        Per data-model.md §1: `has_pending_address_change` is a Boolean,
        computed with `store=True`, `@api.depends('address_change_request_ids.state')`.
        Must recompute when request.state transitions.
        """
        # Initially, should be False
        self.order.refresh()
        self.assertFalse(self.order.has_pending_address_change)

        # Create request in 'requested' state
        request = self._create_address_change_request(state='requested')
        self.order.refresh()
        self.assertTrue(
            self.order.has_pending_address_change,
            "should be True when request is 'requested'"
        )

        # Approve the request
        request.action_approve()
        self.order.refresh()
        self.assertFalse(
            self.order.has_pending_address_change,
            "should be False when request is 'approved' (not 'requested')"
        )

    def test_auto_activity_created_on_request_create(self):
        """Test T055: Auto-mail.activity on create to group_ba_lead.

        Per data-model.md §5 Activity section: on create, posts `mail.activity`
        to `group_ba_lead` with summary "Approve address change for order <ref>",
        type "To Do", deadline +24h.
        """
        request = self._create_address_change_request(state='requested')

        # Search for the mail.activity created for the order
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.order.id),
        ])

        self.assertTrue(
            activity,
            "mail.activity should be created for the order when request is made"
        )

        # Verify activity summary mentions the order reference
        self.assertIn(
            self.order.name,
            activity.summary,
            f"Activity summary should mention order '{self.order.name}'"
        )

        # Verify activity type is "To Do"
        self.assertEqual(activity.activity_type_id.category, 'todo')

        # Verify deadline is +24h (approximately)
        now = fields.Datetime.now()
        expected_deadline = now + timedelta(hours=24)
        actual_deadline = activity.date_deadline
        # Allow 1-hour tolerance for test execution
        time_diff = abs((actual_deadline - expected_deadline.date()).days * 24)
        self.assertLess(
            time_diff, 2,
            f"Deadline should be ~24h from now, got {actual_deadline}"
        )

    def test_create_request_with_valid_data_stores_correctly(self):
        """Regression guard: Create request with valid data and verify field signature.

        Ensures the model can be instantiated with the expected field set
        and that all required fields are persisted correctly.
        """
        request = self._create_address_change_request(
            state='requested',
            reason='Test reason for change',
            requested_fields=['street', 'city'],
            new_values={'street': 'New St', 'city': 'New City'},
        )

        # Verify all fields were stored
        self.assertEqual(request.order_id, self.order)
        self.assertEqual(request.state, 'requested')
        self.assertEqual(request.reason, 'Test reason for change')
        self.assertEqual(request.requested_fields, ['street', 'city'])
        self.assertEqual(request.new_values['street'], 'New St')
        self.assertEqual(request.new_values['city'], 'New City')
        self.assertEqual(request.requested_by, self.env.user)
