"""P1-IMG-DASH-COL — Phase 1 DB + Phase 2 ORM tests for order_image_128.

Computed Binary field on sale.order that returns the first non-empty
product_image_thumb from order_line_ids, with fallback to subsequent
lines if the first is empty. Non-stored (no DB column); evaluates on
read for dashboard rendering.

Depends on P1-IMG-LINE-WIDGET (product_image_thumb on sale.order.line).
"""

import base64

from odoo.tests.common import TransactionCase, tagged

# Import the shared test constant from the predecessor test
from .test_product_image_thumb import _PNG_1X1


@tagged('post_install', '-at_install')
class TestOrderImage128Db(TransactionCase):
    """Phase 1: field-registration introspection.

    Non-stored computed Binary fields create no PG column, so we verify
    via ORM field metadata rather than information_schema.
    """

    def test_order_image_128_field_registered(self):
        """Verify field exists on sale.order with correct type and compute."""
        field = self.env['sale.order']._fields.get('order_image_128')
        self.assertIsNotNone(
            field,
            'order_image_128 must be defined on sale.order',
        )
        self.assertEqual(field.type, 'binary')
        self.assertIsNotNone(
            field.compute,
            'order_image_128 must be a computed field',
        )
        self.assertFalse(
            field.store,
            'order_image_128 must be non-stored (compute on read)',
        )

    def test_order_image_128_depends_on_product_image_thumb(self):
        """Verify @api.depends includes product_image_thumb from order_line_ids.

        @api.depends populates _depends on the compute method itself in
        Odoo 19; the field's `depends` attribute is empty for non-stored
        computes until the registry resolves it.
        """
        so = self.env['sale.order']
        compute_name = so._fields['order_image_128'].compute
        compute_method = getattr(so, compute_name)
        depends = getattr(compute_method, '_depends', ())
        joined = ' '.join(str(d) for d in depends)
        self.assertIn(
            'product_image_thumb',
            joined,
            f'_compute_order_image_128 must @api.depends on product_image_thumb; got {depends!r}',
        )


@tagged('post_install', '-at_install')
class TestOrderImage128Orm(TransactionCase):
    """Phase 2: compute behavior across the 4 spec scenarios."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Order Image Test Partner',
            'email': 'orderimage@example.com',
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

    def _make_order(self, products):
        """Factory: create order with one line per product in iterable.

        :param products: iterable of product.product (or None for no-product line)
        :return: sale.order recordset (1 record)
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        for product in products:
            line_vals = {
                'order_id': order.id,
                'product_uom_qty': 1.0,
            }
            if product:
                line_vals['product_id'] = product.id
            else:
                line_vals['name'] = 'Free-text line, no product'
            self.env['sale.order.line'].create(line_vals)
        return order

    def test_single_line_with_image_returns_thumbnail(self):
        """Single-line order: product has image → order.order_image_128 is populated."""
        order = self._make_order([self.product_with_image])
        line = order.order_line

        # Precondition: line's product has image_128 (auto-derived from image_1920)
        self.assertTrue(
            self.product_with_image.product_tmpl_id.image_128,
            'precondition: product image_128 should be auto-derived from image_1920',
        )
        # Precondition: line's product_image_thumb is populated
        self.assertTrue(
            line.product_image_thumb,
            'precondition: line.product_image_thumb must be populated',
        )

        # Test: order's aggregate matches line's thumbnail
        self.assertTrue(
            order.order_image_128,
            'order_image_128 must be populated when order has line with image',
        )
        self.assertEqual(
            order.order_image_128,
            line.product_image_thumb,
            'order_image_128 must equal the first line\'s product_image_thumb',
        )

    def test_multiple_lines_fallback_to_second_when_first_empty(self):
        """Multi-line order: first line has no image, second has image → falls back."""
        order = self._make_order([self.product_no_image, self.product_with_image])
        lines = order.order_line

        # Preconditions
        self.assertFalse(
            lines[0].product_image_thumb,
            'precondition: first line should have no image',
        )
        self.assertTrue(
            lines[1].product_image_thumb,
            'precondition: second line should have image',
        )

        # Test: order image is the second line's thumbnail (fallback)
        self.assertTrue(
            order.order_image_128,
            'order_image_128 must fall back to second line when first is empty',
        )
        self.assertEqual(
            order.order_image_128,
            lines[1].product_image_thumb,
            'order_image_128 must equal the second line\'s product_image_thumb',
        )

    def test_all_lines_empty_returns_false(self):
        """Multi-line order: all products have no image → order.order_image_128 is False."""
        order = self._make_order([self.product_no_image, self.product_no_image])
        lines = order.order_line

        # Preconditions
        for i, line in enumerate(lines):
            self.assertFalse(
                line.product_image_thumb,
                f'precondition: line {i} should have no image',
            )

        # Test: order image is False when all lines are empty
        self.assertFalse(
            order.order_image_128,
            'order_image_128 must be False when all lines have no image',
        )

    def test_order_with_no_lines_returns_false(self):
        """Order with no lines → order.order_image_128 is False."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Precondition
        self.assertFalse(
            order.order_line,
            'precondition: order should have no lines',
        )

        # Test: order image is False when order has no lines
        self.assertFalse(
            order.order_image_128,
            'order_image_128 must be False when order has no lines',
        )
