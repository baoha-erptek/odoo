"""Sync health observability model.

Tracks the latest run state of any cron / wizard / batch process that touches
Etsy data. One row per integration name; upserted via ``report_run``.

Used by:
- email cron (`_cron_fetch_etsy_emails`)
- import wizard
- migration wizard (deferred)
- image-download cron (deferred)
"""
from odoo import api, fields, models


class EtsySyncHealth(models.Model):
    _name = 'etsy.sync.health'
    _description = 'Etsy Sync Health'
    _order = 'last_run_at desc, name'

    name = fields.Char(string='Integration', required=True, index=True)
    state = fields.Selection(
        [('idle', 'Idle'),
         ('running', 'Running'),
         ('ok', 'OK'),
         ('warning', 'Warning'),
         ('error', 'Error')],
        default='idle', required=True, index=True)
    last_run_at = fields.Datetime(string='Last Run')
    last_successful_run_at = fields.Datetime(string='Last Success')
    last_run_row_count = fields.Integer(string='Rows Processed')
    last_run_error_count = fields.Integer(string='Errors')
    last_error_message = fields.Text(string='Last Error')
    last_processed_id = fields.Integer(
        string='Last Processed ID',
        help='Resumability checkpoint for batched workers')
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)',
         'Sync health rows are keyed by integration name; must be unique.'),
    ]

    @api.model
    def report_run(self, integration_name, *,
                   row_count=None, error_count=None,
                   error_message=None, last_id=None, state=None):
        """Upsert the row for ``integration_name`` with the supplied fields.

        Only fields explicitly passed (non-None) are written; the others keep
        their previous value. ``last_run_at`` is always bumped. When
        ``state == 'ok'``, ``last_successful_run_at`` is also bumped.
        Returns the (created or updated) record.
        """
        record = self.search([('name', '=', integration_name)], limit=1)
        vals = {'last_run_at': fields.Datetime.now()}
        if row_count is not None:
            vals['last_run_row_count'] = row_count
        if error_count is not None:
            vals['last_run_error_count'] = error_count
        if error_message is not None:
            vals['last_error_message'] = error_message
        if last_id is not None:
            vals['last_processed_id'] = last_id
        if state is not None:
            vals['state'] = state
            if state == 'ok':
                vals['last_successful_run_at'] = vals['last_run_at']

        if record:
            record.write(vals)
        else:
            vals['name'] = integration_name
            record = self.create(vals)
        return record
