"""Phase 2 ORM tests for P-LIST-ATTRIBUTES (Wave 2 / Jira ESTY-192).

3-tier fallback for the publisher's per-axis Etsy property resolution
(spec 012 §US6, UX review HIGH #4):

    1. multichannel.listing.attribute_mapping_ids  (per-listing override)
    2. <not implemented yet>                       (shop default — slice
                                                    P-LIST-ATTR-CONFIG)
    3. product.attribute.x_etsy_property_id        (global, ships today)

This slice covers tiers (1) and (3). Tier (2) lands in P-LIST-ATTR-CONFIG
with its own tests.
"""

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


@tagged('post_install', '-at_install')
class TestAttributeMappingCRUD(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.Mapping = cls.env['multichannel.listing.attribute.mapping']
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.tmpl = cls.env['product.template'].create({
            'name': 'PLA Tmpl', 'list_price': 1.0,
        })
        cls.attr_size = cls.env['product.attribute'].create({
            'name': 'PLA Size',
            'x_etsy_property_id': '513',
            'x_etsy_property_name': 'Size',
            'x_publish_as_property': True,
        })

    def test_unique_pair_enforced(self):
        listing = self.Listing.sudo().create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
        })
        self.Mapping.create({
            'listing_id': listing.id,
            'product_attribute_id': self.attr_size.id,
            'etsy_property_id_override': '999',
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Mapping.create({
                    'listing_id': listing.id,
                    'product_attribute_id': self.attr_size.id,
                    'etsy_property_id_override': '888',
                })


@tagged('post_install', '-at_install')
class TestPropertyValueFor3TierFallback(TransactionCase):
    """Exercises EtsyListingPublisher._property_value_for with the iter3
    P-LIST-ATTRIBUTES intent kwarg. Tier #2 (shop default) lands in
    P-LIST-ATTR-CONFIG; this test asserts tiers #1 (listing) and #3
    (global)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def test_tier1_listing_override_wins(self):
        """Per-listing mapping with non-empty override → use the override."""
        tmpl = self.env['product.template'].create({
            'name': 'PLA T1', 'list_price': 1.0,
        })
        axis = self.env['product.attribute'].create({
            'name': 'T1 Color',
            'x_etsy_property_id': '200',
            'x_etsy_property_name': 'Primary color',
            'x_publish_as_property': True,
        })
        listing = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
        })
        self.env['multichannel.listing.attribute.mapping'].create({
            'listing_id': listing.id,
            'product_attribute_id': axis.id,
            'etsy_property_id_override': '9001',
            'etsy_property_name_override': 'Override Color',
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Red', intent=listing,
        )
        self.assertEqual(pv['property_id'], 9001)
        self.assertEqual(pv['property_name'], 'Override Color')
        self.assertEqual(pv['values'], ['Red'])

    def test_tier3_global_when_no_intent(self):
        """No intent provided → fall through to product.attribute global."""
        axis = self.env['product.attribute'].create({
            'name': 'T3 Material',
            'x_etsy_property_id': '300',
            'x_etsy_property_name': 'Material',
            'x_publish_as_property': True,
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Wood', intent=None,
        )
        self.assertEqual(pv['property_id'], 300)
        self.assertEqual(pv['property_name'], 'Material')

    def test_tier3_global_when_intent_has_no_row_for_axis(self):
        """Intent present but no mapping row matches this axis → global."""
        tmpl = self.env['product.template'].create({
            'name': 'PLA T3', 'list_price': 1.0,
        })
        axis_size = self.env['product.attribute'].create({
            'name': 'T3 Size',
            'x_etsy_property_id': '513',
            'x_etsy_property_name': 'Size',
            'x_publish_as_property': True,
        })
        axis_color = self.env['product.attribute'].create({
            'name': 'T3 Color',
            'x_etsy_property_id': '200',
            'x_etsy_property_name': 'Color',
            'x_publish_as_property': True,
        })
        listing = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
        })
        # Only override Color → Size resolution falls through to global
        self.env['multichannel.listing.attribute.mapping'].create({
            'listing_id': listing.id,
            'product_attribute_id': axis_color.id,
            'etsy_property_id_override': '999',
        })
        pv = EtsyListingPublisher._property_value_for(
            axis_size, '11oz', intent=listing,
        )
        self.assertEqual(pv['property_id'], 513,
            'Size axis has no listing override; must use global x_etsy_property_id')

    def test_tier1_blank_override_falls_through(self):
        """Listing row exists for the axis but override field is blank →
        fall through to global (operator created a row but didn't fill it)."""
        tmpl = self.env['product.template'].create({
            'name': 'PLA T1B', 'list_price': 1.0,
        })
        axis = self.env['product.attribute'].create({
            'name': 'T1B Color',
            'x_etsy_property_id': '200',
            'x_etsy_property_name': 'Color',
            'x_publish_as_property': True,
        })
        listing = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
        })
        self.env['multichannel.listing.attribute.mapping'].create({
            'listing_id': listing.id,
            'product_attribute_id': axis.id,
            'etsy_property_id_override': '',
            'etsy_property_name_override': '',
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Red', intent=listing,
        )
        # Blank override → fall through to global
        self.assertEqual(pv['property_id'], 200)
        self.assertEqual(pv['property_name'], 'Color')

    def test_no_global_and_no_override_skips_with_warning(self):
        """No override + no global → return None + WARNING (skip the axis)."""
        axis = self.env['product.attribute'].create({
            'name': 'T-skip',
            'x_etsy_property_id': '',
            'x_etsy_property_name': '',
            'x_publish_as_property': True,
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Whatever', intent=None,
        )
        self.assertIsNone(pv)
