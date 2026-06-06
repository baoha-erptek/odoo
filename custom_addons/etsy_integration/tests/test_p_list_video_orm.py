"""Phase 2 ORM tests for P-LIST-VIDEO (Wave 2 / Jira ESTY-199).

Covers:
- push_video posts multipart with binary + filename to Etsy when intent
  carries a video attachment.
- push_video is a no-op (returns {}) when intent has no video or no intent.
- run() orchestrator treats push_video failures as non-fatal (publish
  chain continues).

ADR-015 layer: video lives on multichannel.listing.video_attachment_id;
the publisher reads it via _resolve_listing_intent.
"""

import base64
from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestPushVideo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Template = cls.env['product.template']
        cls.Listing = cls.env['multichannel.listing']
        cls.Attachment = cls.env['ir.attachment']
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def _make_shop(self, api_id='8000001'):
        shop = self.env['etsy.shop'].create({
            'name': 'PLV TEST',
            'etsy_api_shop_id': api_id,
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })
        return shop

    def _make_tmpl_with_listing(self, video_bytes=None,
                                attachment_name='clip.mp4'):
        tmpl = self.Template.create({
            'name': 'PLV Template',
            'list_price': 10.0,
        })
        listing_vals = {
            'product_tmpl_id': tmpl.id,
            'channel_id': self.channel.id,
        }
        if video_bytes is not None:
            attach = self.Attachment.create({
                'name': attachment_name,
                'datas': base64.b64encode(video_bytes),
                'mimetype': 'video/mp4',
                'res_model': 'multichannel.listing',
                'public': False,
            })
            listing_vals['video_attachment_id'] = attach.id
        self.Listing.sudo().create(listing_vals)
        return tmpl

    def test_push_video_no_intent_returns_empty(self):
        """No multichannel.listing row → returns {} silently."""
        shop = self._make_shop()
        tmpl = self.Template.create({
            'name': 'PLV NoIntent',
            'list_price': 1.0,
        })
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            result = publisher.push_video(tmpl, 'LST-NV', shop)
            self.assertEqual(result, {})
            ClientCls.return_value.post_multipart.assert_not_called()

    def test_push_video_intent_without_attachment_returns_empty(self):
        shop = self._make_shop(api_id='8000002')
        tmpl = self._make_tmpl_with_listing(video_bytes=None)
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            result = publisher.push_video(tmpl, 'LST-NOA', shop)
            self.assertEqual(result, {})
            ClientCls.return_value.post_multipart.assert_not_called()

    def test_push_video_uploads_multipart_when_attached(self):
        shop = self._make_shop(api_id='8000003')
        # Tiny fake video bytes (publisher only b64-decodes, doesn't
        # validate container format).
        tmpl = self._make_tmpl_with_listing(
            video_bytes=b'\x00\x00\x00\x18ftypmp42PLV-TEST-CLIP',
            attachment_name='leather-tray-demo.mp4',
        )
        publisher = EtsyListingPublisher(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_listing_publisher.EtsyApiClient'
        ) as ClientCls:
            client = ClientCls.return_value
            client.post_multipart.return_value = {
                'video_id': 991, 'video_state': 'processing',
            }
            response = publisher.push_video(tmpl, 'LST-V42', shop)
        self.assertEqual(response['video_id'], 991)
        # Verify path + multipart shape
        args, kwargs = client.post_multipart.call_args
        self.assertEqual(args[0], 'shops/8000003/listings/LST-V42/videos')
        files = kwargs['files']
        self.assertIn('video', files)
        filename, payload_bytes, mimetype = files['video']
        self.assertEqual(filename, 'leather-tray-demo.mp4')
        self.assertTrue(payload_bytes.startswith(b'\x00\x00\x00\x18'))
        self.assertEqual(mimetype, 'video/mp4')
        data = kwargs['data']
        self.assertEqual(data['name'], 'leather-tray-demo.mp4')

    def test_run_orchestrator_continues_when_push_video_raises(self):
        """A push_video failure must not block publish."""
        shop = self._make_shop(api_id='8000004')
        # Shop defaults so create_draft can build payload
        shop.sudo().write({
            'default_taxonomy_id': '1',
            'default_shipping_profile_id': '1',
            'default_return_policy_id': '1',
        })
        tmpl = self._make_tmpl_with_listing(
            video_bytes=b'fake-video-bytes',
            attachment_name='broken.mp4',
        )
        # Seed channel status as if a previous create_draft had landed
        Status = self.env['product.channel.status'].sudo()
        Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.channel.id,
            'state': 'draft',
            'external_ref': 'LST-RUN1',
        })
        publisher = EtsyListingPublisher(self.env)
        with patch.object(publisher, 'push_video',
                          side_effect=RuntimeError('vendor flaky')):
            with patch.object(publisher, 'upload_images', return_value=[]):
                with patch.object(publisher, 'push_inventory',
                                  return_value={}):
                    with patch.object(publisher, 'push_variation_images',
                                      return_value=[]):
                        with patch.object(publisher, 'publish',
                                          return_value={'state': 'active'}):
                            with patch.object(publisher, 'push_personalization',
                                              return_value={}):
                                result = publisher.run(tmpl, shop)
        # publish() was reached despite push_video failure
        self.assertIn('listing_id', result)
