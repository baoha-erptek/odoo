"""Phase 2 ORM RED tests for P-BUG-ESTY-188 iter3 — per-variant Etsy model.

Per ADR-014 §4.a (2026-06-06 amendment), the publisher must emit per-variant
SKU / quantity / price / image to Etsy v3, replacing the template-level model
that produced two 400s on staging on 2026-06-06:
- 06:57 createListing 400 {path:/price, type:empty}  (template list_price=0)
- 07:11 push_inventory 400 "quantity must be consistent across all products"
  (3 variants emit distinct qty 5/10/20 under one shared SKU)

Each test in this module locks one contract point Phase 3 must satisfy. All
must be RED before GREEN; the failures should be on AttributeError (new helper
not yet defined) or on assertion mismatches against today's template-level
output — not on import / collection errors.
"""

import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}

# Minimal 1×1 PNG (red pixel) — for variant image_variant_1920 fixtures.
_PNG_1x1 = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000d49444154789c63f8cfc0f01f00050501020df5d3e3'
    '0000000049454e44ae426082'
))


class _IterTestBase(TransactionCase):
    """Shared setup: stub credentials, helper to create shop + listing rows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        cls.Listing = cls.env['etsy.listing']
        cls.Attribute = cls.env['product.attribute']
        cls.AttributeValue = cls.env['product.attribute.value']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(
            active_test=False,
        )
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)

    def _make_shop(self, name='ITER3 TEST', api_id='60752333'):
        # Publisher's _check_shop_defaults requires taxonomy / shipping /
        # return-policy IDs to be set — pin dummy non-zero values so
        # create_draft can reach the payload build path.
        return self.env['etsy.shop'].create({
            'name': name,
            'etsy_api_shop_id': api_id,
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
            'default_taxonomy_id': '1',
            'default_shipping_profile_id': '1',
            'default_return_policy_id': '1',
        })

    def _wire_listing(self, tmpl, shop, listing_id):
        listing = self.Listing.create({
            'shop_id': shop.id,
            'etsy_listing_id': listing_id,
            'title': 'iter3 test',
            'url': 'https://etsy/x/%s' % listing_id,
            'state': 'active',
            'last_modified': '2026-06-06 00:00:00',
        })
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy_channel.id,
            'state': 'draft',
            'external_ref': listing_id,
        })
        return listing

    def _make_size_axis(self, value_names=('4"', '6"', '8"'), price_extras=None):
        """Create a Size attribute (always-variant) with N values + price_extras.

        Also pins ``x_etsy_property_id`` + ``x_etsy_property_name`` so the
        publisher's ``_property_value_for`` lookup yields a non-empty
        ``property_values[]`` entry per variant — without it, the publisher
        falls into the dynamic-variant fallback branch (one product, empty
        property_values), masking the per-variant assertions iter3 needs.

        Returns (attribute, [values]) so callers can wire it onto a template.
        """
        attr = self.Attribute.create({
            'name': 'Iter3 Size',
            'create_variant': 'always',
            'x_publish_as_property': True,
            'x_etsy_property_id': 52047899318,
            'x_etsy_property_name': 'Size',
        })
        values = []
        for name in value_names:
            values.append(self.AttributeValue.create({
                'name': name,
                'attribute_id': attr.id,
            }))
        return attr, values


# ---------------------------------------------------------------------------
# createListing per-variant starting price
# ---------------------------------------------------------------------------

@tagged('post_install', '-at_install')
class TestCreateDraftStartingPrice(_IterTestBase):
    """createListing top-level `price` resolves per ADR-014 §4.a (iter3)."""

    def test_starting_price_uses_min_variant_lst_price_when_template_zero(self):
        """The Leather Tray case: list_price=0, variants carry price via
        price_extra → starting price = min(variant.lst_price)."""
        shop = self._make_shop()
        attr, values = self._make_size_axis()
        tmpl = self.Template.create({
            'name': 'Iter3 Tray',
            'list_price': 0.0,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attr.id,
                'value_ids': [(6, 0, [v.id for v in values])],
            })],
        })
        # Pin distinct price_extra per ptav (Odoo materializes ptavs on attr
        # line write).
        for ptav, extra in zip(tmpl.attribute_line_ids.product_template_value_ids,
                               (10.0, 20.0, 30.0)):
            ptav.price_extra = extra

        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post.return_value = {'listing_id': 'NEW-1'}
            publisher.create_draft(tmpl, shop)
            kwargs = client.post.call_args[1]

        payload = kwargs.get('json') or {}
        # Phase 3 helper _resolve_starting_price must return min variant
        # lst_price (10.0) instead of raw template list_price (0.0).
        self.assertEqual(
            payload.get('price'), 10.0,
            'createListing top-level price must derive from min(variant.lst_price) '
            'when template list_price=0; got %r' % payload.get('price'),
        )

    def test_starting_price_falls_back_to_template_list_price_no_variants(self):
        """Single-variant template, list_price=12.99 → payload price=12.99."""
        shop = self._make_shop(api_id='60752334')
        tmpl = self.Template.create({
            'name': 'Iter3 Simple Cup',
            'list_price': 12.99,
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post.return_value = {'listing_id': 'NEW-2'}
            publisher.create_draft(tmpl, shop)
            kwargs = client.post.call_args[1]
        self.assertEqual((kwargs.get('json') or {}).get('price'), 12.99)

    def test_starting_price_raises_user_error_when_all_zero(self):
        """Template list_price=0 AND no variants resolve to >0 → UserError;
        Etsy is NOT called."""
        shop = self._make_shop(api_id='60752335')
        tmpl = self.Template.create({
            'name': 'Iter3 Zero',
            'list_price': 0.0,
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            with self.assertRaises(UserError):
                publisher.create_draft(tmpl, shop)
            self.assertEqual(
                client.post.call_count, 0,
                'Etsy createListing must not be called when no positive price '
                'can be resolved',
            )


# ---------------------------------------------------------------------------
# push_inventory per-variant SKU / qty / price
# ---------------------------------------------------------------------------

@tagged('post_install', '-at_install')
class TestPushInventoryPerVariant(_IterTestBase):
    """push_inventory emits distinct SKU/qty/price per variant (iter3 contract).

    This is the direct repro of the 2026-06-06 07:11 staging 400
    'quantity must be consistent across all products': 3 variants currently
    share one template-level SKU but have distinct qty_available (5/10/20),
    which Etsy rejects. Iter3 lifts this by emitting distinct SKUs per
    variant — then quantity divergence is allowed.
    """

    def _build_three_size_template(self, with_default_codes=False):
        attr, values = self._make_size_axis()
        tmpl = self.Template.create({
            'name': 'Iter3 Per-Variant Tray',
            'list_price': 0.0,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attr.id,
                'value_ids': [(6, 0, [v.id for v in values])],
            })],
        })
        # Distinct price_extras → distinct variant.lst_price.
        for ptav, extra in zip(tmpl.attribute_line_ids.product_template_value_ids,
                               (10.0, 20.0, 30.0)):
            ptav.price_extra = extra
        # Optional explicit per-variant SKUs.
        if with_default_codes:
            for variant, code in zip(tmpl.product_variant_ids,
                                     ('TRAY-S', 'TRAY-M', 'TRAY-L')):
                variant.default_code = code
        return tmpl, attr

    def _push(self, tmpl, shop, listing_id='LST-ITER3'):
        listing = self._wire_listing(tmpl, shop, listing_id)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.put.return_value = {'products': []}
            publisher.push_inventory(tmpl, listing.etsy_listing_id, shop)
            return client.put.call_args[1]['json']

    def test_distinct_variant_default_codes_become_distinct_sku_per_product(self):
        shop = self._make_shop()
        tmpl, attr = self._build_three_size_template(with_default_codes=True)
        payload = self._push(tmpl, shop)
        skus = [p['sku'] for p in payload['products']]
        self.assertEqual(
            sorted(skus), ['TRAY-L', 'TRAY-M', 'TRAY-S'],
            'Each variant must publish under its own default_code SKU; got %r'
            % skus,
        )
        # sku_on_property must list the Size axis since SKUs vary on it.
        self.assertIn(
            'sku_on_property', payload,
            "updateListingInventory body must include 'sku_on_property' list",
        )
        # property_id is an int Etsy assigns; we just assert non-empty + 1 entry
        self.assertEqual(
            len(payload['sku_on_property']), 1,
            'Size is the only varying axis → sku_on_property has one entry',
        )

    def test_synthetic_sku_when_variant_default_code_empty(self):
        """When variant.default_code is empty, synthesize <base>-<slug>."""
        shop = self._make_shop(api_id='60752336')
        tmpl, attr = self._build_three_size_template(with_default_codes=False)
        # Force base SKU via template default_code (the publisher's
        # _resolve_sku ultimately falls back to default_code).
        tmpl.default_code = 'LT'
        payload = self._push(tmpl, shop, listing_id='LST-ITER3B')
        skus = sorted(p['sku'] for p in payload['products'])
        # The exact slug rule is "uppercase alphanumeric of the value name,
        # joined with '-'". Phase 3 docstring locks the rule; this test asserts
        # the contract that all SKUs share the LT prefix AND are distinct.
        for sku in skus:
            self.assertTrue(
                sku.startswith('LT-'),
                'synthetic SKU must start with base SKU; got %r' % sku,
            )
        self.assertEqual(
            len(set(skus)), 3,
            'three Size variants must produce three distinct SKUs; got %r'
            % skus,
        )

    def test_per_variant_quantity_emitted_distinctly(self):
        """THE production bug: 5/10/20 stock per variant must land as
        distinct offerings[].quantity values without Etsy's consistency rule
        being triggered (which requires sku_on_property to include the axis)."""
        shop = self._make_shop(api_id='60752337')
        tmpl, attr = self._build_three_size_template(with_default_codes=True)
        # Pin distinct on-hand qty per variant (mirror staging 5/10/20).
        # The publisher reads variant.qty_available which is computed from
        # stock_quant; we patch the computed-field read to avoid wiring quants.
        with patch.object(
            type(tmpl.product_variant_ids), 'qty_available',
            new_callable=lambda: property(
                lambda self_: {
                    tmpl.product_variant_ids[0].id: 5.0,
                    tmpl.product_variant_ids[1].id: 10.0,
                    tmpl.product_variant_ids[2].id: 20.0,
                }.get(self_.id, 1.0)
            ),
        ):
            payload = self._push(tmpl, shop, listing_id='LST-ITER3C')

        # Map SKU → offering quantity (order may vary).
        qty_by_sku = {
            p['sku']: p['offerings'][0]['quantity']
            for p in payload['products']
        }
        self.assertEqual(
            sorted(qty_by_sku.values()), [5, 10, 20],
            'each variant must emit its own qty (5/10/20 from variant.qty_available); '
            'got %r' % qty_by_sku,
        )
        self.assertIn(
            'quantity_on_property', payload,
            "payload must declare 'quantity_on_property' so Etsy permits "
            "divergent quantities across variants",
        )
        self.assertEqual(
            len(payload['quantity_on_property']), 1,
            'Size axis drives quantity divergence — one property_id expected',
        )

    def test_per_variant_price_emitted_distinctly(self):
        """price_extras 10/20/30 (with list_price=0) → offerings prices [10,20,30]."""
        shop = self._make_shop(api_id='60752338')
        tmpl, attr = self._build_three_size_template(with_default_codes=True)
        payload = self._push(tmpl, shop, listing_id='LST-ITER3D')
        prices = sorted(p['offerings'][0]['price'] for p in payload['products'])
        self.assertEqual(
            prices, [10.0, 20.0, 30.0],
            'each variant must emit its own lst_price (= list_price + price_extra); '
            'got %r' % prices,
        )
        self.assertIn(
            'price_on_property', payload,
            "payload must declare 'price_on_property'",
        )
        self.assertEqual(len(payload['price_on_property']), 1)


# ---------------------------------------------------------------------------
# updateVariationImages binding
# ---------------------------------------------------------------------------

@tagged('post_install', '-at_install')
class TestVariationImagesBinding(_IterTestBase):
    """Per-variant image binding via POST .../variation-images.

    Schema (Etsy OAS):
      POST /v3/application/shops/{shop_id}/listings/{listing_id}/variation-images
      body: {"variation_images": [{"property_id": int, "value_id": int,
                                   "image_id": int}]}
    """

    def test_variation_images_posted_when_variants_carry_own_images(self):
        shop = self._make_shop(api_id='60752339')
        attr, values = self._make_size_axis()
        tmpl = self.Template.create({
            'name': 'Iter3 With Variant Images',
            'list_price': 15.0,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attr.id,
                'value_ids': [(6, 0, [v.id for v in values])],
            })],
        })
        # Assign a distinct per-variant image (image_variant_1920, NOT
        # image_1920 — image_1920 auto-falls back to template).
        for variant in tmpl.product_variant_ids:
            variant.image_variant_1920 = _PNG_1x1
        listing = self._wire_listing(tmpl, shop, 'LST-ITER3IMG')
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            # uploadListingImage returns a listing_image_id we then bind to
            # the variation value.
            client.post.side_effect = [
                {'listing_image_id': 9001},
                {'listing_image_id': 9002},
                {'listing_image_id': 9003},
                # variation-images endpoint
                {'results': []},
            ]
            publisher.run(tmpl, shop)  # orchestrator wires upload then bind

        # Locate the variation-images POST among the calls.
        variation_calls = [
            c for c in client.post.call_args_list
            if c.args and 'variation-images' in c.args[0]
        ]
        self.assertEqual(
            len(variation_calls), 1,
            'updateVariationImages must be POSTed exactly once when at least '
            'one variant carries image_variant_1920; observed %d call(s)'
            % len(variation_calls),
        )
        body = variation_calls[0].kwargs.get('json') or {}
        self.assertIn('variation_images', body)
        entries = body['variation_images']
        self.assertEqual(
            len(entries), 3,
            'one binding entry per variant with distinct image; got %d' % len(entries),
        )
        for entry in entries:
            self.assertIn('property_id', entry)
            self.assertIn('value_id', entry)
            self.assertIn('image_id', entry)

    def test_variation_images_skipped_when_no_variant_carries_own_image(self):
        """If only the template image is set (image_variant_1920 empty for
        every variant), the publisher must NOT call variation-images."""
        shop = self._make_shop(api_id='60752340')
        attr, values = self._make_size_axis()
        tmpl = self.Template.create({
            'name': 'Iter3 Template-Image-Only',
            'list_price': 15.0,
            'image_1920': _PNG_1x1,  # template image only
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attr.id,
                'value_ids': [(6, 0, [v.id for v in values])],
            })],
        })
        listing = self._wire_listing(tmpl, shop, 'LST-ITER3IMG2')
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post.return_value = {'listing_image_id': 1}
            publisher.run(tmpl, shop)
        variation_calls = [
            c for c in client.post.call_args_list
            if c.args and 'variation-images' in c.args[0]
        ]
        self.assertEqual(
            len(variation_calls), 0,
            'variation-images must not be called when no variant has '
            'image_variant_1920 set',
        )
