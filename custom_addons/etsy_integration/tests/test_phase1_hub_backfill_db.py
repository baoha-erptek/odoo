"""Phase 1 DB tests for P-HUB-BACKFILL (Spec 009 US6)."""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1HubBackfillDB(TransactionCase):

    def test_wizard_registered(self):
        self.assertIn(
            'etsy.listing.backfill.wizard',
            self.env.registry,
            "backfill wizard must be registered",
        )

    def test_wizard_is_transient(self):
        self.assertTrue(
            self.env['etsy.listing.backfill.wizard']._transient,
            "backfill wizard must be transient",
        )
