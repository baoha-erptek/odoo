"""
Phase 2: ORM Unit Tests for label.status.option model (P1-LBL).

Tests verify business logic implementation:
- UNIQUE constraint on code is enforced via ORM (IntegrityError on duplicate)
- bus.bus emit on fulfillment label_status_id change with correct payload
- Write access is gated by BA-manager ACL (FR-017 16th confirmation)
- Address-change lock includes label_status_id field
- Migration helper correctly defaults NULL rows to 'cho_duyet'
- Kanban color is reachable via M2O relationship

Tests use TransactionCase with savepoint isolation and mocked bus.bus._sendone.
References: P1-LBL plan §7 (Two-Phase Testing layout), FR-017 write-defense pattern,
memory feedback_odoo19_test_gotchas.md (Odoo 19 gotchas).
"""

import logging
from unittest.mock import patch, ANY

import psycopg2
from psycopg2 import IntegrityError

from odoo import api
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestLabelStatusOrmBehavior(TransactionCase):
    """Phase 2: ORM tests for label.status.option and related fulfillment logic."""

    @classmethod
    def setUpClass(cls):
        """Set up test data: partners, products, orders, fulfillments, users."""
        super().setUpClass()
        # Disable mail tracking for test isolation
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test partners
        cls.buyer = cls.env['res.partner'].create({
            'name': 'Test Buyer',
            'email': 'buyer@example.com',
            'is_company': False,
        })

        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'is_storable': True,
            'list_price': 100.0,
        })

        # Create test carrier
        cls.carrier = cls.env.ref('multichannel_hub_core.shipping_carrier_usps')

        # Load seed records (assumed to be loaded by module install)
        cls.label_cho_duyet = cls.env.ref('multichannel_hub_core.label_status_cho_duyet')
        cls.label_vn_fulfilled = cls.env.ref('multichannel_hub_core.label_status_vn_fulfilled')

        # Create test users
        cls.salesman = cls.env['res.users'].create({
            'name': 'Test Salesman',
            'login': 'salesman@example.com',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
        })
        cls.ba_manager = cls.env['res.users'].create({
            'name': 'BA Manager',
            'login': 'ba_manager@example.com',
            'group_ids': [(6, 0, [cls.env.ref('multichannel_hub_core.group_ba_manager').id])],
        })

    def _create_order_with_fulfillment(self):
        """Factory: create a sale.order with auto-fulfillment."""
        order = self.env['sale.order'].create({
            'partner_id': self.buyer.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        order.action_confirm()
        # Fulfillment is auto-created by sale.order.create() override
        return order

    def test_create_with_duplicate_code_raises(self):
        """Test that duplicate code raises IntegrityError at DB level.

        Creates two records with the same code within a savepoint; second
        create should raise psycopg2.IntegrityError (wrapped by Odoo's ORM).
        """
        model = self.env['label.status.option']

        # First record succeeds
        record1 = model.create({
            'name': 'Test Label 1',
            'code': 'vn_fulfilled_dup_test',
            'color': 4,
            'sequence': 300,
            'bucket': 'done',
        })
        self.assertIsNotNone(record1.id)

        # Second record with same code should raise
        with self.assertRaises((IntegrityError, psycopg2.IntegrityError)):
            model.create({
                'name': 'Test Label 2 (dup)',
                'code': 'vn_fulfilled_dup_test',  # Duplicate
                'color': 4,
                'sequence': 301,
                'bucket': 'done',
            })

    def test_fulfillment_write_emits_bus_on_label_status_id_change(self):
        """Test that bus.bus emit occurs when fulfillment.label_status_id changes.

        Patches type(self.env['bus.bus'])._sendone and verifies the call
        includes channel 'multichannel_hub.fulfillment_update' and payload
        with label_status key as string code (NOT integer ID).
        Memory: must patch type(record), not record itself (raises AttributeError).
        """
        order = self._create_order_with_fulfillment()
        fulfillment = order.fulfillment_id

        # Patch bus.bus._sendone at the type level
        with patch.object(
            type(self.env['bus.bus']),
            '_sendone',
            return_value=None
        ) as mock_sendone:
            # Write label_status_id
            fulfillment.write({'label_status_id': self.label_cho_duyet.id})

            # Verify _sendone was called
            self.assertTrue(
                mock_sendone.called,
                "bus.bus._sendone should be called on label_status_id write"
            )

            # Extract call arguments
            call_args = mock_sendone.call_args
            self.assertIsNotNone(call_args, "Call args should exist")

            # Verify channel name
            channel = call_args[0][0] if call_args[0] else call_args.kwargs.get('channel')
            self.assertEqual(
                channel,
                'multichannel_hub.fulfillment_update',
                "Channel should be 'multichannel_hub.fulfillment_update'"
            )

            # Verify payload has label_status as code string (not ID)
            payload = call_args[0][2] if len(call_args[0]) > 2 else call_args.kwargs.get('payload')
            self.assertIsNotNone(payload, "Payload should be passed")
            self.assertIn(
                'label_status',
                payload,
                "Payload should include 'label_status' key"
            )
            self.assertEqual(
                payload['label_status'],
                'cho_duyet',
                f"Payload label_status should be code string 'cho_duyet', got {payload['label_status']}"
            )

    def test_fulfillment_write_blocked_for_non_ba_manager(self):
        """Test that non-BA-manager user cannot write label_status_id (FR-017 16th).

        Creates a fulfillment and attempts write with non-BA-manager user;
        should raise AccessError. With BA-manager user, same write succeeds.
        """
        order = self._create_order_with_fulfillment()
        fulfillment = order.fulfillment_id

        # Attempt write as salesman (should fail)
        with self.assertRaises(AccessError):
            fulfillment.with_user(self.salesman).write({
                'label_status_id': self.label_cho_duyet.id
            })

        # Attempt write as BA manager (should succeed)
        fulfillment.with_user(self.ba_manager).write({
            'label_status_id': self.label_cho_duyet.id
        })
        self.assertEqual(fulfillment.label_status_id.id, self.label_cho_duyet.id)

    def test_fulfillment_address_lock_includes_label_status_id(self):
        """Test that address-change lock includes label_status_id field.

        Creates an order with a pending address-change request; attempts
        to write label_status_id should raise UserError mentioning address lock.
        Write succeeds with context flag 'bypass_address_change_check'.
        """
        order = self._create_order_with_fulfillment()
        fulfillment = order.fulfillment_id

        # Create a pending address-change request
        self.env['etsy.address.change.request'].create({
            'order_id': order.id,
            'requested_fields': ['partner_shipping_id'],
            'new_values': {'partner_shipping_id': {'id': self.buyer.id}},
            'state': 'requested',
            'reason': 'Test address change',
        })

        # Verify order.has_pending_address_change is True
        self.assertTrue(
            order.has_pending_address_change,
            "Order should have pending address change"
        )

        # Attempt write without context flag — should raise UserError
        with self.assertRaises(UserError) as ctx:
            fulfillment.write({'label_status_id': self.label_cho_duyet.id})
        self.assertIn(
            'address',
            str(ctx.exception).lower(),
            "Error message should mention address lock"
        )

        # Write with bypass flag should succeed
        fulfillment.write({
            'label_status_id': self.label_cho_duyet.id,
        }, context={'bypass_address_change_check': True})
        self.assertEqual(fulfillment.label_status_id.id, self.label_cho_duyet.id)

    def test_migration_default_writes_cho_duyet_with_warning(self):
        """Test migration helper correctly defaults NULL rows to 'cho_duyet'.

        Creates fulfillments and force-sets label_status_id to NULL via raw SQL.
        Then calls migration helper; verifies rows are updated to cho_duyet ID
        and warning log is emitted with row count + IDs.
        """
        order = self._create_order_with_fulfillment()
        fulfillment = order.fulfillment_id

        # Force-set label_status_id to NULL (simulating legacy no-value state)
        self.env.cr.execute(
            "UPDATE sale_order_fulfillment SET label_status_id = NULL WHERE id = %s",
            (fulfillment.id,)
        )
        fulfillment.invalidate_recordset()

        # Verify it's NULL before migration
        self.assertFalse(fulfillment.label_status_id)

        # Import and call migration helper
        # Note: migration file path is placeholder (set by GREEN phase)
        from odoo.addons.multichannel_hub_core.migrations.post_label_status_default import migrate

        # Call migration
        with self.assertLogs('odoo.addons.multichannel_hub_core', level='WARNING') as log_ctx:
            migrate(self.env.cr, '19.0.1.0.29')

        # Verify record is updated to cho_duyet
        fulfillment.invalidate_recordset()
        self.assertEqual(
            fulfillment.label_status_id.id,
            self.label_cho_duyet.id,
            "Fulfillment should be defaulted to cho_duyet after migration"
        )

        # Verify warning log includes P1-LBL migration marker + audit list
        log_output = '\n'.join(log_ctx.output)
        self.assertIn(
            'P1-LBL migration',
            log_output,
            "Warning log should include 'P1-LBL migration' marker"
        )
        self.assertIn(
            str(fulfillment.id),
            log_output,
            "Warning log should include rewritten record ID in audit list"
        )

    def test_kanban_color_reachable_via_m2o(self):
        """Test that kanban color is reachable via label_status_id M2O.

        Creates fulfillment with label_status_id pointing to a record with
        a color value; verifies fulfillment.label_status_id.color is an integer.
        """
        order = self._create_order_with_fulfillment()
        fulfillment = order.fulfillment_id

        # Write a label with a color
        fulfillment.write({'label_status_id': self.label_vn_fulfilled.id})

        # Access color via the M2O relationship
        color = fulfillment.label_status_id.color
        self.assertIsInstance(
            color,
            int,
            f"Color should be integer, got {type(color)}"
        )
        self.assertEqual(
            color,
            4,
            "vn_fulfilled should have color 4 (blue)"
        )
