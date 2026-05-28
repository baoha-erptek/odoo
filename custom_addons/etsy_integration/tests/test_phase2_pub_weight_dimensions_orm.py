"""Phase 2 ORM tests for P-PUB-WEIGHT-DIMENSIONS (MP006, Spec 011).

Verifies EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)
converts template weight (kg) to shop unit preference (oz/g) and extracts
rectangle dimensions from Size attribute values (R30X18 pattern).

Also covers full _build_create_draft_payload integration to confirm
weight + dimension keys are wired into the listing payload.
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubWeightDimensionsPayload(TransactionCase):
    """ORM tests for _collect_weight_and_dimensions + integration."""

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

    def _shop(self, weight_pref='oz', dim_pref='cm'):
        """Create a test shop with weight/dimension preferences."""
        return self.Shop.create({
            'name': f'WEIGHT_DIM TEST SHOP {weight_pref}/{dim_pref}',
            'etsy_api_shop_id': '99999999',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
            'weight_unit_pref': weight_pref,
            'dimensions_unit_pref': dim_pref,
        })

    def _tmpl_with_size(self, weight=0.0, size_value_name=None):
        """Create template with optional Size attribute value."""
        from odoo.addons.base.models.ir_model import Command
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        kwargs = {
            'name': 'Weight Dim Item',
            'default_code': 'WD-001',
            'list_price': 10.0,
            'weight': weight,
        }

        if size_value_name:
            # Create or find the Size attribute value
            size_val = self.env['product.attribute.value'].search([
                ('attribute_id', '=', size_attr.id),
                ('name', '=', size_value_name),
            ])
            if not size_val:
                size_val = self.env['product.attribute.value'].create({
                    'attribute_id': size_attr.id,
                    'name': size_value_name,
                })

            kwargs['attribute_line_ids'] = [
                Command.create({
                    'attribute_id': size_attr.id,
                    'value_ids': [Command.set([size_val.id])],
                }),
            ]

        return self.Template.create(kwargs)

    # ------------------------------------------------------------------
    # Test 1 — Weight conversion: kg → oz
    # ------------------------------------------------------------------
    def test_weight_kg_to_oz_conversion(self):
        """tmpl.weight=0.35 kg, shop pref 'oz' → item_weight = 12.35 oz."""
        tmpl = self._tmpl_with_size(weight=0.35)
        shop = self._shop(weight_pref='oz')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_weight', result)
        self.assertIn('item_weight_unit', result)
        self.assertAlmostEqual(result['item_weight'], 12.35, places=2)
        self.assertEqual(result['item_weight_unit'], 'oz')

    # ------------------------------------------------------------------
    # Test 2 — Weight conversion: kg → g
    # ------------------------------------------------------------------
    def test_weight_kg_to_g_conversion(self):
        """tmpl.weight=0.5 kg, shop pref 'g' → item_weight = 500.0 g."""
        tmpl = self._tmpl_with_size(weight=0.5)
        shop = self._shop(weight_pref='g')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_weight', result)
        self.assertIn('item_weight_unit', result)
        self.assertAlmostEqual(result['item_weight'], 500.0, places=2)
        self.assertEqual(result['item_weight_unit'], 'g')

    # ------------------------------------------------------------------
    # Test 3 — Weight zero omitted
    # ------------------------------------------------------------------
    def test_weight_zero_omitted(self):
        """tmpl.weight=0 → no item_weight or item_weight_unit keys."""
        tmpl = self._tmpl_with_size(weight=0.0)
        shop = self._shop(weight_pref='oz')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertNotIn('item_weight', result)
        self.assertNotIn('item_weight_unit', result)

    # ------------------------------------------------------------------
    # Test 4 — Weight negative omitted
    # ------------------------------------------------------------------
    def test_weight_negative_omitted(self):
        """tmpl.weight=-0.1 → no weight keys, no crash."""
        tmpl = self._tmpl_with_size(weight=-0.1)
        shop = self._shop(weight_pref='oz')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertNotIn('item_weight', result)
        self.assertNotIn('item_weight_unit', result)

    # ------------------------------------------------------------------
    # Test 5 — Dimensions: rect pattern with leading R
    # ------------------------------------------------------------------
    def test_dimensions_rect_pattern_leading_R(self):
        """Size value 'R30X18', shop dim 'cm' → length=30, width=18."""
        tmpl = self._tmpl_with_size(weight=0.1, size_value_name='R30X18')
        shop = self._shop(weight_pref='oz', dim_pref='cm')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_length', result)
        self.assertIn('item_width', result)
        self.assertIn('item_dimensions_unit', result)
        self.assertEqual(result['item_length'], 30)
        self.assertEqual(result['item_width'], 18)
        self.assertEqual(result['item_dimensions_unit'], 'cm')

    # ------------------------------------------------------------------
    # Test 6 — Dimensions: no leading R, in inches
    # ------------------------------------------------------------------
    def test_dimensions_inch_unit_no_leading_R(self):
        """Size value '12X18', shop dim 'in' → length=12, width=18, unit='in'."""
        tmpl = self._tmpl_with_size(weight=0.2, size_value_name='12X18')
        shop = self._shop(weight_pref='oz', dim_pref='in')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_length', result)
        self.assertIn('item_width', result)
        self.assertIn('item_dimensions_unit', result)
        self.assertEqual(result['item_length'], 12)
        self.assertEqual(result['item_width'], 18)
        self.assertEqual(result['item_dimensions_unit'], 'in')

    # ------------------------------------------------------------------
    # Test 6b — Dimensions: 3D rect pattern → item_height
    # ------------------------------------------------------------------
    def test_dimensions_rect_pattern_3d_height(self):
        """Size value 'R30X18X2' → length=30, width=18, height=2 (P-PUB-ITEM-HEIGHT)."""
        tmpl = self._tmpl_with_size(weight=0.1, size_value_name='R30X18X2')
        shop = self._shop(weight_pref='oz', dim_pref='cm')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertEqual(result['item_length'], 30)
        self.assertEqual(result['item_width'], 18)
        self.assertEqual(result['item_height'], 2)
        self.assertEqual(result['item_dimensions_unit'], 'cm')

    # ------------------------------------------------------------------
    # Test 6c — 2D rect omits item_height (regression)
    # ------------------------------------------------------------------
    def test_dimensions_rect_pattern_2d_omits_height(self):
        """Size value 'R30X18' (2D) → length/width set, no item_height key."""
        tmpl = self._tmpl_with_size(weight=0.1, size_value_name='R30X18')
        shop = self._shop(weight_pref='oz', dim_pref='cm')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_length', result)
        self.assertIn('item_width', result)
        self.assertNotIn('item_height', result)

    # ------------------------------------------------------------------
    # Test 7 — No Size axis → no dimension keys
    # ------------------------------------------------------------------
    def test_no_size_axis_dimensions_omitted(self):
        """Template w/o Size attribute, weight=0.25 oz pref → only weight keys."""
        tmpl = self._tmpl_with_size(weight=0.25, size_value_name=None)
        shop = self._shop(weight_pref='oz', dim_pref='cm')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_weight', result)
        self.assertIn('item_weight_unit', result)
        self.assertNotIn('item_length', result)
        self.assertNotIn('item_width', result)
        self.assertNotIn('item_dimensions_unit', result)

    # ------------------------------------------------------------------
    # Test 8 — Mug Size value (non-rect pattern) → no dimension keys
    # ------------------------------------------------------------------
    def test_size_value_non_rect_pattern_omits_dimensions(self):
        """Size value '11 oz' (Mug family) → only weight keys; no dimensions."""
        tmpl = self._tmpl_with_size(weight=0.3, size_value_name='11 oz')
        shop = self._shop(weight_pref='oz', dim_pref='cm')

        result = EtsyListingPublisher._collect_weight_and_dimensions(tmpl, shop)

        self.assertIn('item_weight', result)
        self.assertIn('item_weight_unit', result)
        self.assertNotIn('item_length', result)
        self.assertNotIn('item_width', result)
        self.assertNotIn('item_dimensions_unit', result)

    # ------------------------------------------------------------------
    # Test 9 — Full payload integration
    # ------------------------------------------------------------------
    def test_payload_integration_create_draft(self):
        """_build_create_draft_payload returns payload with weight + dimension keys."""
        tmpl = self._tmpl_with_size(weight=0.25, size_value_name='R30X18')
        shop = self._shop(weight_pref='oz', dim_pref='cm')

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        # Weight keys present
        self.assertIn('item_weight', payload)
        self.assertIn('item_weight_unit', payload)
        # Dimension keys present
        self.assertIn('item_length', payload)
        self.assertIn('item_width', payload)
        self.assertIn('item_dimensions_unit', payload)
        # Existing keys still present (regression)
        self.assertIn('sku', payload)
        self.assertIn('title', payload)
        self.assertIn('taxonomy_id', payload)
        self.assertEqual(payload['state'], 'draft')

    # ------------------------------------------------------------------
    # Test 10 — Sibling keys regression
    # ------------------------------------------------------------------
    def test_sibling_keys_preserved(self):
        """Existing payload keys (tags, materials) not broken by weight/dimensions."""
        from odoo.addons.base.models.ir_model import Command
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        size_attr = self.env.ref('multichannel_hub_core.attribute_size')

        # Find or create Size R30X18
        size_val = self.env['product.attribute.value'].search([
            ('attribute_id', '=', size_attr.id),
            ('name', '=', 'R30X18'),
        ])
        if not size_val:
            size_val = self.env['product.attribute.value'].create({
                'attribute_id': size_attr.id,
                'name': 'R30X18',
            })

        tmpl = self.Template.create({
            'name': 'Sibling Test Item',
            'default_code': 'SIB-001',
            'list_price': 20.0,
            'weight': 0.5,
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': material_attr.id,
                    'value_ids': [Command.set([ceramic.id])],
                }),
                Command.create({
                    'attribute_id': size_attr.id,
                    'value_ids': [Command.set([size_val.id])],
                }),
            ],
        })

        shop = self._shop(weight_pref='oz', dim_pref='cm')

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, shop)

        # New weight/dimensions keys
        self.assertIn('item_weight', payload)
        self.assertIn('item_dimensions_unit', payload)
        # Existing P-PUB-MATERIALS keys still present
        self.assertIn('materials', payload)
        self.assertIn('Ceramic', payload['materials'])
        # Regression: sku + title still in payload
        self.assertIn('sku', payload)
        self.assertIn('title', payload)
