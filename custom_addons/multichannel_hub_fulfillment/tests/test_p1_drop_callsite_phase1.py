"""P1-DROP-CALLSITE Phase 1 — DB schema and orphan removal verification.

Tests verify:
- Orphan methods removed from sale.order:
  _gearment_push_should_fire, _enqueue_gearment_push, _cron_retry_stalled_gearment_pushes
- Orphan cron XML record ir_cron_gearment_retry_stalled removed
- purchase.order.button_confirm is overridden by multichannel_hub_fulfillment
- stock.picking._action_done is overridden by multichannel_hub_fulfillment

These tests run post_install to ensure the full module/registry is loaded.
"""
import inspect

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP1DropCallsiteOrphanRemoval(TransactionCase):
    """Phase 1 DB tests: orphan method/cron removal (P1-DROP-CALLSITE)."""

    # ======================================================================
    # Test 8: Orphan methods removed from sale.order
    # ======================================================================
    def test_orphan_methods_removed(self):
        """Test that the following private methods have been deleted from
        sale.order during the P1-DROP-CALLSITE refactor:
        - _gearment_push_should_fire
        - _enqueue_gearment_push
        - _cron_retry_stalled_gearment_pushes

        These were part of the old `_write_pipeline_state` hook implementation.
        Their logic is now incorporated into the PO button_confirm override
        and stock picking _action_done override.
        """
        sale_order_model = self.env['sale.order']

        self.assertFalse(hasattr(sale_order_model, '_gearment_push_should_fire'),
                         "sale.order._gearment_push_should_fire should be deleted")

        self.assertFalse(hasattr(sale_order_model, '_enqueue_gearment_push'),
                         "sale.order._enqueue_gearment_push should be deleted")

        self.assertFalse(hasattr(sale_order_model, '_cron_retry_stalled_gearment_pushes'),
                         "sale.order._cron_retry_stalled_gearment_pushes should be deleted")

    # ======================================================================
    # Test 9: Orphan cron XML record removed
    # ======================================================================
    def test_orphan_cron_xml_removed(self):
        """Test that the ir_cron_gearment_retry_stalled cron record has been
        removed from the data files.

        The cron was defined in data/ir_cron_gearment_retry.xml and was used
        by _cron_retry_stalled_gearment_pushes to retry stalled pushes. This
        logic is now replaced by PO re-confirm via button_confirm.
        """
        cron_record = self.env.ref(
            'multichannel_hub_fulfillment.ir_cron_gearment_retry_stalled',
            raise_if_not_found=False)

        self.assertFalse(cron_record,
                         "ir_cron_gearment_retry_stalled should be deleted from data")

    # ======================================================================
    # Test 10: purchase.order.button_confirm overridden by mhf
    # ======================================================================
    def test_purchase_order_action_confirm_overridden_by_mhf(self):
        """Test that purchase.order.button_confirm is overridden by the
        multichannel_hub_fulfillment module.

        This verifies that the new PO override exists and will be called
        on PO confirmation. The override handles Gearment dropship push logic.
        """
        po_model_class = type(self.env['purchase.order'])
        button_confirm_method = po_model_class.button_confirm

        # Check if the method comes from a multichannel_hub_fulfillment module
        method_module = inspect.getmodule(button_confirm_method)
        self.assertIsNotNone(method_module,
                             "button_confirm should have a module")

        method_module_name = method_module.__name__
        self.assertIn('multichannel_hub_fulfillment',
                      method_module_name,
                      f"purchase.order.button_confirm should be overridden by mhf; "
                      f"got module: {method_module_name}")

    # ======================================================================
    # Test 11: stock.picking._action_done overridden by mhf
    # ======================================================================
    def test_stock_picking_action_done_overridden_by_mhf(self):
        """Test that stock.picking._action_done is overridden by the
        multichannel_hub_fulfillment module.

        This verifies that the new stock picking override exists and will be
        called when pickings are completed. The override handles advancing
        the SO pipeline to 'shipped' for dropship pickings.
        """
        picking_model_class = type(self.env['stock.picking'])
        action_done_method = picking_model_class._action_done

        # Check if the method comes from a multichannel_hub_fulfillment module
        method_module = inspect.getmodule(action_done_method)
        self.assertIsNotNone(method_module,
                             "_action_done should have a module")

        method_module_name = method_module.__name__
        self.assertIn('multichannel_hub_fulfillment',
                      method_module_name,
                      f"stock.picking._action_done should be overridden by mhf; "
                      f"got module: {method_module_name}")
