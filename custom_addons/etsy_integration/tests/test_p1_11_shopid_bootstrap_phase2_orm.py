"""
Phase 2 ORM Unit Tests for P1-11-SHOPID-BOOTSTRAP: Etsy shop_id auto-bootstrap.

Tests verify business logic, constraints, and API callback behavior through the Odoo API.

Scope:
1. C-ESY-003 constraint: raises when active_source='api' without etsy_api_shop_id
2. OAuth callback: calls /users/me, extracts shop_id, writes field atomically
3. _probe_api() method: mocked requests to exercise real method body
4. Service guards: order syncer, tracking pusher, listing publisher refuse on NULL shop_id
5. Migration 19.0.2.31.0: refuses email→api flip without shop_id

RED: These tests FAIL because the production code does not yet:
- Implement C-ESY-003 @api.constrains
- Call GET /users/me in the OAuth callback
- Write etsy_api_shop_id atomically with tokens
- Create migration 19.0.2.31.0 to gate the flip

Expected failure patterns documented in each test docstring.
"""

import json
import logging
from unittest import mock
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module

_logger = logging.getLogger(__name__)

_FAKE_CREDS = {'client_id': 'kid-test', 'client_secret': 'secret-test'}


def _bypass_c_esy_003_create_api_shop(env, name, with_tokens=True, with_shop_id=False):
    """Create an etsy.shop via raw SQL bypassing C-ESY-003.

    Tests that exercise service guards / probe paths need a shop with
    active_source='api' but no etsy_api_shop_id — the very state the
    constraint is designed to refuse. ORM create() can't help; raw SQL
    in the test's savepoint can.
    """
    expires_at = fields.Datetime.add(fields.Datetime.now(), seconds=3600)
    env.cr.execute(
        """
        INSERT INTO etsy_shop (
            name, active_source, etsy_oauth_access_token,
            etsy_oauth_refresh_token, etsy_oauth_token_expires_at,
            etsy_api_shop_id, create_uid, create_date
        ) VALUES (%s, 'api', %s, %s, %s, %s, %s, now())
        RETURNING id
        """,
        (
            name,
            'access_token_ciphertext' if with_tokens else None,
            'refresh_token_ciphertext' if with_tokens else None,
            expires_at,
            '60752333' if with_shop_id else None,
            env.user.id,
        ),
    )
    shop_id = env.cr.fetchone()[0]
    env['etsy.shop'].invalidate_model()
    return env['etsy.shop'].browse(shop_id)


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase2_ConstraintCESY003(TransactionCase):
    """Phase 2: Verify C-ESY-003 constraint requires shop_id when active_source='api'.

    FAILURE REASON for RED: @api.constrains('active_source', 'etsy_api_shop_id')
    decorator and _check_api_source_has_shop_id method not implemented.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _create_shop_with_tokens_no_shop_id(self):
        """Factory: shop with OAuth tokens but no etsy_api_shop_id."""
        return self.env['etsy.shop'].create({
            'name': 'Test Shop No Shop ID',
            'etsy_oauth_access_token': 'test_access_token_ciphertext',
            'etsy_oauth_refresh_token': 'test_refresh_token_ciphertext',
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=3600
            ),
            'active_source': 'email',
            # Deliberately no etsy_api_shop_id
        })

    def _create_shop_with_tokens_and_shop_id(self):
        """Factory: shop with OAuth tokens AND etsy_api_shop_id."""
        return self.env['etsy.shop'].create({
            'name': 'Test Shop With Shop ID',
            'etsy_oauth_access_token': 'test_access_token_ciphertext',
            'etsy_oauth_refresh_token': 'test_refresh_token_ciphertext',
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=3600
            ),
            'etsy_api_shop_id': '60752333',  # JaHandmadeArt real Etsy ID
            'active_source': 'email',
        })

    def test_c_esy_003_raises_when_active_source_api_and_shop_id_empty(self):
        """FAIL (expected): Flipping to active_source='api' without shop_id raises ValidationError.

        Expected exception: ValidationError mentioning 'etsy_api_shop_id'.
        Expected constraint: C-ESY-003.
        """
        shop = self._create_shop_with_tokens_no_shop_id()

        # This write should raise because we're setting active_source='api'
        # but etsy_api_shop_id is NULL
        with self.assertRaises(ValidationError) as ctx:
            shop.write({'active_source': 'api'})

        self.assertIn(
            'etsy_api_shop_id',
            str(ctx.exception),
            "Error message must mention etsy_api_shop_id"
        )

    def test_c_esy_003_allows_active_source_api_when_shop_id_present(self):
        """PASS (sanity): Flipping to active_source='api' WITH shop_id succeeds."""
        shop = self._create_shop_with_tokens_and_shop_id()

        # This write should succeed because etsy_api_shop_id is set
        shop.write({'active_source': 'api'})

        self.assertEqual(
            shop.active_source,
            'api',
            "active_source should update to 'api' when etsy_api_shop_id is present"
        )

    def test_c_esy_003_allows_active_source_email_when_shop_id_empty(self):
        """PASS (sanity): active_source='email' allowed regardless of shop_id."""
        shop = self._create_shop_with_tokens_no_shop_id()

        # This write should succeed because active_source is 'email', not 'api'
        shop.write({'active_source': 'email'})

        self.assertEqual(
            shop.active_source,
            'email',
            "active_source='email' should not trigger C-ESY-003 constraint"
        )

    def test_c_esy_003_raises_on_create_with_api_source_no_shop_id(self):
        """FAIL (expected): Creating a shop with active_source='api' and no shop_id raises."""
        with self.assertRaises(ValidationError) as ctx:
            self.env['etsy.shop'].create({
                'name': 'API Shop No ID',
                'etsy_oauth_access_token': 'test_access_token_ciphertext',
                'etsy_oauth_refresh_token': 'test_refresh_token_ciphertext',
                'active_source': 'api',
                # Deliberately no etsy_api_shop_id
            })

        self.assertIn(
            'etsy_api_shop_id',
            str(ctx.exception),
            "Error message must mention etsy_api_shop_id"
        )


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase2_OAuthCallback(TransactionCase):
    """Phase 2: Verify OAuth callback populates etsy_api_shop_id from /users/me.

    FAILURE REASON for RED: Controller does not call GET /v3/application/users/me
    or does not extract shop_id from response or does not write it to the field.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls._creds_patcher = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    def test_etsy_api_client_has_fetch_users_me_shop_id_method(self):
        """FAIL (expected): EtsyApiClient must expose a fetch_users_me_shop_id() helper.

        The OAuth callback (GREEN) will call this helper to discover the real Etsy
        shop_id from /v3/application/users/me, then persist it atomically with tokens.
        Extracting it to a method (vs. inlining in the controller) makes it unit-
        testable without spinning up HttpCase.
        """
        from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient
        self.assertTrue(
            hasattr(EtsyApiClient, 'fetch_users_me_shop_id'),
            "EtsyApiClient.fetch_users_me_shop_id() helper missing — "
            "OAuth callback cannot discover shop_id atomically"
        )

    @patch('requests.Session.request')
    def test_fetch_users_me_shop_id_returns_shop_id_string_on_200(self, mock_request):
        """FAIL (expected): helper calls GET /users/me, parses shop_id, returns str.

        Real Etsy /users/me response (empirical 2026-05-22):
            {'user_id': 12345, 'shop_id': 60752333, ...}

        Helper must:
        1. Call EtsyApiClient.get('users/me') — exercises real request body
        2. Cast the int shop_id to str (gotcha #144 — XML-RPC int32 overflow risk)
        3. Return the str
        """
        shop = self.env['etsy.shop'].create({
            'name': 'Fetch ShopID Test',
            'etsy_oauth_access_token': 'access_token_ciphertext',
            'etsy_oauth_refresh_token': 'refresh_token_ciphertext',
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=3600
            ),
            'active_source': 'email',
        })

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'user_id': 12345, 'shop_id': 60752333}
        mock_request.return_value = mock_resp

        from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient
        client = EtsyApiClient(shop.sudo())
        result = client.fetch_users_me_shop_id()

        self.assertEqual(
            result, '60752333',
            "fetch_users_me_shop_id must return str(shop_id) from /users/me"
        )
        mock_request.assert_called()

    @patch('requests.Session.request')
    def test_fetch_users_me_shop_id_returns_none_and_warns_on_4xx(self, mock_request):
        """FAIL (expected): helper returns None + WARNING log on /users/me 4xx.

        On failure the callback must STILL persist tokens (don't break OAuth on
        a /users/me hiccup). Helper signals failure with None return + warning so
        the controller can log + proceed.
        """
        shop = self.env['etsy.shop'].create({
            'name': 'Fetch ShopID 403 Test',
            'etsy_oauth_access_token': 'access_token_ciphertext',
            'etsy_oauth_refresh_token': 'refresh_token_ciphertext',
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=3600
            ),
            'active_source': 'email',
        })

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = '{"error": "scope_not_granted"}'
        mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")
        mock_request.return_value = mock_resp

        from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient
        client = EtsyApiClient(shop.sudo())

        with self.assertLogs(
            'odoo.addons.etsy_integration.services.etsy_api_client', level='WARNING'
        ):
            result = client.fetch_users_me_shop_id()

        self.assertIsNone(
            result,
            "fetch_users_me_shop_id must return None on 4xx (callback proceeds)"
        )


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase2_ProbeAPI(TransactionCase):
    """Phase 2: Verify _probe_api() with mocked requests (gotcha #152).

    FAILURE REASON for RED: Either _probe_api method doesn't exist, or tests
    are mocking _probe_api itself instead of mocking requests.Session.request.

    This test is the CANARY that would have caught P1-11-WIRE-LIVE bugs
    (double-prefix `/v3/application/v3/application`, etc.).
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls._creds_patcher = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    def _create_shop_with_tokens(self):
        """Factory: shop with OAuth tokens + shop_id.

        Uses raw-SQL bypass for active_source='api' so the shop survives the
        C-ESY-001 + C-ESY-003 constraints without us having to set every
        OAuth field via ORM (which would also invoke encryption hooks).
        """
        return _bypass_c_esy_003_create_api_shop(
            self.env, 'Probe Test Shop',
            with_tokens=True, with_shop_id=True,
        )

    @patch('requests.Session.request')
    def test_probe_api_with_mocked_requests_returns_true_on_200(self, mock_request):
        """PASS: _probe_api calls EtsyApiClient.get('openapi-ping') and returns True."""
        shop = self._create_shop_with_tokens()

        # Mock the underlying requests.Session.request (NOT _probe_api)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_request.return_value = mock_response

        # Call the actual _probe_api method
        result = shop._probe_api()

        self.assertTrue(
            result,
            "_probe_api should return True on HTTP 2xx"
        )
        # Verify that requests.Session.request was called (the real method body ran)
        mock_request.assert_called()

    @patch('requests.Session.request')
    def test_probe_api_with_mocked_requests_returns_false_on_403(self, mock_request):
        """PASS: _probe_api returns False on 403, logs warning."""
        shop = self._create_shop_with_tokens()

        # Mock the underlying requests.Session.request
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = Exception("403 Forbidden")
        mock_request.return_value = mock_response

        # _probe_api catches exceptions and logs warning, returns False
        with self.assertLogs('odoo.addons.etsy_integration.models.etsy_shop', level='WARNING'):
            result = shop._probe_api()

        self.assertFalse(
            result,
            "_probe_api should return False on HTTP 4xx/5xx"
        )


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase2_ServiceGuards(TransactionCase):
    """Phase 2: Verify services refuse to operate when shop_id is NULL.

    The 3 caller sites (order syncer, tracking pusher, listing publisher) already
    have guards that refuse with warnings. These tests are regression guards.

    FAILURE REASON for RED: Services don't check etsy_api_shop_id or guards are missing.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls._creds_patcher = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    def _create_shop_without_shop_id(self):
        """Factory: api-source shop missing etsy_api_shop_id.

        This is precisely the state C-ESY-003 refuses, so the shop must be
        inserted via raw SQL bypassing the constraint (the guards under
        test pre-date the constraint and protected against this same state
        before C-ESY-003 existed).
        """
        return _bypass_c_esy_003_create_api_shop(
            self.env, 'Guard Test Shop',
            with_tokens=True, with_shop_id=False,
        )

    def test_etsy_order_syncer_refuses_when_etsy_api_shop_id_is_null(self):
        """PASS (regression guard): Order syncer logs warning and returns early."""
        shop = self._create_shop_without_shop_id()

        from odoo.addons.etsy_integration.services.etsy_order_syncer import EtsyOrderSyncer

        syncer = EtsyOrderSyncer(self.env)

        with self.assertLogs(
            'odoo.addons.etsy_integration.services.etsy_order_syncer',
            level='WARNING',
        ) as log_ctx:
            result = syncer.sync_shop_orders(shop)

        self.assertEqual(
            result, {'ingested': 0, 'audited': 0},
            "Syncer must return zero-count dict when shop_id is NULL"
        )
        self.assertTrue(
            any('etsy_api_shop_id' in msg for msg in log_ctx.output),
            "Syncer must log warning naming etsy_api_shop_id when NULL"
        )

    def test_etsy_tracking_pusher_refuses_when_etsy_api_shop_id_is_null(self):
        """PASS (regression guard): Tracking pusher refuses + populates error field."""
        shop = self._create_shop_without_shop_id()
        # Minimal order with required Etsy fields; partner_root is always available.
        order = self.env['sale.order'].create({
            'partner_id': self.env.ref('base.partner_root').id,
            'etsy_shop_id': shop.id,
            'etsy_order_id': '999999999',
        })
        # Pusher requires a fulfillment with a tracking number to even reach the
        # shop_id check; create one so the guard fires for the right reason.
        self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': 'TRK-TEST-1',
        })

        from odoo.addons.etsy_integration.services.etsy_tracking_pusher import EtsyTrackingPusher

        pusher = EtsyTrackingPusher(self.env)
        result = pusher.push(order)

        self.assertFalse(
            result,
            "push() must return False when shop has no etsy_api_shop_id"
        )
        self.assertIn(
            'etsy_api_shop_id',
            (order.etsy_tracking_push_error or '').lower(),
            "Order's etsy_tracking_push_error must mention etsy_api_shop_id"
        )

    def test_etsy_listing_publisher_refuses_when_etsy_api_shop_id_is_null(self):
        """PASS (regression guard): push_personalization raises ValueError on NULL shop_id.

        Uses push_personalization because its shop_id check fires WITHOUT the
        publisher's _check_shop_defaults pre-check (which would mask the test's
        target failure with a different ValueError about missing defaults).
        """
        shop = self._create_shop_without_shop_id()
        tmpl = self.env['product.template'].create({
            'name': 'Listing Guard Test',
            'x_is_personalizable': True,
            'x_personalization_instructions': 'Add your name',
        })

        from odoo.addons.etsy_integration.services.etsy_listing_publisher import EtsyListingPublisher

        publisher = EtsyListingPublisher(self.env)

        with self.assertRaises(ValueError) as ctx:
            publisher.push_personalization(tmpl, 'FAKE_LISTING_ID', shop)
        self.assertIn(
            'etsy_api_shop_id',
            str(ctx.exception),
            "push_personalization must raise ValueError naming etsy_api_shop_id"
        )


