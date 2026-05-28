"""Phase 2 ORM tests for R-PUB-PERSONALIZATION-ENDPOINTS (MP006 Spec 011).

Etsy deprecated inline personalization fields on createListing (2026-05-28).
This slice implements a dedicated `push_personalization` method + integration
into the publish orchestrator's `run()` chain via Etsy's per-listing
personalization endpoint.

Tests assert the FINAL contract (they error at RED because the method does
not exist yet, and pass once implemented):
  - push_personalization(tmpl, listing_id, shop) validation + API call
  - char_count passes through (ORM constraint already pins it to 1-1024);
    instructions truncated to Etsy's 256-char ceiling at the API boundary
  - run() orchestrator integration + resilience on personalization failure
"""

from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubPersonalizationEndpoints(TransactionCase):
    """ORM tests for push_personalization method and run() integration."""

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
        cls.Status = cls.env['product.channel.status']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(
            active_test=False
        )
        cls.etsy_channel = ChannelAll.search([('code', '=', 'etsy')], limit=1)

    def _shop(self, **kwargs):
        """Factory to create test etsy.shop with required publisher defaults."""
        defaults = {
            'name': 'PERSONALIZATION TEST SHOP',
            'etsy_api_shop_id': '99999999',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
            'default_taxonomy_id': 1,
            'default_shipping_profile_id': 2,
            'default_return_policy_id': 3,
            'default_who_made': 'i_did',
            'default_when_made': 'made_to_order',
        }
        defaults.update(kwargs)
        return self.Shop.create(defaults)

    def _tmpl(self, name='Test Product', list_price=10.0, **personalization_kwargs):
        """Factory to create product.template with personalization fields."""
        vals = {
            'name': name,
            'default_code': name.upper().replace(' ', '-'),
            'list_price': list_price,
        }
        vals.update(personalization_kwargs)
        return self.Template.create(vals)

    @staticmethod
    def _mock_client_cls(client):
        """Patch the EtsyApiClient symbol used inside the publisher module."""
        return patch(
            'odoo.addons.etsy_integration.services.'
            'etsy_listing_publisher.EtsyApiClient',
            return_value=client,
        )

    @staticmethod
    def _sole_question(client):
        """Extract the single personalization question dict from the last
        client.post call's json payload."""
        _, kwargs = client.post.call_args
        payload = kwargs['json']
        questions = payload['personalization_questions']
        assert len(questions) == 1, "Etsy migration period allows one question"
        return questions[0]

    # ------------------------------------------------------------------
    # push_personalization validation
    # ------------------------------------------------------------------

    def test_push_personalization_raises_without_listing_id(self):
        """Falsy listing_id → ValueError before any client construction."""
        tmpl = self._tmpl('no-listing-test', x_is_personalizable=True)
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        with self.assertRaises(ValueError) as ctx:
            pub.push_personalization(tmpl, None, shop)
        self.assertIn('listing_id', str(ctx.exception))

    def test_push_personalization_no_op_when_disabled(self):
        """x_is_personalizable=False → returns {} and makes NO client call."""
        tmpl = self._tmpl('disabled-personalization', x_is_personalizable=False)
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        client = MagicMock()
        with self._mock_client_cls(client):
            result = pub.push_personalization(tmpl, '12345', shop)

        self.assertEqual(result, {})
        client.post.assert_not_called()

    def test_push_personalization_raises_without_api_shop_id(self):
        """Enabled feature but blank shop.etsy_api_shop_id → ValueError."""
        tmpl = self._tmpl('no-shop-id-test', x_is_personalizable=True)
        shop = self._shop(etsy_api_shop_id='')
        pub = EtsyListingPublisher(self.env)

        with self.assertRaises(ValueError) as ctx:
            pub.push_personalization(tmpl, '12345', shop)
        self.assertIn('etsy_api_shop_id', str(ctx.exception))

    # ------------------------------------------------------------------
    # Payload shape + _clamp_personalization (via payload assertions)
    # ------------------------------------------------------------------

    def test_push_personalization_builds_single_text_input_question(self):
        """Payload = one text_input question; path targets the listing."""
        tmpl = self._tmpl(
            'payload-test',
            x_is_personalizable=True,
            x_personalization_required=True,
            x_personalization_char_count=100,
            x_personalization_instructions='Specify initials',
        )
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        client = MagicMock()
        client.post.return_value = {'personalization_questions': []}
        with self._mock_client_cls(client):
            pub.push_personalization(tmpl, '12345', shop)

        client.post.assert_called_once()
        path, _ = client.post.call_args[0], client.post.call_args[1]
        self.assertEqual(
            client.post.call_args[0][0],
            'shops/99999999/listings/12345/personalization',
        )
        q = self._sole_question(client)
        self.assertEqual(q['question_type'], 'text_input')
        self.assertEqual(q['question_text'], 'Personalization')
        self.assertEqual(q['instructions'], 'Specify initials')
        self.assertTrue(q['required'])
        self.assertEqual(q['max_allowed_characters'], 100)

    def test_push_personalization_passes_char_count_through(self):
        """max_allowed_characters mirrors the stored char_count.

        The ORM constraint `_check_personalization_char_count` already pins
        x_personalization_char_count to [1,1024] when personalization is on,
        so the publisher passes the value straight through (no clamp).
        """
        tmpl = self._tmpl(
            'char-count-test',
            x_is_personalizable=True,
            x_personalization_char_count=512,
            x_personalization_instructions='Any text',
        )
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        client = MagicMock()
        client.post.return_value = {}
        with self._mock_client_cls(client):
            pub.push_personalization(tmpl, '12345', shop)

        self.assertEqual(self._sole_question(client)['max_allowed_characters'], 512)

    def test_push_personalization_truncates_instructions_to_256(self):
        """instructions > 256 chars → truncated to 256."""
        tmpl = self._tmpl(
            'long-instr-test',
            x_is_personalizable=True,
            x_personalization_char_count=100,
            x_personalization_instructions='x' * 300,
        )
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        client = MagicMock()
        client.post.return_value = {}
        with self._mock_client_cls(client):
            pub.push_personalization(tmpl, '12345', shop)

        self.assertEqual(self._sole_question(client)['instructions'], 'x' * 256)

    # ------------------------------------------------------------------
    # run() orchestrator integration
    # ------------------------------------------------------------------

    def _full_chain_client(self):
        client = MagicMock()
        client.post.return_value = {'listing_id': 12345}
        client.post_multipart.return_value = {'listing_image_id': 9}
        client.put.return_value = {'products': []}
        client.patch.return_value = {'state': 'active'}
        return client

    def test_run_calls_push_personalization_after_create_draft(self):
        """run() issues a POST to the /personalization endpoint for the listing."""
        tmpl = self._tmpl(
            'run-integration-test',
            x_is_personalizable=True,
            x_personalization_required=True,
            x_personalization_char_count=256,
            x_personalization_instructions='Test instruction',
        )
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        client = self._full_chain_client()
        with self._mock_client_cls(client):
            pub.run(tmpl, shop)

        paths = [c.args[0] for c in client.post.call_args_list if c.args]
        self.assertTrue(
            any(p.endswith('/personalization') for p in paths),
            "run() must POST to the personalization endpoint; saw %r" % paths,
        )
        # createListing must still be issued before personalization
        self.assertTrue(
            any(p == 'shops/99999999/listings' for p in paths),
            "create_draft POST must precede personalization; saw %r" % paths,
        )

    def test_run_continues_when_personalization_post_fails(self):
        """A personalization POST failure is non-fatal — run() still publishes."""
        tmpl = self._tmpl(
            'personalization-resilience-test',
            x_is_personalizable=True,
            x_personalization_char_count=100,
            x_personalization_instructions='Test',
        )
        shop = self._shop()
        pub = EtsyListingPublisher(self.env)

        client = MagicMock()

        def post_side_effect(path, **kwargs):
            if path.endswith('/personalization'):
                raise Exception("Personalization endpoint failed (simulated)")
            return {'listing_id': 12345}

        client.post.side_effect = post_side_effect
        client.post_multipart.return_value = {'listing_image_id': 9}
        client.put.return_value = {'products': []}
        client.patch.return_value = {'state': 'active'}

        with self._mock_client_cls(client):
            pub.run(tmpl, shop)

        status = self.Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', self.etsy_channel.id),
        ])
        self.assertEqual(status.state, 'published')
        self.assertFalse(status.last_sync_error)
