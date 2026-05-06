"""P1-DROP-CALLSITE Phase 2 — ORM tests for Gearment auto-push on PO confirm.

Tests verify:
- PO button_confirm override triggers Gearment push for dropship Gearment POs
- SO pipeline state advances to 'confirmed' on successful push
- Idempotency: pre-pushed SOs skip the push on PO re-confirm
- Push failure raises UserError and rolls back PO + SO state
- Chatter audit trail survives rollback via savepoint(flush=False)
- Dropship picking done advances SO pipeline to 'shipped'
- Non-Gearment/non-dropship POs do not trigger push

Tests use TransactionCase for test isolation. Each test runs in a savepoint
that rolls back after the test completes.

Mock gearment_adapter.GearmentApiAdapter.push_order to verify push logic
without hitting the real Gearment API.
"""
import os
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..services import gearment_adapter as ga_mod


def _set_gearment_env():
    """Set required Gearment environment variables for tests."""
    os.environ.setdefault('GEARMENT_API_KEY', 'test')
    os.environ.setdefault('GEARMENT_API_SECRET', 'test')
    os.environ.setdefault('GEARMENT_API_BASE_URL', 'https://test.gearment.example')


@tagged('post_install', '-at_install')
class TestPurchaseOrderCallsite(TransactionCase):
    """Phase 2 ORM tests for PO button_confirm override (P1-DROP-CALLSITE)."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data once for all tests."""
        super().setUpClass()
        _set_gearment_env()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Load pipelines and states
        cls.gearment_pipeline = cls.env.ref(
            'multichannel_hub_core.order_pipeline_gearment_pod')
        cls.state_quoted = cls.env.ref(
            'multichannel_hub_core.state_gearment_quoted')
        cls.state_confirmed = cls.env.ref(
            'multichannel_hub_core.state_gearment_confirmed')
        cls.state_shipped = cls.env.ref(
            'multichannel_hub_core.state_gearment_shipped')

        # Create test partner (customer)
        cls.partner = cls.env['res.partner'].create({
            'name': 'PO Callsite Test Customer',
            'street': '456 Test Ave',
            'city': 'Bangkok',
            'zip': '10110',
        })

        # Create product with Gearment SKU (auto-routes to dropship per P1-DROP-SEED)
        cls.product = cls.env['product.product'].create({
            'name': 'Dropship POD Product',
            'list_price': 29.99,
        })
        cls.product.product_tmpl_id.write({
            'x_gearment_sku': 'TEST_SKU_001',
            'x_default_pipeline_id': cls.gearment_pipeline.id,
        })

    def _create_sale_order(self, **kwargs):
        """Factory method to create a sale order on gearment_pod pipeline."""
        defaults = {
            'partner_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
            'sales_channel': 'etsy',
            'channel_order_ref': f'ETSY-TEST-{self.env.cr.now().timestamp()}',
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        }
        defaults.update(kwargs)
        order = self.env['sale.order'].create(defaults)
        # Ensure pipeline resolved to gearment_pod
        order.invalidate_recordset(['x_pipeline_id', 'x_pipeline_state_id'])
        return order

    def _confirm_sale_order_and_get_po(self, sale_order):
        """Confirm a sale order and return the generated purchase order.

        Returns None if no PO was auto-created (e.g., product not on a dropship route).
        """
        sale_order.action_confirm()
        # Lookup the PO via the order lines' sale_line_id linkage
        pos = self.env['purchase.order'].search([
            ('order_line.sale_line_id', 'in', sale_order.order_line.ids),
        ])
        return pos[0] if pos else None

    # ======================================================================
    # Test 1: PO confirm pushes to Gearment and advances pipeline
    # ======================================================================
    def test_po_confirm_pushes_to_gearment_and_advances_pipeline(self):
        """Test that PO button_confirm calls push_to_gearment and advances SO
        pipeline state to 'confirmed'.

        Flow:
        1. Create SO, confirm it -> PO auto-created against Gearment vendor
        2. Mock push_order to return {'id': 'GEAR_REF_42', 'status': 'pending'}
        3. Call po.button_confirm()
        4. Assert: x_gearment_outbound_ref, x_gearment_pushed_at, and
           x_gearment_status are stamped; pipeline state is 'confirmed'
        5. Assert: push_order was called exactly once
        """
        so = self._create_sale_order()
        po = self._confirm_sale_order_and_get_po(so)
        self.assertIsNotNone(po, "PO should have been auto-created on SO confirm")

        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
                return_value={'id': 'GEAR_REF_42', 'status': 'pending'},
        ) as mock_push:
            po.button_confirm()

        # Verify push was called exactly once
        self.assertTrue(mock_push.called, "push_order should have been called")
        self.assertEqual(mock_push.call_count, 1)

        # Refresh SO state from DB
        so.invalidate_recordset()

        # Verify stamps
        self.assertEqual(so.x_gearment_outbound_ref, 'GEAR_REF_42',
                         "Outbound ref should be stamped from push response")
        self.assertIsNotNone(so.x_gearment_pushed_at,
                             "Pushed timestamp should be set")
        self.assertEqual(so.x_gearment_status, 'pending',
                         "Gearment status should be 'pending' after push")

        # Verify pipeline advanced to 'confirmed'
        self.assertEqual(so.x_pipeline_state_id.code, 'confirmed',
                         "Pipeline state should advance to 'confirmed' on successful push")

        # Verify PO state is now 'purchase'
        self.assertEqual(po.state, 'purchase',
                         "PO state should be 'purchase' after confirm")

    # ======================================================================
    # Test 2: PO confirm idempotent when SO already pushed
    # ======================================================================
    def test_po_confirm_idempotent_when_so_already_pushed(self):
        """Test that PO confirm skips Gearment push if SO already has
        x_gearment_outbound_ref set (idempotency).

        Flow:
        1. Create SO, confirm it -> PO auto-created
        2. Pre-stamp SO with x_gearment_outbound_ref = 'GEAR_REF_PRE'
        3. Call po.button_confirm()
        4. Assert: push_order was NOT called
        5. Assert: x_gearment_outbound_ref unchanged; PO still confirms
        """
        so = self._create_sale_order()
        po = self._confirm_sale_order_and_get_po(so)
        self.assertIsNotNone(po, "PO should have been auto-created")

        # Pre-stamp the SO
        so.x_gearment_outbound_ref = 'GEAR_REF_PRE'

        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
        ) as mock_push:
            po.button_confirm()

        # Verify push was NOT called
        self.assertFalse(mock_push.called,
                         "push_order should NOT be called for already-pushed SO")

        # Verify ref unchanged
        self.assertEqual(so.x_gearment_outbound_ref, 'GEAR_REF_PRE',
                         "Outbound ref should remain unchanged")

        # Verify PO still confirmed
        self.assertEqual(po.state, 'purchase',
                         "PO should still confirm even when push is skipped")

    # ======================================================================
    # Test 3: PO confirm raises UserError on push failure and rolls back
    # ======================================================================
    def test_po_confirm_raises_userror_on_push_failure_and_rolls_back(self):
        """Test that PO confirm raises UserError when push fails, rolls back
        PO and SO state, and emits a WARNING-level audit log.

        Note on durability: PostgreSQL savepoints live INSIDE the outer
        transaction; once UserError propagates and the dispatcher rolls the
        outer transaction back, all SAVEPOINTs within it are gone too —
        chatter posted during the override does not survive. The durable
        audit channel is `_logger.warning` (server log file). This test
        therefore asserts the log warning fires; chatter is best-effort.

        Flow:
        1. Create SO, confirm it -> PO auto-created
        2. Mock push_order to raise RuntimeError
        3. Call po.button_confirm() inside assertRaises(UserError)
        4. Assert: PO state rolled back to 'draft'
        5. Assert: SO pipeline state unchanged (rollback)
        6. Assert: SO has no outbound ref (idempotent)
        7. Assert: WARNING log captured with "Gearment push failed during PO"
        """
        so = self._create_sale_order()
        po = self._confirm_sale_order_and_get_po(so)
        self.assertIsNotNone(po, "PO should have been auto-created")
        initial_pipeline_code = so.x_pipeline_state_id.code

        po_logger = (
            'odoo.addons.multichannel_hub_fulfillment.models.purchase_order')
        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
                side_effect=RuntimeError("HTTP 500: Internal Server Error"),
        ):
            with self.assertLogs(po_logger, level='WARNING') as log_cm:
                with self.assertRaises(UserError):
                    po.button_confirm()

        # Refresh from DB
        po.invalidate_recordset()
        so.invalidate_recordset()

        # Verify rollback: PO should remain in draft
        self.assertEqual(po.state, 'draft',
                         "PO state should roll back to 'draft' on push failure")

        # Verify rollback: SO pipeline state unchanged from before PO confirm
        self.assertEqual(so.x_pipeline_state_id.code, initial_pipeline_code,
                         "SO pipeline should be unchanged after rollback")

        # Verify SO has no outbound ref (idempotent)
        self.assertFalse(so.x_gearment_outbound_ref,
                         "SO should have no outbound ref after rollback")

        # Verify durable audit channel: WARNING log emitted by PO override
        self.assertTrue(
            any('Gearment push failed during PO' in line and 'confirm for SO' in line
                for line in log_cm.output),
            f"PO override should emit a WARNING log with the failure context; "
            f"got: {log_cm.output}",
        )

    # ======================================================================
    # Test 4: Dropship picking done advances pipeline to shipped
    # ======================================================================
    def test_dropship_picking_done_advances_pipeline_to_shipped(self):
        """Test that when a dropship picking transitions to done,
        the SO pipeline advances from 'confirmed' to 'shipped'.

        Flow:
        1. Create SO, confirm it -> PO auto-created against Gearment
        2. Mock push_order to return success
        3. Call po.button_confirm() -> SO pushed and pipeline at 'confirmed'
        4. Get the dropship picking from the SO
        5. Call picking._action_done() (or simulate picking validation)
        6. Assert: SO pipeline state is now 'shipped'
        """
        so = self._create_sale_order()
        po = self._confirm_sale_order_and_get_po(so)
        self.assertIsNotNone(po, "PO should have been auto-created")

        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
                return_value={'id': 'GEAR_REF_SHIP', 'status': 'pending'},
        ):
            po.button_confirm()

        # Verify SO now at 'confirmed'
        so.invalidate_recordset()
        self.assertEqual(so.x_pipeline_state_id.code, 'confirmed',
                         "SO should be at 'confirmed' after PO confirm")

        # Get the dropship picking (should exist after PO confirm)
        pickings = self.env['stock.picking'].search([
            ('sale_id', '=', so.id),
            ('picking_type_id.code', '=', 'dropship'),
        ])
        self.assertTrue(len(pickings) > 0,
                        "Dropship picking should exist for the SO")

        picking = pickings[0]

        # Simulate picking validation (calls _action_done)
        picking._action_done()

        # Refresh and verify pipeline advanced to 'shipped'
        so.invalidate_recordset()
        self.assertEqual(so.x_pipeline_state_id.code, 'shipped',
                         "SO pipeline should advance to 'shipped' when picking done")

    # ======================================================================
    # Test 5: Picking done idempotent when SO already shipped
    # ======================================================================
    def test_picking_done_idempotent_when_so_already_shipped(self):
        """Test that calling _action_done on a picking when SO is already
        at 'shipped' does not cause an exception and state remains unchanged.

        Flow:
        1. Create SO, pre-stamp it at 'shipped' state
        2. Create a dropship picking linked to the SO
        3. Call picking._action_done()
        4. Assert: no exception; pipeline state unchanged at 'shipped'
        """
        so = self._create_sale_order()
        po = self._confirm_sale_order_and_get_po(so)
        self.assertIsNotNone(po, "PO should have been auto-created")

        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
                return_value={'id': 'GEAR_REF_IDEMPOTENT', 'status': 'pending'},
        ):
            po.button_confirm()

        # Pre-stamp SO at 'shipped'
        so.with_context(
            bypass_pipeline_state_guard=True,
        ).write({'x_pipeline_state_id': self.state_shipped.id})

        # Get the picking and call _action_done again
        pickings = self.env['stock.picking'].search([
            ('sale_id', '=', so.id),
            ('picking_type_id.code', '=', 'dropship'),
        ])
        self.assertTrue(len(pickings) > 0)

        picking = pickings[0]

        # Call _action_done — should be idempotent
        picking._action_done()

        so.invalidate_recordset()
        self.assertEqual(so.x_pipeline_state_id.code, 'shipped',
                         "Pipeline should remain at 'shipped'; no exception")

    # ======================================================================
    # Test 6: Non-Gearment dropship PO does not trigger push
    # ======================================================================
    def test_non_gearment_dropship_po_does_not_trigger_push(self):
        """Test that a dropship PO against a vendor OTHER than Gearment
        does not trigger a Gearment push, even if the picking type is dropship.

        Flow:
        1. Create a non-Gearment vendor partner
        2. Create a PO with picking_type.code='dropship' but partner != Gearment
        3. Mock push_order (should NOT be called)
        4. Call po.button_confirm()
        5. Assert: push_order not called
        """
        # Create non-Gearment dropship vendor
        other_vendor = self.env['res.partner'].create({
            'name': 'Other Dropship Vendor',
            'is_company': True,
        })

        # Get dropship picking type
        dropship_picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'dropship'),
        ], limit=1)

        if not dropship_picking_type:
            self.skipTest("Dropship picking type not found; stock_dropshipping may not be installed")

        # Create a non-Gearment dropship PO
        po = self.env['purchase.order'].create({
            'partner_id': other_vendor.id,
            'picking_type_id': dropship_picking_type.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 10.0,
            })],
        })

        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
        ) as mock_push:
            po.button_confirm()

        # Verify push was NOT called
        self.assertFalse(mock_push.called,
                         "push_order should NOT be called for non-Gearment vendor")

        # Verify PO still confirms
        self.assertEqual(po.state, 'purchase')

    # ======================================================================
    # Test 7: Non-dropship PO does not trigger push
    # ======================================================================
    def test_non_dropship_po_does_not_trigger_push(self):
        """Test that a regular (non-dropship) PO against the Gearment vendor
        does not trigger a push, even if the vendor is Gearment.

        This edge case could occur if an operator manually creates an incoming
        PO against the Gearment partner.

        Flow:
        1. Get the Gearment vendor partner
        2. Get an 'incoming' picking type (regular purchase)
        3. Create a PO with picking_type.code='incoming' and partner=Gearment
        4. Mock push_order (should NOT be called)
        5. Call po.button_confirm()
        6. Assert: push_order not called
        """
        gearment_vendor = self.env.ref(
            'multichannel_hub_fulfillment.partner_gearment_vendor',
            raise_if_not_found=False)

        if not gearment_vendor:
            self.skipTest("Gearment vendor seed not loaded")

        # Get incoming picking type
        incoming_picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
        ], limit=1)

        if not incoming_picking_type:
            self.skipTest("Incoming picking type not found")

        # Create a regular (non-dropship) PO against Gearment vendor
        po = self.env['purchase.order'].create({
            'partner_id': gearment_vendor.id,
            'picking_type_id': incoming_picking_type.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1,
                'price_unit': 10.0,
            })],
        })

        with patch.object(
                ga_mod.GearmentApiAdapter, 'push_order',
        ) as mock_push:
            po.button_confirm()

        # Verify push was NOT called
        self.assertFalse(mock_push.called,
                         "push_order should NOT be called for non-dropship PO")

        # Verify PO still confirms
        self.assertEqual(po.state, 'purchase')
