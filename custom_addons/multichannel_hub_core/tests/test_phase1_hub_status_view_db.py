"""
Phase 1: DB-level verification for P-HUB-STATUS-VIEW (Spec 009 US5).

Checks that the product.template form view extension is registered and
that the `x_published_channel_count` computed field column exists.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1HubStatusViewDB(TransactionCase):

    def test_x_published_channel_count_column_exists(self):
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_template'
              AND column_name = 'x_published_channel_count'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "product_template.x_published_channel_count column must exist",
        )

    def test_status_view_extension_registered(self):
        view = self.env.ref(
            'multichannel_hub_core.product_template_form_hub_status_tab',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "Channels tab inheriting view must be registered")
        self.assertEqual(view.model, 'product.template')
        self.assertEqual(view.mode, 'extension')
