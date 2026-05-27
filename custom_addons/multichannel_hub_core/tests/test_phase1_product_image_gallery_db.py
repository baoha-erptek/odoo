"""Phase 1 DB tests for P-PUB-MULTI-IMAGE custom mini-gallery (MP006).

Owner pivoted away from website_sale's product.image (would pull 10+
unwanted modules). Custom model `multichannel.product.image` lives in
multichannel_hub_core with channel-agnostic naming.

Verifies table + columns + FK + sequence default + index using
information_schema and pg_indexes (regex-tolerant per gotcha #144 —
PG index names use DOUBLE underscores in Odoo 19).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase1ProductImageGalleryDB(TransactionCase):

    TABLE = 'multichannel_product_image'

    def _row(self, sql, *params):
        self.env.cr.execute(sql, params)
        return self.env.cr.fetchone()

    def _rows(self, sql, *params):
        self.env.cr.execute(sql, params)
        return self.env.cr.fetchall()

    def test_table_exists(self):
        row = self._row(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=%s)",
            self.TABLE,
        )
        self.assertTrue(row[0], "multichannel_product_image table must exist")

    def test_product_tmpl_id_column_not_null(self):
        row = self._row(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name=%s AND column_name='product_tmpl_id'",
            self.TABLE,
        )
        self.assertIsNotNone(row, "product_tmpl_id column missing")
        self.assertEqual(row[0], 'NO', "product_tmpl_id must be NOT NULL")

    def test_product_tmpl_id_fk_exists(self):
        rows = self._rows(
            "SELECT tc.constraint_name "
            "FROM information_schema.table_constraints tc "
            "WHERE tc.table_name=%s AND tc.constraint_type='FOREIGN KEY'",
            self.TABLE,
        )
        self.assertTrue(
            any('product_tmpl' in r[0] for r in rows),
            f"Expected FK on product_tmpl_id, found: {rows}",
        )

    def test_sequence_column_exists(self):
        row = self._row(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name=%s AND column_name='sequence'",
            self.TABLE,
        )
        self.assertIsNotNone(row, "sequence column missing")
        self.assertEqual(row[0], 'integer')

    def test_image_1920_field_registered(self):
        # fields.Image() is attachment-backed; no inline column. Verify the
        # field is registered on the model instead.
        row = self._row(
            "SELECT ttype FROM ir_model_fields "
            "WHERE model=%s AND name='image_1920'",
            'multichannel.product.image',
        )
        self.assertIsNotNone(row, "image_1920 field not registered on model")
        self.assertEqual(row[0], 'binary')

    def test_product_tmpl_id_index_exists(self):
        rows = self._rows(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename=%s AND indexname LIKE %s",
            self.TABLE, '%product_tmpl_id%',
        )
        self.assertTrue(
            len(rows) > 0,
            "Expected an index covering product_tmpl_id, found none",
        )
