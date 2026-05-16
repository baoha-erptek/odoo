"""Phase 1 DB tests for P-LIST-PULL — Etsy listing metadata ingest (Spec 008 US1).

Schema / DB-integrity verification without relying on service implementation:
- etsy_listing table + columns exist
- C-LIST-001 UNIQUE(shop_id, etsy_listing_id) enforced + named
- init() raw-SQL constraint mirror is idempotent (re-run safe)
- ir.cron 'cron_etsy_listing_sync' exists with 5-minute schedule
- ir.model.access rows exist for model_etsy_listing

PHASE: RED (implementation does not exist yet)
"""
import logging

import psycopg2
from odoo.tests.common import SingleTransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p_list_pull')
class TestPListPullSchema(SingleTransactionCase):
    """Phase 1: etsy.listing schema + constraint + cron + ACL."""

    def test_etsy_listing_table_and_columns_exist(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_listing'
        """)
        cols = {r[0] for r in self.env.cr.fetchall()}
        expected = {
            'shop_id', 'etsy_listing_id', 'title', 'state', 'description',
            'url', 'price', 'quantity', 'created_at', 'last_modified',
            'last_synced_at', 'is_active',
        }
        missing = expected - cols
        self.assertFalse(missing, "etsy_listing missing columns: %s" % missing)

    def test_c_list_001_unique_constraint_named_and_enforced(self):
        """C-LIST-001 UNIQUE(shop_id, etsy_listing_id) present + enforced."""
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'etsy_listing_shop_listing_uniq'
        """)
        self.assertTrue(
            self.env.cr.fetchone(),
            "C-LIST-001 constraint 'etsy_listing_shop_listing_uniq' missing",
        )
        shop = self.env['etsy.shop'].create({'name': 'P-LIST-PULL DB Shop'})
        self.env['etsy.listing'].create({
            'shop_id': shop.id, 'etsy_listing_id': 'L-DUP',
            'title': 'A', 'state': 'active',
        })
        with self.assertRaises(psycopg2.IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['etsy.listing'].create({
                    'shop_id': shop.id, 'etsy_listing_id': 'L-DUP',
                    'title': 'B', 'state': 'active',
                })

    def test_init_constraint_mirror_is_idempotent(self):
        """init() must be safe to re-run (drift template — pg_constraint
        IF NOT EXISTS pre-check, not EXCEPTION clause)."""
        model = self.env['etsy.listing']
        model.init()
        model.init()  # second call must not raise

    def test_cron_etsy_listing_sync_exists_5min(self):
        cron = self.env.ref(
            'etsy_integration.cron_etsy_listing_sync',
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "cron_etsy_listing_sync record missing")
        self.assertEqual(cron.interval_number, 5)
        self.assertEqual(cron.interval_type, 'minutes')
        self.assertIn('_cron_sync_listings', cron.code)

    def test_acl_rows_for_etsy_listing(self):
        self.env.cr.execute("""
            SELECT g.id IS NOT NULL AS has_group, a.perm_read, a.perm_write
            FROM ir_model_access a
            JOIN ir_model m ON m.id = a.model_id
            LEFT JOIN res_groups g ON g.id = a.group_id
            WHERE m.model = 'etsy.listing'
        """)
        rows = self.env.cr.fetchall()
        self.assertTrue(rows, "no ir.model.access rows for etsy.listing")
        self.assertTrue(
            any(r[2] for r in rows),
            "etsy.listing has no group with write access (system row missing)",
        )
