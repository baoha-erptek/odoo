"""Phase 2 ORM tests for personalization publisher payload (MP006, Spec 011).

R-PUB-RESPONSE-BODY-DIAGNOSE (2026-05-28): Etsy DEPRECATED the four inline
personalization fields on createListing (is_personalizable,
personalization_is_required, personalization_char_count_max,
personalization_instructions) — they now 400 ("Use the dedicated
personalization endpoints instead"). Per owner decision, emission is gated
OFF: the Odoo fields/UI stay (data preserved), but the publisher never sends
them on createListing. A follow-up slice will integrate Etsy's dedicated
personalization-migration endpoints.

These tests therefore assert the four keys are ALWAYS absent from the
createListing payload, regardless of x_is_personalizable.
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

    _DEPRECATED_KEYS = (
        'is_personalizable',
        'personalization_is_required',
        'personalization_char_count_max',
        'personalization_instructions',
    )

    def test_payload_omits_deprecated_keys_when_feature_off(self):
        """When x_is_personalizable=False, the 4 deprecated keys are absent."""
        tmpl = self._tmpl(
            'unpersonalized item',
            x_is_personalizable=False,
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        for key in self._DEPRECATED_KEYS:
            self.assertNotIn(key, payload)

    def test_payload_omits_deprecated_keys_even_when_feature_on(self):
        """Gate-off: even with x_is_personalizable=True, Etsy-deprecated keys
        are NOT emitted (they 400 createListing since 2026). The Odoo fields
        still store their values — only the createListing emission is gated.
        """
        tmpl = self._tmpl(
            'personalized item',
            x_is_personalizable=True,
            x_personalization_required=True,
            x_personalization_char_count=512,
            x_personalization_instructions='Specify thread color',
        )
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())

        for key in self._DEPRECATED_KEYS:
            self.assertNotIn(
                key, payload,
                f"{key} is deprecated by Etsy and must not be sent on createListing",
            )

    def test_odoo_personalization_fields_still_persist(self):
        """Gate-off does NOT delete the feature: the Odoo fields keep storing
        their values (data preserved for the future dedicated-endpoint slice).
        """
        tmpl = self._tmpl(
            'still stored',
            x_is_personalizable=True,
            x_personalization_required=True,
            x_personalization_char_count=512,
            x_personalization_instructions='Specify thread color',
        )
        self.assertTrue(tmpl.x_is_personalizable)
        self.assertTrue(tmpl.x_personalization_required)
        self.assertEqual(tmpl.x_personalization_char_count, 512)
        self.assertEqual(tmpl.x_personalization_instructions, 'Specify thread color')
