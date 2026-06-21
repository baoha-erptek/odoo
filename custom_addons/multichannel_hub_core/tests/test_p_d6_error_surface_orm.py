"""Phase D#6 — surface the publisher error on the listing form.

Flow 1 mockup screen 4 ("Error Modal — 400 from Etsy"). The Etsy error body is
captured by EtsyListingPublisher and persisted on product.channel.status; this
mirrors it read-only onto multichannel.listing.last_sync_error so an operator
can diagnose a failed publish without re-running it.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestListingErrorSurface(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.product = cls.env['product.template'].create({'name': 'Err Demo Mug'})
        cls.listing = cls.env['multichannel.listing'].create({
            'product_tmpl_id': cls.product.id,
            'channel_id': cls.channel.id,
            'state': 'error',
        })

    def test_error_mirrored_from_channel_status(self):
        msg = 'Etsy 400: readiness_state_id required for physical listings'
        self.env['product.channel.status'].create({
            'product_tmpl_id': self.product.id,
            'channel_id': self.channel.id,
            'state': 'error',
            'last_sync_error': msg,
        })
        self.listing.invalidate_recordset(['last_sync_error'])
        self.assertEqual(self.listing.last_sync_error, msg)

    def test_no_status_row_yields_no_error(self):
        # No product.channel.status row for this (product, channel) yet.
        self.assertFalse(self.listing.last_sync_error)
