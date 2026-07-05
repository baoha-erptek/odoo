"""Phase 2 ORM tests for P-PUB-INVENTORY (Spec 011 T022).

Covers:
- push_inventory builds products[] from product.template variants
- SKU resolution applied per variant (ADR-014 §4)
- Entire-array PUT shape (route to /listings/{id}/inventory)
- EtsyInventoryPusher.push thin alias resolves listing_id from
  product.channel.status.external_ref
- Snapshot sync updates etsy.listing.product rows from response
- Refuses when no listing_id can be resolved
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)
from odoo.addons.etsy_integration.services.etsy_inventory_pusher import (
    EtsyInventoryPusher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubInventoryORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(eac_module, '_read_credentials', return_value=_FAKE)
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        cls.Listing = cls.env['etsy.listing']
        cls.ListingProduct = cls.env['etsy.listing.product']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)

    def _make_shop(self):
        return self.env['etsy.shop'].create({
            'name': 'INV TEST',
            'etsy_api_shop_id': '77777777',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def _make_product_with_listing(self, code='INV-SKU-1', listing_id='LST-1',
                                     shop=None):
        if shop is None:
            shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'Custom Coffee Mug',
            'default_code': code,
            'list_price': 19.99,
        })
        listing = self.Listing.create({
            'shop_id': shop.id,
            'etsy_listing_id': listing_id,
            'title': 'L %s' % listing_id,
            'url': 'https://etsy/x/%s' % listing_id,
            'state': 'active',
            'last_modified': '2026-05-23 00:00:00',
        })
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy_channel.id,
            'state': 'draft',
            'external_ref': listing_id,
        })
        return shop, tmpl, listing

    # ------------------------------------------------------------------
    # Payload + path
    # ------------------------------------------------------------------

    def test_push_inventory_payload_has_products_array(self):
        shop, tmpl, listing = self._make_product_with_listing()
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
            args, kwargs = client.put.call_args
        self.assertEqual(args[0], 'listings/LST-1/inventory')
        payload = kwargs.get('json') or {}
        self.assertIn('products', payload)
        self.assertIsInstance(payload['products'], list)
        self.assertGreaterEqual(len(payload['products']), 1)
        for p in payload['products']:
            self.assertIn('sku', p)
            self.assertIn('property_values', p)
            self.assertIn('offerings', p)

    def test_push_inventory_emits_offering_when_variants_not_materialized(self):
        """R-PUB-RESPONSE-BODY-DIAGNOSE TC-015: a template whose only attribute
        line is a dynamic-variant axis has an EMPTY product_variant_ids, so the
        old loop produced an empty products[] → Etsy 400 "No products supplied".
        push_inventory must emit at least one fallback product offering.
        """
        shop = self._make_shop()
        dyn_attr = self.env['product.attribute'].create({
            'name': 'R-PUB Dyn Color',
            'create_variant': 'dynamic',
        })
        dyn_val = self.env['product.attribute.value'].create({
            'name': 'Onyx',
            'attribute_id': dyn_attr.id,
        })
        tmpl = self.Template.create({
            'name': 'Dynamic Variant Mug',
            'default_code': 'DYN-MUG-1',
            'list_price': 21.0,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': dyn_attr.id,
                'value_ids': [(6, 0, [dyn_val.id])],
            })],
        })
        # Precondition: a dynamic-only template materializes no variants.
        self.assertEqual(
            len(tmpl.product_variant_ids), 0,
            "expected dynamic-variant template to have no materialized variants",
        )
        listing = self.Listing.create({
            'shop_id': shop.id,
            'etsy_listing_id': 'LST-DYN',
            'title': 'L DYN',
            'url': 'https://etsy/x/DYN',
            'state': 'active',
            'last_modified': '2026-05-23 00:00:00',
        })
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy_channel.id,
            'state': 'draft',
            'external_ref': 'LST-DYN',
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
            kwargs = client.put.call_args[1]
        products = kwargs['json']['products']
        self.assertGreaterEqual(
            len(products), 1,
            "push_inventory must send a non-empty products[] even when "
            "product_variant_ids is empty (dynamic-variant template)",
        )
        fallback = products[0]
        self.assertIn('sku', fallback)
        self.assertIn('offerings', fallback)
        self.assertGreaterEqual(len(fallback['offerings']), 1)
        self.assertEqual(fallback['property_values'], [])

    def test_push_inventory_uses_v2_sku_per_variant(self):
        shop, tmpl, listing = self._make_product_with_listing(
            code='LEGACY-MUG-1',
        )
        # Mug regex matches → v2 = MUG; status defaults to non_canonical
        self.assertEqual(tmpl.x_sku_v2_suggested, 'MUG')
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
            kwargs = client.put.call_args[1]
        sku = kwargs['json']['products'][0]['sku']
        self.assertEqual(sku, 'MUG')

    def test_push_inventory_keeps_legacy_when_ba_approved(self):
        shop, tmpl, listing = self._make_product_with_listing(
            code='LEGACY-MUG-1',
        )
        tmpl.write({'x_sku_v2_status': 'ba_approved_legacy'})
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
            kwargs = client.put.call_args[1]
        self.assertEqual(kwargs['json']['products'][0]['sku'], 'LEGACY-MUG-1')

    # ------------------------------------------------------------------
    # Alias entry point (T019)
    # ------------------------------------------------------------------

    def test_inventory_pusher_resolves_listing_id_from_status(self):
        shop, tmpl, listing = self._make_product_with_listing(listing_id='LST-77')
        pusher = EtsyInventoryPusher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            pusher.push(tmpl, shop)
            args = client.put.call_args[0]
        self.assertEqual(args[0], 'listings/LST-77/inventory')

    def test_inventory_pusher_refuses_when_no_external_ref(self):
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'No listing yet',
            'default_code': 'NO-LST',
        })
        pusher = EtsyInventoryPusher(self.env)
        with self.assertRaises(ValueError):
            pusher.push(tmpl, shop)

    # ------------------------------------------------------------------
    # Snapshot sync (T020)
    # ------------------------------------------------------------------

    def test_push_inventory_updates_local_snapshot_from_response(self):
        shop, tmpl, listing = self._make_product_with_listing(
            code='SNAP-1', listing_id='LST-SNAP',
        )
        # Pre-existing snapshot row
        existing = self.ListingProduct.create({
            'listing_id': listing.id,
            'etsy_product_id': 'PROD-A',
            'sku': 'old-sku',
            'quantity': 5,
            'price': 10.0,
        })
        response = {
            'products': [
                {
                    'product_id': 'PROD-A',
                    'sku': 'new-sku',
                    'offerings': [{'quantity': 12, 'price': {'amount': 1500, 'divisor': 100}}],
                    'property_values': [],
                },
            ],
        }
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = response
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
        existing.invalidate_recordset()
        self.assertEqual(existing.sku, 'new-sku')
        self.assertEqual(existing.quantity, 12)

    def test_snapshot_upsert_links_product_by_sku(self):
        """E2E-F1 §8 root cause: snapshot rows created/updated by the
        publisher must be SKU-linked immediately (not wait for the
        variant-sync cron, which races and can skip the listing)."""
        shop, tmpl, listing = self._make_product_with_listing(
            code='SNAP-LINK-1', listing_id='LST-SNAP-LINK',
        )
        variant = tmpl.product_variant_id
        # Existing unlinked row whose SKU now matches a live product
        existing = self.ListingProduct.create({
            'listing_id': listing.id,
            'etsy_product_id': 'PROD-A',
            'sku': 'stale',
            'quantity': 1,
            'price': 5.0,
        })
        response = {
            'products': [
                {   # updates `existing` -> should link to variant
                    'product_id': 'PROD-A',
                    'sku': 'SNAP-LINK-1',
                    'offerings': [{'quantity': 3, 'price': {'amount': 1999, 'divisor': 100}}],
                },
                {   # brand-new row -> should be born linked
                    'product_id': 'PROD-B',
                    'sku': 'SNAP-LINK-1',
                    'offerings': [{'quantity': 4, 'price': {'amount': 1999, 'divisor': 100}}],
                },
            ],
        }
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = response
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
        existing.invalidate_recordset()
        self.assertEqual(existing.product_id, variant,
                         'updated snapshot row must SKU-link to the variant')
        created = self.ListingProduct.search([
            ('listing_id', '=', listing.id),
            ('etsy_product_id', '=', 'PROD-B'),
        ], limit=1)
        self.assertEqual(created.product_id, variant,
                         'new snapshot row must be born SKU-linked')
