"""
Phase 1 Database & Architecture Tests for P1-11-RUNBOOK: Etsy Shop Runbook Actions.

Tests verify method existence, view architecture, and button gating at the XML level.

RED: These tests FAIL because the production code (action methods + buttons) does not yet exist.
Expected failure reasons documented in each test.
"""

import logging
from lxml import etree

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP1_11Runbook_Phase1_Methods(TransactionCase):
    """Phase 1: Verify action methods exist on etsy.shop model.

    FAILURE REASON for RED: Methods not yet defined in etsy_shop.py.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_action_test_connection_method_exists(self):
        """FAIL: action_test_connection() method not defined on etsy.shop."""
        model = self.env['etsy.shop']
        self.assertTrue(
            hasattr(model, 'action_test_connection'),
            "etsy.shop must have action_test_connection method"
        )
        self.assertTrue(
            callable(getattr(model, 'action_test_connection')),
            "action_test_connection must be callable"
        )

    def test_action_authorize_etsy_method_exists(self):
        """FAIL: action_authorize_etsy() method not defined on etsy.shop."""
        model = self.env['etsy.shop']
        self.assertTrue(
            hasattr(model, 'action_authorize_etsy'),
            "etsy.shop must have action_authorize_etsy method"
        )
        self.assertTrue(
            callable(getattr(model, 'action_authorize_etsy')),
            "action_authorize_etsy must be callable"
        )


@tagged('post_install', '-at_install')
class TestP1_11Runbook_Phase1_ViewArchitecture(TransactionCase):
    """Phase 1: Verify form view buttons exist and are properly gated.

    FAILURE REASON for RED: Buttons not yet added to etsy_shop_view_form XML.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_form_view_has_authorize_button(self):
        """FAIL: etsy_shop_view_form missing button[@name='action_authorize_etsy']."""
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        self.assertTrue(
            view.exists(),
            "etsy_integration.etsy_shop_view_form must exist"
        )

        # Parse the view arch XML
        arch_tree = etree.fromstring(view.arch.encode('utf-8'))

        # Find button with name='action_authorize_etsy'
        buttons = arch_tree.xpath(
            "//button[@name='action_authorize_etsy']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )

        self.assertTrue(
            len(buttons) > 0,
            "etsy_shop_view_form must have button[@name='action_authorize_etsy']"
        )

    def test_form_view_has_test_connection_button(self):
        """FAIL: etsy_shop_view_form missing button[@name='action_test_connection']."""
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        self.assertTrue(
            view.exists(),
            "etsy_integration.etsy_shop_view_form must exist"
        )

        # Parse the view arch XML
        arch_tree = etree.fromstring(view.arch.encode('utf-8'))

        # Find button with name='action_test_connection'
        buttons = arch_tree.xpath(
            "//button[@name='action_test_connection']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )

        self.assertTrue(
            len(buttons) > 0,
            "etsy_shop_view_form must have button[@name='action_test_connection']"
        )

    def test_form_buttons_system_gated(self):
        """FAIL: Buttons must have groups='base.group_system' attribute.

        Per FR-017 (18 confirmations): UI groups= MUST be in place.
        View-level gating is the UX boundary; method-level gates the RPC boundary.
        """
        view = self.env.ref('etsy_integration.etsy_shop_view_form')

        # Parse the view arch XML
        arch_tree = etree.fromstring(view.arch.encode('utf-8'))

        # Check both buttons for groups attribute
        auth_buttons = arch_tree.xpath(
            "//button[@name='action_authorize_etsy']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )
        test_buttons = arch_tree.xpath(
            "//button[@name='action_test_connection']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )

        # Verify at least one of each button type exists
        self.assertTrue(
            len(auth_buttons) > 0,
            "authorize button must exist"
        )
        self.assertTrue(
            len(test_buttons) > 0,
            "test_connection button must exist"
        )

        # Check that the authorize button has groups attribute
        auth_button = auth_buttons[0]
        auth_groups = auth_button.get('groups', '')
        self.assertIn(
            'base.group_system',
            auth_groups,
            "action_authorize_etsy button must have groups='base.group_system'"
        )

        # Check that the test_connection button has groups attribute
        test_button = test_buttons[0]
        test_groups = test_button.get('groups', '')
        self.assertIn(
            'base.group_system',
            test_groups,
            "action_test_connection button must have groups='base.group_system'"
        )

    def test_form_buttons_are_object_type(self):
        """Verify buttons have type='object' (calls method, not XMLID action)."""
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        arch_tree = etree.fromstring(view.arch.encode('utf-8'))

        auth_buttons = arch_tree.xpath(
            "//button[@name='action_authorize_etsy']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )
        test_buttons = arch_tree.xpath(
            "//button[@name='action_test_connection']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )

        auth_button = auth_buttons[0]
        test_button = test_buttons[0]

        self.assertEqual(
            auth_button.get('type'),
            'object',
            "action_authorize_etsy button must have type='object'"
        )
        self.assertEqual(
            test_button.get('type'),
            'object',
            "action_test_connection button must have type='object'"
        )

    def test_form_buttons_in_button_box(self):
        """Verify buttons are placed inside the oe_button_box div."""
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        arch_tree = etree.fromstring(view.arch.encode('utf-8'))

        # Find the button_box div
        button_box = arch_tree.xpath(
            "//div[@class='oe_button_box' or contains(@class, 'oe_button_box')]",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )

        self.assertTrue(
            len(button_box) > 0,
            "Form must have a div with oe_button_box class"
        )

        # Verify that our buttons are descendants of the button_box
        box = button_box[0]
        auth_buttons_in_box = box.xpath(
            ".//button[@name='action_authorize_etsy']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )
        test_buttons_in_box = box.xpath(
            ".//button[@name='action_test_connection']",
            namespaces={'t': 'http://www.odoo.com/binding'}
        )

        self.assertTrue(
            len(auth_buttons_in_box) > 0,
            "action_authorize_etsy button must be inside oe_button_box"
        )
        self.assertTrue(
            len(test_buttons_in_box) > 0,
            "action_test_connection button must be inside oe_button_box"
        )
