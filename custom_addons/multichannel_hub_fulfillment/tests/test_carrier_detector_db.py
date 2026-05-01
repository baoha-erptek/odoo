"""P2-02 Phase 1 — DB schema verification for carrier auto-detection."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCarrierDetectorDB(TransactionCase):

    def test_other_carrier_seed_exists(self):
        other = self.env['shipping.carrier'].search(
            [('code', '=', 'other')], limit=1)
        self.assertTrue(other, "P2-02 fallback carrier 'other' must be seeded")
        self.assertTrue(other.is_active)

    def test_tracking_import_line_needs_review_column(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='tracking_import_line' AND column_name='needs_review'
        """)
        self.assertTrue(self.env.cr.fetchone(),
                        "tracking_import_line.needs_review column must exist")

    def test_shipping_carrier_tracking_prefix_regex_column(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='shipping_carrier'
              AND column_name='tracking_prefix_regex'
        """)
        self.assertTrue(self.env.cr.fetchone())
