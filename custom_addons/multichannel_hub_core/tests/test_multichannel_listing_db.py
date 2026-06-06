"""Phase 1 DB tests for `multichannel.listing` (P-LIST-MODEL).

Direct PostgreSQL probes — does NOT exercise the ORM. Locks the
schema contracts: table existence, FK shape, UNIQUE index, ACL CSV
rows present after install.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultichannelListingSchema(TransactionCase):
    def test_table_exists(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'multichannel_listing'
        """)
        self.assertIsNotNone(self.env.cr.fetchone(),
            'multichannel_listing table must be created on install')

    def test_fk_to_product_template_cascade(self):
        self.env.cr.execute("""
            SELECT confdeltype FROM pg_constraint
            WHERE conrelid = 'multichannel_listing'::regclass
              AND confrelid = 'product_template'::regclass
        """)
        rows = self.env.cr.fetchall()
        self.assertEqual(len(rows), 1,
            'exactly one FK from multichannel_listing → product_template')
        # 'c' = CASCADE per PG documentation
        self.assertEqual(rows[0][0], 'c',
            'FK to product.template must be ondelete=cascade')

    def test_unique_index_present(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'multichannel_listing'
              AND indexname = 'uniq_multichannel_listing_tmpl_channel_shop'
        """)
        self.assertIsNotNone(self.env.cr.fetchone(),
            'init() must create unique index on (tmpl, channel, COALESCE(shop_ref, \'\'))')


@tagged('post_install', '-at_install')
class TestMultichannelListingACL(TransactionCase):
    def test_acl_rows_for_each_group(self):
        IMA = self.env['ir.model.access']
        accesses = IMA.search([
            ('model_id.model', '=', 'multichannel.listing'),
        ])
        group_ids = set(accesses.mapped('group_id.id'))
        self.assertIn(
            self.env.ref('multichannel_hub_core.group_marketing_user').id,
            group_ids,
            'group_marketing_user must have an access row',
        )
        self.assertIn(
            self.env.ref('multichannel_hub_core.group_ba_user').id,
            group_ids,
            'group_ba_user must have an access row',
        )
        self.assertIn(
            self.env.ref('multichannel_hub_core.group_ba_lead').id,
            group_ids,
            'group_ba_lead must have an access row',
        )

    def test_ba_user_is_read_only(self):
        access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'multichannel.listing'),
            ('group_id', '=',
             self.env.ref('multichannel_hub_core.group_ba_user').id),
        ], limit=1)
        self.assertTrue(access, 'BA User ACL must exist')
        self.assertTrue(access.perm_read)
        self.assertFalse(access.perm_write, 'BA User must be read-only')
        self.assertFalse(access.perm_create, 'BA User must be read-only')
        self.assertFalse(access.perm_unlink, 'BA User must be read-only')

    def test_marketing_is_rw(self):
        access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'multichannel.listing'),
            ('group_id', '=',
             self.env.ref('multichannel_hub_core.group_marketing_user').id),
        ], limit=1)
        self.assertTrue(access, 'Marketing ACL must exist')
        self.assertTrue(access.perm_read)
        self.assertTrue(access.perm_write)
        self.assertTrue(access.perm_create)
        self.assertTrue(access.perm_unlink, 'Marketing must own listings RW')
