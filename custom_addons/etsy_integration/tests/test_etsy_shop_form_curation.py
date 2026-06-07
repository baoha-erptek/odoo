"""Two-phase tests for etsy.shop form view curation (P-DS-3a).

PHASE 1 (Data Verification): Direct SQL verification of columns.
PHASE 2 (ORM Unit Tests): Verify form view XML groups attributes and widget specs.

These tests verify:
1. Database-level column existence (Phase 1)
2. Form view arch contains Tier 3 groups and widget attributes (Phase 2)
"""
import re

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestEtsyShopFormCurationPhase1(TransactionCase):
    """Phase 1: Database-level verification of Tier 3 columns.

    Direct SQL checks that the database schema has the expected columns
    for Tier 3 health monitoring and recovery fields.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_table_exists(self):
        """Phase 1: Verify etsy_shop table exists in database.

        The base etsy.shop model must exist with its primary table.
        """
        self.env.cr.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'etsy_shop'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            'etsy_shop table must exist in database',
        )

    def test_tier_3_columns_exist(self):
        """Phase 1: Verify Tier 3 columns exist on etsy_shop table.

        Required columns for health monitoring and recovery:
        - active_source_changed_at (Datetime)
        - auto_recovery (Boolean)
        - health_check_consecutive_failures (Integer)
        - recovery_probe_consecutive_successes (Integer)
        """
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop'
            ORDER BY column_name
        """)
        columns = {row[0]: row[1] for row in self.env.cr.fetchall()}

        tier_3_fields = {
            'active_source_changed_at': 'timestamp without time zone',
            'auto_recovery': 'boolean',
            'health_check_consecutive_failures': 'integer',
            'recovery_probe_consecutive_successes': 'integer',
        }

        for field_name, expected_type in tier_3_fields.items():
            self.assertIn(
                field_name,
                columns,
                f'Column {field_name} must exist on etsy_shop table',
            )
            actual_type = columns[field_name]
            # Allow timestamp with/without time zone for Datetime
            if expected_type == 'timestamp without time zone':
                self.assertIn(
                    actual_type,
                    ['timestamp without time zone', 'timestamp with time zone'],
                    f'Column {field_name} must be timestamp type, got {actual_type}',
                )
            else:
                self.assertEqual(
                    actual_type,
                    expected_type,
                    f'Column {field_name} must be {expected_type}, got {actual_type}',
                )

    def test_active_source_column_type(self):
        """Phase 1: Verify active_source column is character varying (VARCHAR).

        The active_source field is a Selection field that stores string values.
        """
        self.env.cr.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop'
            AND column_name = 'active_source'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result,
            'active_source column must exist on etsy_shop table',
        )
        self.assertEqual(
            result[0],
            'character varying',
            'active_source must be VARCHAR (character varying) type',
        )


@tagged('post_install', '-at_install')
class TestEtsyShopFormCurationPhase2(TransactionCase):
    """Phase 2: ORM and view XML verification for form curation.

    Tests the form view arch via Odoo ORM API to verify:
    - Tier 3 fields are hidden with groups="base.group_no_one"
    - active_source has widget="badge" attribute
    - etsy_api_shop_id has class="mu-mono" attribute
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_fields_view_get_tier_3_groups_attribute(self):
        """Phase 2: Verify form view contains groups="base.group_no_one" for Tier 3.

        The form arch must contain:
        - All 4 Tier 3 field names in the arch XML
        - groups="base.group_no_one" attributes on Tier 3 fields
        """
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        arch = view.arch

        self.assertIsNotNone(arch, 'Form view arch must exist')

        # Verify groups attribute is present
        self.assertIn(
            'groups="base.group_no_one"',
            arch,
            'Form must contain groups="base.group_no_one" for Tier 3 visibility',
        )

        # Verify all 4 Tier 3 fields are in the arch
        tier_3_fields = [
            'active_source_changed_at',
            'auto_recovery',
            'health_check_consecutive_failures',
            'recovery_probe_consecutive_successes',
        ]

        for field_name in tier_3_fields:
            self.assertIn(
                f'name="{field_name}"',
                arch,
                f'Field {field_name} must be present in form view arch',
            )

    def test_active_source_widget_badge(self):
        """Phase 2: Verify active_source field has widget="badge" attribute.

        The active_source Selection field must render as a badge widget
        in the form view for visual consistency with MU design system.
        """
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        arch = view.arch

        self.assertIsNotNone(arch, 'Form view arch must exist')

        # Regex to find <field name="active_source" ... widget="badge" ...>
        pattern = r'<field[^>]*name="active_source"[^>]*widget="badge"'

        match = re.search(pattern, arch)
        self.assertIsNotNone(
            match,
            'active_source field must have widget="badge" attribute',
        )

    def test_etsy_api_shop_id_mu_mono_class(self):
        """Phase 2: Verify etsy_api_shop_id field has class="mu-mono" attribute.

        The etsy_api_shop_id field (shop ID string) must have the mu-mono
        CSS class from the Mu design system for monospace rendering.
        """
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        arch = view.arch

        self.assertIsNotNone(arch, 'Form view arch must exist')

        # Regex to find <field name="etsy_api_shop_id" ... class="mu-mono" ...>
        pattern = r'<field[^>]*name="etsy_api_shop_id"[^>]*class="mu-mono"'

        match = re.search(pattern, arch)
        self.assertIsNotNone(
            match,
            'etsy_api_shop_id field must have class="mu-mono" attribute',
        )
