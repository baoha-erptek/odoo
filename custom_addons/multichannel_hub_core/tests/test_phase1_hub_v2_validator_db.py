"""
Phase 1: Database-level verification for P-HUB-V2-VALIDATE-ON-CREATE (Spec 009 §7).

Verifies the ICP seed row that gates SKU v2.1 enforce mode:
- ir.config_parameter row with key 'multichannel_hub.sku_v2_enforce_mode' exists
- Default value is 'soft' (D-V2-2 DECIDED 2026-05-26)

Direct SQL via self.env.cr.execute — independent of ORM caches.

Spec 009 T065. RED before T061 ICP seed XML lands.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestHubV2ValidatorDb(TransactionCase):

    def test_icp_sku_v2_enforce_mode_row_present_and_soft(self):
        """ICP row must exist post-install with default value 'soft' (D-V2-2)."""
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s",
            ('multichannel_hub.sku_v2_enforce_mode',),
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "ICP key 'multichannel_hub.sku_v2_enforce_mode' must be seeded "
            "by data/sku_v2_enforce_mode_seed.xml (T061).",
        )
        self.assertEqual(
            row[0],
            'soft',
            "Default enforce mode must be 'soft' per D-V2-2 (SKU_GRAMMAR.md §12).",
        )
