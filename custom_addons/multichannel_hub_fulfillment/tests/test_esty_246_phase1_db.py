"""
Phase 1: Database verification tests for ESTY-246 — Request Gearment Quote on dropship PO.

Tests verify at the database level:
- x_gearment_quote_breakdown_json column exists on purchase_order
- Methods action_request_gearment_quote, _check_purchase_or_shipping_or_raise,
  _allocate_gearment_costs_to_lines, _compute_is_gearment_dropship_po exist on
  purchase.order model
- Computed field is_gearment_dropship_po exists on purchase.order
- Service product multichannel_hub_fulfillment.product_gearment_fees can be resolved

Tests use direct SQL queries and env.ref() for database and seed verification.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGearmentQuotePhase1DB(TransactionCase):
    """Phase 1: Verify ESTY-246 database schema and seed data."""

    def test_purchase_order_gearment_quote_breakdown_json_column_exists(self):
        """Test that x_gearment_quote_breakdown_json column exists on purchase_order table."""
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'purchase_order'
            AND column_name = 'x_gearment_quote_breakdown_json'
            AND table_schema = 'public'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            "Column 'x_gearment_quote_breakdown_json' should exist on purchase_order table"
        )

    def test_purchase_order_is_gearment_dropship_po_field_exists(self):
        """Test that is_gearment_dropship_po computed Boolean field exists on purchase.order."""
        po_model = self.env['purchase.order']
        self.assertIn(
            'is_gearment_dropship_po',
            po_model._fields,
            "Field 'is_gearment_dropship_po' should exist on purchase.order model"
        )

        field = po_model._fields['is_gearment_dropship_po']
        self.assertEqual(
            field.type,
            'boolean',
            "Field 'is_gearment_dropship_po' should be a Boolean field"
        )

    def test_action_request_gearment_quote_method_exists(self):
        """Test that action_request_gearment_quote method exists on purchase.order."""
        po_model = self.env['purchase.order']
        self.assertTrue(
            hasattr(po_model, 'action_request_gearment_quote'),
            "Method 'action_request_gearment_quote' should exist on purchase.order"
        )

    def test_check_purchase_or_shipping_or_raise_method_exists(self):
        """Test that _check_purchase_or_shipping_or_raise method exists on purchase.order."""
        po_model = self.env['purchase.order']
        self.assertTrue(
            hasattr(po_model, '_check_purchase_or_shipping_or_raise'),
            "Method '_check_purchase_or_shipping_or_raise' should exist on purchase.order"
        )

    def test_allocate_gearment_costs_to_lines_method_exists(self):
        """Test that _allocate_gearment_costs_to_lines method exists on purchase.order."""
        po_model = self.env['purchase.order']
        self.assertTrue(
            hasattr(po_model, '_allocate_gearment_costs_to_lines'),
            "Method '_allocate_gearment_costs_to_lines' should exist on purchase.order"
        )

    def test_compute_is_gearment_dropship_po_method_exists(self):
        """Test that _compute_is_gearment_dropship_po method exists on purchase.order."""
        po_model = self.env['purchase.order']
        self.assertTrue(
            hasattr(po_model, '_compute_is_gearment_dropship_po'),
            "Method '_compute_is_gearment_dropship_po' should exist on purchase.order"
        )

    def test_product_gearment_fees_seed_exists(self):
        """Test that service product multichannel_hub_fulfillment.product_gearment_fees exists."""
        product = self.env.ref(
            'multichannel_hub_fulfillment.product_gearment_fees',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            product,
            "Service product 'multichannel_hub_fulfillment.product_gearment_fees' should exist"
        )

        if product:
            self.assertEqual(
                product.type,
                'service',
                "Product 'product_gearment_fees' should be a service type"
            )

    def test_gearment_vendor_partner_exists(self):
        """Test that Gearment vendor partner seed exists."""
        partner = self.env.ref(
            'multichannel_hub_fulfillment.partner_gearment_vendor',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            partner,
            "Partner 'multichannel_hub_fulfillment.partner_gearment_vendor' should exist"
        )

    def test_group_ba_shipping_exists(self):
        """Test that group_ba_shipping group exists."""
        group = self.env.ref(
            'multichannel_hub_fulfillment.group_ba_shipping',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            group,
            "Group 'multichannel_hub_fulfillment.group_ba_shipping' should exist"
        )

    def test_purchase_group_user_exists(self):
        """Test that purchase.group_purchase_user group exists."""
        group = self.env.ref(
            'purchase.group_purchase_user',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            group,
            "Group 'purchase.group_purchase_user' should exist"
        )
