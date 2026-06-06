"""Phase 2 ORM tests for variant property_values + R-PUB-VARIANT-MATERIALIZE.

EtsyListingPublisher._property_value_for(axis, value_name) emits one Etsy
push_inventory property_values[] entry:

    {property_id: <int|str>, property_name: <str>, values: [<value name>]}

Etsy REQUIRES both a property_id AND a non-null property_name (the inventory
PUT 400s "Expected string value for property_name" without it — verified live
2026-05-28), so an axis missing either is skipped with a WARNING.

push_inventory builds the products[] grid from the cartesian product of the
publishable variant-creating attribute lines (R-PUB-VARIANT-MATERIALIZE), so
dynamic-variant axes (Color) that materialize no product.product still produce
real Etsy variations. Varying axes (>1 value) form the grid (Etsy caps at 2);
single-value publishable axes ride along as fixed property_values.
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged
from odoo.addons.base.models.ir_model import Command

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubVariantPropertiesPayload(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Shop = cls.env['etsy.shop']

    def _shop(self):
        return self.Shop.create({
            'name': 'VARPROP TEST SHOP',
            'etsy_api_shop_id': '99999999',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def _axis(self, xmlid, pid, pname, publish=True):
        attr = self.env.ref('multichannel_hub_core.%s' % xmlid)
        attr.x_publish_as_property = publish
        attr.x_etsy_property_id = pid
        attr.x_etsy_property_name = pname
        return attr

    def _tmpl(self, lines):
        """lines = [(attribute_record, [value_ids]), ...]."""
        return self.Template.create({
            'name': 'VarProp Item',
            'default_code': 'VP-001',
            'list_price': 10.0,
            'attribute_line_ids': [
                Command.create({'attribute_id': attr.id, 'value_ids': [Command.set(vids)]})
                for attr, vids in lines
            ],
        })

    # --- _property_value_for ------------------------------------------------

    def test_property_value_requires_id_and_name(self):
        """Publishable axis with id+name → {property_id, property_name, values}."""
        color = self._axis('attribute_color', '200', 'Primary color')
        pv = EtsyListingPublisher._property_value_for(color, 'Black')
        self.assertEqual(pv, {'property_id': 200, 'property_name': 'Primary color', 'values': ['Black']})

    def test_axis_publish_false_returns_none(self):
        color = self._axis('attribute_color', '200', 'Primary color', publish=False)
        self.assertIsNone(EtsyListingPublisher._property_value_for(color, 'Black'))

    def test_missing_property_name_skipped_with_warning(self):
        color = self._axis('attribute_color', '200', False)
        with self.assertLogs(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher',
            level='WARNING',
        ) as cm:
            pv = EtsyListingPublisher._property_value_for(color, 'Black')
        self.assertIsNone(pv)
        self.assertTrue(any('Color' in m for m in cm.output))

    def test_missing_property_id_skipped_with_warning(self):
        color = self._axis('attribute_color', False, 'Primary color')
        with self.assertLogs(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher',
            level='WARNING',
        ):
            self.assertIsNone(EtsyListingPublisher._property_value_for(color, 'Black'))

    def test_property_id_int_cast_numeric_else_string(self):
        a = self._axis('attribute_color', '12345', 'Primary color')
        b = self._axis('attribute_size', 'abc', 'Size')
        self.assertEqual(EtsyListingPublisher._property_value_for(a, 'X')['property_id'], 12345)
        self.assertEqual(EtsyListingPublisher._property_value_for(b, 'Y')['property_id'], 'abc')

    def test_collect_property_values_empty_for_bare_variant(self):
        tmpl = self.Template.create({'name': 'Bare', 'default_code': 'BARE-1', 'list_price': 5.0})
        self.assertEqual(
            EtsyListingPublisher._collect_property_values(tmpl.product_variant_ids[0]), [],
        )

    # --- push_inventory cartesian -------------------------------------------

    def _capture_put(self, pub, tmpl, shop):
        captured = {}

        def fake_put(self_client, path, json=None, **_kw):  # noqa: ARG001
            captured['json'] = json
            return {'products': []}

        with patch.object(EtsyListingPublisher, '_sync_inventory_snapshot', return_value=None), \
            patch('odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient.put', new=fake_put):
            pub.push_inventory(tmpl, listing_id='LST-1', shop=shop)
        return captured['json']['products']

    def test_single_value_axes_become_fixed_properties(self):
        """Material + Size single-value → 1 product with both as fixed props."""
        mat = self._axis('attribute_material', '148789511893', 'Material multi')
        size = self._axis('attribute_size', '513', 'Size')
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        tmpl = self._tmpl([(mat, [ceramic.id]), (size, [s35.id])])

        products = self._capture_put(EtsyListingPublisher(self.env), tmpl, self._shop())

        self.assertEqual(len(products), 1)
        names = {p['property_name'] for p in products[0]['property_values']}
        self.assertEqual(names, {'Material multi', 'Size'})
        for pv in products[0]['property_values']:
            self.assertIn('property_id', pv)
            self.assertIn('property_name', pv)

    def test_varying_axis_cartesian_materializes_dynamic_color(self):
        """Color [Black, White] (dynamic, no product.product) → 2 Etsy products."""
        color = self._axis('attribute_color', '200', 'Primary color')
        black = self.env.ref('multichannel_hub_core.value_color_bk')
        white = self.env.ref('multichannel_hub_core.value_color_wh')
        tmpl = self._tmpl([(color, [black.id, white.id])])
        # dynamic axis → no materialized variants
        self.assertLessEqual(len(tmpl.product_variant_ids), 1)

        products = self._capture_put(EtsyListingPublisher(self.env), tmpl, self._shop())

        self.assertEqual(len(products), 2)
        values = {p['property_values'][0]['values'][0] for p in products}
        self.assertEqual(values, {'Black', 'White'})
        for p in products:
            self.assertEqual(p['property_values'][0]['property_name'], 'Primary color')
        # P-BUG-ESTY-188 iter3: SKUs are per-variant now (ADR-014 §4.a).
        # For a dynamic-axis Color template with no per-variant default_code,
        # the publisher synthesizes `{base}-{slug}` per combo → SKUs MUST
        # differ across variants (otherwise Etsy 400s on the SKU consistency
        # vs `sku_on_property` rule).
        skus = {p['sku'] for p in products}
        self.assertEqual(len(skus), 2,
            "iter3 emits distinct per-variant SKUs; got %r" % skus)

    def test_more_than_two_varying_axes_raises(self):
        """>2 varying publishable axes → ValueError (Etsy 2-variation cap)."""
        mat = self._axis('attribute_material', '148789511893', 'Material multi')
        size = self._axis('attribute_size', '513', 'Size')
        color = self._axis('attribute_color', '200', 'Primary color')
        ce = self.env.ref('multichannel_hub_core.value_mat_ce')
        wd = self.env.ref('multichannel_hub_core.value_mat_wd')
        s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        s41 = self.env.ref('multichannel_hub_core.value_size_s41')
        bk = self.env.ref('multichannel_hub_core.value_color_bk')
        wt = self.env.ref('multichannel_hub_core.value_color_wh')
        tmpl = self._tmpl([(mat, [ce.id, wd.id]), (size, [s35.id, s41.id]), (color, [bk.id, wt.id])])

        with self.assertRaises(ValueError):
            self._capture_put(EtsyListingPublisher(self.env), tmpl, self._shop())

    def test_materials_sibling_regression(self):
        """materials[] still derived from the Material axis (listing-level)."""
        mat = self._axis('attribute_material', '148789511893', 'Material multi', publish=False)
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        tmpl = self._tmpl([(mat, [ceramic.id])])
        payload = EtsyListingPublisher(self.env)._build_create_draft_payload(tmpl, self._shop())
        self.assertIn('materials', payload)
        self.assertIn('Ceramic', payload['materials'])
