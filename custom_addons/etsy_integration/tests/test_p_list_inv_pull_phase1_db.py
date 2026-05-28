"""Phase 1 DB tests for P-LIST-INV-PULL — variant inventory snapshot
(Spec 008 US2/US3/US4).

- etsy_listing_product table + columns
- C-LPROD-001 UNIQUE(listing_id, etsy_product_id) enforced + named
- init() raw-SQL mirror idempotent (Odoo 19 _sql_constraints inert)
- product_product.etsy_listing_variant_id FK column exists
- ACL rows for model_etsy_listing_product

PHASE: RED (implementation does not exist yet)
"""
import logging

import psycopg2
from odoo.tests.common import SingleTransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p_list_inv_pull')
class TestPListInvPullSchema(SingleTransactionCase):

    def test_table_and_columns_exist(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'etsy_listing_product'
        """)
        cols = {r[0] for r in self.env.cr.fetchall()}
        expected = {
            'listing_id', 'etsy_product_id', 'sku', 'property_values',
            'quantity', 'price', 'product_id', 'is_active', 'last_synced_at',
        }
        missing = expected - cols
        self.assertFalse(missing, "etsy_listing_product missing: %s" % missing)

    def test_product_product_fk_column_exists(self):
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'product_product'
            AND column_name = 'etsy_listing_variant_id'
        """)
        self.assertTrue(
            self.env.cr.fetchone(),
            "product_product.etsy_listing_variant_id column missing",
        )

    def test_c_lprod_001_unique_named_and_enforced(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'etsy_listing_product_listing_prod_uniq'
        """)
        self.assertTrue(
            self.env.cr.fetchone(),
            "C-LPROD-001 constraint missing",
        )
        shop = self.env['etsy.shop'].create({'name': 'INV DB Shop'})
        listing = self.env['etsy.listing'].create({
            'shop_id': shop.id, 'etsy_listing_id': 'L-INV',
            'title': 'L', 'state': 'active',
        })
        self.env['etsy.listing.product'].create({
            'listing_id': listing.id, 'etsy_product_id': 'P-DUP',
        })
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['etsy.listing.product'].create({
                    'listing_id': listing.id, 'etsy_product_id': 'P-DUP',
                })

    def test_init_mirror_idempotent(self):
        model = self.env['etsy.listing.product']
        model.init()
        model.init()

    def test_acl_rows_exist(self):
        self.env.cr.execute("""
            SELECT a.perm_read, a.perm_write
            FROM ir_model_access a
            JOIN ir_model m ON m.id = a.model_id
            WHERE m.model = 'etsy.listing.product'
        """)
        rows = self.env.cr.fetchall()
        self.assertTrue(rows, "no ACL rows for etsy.listing.product")
        self.assertTrue(any(r[1] for r in rows),
                        "no group with write access (system row missing)")
