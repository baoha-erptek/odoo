"""Per-row staging for catalog Excel sync (Spec 010 P-HUB-XLS-PARSE T002).

Transient during parse; persists post-commit only for error rows. C-CIL-001
UNIQUE(run_id, sheet_name, row_number) mirrored in init() raw SQL.
"""

from odoo import fields, models


LINE_STATE_VALUES = [
    ('pending', 'Pending'),
    ('upserted', 'Upserted'),
    ('unchanged', 'Unchanged'),
    ('error', 'Error'),
]
ERROR_KIND_VALUES = [
    ('parse', 'Parse'),
    ('validation', 'Validation'),
    ('upsert', 'Upsert'),
    ('image_download', 'Image Download'),
    ('duplicate_sku', 'Duplicate SKU'),
]
SKU_V2_STATUS_VALUES = [
    ('matches', 'Matches'),
    ('non_canonical', 'Non-canonical'),
    ('msc_catchall', 'MSC Catch-all'),
]


class ProductCatalogImportLine(models.Model):
    _name = 'product.catalog.import.line'
    _description = 'Product Catalog Import Line'
    _order = 'run_id desc, sheet_name, row_number'

    run_id = fields.Many2one(
        'product.catalog.import.run',
        required=True, ondelete='cascade', index=True,
    )
    sheet_name = fields.Char(required=True)
    row_number = fields.Integer(required=True)
    sku = fields.Char(index=True)
    name = fields.Char()
    availability = fields.Char()
    price_usd = fields.Float()
    price_eu = fields.Float()
    price_cad = fields.Float()
    price_vnd = fields.Float()
    shipping_fee = fields.Float()
    image_1_ref = fields.Char()
    image_2_ref = fields.Char()
    state = fields.Selection(LINE_STATE_VALUES, required=True, default='pending')
    error_kind = fields.Selection(ERROR_KIND_VALUES)
    error_message = fields.Text()
    target_product_id = fields.Many2one('product.template')
    suggested_sku = fields.Char()
    sku_v2_status = fields.Selection(SKU_V2_STATUS_VALUES)

    def init(self):
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS product_catalog_import_line_run_state_idx
                ON product_catalog_import_line (run_id, state)
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS product_catalog_import_line_state_kind_idx
                ON product_catalog_import_line (state, error_kind)
        """)
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_product_catalog_import_line_run_sheet_row'
                ) THEN
                    ALTER TABLE product_catalog_import_line
                        ADD CONSTRAINT uniq_product_catalog_import_line_run_sheet_row
                        UNIQUE (run_id, sheet_name, row_number);
                END IF;
            END $$
        """)
