"""Per-sheet schema fingerprint whitelist (Spec 010 P-HUB-XLS-PARSE T002).

R-010-2 mitigation: parser refuses to import a sheet whose header
fingerprint isn't admin-approved. C-CSF-001 UNIQUE(sheet_name,
column_headers_sha256) mirrored in init().
"""

from odoo import fields, models


class ProductCatalogSheetFingerprint(models.Model):
    _name = 'product.catalog.sheet.fingerprint'
    _description = 'Product Catalog Sheet Fingerprint (Approval Whitelist)'
    _order = 'sheet_name, first_seen_at desc'

    sheet_name = fields.Char(required=True, index=True)
    column_headers_sha256 = fields.Char(required=True, index=True)
    column_headers_preview = fields.Text(required=True)
    approved = fields.Boolean(required=True, default=False)
    approved_by = fields.Many2one('res.users')
    approved_at = fields.Datetime()
    first_seen_at = fields.Datetime(required=True, default=fields.Datetime.now)
    last_seen_at = fields.Datetime(required=True, default=fields.Datetime.now)

    def init(self):
        cr = self.env.cr
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_product_catalog_sheet_fingerprint_sheet_sha'
                ) THEN
                    ALTER TABLE product_catalog_sheet_fingerprint
                        ADD CONSTRAINT uniq_product_catalog_sheet_fingerprint_sheet_sha
                        UNIQUE (sheet_name, column_headers_sha256);
                END IF;
            END $$
        """)
