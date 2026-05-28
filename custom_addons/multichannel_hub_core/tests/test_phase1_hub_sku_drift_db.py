"""
Phase 1: DB-level verification for P-HUB-SKU-DRIFT (Spec 009 US4) — mhc-half.

Verifies the canonicalisation wizard transient model is registered and that
`product.template.x_sku_legacy` is a settable Char column at the DB layer.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1HubSkuDriftDB(TransactionCase):

    def test_canonicalise_wizard_registered(self):
        self.assertIn(
            'product.sku.canonicalise.wizard',
            self.env.registry,
            "product.sku.canonicalise.wizard TransientModel must be registered",
        )

    def test_canonicalise_wizard_is_transient(self):
        self.assertTrue(
            self.env['product.sku.canonicalise.wizard']._transient,
            "canonicalise wizard must be transient",
        )

    def test_canonicalise_wizard_product_field(self):
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_sku_canonicalise_wizard'
              AND column_name = 'product_tmpl_id'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "wizard.product_tmpl_id column must exist",
        )

    def test_x_sku_legacy_settable_via_sql(self):
        """x_sku_legacy is a plain Char — settable directly at DB layer."""
        tmpl = self.env['product.template'].create({
            'name': 'Drift SQL Test',
            'default_code': 'LEGACY-001',
        })
        self.env.cr.execute(
            "UPDATE product_template SET x_sku_legacy = %s WHERE id = %s",
            ('LEGACY-001', tmpl.id),
        )
        self.env.cr.execute(
            "SELECT x_sku_legacy FROM product_template WHERE id = %s",
            (tmpl.id,),
        )
        self.assertEqual(self.env.cr.fetchone()[0], 'LEGACY-001')
