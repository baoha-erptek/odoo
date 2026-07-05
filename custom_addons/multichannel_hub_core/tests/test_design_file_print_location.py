"""P-GEAR-PRINT-SIDES — RED tests for design.file.print_location (mhc side).

Two-Phase: Phase 1 verifies the column landed in the DB; Phase 2 verifies the
selection contract (front/back, NO hard default — unset means "auto/positional"
so legacy rows and single-file lines keep working) and that both seeders stamp
the side from their Front/Back role.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'design_print_location')
class TestPrintLocationField(TransactionCase):

    def test_phase1_column_exists(self):
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'design_file'
              AND column_name = 'print_location'
        """)
        self.assertTrue(self.env.cr.fetchone(),
                        "design_file.print_location column missing")

    def test_selection_values_are_front_back(self):
        field = self.env['design.file']._fields['print_location']
        self.assertEqual([v for v, _l in field.selection], ['front', 'back'])

    def test_no_hard_default_unset_means_auto(self):
        order = self._make_order()
        df = self.env['design.file'].create({
            'name': 'no side chosen',
            'order_line_id': order.order_line[0].id,
            'storage_mode': 'url',
            'file_url': 'https://x/a.png',
        })
        self.assertFalse(df.print_location)

    def test_live_seeder_stamps_sides_from_roles(self):
        order = self._make_order(
            design_link_front='https://x/front.png',
            design_link_back='https://x/back.png',
        )
        created = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='api_ingest')
        self.assertEqual(created, 2)
        files = order.order_line.design_file_ids
        by_url = {f.file_url: f.print_location for f in files}
        self.assertEqual(by_url['https://x/front.png'], 'front')
        self.assertEqual(by_url['https://x/back.png'], 'back')

    def _make_order(self, **line_vals):
        partner = self.env['res.partner'].create({'name': 'Seed Buyer'})
        product = self.env['product.product'].create({
            'name': 'Seed Tee', 'type': 'consu', 'list_price': 5.0,
        })
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                **line_vals,
            })],
        })
