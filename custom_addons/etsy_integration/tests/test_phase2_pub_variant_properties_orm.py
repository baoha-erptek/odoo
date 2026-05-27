"""Phase 2 ORM tests for P-PUB-VARIANT-PROPERTIES (MP006, Spec 011).

Verifies EtsyListingPublisher._collect_property_values(variant) emits the
correct shape for Etsy push_inventory products[].property_values[]:

    {property_id: <int|str>, values: [<variant value name>]}

Per-axis enabled via product.attribute.x_publish_as_property (default True);
fallback to attribute name + WARNING log when x_etsy_property_id is empty.
Empty M2M (dynamic-variant trap, memory entry 150) returns [].

Also covers full push_inventory integration to confirm property_values are
wired into the products[] payload (replacing the hardcoded [] literal).
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubVariantPropertiesPayload(TransactionCase):
    """ORM tests for _collect_property_values + push_inventory integration."""

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

    def _tmpl_material_size(self, material_value_ids, size_value_ids):
        """Create a template with Material + Size attribute lines (both 'always')."""
        from odoo.addons.base.models.ir_model import Command
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')
        return self.Template.create({
            'name': 'VarProp Item',
            'default_code': 'VP-001',
            'list_price': 10.0,
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': material_attr.id,
                    'value_ids': [Command.set(material_value_ids)],
                }),
                Command.create({
                    'attribute_id': size_attr.id,
                    'value_ids': [Command.set(size_value_ids)],
                }),
            ],
        })

    # ------------------------------------------------------------------
    # Test 1 — happy path: two axes, both enabled, both have property_id
    # ------------------------------------------------------------------
    def test_two_axes_publish_with_explicit_property_ids(self):
        """Material + Size both flagged publish=True with property_id → 2 dicts."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        material_attr.x_etsy_property_id = '200'
        material_attr.x_publish_as_property = True
        size_attr.x_etsy_property_id = '100'
        size_attr.x_publish_as_property = True

        tmpl = self._tmpl_material_size([ceramic.id], [size_s35.id])
        variant = tmpl.product_variant_ids[0]

        result = EtsyListingPublisher._collect_property_values(variant)

        self.assertEqual(len(result), 2)
        by_pid = {entry['property_id']: entry['values'] for entry in result}
        self.assertEqual(by_pid[200], ['Ceramic'])
        # Size value display name varies; assert structure only
        self.assertEqual(len(by_pid[100]), 1)

    # ------------------------------------------------------------------
    # Test 2 — axis flagged x_publish_as_property=False is excluded
    # ------------------------------------------------------------------
    def test_axis_with_publish_false_excluded(self):
        """When Size.x_publish_as_property=False, only Material appears."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        material_attr.x_etsy_property_id = '200'
        material_attr.x_publish_as_property = True
        size_attr.x_etsy_property_id = '100'
        size_attr.x_publish_as_property = False  # disabled

        tmpl = self._tmpl_material_size([ceramic.id], [size_s35.id])
        variant = tmpl.product_variant_ids[0]

        result = EtsyListingPublisher._collect_property_values(variant)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['property_id'], 200)
        self.assertEqual(result[0]['values'], ['Ceramic'])

    # ------------------------------------------------------------------
    # Test 3 — missing x_etsy_property_id logs WARNING and falls back to name
    # ------------------------------------------------------------------
    def test_missing_property_id_warns_and_falls_back_to_name(self):
        """When x_etsy_property_id is empty, fall back to attribute name +
        log WARNING (per playbook + memory 148)."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        # Material has no x_etsy_property_id; Size does
        material_attr.x_etsy_property_id = False
        material_attr.x_publish_as_property = True
        size_attr.x_etsy_property_id = '100'
        size_attr.x_publish_as_property = True

        tmpl = self._tmpl_material_size([ceramic.id], [size_s35.id])
        variant = tmpl.product_variant_ids[0]

        with self.assertLogs(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher',
            level='WARNING',
        ) as cm:
            result = EtsyListingPublisher._collect_property_values(variant)

        # WARNING logged for Material axis
        self.assertTrue(
            any('Material' in msg for msg in cm.output),
            f"Expected WARNING about Material attr, got {cm.output}",
        )
        # Material entry uses attribute name as property_id
        by_pid = {entry['property_id']: entry['values'] for entry in result}
        self.assertIn('Material', by_pid)
        self.assertEqual(by_pid['Material'], ['Ceramic'])

    # ------------------------------------------------------------------
    # Test 4 — empty M2M (dynamic-variant trap) returns []
    # ------------------------------------------------------------------
    def test_empty_variant_attribute_m2m_returns_empty_list(self):
        """When variant.product_template_attribute_value_ids is empty
        (no attribute lines on template), method returns []."""
        tmpl = self.Template.create({
            'name': 'Bare Item',
            'default_code': 'BARE-001',
            'list_price': 5.0,
        })
        variant = tmpl.product_variant_ids[0]

        # No attribute lines → ptav M2M is empty
        self.assertFalse(variant.product_template_attribute_value_ids)

        result = EtsyListingPublisher._collect_property_values(variant)
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # Test 5 — numeric property_id cast to int; non-numeric stays string
    # ------------------------------------------------------------------
    def test_property_id_int_cast_when_numeric_else_string(self):
        """x_etsy_property_id='12345' → int(12345); 'abc' → 'abc'."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        material_attr.x_etsy_property_id = '12345'
        material_attr.x_publish_as_property = True
        size_attr.x_etsy_property_id = 'abc'  # non-numeric stays as string
        size_attr.x_publish_as_property = True

        tmpl = self._tmpl_material_size([ceramic.id], [size_s35.id])
        variant = tmpl.product_variant_ids[0]

        result = EtsyListingPublisher._collect_property_values(variant)

        pids = {entry['property_id'] for entry in result}
        self.assertIn(12345, pids)  # int
        self.assertIn('abc', pids)  # str

    # ------------------------------------------------------------------
    # Test 6 — push_inventory embeds property_values per offering (no more [])
    # ------------------------------------------------------------------
    def test_push_inventory_embeds_property_values(self):
        """Full integration: push_inventory products[] entries carry
        property_values from _collect_property_values, not the hardcoded []."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        material_attr.x_etsy_property_id = '200'
        material_attr.x_publish_as_property = True
        size_attr.x_etsy_property_id = '100'
        size_attr.x_publish_as_property = True

        tmpl = self._tmpl_material_size([ceramic.id], [size_s35.id])
        shop = self._shop()

        captured = {}

        def fake_put(self_client, path, json=None, **_kw):  # noqa: ARG001
            captured['path'] = path
            captured['json'] = json
            return {'products': []}

        pub = EtsyListingPublisher(self.env)
        with patch.object(
            EtsyListingPublisher,
            '_sync_inventory_snapshot',
            return_value=None,
        ), patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient.put',
            new=fake_put,
        ):
            pub.push_inventory(tmpl, listing_id='LISTING-1', shop=shop)

        products = captured['json']['products']
        self.assertTrue(products, "push_inventory must emit at least one product")
        for entry in products:
            self.assertIn('property_values', entry)
            # Must not be the old hardcoded empty list when axes are configured
            self.assertNotEqual(
                entry['property_values'], [],
                "property_values must be populated when axes are configured",
            )
            # At least one of our two configured axes appears
            pids = {p['property_id'] for p in entry['property_values']}
            self.assertTrue(
                {100, 200} & pids,
                f"Expected at least one of {{100, 200}}, got {pids}",
            )

    # ------------------------------------------------------------------
    # Test 7 — sibling regression: materials[] still emitted alongside
    # ------------------------------------------------------------------
    def test_property_values_does_not_break_materials_collection(self):
        """P-PUB-MATERIALS sibling regression: materials[] still derived from
        template-level attribute lines while property_values flows per variant."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_s35 = self.env.ref('multichannel_hub_core.value_size_s35')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        material_attr.x_etsy_property_id = '200'
        material_attr.x_publish_as_property = True

        tmpl = self._tmpl_material_size([ceramic.id], [size_s35.id])
        shop = self._shop()

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        # _build_create_draft_payload is listing-level; materials[] must still
        # carry the template's Material values regardless of property_values flow
        self.assertIn('materials', payload)
        self.assertIn('Ceramic', payload['materials'])
