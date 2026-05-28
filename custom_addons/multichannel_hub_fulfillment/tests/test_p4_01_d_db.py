"""P4-01-D Phase 1 view-arch — D3 server action + D4 Etsy-tab Shipping
subsection + D5 form button + Gearment notebook tab.

Reference: `specs/004-fulfillment-routing/p4-01-d-plan.md`.
"""
from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DD3ServerAction(TransactionCase):
    """D3 — bulk Gearment sync server action on sale.order.line list."""

    def test_action_server_gearment_bulk_sync_exists(self):
        action = self.env.ref(
            'multichannel_hub_fulfillment.action_server_gearment_bulk_sync',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(action, 'D3 server action missing')
        self.assertEqual(action.model_id.model, 'sale.order.line')
        self.assertEqual(action.binding_model_id.model, 'sale.order.line')
        self.assertEqual(action.binding_view_types, 'list')
        # Action body must call the FR-017-gated bulk method
        self.assertIn('action_gearment_bulk_sync', action.code or '')


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DD5FormButton(TransactionCase):
    """D5 — 'Sync to Gearment' button + Gearment notebook tab on SO form."""

    def setUp(self):
        super().setUp()
        view = self.env.ref(
            'multichannel_hub_fulfillment.view_order_form_gearment_inherit',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(view, 'D5 mhf SO form inheritance view missing')
        self.arch = etree.fromstring(view.arch.encode('utf-8'))

    def test_d5_button_exists(self):
        buttons = self.arch.xpath(
            "//button[@name='action_get_gearment_quote']"
        )
        self.assertEqual(len(buttons), 1, 'D5 button not found')

    def test_d5_button_has_group_ba_shipping(self):
        button = self.arch.xpath(
            "//button[@name='action_get_gearment_quote']"
        )[0]
        groups = button.get('groups', '')
        self.assertIn('group_ba_shipping', groups)

    def test_d5_button_has_visibility_expression(self):
        button = self.arch.xpath(
            "//button[@name='action_get_gearment_quote']"
        )[0]
        expr = button.get('invisible', '')
        # Must reference the 3 conditions from DD4.b
        self.assertIn('sales_channel', expr)
        self.assertIn('x_gearment_outbound_ref', expr)

    def test_d5_gearment_notebook_tab_exists(self):
        pages = self.arch.xpath("//page[@name='gearment_tab']")
        self.assertEqual(len(pages), 1, 'D5 Gearment notebook tab not found')

    def test_d5_gearment_tab_renders_state_field(self):
        page = self.arch.xpath("//page[@name='gearment_tab']")[0]
        rendered = etree.tostring(page).decode()
        self.assertIn('x_gearment_outbound_state', rendered)
        self.assertIn('x_gearment_quote_total', rendered)
        self.assertIn('x_gearment_quote_expires_at', rendered)


@tagged('post_install', '-at_install', 'p4_01_d')
class TestP401DD4EtsyShippingSubsection(TransactionCase):
    """D4 — read-only Shipping subsection in Etsy tab."""

    def setUp(self):
        super().setUp()
        view = self.env.ref(
            'etsy_integration.view_order_form_etsy_inherit',
            raise_if_not_found=False,
        )
        self.assertTrue(view, 'etsy_integration SO form view not found')
        # `view.arch` in Odoo 19 returns the post-processed/combined arch.
        # For inheritance-view xpath assertions, read the raw arch_db
        # attribute which preserves the source XML structure.
        raw = view.arch_db or view.arch
        self.arch = etree.fromstring(raw.encode('utf-8'))

    def test_d4_shipping_tracking_subsection_exists(self):
        # New subsection must be inside the Etsy tab
        page = self.arch.xpath("//page[@name='etsy_tab']")
        self.assertTrue(page, 'Etsy tab not found')
        groups = page[0].xpath(".//group[@string='Shipping Tracking']")
        self.assertEqual(
            len(groups), 1,
            'D4 Shipping Tracking subsection missing from Etsy tab',
        )

    def test_d4_shipping_tracking_fields_readonly(self):
        page = self.arch.xpath("//page[@name='etsy_tab']")[0]
        for field_name in (
            'tracking_number', 'shipping_carrier_id',
            'tracking_state', 'shipping_date', 'tracking_url',
        ):
            elems = page.xpath(
                f".//group[@string='Shipping Tracking']"
                f"//field[@name='{field_name}']"
            )
            self.assertEqual(
                len(elems), 1,
                f'D4 field {field_name} missing from Shipping Tracking',
            )
            self.assertEqual(
                elems[0].get('readonly'), '1',
                f'D4 field {field_name} not readonly',
            )
