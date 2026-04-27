"""Two-phase tests for OAuth token fields on etsy.shop model.

PHASE 1 (Data Verification): Direct SQL verification of column existence and storage.
PHASE 2 (ORM Unit Tests): Test through Odoo ORM API.

These tests verify:
1. Database-level column existence and type (Phase 1)
2. ORM-level field creation, persistence, and access control (Phase 2)
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestEtsyShopOAuthColumnsPhase1(TransactionCase):
    """Phase 1: Database-level verification of OAuth token columns.

    Direct SQL checks that the database schema has the expected columns.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_etsy_shop_oauth_columns_exist(self):
        """Phase 1: Verify OAuth columns exist in etsy_shop table.

        Columns required:
        - etsy_oauth_access_token (Char)
        - etsy_oauth_refresh_token (Char)
        - etsy_oauth_token_expires_at (Datetime)
        """
        # Query the database directly to check column existence
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop'
            ORDER BY column_name
        """)
        columns = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Verify all three OAuth columns exist
        self.assertIn(
            'etsy_oauth_access_token',
            columns,
            'Column etsy_oauth_access_token must exist on etsy_shop table',
        )
        self.assertIn(
            'etsy_oauth_refresh_token',
            columns,
            'Column etsy_oauth_refresh_token must exist on etsy_shop table',
        )
        self.assertIn(
            'etsy_oauth_token_expires_at',
            columns,
            'Column etsy_oauth_token_expires_at must exist on etsy_shop table',
        )

    def test_etsy_shop_oauth_token_expires_at_is_datetime(self):
        """Phase 1: Verify token_expires_at column is stored as timestamp."""
        self.env.cr.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop'
            AND column_name = 'etsy_oauth_token_expires_at'
        """)
        data_type = self.env.cr.fetchone()

        self.assertIsNotNone(
            data_type,
            'Column etsy_oauth_token_expires_at must exist',
        )
        # PostgreSQL timestamp type for Odoo Datetime field
        self.assertIn(
            data_type[0],
            ['timestamp without time zone', 'timestamp with time zone'],
            'token_expires_at must be stored as timestamp',
        )


@tagged('post_install', '-at_install')
class TestEtsyShopOAuthFieldsPhase2(TransactionCase):
    """Phase 2: ORM-level tests for OAuth token fields on etsy.shop.

    Tests the fields through the Odoo ORM API.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _create_etsy_shop(self, **kwargs):
        """Factory method to create a test etsy.shop record."""
        defaults = {
            'name': f'Test Shop {self.env.cr.rowcount}',
        }
        defaults.update(kwargs)
        return self.env['etsy.shop'].create(defaults)

    def test_etsy_shop_token_persist_round_trip(self):
        """Phase 2: Test writing and reading OAuth tokens via ORM.

        Write tokens to a new shop, read them back via admin user.
        """
        shop = self._create_etsy_shop()

        access_token = 'test_access_token_abc123def456'
        refresh_token = 'test_refresh_token_xyz789uvw012'

        # Write tokens
        shop.write({
            'etsy_oauth_access_token': access_token,
            'etsy_oauth_refresh_token': refresh_token,
        })

        # Read back via ORM
        shop.invalidate_recordset()
        self.assertEqual(
            shop.etsy_oauth_access_token,
            access_token,
            'Access token must persist round-trip',
        )
        self.assertEqual(
            shop.etsy_oauth_refresh_token,
            refresh_token,
            'Refresh token must persist round-trip',
        )

    def test_etsy_shop_token_hidden_from_non_system_user(self):
        """Phase 2: Test that token fields are hidden from non-system users.

        Fields should have groups='base.group_system' ACL.
        When a non-system user reads the field, Odoo should enforce access control.

        Note: Behavior varies by Odoo version. This test checks the actual behavior
        and asserts it (either empty string or AccessError).
        """
        # Create a non-system user (has base.group_user but not group_system)
        user = self.env['res.users'].create({
            'name': 'Salesman Test',
            'login': 'salesman_test@example.com',
            'group_ids': [
                (6, 0, [self.env.ref('base.group_user').id])
            ],
        })

        shop = self._create_etsy_shop()
        shop.write({
            'etsy_oauth_access_token': 'secret_token_abc123',
            'etsy_oauth_refresh_token': 'secret_refresh_xyz789',
        })

        # Attempt to read the token field as salesman
        shop_as_salesman = shop.with_user(user)

        try:
            # Try to read access_token field
            token_value = shop_as_salesman.etsy_oauth_access_token

            # Odoo 19 behavior: may return empty string due to field-level ACL
            self.assertNotEqual(
                token_value,
                'secret_token_abc123',
                'Non-system user must not see actual token value',
            )
        except AccessError:
            # Also acceptable: raise AccessError on field read
            # This is valid Odoo 19 behavior for group-restricted fields
            pass

    def test_etsy_shop_token_expires_at_datetime_storage(self):
        """Phase 2: Test that token_expires_at stores UTC datetime correctly.

        Write a known datetime, read back unchanged.
        """
        from datetime import datetime, timedelta

        shop = self._create_etsy_shop()

        # Create a future timestamp (1 hour from now)
        expires_at = datetime.now() + timedelta(hours=1)

        shop.write({
            'etsy_oauth_token_expires_at': expires_at,
        })

        shop.invalidate_recordset()
        read_back = shop.etsy_oauth_token_expires_at

        self.assertIsNotNone(
            read_back,
            'token_expires_at must be stored and readable',
        )

        # Compare as datetime objects (allow ±1 second tolerance due to rounding)
        time_diff = abs((read_back - expires_at).total_seconds())
        self.assertLess(
            time_diff,
            2,
            'token_expires_at must be stored as-is (within 1 second)',
        )

    def test_etsy_shop_no_existing_data_loss(self):
        """Phase 2: Regression test — adding new fields must not break create().

        A shop created without the new fields should still create successfully.
        """
        shop = self._create_etsy_shop(
            name='Regression Test Shop',
            active=True,
        )

        self.assertTrue(
            shop.id,
            'Shop must be created successfully with new fields present',
        )
        self.assertEqual(
            shop.name,
            'Regression Test Shop',
        )

        # New fields should default to empty/None
        self.assertFalse(
            shop.etsy_oauth_access_token,
            'access_token should default to empty',
        )
        self.assertFalse(
            shop.etsy_oauth_refresh_token,
            'refresh_token should default to empty',
        )
        self.assertFalse(
            shop.etsy_oauth_token_expires_at,
            'token_expires_at should default to empty',
        )

    def test_etsy_shop_token_fields_searchable(self):
        """Phase 2: Test that token fields can be searched (no crashes).

        Create shops with and without tokens, search for those with tokens.
        """
        shop_with_token = self._create_etsy_shop(name='With Token')
        shop_with_token.write({
            'etsy_oauth_access_token': 'token_abc123',
        })

        shop_without_token = self._create_etsy_shop(name='Without Token')

        # Search for shops with token
        shops_with_tokens = self.env['etsy.shop'].search([
            ('etsy_oauth_access_token', '!=', False),
        ])

        self.assertIn(
            shop_with_token.id,
            shops_with_tokens.ids,
            'Shop with token must be found in search',
        )
        self.assertNotIn(
            shop_without_token.id,
            shops_with_tokens.ids,
            'Shop without token must not be found',
        )
