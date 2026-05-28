"""
Phase 2: ORM unit tests for P2-05 shipping.carrier admin UX + system-only writes.

Tests verify the business logic and access control:
- At-least-one mapping constraint (regex OR etsy_name)
- System-only write/create/unlink gates
- Sales manager can read but not modify
- Admin user can full CRUD
- Constraint ordering (at-least-one runs; empty regex skipped early)
- Inactive carriers still render on existing references

Tests use TransactionCase for test isolation. Uses a non-admin sales-manager
user to test access control enforcement.
"""

from odoo.exceptions import ValidationError, AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase2ShippingCarrierP2_05ORM(TransactionCase):
    """ORM and access-control tests for P2-05 shipping.carrier admin UX."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data once for all tests."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a sales manager user (no group_system)
        sales_manager_group = cls.env.ref('sales_team.group_sale_manager')
        cls.sales_mgr_user = cls.env['res.users'].create({
            'name': 'P2-05 Sales Manager (no system)',
            'login': 'p2_05_sales_mgr',
            'email': 'p2_05_sales_mgr@example.com',
            'group_ids': [(6, 0, [sales_manager_group.id])],  # Odoo 19 rename
        })

    def _create_carrier(self, **kwargs):
        """Factory method to create a shipping.carrier with default test data."""
        defaults = {
            'name': 'Test Carrier',
            'code': 'test_carrier_' + str(hash(frozenset(kwargs.items())))[-6:],
            'sequence': 10,
            'tracking_prefix_regex': '^TEST[0-9]+$',
        }
        defaults.update(kwargs)
        return self.env['shipping.carrier'].create(defaults)

    def test_create_requires_at_least_regex_or_etsy(self):
        """Test: create with both regex and etsy_name empty raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self.env['shipping.carrier'].create({
                'name': 'Bad Carrier',
                'code': 'bad_carrier_001',
                'tracking_prefix_regex': False,  # Empty
                'etsy_carrier_name': False,  # Empty
            })

        self.assertIn('at least one', str(cm.exception).lower())

    def test_create_accepts_regex_only(self):
        """Test: create with regex only (no etsy_name) succeeds."""
        carrier = self._create_carrier(
            name='USPS',
            code='usps_only',
            tracking_prefix_regex='^9[0-9]{15,21}$',
            etsy_carrier_name=False,  # Empty
        )

        self.assertEqual(carrier.name, 'USPS')
        self.assertEqual(carrier.code, 'usps_only')
        self.assertTrue(carrier.tracking_prefix_regex)

    def test_create_accepts_etsy_only(self):
        """Test: create with etsy_name only (no regex) succeeds."""
        carrier = self._create_carrier(
            name='Custom Etsy',
            code='custom_etsy',
            tracking_prefix_regex=False,  # Empty
            etsy_carrier_name='other',
        )

        self.assertEqual(carrier.name, 'Custom Etsy')
        self.assertEqual(carrier.code, 'custom_etsy')
        self.assertFalse(carrier.tracking_prefix_regex)
        self.assertEqual(carrier.etsy_carrier_name, 'other')

    def test_write_to_clear_both_mappings_raises(self):
        """Test: write to clear both regex and etsy_name raises ValidationError."""
        carrier = self._create_carrier(
            name='Existing',
            code='existing_001',
            tracking_prefix_regex='^EX[0-9]+$',
            etsy_carrier_name='other',
        )

        with self.assertRaises(ValidationError) as cm:
            carrier.write({
                'tracking_prefix_regex': False,
                'etsy_carrier_name': False,
            })

        self.assertIn('at least one', str(cm.exception).lower())

    def test_create_blocked_for_non_system_user(self):
        """Test: sales-manager user cannot create carrier (AccessError)."""
        with self.cr.savepoint():
            with self.assertRaises(AccessError):
                self.env['shipping.carrier'].with_user(
                    self.sales_mgr_user
                ).create({
                    'name': 'Unauthorized',
                    'code': 'unauthorized_001',
                    'tracking_prefix_regex': '^UN[0-9]+$',
                })

    def test_write_blocked_for_non_system_user(self):
        """Test: sales-manager user cannot write to carrier (AccessError)."""
        carrier = self._create_carrier(
            name='Original Name',
            code='readonly_test',
        )

        with self.cr.savepoint():
            with self.assertRaises(AccessError):
                carrier.with_user(self.sales_mgr_user).write({
                    'name': 'Modified Name',
                })

    def test_unlink_blocked_for_non_system_user(self):
        """Test: sales-manager user cannot unlink carrier (AccessError)."""
        carrier = self._create_carrier(
            name='Deletable',
            code='delete_test',
        )

        with self.cr.savepoint():
            with self.assertRaises(AccessError):
                carrier.with_user(self.sales_mgr_user).unlink()

    def test_create_succeeds_for_system_user(self):
        """Test: admin user (group_system) can create carriers."""
        # Admin is group_system in test env by default
        carrier = self._create_carrier(
            name='Admin Created',
            code='admin_created_001',
            tracking_prefix_regex='^ADMIN[0-9]+$',
        )

        self.assertTrue(carrier.id)
        self.assertEqual(carrier.name, 'Admin Created')

    def test_write_succeeds_for_system_user(self):
        """Test: admin user (group_system) can modify existing carriers."""
        carrier = self._create_carrier(
            name='Original',
            code='writable_test',
        )

        # Admin can write
        carrier.write({'name': 'Modified'})

        self.assertEqual(carrier.name, 'Modified')

    def test_at_least_one_constraint_runs_after_regex_safe(self):
        """Test: empty regex + no etsy_name surfaces AS1 error (not regex-safe).

        Establishes constraint-ordering contract: _check_at_least_one_mapping
        must run and fail BEFORE or in parallel with _check_tracking_prefix_regex_safe.
        An empty regex is treated as "not provided" by AS1, so the at-least-one
        constraint should surface first.
        """
        with self.assertRaises(ValidationError) as cm:
            self.env['shipping.carrier'].create({
                'name': 'No Mapping',
                'code': 'no_mapping_001',
                'tracking_prefix_regex': '',  # Empty string (not False/None)
                'etsy_carrier_name': False,
            })

        # Should mention "at least one" requirement, not regex safety
        error_text = str(cm.exception).lower()
        self.assertIn('at least one', error_text)
