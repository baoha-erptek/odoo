"""Phase 2 ORM tests for P-PUB-MATERIALS publisher payload (MP006, Spec 011).

Verifies EtsyListingPublisher._build_create_draft_payload includes a `materials`
array extracted from variant attribute Material values, with charset cleaning
(special chars stripped) and 13-item cap enforced. When no Material attributes
are present, the `materials` key is omitted entirely.
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubMaterialsPayload(TransactionCase):
    """ORM tests for materials payload builder."""

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
        """Factory to create test etsy.shop."""
        return self.Shop.create({
            'name': 'MATERIALS TEST SHOP',
            'etsy_api_shop_id': '88888888',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def _tmpl(self, name='Test Product', list_price=10.0, material_value_ids=()):
        """Factory to create product.template with Material attribute line.

        Args:
            name: Template name
            list_price: Price
            material_value_ids: List of product.attribute.value IDs for Material attribute
        """
        vals = {
            'name': name,
            'default_code': name.upper().replace(' ', '-'),
            'list_price': list_price,
        }
        if material_value_ids:
            from odoo.addons.base.models.ir_model import Command
            material_attr = self.env.ref('multichannel_hub_core.attribute_material')
            vals['attribute_line_ids'] = [
                Command.create({
                    'attribute_id': material_attr.id,
                    'value_ids': [Command.set(material_value_ids)],
                })
            ]
        return self.Template.create(vals)

    def test_materials_emitted_when_variant_has_material_values(self):
        """When variant has Material attribute values, they appear in payload."""
        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        wood = self.env.ref('multichannel_hub_core.value_mat_wd')

        tmpl = self._tmpl(
            'Ceramic and Wood Item',
            material_value_ids=[ceramic.id, wood.id],
        )

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertIn('materials', payload)
        self.assertEqual(set(payload['materials']), {'Ceramic', 'Wood'})

    def test_materials_key_omitted_when_no_material_values(self):
        """When template has no Material attributes, materials key is absent."""
        tmpl = self._tmpl('No Materials Item', material_value_ids=[])

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertNotIn('materials', payload)

    def test_non_material_attributes_ignored(self):
        """When template has Material + Shape attributes, only Material appears."""
        from odoo.addons.base.models.ir_model import Command

        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        square = self.env.ref('multichannel_hub_core.value_shape_sq')

        material_attr = self.env.ref('multichannel_hub_core.attribute_material')
        shape_attr = self.env.ref('multichannel_hub_core.attribute_shape')

        vals = {
            'name': 'Shape + Material Item',
            'default_code': 'SHAPE-MAT',
            'list_price': 10.0,
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': material_attr.id,
                    'value_ids': [Command.set([ceramic.id])],
                }),
                Command.create({
                    'attribute_id': shape_attr.id,
                    'value_ids': [Command.set([square.id])],
                }),
            ]
        }
        tmpl = self.Template.create(vals)

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertIn('materials', payload)
        self.assertEqual(payload['materials'], ['Ceramic'])
        # Shape should not appear in materials
        self.assertNotIn('Square', str(payload.get('materials', [])))

    def test_charset_cleaned_special_chars_stripped(self):
        """Material value 'Ceramic + Chrome' becomes 'Ceramic Chrome' (charset cleaned)."""
        ceramic_chrome = self.env.ref('multichannel_hub_core.value_mat_cr')

        tmpl = self._tmpl(
            'Ceramic Chrome Item',
            material_value_ids=[ceramic_chrome.id],
        )

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertIn('materials', payload)
        # The name is "Ceramic + Chrome" but should be cleaned to "Ceramic Chrome"
        # (+ stripped, whitespace collapsed)
        self.assertEqual(payload['materials'], ['Ceramic Chrome'])

    def test_materials_capped_at_13(self):
        """When variant has > 13 Material values, payload includes only first 13."""
        # Create a synthetic Material attribute with 15 values for testing
        from odoo.addons.base.models.ir_model import Command

        material_attr = self.env.ref('multichannel_hub_core.attribute_material')

        # Create 15 additional Material values (beyond the 7 seeded ones)
        extra_values = self.env['product.attribute.value'].create([
            {
                'attribute_id': material_attr.id,
                'name': f'Material{i:02d}',
                'sequence': 100 + i,
            }
            for i in range(15)
        ])

        all_value_ids = [extra_values[i].id for i in range(15)]

        vals = {
            'name': 'Max Materials Item',
            'default_code': 'MAX-MAT',
            'list_price': 10.0,
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': material_attr.id,
                    'value_ids': [Command.set(all_value_ids)],
                })
            ]
        }
        tmpl = self.Template.create(vals)

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertIn('materials', payload)
        self.assertEqual(len(payload['materials']), 13)

    def test_material_paper_card_slash_stripped(self):
        """Material value 'Paper / Card' becomes 'Paper Card' (slash stripped)."""
        paper_card = self.env.ref('multichannel_hub_core.value_mat_pa')

        tmpl = self._tmpl(
            'Paper Card Item',
            material_value_ids=[paper_card.id],
        )

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertIn('materials', payload)
        # The name is "Paper / Card" but should be cleaned to "Paper Card"
        # (/ stripped, whitespace collapsed)
        self.assertEqual(payload['materials'], ['Paper Card'])

    def test_materials_preserves_other_payload_fields(self):
        """Adding materials does not affect other payload fields like tags."""
        from odoo.addons.base.models.ir_model import Command

        ceramic = self.env.ref('multichannel_hub_core.value_mat_ce')
        material_attr = self.env.ref('multichannel_hub_core.attribute_material')

        # Create tags for the template
        tag = self.env['product.tag'].create({'name': 'Handmade'})

        vals = {
            'name': 'Full Item',
            'default_code': 'FULL-ITEM',
            'list_price': 99.99,
            'product_tag_ids': [Command.set([tag.id])],
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': material_attr.id,
                    'value_ids': [Command.set([ceramic.id])],
                })
            ]
        }
        tmpl = self.Template.create(vals)

        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        # Verify both materials and tags are present
        self.assertIn('materials', payload)
        self.assertEqual(payload['materials'], ['Ceramic'])
        self.assertIn('tags', payload)
        self.assertEqual(payload['tags'], ['Handmade'])
        # And other core fields
        self.assertIn('title', payload)
        self.assertIn('price', payload)
