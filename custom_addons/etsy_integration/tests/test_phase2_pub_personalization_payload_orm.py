"""Phase 2 ORM tests for P-PUB-PERSONALIZATION publisher payload (MP006, Spec 011).

Verifies EtsyListingPublisher._build_create_draft_payload includes
personalization keys when x_is_personalizable=True and omits them
entirely when x_is_personalizable=False.
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubPersonalizationPayload(TransactionCase):
    """ORM tests for personalization payload builder."""

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
            'name': 'PERSONALIZATION TEST SHOP',
            'etsy_api_shop_id': '99999999',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def _tmpl(self, name='Test Product', list_price=10.0, **personalization_kwargs):
        """Factory to create product.template with personalization fields."""
        vals = {
            'name': name,
            'default_code': name.upper().replace(' ', '-'),
            'list_price': list_price,
        }
        vals.update(personalization_kwargs)
        return self.Template.create(vals)

    def test_payload_omits_all_4_keys_when_feature_off(self):
        """When x_is_personalizable=False, all 4 keys absent from payload."""
        tmpl = self._tmpl(
            'unersonalized item',
            x_is_personalizable=False,
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        # Verify all 4 keys are absent
        self.assertNotIn('is_personalizable', payload)
        self.assertNotIn('personalization_is_required', payload)
        self.assertNotIn('personalization_char_count_max', payload)
        self.assertNotIn('personalization_instructions', payload)

    def test_payload_includes_all_4_keys_when_feature_on(self):
        """When x_is_personalizable=True, all 4 keys present with correct values."""
        tmpl = self._tmpl(
            'personalized item',
            x_is_personalizable=True,
            x_personalization_required=False,
            x_personalization_char_count=512,
            x_personalization_instructions='Specify thread color',
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertIn('is_personalizable', payload)
        self.assertEqual(payload['is_personalizable'], True)

        self.assertIn('personalization_is_required', payload)
        self.assertEqual(payload['personalization_is_required'], False)

        self.assertIn('personalization_char_count_max', payload)
        self.assertEqual(payload['personalization_char_count_max'], 512)

        self.assertIn('personalization_instructions', payload)
        self.assertEqual(payload['personalization_instructions'], 'Specify thread color')

    def test_payload_required_flag_reflects_field(self):
        """When x_personalization_required=True, payload reflects it."""
        tmpl = self._tmpl(
            'required personalization',
            x_is_personalizable=True,
            x_personalization_required=True,
            x_personalization_char_count=100,
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertEqual(payload['personalization_is_required'], True)

    def test_payload_char_count_falls_back_to_256_when_null(self):
        """When char_count is NULL, payload defaults to 256."""
        tmpl = self._tmpl(
            'default char count',
            x_is_personalizable=True,
            x_personalization_required=False,
            # Leave char_count at default (NULL or 256)
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertEqual(payload['personalization_char_count_max'], 256)

    def test_payload_instructions_empty_string_when_null(self):
        """When instructions is NULL, payload has empty string, not None."""
        tmpl = self._tmpl(
            'no instructions',
            x_is_personalizable=True,
            x_personalization_required=False,
            x_personalization_char_count=100,
            # Leave instructions NULL
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        self.assertEqual(payload['personalization_instructions'], '')
        self.assertIsNotNone(payload['personalization_instructions'])
