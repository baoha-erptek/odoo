"""
Phase 1: Database-level verification for P-HUB-PROD-MODEL (Spec 009).

Verifies the underlying PostgreSQL schema for the central product hub:
- multichannel_sales_channel table + columns + UNIQUE(code) mirror + indexes
- product_channel_status table + columns + UNIQUE(product_tmpl_id, channel_id) mirror
- product_template new columns (excluding M2M / O2M which are JOIN tables)
- seed channels loaded with correct active flags

Tests use direct SQL via self.env.cr.execute to verify schema state at the
lowest level, independent of ORM machinery.
"""

from psycopg2 import IntegrityError, errors as pg_errors

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('at_install', '-post_install')
class TestPhase1HubProductModelDB(TransactionCase):
    """Direct PostgreSQL verification for P-HUB-PROD-MODEL schema."""

    # ------------------------------------------------------------------
    # multichannel.sales.channel
    # ------------------------------------------------------------------

    def test_multichannel_sales_channel_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'multichannel_sales_channel'
            )
        """)
        self.assertTrue(
            self.env.cr.fetchone()[0],
            "multichannel_sales_channel table must exist",
        )

    def test_multichannel_sales_channel_columns(self):
        expected = {
            'code': 'character varying',
            'name': 'jsonb',  # translatable Char → jsonb in Odoo 19
            'sequence': 'integer',
            'active': 'boolean',
            'description': 'text',
        }
        for column, _expected_type in expected.items():
            self.env.cr.execute(
                """
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'multichannel_sales_channel'
                  AND column_name = %s
                """,
                (column,),
            )
            row = self.env.cr.fetchone()
            self.assertIsNotNone(
                row,
                "multichannel_sales_channel.%s column must exist" % column,
            )

    def test_unique_constraint_channel_code_mirrored(self):
        """C-CH-001 UNIQUE(code) mirror from init() must be present in pg_constraint."""
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uniq_multichannel_sales_channel_code'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "C-CH-001 UNIQUE(code) constraint must be mirrored in pg_constraint",
        )

    def test_unique_constraint_channel_code_enforced(self):
        """Inserting a duplicate code must raise IntegrityError."""
        Channel = self.env['multichannel.sales.channel']
        Channel.create({'code': 'dup_test', 'name': 'Dup Test 1'})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Channel.create({'code': 'dup_test', 'name': 'Dup Test 2'})

    def test_channel_seed_loaded(self):
        """Seed XML must load 3 channels: etsy active, amazon+website inactive."""
        Channel = self.env['multichannel.sales.channel'].with_context(active_test=False)
        etsy = Channel.search([('code', '=', 'etsy')])
        amazon = Channel.search([('code', '=', 'amazon')])
        website = Channel.search([('code', '=', 'website')])
        self.assertEqual(len(etsy), 1, "etsy channel seed missing")
        self.assertEqual(len(amazon), 1, "amazon channel seed missing")
        self.assertEqual(len(website), 1, "website channel seed missing")
        self.assertTrue(etsy.active, "etsy channel must be active")
        self.assertFalse(amazon.active, "amazon channel must be inactive (Phase 5)")
        self.assertFalse(website.active, "website channel must be inactive (Phase 5)")

    # ------------------------------------------------------------------
    # product.channel.status
    # ------------------------------------------------------------------

    def test_product_channel_status_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'product_channel_status'
            )
        """)
        self.assertTrue(
            self.env.cr.fetchone()[0],
            "product_channel_status table must exist",
        )

    def test_product_channel_status_columns(self):
        for column in (
            'product_tmpl_id',
            'channel_id',
            'state',
            'external_ref',
            'last_sync_at',
            'last_sync_error',
        ):
            self.env.cr.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'product_channel_status'
                  AND column_name = %s
                """,
                (column,),
            )
            self.assertIsNotNone(
                self.env.cr.fetchone(),
                "product_channel_status.%s column must exist" % column,
            )

    def test_unique_constraint_product_channel_mirrored(self):
        """C-PCS-001 UNIQUE(product_tmpl_id, channel_id) mirror."""
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uniq_product_channel_status_product_channel'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "C-PCS-001 UNIQUE constraint must be mirrored in pg_constraint",
        )

    def test_product_channel_status_fk_cascade_product(self):
        """FK product_tmpl_id must cascade on delete (template removal)."""
        self.env.cr.execute("""
            SELECT confdeltype FROM pg_constraint
            WHERE conrelid = 'product_channel_status'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%product_tmpl_id%'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "product_tmpl_id FK must exist")
        self.assertEqual(row[0], 'c', "product_tmpl_id FK must be CASCADE")

    def test_product_channel_status_fk_restrict_channel(self):
        """FK channel_id must restrict on delete (cannot delete a channel that has statuses)."""
        self.env.cr.execute("""
            SELECT confdeltype FROM pg_constraint
            WHERE conrelid = 'product_channel_status'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%channel_id%'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "channel_id FK must exist")
        self.assertEqual(row[0], 'r', "channel_id FK must be RESTRICT")

    # ------------------------------------------------------------------
    # product.template extensions
    # ------------------------------------------------------------------

    def test_product_template_new_columns_exist(self):
        for column in (
            'x_listing_price',
            'x_shipping_price_internal',
            'x_additional_cost',
            'x_unit_margin',
            'x_sku_v2_suggested',
            'x_sku_v2_status',
            'x_sku_legacy',
        ):
            self.env.cr.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'product_template'
                  AND column_name = %s
                """,
                (column,),
            )
            self.assertIsNotNone(
                self.env.cr.fetchone(),
                "product_template.%s column must exist" % column,
            )

    def test_product_template_m2m_join_table_exists(self):
        """x_channel_applicability_ids M2M creates a JOIN table."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name LIKE '%channel_applicability%'
            )
        """)
        self.assertTrue(
            self.env.cr.fetchone()[0],
            "M2M JOIN table for x_channel_applicability_ids must exist",
        )
