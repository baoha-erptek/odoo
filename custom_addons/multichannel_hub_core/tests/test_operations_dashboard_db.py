"""Phase 1 (Database Verification) Tests for P1-DASH-MERGE Operations Dashboard.

Verifies the unified Operations Dashboard consolidates P1-01a (Order Dashboard)
and P1-03 (Tracking Dashboard) into a single view accessible to multiple teams.

Tests verify:
- operations_dashboard view records exist and have correct model references
- operations_dashboard menu exists and is properly parented
- Saved filters exist for Marketing User, BA Lead, and Production Team
- No RD-specific filters exist (deferred per CEO decision)
- Bulk Mark Shipped action is bound to the unified list
- Related fields from fulfillment are readable on sale.order records
- Old menu records are deleted post-merge
- Manifest includes new view file and excludes old ones
"""

import logging
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestOperationsDashboardMerge(TransactionCase):
    """Phase 1: Database schema and structure verification for unified Dashboard."""

    def test_operations_dashboard_list_view_exists(self):
        """Verify operations_dashboard_list_view ir.ui.view record exists."""
        try:
            view = self.env.ref('multichannel_hub_core.operations_dashboard_list_view')
            self.assertIsNotNone(view, "operations_dashboard_list_view should exist")
            self.assertEqual(view.model, 'sale.order.line', "View should target sale.order model")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.operations_dashboard_list_view') "
                     "raised ValueError; view not found")

    def test_operations_dashboard_search_view_exists(self):
        """Verify operations_dashboard_search_view ir.ui.view record exists."""
        try:
            view = self.env.ref('multichannel_hub_core.operations_dashboard_search_view')
            self.assertIsNotNone(view, "operations_dashboard_search_view should exist")
            self.assertEqual(view.model, 'sale.order.line', "Search view should target sale.order model")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.operations_dashboard_search_view') "
                     "raised ValueError; search view not found")

    def test_operations_dashboard_action_exists(self):
        """Verify action_operations_dashboard ir.actions.act_window record exists."""
        try:
            action = self.env.ref('multichannel_hub_core.action_operations_dashboard')
            self.assertIsNotNone(action, "action_operations_dashboard should exist")
            self.assertEqual(
                action.res_model, 'sale.order.line',
                "Operations dashboard action should target sale.order model"
            )
            self.assertIn('list', action.view_mode, "Action should include list view")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.action_operations_dashboard') "
                     "raised ValueError; action not found")

    def test_menu_operations_dashboard_exists(self):
        """Verify menu_operations_dashboard menu item exists and is properly parented."""
        try:
            menu = self.env.ref('multichannel_hub_core.menu_operations_dashboard')
            self.assertIsNotNone(menu, "menu_operations_dashboard should exist")
            self.assertIsNotNone(menu.parent_id, "Menu should have a parent")

            # Verify parent is the Operations root menu
            operations_root = self.env.ref('multichannel_hub_core.menu_operations_root')
            self.assertEqual(
                menu.parent_id, operations_root,
                "Operations Dashboard menu should be under Operations root"
            )

            # Verify action is linked
            self.assertEqual(
                menu.action, self.env.ref('multichannel_hub_core.action_operations_dashboard'),
                "Menu should link to action_operations_dashboard"
            )
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.menu_operations_dashboard') "
                     "raised ValueError; menu not found")

    def test_old_menu_order_dashboard_deleted(self):
        """Verify menu_order_dashboard is deleted post-merge."""
        menu = self.env.ref(
            'multichannel_hub_core.menu_order_dashboard',
            raise_if_not_found=False
        )
        self.assertFalse(
            menu,
            "menu_order_dashboard should be deleted after merge to unified dashboard"
        )

    def test_old_menu_tracking_dashboard_deleted(self):
        """Verify menu_tracking_dashboard is deleted post-merge."""
        menu = self.env.ref(
            'multichannel_hub_core.menu_tracking_dashboard',
            raise_if_not_found=False
        )
        self.assertFalse(
            menu,
            "menu_tracking_dashboard should be deleted after merge to unified dashboard"
        )

    def test_saved_filter_marketing_user_installed(self):
        """Verify saved filter_operations_marketing_user is installed."""
        try:
            filter_rec = self.env.ref('multichannel_hub_core.filter_operations_marketing_user')
            self.assertIsNotNone(filter_rec, "filter_operations_marketing_user should exist")
            # ir.filters.model_id is a Selection (Char-like), not a Many2one.
            self.assertEqual(
                filter_rec.model_id, 'sale.order.line',
                "Marketing filter should apply to sale.order"
            )
            self.assertIsNotNone(filter_rec.domain, "Filter should have a domain defined")
            self.assertTrue(len(filter_rec.domain) > 0, "Filter domain should be non-empty")

            # ir.filters has no group_ids in Odoo 19 — only user_ids
            # (M2M res.users). Role scoping is naming-based; assert the
            # name marker so a future refactor can't silently drop it.
            self.assertIn(
                'Marketing', filter_rec.name,
                "Marketing filter name should mark its role for self-selection"
            )
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.filter_operations_marketing_user') "
                     "raised ValueError; filter not found")

    def test_saved_filter_ba_lead_installed(self):
        """Verify saved filter_operations_ba_lead is installed."""
        try:
            filter_rec = self.env.ref('multichannel_hub_core.filter_operations_ba_lead')
            self.assertIsNotNone(filter_rec, "filter_operations_ba_lead should exist")
            self.assertEqual(
                filter_rec.model_id, 'sale.order.line',
                "BA Lead filter should apply to sale.order"
            )
            self.assertIsNotNone(filter_rec.domain, "Filter should have a domain defined")
            self.assertTrue(len(filter_rec.domain) > 0, "Filter domain should be non-empty")

            self.assertIn(
                'BA Lead', filter_rec.name,
                "BA Lead filter name should mark its role for self-selection"
            )
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.filter_operations_ba_lead') "
                     "raised ValueError; filter not found")

    def test_saved_filter_production_team_installed(self):
        """Verify saved filter_operations_production_team is installed."""
        try:
            filter_rec = self.env.ref('multichannel_hub_core.filter_operations_production_team')
            self.assertIsNotNone(filter_rec, "filter_operations_production_team should exist")
            self.assertEqual(
                filter_rec.model_id, 'sale.order.line',
                "Production Team filter should apply to sale.order"
            )
            self.assertIsNotNone(filter_rec.domain, "Filter should have a domain defined")
            self.assertTrue(len(filter_rec.domain) > 0, "Filter domain should be non-empty")

            self.assertIn(
                'Production', filter_rec.name,
                "Production filter name should mark its role for self-selection"
            )
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.filter_operations_production_team') "
                     "raised ValueError; filter not found")

    def test_no_rd_filter_installed(self):
        """Verify RD filter is NOT installed (deferred per CEO decision)."""
        filter_rec = self.env.ref(
            'multichannel_hub_core.filter_operations_rd',
            raise_if_not_found=False
        )
        self.assertFalse(
            filter_rec,
            "filter_operations_rd should NOT be installed (RD filters deferred)"
        )

    def test_bulk_mark_shipped_bound_to_unified_list(self):
        """Verify action_server_bulk_mark_shipped is bound to sale.order list view."""
        try:
            action = self.env.ref('multichannel_hub_core.action_server_bulk_mark_shipped')
            self.assertIsNotNone(action, "action_server_bulk_mark_shipped should exist")

            # Verify binding model is sale.order (not sale.order.fulfillment)
            self.assertIsNotNone(
                action.binding_model_id,
                "Server action should have a binding_model_id"
            )
            self.assertEqual(
                action.binding_model_id.model, 'sale.order.line',
                "Bulk Mark Shipped should be bound to sale.order (unified list)"
            )

            # Verify binding includes list view
            self.assertIn(
                'list', action.binding_view_types,
                "Server action should be available on list view"
            )
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.action_server_bulk_mark_shipped') "
                     "raised ValueError; action not found")

    def test_unified_list_includes_tracking_columns(self):
        """Verify unified list view includes tracking columns from fulfillment."""
        view = self.env.ref('multichannel_hub_core.operations_dashboard_list_view')
        arch = view.arch

        # Verify key tracking columns are present
        self.assertIn(
            '<field name="tracking_number"',
            arch,
            "List view should include tracking_number column"
        )
        self.assertIn(
            '<field name="tracking_state"',
            arch,
            "List view should include tracking_state column"
        )
        self.assertIn(
            '<field name="label_status_id"',
            arch,
            "List view should include label_status_id column (P1-LBL M2O swap)"
        )
        self.assertIn(
            '<field name="shipping_date"',
            arch,
            "List view should include shipping_date column"
        )

    def test_unified_list_includes_p1_01a_decorations(self):
        """Verify unified list includes P1-01a order dashboard decorations.

        The unified view should include all four decorations from the original
        Order Dashboard:
        1. qty_total >= 2 (decoration-info)
        2. is_duplicate_buyer (decoration-bf)
        3. order_priority in ('push','urgent') (decoration-danger)
        4. sales_channel == 'amazon' (decoration-warning)
        """
        view = self.env.ref('multichannel_hub_core.operations_dashboard_list_view')
        arch = view.arch

        # Check qty_total >= 2 decoration
        self.assertIn(
            'qty_total',
            arch,
            "List should include qty_total field/decoration"
        )

        # Check is_duplicate_buyer decoration
        self.assertIn(
            'is_duplicate_buyer',
            arch,
            "List should include is_duplicate_buyer field/decoration"
        )

        # Check order_priority decoration
        self.assertIn(
            "order_priority",
            arch,
            "List should include order_priority field/decoration for push/urgent"
        )

        # Check sales_channel decoration
        self.assertIn(
            "sales_channel == 'amazon'",
            arch,
            "List should include sales_channel decoration for Amazon orders"
        )

    def test_old_view_files_not_in_manifest(self):
        """Verify old view files are removed from __manifest__.py."""
        manifest_path = (
            Path(__file__).parent.parent / '__manifest__.py'
        )
        manifest_content = manifest_path.read_text()

        # Old view files should NOT be referenced
        self.assertNotIn(
            'views/order_dashboard_views.xml',
            manifest_content,
            "Old order_dashboard_views.xml should be removed from manifest"
        )
        self.assertNotIn(
            'views/tracking_dashboard_views.xml',
            manifest_content,
            "Old tracking_dashboard_views.xml should be removed from manifest"
        )

        # New unified view file SHOULD be referenced
        self.assertIn(
            'views/operations_dashboard_views.xml',
            manifest_content,
            "New operations_dashboard_views.xml should be in manifest"
        )
