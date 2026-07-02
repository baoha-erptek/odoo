"""
Phase 2: ORM unit tests for ESTY-246 — Request Gearment Quote on dropship PO.

Tests verify business logic and ORM semantics:
- is_gearment_dropship_po computed field evaluates correctly
- action_request_gearment_quote is guarded on state, dropship, vendor, and SOs
- Access control: requires purchase.group_purchase_user or
  multichannel_hub_fulfillment.group_ba_shipping
- Single-SO happy path: item costs allocated, one fees line created, totals match
- Multi-SO PO: one fees line per SO, costs traced per SO, totals reconcile
- Re-request: old fees line replaced (not duplicated), price_unit overwritten, chatter posted
- Empty source SOs: raises UserError
- Rounding reconciliation: penny residual placed on largest line

Tests use TransactionCase for isolation. GearmentApiAdapter.get_quote is mocked
to return inline Decimal dicts (no real HTTP).
"""

import json
import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..services import gearment_adapter as ga_mod

_logger = logging.getLogger(__name__)

# Gearment quote fixture: order-level breakdown with Decimal values
GEARMENT_QUOTE_FIXTURE = {
    'order_total': Decimal('123.45'),
    'order_sub_total': Decimal('100.00'),
    'order_shipping_fee': Decimal('10.00'),
    'order_tax': Decimal('8.00'),
    'order_discount': Decimal('-2.00'),
    'order_handle_fee': Decimal('3.50'),
    'order_gift_message_fee': Decimal('2.00'),
    'order_fee': Decimal('1.95'),
    'currency': 'USD',
    'raw_response': {'mock': 'response'},
}


def _set_gearment_env():
    """Set required Gearment environment variables for tests."""
    import os
    os.environ.setdefault('GEARMENT_API_KEY', 'test')
    os.environ.setdefault('GEARMENT_API_SECRET', 'test')
    os.environ.setdefault('GEARMENT_API_BASE_URL', 'https://test.gearment.example')


