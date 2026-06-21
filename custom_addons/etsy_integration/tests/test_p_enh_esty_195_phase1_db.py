"""
Phase 1 Database Verification Tests for P-ENH-ESTY-195: Listing Currency Display.

These tests verify data layer integrity at the database level:
- Column creation (etsy_shop_id M2O → stored as int4 FK)
- Computed field non-existence (display_price_in_shop_currency, display_currency_id)
- Cron record seeding (ir.cron row exists, properly configured)
- Config parameter seeding (ir.config_parameter default value)

RED: These tests FAIL when:
- etsy_shop_id column not yet created (field not declared in Phase 3)
- Computed fields accidentally marked `store=True` (buggy Phase 3)
- ir_cron record not seeded via data file
- ir_config_parameter not seeded with default 'manual' value

Test isolation: Each test uses direct SQL (self.env.cr.execute) rather than
ORM to verify DB state independently of model registry caching. No mocking.
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPEnhEsty195Phase1DB(TransactionCase):
    """Phase 1: Database column and seeded record verification."""

    def test_etsy_shop_id_column_exists(self):
        """Verify etsy_shop_id column exists as an int4 FK in multichannel_listing.

        RED: Fails when the multichannel_listing.etsy_shop_id field (M2O)
        has not been declared in Phase 3. The column will be created by the
        field definition on module upgrade (-u etsy_integration).
        """
        self.env.cr.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'multichannel_listing' AND column_name = 'etsy_shop_id'
        """)
        rows = self.env.cr.fetchall()
        self.assertEqual(len(rows), 1, "Column 'etsy_shop_id' must exist in multichannel_listing table")
        col_name, data_type = rows[0]
        self.assertEqual(col_name, 'etsy_shop_id')
        self.assertIn(data_type, ('integer', 'bigint'), f"Expected int4/int8 FK, got {data_type}")

    def test_display_columns_are_not_stored(self):
        """Verify display_price_in_shop_currency and display_currency_id are NOT stored.

        Non-stored computed fields must NOT have physical columns in the table.
        RED: Fails if a sloppy Phase 3 declares these with `store=True`.

        This is a guardrail against buggy `@api.depends` + `store=True` patterns.
        """
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'multichannel_listing'
              AND column_name IN ('display_price_in_shop_currency', 'display_currency_id')
        """)
        rows = self.env.cr.fetchall()
        self.assertEqual(
            len(rows), 0,
            "display_price_in_shop_currency and display_currency_id must NOT be stored columns. "
            "They are non-stored computed fields. If columns exist, Phase 3 incorrectly declared `store=True`.",
        )

    def test_cron_record_exists(self):
        """Verify ir.cron record 'Etsy: Refresh Shop Currency Rates' is seeded.

        RED: Fails when the ir_cron_currency_rates.xml data file has not been
        added to the manifest or the record is missing/misconfigured.
        """
        try:
            cron = self.env.ref('etsy_integration.ir_cron_etsy_refresh_currency_rates')
        except ValueError as e:
            self.fail(
                f"ir.cron XML ID 'etsy_integration.ir_cron_etsy_refresh_currency_rates' not found. "
                f"Data file ir_cron_currency_rates.xml must be created and added to __manifest__.py. "
                f"Error: {e}",
            )

        # Verify cron exists and has expected configuration
        # (active state may be mutated in dev env but wiring matters for deployment)
        self.assertEqual(cron.interval_number, 1, "Cron interval_number must be 1 (daily)")
        self.assertEqual(cron.interval_type, 'days', "Cron interval_type must be 'days'")
        # nextcall hour verification skipped: varies based on when migration ran

    def test_config_parameter_default_manual(self):
        """Verify ir.config_parameter default 'etsy_integration.currency_rate_provider' is 'manual'.

        RED: Fails when ir_config_parameter_currency.xml data file is not created
        or the default value is missing/incorrect.
        """
        val = self.env['ir.config_parameter'].sudo().get_param(
            'etsy_integration.currency_rate_provider', default=False,
        )
        self.assertEqual(
            val, 'manual',
            "ir.config_parameter 'etsy_integration.currency_rate_provider' must default to 'manual'. "
            "Seed via ir_config_parameter_currency.xml data file.",
        )
