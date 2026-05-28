"""P1-IMG-LINE-WIDGET — Phase 1 DB + Phase 2 ORM tests for product_image_thumb.

Computed Binary field on sale.order.line that returns
product_id.product_tmpl_id.image_128. Non-stored (no DB column);
fallback to image_downloader cron is async (out of scope here — see
P1-IMG-BACKFILL).
"""

import base64

from odoo.tests.common import TransactionCase, tagged


# 1x1 transparent PNG — smallest valid PNG, ~70 bytes
_PNG_1X1 = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA'
    b'DUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


@tagged('post_install', '-at_install')
class TestProductImageThumbDb(TransactionCase):
    """Phase 1: field-registration introspection.

    Non-stored computed Binary fields create no PG column, so we verify
    via ORM field metadata rather than information_schema.
    """

    def test_product_image_thumb_field_registered(self):
        field = self.env['sale.order.line']._fields.get('product_image_thumb')
        self.assertIsNotNone(
            field,
            'product_image_thumb must be defined on sale.order.line',
        )
        self.assertEqual(field.type, 'binary')
        self.assertIsNotNone(
            field.compute,
            'product_image_thumb must be a computed field',
        )
        self.assertFalse(
            field.store,
            'product_image_thumb must be non-stored (compute on read)',
        )

    def test_product_image_thumb_depends_on_image_128(self):
        # @api.depends populates _depends on the compute method itself in
        # Odoo 19; the field's `depends` attribute is empty for non-stored
        # computes until the registry resolves it.
        sol = self.env['sale.order.line']
        compute_name = sol._fields['product_image_thumb'].compute
        compute_method = getattr(sol, compute_name)
        depends = getattr(compute_method, '_depends', ())
        joined = ' '.join(str(d) for d in depends)
        self.assertIn(
            'image_128',
            joined,
            f'_compute_product_image_thumb must @api.depends on image_128; got {depends!r}',
        )


@tagged('post_install', '-at_install')
class TestProductImageThumbOrm(TransactionCase):
    """Phase 2: compute behavior across the 3 spec scenarios."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Image Thumb Test Partner',
            'email': 'imgthumb@example.com',
        })

        cls.product_with_image = cls.env['product.product'].create({
            'name': 'Product With Image',
            'is_storable': True,
            'list_price': 10.0,
            'image_1920': base64.b64encode(_PNG_1X1).decode('ascii'),
        })

        cls.product_no_image = cls.env['product.product'].create({
            'name': 'Product Without Image',
            'is_storable': True,
            'list_price': 10.0,
        })

    def _make_order_line(self, product, etsy_image_url=None):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        line_vals = {
            'order_id': order.id,
            'product_id': product.id if product else False,
            'product_uom_qty': 1.0,
        }
        if product is False:
            # Order line with no product (rare but valid in draft)
            line_vals.pop('product_id')
            line_vals['name'] = 'Free-text line, no product'
        if etsy_image_url is not None and 'etsy_image_url' in self.env['sale.order.line']._fields:
            line_vals['etsy_image_url'] = etsy_image_url
        return self.env['sale.order.line'].create(line_vals)

    def test_thumb_returns_image_128_when_product_has_image(self):
        line = self._make_order_line(self.product_with_image)
        # image_128 is auto-derived by Odoo's image-resize pipeline
        self.assertTrue(
            self.product_with_image.product_tmpl_id.image_128,
            'precondition: product image_128 should be auto-derived',
        )
        self.assertTrue(
            line.product_image_thumb,
            'product_image_thumb must be populated when product has image_128',
        )
        self.assertEqual(
            line.product_image_thumb,
            self.product_with_image.product_tmpl_id.image_128,
            'product_image_thumb must equal product.template.image_128',
        )

    def test_thumb_is_false_when_product_image_empty(self):
        # Async-not-yet-run: product exists but image_1920/128 not populated.
        # etsy_image_url may also be set; this slice does NOT trigger an on-read
        # download — that is P1-IMG-BACKFILL's responsibility via the existing
        # cron_download_pending_images.
        line = self._make_order_line(
            self.product_no_image,
            etsy_image_url='https://i.etsystatic.com/example.jpg',
        )
        self.assertFalse(
            line.product_image_thumb,
            'product_image_thumb must be False when product.image_128 is empty',
        )

    def test_thumb_is_false_when_no_product(self):
        line = self._make_order_line(False)
        self.assertFalse(
            line.product_id,
            'precondition: line has no product',
        )
        self.assertFalse(
            line.product_image_thumb,
            'product_image_thumb must be False when line has no product',
        )
