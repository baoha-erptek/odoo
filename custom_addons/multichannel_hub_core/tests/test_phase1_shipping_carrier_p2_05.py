"""
Phase 1: Static-asset verification for P2-05 shipping.carrier admin UX.

Tests verify that the underlying XML seed data and ACL CSV are correctly
configured for the extended-seed and system-only-edit requirements:
- Seed XML has noupdate="1" (admin edits persist across upgrades)
- ACL CSV has system-group row for full access
- ACL CSV has manager-group row downgraded to read-only

Tests use direct file I/O and CSV parsing to verify the source files
independent of ORM loading.
"""

import csv
import os
from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase1ShippingCarrierP2_05(TransactionCase):
    """Static-asset verification for P2-05 shipping.carrier UX requirements."""

    def _get_module_path(self):
        """Return absolute path to the multichannel_hub_core module directory."""
        # tests/test_phase1_shipping_carrier_p2_05.py -> tests/ -> module/
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_seed_xml_is_noupdate_one(self):
        """Verify shipping_carrier_data.xml has noupdate="1" (line 2)."""
        module_path = self._get_module_path()
        xml_file = os.path.join(
            module_path,
            'data',
            'shipping_carrier_data.xml'
        )

        self.assertTrue(
            os.path.exists(xml_file),
            f"shipping_carrier_data.xml must exist at {xml_file}"
        )

        # Parse XML to check the root element's noupdate attribute
        with open(xml_file, 'r', encoding='utf-8') as f:
            tree = etree.parse(f)
            root = tree.getroot()

        noupdate = root.get('noupdate')
        self.assertEqual(
            noupdate,
            '1',
            f"Root <odoo> element must have noupdate='1', got {noupdate!r}"
        )

    def test_acl_csv_has_system_row_for_shipping_carrier(self):
        """Verify ACL CSV has system-group full-access row for shipping.carrier."""
        module_path = self._get_module_path()
        acl_file = os.path.join(
            module_path,
            'security',
            'ir.model.access.csv'
        )

        self.assertTrue(
            os.path.exists(acl_file),
            f"ir.model.access.csv must exist at {acl_file}"
        )

        with open(acl_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find the system-group row for shipping.carrier
        system_row = None
        for row in rows:
            if (row.get('model_id:id') == 'model_shipping_carrier'
                    and row.get('group_id:id') == 'base.group_system'):
                system_row = row
                break

        self.assertIsNotNone(
            system_row,
            "ACL CSV must have a row for model_shipping_carrier + base.group_system"
        )

        # Verify full access (1,1,1,1)
        self.assertEqual(
            system_row.get('perm_read'),
            '1',
            "System group must have perm_read=1"
        )
        self.assertEqual(
            system_row.get('perm_write'),
            '1',
            "System group must have perm_write=1"
        )
        self.assertEqual(
            system_row.get('perm_create'),
            '1',
            "System group must have perm_create=1"
        )
        self.assertEqual(
            system_row.get('perm_unlink'),
            '1',
            "System group must have perm_unlink=1"
        )

    def test_acl_csv_manager_row_is_read_only(self):
        """Verify manager row for shipping.carrier is downgraded to read-only."""
        module_path = self._get_module_path()
        acl_file = os.path.join(
            module_path,
            'security',
            'ir.model.access.csv'
        )

        with open(acl_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find the manager row for shipping.carrier
        manager_row = None
        for row in rows:
            if (row.get('model_id:id') == 'model_shipping_carrier'
                    and row.get('group_id:id') == 'sales_team.group_sale_manager'):
                manager_row = row
                break

        self.assertIsNotNone(
            manager_row,
            "ACL CSV must have a row for shipping.carrier + sales_team.group_sale_manager"
        )

        # Verify read-only (1,0,0,0)
        self.assertEqual(
            manager_row.get('perm_read'),
            '1',
            "Manager must have perm_read=1"
        )
        self.assertEqual(
            manager_row.get('perm_write'),
            '0',
            "Manager must have perm_write=0 (read-only)"
        )
        self.assertEqual(
            manager_row.get('perm_create'),
            '0',
            "Manager must have perm_create=0 (read-only)"
        )
        self.assertEqual(
            manager_row.get('perm_unlink'),
            '0',
            "Manager must have perm_unlink=0 (read-only)"
        )
