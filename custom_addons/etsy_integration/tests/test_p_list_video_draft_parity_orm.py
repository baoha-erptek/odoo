"""Phase 2 ORM tests for P-LIST-VIDEO-DRAFT-PARITY.

The "Publish Draft Only" wizard action previously ran only
create_draft + upload_images + push_inventory and never pushed the
listing video — so a video attached to multichannel.listing was silently
omitted on the draft path (it only uploaded on the full publish chain).

These tests pin that action_run_publish_draft_only now also calls
push_video (best-effort) and that a push_video failure does not break the
draft publish.
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

_WIZ_MODULE = 'odoo.addons.etsy_integration.wizards.etsy_publish_wizard'


@tagged('post_install', '-at_install')
class TestDraftOnlyVideoParity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        # Wizard gate requires BA membership (FR-017).
        cls.env.user.write({
            'group_ids': [
                (4, cls.env.ref('multichannel_hub_core.group_ba_user').id),
            ],
        })
        cls.tmpl = cls.env['product.template'].create({
            'name': 'Draft Parity Tmpl', 'list_price': 9.0,
        })
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'DraftParityShop',
            'etsy_api_shop_id': '9000001',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })
        cls.wizard = cls.env['etsy.publish.wizard'].create({
            'product_tmpl_id': cls.tmpl.id,
            'shop_id': cls.shop.id,
        })

    def _patched_publisher(self):
        """Return a MagicMock publisher whose create_draft yields a
        listing_id; caller patches the wizard's class symbol with it."""
        publisher = MagicMock()
        publisher.create_draft.return_value = {'listing_id': 'LST-DRAFT-1'}
        publisher.upload_images.return_value = []
        publisher.push_inventory.return_value = {}
        publisher.push_video.return_value = {}
        return publisher

    def test_draft_only_calls_push_video(self):
        publisher = self._patched_publisher()
        with patch(f'{_WIZ_MODULE}.EtsyListingPublisher',
                   return_value=publisher):
            self.wizard.action_run_publish_draft_only()
        publisher.push_video.assert_called_once_with(
            self.tmpl, 'LST-DRAFT-1', self.shop,
        )

    def test_draft_only_push_video_failure_is_non_fatal(self):
        publisher = self._patched_publisher()
        publisher.push_video.side_effect = RuntimeError('vendor flaky')
        with patch(f'{_WIZ_MODULE}.EtsyListingPublisher',
                   return_value=publisher):
            # Must not raise — draft publish completes despite video failure.
            result = self.wizard.action_run_publish_draft_only()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        publisher.push_video.assert_called_once()

    def test_draft_only_still_uploads_images_and_inventory(self):
        publisher = self._patched_publisher()
        with patch(f'{_WIZ_MODULE}.EtsyListingPublisher',
                   return_value=publisher):
            self.wizard.action_run_publish_draft_only()
        publisher.upload_images.assert_called_once()
        publisher.push_inventory.assert_called_once()
