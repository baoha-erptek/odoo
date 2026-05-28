"""Phase 2: ORM unit tests for multichannel.enquiry model.

Tests verify business logic through Odoo ORM:
- State machine transitions (new -> qualified -> converted/closed)
- Computed field (name) calculation and storage
- Constraint enforcement
- ACL and action-level RPC gating
- Partner matching and creation
- Close wizard workflow

Uses TransactionCase with @tagged('post_install', '-at_install') since
init() raw SQL (indexes) must have run first.
"""

import logging
import re
from datetime import datetime
from unittest import mock

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p3_lead_model')
class TestEnquiryPhase2(TransactionCase):
    """ORM and business logic tests for multichannel.enquiry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disable chatter tracking to speed up tests
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create shared test data
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Buyer',
            'email': 'buyer@example.com',
        })

        # Create etsy.shop for tests that need it.
        # `name` is the only required field on etsy.shop in this codebase.
        cls.etsy_shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop',
        })

        # Create users with specific groups
        # Salesman group: sales_team.group_sale_salesman
        cls.salesman_user = cls.env['res.users'].create({
            'login': 'salesman@example.com',
            'name': 'Salesman User',
            'email': 'salesman@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('sales_team.group_sale_salesman').id,
                cls.env.ref('base.group_user').id,
            ])],
        })

        # BA Lead group: multichannel_hub_core.group_ba_lead
        cls.ba_lead_user = cls.env['res.users'].create({
            'login': 'ba_lead@example.com',
            'name': 'BA Lead User',
            'email': 'ba_lead@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('multichannel_hub_core.group_ba_lead').id,
                cls.env.ref('base.group_user').id,
            ])],
        })

        # Manager group: sales_team.group_sale_manager
        cls.manager_user = cls.env['res.users'].create({
            'login': 'manager@example.com',
            'name': 'Sales Manager',
            'email': 'manager@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('sales_team.group_sale_manager').id,
                cls.env.ref('base.group_user').id,
            ])],
        })

        # User with no special group (access denied)
        cls.no_access_user = cls.env['res.users'].create({
            'login': 'no_access@example.com',
            'name': 'No Access User',
            'email': 'no_access@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
            ])],
        })

    def _create_enquiry(self, **kwargs):
        """Factory method to create test enquiry with sensible defaults."""
        defaults = {
            'name': 'Test Enquiry',
            'source': 'manual',
            'partner_email': 'test@example.com',
        }
        defaults.update(kwargs)
        return self.env['multichannel.enquiry'].create(defaults)

    def test_default_state_new(self):
        """Test that new enquiry defaults to 'new' state."""
        enq = self._create_enquiry()
        self.assertEqual(
            enq.state, 'new',
            "Default state must be 'new'"
        )

    def test_compute_name_format(self):
        """Test computed name format: 'Enquiry from {email} · {date}'."""
        enq = self._create_enquiry(
            partner_email='alice@example.com',
            name='placeholder',  # Will be overridden by compute
        )
        # Name is computed; check format
        match = re.match(
            r"Enquiry from alice@example\.com · \d{4}-\d{2}-\d{2}",
            enq.name
        )
        self.assertIsNotNone(
            match,
            f"Computed name '{enq.name}' must match "
            r"'Enquiry from alice@example.com · YYYY-MM-DD' format"
        )

    def test_qualify_advances_state(self):
        """Test action_qualify() transitions new -> qualified."""
        enq = self._create_enquiry(state='new')
        enq.action_qualify()
        self.assertEqual(
            enq.state, 'qualified',
            "action_qualify() must transition state from 'new' to 'qualified'"
        )
        # Verify chatter message posted
        messages = enq.message_ids.filtered(
            lambda m: m.body and m.body.strip()
        )
        self.assertTrue(
            messages,
            "action_qualify() must post a chatter message"
        )
        # At least one message should contain 'Qualified'
        self.assertTrue(
            any('Qualified' in msg.body for msg in messages),
            "Chatter message must mention 'Qualified'"
        )

    def test_qualify_from_non_new_raises(self):
        """Test action_qualify() from non-new state raises UserError."""
        enq = self._create_enquiry(state='qualified')
        with self.assertRaises(UserError):
            enq.action_qualify()

    def test_close_requires_reason(self):
        """Test action_close() requires a non-empty reason.

        Memory gotcha: assertRaises((UserError, ValidationError)) tuple
        breaks Odoo's TransactionCase._assertRaises issubclass check —
        use savepoint + manual try/except instead.
        """
        enq = self._create_enquiry(state='new')
        raised = False
        try:
            with self.cr.savepoint():
                enq.action_close(reason='')
        except (UserError, ValidationError):
            raised = True
        self.assertTrue(
            raised,
            "action_close('') must raise UserError or ValidationError"
        )

        # Valid reason should work
        enq.action_close(reason='spam')
        self.assertEqual(enq.state, 'closed')
        self.assertEqual(enq.closed_reason, 'spam')

    def test_convert_creates_draft_order(self):
        """Test action_convert_to_quote() creates sale.order.

        - Creates draft sale.order with partner_id and origin=enq.name
        - Enquiry state -> 'converted', converted_at set, converted_order_id set
        - Returns ir.actions.act_window
        """
        enq = self._create_enquiry(
            state='new',
            partner_id=self.partner.id,
        )
        original_name = enq.name

        action_result = enq.action_convert_to_quote()

        # Check return is an action
        self.assertIsNotNone(action_result)
        self.assertEqual(action_result.get('type'), 'ir.actions.act_window')

        # Check enquiry state updated
        self.assertEqual(
            enq.state, 'converted',
            "Enquiry state must transition to 'converted'"
        )
        self.assertTrue(
            enq.converted_at,
            "converted_at must be set"
        )
        self.assertIsNotNone(
            enq.converted_order_id,
            "converted_order_id must be set"
        )

        # Check order created
        order = enq.converted_order_id
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.partner_id, self.partner)
        self.assertEqual(order.origin, original_name)

        # Check chatter messages on both enquiry and order
        enq_messages = enq.message_ids.filtered(
            lambda m: m.body and m.body.strip()
        )
        self.assertTrue(enq_messages)
        self.assertTrue(
            any('Converted' in msg.body for msg in enq_messages),
            "Enquiry chatter must contain 'Converted'"
        )

    def test_backwards_transition_blocked_via_write(self):
        """Test direct write({'state': 'new'}) from 'qualified' raises."""
        enq = self._create_enquiry(state='qualified')
        with self.assertRaises(ValidationError):
            enq.write({'state': 'new'})

    def test_backwards_transition_blocked_via_action(self):
        """Sanity test: no action_unqualify exists."""
        enq = self._create_enquiry(state='qualified')
        self.assertFalse(
            hasattr(enq, 'action_unqualify'),
            "No action_unqualify() method should exist"
        )

    def test_terminal_states_immutable(self):
        """Test 'closed' and 'converted' states block all transitions."""
        # From closed
        closed_enq = self._create_enquiry(
            state='closed',
            closed_reason='spam',
        )
        with self.assertRaises(ValidationError):
            closed_enq.write({'state': 'new'})

        # From converted
        conv_enq = self._create_enquiry(state='new')
        conv_enq.action_convert_to_quote()
        with self.assertRaises(ValidationError):
            conv_enq.write({'state': 'qualified'})

    def test_convert_from_qualified_state_creates_order(self):
        """Test action_convert_to_quote() from 'qualified' state also works."""
        enq = self._create_enquiry(
            state='qualified',
            partner_id=self.partner.id,
        )
        original_name = enq.name

        action_result = enq.action_convert_to_quote()

        # Check return is an action
        self.assertIsNotNone(action_result)
        self.assertEqual(action_result.get('type'), 'ir.actions.act_window')

        # Check enquiry state updated
        self.assertEqual(
            enq.state, 'converted',
            "Enquiry state must transition to 'converted' from 'qualified'"
        )
        self.assertTrue(
            enq.converted_at,
            "converted_at must be set"
        )
        self.assertIsNotNone(
            enq.converted_order_id,
            "converted_order_id must be set"
        )

        # Check order created
        order = enq.converted_order_id
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.partner_id, self.partner)
        self.assertEqual(order.origin, original_name)

    def test_convert_idempotent_on_reinvoke(self):
        """Test re-invocation when state='converted' returns existing order.

        Idempotency (T064): call action twice on same enquiry; second call
        returns the existing order's act_window action with res_id == first_order.id;
        assert exactly one sale.order exists with origin=enq.name AND
        partner_id=enq.partner_id; assert no second chatter message added.
        """
        # Setup: create enquiry and convert once
        enq = self._create_enquiry(
            state='new',
            partner_id=self.partner.id,
        )
        first_action = enq.action_convert_to_quote()
        first_order_id = enq.converted_order_id.id

        # Count chatter messages after first convert
        first_msg_count = len(enq.message_ids)

        # Re-invoke action (idempotency test)
        second_action = enq.action_convert_to_quote()

        # Verify same order is returned
        self.assertEqual(
            second_action['res_id'], first_order_id,
            "Second invocation should return same order"
        )
        self.assertEqual(
            enq.converted_order_id.id, first_order_id,
            "converted_order_id should not change"
        )

        # Verify no duplicate sale.order created
        all_orders = self.env['sale.order'].search([
            ('origin', '=', enq.name),
            ('partner_id', '=', self.partner.id),
        ])
        self.assertEqual(
            len(all_orders), 1,
            "Only one sale.order should exist with same origin and partner"
        )

        # Verify no new chatter message posted on second invocation
        second_msg_count = len(enq.message_ids)
        self.assertEqual(
            first_msg_count, second_msg_count,
            "No new chatter message should be posted on idempotent re-call"
        )

    def test_convert_from_closed_raises_user_error(self):
        """Test action_convert_to_quote() from 'closed' state raises UserError.

        Pre-condition (T065): calling on state='closed' enquiry raises UserError.
        Verify converted_order_id stays empty and no sale.order created.
        """
        enq = self._create_enquiry(
            state='closed',
            closed_reason='spam',
        )

        with self.assertRaises(UserError):
            enq.action_convert_to_quote()

        # Verify no order created
        self.assertFalse(
            enq.converted_order_id,
            "converted_order_id should remain empty after error"
        )
        self.assertFalse(
            enq.converted_at,
            "converted_at should remain empty after error"
        )

        # Verify no sale.order created with enquiry name as origin
        all_orders = self.env['sale.order'].search([
            ('origin', '=', enq.name),
        ])
        self.assertEqual(
            len(all_orders), 0,
            "No sale.order should be created when conversion fails"
        )

    def test_convert_calls_match_or_create_partner_when_partner_id_empty(self):
        """Test action_convert_to_quote() calls _match_or_create_partner.

        When enquiry has no partner_id but has partner_email, the action
        should call _match_or_create_partner() which creates/matches a partner,
        then creates the order with that partner.
        """
        enq = self._create_enquiry(
            state='new',
            partner_id=False,
            partner_email='newbuyer-p3convert@example.com',
        )

        action = enq.action_convert_to_quote()

        # Verify partner was created/matched
        self.assertIsNotNone(
            enq.partner_id,
            "partner_id should be populated by _match_or_create_partner()"
        )
        self.assertEqual(
            enq.partner_id.email_normalized,
            'newbuyer-p3convert@example.com',
            "Partner email should match enquiry email"
        )

        # Verify order was created with the matched/created partner
        order = enq.converted_order_id
        self.assertIsNotNone(order)
        self.assertEqual(
            order.partner_id.id, enq.partner_id.id,
            "Order partner must match enquiry partner"
        )

    def test_convert_chatter_xss_escaped_for_partner_email_with_html(self):
        """Test chatter is safe when partner_email contains HTML.

        Even if partner_email is updated elsewhere with HTML, the convert
        action's chatter messages should not render raw script tags.
        """
        enq = self._create_enquiry(
            state='new',
            partner_id=self.partner.id,
            partner_email='<script>alert("xss")</script>@example.com',
        )

        # Convert the enquiry
        action = enq.action_convert_to_quote()

        # Verify chatter body on the enquiry is safe
        enq_messages = enq.message_ids.filtered(
            lambda m: m.body and m.body.strip()
        )
        for msg in enq_messages:
            self.assertNotIn(
                '<script>',
                msg.body,
                "Enquiry chatter body must escape HTML"
            )

        # Verify chatter body on the order is safe
        order = enq.converted_order_id
        order_messages = order.message_ids.filtered(
            lambda m: m.body and m.body.strip()
        )
        for msg in order_messages:
            self.assertNotIn(
                '<script>',
                msg.body,
                "Order chatter body must escape HTML"
            )

    def test_match_partner_existing(self):
        """Test _match_or_create_partner() finds existing partner by email."""
        # Create existing partner
        existing = self.env['res.partner'].create({
            'name': 'Bob Smith',
            'email': 'Bob@Example.com',  # Case differs
            'is_etsy_customer': True,
        })

        enq = self._create_enquiry(
            partner_email='bob@example.com',  # Lowercase
        )
        # Manual call to helper (not part of public API, but testable)
        enq._match_or_create_partner()

        self.assertEqual(
            enq.partner_id, existing,
            "email_normalize() should match case-insensitive"
        )

    def test_match_partner_creates_when_absent(self):
        """Test _match_or_create_partner() creates partner if missing."""
        enq = self._create_enquiry(partner_email='novel@example.com')
        enq._match_or_create_partner()

        self.assertTrue(enq.partner_id)
        new_partner = enq.partner_id
        self.assertEqual(new_partner.email_normalized, 'novel@example.com')
        self.assertTrue(new_partner.is_etsy_customer)

    def test_match_partner_blank_email(self):
        """Test _match_or_create_partner() handles blank email safely."""
        enq = self._create_enquiry(partner_email='')
        partner_count_before = self.env['res.partner'].search_count([])

        enq._match_or_create_partner()

        # No new partner should be created
        partner_count_after = self.env['res.partner'].search_count([])
        self.assertEqual(
            partner_count_before, partner_count_after,
            "Blank email should not create a junk partner"
        )
        self.assertFalse(enq.partner_id)

    def test_acl_salesman_can_create(self):
        """Test salesman has create+write ACL."""
        enq = self.env['multichannel.enquiry'].with_user(
            self.salesman_user
        ).create({
            'name': 'Salesman Enquiry',
            'source': 'manual',
            'partner_email': 'sales@example.com',
        })
        self.assertTrue(enq.id)

        # Salesman can write
        self.env['multichannel.enquiry'].with_user(
            self.salesman_user
        ).browse(enq.id).write({'partner_email': 'updated@example.com'})
        enq.invalidate_recordset()
        self.assertEqual(enq.partner_email, 'updated@example.com')

        # Salesman cannot unlink (no unlink ACL)
        with self.assertRaises(AccessError):
            with self.cr.savepoint():
                self.env['multichannel.enquiry'].with_user(
                    self.salesman_user
                ).browse(enq.id).unlink()

    def test_acl_ba_lead_can_unlink(self):
        """Test BA Lead has full CRUD including unlink."""
        enq = self.env['multichannel.enquiry'].with_user(
            self.ba_lead_user
        ).create({
            'name': 'BA Enquiry',
            'source': 'manual',
            'partner_email': 'ba@example.com',
        })
        enq_id = enq.id

        # BA Lead can unlink
        self.env['multichannel.enquiry'].with_user(
            self.ba_lead_user
        ).browse(enq_id).unlink()

        # Verify deleted
        remaining = self.env['multichannel.enquiry'].search(
            [('id', '=', enq_id)]
        )
        self.assertEqual(len(remaining), 0)

    def test_action_qualify_rpc_gated_for_no_group(self):
        """Test action_qualify() RPC is gated by _check_sale_user_or_raise()."""
        enq = self._create_enquiry(state='new')

        # User without group_sale_salesman cannot call action
        with self.assertRaises(UserError):
            enq.with_user(self.no_access_user).action_qualify()

    def test_action_convert_to_quote_rpc_gated_for_no_group(self):
        """Test action_convert_to_quote() RPC is gated by _check_sale_user_or_raise().

        FR-017 12th confirmation: action-level RPC gate must reject users
        without group_sale_salesman even when ACL would otherwise allow read.
        """
        enq = self._create_enquiry(state='new', partner_id=self.partner.id)

        # User without group_sale_salesman cannot call action via RPC
        with self.assertRaises(UserError):
            enq.with_user(self.no_access_user).action_convert_to_quote()

        # State and converted_order_id remain unchanged
        enq.invalidate_recordset()
        self.assertEqual(enq.state, 'new')
        self.assertFalse(enq.converted_order_id)

    def test_partial_unique_enforced(self):
        """Test partial UNIQUE(etsy_shop_id, etsy_conversation_id) constraint.

        Two rows with same (shop, conversation_id) should fail.
        But two rows with conversation_id=NULL should succeed (partial).
        """
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger

        # Create first enquiry with conversation_id
        enq1 = self._create_enquiry(
            etsy_shop_id=self.etsy_shop.id,
            etsy_conversation_id='CONV_001',
        )

        # Duplicate (shop, conversation_id) should fail
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self._create_enquiry(
                    etsy_shop_id=self.etsy_shop.id,
                    etsy_conversation_id='CONV_001',
                )

        # Two rows with NULL conversation_id should succeed (partial index)
        enq2 = self._create_enquiry(
            etsy_shop_id=self.etsy_shop.id,
            etsy_conversation_id=None,
        )
        enq3 = self._create_enquiry(
            etsy_shop_id=self.etsy_shop.id,
            etsy_conversation_id=None,
        )
        self.assertTrue(enq2.id)
        self.assertTrue(enq3.id)

    def test_dedupe_target_enquiry_fk_intact(self):
        """Sanity test: etsy.message.dedupe target_enquiry_id FK exists.

        This FK is declared in etsy.message.dedupe (P3-LEAD-DEDUPE).
        Unlink enquiry -> dedupe row's target_enquiry_id becomes NULL.
        """
        enq = self._create_enquiry()
        enq_id = enq.id

        # Create a dedupe record pointing to this enquiry
        dedupe = self.env['etsy.message.dedupe'].create({
            'etsy_shop_id': self.etsy_shop.id,
            'etsy_message_id': 'MSG_001',
            'channel': 'api',
            'posted_at': datetime.now(),
            'target_enquiry_id': enq.id,
        })

        self.assertEqual(dedupe.target_enquiry_id.id, enq_id)

        # Unlink enquiry
        enq.unlink()

        # Dedupe target_enquiry_id should be NULL (ondelete='set null')
        dedupe.invalidate_recordset()
        self.assertFalse(dedupe.target_enquiry_id)


@tagged('post_install', '-at_install', 'p3_lead_model')
class TestEnquiryCloseWizard(TransactionCase):
    """Tests for multichannel.enquiry.close.wizard workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test data
        cls.partner = cls.env['res.partner'].create({
            'name': 'Buyer',
            'email': 'buyer@example.com',
        })

    def test_wizard_close_flow(self):
        """Test close wizard creates enquiry with reason and notes.

        Creates enquiry in 'new' state -> instantiate wizard with
        reason='spam' and notes='dup of #123' -> wizard.action_close() ->
        enquiry state='closed', closed_reason='spam', chatter message
        with notes in body.
        """
        # Create enquiry
        enq = self.env['multichannel.enquiry'].create({
            'name': 'Enquiry to Close',
            'source': 'manual',
            'partner_email': 'closing@example.com',
            'state': 'new',
            'partner_id': self.partner.id,
        })

        # Create close wizard
        wizard = self.env['multichannel.enquiry.close.wizard'].create({
            'enquiry_id': enq.id,
            'reason': 'spam',
            'notes': 'Duplicate of #123',
        })

        # Execute action_close on wizard
        wizard.action_close()

        # Verify enquiry updated
        enq.invalidate_recordset()
        self.assertEqual(enq.state, 'closed')
        self.assertEqual(enq.closed_reason, 'spam')

        # Verify chatter message contains notes
        messages = enq.message_ids.filtered(
            lambda m: m.body and m.body.strip()
        )
        self.assertTrue(messages)
        self.assertTrue(
            any('Duplicate of #123' in msg.body for msg in messages),
            "Wizard notes should be included in chatter message body"
        )
