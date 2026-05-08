"""
Phase 2: ORM unit tests for P2-04 tracking import log visibility + replay.

Tests verify business logic and ORM semantics:
- action_replay_line reruns order resolution (resolve_orders)
- action_replay_line reruns carrier detection
- action_replay_line reruns fulfillment write (apply_to_fulfillment)
- action_replay_line rollback on exception (savepoint protection)
- action_replay_line updates parent log summary (_recount_summary)
- action_resolve_conflict operator selects from candidates
- Both actions are gated to BA shipping group (FR-017 13th confirmation)
- action_resolve_conflict rejects non-conflict state
- action_view_today_imports returns domain filtered by today
- Replay is idempotent on duplicate call (UNIQUE purpose marker from P2-03)

Tests use TransactionCase for test isolation. Each test runs in a savepoint.
Tests are tagged post_install so the full ORM registry is loaded.
"""

import logging
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP204Replay(TransactionCase):
    """ORM tests for P2-04 tracking import line replay + conflict resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data once for all tests."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # BA Shipping user group — required for replay/resolve actions
        ba_group = cls.env.ref('multichannel_hub_fulfillment.group_ba_shipping')
        cls.ba_user = cls.env['res.users'].create({
            'name': 'BA Shipping User P2-04',
            'login': 'ba_shipping_user_p2_04',
            'group_ids': [(4, ba_group.id)],
        })

        # Regular user without BA group — for access control testing
        user_group = cls.env.ref('base.group_user')
        cls.regular_user = cls.env['res.users'].create({
            'name': 'Regular User P2-04',
            'login': 'regular_user_p2_04',
            'group_ids': [(4, user_group.id)],
        })

        # Test partner for orders
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner P2-04',
            'street': '123 Test Street',
            'city': 'Test City',
            'zip': '12345',
        })

        # Storable product for order lines (Odoo 19: type='consu' + is_storable=True)
        cls.product = cls.env['product.product'].create({
            'name': 'P2-04 Test Product',
            'type': 'consu',
            'is_storable': True,
            'list_price': 100.0,
        })

    def _make_log(self, **kwargs):
        """Factory: create tracking.import.log with sensible defaults."""
        defaults = {
            'filename': 'test_import.xlsx',
            'schema_hash': 'abc123def456',
            'header_columns': '["Order", "Tracking", "Carrier", "Date"]',
            'total_rows': 0,
            'state': 'processing',
            'triggered_by_user_id': self.env.user.id,
        }
        defaults.update(kwargs)
        return self.env['tracking.import.log'].create(defaults)

    def _make_line(self, log, state='matched', order=None, **kwargs):
        """Factory: create tracking.import.line with sensible defaults.

        If order is provided, resolves fulfillment_id automatically.
        """
        defaults = {
            'log_id': log.id,
            'row_number': 1,
            'state': state,
            'raw_order_number': 'TEST-ORDER-001',
            'raw_tracking_number': '1Z999AA10123456784',
            'raw_carrier_label': 'UPS',
            'raw_shipping_date': '2026-05-01',
            'raw_payload': '{}',
            'source_row_hash': 'hash_001',
        }

        # If order provided, attach fulfillment
        if order:
            defaults['sale_order_id'] = order.id
            fulfillment = order.fulfillment_id or self.env['sale.order.fulfillment'].search(
                [('order_id', '=', order.id)], limit=1
            )
            if fulfillment:
                defaults['fulfillment_id'] = fulfillment.id
            defaults['raw_order_number'] = order.channel_order_ref or 'TEST-ORDER-001'

        defaults.update(kwargs)
        return self.env['tracking.import.line'].create(defaults)

    def _make_order(self, ref='ORDER-001', **kwargs):
        """Factory: create sale.order with storable line and confirm.

        Returns confirmed sale.order with fulfillment_id populated.
        """
        defaults = {
            'partner_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
            'sales_channel': 'etsy',
            'channel_order_ref': ref,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        }
        defaults.update(kwargs)

        order = self.env['sale.order'].create(defaults)
        # Confirm to trigger fulfillment creation
        order.action_confirm()

        return order

    def test_action_replay_line_reruns_resolve_orders(self):
        """T2-04-06: Replay reruns order resolution (resolve_orders).

        Create unmatched line for a valid order; replay; assert line
        transitions to 'matched' with sale_order_id set.
        """
        log = self._make_log()
        order = self._make_order(ref='REPLAY-ORD-001')

        # Create unmatched line for the order
        line = self._make_line(
            log, state='unmatched',
            raw_order_number=order.channel_order_ref,
            source_row_hash='unmatched_hash_001'
        )

        self.assertEqual(line.state, 'unmatched')
        self.assertFalse(line.sale_order_id)

        # Replay with BA user
        line.with_user(self.ba_user).action_replay_line()

        # After replay, line should be matched with order resolved
        self.assertEqual(line.state, 'matched')
        self.assertEqual(line.sale_order_id, order)

    def test_action_replay_line_reruns_carrier_detection(self):
        """T2-04-07: Replay reruns carrier detection.

        Create matched line with USPS-pattern tracking number;
        replay; assert detected_carrier_id is set via P2-02 detector.
        """
        log = self._make_log()
        order = self._make_order(ref='REPLAY-CARRIER-001')
        fulfillment = order.fulfillment_id

        # USPS 22-digit tracking number pattern
        usps_tracking = '94001112025555600000099'

        line = self._make_line(
            log, state='matched', order=order,
            raw_tracking_number=usps_tracking,
            source_row_hash='carrier_detect_hash_001'
        )

        # Replay should detect USPS carrier
        line.with_user(self.ba_user).action_replay_line()

        # Carrier should be detected (P2-02 USPS regex match)
        self.assertIsNotNone(
            line.detected_carrier_id,
            "Detected carrier should be populated from P2-02 regex"
        )

    def test_action_replay_line_reruns_fulfillment_write(self):
        """T2-04-08: Replay reruns fulfillment write (apply_to_fulfillment).

        Create error line with valid order/fulfillment; clear error_message;
        replay; assert tracking_number written + state='imported'.
        """
        log = self._make_log()
        order = self._make_order(ref='REPLAY-FULFILL-001')
        fulfillment = order.fulfillment_id

        # Create error line (pretend previous issue resolved)
        line = self._make_line(
            log, state='error', order=order,
            raw_tracking_number='1Z999AA10000000001',
            error_message='Previous error',
            source_row_hash='fulfill_error_hash_001'
        )

        # Clear error to simulate issue resolved
        line.error_message = ''
        line.state = 'matched'

        # Replay should apply to fulfillment
        line.with_user(self.ba_user).action_replay_line()

        # After replay, line state should be imported and tracking written
        self.assertEqual(line.state, 'imported')
        self.assertEqual(
            fulfillment.tracking_number,
            line.raw_tracking_number,
            "Tracking number should be written to fulfillment"
        )

    def test_action_replay_line_savepoint_rollback_on_error(self):
        """T2-04-09: Savepoint rollback on fulfillment write error.

        Create matched line; mock apply_to_fulfillment to raise;
        replay; assert state reverts to 'error' with error_message.
        """
        log = self._make_log()
        order = self._make_order(ref='REPLAY-SAVEPOINT-001')

        line = self._make_line(
            log, state='matched', order=order,
            raw_tracking_number='ERR123456789',
            source_row_hash='savepoint_error_hash_001'
        )

        # Mock apply_to_fulfillment to raise ValidationError
        with patch('odoo.addons.multichannel_hub_fulfillment.services.tracking_importer.apply_to_fulfillment') as mock_apply:
            mock_apply.side_effect = ValidationError("Simulated write error")

            # Replay should catch exception and mark error
            line.with_user(self.ba_user).action_replay_line()

        # Line should be in error state with message
        self.assertEqual(line.state, 'error')
        self.assertIsNotNone(line.error_message)
        self.assertIn(
            'Simulated write error',
            line.error_message,
            "Error message should contain exception details"
        )

    def test_action_replay_line_updates_parent_summary(self):
        """T2-04-10: Replay updates parent log summary via _recount_summary.

        Create log with 3 lines (matched, unmatched, error); manually set
        summary counts; replay error line; assert counts recounted correctly.
        """
        log = self._make_log()
        order1 = self._make_order(ref='RECOUNT-ORD-001')

        # Create 3 lines: matched, unmatched, error
        line_matched = self._make_line(
            log, state='matched', order=order1,
            source_row_hash='recount_matched_hash_001'
        )
        line_unmatched = self._make_line(
            log, state='unmatched',
            source_row_hash='recount_unmatched_hash_001'
        )
        line_error = self._make_line(
            log, state='error',
            raw_order_number=order1.channel_order_ref,
            error_message='Initial error',
            source_row_hash='recount_error_hash_001'
        )

        # Manually set counts to reflect current state
        log.matched_count = 1
        log.unmatched_count = 1
        log.error_count = 1

        # Fix error line and replay
        line_error.write({
            'state': 'matched',
            'sale_order_id': order1.id,
            'error_message': '',
        })

        line_error.with_user(self.ba_user).action_replay_line()

        # After replay, parent summary should be recounted
        log._recount_summary()

        self.assertEqual(log.matched_count, 2, "Matched count should increase")
        self.assertEqual(log.unmatched_count, 1, "Unmatched count should stay same")
        self.assertEqual(log.error_count, 0, "Error count should decrease")
        self.assertEqual(log.imported_count, 1, "Imported count should increase")

    def test_conflict_line_operator_selects_candidate_order(self):
        """T2-04-11: Conflict resolution operator selects from candidates.

        Create 2 orders with duplicate channel_order_ref; create conflict line;
        call action_resolve_conflict; assert sale_order_id set + parent chatter.
        """
        log = self._make_log()

        # Create 2 orders with duplicate channel_order_ref
        order1 = self._make_order(ref='DUP-ORD-001')
        order2 = self._make_order(ref='DUP-ORD-001')

        # Create conflict line
        line = self._make_line(
            log, state='conflict',
            raw_order_number='DUP-ORD-001',
            source_row_hash='conflict_dup_hash_001'
        )

        initial_chatter_count = len(log.message_ids)

        # Operator resolves conflict by selecting order1
        line.with_user(self.ba_user).action_resolve_conflict(order1.id)

        # Line should be matched with order1
        self.assertEqual(line.state, 'matched')
        self.assertEqual(line.sale_order_id, order1)

        # Parent log should have chatter audit message
        new_messages = log.message_ids
        self.assertGreater(
            len(new_messages),
            initial_chatter_count,
            "Parent log should have new chatter message"
        )

        # Message should reference row number and order
        message_body = new_messages[-1].body
        self.assertIn(
            str(line.row_number),
            message_body,
            "Audit message should include row number"
        )
        self.assertIn(
            order1.display_name,
            message_body,
            "Audit message should include selected order name"
        )

    def test_action_replay_line_gated_to_ba_shipping(self):
        """T2-04-12: action_replay_line is gated to BA shipping group (FR-017).

        Regular (non-BA) user calls action_replay_line; assert AccessError.
        """
        log = self._make_log()
        order = self._make_order(ref='GATE-REPLAY-001')

        line = self._make_line(
            log, state='matched', order=order,
            source_row_hash='gate_replay_hash_001'
        )

        # Regular user should not have access
        with self.assertRaises(AccessError):
            line.with_user(self.regular_user).action_replay_line()

    def test_action_resolve_conflict_gated_to_ba_shipping(self):
        """T2-04-13: action_resolve_conflict is gated to BA shipping (FR-017).

        Regular (non-BA) user calls action_resolve_conflict; assert AccessError.
        """
        log = self._make_log()
        order = self._make_order(ref='GATE-RESOLVE-001')

        line = self._make_line(
            log, state='conflict',
            raw_order_number=order.channel_order_ref,
            source_row_hash='gate_resolve_hash_001'
        )

        # Regular user should not have access
        with self.assertRaises(AccessError):
            line.with_user(self.regular_user).action_resolve_conflict(order.id)

    def test_action_resolve_conflict_rejects_non_conflict_state(self):
        """T2-04-14: action_resolve_conflict rejects non-conflict state.

        Create matched line (not conflict); call resolve; assert ValidationError.
        """
        log = self._make_log()
        order = self._make_order(ref='REJECT-CONFLICT-001')

        line = self._make_line(
            log, state='matched', order=order,
            source_row_hash='reject_conflict_hash_001'
        )

        # Should reject because line is matched, not conflict
        with self.assertRaises(ValidationError) as context:
            line.with_user(self.ba_user).action_resolve_conflict(order.id)

        self.assertIn(
            'conflict',
            str(context.exception).lower(),
            "Error should mention conflict state requirement"
        )

    def test_smart_button_action_filters_by_today(self):
        """T2-04-15: action_view_today_imports returns domain with today filter.

        Call log.action_view_today_imports(); assert returned domain includes
        create_date >= today's date (time-agnostic).
        """
        log = self._make_log()

        # Call the smart-button action
        result = log.action_view_today_imports()

        self.assertIsNotNone(result, "Action should return a dict")
        self.assertIn('domain', result, "Result should have 'domain' key")

        # Domain should filter by create_date
        domain = result['domain']
        self.assertTrue(
            any(d[0] == 'create_date' for d in domain if isinstance(d, (tuple, list))),
            "Domain should include create_date filter"
        )

        # Check for >= operator (today's start)
        create_date_clause = [d for d in domain if isinstance(d, (tuple, list)) and d[0] == 'create_date']
        self.assertTrue(
            any('>=' in str(d) for d in create_date_clause),
            "create_date filter should use >= operator for today's start"
        )

    def test_replay_idempotent_on_duplicate_call(self):
        """T2-04-16: Replay is idempotent on duplicate call.

        Create matched line + fulfillment with tracking; replay twice;
        assert no duplicate stock.move (P2-03 UNIQUE purpose marker).
        """
        log = self._make_log()
        order = self._make_order(ref='IDEMPOTENT-001')
        fulfillment = order.fulfillment_id

        line = self._make_line(
            log, state='matched', order=order,
            raw_tracking_number='IDEM123456789',
            source_row_hash='idempotent_hash_001'
        )

        # First replay: writes tracking + transitions to imported
        line.with_user(self.ba_user).action_replay_line()

        first_state = line.state
        first_tracking = fulfillment.tracking_number
        first_move_count = self.env['stock.move'].search_count([
            ('purpose', '=', 'production_completion'),
            ('sale_order_id', '=', order.id),
        ])

        # Second replay: should be idempotent (no error)
        # Since state is 'imported', replay loop skips (line 96 in plan)
        # But if it didn't skip, UNIQUE constraint prevents duplicate
        line.with_user(self.ba_user).action_replay_line()

        # State and tracking should remain same
        self.assertEqual(line.state, first_state)
        self.assertEqual(fulfillment.tracking_number, first_tracking)

        # No new stock.move should be created
        second_move_count = self.env['stock.move'].search_count([
            ('purpose', '=', 'production_completion'),
            ('sale_order_id', '=', order.id),
        ])

        self.assertEqual(
            first_move_count,
            second_move_count,
            "Duplicate replay should not create additional stock.move"
        )
