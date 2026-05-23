"""Phase 1 DB tests for P-HUB-XLS-PARSE-MODELS (Spec 010 T006).

Verifies the 3 new catalog staging tables + UNIQUE mirrors + sequence load.
"""

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('at_install', '-post_install')
class TestPhase1CatalogDB(TransactionCase):

    def test_import_run_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='product_catalog_import_run')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_import_line_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='product_catalog_import_line')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_sheet_fingerprint_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='product_catalog_sheet_fingerprint')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_c_cil_001_unique_mirror_present(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname='uniq_product_catalog_import_line_run_sheet_row'
        """)
        self.assertIsNotNone(self.env.cr.fetchone())

    def test_c_csf_001_unique_mirror_present(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname='uniq_product_catalog_sheet_fingerprint_sheet_sha'
        """)
        self.assertIsNotNone(self.env.cr.fetchone())

    def test_c_cil_001_enforced(self):
        Run = self.env['product.catalog.import.run']
        Line = self.env['product.catalog.import.line']
        run = Run.create({
            'mode': 'dry_run', 'source_kind': 'manual_upload',
            'source_path': '/tmp/x.xlsx',
        })
        Line.create({
            'run_id': run.id, 'sheet_name': 'A', 'row_number': 1,
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Line.create({
                    'run_id': run.id, 'sheet_name': 'A', 'row_number': 1,
                })

    def test_sequence_loaded(self):
        seq = self.env['ir.sequence'].sudo().search([
            ('code', '=', 'product.catalog.import.run'),
        ], limit=1)
        self.assertTrue(seq, "catalog import run sequence must be loaded")

    def test_import_run_default_name_uses_sequence(self):
        run = self.env['product.catalog.import.run'].create({
            'mode': 'dry_run', 'source_kind': 'manual_upload',
            'source_path': '/tmp/x.xlsx',
        })
        self.assertTrue(run.name)
        self.assertNotEqual(run.name, 'CAT-IMP-NEW')
