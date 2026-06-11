"""Phase 1 DB tests for P-LIST-IMAGE-GALLERY-SURFACE.

Surfaces the product's shared x_extra_image_ids gallery on the
multichannel.listing form via a writable related One2many
(extra_image_ids). These probes lock the *view* contract: the listing
form must carry the field + an "Images" page.

The gallery rows live on product.template (model
multichannel.product.image, P-PUB-MULTI-IMAGE); editing them through the
related field requires product.template write — by design (Odoo-standard
related-field write-through). No new ACL row is added, so there is
nothing ACL-shaped to assert here.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestListingImageGallerySurfaceView(TransactionCase):

    def test_form_arch_has_extra_image_ids_field(self):
        view = self.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form',
        )
        self.assertIn(
            'extra_image_ids', view.arch_db or '',
            'listing form must surface the extra_image_ids gallery field',
        )

    def test_form_arch_has_images_page(self):
        view = self.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form',
        )
        self.assertIn(
            'name="images"', view.arch_db or '',
            'listing form must carry an Images notebook page',
        )

    def test_extra_image_ids_field_is_related_one2many(self):
        field = self.env['multichannel.listing']._fields.get('extra_image_ids')
        self.assertIsNotNone(field, 'extra_image_ids field must be registered')
        self.assertEqual(field.type, 'one2many')
        # `related` is the dotted path string (ORM splits it on '.').
        self.assertEqual(field.related, 'product_tmpl_id.x_extra_image_ids')
        self.assertEqual(field.comodel_name, 'multichannel.product.image')
