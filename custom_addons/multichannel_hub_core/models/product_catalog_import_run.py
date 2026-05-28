"""Audit header for catalog Excel sync runs (Spec 010 P-HUB-XLS-PARSE T002).

One row per cron-run / wizard-run. Captures parse stats + per-sheet
summary. Error lines persist under `line_ids`; success/unchanged lines
are cleared at end-of-run for volume control.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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

    @api.model
    def _cron_run_catalog_sync(self):
        """Spec 010 P-HUB-XLS-CRON — daily scheduled entry point.

        Selects source via ICPs (GDrive takes precedence over local):
        - `multichannel_hub.catalog_cron_gdrive_file_id`
        - `multichannel_hub.catalog_cron_source_path`

        No-op when neither is configured. All failures (GDrive HttpError,
        OSError, parser exception) → warning log + return False so the
        cron survives.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        gdrive_file_id = (ICP.get_param(
            'multichannel_hub.catalog_cron_gdrive_file_id') or '').strip()
        source_path = (ICP.get_param(
            'multichannel_hub.catalog_cron_source_path') or '').strip()
        if gdrive_file_id:
            try:
                from ..services.gdrive_uploader_helper import fetch_gdrive_bytes
                source_bytes = fetch_gdrive_bytes(self.env, gdrive_file_id)
            except Exception as exc:  # noqa: BLE001 — cron must survive
                _logger.warning(
                    "catalog cron GDrive fetch failed file_id=%s: %s",
                    gdrive_file_id, exc,
                )
                return False
            run = self.create({
                'mode': 'commit',
                'source_kind': 'gdrive',
                'source_path': gdrive_file_id,
            })
            run.run_parse_and_ingest(source_bytes)
            return True
        if not source_path:
            _logger.debug(
                "catalog cron skipped: no GDrive file id and no local path"
                " configured",
            )
            return False
        try:
            with open(source_path, 'rb') as fp:
                source_bytes = fp.read()
        except OSError as exc:
            _logger.warning(
                "catalog cron local source unreadable %s: %s", source_path, exc,
            )
            return False
        run = self.create({
            'mode': 'commit',
            'source_kind': 'local',
            'source_path': source_path,
        })
        run.run_parse_and_ingest(source_bytes)
        return True

    def run_parse_and_ingest(self, source_bytes):
        """Spec 010 P-HUB-XLS-CRON — orchestrator.

        Args:
            source_bytes: bytes of the xlsx file.

        Phases (this run owns the audit row + counters; called from cron
        or from the manual-run wizard):
            1. state='parsing'
            2. excel_catalog_parser.parse(env, self, source_bytes)
            3. catalog_ingestor.upsert(env, self, lines) on the pending rows
            4. state='imported' on success / 'error' on parser failure

        Per-row failures during ingest don't flip the whole run to 'error' —
        they accumulate in rows_error counter; rows_upserted/unchanged
        grow normally for successful rows. A truly-unrecoverable parser
        exception (file corrupt / openpyxl raises) flips the run to error.
        """
        from ..services.excel_catalog_parser import parse as parse_xlsx
        from ..services.catalog_ingestor import upsert as ingest_upsert
        self.ensure_one()
        self.sudo().write({
            'state': 'parsing',
            'start_at': fields.Datetime.now(),
            'file_size_bytes': len(source_bytes or b''),
        })
        try:
            parse_summary = parse_xlsx(self.env, self, source_bytes)
        except Exception as exc:  # noqa: BLE001 — parser-level failure path
            self.sudo().write({
                'state': 'error',
                'end_at': fields.Datetime.now(),
                'summary_json': '{"parser_error": %r}' % str(exc)[:1000],
            })
            raise
        # Pending lines from this run get upserted; error lines stay
        # untouched and survive end-of-run cleanup.
        pending = self.env['product.catalog.import.line'].sudo().search([
            ('run_id', '=', self.id),
            ('state', '=', 'pending'),
        ])
        ingest_counters = ingest_upsert(self.env, self, pending)
        self.sudo().write({
            'state': 'imported' if self.mode == 'commit' else 'previewed',
            'end_at': fields.Datetime.now(),
            'sheets_parsed': parse_summary.get('sheets_parsed', 0),
            'rows_total': parse_summary.get('rows_emitted', 0)
                          + parse_summary.get('rows_error', 0),
            'rows_upserted': ingest_counters.get('upserted', 0),
            'rows_unchanged': ingest_counters.get('unchanged', 0),
            'rows_error': parse_summary.get('rows_error', 0)
                          + ingest_counters.get('error', 0),
        })
        return {
            'run': self,
            'parse_summary': parse_summary,
            'ingest_counters': ingest_counters,
        }

    def init(self):
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS product_catalog_import_run_state_mode_idx
                ON product_catalog_import_run (state, mode)
        """)
