"""Phase 1 DB tests for P1-10 — Production OAuth + Fernet-at-rest token encryption.

These tests verify data schema and database-level integrity without relying on
service implementation. They use direct SQL to verify:
- Fernet key ICP record exists with system-only ACL
- etsy.api.log source enum includes scope_validation
- Token columns exist with correct properties
- Encrypted data is persisted as Fernet ciphertext

PHASE: RED (failing tests — implementation does not exist yet)
"""
import logging

from odoo.exceptions import AccessError
from odoo.tests.common import SingleTransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p1_10')
class TestP1_10Schema(SingleTransactionCase):
    """Phase 1: Database schema verification for P1-10 Fernet encryption."""

    def test_fernet_key_icp_record_exists(self):
        """Test that ir.config_parameter row with key 'etsy.oauth.fernet_key' exists.

        The key is declared by data/ir_config_parameter.xml with system-only ACL.
        """
        icp = self.env['ir.config_parameter'].sudo()

        # Try to read the ICP key; it should exist with an empty default value
        # (lazy generation on first encrypt call — D-P1-10-02).
        key_value = icp.get_param('etsy.oauth.fernet_key', default=None)

        # The row must exist in the database (even if the value is empty/None).
        self.env.cr.execute(
            "SELECT id, key FROM ir_config_parameter WHERE key = %s",
            ('etsy.oauth.fernet_key',)
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "ir_config_parameter row for etsy.oauth.fernet_key must exist")

    def test_fernet_key_system_group_acl(self):
        """Test that non-admin user cannot read 'etsy.oauth.fernet_key' ICP.

        The key is declared with groups='base.group_system' — only system users.
        """
        # Create a non-admin, non-system user
        test_user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        # Non-admin user should NOT be able to read the ICP key
        icp_with_user = self.env['ir.config_parameter'].with_user(test_user)

        with self.assertRaises(AccessError):
            icp_with_user.get_param('etsy.oauth.fernet_key')

        # Admin (system) user should be able to read it
        icp_admin = self.env['ir.config_parameter'].sudo()
        # Should not raise
        value = icp_admin.get_param('etsy.oauth.fernet_key', default='')
        self.assertIsInstance(value, str)

    def test_api_log_source_includes_scope_validation(self):
        """Test that etsy.api.log source Selection includes 'scope_validation'.

        The source field is a Selection; D-P1-10-05 extends the enum.
        """
        source_field = self.env['etsy.api.log']._fields['source']

        # source must be a Selection field
        self.assertEqual(
            source_field.type,
            'selection',
            "etsy.api.log.source must be a Selection field"
        )

        # Extract the selection tuples
        selection_values = [choice[0] for choice in source_field.selection]

        # 'scope_validation' must be in the selection
        self.assertIn(
            'scope_validation',
            selection_values,
            "etsy.api.log.source must include 'scope_validation' choice"
        )

    def test_etsy_shop_token_columns_unchanged_after_p1_10(self):
        """Test that the 3 token columns still exist with system ACL (no regression).

        Per D-P1-10-01, columns are NOT encrypted at the field level; helpers
        route access through `_get_access_token()` / `_set_access_token()`.
        Columns remain plain Char fields with groups='base.group_system'.
        """
        shop_model = self.env['etsy.shop']

        # Verify the three token fields exist
        self.assertIn('etsy_oauth_access_token', shop_model._fields)
        self.assertIn('etsy_oauth_refresh_token', shop_model._fields)
        self.assertIn('etsy_oauth_token_expires_at', shop_model._fields)

        # Verify they have system-only ACL
        access_field = shop_model._fields['etsy_oauth_access_token']
        refresh_field = shop_model._fields['etsy_oauth_refresh_token']
        expires_field = shop_model._fields['etsy_oauth_token_expires_at']

        # Fields should have groups restriction
        self.assertIsNotNone(
            access_field.groups,
            "etsy_oauth_access_token must have groups ACL"
        )
        self.assertIsNotNone(
            refresh_field.groups,
            "etsy_oauth_refresh_token must have groups ACL"
        )
        # Note: expires_field may not have groups (depends on model definition)

    def test_token_column_holds_ciphertext_after_write(self):
        """Test that after _set_access_token() writes, the raw column holds Fernet ciphertext.

        Phase 1 verification: direct SQL query shows the column value starts
        with 'gAAAAA' (Fernet token base64 prefix). This proves encryption
        happened at the ORM layer.

        This test will FAIL in RED phase because _set_access_token() doesn't
        exist yet. In GREEN phase, the helper will exist and encrypt plaintext.
        """
        # Create a test shop
        shop = self.env['etsy.shop'].create({
            'name': 'Test Shop for Encryption Verify',
        })

        try:
            # Import the helper (will fail in RED phase — that's expected)
            from odoo.addons.etsy_integration.models.etsy_shop import EtsyShop

            # Call the helper to set a plaintext token
            shop._set_access_token('plaintext_token_for_testing_12345')

            # Query the raw column value
            self.env.cr.execute(
                "SELECT etsy_oauth_access_token FROM etsy_shop WHERE id = %s",
                (shop.id,)
            )
            row = self.env.cr.fetchone()
            self.assertIsNotNone(row, "Shop record should exist after write")

            ciphertext = row[0]
            self.assertIsNotNone(ciphertext, "Ciphertext should not be None")

            # Fernet tokens always start with 'gAAAAA' (base64 encoding of the
            # Fernet format identifier 0x80 0x00 0x00)
            self.assertTrue(
                ciphertext.startswith('gAAAAA'),
                f"Ciphertext must start with 'gAAAAA' (Fernet marker), got: {ciphertext[:10]}"
            )
        except (AttributeError, ImportError):
            # If the helper doesn't exist yet, this test will fail in RED phase
            self.fail("_set_access_token() helper not yet implemented (RED OK)")
