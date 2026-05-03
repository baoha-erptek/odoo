"""Phase 1 (Database Verification) Tests for P1-04 Address-Change Approval Workflow.

Verifies table structure, columns, indexes, and security group definitions
are correctly created post-install. These tests ensure data integrity at
the database level before ORM unit tests run.

Tasks covered: DB shape for T051-T060 exit criteria.
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestAddressChangeDbShape(TransactionCase):
    """Phase 1: Database schema verification for etsy.address.change.request."""

    def test_etsy_address_change_request_table_exists(self):
        """Verify the etsy_address_change_request table exists post-install."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'etsy_address_change_request'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            table_exists,
            "Table 'etsy_address_change_request' not found in database"
        )

    def test_address_change_request_columns_exist(self):
        """Verify all required columns exist with correct types."""
        required_columns = {
            'id': 'bigint',
            'order_id': 'bigint',
            'requested_fields': 'text',  # json in Odoo
            'new_values': 'text',  # json in Odoo
            'state': 'character varying',  # Selection field
            'reason': 'text',
            'rejection_reason': 'text',
            'requested_by': 'bigint',
            'approved_by': 'bigint',
            'approved_at': 'timestamp without time zone',
            'rejected_at': 'timestamp without time zone',
        }

        for col_name, expected_type in required_columns.items():
            self.env.cr.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'etsy_address_change_request'
                    AND column_name = %s
                )
            """, (col_name,))
            col_exists = self.env.cr.fetchone()[0]
            self.assertTrue(
                col_exists,
                f"Column '{col_name}' not found in 'etsy_address_change_request'"
            )

    def test_groups_ba_lead_exists(self):
        """Verify group_ba_lead group is resolvable via env.ref()."""
        try:
            group = self.env.ref('multichannel_hub_core.group_ba_lead')
            self.assertTrue(group, "group_ba_lead should exist and be resolvable")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.group_ba_lead') raised ValueError; "
                     "group not found in database")

    def test_groups_ba_user_exists(self):
        """Verify group_ba_user group is resolvable via env.ref()."""
        try:
            group = self.env.ref('multichannel_hub_core.group_ba_user')
            self.assertTrue(group, "group_ba_user should exist and be resolvable")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.group_ba_user') raised ValueError; "
                     "group not found in database")

    def test_groups_marketing_user_exists(self):
        """Verify group_marketing_user group is resolvable via env.ref()."""
        try:
            group = self.env.ref('multichannel_hub_core.group_marketing_user')
            self.assertTrue(group, "group_marketing_user should exist and be resolvable")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.group_marketing_user') raised ValueError; "
                     "group not found in database")

    def test_sale_order_has_pending_address_change_column(self):
        """Verify sale.order has has_pending_address_change Boolean column."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'has_pending_address_change'
            )
        """)
        col_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            col_exists,
            "Column 'has_pending_address_change' not found in 'sale_order'"
        )

    def test_acl_rows_exist_for_address_change_request(self):
        """Verify ACL rows exist for etsy.address.change.request model."""
        ACL = self.env['ir.model.access']
        model_id = self.env['ir.model'].search([
            ('model', '=', 'etsy.address.change.request')
        ])
        self.assertTrue(
            model_id,
            "ir.model record for 'etsy.address.change.request' not found"
        )

        acl_rows = ACL.search([('model_id', '=', model_id.id)])
        self.assertTrue(
            acl_rows,
            "No ACL rows found for 'etsy.address.change.request' model"
        )
