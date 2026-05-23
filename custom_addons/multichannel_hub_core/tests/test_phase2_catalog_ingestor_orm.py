"""Phase 2 ORM tests for P-HUB-XLS-INGEST core (Spec 010 T012).

Pricelist seed (T011/US5) and parser integration deferred.
"""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_core.services.catalog_ingestor import upsert


@tagged('post_install', '-at_install')
class TestCatalogIngestorORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['product.catalog.import.run']
        cls.Line = cls.env['product.catalog.import.line']
        cls.Template = cls.env['product.template']

    def _make_run(self):
        return self.Run.create({
            'mode': 'commit', 'source_kind': 'manual_upload',
            'source_path': '/tmp/test.xlsx',
        })

    def _make_line(self, run, sheet='Accessories', row=1, sku='ING-1',
                   name='Custom Ring Dish 3.5"', price_usd=49.99,
                   shipping=2.5):
        return self.Line.create({
            'run_id': run.id, 'sheet_name': sheet, 'row_number': row,
            'sku': sku, 'name': name,
            'price_usd': price_usd, 'shipping_fee': shipping,
        })

    def test_upsert_creates_new_template(self):
        run = self._make_run()
        line = self._make_line(run, sku='NEW-1')
        counters = upsert(self.env, run, line)
        self.assertEqual(counters['upserted'], 1)
        tmpl = self.Template.search([('default_code', '=', 'NEW-1')], limit=1)
        self.assertTrue(tmpl)
        self.assertEqual(tmpl.x_listing_price, 49.99)
        self.assertEqual(line.state, 'upserted')
        self.assertEqual(line.target_product_id, tmpl)

    def test_upsert_updates_existing_template_excel_wins(self):
        run = self._make_run()
        existing = self.Template.create({
            'name': 'Old name', 'default_code': 'UPD-1',
            'x_listing_price': 10.0,
        })
        line = self._make_line(run, sku='UPD-1', name='Excel name', price_usd=99.99)
        upsert(self.env, run, line)
        existing.invalidate_recordset()
        self.assertEqual(existing.name, 'Excel name')
        self.assertEqual(existing.x_listing_price, 99.99)

    def test_upsert_preserves_x_channel_applicability(self):
        """ADR-014 §3: Odoo wins on x_channel_applicability_ids."""
        run = self._make_run()
        ChannelAll = self.env['multichannel.sales.channel'].with_context(active_test=False)
        etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        tmpl = self.Template.create({
            'name': 'preserve test', 'default_code': 'PRES-1',
        })
        tmpl.x_channel_applicability_ids = [(4, etsy.id)]
        line = self._make_line(run, sku='PRES-1', name='Excel-updated name')
        upsert(self.env, run, line)
        tmpl.invalidate_recordset()
        self.assertIn(etsy, tmpl.x_channel_applicability_ids,
                       "x_channel_applicability_ids must NOT be cleared by upsert")
        self.assertEqual(tmpl.name, 'Excel-updated name')

    def test_upsert_unchanged_line_marks_unchanged(self):
        run = self._make_run()
        self.Template.create({
            'name': 'Same name', 'default_code': 'UNCH-1',
            'x_listing_price': 5.0, 'x_shipping_price_internal': 1.0,
        })
        line = self._make_line(run, sku='UNCH-1', name='Same name',
                                price_usd=5.0, shipping=1.0)
        counters = upsert(self.env, run, line)
        self.assertEqual(counters['unchanged'], 1)
        self.assertEqual(counters['upserted'], 0)

    def test_upsert_missing_sku_marks_error(self):
        run = self._make_run()
        line = self._make_line(run, sku='')
        counters = upsert(self.env, run, line)
        self.assertEqual(counters['error'], 1)
        self.assertEqual(line.state, 'error')
        self.assertEqual(line.error_kind, 'upsert')
        self.assertIn('SKU', line.error_message)

    def test_upsert_per_row_savepoint_other_lines_succeed(self):
        run = self._make_run()
        good = self._make_line(run, row=1, sku='GOOD-1', name='good 1')
        bad = self._make_line(run, row=2, sku='')  # missing SKU → error
        also_good = self._make_line(run, row=3, sku='GOOD-2', name='good 2')
        counters = upsert(self.env, run, good + bad + also_good)
        self.assertEqual(counters['upserted'], 2)
        self.assertEqual(counters['error'], 1)
        self.assertEqual(good.state, 'upserted')
        self.assertEqual(bad.state, 'error')
        self.assertEqual(also_good.state, 'upserted')