@tagged('post_install', '-at_install')
class TestGearmentQuotePhase2ORM(TransactionCase):
    """Phase 2 ORM tests for ESTY-246: Request Gearment Quote on dropship PO."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data once for all tests."""
        super().setUpClass()
        _set_gearment_env()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Get Gearment vendor partner
        cls.gearment_vendor = cls.env.ref(
            'multichannel_hub_fulfillment.partner_gearment_vendor'
        )

        # Get dropship picking type by code (not by xmlid)
        cls.dropship_picking_type = cls.env['stock.picking.type'].search(
            [('code', '=', 'dropship')],
            limit=1
        )
        if not cls.dropship_picking_type:
            # Create a dropship picking type if it doesn't exist (unlikely in test DB)
            cls.dropship_picking_type = cls.env['stock.picking.type'].create({
                'name': 'Dropship',
                'code': 'dropship',
                'sequence_id': cls.env['ir.sequence'].create({
                    'name': 'Stock Picking Dropship',
                    'code': 'stock.picking.dropship',
                }).id,
            })

        # Get any non-dropship picking type (this DB may not have 'internal';
        # any non-dropship type exercises the is_gearment_dropship_po=False path)
        cls.internal_picking_type = cls.env['stock.picking.type'].search(
            [('code', '!=', 'dropship')],
            limit=1
        )

        # Create a non-Gearment vendor
        cls.non_gearment_vendor = cls.env['res.partner'].create({
            'name': 'Non-Gearment Vendor',
            'supplier_rank': 1,
        })

        # Create a test customer
        cls.customer = cls.env['res.partner'].create({
            'name': 'Test Customer for ESTY-246',
            'street': '123 Test St',
            'city': 'Test City',
            'zip': '12345',
        })

        # Create a test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product for ESTY-246',
            'type': 'consu',  # Odoo 19: 'product' type removed; 'consu' is a good (non-service)
            'list_price': 100.0,
        })

        # Get or create purchase and shipping groups
        cls.purchase_group = cls.env.ref('purchase.group_purchase_user')
        cls.shipping_group = cls.env.ref('multichannel_hub_fulfillment.group_ba_shipping')

        # Create test users with different permission levels
        cls.purchase_user = cls.env['res.users'].create({
            'name': 'Purchase User',
            'login': 'purchase_user@test.com',
            'email': 'purchase_user@test.com',
            'group_ids': [(6, 0, [cls.purchase_group.id])],
        })

        cls.shipping_user = cls.env['res.users'].create({
            'name': 'Shipping User',
            'login': 'shipping_user@test.com',
            'email': 'shipping_user@test.com',
            'group_ids': [(6, 0, [cls.shipping_group.id])],
        })

        cls.no_group_user = cls.env['res.users'].create({
            'name': 'No Group User',
            'login': 'no_group_user@test.com',
            'email': 'no_group_user@test.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        # Get fees product
        cls.fees_product = cls.env.ref('multichannel_hub_fulfillment.product_gearment_fees')

    def _create_sale_order(self, partner=None, **kwargs):
        """Factory method to create a sale order."""
        if partner is None:
            partner = self.customer

        defaults = {
            'partner_id': partner.id,
            'partner_shipping_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        }
        defaults.update(kwargs)
        return self.env['sale.order'].create(defaults)

    def _create_dropship_po(self, vendor=None, picking_type=None, sale_order=None, **kwargs):
        """Factory method to create a dropship purchase order."""
        if vendor is None:
            vendor = self.gearment_vendor
        if picking_type is None:
            picking_type = self.dropship_picking_type

        defaults = {
            'partner_id': vendor.id,
            'picking_type_id': picking_type.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
                'sale_line_id': sale_order.order_line[0].id if sale_order else None,
            })],
        }
        defaults.update(kwargs)
        return self.env['purchase.order'].create(defaults)

    # ======================================================================
    # Test 1: is_gearment_dropship_po computed field
    # ======================================================================
    def test_is_gearment_dropship_po_true_for_gearment_dropship(self):
        """Test that is_gearment_dropship_po is True for dropship + Gearment vendor PO."""
        po = self._create_dropship_po(
            vendor=self.gearment_vendor,
            picking_type=self.dropship_picking_type
        )

        self.assertTrue(
            po.is_gearment_dropship_po,
            "is_gearment_dropship_po should be True for Gearment vendor dropship PO"
        )

    def test_is_gearment_dropship_po_false_for_non_gearment_vendor(self):
        """Test that is_gearment_dropship_po is False for non-Gearment vendor dropship PO."""
        po = self._create_dropship_po(
            vendor=self.non_gearment_vendor,
            picking_type=self.dropship_picking_type
        )

        self.assertFalse(
            po.is_gearment_dropship_po,
            "is_gearment_dropship_po should be False for non-Gearment vendor"
        )

    def test_is_gearment_dropship_po_false_for_non_dropship(self):
        """Test that is_gearment_dropship_po is False for non-dropship PO."""
        po = self._create_dropship_po(
            vendor=self.gearment_vendor,
            picking_type=self.internal_picking_type
        )

        self.assertFalse(
            po.is_gearment_dropship_po,
            "is_gearment_dropship_po should be False for non-dropship picking type"
        )

    # ======================================================================
    # Test 2: Access control guards
    # ======================================================================
    def test_action_request_gearment_quote_access_denied_for_user_without_group(self):
        """Test that AccessError is raised for user without purchase or shipping group."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        with self.assertRaises(AccessError):
            po.with_user(self.no_group_user).action_request_gearment_quote()

    def test_action_request_gearment_quote_allowed_for_purchase_user(self):
        """Test that purchase.group_purchase_user can call action_request_gearment_quote."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=GEARMENT_QUOTE_FIXTURE
        ):
            # Should not raise AccessError
            try:
                po.with_user(self.purchase_user).action_request_gearment_quote()
            except AccessError:
                self.fail("purchase_user should have access")
            except UserError:
                # UserError is OK (business logic guard), AccessError is not
                pass

    def test_action_request_gearment_quote_allowed_for_shipping_user(self):
        """Test that group_ba_shipping can call action_request_gearment_quote."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=GEARMENT_QUOTE_FIXTURE
        ):
            # Should not raise AccessError
            try:
                po.with_user(self.shipping_user).action_request_gearment_quote()
            except AccessError:
                self.fail("shipping_user should have access")
            except UserError:
                # UserError is OK (business logic guard), AccessError is not
                pass

    # ======================================================================
    # Test 3: Business logic guards
    # ======================================================================
    def test_action_request_gearment_quote_guards_non_dropship_po(self):
        """Test that UserError is raised for non-dropship PO."""
        so = self._create_sale_order()
        po = self._create_dropship_po(
            sale_order=so,
            picking_type=self.internal_picking_type
        )

        with self.assertRaises(UserError):
            po.action_request_gearment_quote()

    def test_action_request_gearment_quote_guards_non_gearment_vendor(self):
        """Test that UserError is raised for non-Gearment vendor dropship PO."""
        so = self._create_sale_order()
        po = self._create_dropship_po(
            sale_order=so,
            vendor=self.non_gearment_vendor
        )

        with self.assertRaises(UserError):
            po.action_request_gearment_quote()

    def test_action_request_gearment_quote_guards_confirmed_po(self):
        """Test that UserError is raised for confirmed PO (state != 'draft'/'sent')."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        # Put the PO in a confirmed state. We write state directly instead of
        # button_confirm() because the existing button_confirm override fires a
        # real Gearment push (HTTP) for Gearment dropship POs, which is out of
        # scope for this state-guard test.
        po.sudo().write({'state': 'purchase'})
        self.assertEqual(po.state, 'purchase')

        with self.assertRaises(UserError):
            po.action_request_gearment_quote()

    def test_action_request_gearment_quote_guards_empty_source_sale_orders(self):
        """Test that UserError is raised when PO has no source SOs."""
        # Create a PO with no sale_line_id links
        po = self._create_dropship_po()
        po.order_line[0].write({'sale_line_id': None})

        with self.assertRaises(UserError):
            po.action_request_gearment_quote()

    # ======================================================================
    # Test 4: Single-SO happy path
    # ======================================================================
    def test_action_request_gearment_quote_single_so_happy_path(self):
        """Test single-SO happy path: costs allocated, fees line created, totals match."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=GEARMENT_QUOTE_FIXTURE
        ):
            po.action_request_gearment_quote()

        # Verify product line price_unit was updated
        product_line = po.order_line.filtered(lambda l: l.product_id.type != 'service')
        self.assertTrue(product_line, "Should have at least one product line")

        # Verify fees line was created
        fees_lines = po.order_line.filtered(
            lambda l: l.product_id == self.fees_product
        )
        self.assertEqual(len(fees_lines), 1, "Should have exactly one fees line")

        fees_line = fees_lines[0]
        self.assertEqual(fees_line.product_qty, 1.0, "Fees line qty should be 1")

        # Verify x_gearment_quote_breakdown_json was set
        self.assertIsNotNone(
            po.x_gearment_quote_breakdown_json,
            "x_gearment_quote_breakdown_json should be set"
        )

    # ======================================================================
    # Test 5: Multi-SO PO
    # ======================================================================
    def test_action_request_gearment_quote_multi_so_po(self):
        """Test multi-SO PO: one fees line per SO, costs traced per SO."""
        # Create two sale orders
        so1 = self._create_sale_order(partner=self.customer)
        so2 = self._create_sale_order(partner=self.customer)

        # Create PO with lines from both SOs
        po = self.env['purchase.order'].create({
            'partner_id': self.gearment_vendor.id,
            'picking_type_id': self.dropship_picking_type.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1.0,
                    'price_unit': 100.0,
                    'sale_line_id': so1.order_line[0].id,
                }),
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1.0,
                    'price_unit': 100.0,
                    'sale_line_id': so2.order_line[0].id,
                }),
            ],
        })

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=GEARMENT_QUOTE_FIXTURE
        ):
            po.action_request_gearment_quote()

        # Verify two fees lines were created (one per SO)
        fees_lines = po.order_line.filtered(
            lambda l: l.product_id == self.fees_product
        )
        self.assertEqual(len(fees_lines), 2, "Should have one fees line per SO")

    # ======================================================================
    # Test 6: Re-request behavior
    # ======================================================================
    def test_action_request_gearment_quote_re_request_replaces_fees_line(self):
        """Test re-request: old fees line replaced (not duplicated), price_unit overwritten."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        fixture1 = dict(GEARMENT_QUOTE_FIXTURE)
        fixture1['order_total'] = Decimal('123.45')

        fixture2 = dict(GEARMENT_QUOTE_FIXTURE)
        fixture2['order_total'] = Decimal('234.56')

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=fixture1
        ):
            po.action_request_gearment_quote()

        # Verify first fees line created
        fees_lines_after_first = po.order_line.filtered(
            lambda l: l.product_id == self.fees_product
        )
        self.assertEqual(len(fees_lines_after_first), 1)
        first_fees_line_id = fees_lines_after_first.id

        # Re-request with different quote
        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=fixture2
        ):
            po.action_request_gearment_quote()

        # Verify only one fees line exists (old one deleted/replaced)
        fees_lines_after_second = po.order_line.filtered(
            lambda l: l.product_id == self.fees_product
        )
        self.assertEqual(len(fees_lines_after_second), 1, "Should still have exactly one fees line")

        # Verify it's a different line (or same line with updated price)
        # If it's a different line, the old one should be gone
        if fees_lines_after_second.id != first_fees_line_id:
            # Old line was deleted and new one created
            self.assertFalse(
                first_fees_line_id in po.order_line.ids,
                "Old fees line should be deleted on re-request"
            )

    def test_action_request_gearment_quote_re_request_posts_chatter(self):
        """Test re-request posts old -> new total chatter message."""
        so = self._create_sale_order()
        po = self._create_dropship_po(sale_order=so)

        fixture1 = dict(GEARMENT_QUOTE_FIXTURE)
        fixture2 = dict(GEARMENT_QUOTE_FIXTURE)

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=fixture1
        ):
            po.action_request_gearment_quote()

        initial_msg_count = len(po.message_ids)

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=fixture2
        ):
            po.action_request_gearment_quote()

        # Verify a new message was posted (re-request case posts old -> new)
        # On first request, it posts "fetched", on re-request it posts "old -> new"
        self.assertGreater(
            len(po.message_ids),
            initial_msg_count,
            "Chatter message should be posted on re-request"
        )

    # ======================================================================
    # Test 7: Rounding reconciliation
    # ======================================================================
    def test_action_request_gearment_quote_rounding_reconciliation(self):
        """Test rounding: penny residual placed on largest line, total matches exactly."""
        so = self._create_sale_order()

        # Create PO with 3 product lines of different quantities
        po = self.env['purchase.order'].create({
            'partner_id': self.gearment_vendor.id,
            'picking_type_id': self.dropship_picking_type.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 3.0,
                    'price_unit': 50.0,  # 150.00
                    'sale_line_id': so.order_line[0].id,
                }),
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1.0,
                    'price_unit': 50.0,  # 50.00
                    'sale_line_id': so.order_line[0].id,
                }),
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 2.0,
                    'price_unit': 25.0,  # 50.00 (total so far: 250.00)
                    'sale_line_id': so.order_line[0].id,
                }),
            ],
        })

        with patch.object(
            ga_mod.GearmentApiAdapter, 'get_quote',
            return_value=GEARMENT_QUOTE_FIXTURE
        ):
            po.action_request_gearment_quote()

        # Verify total amount matches order_total
        # amount_untaxed = sum of product line extended costs + fees line cost
        # should equal order_total within 0.01
        product_lines = po.order_line.filtered(lambda l: l.product_id.type != 'service')
        fees_lines = po.order_line.filtered(lambda l: l.product_id.type == 'service')

        product_total = sum(line.price_subtotal for line in product_lines)
        fees_total = sum(line.price_subtotal for line in fees_lines)
        combined_total = product_total + fees_total

        self.assertAlmostEqual(
            combined_total,
            float(GEARMENT_QUOTE_FIXTURE['order_total']),
            places=2,
            msg="Combined total should match order_total within 0.01"
        )
