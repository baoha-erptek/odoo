"""
Phase 1: Database-level verification for P-HUB-SKU-BUILDER (Spec 009 §2.5).

Verifies the underlying PostgreSQL schema for the managed SKU taxonomy:
- mhc_sku_family table + columns + UNIQUE(code) C-SKU-FAM-001 mirror + index
- product_attribute_value extension columns (x_code / x_namespace) +
  Many2many relation table for x_applicable_family_ids
- Seed counts: 22 families, 7 attributes, >=55 attribute values
- product.sku.builder.wizard transient model registered in ir_model

Tests use direct SQL via self.env.cr.execute to verify schema state at the
lowest level, independent of ORM machinery.

Spec 009 T048. RED before T038-T047 implementation lands.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1HubSkuBuilderDB(TransactionCase):
    """Direct PostgreSQL verification for P-HUB-SKU-BUILDER schema."""

    # ------------------------------------------------------------------
    # mhc.sku.family — model + table + columns
    # ------------------------------------------------------------------

    def test_mhc_sku_family_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'mhc_sku_family'
            )
        """)
        self.assertTrue(
            self.env.cr.fetchone()[0],
            "mhc_sku_family table must exist",
        )

    def test_mhc_sku_family_columns(self):
        expected_columns = (
            'code',
            'name',
            'priority',
            'regex_pattern',
            'default_route',
            'default_material_id',
            'active',
        )
        for column in expected_columns:
            self.env.cr.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'mhc_sku_family'
                  AND column_name = %s
                """,
                (column,),
            )
            self.assertIsNotNone(
                self.env.cr.fetchone(),
                "mhc_sku_family.%s column must exist" % column,
            )

    def test_unique_constraint_sku_family_code_mirrored(self):
        """C-SKU-FAM-001 UNIQUE(code) mirror from init() must be present in pg_constraint."""
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uniq_mhc_sku_family_code'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "C-SKU-FAM-001 UNIQUE(code) constraint must be mirrored in pg_constraint",
        )

    def test_index_on_sku_family_code(self):
        """Odoo's index=True on code creates a btree index — name format varies
        across Odoo versions (single vs double underscore). Just assert one
        exists that references the code column."""
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'mhc_sku_family'
              AND indexdef ILIKE '%(code)%'
              AND indexname != 'uniq_mhc_sku_family_code'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "mhc_sku_family.code must have a btree index",
        )

    # ------------------------------------------------------------------
    # mhc.sku.family — seeds
    # ------------------------------------------------------------------

    def test_sku_family_seed_count(self):
        """22 family rows must be seeded from data/sku_family_seed.xml (SKU_GRAMMAR §2)."""
        self.env.cr.execute("SELECT count(*) FROM mhc_sku_family")
        count = self.env.cr.fetchone()[0]
        self.assertGreaterEqual(
            count, 22,
            "At least 22 family rows must be seeded (got %s)" % count,
        )

    def test_sku_family_seed_specific_codes_present(self):
        """Representative family codes from each routing bucket must be seeded."""
        expected_codes = ('RDS', 'MUG', 'APR', 'DMT', 'APP')
        self.env.cr.execute(
            "SELECT code FROM mhc_sku_family WHERE code = ANY(%s)",
            (list(expected_codes),),
        )
        found_codes = {row[0] for row in self.env.cr.fetchall()}
        missing = set(expected_codes) - found_codes
        self.assertFalse(
            missing,
            "Seed missing required family codes: %s" % missing,
        )

    # ------------------------------------------------------------------
    # product.attribute.value extension
    # ------------------------------------------------------------------

    def test_product_attribute_value_x_code_column(self):
        """T039: x_code Char(6) added via _inherit."""
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_attribute_value'
              AND column_name = 'x_code'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "product_attribute_value.x_code column must exist",
        )

    def test_product_attribute_value_x_namespace_column(self):
        """T039: x_namespace Selection (nullable) for Size-family disambiguation."""
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_attribute_value'
              AND column_name = 'x_namespace'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "product_attribute_value.x_namespace column must exist",
        )

    def test_product_attribute_value_family_m2m_table_exists(self):
        """T039: x_applicable_family_ids M2M creates a JOIN table."""
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE '%product_attribute_value%sku_family%'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "M2M JOIN table for x_applicable_family_ids must exist",
        )

    # ------------------------------------------------------------------
    # Attribute + value seeds (sku_attribute_seed.xml)
    # ------------------------------------------------------------------

    def test_attribute_seed_count(self):
        """7 product.attribute rows must be seeded (Family-tag/Material/Shape/Size/Fluid oz/Apparel size/Color)."""
        # Translatable Char names live in jsonb; cast to text and use ->>'en_US'
        self.env.cr.execute("""
            SELECT count(*) FROM product_attribute
            WHERE (name->>'en_US') IN ('Family', 'Material', 'Shape', 'Size',
                                       'Fluid oz', 'Apparel size', 'Color')
               OR name::text ILIKE '%Family%'
               OR name::text ILIKE '%Material%'
               OR name::text ILIKE '%Shape%'
               OR name::text ILIKE '%Size%'
               OR name::text ILIKE '%Fluid oz%'
               OR name::text ILIKE '%Apparel size%'
               OR name::text ILIKE '%Color%'
        """)
        count = self.env.cr.fetchone()[0]
        self.assertGreaterEqual(
            count, 7,
            "At least 7 product.attribute seeds expected (got %s)" % count,
        )

    def test_attribute_value_seed_count_minimum(self):
        """At least 55 product.attribute.value rows with x_code populated."""
        self.env.cr.execute("""
            SELECT count(*) FROM product_attribute_value
            WHERE x_code IS NOT NULL AND x_code != ''
        """)
        count = self.env.cr.fetchone()[0]
        self.assertGreaterEqual(
            count, 55,
            "At least 55 attribute values with x_code expected (got %s)" % count,
        )

    # ------------------------------------------------------------------
    # product.sku.builder.wizard — model registration
    # ------------------------------------------------------------------

    def test_builder_wizard_model_registered(self):
        """T045: TransientModel must register in ir_model."""
        self.env.cr.execute(
            "SELECT 1 FROM ir_model WHERE model = 'product.sku.builder.wizard'"
        )
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "product.sku.builder.wizard must be registered in ir_model",
        )

    def test_builder_wizard_is_transient(self):
        """Wizard model must be transient (table exists but cleared periodically)."""
        self.env.cr.execute(
            "SELECT transient FROM ir_model WHERE model = 'product.sku.builder.wizard'"
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "model row must exist")
        self.assertTrue(row[0], "product.sku.builder.wizard must be transient")
