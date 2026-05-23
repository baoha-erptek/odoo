"""
Phase 1: Database-level verification for P-HUB-WIZARD (Spec 009 US3).

Verifies the product.creation.wizard transient model is registered and the
expected columns exist on its underlying table.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1HubWizardDB(TransactionCase):

    def test_wizard_model_registered(self):
        self.assertIn(
            'product.creation.wizard',
            self.env.registry,
            "product.creation.wizard transient model must be registered",
        )

    def test_wizard_is_transient(self):
        wizard_cls = self.env['product.creation.wizard']
        self.assertTrue(
            wizard_cls._transient,
            "product.creation.wizard must be a TransientModel",
        )

    def test_wizard_table_columns(self):
        for column in (
            'name',
            'default_code',
            'categ_id',
            'x_listing_price',
            'x_shipping_price_internal',
            'x_additional_cost',
            'x_gearment_sku',
        ):
            self.env.cr.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'product_creation_wizard'
                  AND column_name = %s
                """,
                (column,),
            )
            self.assertIsNotNone(
                self.env.cr.fetchone(),
                "product_creation_wizard.%s column must exist" % column,
            )

    def test_wizard_channel_m2m_join_table(self):
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name LIKE '%creation_wizard%channel%'
            )
        """)
        self.assertTrue(
            self.env.cr.fetchone()[0],
            "M2M join table for wizard channel applicability must exist",
        )