@tagged('post_install', '-at_install')
class TestP1_11_ShopID_Phase2_Migration(TransactionCase):
    """Phase 2: Verify migration 19.0.2.31.0 refuses email→api flip without shop_id.

    FAILURE REASON for RED: Migration script does not exist or does not enforce the gate.

    Migration must raise with a clear error message listing affected shops.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_migration_refuses_email_to_api_flip_without_shop_id(self):
        """FAIL (expected): migrations/19.0.2.31.0/post-migrate.py refuses bad data.

        The migration's `migrate(cr, version)` function must SELECT shops with
        active_source='api' AND empty etsy_api_shop_id, then raise with shop
        names listed so the operator knows what to fix.

        RED: importing the migrate function fails because the file doesn't exist.
        """
        # Pre-seed an unsafe shop via raw SQL within the test savepoint
        # (TransactionCase forbids cr.commit; SAVEPOINT-visible INSERT is enough).
        shop_name = 'Unsafe Flip Shop P1_11_SHOPID'
        self.env.cr.execute(
            """
            INSERT INTO etsy_shop (name, active_source, create_uid, create_date)
            VALUES (%s, %s, %s, now())
            """,
            (shop_name, 'api', self.env.user.id),
        )

        # Import and invoke the migration's migrate() function. The file path
        # the GREEN phase must create:
        #   custom_addons/etsy_integration/migrations/19.0.2.31.0/post-migrate.py
        # exposing `def migrate(cr, version): ...`.
        import importlib.util
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migrations', '19.0.2.31.0', 'post-migrate.py',
        )
        self.assertTrue(
            os.path.exists(migration_path),
            f"Migration file missing: {migration_path}"
        )

        spec = importlib.util.spec_from_file_location(
            'etsy_integration_p1_11_shopid_post_migrate', migration_path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with self.assertRaises(Exception) as ctx:
            module.migrate(self.env.cr, '19.0.2.31.0')
        self.assertIn(
            shop_name,
            str(ctx.exception),
            "Migration error must list the affected shop name"
        )
