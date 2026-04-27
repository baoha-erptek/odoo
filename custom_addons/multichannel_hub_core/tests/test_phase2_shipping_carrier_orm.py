"""
Phase 2: ORM unit tests for shipping.carrier model.

Tests verify the business logic and data integrity:
- shipping.carrier can be created with required fields
- Required fields (name, code) enforce presence
- Code uniqueness constraint prevents duplicates
- Selection fields (etsy_carrier_name) enforce valid values
- Seed carriers are accessible via env.ref() with correct values
- Fulfillment can link to a shipping carrier
- Deleting a carrier sets the FK to null (set null ondelete)
- Access control prevents non-managers from unlinking carriers

Tests use TransactionCase to isolate each test in a savepoint.
Tests are tagged post_install so the full ORM registry is loaded.
"""

from odoo.exceptions import ValidationError, AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase2ShippingCarrierORM(TransactionCase):
    """ORM and business logic tests for shipping.carrier."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data once for all tests."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'customer@test.com',
        })

        cls.salesman_group = cls.env.ref('sales_team.group_sale_salesman')
        cls.manager_group = cls.env.ref('sales_team.group_sale_manager')

    def _create_carrier(self, **kwargs):
        """Factory method to create a shipping.carrier with default test data."""
        defaults = {
            'name': 'Test Carrier',
            'code': 'test_carrier',
            'sequence': 10,
        }
        defaults.update(kwargs)
        return self.env['shipping.carrier'].create(defaults)

    def _create_order(self, **kwargs):
        """Factory method to create a sale.order with default test data."""
        defaults = {
            'partner_id': self.partner.id,
            'order_line': [],
        }
        defaults.update(kwargs)
        return self.env['sale.order'].create(defaults)

    def test_create_carrier_basic(self):
        """Test that carrier is created with correct defaults."""
        # NOTE: must use a code that is NOT in the seed (usps/uniuni/yunexpress/
        # 4px/dhl_ecommerce/fedex_smartpost/gke_local) to avoid colliding with
        # the unique-code constraint when the seed XML loads the standard 7.
        carrier = self._create_carrier(name='Aramex', code='aramex_test')

        self.assertTrue(carrier.id, "Carrier should be created with an ID")
        self.assertEqual(carrier.name, 'Aramex')
        self.assertEqual(carrier.code, 'aramex_test')
        self.assertTrue(carrier.is_active, "is_active should default to True")
        self.assertEqual(carrier.sequence, 10, "sequence should default to 10")

    def test_create_carrier_required_name(self):
        """Test that creating without name raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_carrier(name='')

    def test_create_carrier_required_code(self):
        """Test that creating without code raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_carrier(code='')

    def test_code_unique_constraint(self):
        """Test that duplicate code values raise ValidationError."""
        self._create_carrier(name='First Carrier', code='dup')

        with self.assertRaises(ValidationError):
            self._create_carrier(name='Second Carrier', code='dup')

    def test_etsy_carrier_name_selection_usps(self):
        """Test etsy_carrier_name selection accepts 'usps'."""
        carrier = self._create_carrier(etsy_carrier_name='usps')
        self.assertEqual(carrier.etsy_carrier_name, 'usps')

    def test_etsy_carrier_name_selection_ups(self):
        """Test etsy_carrier_name selection accepts 'ups'."""
        carrier = self._create_carrier(etsy_carrier_name='ups')
        self.assertEqual(carrier.etsy_carrier_name, 'ups')

    def test_etsy_carrier_name_selection_fedex(self):
        """Test etsy_carrier_name selection accepts 'fedex'."""
        carrier = self._create_carrier(etsy_carrier_name='fedex')
        self.assertEqual(carrier.etsy_carrier_name, 'fedex')

    def test_etsy_carrier_name_selection_dhl(self):
        """Test etsy_carrier_name selection accepts 'dhl'."""
        carrier = self._create_carrier(etsy_carrier_name='dhl')
        self.assertEqual(carrier.etsy_carrier_name, 'dhl')

    def test_etsy_carrier_name_selection_4px(self):
        """Test etsy_carrier_name selection accepts '4px'."""
        carrier = self._create_carrier(etsy_carrier_name='4px')
        self.assertEqual(carrier.etsy_carrier_name, '4px')

    def test_etsy_carrier_name_selection_other(self):
        """Test etsy_carrier_name selection accepts 'other'."""
        carrier = self._create_carrier(etsy_carrier_name='other')
        self.assertEqual(carrier.etsy_carrier_name, 'other')

    def test_etsy_carrier_name_invalid_value_raises(self):
        """Test that invalid etsy_carrier_name value raises ValueError."""
        with self.assertRaises(ValueError):
            self._create_carrier(etsy_carrier_name='amazon')

    def test_seed_usps_present(self):
        """Test that seed USPS carrier is accessible via env.ref()."""
        usps = self.env.ref('multichannel_hub_core.shipping_carrier_usps')
        self.assertEqual(usps.code, 'usps')
        self.assertEqual(usps.etsy_carrier_name, 'usps')

    def test_seed_uniuni_falls_back_to_other(self):
        """Test that seed UniUni carrier has etsy_carrier_name = 'other'."""
        uniuni = self.env.ref('multichannel_hub_core.shipping_carrier_uniuni')
        self.assertEqual(uniuni.etsy_carrier_name, 'other')

    def test_assign_carrier_to_fulfillment(self):
        """Test that carrier can be assigned to a fulfillment and read back."""
        usps = self.env.ref('multichannel_hub_core.shipping_carrier_usps')
        order = self._create_order()
        fulfillment = order.fulfillment_id

        fulfillment.write({'shipping_carrier_id': usps.id})

        self.assertEqual(
            fulfillment.shipping_carrier_id.id,
            usps.id,
            "Carrier should be assigned to fulfillment"
        )

    def test_set_null_when_carrier_unlinked(self):
        """Test that fulfillment.shipping_carrier_id becomes null when carrier is unlinked.

        Uses admin user to bypass any ACL restrictions on carrier unlink.
        """
        usps = self.env.ref('multichannel_hub_core.shipping_carrier_usps')
        order = self._create_order()
        fulfillment = order.fulfillment_id
        fulfillment.write({'shipping_carrier_id': usps.id})

        self.assertEqual(fulfillment.shipping_carrier_id.id, usps.id)

        admin = self.env.ref('base.user_admin')
        usps.with_user(admin).unlink()

        fulfillment.invalidate_recordset(['shipping_carrier_id'])
        self.assertFalse(
            fulfillment.shipping_carrier_id,
            "shipping_carrier_id should be set to null when carrier is unlinked"
        )

    def test_carrier_unlink_blocked_for_salesman(self):
        """Test that sales_team.group_sale_salesman user cannot unlink carriers.

        Only managers with ir.model.access perm_unlink can unlink carriers.
        """
        salesman = self.env['res.users'].create({
            'name': 'Test Salesman',
            'login': f'salesman_{self.env.cr.dbname}@test.com',
            'group_ids': [(6, 0, [self.salesman_group.id])],
        })

        carrier = self._create_carrier(name='Unlink Test', code='unlink_test')

        with self.assertRaises(AccessError):
            carrier.with_user(salesman).unlink()
