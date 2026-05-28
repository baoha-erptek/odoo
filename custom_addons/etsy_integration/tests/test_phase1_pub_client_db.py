"""Phase 1 DB tests for P-PUB-CLIENT (Spec 011 T005)."""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1PubClientDB(TransactionCase):

    def test_etsy_api_log_source_includes_publish_values(self):
        """T002: new Selection values present."""
        Selection = self.env['etsy.api.log']._fields['source'].selection
        codes = {code for code, _ in Selection}
        for needed in (
            'listing_create', 'listing_image_upload', 'listing_image_delete',
            'listing_inventory_push', 'listing_publish',
            'catalog_import_run', 'catalog_image_download',
        ):
            self.assertIn(needed, codes,
                           "etsy.api.log.source must include %r" % needed)

    def test_etsy_shop_default_fields_exist(self):
        for column in (
            'default_taxonomy_id',
            'default_shipping_profile_id',
            'default_return_policy_id',
            'default_who_made',
            'default_when_made',
            'default_is_supply',
        ):
            self.env.cr.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'etsy_shop'
                  AND column_name = %s
                """,
                (column,),
            )
            self.assertIsNotNone(
                self.env.cr.fetchone(),
                "etsy_shop.%s must exist" % column,
            )
