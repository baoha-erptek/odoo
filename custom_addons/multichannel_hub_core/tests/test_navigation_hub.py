# P-IA-01 — Navigation hub reorganization (mockup-v3 plan).
# Phase 2 ORM tests: hub sections exist, children re-parented, P0 gating fixed.
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNavigationHub(TransactionCase):

    def _ref(self, xmlid):
        return self.env.ref(xmlid)

    def test_hub_sections_exist_under_operations_root(self):
        root = self._ref('multichannel_hub_core.menu_operations_root')
        expected = {
            'multichannel_hub_core.menu_daily_work': 10,
            'multichannel_hub_core.menu_sales_publish': 20,
            'multichannel_hub_core.menu_fulfillment': 30,
            'multichannel_hub_core.menu_after_sales': 40,
            'multichannel_hub_core.menu_monitoring': 50,
            'multichannel_hub_core.menu_operations_config': 60,
        }
        for xmlid, seq in expected.items():
            menu = self._ref(xmlid)
            self.assertEqual(menu.parent_id, root, f'{xmlid} not under root')
            self.assertEqual(menu.sequence, seq, f'{xmlid} sequence')

    def test_daily_work_children(self):
        daily = self._ref('multichannel_hub_core.menu_daily_work')
        for xmlid in (
            'multichannel_hub_core.menu_operations_dashboard',
            'etsy_integration.menu_etsy_orders',
            'multichannel_hub_core.menu_design_file',
            'design.menu_design_order',
            'etsy_integration.menu_etsy_design_queue',
        ):
            self.assertEqual(self._ref(xmlid).parent_id, daily, xmlid)

    def test_sales_publish_children(self):
        sales = self._ref('multichannel_hub_core.menu_sales_publish')
        for xmlid in (
            'multichannel_hub_core.menu_sku_builder_wizard',
            'multichannel_hub_core.menu_multichannel_listing',
            'etsy_integration.menu_etsy_listing_products',
            'multichannel_hub_core.menu_product_channel_status',
            'multichannel_hub_core.menu_product_sku_drift',
        ):
            self.assertEqual(self._ref(xmlid).parent_id, sales, xmlid)

    def test_fulfillment_children(self):
        fulfillment = self._ref('multichannel_hub_core.menu_fulfillment')
        for xmlid in (
            'multichannel_hub_fulfillment.menu_sale_order_fulfillment_detail',
            'multichannel_hub_fulfillment.menu_tracking_import_root',
        ):
            self.assertEqual(self._ref(xmlid).parent_id, fulfillment, xmlid)

    def test_after_sales_children_flow4_nav_exists(self):
        after = self._ref('multichannel_hub_core.menu_after_sales')
        ticket = self._ref('etsy_integration.menu_etsy_order_ticket')
        addr = self._ref('etsy_integration.menu_etsy_address_change_request')
        enquiry = self._ref('multichannel_hub_core.menu_multichannel_enquiry')
        self.assertEqual(ticket.parent_id, after)
        self.assertEqual(addr.parent_id, after)
        self.assertEqual(
            addr.action.id,
            self._ref('etsy_integration.action_etsy_address_change_request').id,
        )
        self.assertEqual(enquiry.parent_id, after)

    def test_monitoring_children(self):
        monitoring = self._ref('multichannel_hub_core.menu_monitoring')
        for xmlid in (
            'multichannel_hub_core.menu_multichannel_sync_health',
            'etsy_integration.menu_etsy_sync_health',
            'etsy_integration.menu_etsy_api_log',
            'etsy_integration.menu_etsy_email_log',
            'etsy_integration.menu_etsy_dashboard',
            'multichannel_hub_fulfillment.menu_gearment_root',
        ):
            self.assertEqual(self._ref(xmlid).parent_id, monitoring, xmlid)

    def test_config_children(self):
        config = self._ref('multichannel_hub_core.menu_operations_config')
        for xmlid in (
            'multichannel_hub_core.menu_sku_families',
            'etsy_integration.menu_etsy_shops',
            'multichannel_hub_core.menu_shipping_carrier',
            'multichannel_hub_fulfillment.menu_logistics_partner',
            'etsy_integration.menu_etsy_shipping_profile',
            'etsy_integration.menu_etsy_taxonomy_node',
            'multichannel_hub_core.menu_order_pipeline',
            'multichannel_hub_core.menu_pipeline_team',
            'multichannel_hub_core.menu_pipeline_transition_log',
            'multichannel_hub_core.menu_catalog_import_run_wizard',
            'multichannel_hub_core.menu_catalog_import_run_history',
            'etsy_integration.menu_etsy_import_orders',
            'etsy_integration.menu_etsy_data_migration',
        ):
            self.assertEqual(self._ref(xmlid).parent_id, config, xmlid)

    def test_etsy_root_removed(self):
        self.assertFalse(
            self.env.ref('etsy_integration.menu_etsy_root',
                         raise_if_not_found=False),
            'old Etsy root app menu should be deleted',
        )

    def test_p0_gating_fixed(self):
        production = self._ref('multichannel_hub_core.group_production_team')
        manager = self._ref('sales_team.group_sale_manager')
        ba_user = self._ref('multichannel_hub_core.group_ba_user')
        ba_lead = self._ref('multichannel_hub_core.group_ba_lead')
        cases = {
            'multichannel_hub_core.menu_design_file': production,
            'design.menu_design_order': production,
            'etsy_integration.menu_etsy_design_queue': production,
            # BA Leads own shop publisher defaults (Flow 1)
            'etsy_integration.menu_etsy_shops': ba_lead,
            'etsy_integration.menu_etsy_import_orders': manager,
            'etsy_integration.menu_etsy_orders': ba_user,
            'etsy_integration.menu_etsy_email_log': ba_user,
        }
        for xmlid, group in cases.items():
            self.assertIn(
                group,
                self._ref(xmlid).group_ids,
                f'{xmlid} missing group {group.name}',
            )

    def test_config_section_manager_gated(self):
        config = self._ref('multichannel_hub_core.menu_operations_config')
        self.assertIn(
            self._ref('sales_team.group_sale_manager'), config.group_ids,
        )
