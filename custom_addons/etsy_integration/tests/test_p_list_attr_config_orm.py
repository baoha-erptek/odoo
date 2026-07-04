"""Phase 2 ORM tests for P-LIST-ATTR-CONFIG (Wave 2 / Jira ESTY-194).

Tier 2 of the 3-tier publisher property-id fallback:
  1. listing override     (P-LIST-ATTRIBUTES — shipped)
  2. shop default mapping (THIS slice)
  3. product.attribute global

Validates the full 3-tier chain end-to-end.
"""

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


@tagged('post_install', '-at_install')
class TestShopAttributeMappingCRUD(TransactionCase):

    def test_unique_pair_enforced(self):
        shop = self.env['etsy.shop'].create({
            'name': 'PAC A', 'etsy_api_shop_id': '9300001',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })
        attr = self.env['product.attribute'].create({
            'name': 'PAC Size', 'x_etsy_property_id': '513',
            'x_etsy_property_name': 'Size', 'x_publish_as_property': True,
        })
        Mapping = self.env['etsy.shop.attribute.mapping']
        Mapping.create({
            'shop_id': shop.id, 'product_attribute_id': attr.id,
            'etsy_property_id_override': '8001',
        })
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Mapping.create({
                    'shop_id': shop.id, 'product_attribute_id': attr.id,
                    'etsy_property_id_override': '8002',
                })


@tagged('post_install', '-at_install')
class Test3TierChainFullCoverage(TransactionCase):
    """Now that tier-2 exists, lock the full chain: listing → shop → global."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def _shop(self):
        return self.env['etsy.shop'].create({
            'name': 'PAC TEST', 'etsy_api_shop_id': '9300002',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def test_tier1_listing_beats_shop_and_global(self):
        shop = self._shop()
        axis = self.env['product.attribute'].create({
            'name': 'PAC Color', 'x_etsy_property_id': '200',
            'x_etsy_property_name': 'Color', 'x_publish_as_property': True,
        })
        # Shop default
        self.env['etsy.shop.attribute.mapping'].create({
            'shop_id': shop.id, 'product_attribute_id': axis.id,
            'etsy_property_id_override': '5000',
            'etsy_property_name_override': 'Shop Color',
        })
        # Listing override
        tmpl = self.env['product.template'].create({
            'name': 'PAC T1', 'list_price': 1.0,
        })
        listing = self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id, 'channel_id': self.channel.id,
        })
        self.env['multichannel.listing.attribute.mapping'].create({
            'listing_id': listing.id, 'product_attribute_id': axis.id,
            'etsy_property_id_override': '9999',
            'etsy_property_name_override': 'Listing Color',
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Red', intent=listing, shop=shop,
        )
        self.assertEqual(pv['property_id'], 9999)
        self.assertEqual(pv['property_name'], 'Listing Color')

    def test_tier2_shop_beats_global_when_listing_empty(self):
        shop = self._shop()
        axis = self.env['product.attribute'].create({
            'name': 'PAC T2 Color', 'x_etsy_property_id': '200',
            'x_etsy_property_name': 'Color', 'x_publish_as_property': True,
        })
        self.env['etsy.shop.attribute.mapping'].create({
            'shop_id': shop.id, 'product_attribute_id': axis.id,
            'etsy_property_id_override': '5000',
            'etsy_property_name_override': 'Shop Color',
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Red', intent=None, shop=shop,
        )
        self.assertEqual(pv['property_id'], 5000,
            'Tier 2 (shop default) must win over Tier 3 (global) when '
            'no listing override is present.')
        self.assertEqual(pv['property_name'], 'Shop Color')

    def test_tier3_global_used_when_neither_listing_nor_shop_set(self):
        shop = self._shop()
        axis = self.env['product.attribute'].create({
            'name': 'PAC T3 Material', 'x_etsy_property_id': '300',
            'x_etsy_property_name': 'Material',
            'x_publish_as_property': True,
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Wood', intent=None, shop=shop,
        )
        self.assertEqual(pv['property_id'], 300)
        self.assertEqual(pv['property_name'], 'Material')

    def test_shop_default_partial_falls_through_for_name(self):
        """Shop default carries an id-override but no name → name falls
        through to global product.attribute.x_etsy_property_name."""
        shop = self._shop()
        axis = self.env['product.attribute'].create({
            'name': 'PAC Partial', 'x_etsy_property_id': '300',
            'x_etsy_property_name': 'Material',
            'x_publish_as_property': True,
        })
        self.env['etsy.shop.attribute.mapping'].create({
            'shop_id': shop.id, 'product_attribute_id': axis.id,
            'etsy_property_id_override': '7000',
            # No name override
        })
        pv = EtsyListingPublisher._property_value_for(
            axis, 'Wood', intent=None, shop=shop,
        )
        self.assertEqual(pv['property_id'], 7000,
            'id from shop default (tier 2)')
        self.assertEqual(pv['property_name'], 'Material',
            'name falls through to global (tier 3)')
