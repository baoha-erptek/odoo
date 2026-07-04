"""Phase 2 ORM tests for P-LIST-IMAGE-GALLERY-SURFACE.

The listing form exposes the product's shared gallery
(product.template.x_extra_image_ids) through a writable related
One2many `multichannel.listing.extra_image_ids`. These tests verify the
write-through and read-back both directions, and that ordering follows
the gallery sequence (the Etsy publisher iterates by sequence).
"""

from odoo.tests.common import TransactionCase, tagged

# Valid 1x1 PNG (PIL-generated) — fields.Image runs the bytes through PIL,
# so the payload must be a genuinely decodable image, not a truncated stub.
_PNG_1PX = (
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8'
    b'AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC'
)


@tagged('post_install', '-at_install')
class TestListingExtraImageRelated(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.tmpl = cls.env['product.template'].create({
            'name': 'Gallery Surface Tmpl',
            'list_price': 12.0,
        })
        cls.listing = cls.env['multichannel.listing'].create({
            'product_tmpl_id': cls.tmpl.id,
            'channel_id': cls.channel.id,
        })

    def test_create_through_listing_lands_on_product(self):
        self.listing.extra_image_ids = [
            (0, 0, {'name': 'front', 'sequence': 10, 'image_1920': _PNG_1PX}),
        ]
        self.assertEqual(len(self.tmpl.x_extra_image_ids), 1)
        self.assertEqual(self.tmpl.x_extra_image_ids.name, 'front')

    def test_read_back_through_listing(self):
        self.tmpl.x_extra_image_ids = [
            (0, 0, {'name': 'side', 'sequence': 20, 'image_1920': _PNG_1PX}),
        ]
        names = self.listing.extra_image_ids.mapped('name')
        self.assertIn('side', names)

    def test_ordering_follows_sequence(self):
        self.tmpl.x_extra_image_ids = [
            (0, 0, {'name': 'b', 'sequence': 20, 'image_1920': _PNG_1PX}),
            (0, 0, {'name': 'a', 'sequence': 10, 'image_1920': _PNG_1PX}),
        ]
        # multichannel.product.image _order = 'sequence, id'
        self.assertEqual(
            self.listing.extra_image_ids.mapped('name'), ['a', 'b'],
        )

    def test_unlink_through_listing_removes_from_product(self):
        self.listing.extra_image_ids = [
            (0, 0, {'name': 'gone', 'sequence': 10, 'image_1920': _PNG_1PX}),
        ]
        row = self.tmpl.x_extra_image_ids
        self.assertEqual(len(row), 1)
        self.listing.extra_image_ids = [(2, row.id, 0)]
        self.assertEqual(len(self.tmpl.x_extra_image_ids), 0)
