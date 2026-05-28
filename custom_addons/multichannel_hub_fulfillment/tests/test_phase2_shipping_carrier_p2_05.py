"""
Phase 2: ORM tests for P2-05 shipping.carrier detector interaction.

Tests verify that the carrier detector correctly skips inactive carriers
and that inactive carrier references still render on fulfillment records.

These tests live in multichannel_hub_fulfillment (not mhc) because they
depend on the carrier_detector service and fulfillment models.
"""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services.carrier_detector import detect_carrier


@tagged('post_install', '-at_install')
class TestPhase2ShippingCarrierP2_05Detector(TransactionCase):
    """Detector and inactive carrier tests for P2-05 shipping.carrier."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a test partner for fulfillments
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
        })

        # Create a test sale order
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [],
        })

    def _create_carrier(self, **kwargs):
        """Factory method for creating test carriers."""
        defaults = {
            'name': 'Test Carrier',
            'code': 'test_' + str(hash(frozenset(kwargs.items())))[-6:],
            'sequence': 10,
            'tracking_prefix_regex': '^TEST[0-9]+$',
        }
        defaults.update(kwargs)
        return self.env['shipping.carrier'].create(defaults)

    def test_inactive_carrier_skipped_by_detector(self):
        """Test: detector skips inactive carriers (T2-05-13).

        Create a carrier with prefix ^ZZZ and is_active=False.
        Call detect_carrier(env, 'ZZZ123456').
        Expect: returns fallback 'other' carrier, not the inactive row.
        """
        # Create an inactive carrier with a specific prefix
        inactive = self._create_carrier(
            name='Inactive Special',
            code='inactive_special',
            tracking_prefix_regex='^ZZZ[0-9]+$',
            is_active=False,
        )

        # Call detector on a tracking number that WOULD match the inactive carrier
        result, needs_review = detect_carrier(self.env, 'ZZZ123456')

        # Should return the 'other' fallback, not the inactive carrier
        self.assertEqual(
            result.code,
            'other',
            f"Detector must skip inactive carrier; expected code='other', got {result.code!r}"
        )
        self.assertTrue(
            needs_review,
            "Fallback to 'other' should set needs_review=True"
        )

    def test_inactive_carrier_name_still_renders(self):
        """Test: inactive carrier references still render names (T2-05-14).

        Create a fulfillment with shipping_carrier_id pointing to an active carrier.
        Flip the carrier to is_active=False.
        Re-read fulfillment.shipping_carrier_id.name.
        Expect: name still renders (no blanking on is_active=False).
        """
        # Create an active carrier
        carrier = self._create_carrier(
            name='Originally Active',
            code='originally_active',
            tracking_prefix_regex='^ORIG[0-9]+$',
            is_active=True,
        )

        # Create a fulfillment linked to this carrier
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': self.order.id,
            'shipping_carrier_id': carrier.id,
        })

        # Verify name renders before deactivation
        self.assertEqual(
            fulfillment.shipping_carrier_id.name,
            'Originally Active'
        )

        # Deactivate the carrier
        carrier.write({'is_active': False})

        # Re-read and verify name still renders (Odoo 19: invalidate_recordset, not invalidate_cache)
        fulfillment.invalidate_recordset()
        self.assertEqual(
            fulfillment.shipping_carrier_id.name,
            'Originally Active',
            "Inactive carrier reference should still render the name"
        )
