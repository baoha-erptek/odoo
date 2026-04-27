"""Phase 1: Module installation verification test.

This test verifies that the multichannel_hub_fulfillment module
installs successfully and is registered in ir.module.module.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultichannelHubFulfillmentInstall(TransactionCase):
    """Phase 1: Verify module installation."""

    def test_module_record_exists_and_installed(self):
        """Module is registered and installed in ir.module.module."""
        module_record = self.env['ir.module.module'].search([
            ('name', '=', 'multichannel_hub_fulfillment')
        ])

        self.assertEqual(
            len(module_record),
            1,
            "Module multichannel_hub_fulfillment should exist exactly once"
        )

        self.assertEqual(
            module_record.state,
            'installed',
            "Module multichannel_hub_fulfillment should be in installed state"
        )
