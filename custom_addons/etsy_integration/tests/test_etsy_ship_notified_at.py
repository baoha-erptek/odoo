"""
Phase 2: Cross-Module Test for etsy_ship_notified_at Field.

Tests verify P1-03 T038: etsy_ship_notified_at field added to sale.order.fulfillment
via etsy_integration _inherit extension (not in multichannel_hub_core, per Etsy-name prohibition).

This field is stamped by Spec 005 EtsyTrackingPusher when Etsy notification received.
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestEtsyShipNotifiedAt(TransactionCase):
    """Phase 2 ORM: Test etsy_ship_notified_at field on fulfillment."""

    @classmethod
    def setUpClass(cls):
        """Set up test data: partner, product, order, fulfillment."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
            'is_company': False,
            'is_etsy_customer': True,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'is_storable': True,
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        cls.order.action_confirm()

        cls.carrier = cls.env.ref('multichannel_hub_core.shipping_carrier_usps')

        cls.fulfillment = cls.env['sale.order.fulfillment'].create({
            'order_id': cls.order.id,
            'tracking_number': '9400111899223456789001',
            'shipping_carrier_id': cls.carrier.id,
            'label_status': 'bought',
            'tracking_state': 'shipped',
        })

    def test_etsy_ship_notified_at_field_exists_on_fulfillment_model(self):
        """Test T038: etsy_ship_notified_at field exists on sale.order.fulfillment."""
        fulfillment_fields = self.env['sale.order.fulfillment']._fields

        self.assertIn(
            'etsy_ship_notified_at',
            fulfillment_fields,
            "etsy_ship_notified_at field should exist on sale.order.fulfillment"
        )

        field = fulfillment_fields['etsy_ship_notified_at']
        self.assertEqual(
            field.type,
            'datetime',
            "etsy_ship_notified_at should be a Datetime field"
        )

    def test_etsy_ship_notified_at_writable_via_inherit(self):
        """Test T038: etsy_ship_notified_at can be written via inherited model."""
        from odoo import fields as odoo_fields

        # Write the field
        test_datetime = odoo_fields.Datetime.now()
        self.fulfillment.write({'etsy_ship_notified_at': test_datetime})

        # Verify: field is written and readable
        self.fulfillment.refresh()
        self.assertIsNotNone(self.fulfillment.etsy_ship_notified_at)
        self.assertEqual(
            self.fulfillment.etsy_ship_notified_at,
            test_datetime,
            "etsy_ship_notified_at should be writable and readable"
        )

    def test_etsy_ship_notified_at_column_in_db(self):
        """Test T038: etsy_ship_notified_at column exists in database."""
        self.env.cr.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sale_order_fulfillment'
            AND column_name = 'etsy_ship_notified_at'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "etsy_ship_notified_at column should exist in database")
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'etsy_ship_notified_at')
        self.assertEqual(
            data_type,
            'timestamp without time zone',
            "etsy_ship_notified_at should be timestamp type"
        )
        self.assertEqual(is_nullable, 'YES', "etsy_ship_notified_at should be nullable")

    def test_etsy_ship_notified_at_null_by_default(self):
        """Test T038: etsy_ship_notified_at is NULL by default."""
        new_fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': self.order.id,
            'tracking_number': '9400111899223456789002',
            'shipping_carrier_id': self.carrier.id,
            'label_status': 'none',
            'tracking_state': 'none',
        })

        self.assertIsNone(
            new_fulfillment.etsy_ship_notified_at,
            "etsy_ship_notified_at should be NULL by default"
        )

    def test_etsy_ship_notified_at_preserved_on_fulfillment_update(self):
        """Test T038: etsy_ship_notified_at persists across other field updates."""
        from odoo import fields as odoo_fields

        # Set the field
        test_datetime = odoo_fields.Datetime.now()
        self.fulfillment.write({'etsy_ship_notified_at': test_datetime})
        self.fulfillment.refresh()

        # Update another field
        self.fulfillment.write({'tracking_state': 'delivered'})

        # Verify: etsy_ship_notified_at is preserved
        self.fulfillment.refresh()
        self.assertEqual(
            self.fulfillment.etsy_ship_notified_at,
            test_datetime,
            "etsy_ship_notified_at should be preserved when updating other fields"
        )
