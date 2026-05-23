"""Audit header for catalog Excel sync runs (Spec 010 P-HUB-XLS-PARSE T002).

One row per cron-run / wizard-run. Captures parse stats + per-sheet
summary. Error lines persist under `line_ids`; success/unchanged lines
are cleared at end-of-run for volume control.
"""

from odoo import api, fields, models


STATE_VALUES = [
    ('parsing', 'Parsing'),
    ('previewed', 'Previewed (Dry Run)'),
    ('imported', 'Imported'),
    ('error', 'Error'),
    ('cancelled', 'Cancelled'),
]
MODE_VALUES = [
    ('dry_run', 'Dry Run'),
    ('commit', 'Commit'),
]
SOURCE_KIND_VALUES = [
    ('gdrive', 'Google Drive'),
    ('local', 'Local Path'),
    ('manual_upload', 'Manual Upload'),
]


class ProductCatalogImportRun(models.Model):
    _name = 'product.catalog.import.run'
    _description = 'Product Catalog Import Run'
    _order = 'start_at desc, id desc'

    name = fields.Char(required=True, index=True, copy=False,
                        default=lambda self: self._next_sequence())
    start_at = fields.Datetime(required=True, default=fields.Datetime.now)
    end_at = fields.Datetime()
    state = fields.Selection(STATE_VALUES, required=True, default='parsing', index=True)
    mode = fields.Selection(MODE_VALUES, required=True, default='dry_run')
    source_kind = fields.Selection(SOURCE_KIND_VALUES, required=True, default='manual_upload')
    source_path = fields.Char(required=True)
    file_size_bytes = fields.Integer()
    sheets_parsed = fields.Integer(default=0)
    rows_total = fields.Integer(default=0)
    rows_upserted = fields.Integer(default=0)
    rows_unchanged = fields.Integer(default=0)
    rows_error = fields.Integer(default=0)
    images_downloaded = fields.Integer(default=0)
    images_skipped_unchanged = fields.Integer(default=0)
    images_failed = fields.Integer(default=0)
    triggered_by = fields.Many2one('res.users')
    summary_json = fields.Text()
    line_ids = fields.One2many(
        'product.catalog.import.line', 'run_id', string='Lines',
    )

    @api.model
    def _next_sequence(self):
        seq = self.env['ir.sequence'].sudo().next_by_code(
            'product.catalog.import.run',
        )
        return seq or 'CAT-IMP-NEW'

    def init(self):
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS product_catalog_import_run_state_mode_idx
                ON product_catalog_import_run (state, mode)
        """)
