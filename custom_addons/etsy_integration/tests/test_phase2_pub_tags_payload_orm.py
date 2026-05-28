"""Phase 2 ORM tests for P-PUB-TAGS publisher payload (Spec 011, MP006).

Verifies EtsyListingPublisher._build_create_draft_payload includes a
`tags` array when present and omits the key entirely when empty.
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPubTagsPayloadORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(eac_module, '_read_credentials', return_value=_FAKE)
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Tag = cls.env['product.tag']
        cls.Shop = cls.env['etsy.shop']

    def _shop(self):
        return self.Shop.create({
            'name': 'TAG TEST SHOP',
            'etsy_api_shop_id': '77777777',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def _tmpl(self, name, list_price=10.0, tag_names=()):
        vals = {
            'name': name,
            'default_code': name.upper().replace(' ', '-'),
            'list_price': list_price,
        }
        if tag_names:
            tag_ids = self.Tag.create([{'name': n} for n in tag_names]).ids
            vals['product_tag_ids'] = [(6, 0, tag_ids)]
        return self.Template.create(vals)

    def test_payload_includes_tags_when_present(self):
        tmpl = self._tmpl('tagged item', tag_names=('Ceramic', 'Handmade'))
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())
        self.assertIn('tags', payload)
        self.assertEqual(set(payload['tags']), {'Ceramic', 'Handmade'})

    def test_payload_omits_tags_when_empty(self):
        tmpl = self._tmpl('untagged item')
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())
        self.assertNotIn('tags', payload)

    def test_payload_includes_thirteen_tags(self):
        names = tuple(f'tag{i}' for i in range(13))
        tmpl = self._tmpl('max tagged', tag_names=names)
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())
        self.assertEqual(len(payload['tags']), 13)

    def test_payload_single_tag(self):
        tmpl = self._tmpl('lone tag', tag_names=('Solo',))
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())
        self.assertEqual(payload['tags'], ['Solo'])

    def test_payload_special_chars_pass_through(self):
        names = ('Made-To-Order', "Customer's Pick")
        tmpl = self._tmpl('special chars', tag_names=names)
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())
        self.assertEqual(set(payload['tags']), set(names))

    def test_payload_other_fields_preserved(self):
        tmpl = self._tmpl('full item', list_price=99.99, tag_names=('Tag1',))
        pub = EtsyListingPublisher(self.env)
        payload = pub._build_create_draft_payload(tmpl, self._shop())
        for key in ('sku', 'title', 'description', 'price', 'tags'):
            self.assertIn(key, payload)
