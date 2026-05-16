"""
Phase 2 ORM Unit Tests for P1-11-RUNBOOK: Etsy Shop Runbook Actions.

Tests verify business logic, return values, access control, and ORM behavior
through the Odoo API and mocking of dependencies.

RED: These tests FAIL because the production code (action methods) does not yet exist.
Expected failure reasons documented in each test.
"""

import logging
from unittest import mock

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP1_11Runbook_Phase2_TestConnection(TransactionCase):
    """Phase 2: Verify action_test_connection() behavior.

    FAILURE REASON for RED: Method not yet implemented.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shop and users."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a test shop
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop For action_test_connection',
        })

        # Create a non-system user for access testing
        cls.non_system_user = cls.env['res.users'].create({
            'name': 'Non-System User',
            'login': 'nonsystem_p1_11@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        # System user (admin)
        cls.system_user = cls.env.ref('base.user_root')

    def test_test_connection_success_returns_success_notification(self):
        """FAIL: action_test_connection() not implemented.

        When _probe_api() returns True, method must return a display_notification
        action dict with type='success'.
        """
        shop_as_admin = self.shop.with_user(self.system_user)

        # Mock _probe_api to return True
        with mock.patch.object(type(shop_as_admin), '_probe_api', return_value=True):
            result = shop_as_admin.action_test_connection()

        # Verify the action dict structure
        self.assertIsInstance(result, dict, "action_test_connection must return dict")
        self.assertEqual(
            result.get('type'),
            'ir.actions.client',
            "action type must be 'ir.actions.client'"
        )
        self.assertEqual(
            result.get('tag'),
            'display_notification',
            "action tag must be 'display_notification'"
        )

        # Verify params structure
        params = result.get('params', {})
        self.assertIsInstance(params, dict, "params must be dict")
        self.assertEqual(
            params.get('type'),
            'success',
            "notification type must be 'success' when probe succeeds"
        )
        self.assertFalse(
            params.get('sticky', True),
            "sticky should be False (notification auto-closes)"
        )
        self.assertIn('title', params, "notification must have a title")
        self.assertIn('message', params, "notification must have a message")

    def test_test_connection_failure_returns_warning_notification(self):
        """FAIL: action_test_connection() not implemented.

        When _probe_api() returns False, method must return a display_notification
        action dict with type='warning'.
        """
        shop_as_admin = self.shop.with_user(self.system_user)

        # Mock _probe_api to return False
        with mock.patch.object(type(shop_as_admin), '_probe_api', return_value=False):
            result = shop_as_admin.action_test_connection()

        # Verify the action dict structure
        self.assertIsInstance(result, dict, "action_test_connection must return dict")
        self.assertEqual(
            result.get('type'),
            'ir.actions.client',
            "action type must be 'ir.actions.client'"
        )
        self.assertEqual(
            result.get('tag'),
            'display_notification',
            "action tag must be 'display_notification'"
        )

        # Verify params structure
        params = result.get('params', {})
        self.assertEqual(
            params.get('type'),
            'warning',
            "notification type must be 'warning' when probe fails"
        )

    def test_test_connection_calls_probe_api_once(self):
        """FAIL: action_test_connection() not implemented.

        Method must call _probe_api() exactly once.
        """
        shop_as_admin = self.shop.with_user(self.system_user)

        # Mock _probe_api and verify call count
        with mock.patch.object(type(shop_as_admin), '_probe_api', return_value=True) as mock_probe:
            result = shop_as_admin.action_test_connection()

        mock_probe.assert_called_once()

    def test_test_connection_non_system_raises_access_error(self):
        """FAIL: action_test_connection() not implemented with FR-017 gate.

        Non-system user calling action_test_connection() must raise AccessError.
        The gate must fire BEFORE _probe_api is called.
        """
        shop_as_user = self.shop.with_user(self.non_system_user)

        # Mock _probe_api to verify it is NOT called (gate fires first)
        with mock.patch.object(type(shop_as_user), '_probe_api', return_value=True) as mock_probe:
            with self.assertRaises(AccessError) as cm:
                shop_as_user.action_test_connection()

            # Verify _probe_api was not called (gate prevents it)
            mock_probe.assert_not_called()

        self.assertIn(
            'system',
            str(cm.exception).lower(),
            "AccessError should mention system administrator requirement"
        )

    def test_test_connection_system_user_succeeds(self):
        """Happy path: system user can call action_test_connection()."""
        shop_as_admin = self.shop.with_user(self.system_user)

        with mock.patch.object(type(shop_as_admin), '_probe_api', return_value=True):
            result = shop_as_admin.action_test_connection()

        # Should not raise; should return a dict
        self.assertIsInstance(result, dict)

    def test_test_connection_ensure_one(self):
        """FAIL: action_test_connection() missing ensure_one().

        Method must enforce single-record operation (ensure_one).
        """
        # Create another shop
        shop2 = self.env['etsy.shop'].create({
            'name': 'Second Test Shop',
        })

        # Try to call on a recordset with 2 shops
        multi_shops = self.shop | shop2

        with self.assertRaises(Exception) as cm:
            with mock.patch.object(type(multi_shops), '_probe_api', return_value=True):
                multi_shops.action_test_connection()

        # Could raise ValueError (ensure_one) or similar; the exact exception
        # depends on Odoo's ensure_one implementation
        # Just verify that calling on multi-record recordset raises
        self.assertIsNotNone(cm.exception)


@tagged('post_install', '-at_install')
class TestP1_11Runbook_Phase2_AuthorizeEtsy(TransactionCase):
    """Phase 2: Verify action_authorize_etsy() behavior.

    FAILURE REASON for RED: Method not yet implemented.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test shop and users."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a test shop
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop For action_authorize_etsy',
        })

        # Create a non-system user for access testing
        cls.non_system_user = cls.env['res.users'].create({
            'name': 'Non-System User Auth',
            'login': 'nonsystem_auth_p1_11@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        # System user (admin)
        cls.system_user = cls.env.ref('base.user_root')

    def test_authorize_etsy_returns_act_url_with_shop_id(self):
        """FAIL: action_authorize_etsy() not implemented.

        Method must return ir.actions.act_url pointing to /etsy/api/oauth/authorize
        with query param shop_id=<self.id>.
        """
        shop_as_admin = self.shop.with_user(self.system_user)

        result = shop_as_admin.action_authorize_etsy()

        # Verify the action dict structure
        self.assertIsInstance(result, dict, "action_authorize_etsy must return dict")
        self.assertEqual(
            result.get('type'),
            'ir.actions.act_url',
            "action type must be 'ir.actions.act_url'"
        )

        # Verify URL structure
        url = result.get('url', '')
        self.assertIn(
            '/etsy/api/oauth/authorize',
            url,
            f"URL must contain /etsy/api/oauth/authorize; got {url}"
        )
        self.assertIn(
            f'shop_id={self.shop.id}',
            url,
            f"URL must contain shop_id={self.shop.id} query param; got {url}"
        )

        # Verify target
        self.assertEqual(
            result.get('target'),
            'self',
            "action target should be 'self'"
        )

    def test_authorize_etsy_non_system_raises_access_error(self):
        """FAIL: action_authorize_etsy() not implemented with FR-017 gate.

        Non-system user calling action_authorize_etsy() must raise AccessError.
        """
        shop_as_user = self.shop.with_user(self.non_system_user)

        with self.assertRaises(AccessError) as cm:
            shop_as_user.action_authorize_etsy()

        self.assertIn(
            'system',
            str(cm.exception).lower(),
            "AccessError should mention system administrator requirement"
        )

    def test_authorize_etsy_system_user_succeeds(self):
        """Happy path: system user can call action_authorize_etsy()."""
        shop_as_admin = self.shop.with_user(self.system_user)

        result = shop_as_admin.action_authorize_etsy()

        # Should not raise; should return a dict
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('type'), 'ir.actions.act_url')

    def test_authorize_etsy_ensure_one(self):
        """FAIL: action_authorize_etsy() missing ensure_one().

        Method must enforce single-record operation (ensure_one).
        """
        # Create another shop
        shop2 = self.env['etsy.shop'].create({
            'name': 'Second Shop For Auth',
        })

        # Try to call on a recordset with 2 shops
        multi_shops = self.shop | shop2
        multi_shops_as_admin = multi_shops.with_user(self.system_user)

        with self.assertRaises(Exception) as cm:
            multi_shops_as_admin.action_authorize_etsy()

        # Could raise ValueError (ensure_one) or similar
        # Just verify that calling on multi-record recordset raises
        self.assertIsNotNone(cm.exception)

    def test_authorize_etsy_url_structure_correct(self):
        """Verify URL is properly formatted and has correct shop_id value."""
        shop_as_admin = self.shop.with_user(self.system_user)
        result = shop_as_admin.action_authorize_etsy()

        url = result.get('url', '')

        # Extract shop_id from URL and verify it matches
        self.assertIn(
            f'shop_id={self.shop.id}',
            url,
            "shop_id query parameter must match the called shop's id"
        )

    def test_authorize_etsy_url_format_query_param(self):
        """Verify shop_id is a proper query parameter (after ?)."""
        shop_as_admin = self.shop.with_user(self.system_user)
        result = shop_as_admin.action_authorize_etsy()

        url = result.get('url', '')

        # Should have ? followed by shop_id
        self.assertIn('?', url, "URL must have a query string separator (?)")
        self.assertGreater(
            url.index(f'shop_id='),
            url.index('?'),
            "shop_id parameter should come after the ? separator"
        )
