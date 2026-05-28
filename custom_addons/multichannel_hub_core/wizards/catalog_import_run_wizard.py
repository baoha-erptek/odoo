"""Manual catalog Excel sync wizard (Spec 010 P-HUB-XLS-CRON manual run).

Operator uploads an xlsx file + picks dry-run or commit mode. Creates a
`product.catalog.import.run` row and routes to
`run_parse_and_ingest(source_bytes)`. FR-017 method-top gate.

The cron-scheduled equivalent (daily 02:00 UTC + GDrive fetcher + admin
manual-trigger button) lands in a follow-up UI slice.
"""

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'


class CatalogImportRunWizard(models.TransientModel):
    _name = 'catalog.import.run.wizard'
    _description = 'Manual Catalog Excel Import Wizard'

    source_file = fields.Binary(
        string='Excel File (.xlsx)', required=True, attachment=False,
    )
    source_filename = fields.Char()
    mode = fields.Selection(
        [('dry_run', 'Dry Run (no writes)'),
         ('commit', 'Commit (write to product.template)')],
        required=True, default='dry_run',
    )

    def _check_ba_or_raise(self):
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_(
                "Only BA users can run the catalog Excel sync wizard."
            ))

    def action_run(self):
        self._check_ba_or_raise()  # FR-017 25th confirmation
        self.ensure_one()
        if not self.source_file:
            raise AccessError(_("Please upload an .xlsx file."))
        source_bytes = base64.b64decode(self.source_file)
        run = self.env['product.catalog.import.run'].sudo().create({
            'mode': self.mode,
            'source_kind': 'manual_upload',
            'source_path': self.source_filename or 'manual_upload.xlsx',
            'triggered_by': self.env.user.id,
        })
        run.run_parse_and_ingest(source_bytes)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.catalog.import.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('Catalog Import Run %s') % run.name,
        }
