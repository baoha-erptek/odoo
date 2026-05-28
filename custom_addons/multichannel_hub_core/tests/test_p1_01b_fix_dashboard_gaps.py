"""P1-01b-FIX-DASHBOARD-GAPS — Phase 2 ORM tests (2026-05-10).

Three deltas under test:

1. ``order_id`` column surfaced on the Operations Dashboard tree view
   (``operations_dashboard_list_view``). Verified by inspecting the view
   ``arch_db`` for the new ``<field name="order_id">`` node.

2. ``sale.order.line.label_status_id`` flipped from related-readonly to
   related-writable so the dashboard supports inline edit. Verified by
   writing on the line and reading back the parent order's label.

3. ``OrderCreator`` mirrors parsed values into channel-agnostic shadows
   on both ``sale.order`` (gift_message, processing_time, discount_code,
   shipping_service_label, shipping_cost) and ``sale.order.line``
   (transaction_id, personalisation, image_url, design_link_front,
   design_link_back, plus *_manual variant labels). Verified via direct
   call to ``OrderCreator.process_parse_result`` with a stubbed
   ParseResult, then field reads on the created order + line.

References: ``.claude/plans/quirky-shimmying-charm.md`` Annex A;
``specs/003-dashboard-design-multichannel/p1-01b-plan.md`` DECISION 1.
"""
import logging
from types import SimpleNamespace

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDashboardGapsP101bFix(TransactionCase):
    """Phase 2 ORM verification for the 3 dashboard-gap deltas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'P101b-FIX Test Buyer',
            'email': 'p101b@example.com',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'P101b-FIX Test Product',
            'list_price': 25.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1.0,
            })],
        })
        cls.line = cls.order.order_line[:1]

    # -----------------------------------------------------------------
    # Delta 1 — Dashboard view exposes order_id
    # -----------------------------------------------------------------
    def test_view_arch_includes_order_id_column(self):
        """The Operations Dashboard list view declares an order_id column."""
        view = self.env.ref(
            'multichannel_hub_core.operations_dashboard_list_view')
        self.assertIn(
            'name="order_id"',
            view.arch_db,
            'Operations Dashboard should expose <field name="order_id"> column '
            '(P1-01b-FIX-DASHBOARD-GAPS delta 1).',
        )

    # -----------------------------------------------------------------
    # Delta 2 — label_status_id is writable from the line
    # -----------------------------------------------------------------
    def test_label_status_id_writable_via_line(self):
        """Writing label_status_id on a line propagates to the parent order."""
        # Pick any seeded label.status.option, or create an isolated one.
        label = self.env['label.status.option'].search(
            [('active', '=', True)], limit=1)
        if not label:
            label = self.env['label.status.option'].create({
                'name': 'P101b-FIX Test Label',
                'code': 'P101B_TEST',
                'bucket': 'target',
            })

        # The field must NOT be readonly on the line model definition.
        field = self.env['sale.order.line']._fields['label_status_id']
        self.assertFalse(
            field.readonly,
            'sale.order.line.label_status_id should be writable '
            '(P1-01b-FIX-DASHBOARD-GAPS delta 2).',
        )

        # Write through the line; expect related write-through to order.
        self.line.write({'label_status_id': label.id})
        self.line.invalidate_recordset()
        self.assertEqual(
            self.order.label_status_id,
            label,
            'Writing label_status_id on the line should propagate to '
            'order_id.label_status_id (related-writable path).',
        )

    # -----------------------------------------------------------------
    # Delta 3 — OrderCreator mirrors channel-agnostic shadows
    # -----------------------------------------------------------------
    def test_order_creator_backfills_channel_agnostic_fields(self):
        """``process_parse_result`` writes channel-agnostic shadow fields.

        We construct a minimal ``ParseResult``-shaped namespace, call
        ``OrderCreator.process_parse_result``, then assert both order- and
        line-level shadows are populated.
        """
        from odoo.addons.etsy_integration.services.order_creator import OrderCreator

        # Arrange — a parse result with all the fields we expect to mirror.
        txn = SimpleNamespace(
            transaction_id='9999900001',
            product_name='P101b-FIX Mirror Product',
            sku='P101B-MIRROR',
            quantity=2,
            price=12.5,
            personalisation='Happy Birthday',
            option='Print Side: Front',
            color='Red',
            size='Medium',
            side='Front',
            face_mask_size='Adult',
            image_url='https://example.com/p101b.jpg',
            design_link_front='https://example.com/p101b-front.png',
            design_link_back='https://example.com/p101b-back.png',
        )
        shipping = SimpleNamespace(
            name='P101b-FIX Mirror Shipping',
            address1='123 Mirror St',
            address2='',
            city='Mirrorville',
            state='CA',
            zipcode='90210',
            country='United States',
            country_code='US',
            phone='',
            email='mirror@example.com',
        )
        parse_result = SimpleNamespace(
            order_id='9999911111',
            shop='P101b Mirror Shop',
            date='2026-05-10',
            note_from_buyer='Mirror buyer note',
            note_from_buyer_name='',
            gift_message='Mirror gift message',
            shipping_service='USPS Priority Mirror',
            processing_time='1-3 business days',
            discount_code='MIRROR10',
            shipping_cost=4.99,
            subtotal=29.99,
            shipping_address=shipping,
            transactions=[txn],
            currency='USD',
        )

        creator = OrderCreator(self.env)

        # Act
        order = creator.process_parse_result(parse_result, email_log_id=False)

        # Assert order-level shadows
        self.assertIsNotNone(order, 'process_parse_result should create the order')
        self.assertEqual(order.gift_message, 'Mirror gift message')
        self.assertEqual(order.processing_time, '1-3 business days')
        self.assertEqual(order.discount_code, 'MIRROR10')
        self.assertEqual(order.shipping_service_label, 'USPS Priority Mirror')
        # shipping_cost on sale.order is Char (P1-01b T-01b-02 surprise).
        self.assertTrue(
            order.shipping_cost,
            'shipping_cost (Char) should be populated from parsed value',
        )
        # Heritage fields the prior slice already covered — sanity check no regression.
        self.assertEqual(order.sales_channel, 'etsy')
        self.assertEqual(order.channel_order_ref, '9999911111')

        # Assert line-level shadows. The first line is the product line; the
        # shipping line (if any) follows. Filter to the product line.
        product_line = order.order_line.filtered(
            lambda l: l.product_id == self._mirror_product(order))
        self.assertTrue(product_line, 'Expected a product line on the new order')
        line = product_line[:1]
        self.assertEqual(line.transaction_id, '9999900001')
        self.assertEqual(line.personalisation, 'Happy Birthday')
        self.assertEqual(line.image_url, 'https://example.com/p101b.jpg')
        self.assertEqual(line.design_link_front, 'https://example.com/p101b-front.png')
        self.assertEqual(line.design_link_back, 'https://example.com/p101b-back.png')
        # Variant manual overrides should be populated for dashboard rendering.
        self.assertEqual(line.option_label_manual, 'Print Side: Front')
        self.assertEqual(line.color_manual, 'Red')
        self.assertEqual(line.size_manual, 'Medium')
        self.assertEqual(line.side_manual, 'Front')
        self.assertEqual(line.face_mask_size_manual, 'Adult')

    def _mirror_product(self, order):
        """Locate the product created by ``process_parse_result`` for the txn."""
        return order.order_line.mapped('product_id').filtered(
            lambda p: 'Mirror' in p.name)[:1]
