"""Wizard for remediating the historical Etsy order backlog.

W3.2a backbone: model + 12 fields, anomaly quarantine (T036), batched
iteration with last_processed_id resumption (T037 / R4), per-batch
``etsy.sync.health`` checkpoints (T038 / R8), and an orchestration shell
(T046) that walks every Etsy order through the per-checkbox fix pipeline.

The fix-helper bodies (T039 _fix_financial_config, T040 _fix_shipping_lines,
T041 _fix_prices_from_excel, T042 _fix_product_config, T043
_confirm_and_complete, T044 _generate_dedup_report, T045
action_apply_merges) land in W3.2b. They are stubbed here as no-ops so the
orchestration shell can be exercised end-to-end on real data without
mutating it.
"""
import csv
import logging
import os
import tempfile

from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# etsy.sync.health integration name for this wizard.
_HEALTH_INTEGRATION = 'data_migration'

# Anomaly export header — see T036 / spec R9.
_ANOMALY_CSV_HEADER = ('transaction_id', 'order_id', 'shop', 'raw_price')


class DataMigrationWizard(models.TransientModel):
    _name = 'etsy.data.migration.wizard'
    _description = 'Etsy Data Migration Wizard'

    # ------------------------------------------------------------------
    # Fields (T035 — 12 fields per spec US6)
    # ------------------------------------------------------------------
    excel_file = fields.Binary(
        string='Source Excel (optional)',
        help='Optional Excel file consumed by the price-from-Excel fix '
             '(T041, lands in W3.2b). Not required for the backbone run.')
    excel_filename = fields.Char(
        string='Filename',
        help='Filename of the uploaded source Excel file (optional).')
    auto_confirm = fields.Boolean(
        string='Confirm + invoice', default=True,
        help='When enabled, draft orders are confirmed, their pickings '
             'are validated, and invoice_status is set to invoiced (R5). '
             'No invoice records are generated.')
    fix_shipping_lines = fields.Boolean(
        string='Add shipping lines', default=True,
        help='Backfill the Etsy Shipping order line on orders where '
             'etsy_shipping_cost > 0 and no shipping line exists.')
    fix_financial_config = fields.Boolean(
        string='Fix financial config', default=True,
        help='Set fiscal_position_id, payment_term_id, team_id, '
             'pricelist_id, currency_id on every Etsy order.')
    fix_product_config = fields.Boolean(
        string='Fix product config', default=True,
        help='Set is_storable=True and run the product categorizer on '
             'all Etsy products touched in the current batch.')
    generate_dedup_report = fields.Boolean(
        string='Generate dedup CSV', default=True,
        help='Cluster Etsy partners by normalized name+address+city+zip '
             'and write a /tmp CSV of proposed merges. The wizard never '
             'modifies partners on its own (R10) — apply via the '
             'separate Apply Merges action with a BA-approved CSV.')
    include_anomalies = fields.Boolean(
        string='Include $0 anomalies', default=False,
        help='When False (default), orders with etsy_price_anomaly=True '
             'are excluded from the migration loop and only quarantined '
             'to a CSV. Enable to also process them through the fixes.')
    resume_from_checkpoint = fields.Boolean(
        string='Resume from last checkpoint', default=True,
        help='When True, the migration only iterates orders with '
             'id > last_processed_id (R4). Disable for a full re-run.')
    batch_size = fields.Integer(
        string='Batch size', default=500, required=True,
        help='Number of orders per savepoint. 500 balances memory '
             'against rollback granularity for the 17K backlog.')
    last_processed_id = fields.Integer(
        string='Last processed order id', readonly=True, default=0,
        help='Resumability checkpoint — updated after each successful '
             'batch. The next run with resume_from_checkpoint=True '
             'starts at id > last_processed_id.')
    sync_health_id = fields.Many2one(
        'etsy.sync.health', string='Sync Health', readonly=True,
        help='Health row created/updated for this run. Smart button '
             'opens the live state.')
    status_message = fields.Text(string='Status', readonly=True)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('batch_size')
    def _check_batch_size(self):
        for wizard in self:
            if wizard.batch_size < 1:
                raise ValidationError(_(
                    "Batch size must be at least 1 (got %(size)s).",
                    size=wizard.batch_size))

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------
    def action_migrate(self):
        """Run the migration: quarantine anomalies, then batch-iterate.

        **Failure semantics (R4)**: per-order savepoints isolate single-order
        failures so the rest of the batch continues. ``last_processed_id``
        advances to the last id of every completed batch, including batches
        with errored orders — failed orders are recorded in
        ``etsy.sync.health.last_error_message`` and ``last_run_error_count``,
        not retried automatically. To retry, the operator either (a) sets
        ``resume_from_checkpoint=False`` for a full re-scan, or (b) manually
        clears ``etsy_price_anomaly`` / fixes the underlying issue and runs
        again. A dedicated retry-failed-orders helper is W3.2b territory.
        """
        self.ensure_one()
        SyncHealth = self.env['etsy.sync.health']
        health = SyncHealth.report_run(
            _HEALTH_INTEGRATION, state='running',
            row_count=0, error_count=0,
            last_id=self.last_processed_id if self.resume_from_checkpoint
            else 0,
        )
        self.sync_health_id = health.id

        anomaly_count = self._quarantine_anomalies()

        domain = [('etsy_order_id', '!=', False)]
        if self.resume_from_checkpoint and self.last_processed_id:
            domain.append(('id', '>', self.last_processed_id))
        domain.append(('etsy_price_anomaly', '=', self.include_anomalies))

        SaleOrder = self.env['sale.order']
        order_ids = SaleOrder.search(domain, order='id asc').ids
        total = len(order_ids)
        batch_size = max(1, self.batch_size or 500)

        processed = 0
        errors = 0
        last_error = None

        for offset in range(0, total, batch_size):
            chunk_ids = order_ids[offset:offset + batch_size]
            try:
                with self.env.cr.savepoint():
                    chunk = SaleOrder.browse(chunk_ids)
                    for order in chunk:
                        try:
                            with self.env.cr.savepoint():
                                self._process_one_order(order)
                        except Exception as exc:  # noqa: BLE001
                            errors += 1
                            last_error = f'Order {order.id}: {exc}'
                            _logger.exception(
                                'Migration error on order %s', order.id)
                        processed += 1
            except Exception as exc:  # noqa: BLE001
                # The outer savepoint should not normally fire — per-order
                # savepoints already isolate failures. If it does (DB
                # connection issue, lock timeout), record the whole chunk
                # as errored.
                errors += len(chunk_ids)
                last_error = f'Batch {offset}-{offset + len(chunk_ids)}: {exc}'
                _logger.exception(
                    'Migration batch failed at offset %d', offset)

            if chunk_ids:
                self.last_processed_id = chunk_ids[-1]
            SyncHealth.report_run(
                _HEALTH_INTEGRATION,
                row_count=processed,
                error_count=errors,
                error_message=last_error,
                last_id=self.last_processed_id,
            )

        if total == 0 or errors == 0:
            final_state = 'ok'
        elif errors / total < 0.05:
            final_state = 'warning'
        else:
            final_state = 'error'
        SyncHealth.report_run(
            _HEALTH_INTEGRATION,
            row_count=processed,
            error_count=errors,
            state=final_state,
            error_message=last_error,
            last_id=self.last_processed_id,
        )

        self.status_message = _(
            "Migration complete: %(processed)s orders processed, "
            "%(errors)s errors, %(anomalies)s anomalies quarantined.",
            processed=processed,
            errors=errors,
            anomalies=anomaly_count,
        )
        return self._return_form()

    def action_apply_merges(self):
        """Apply BA-approved partner merges from an uploaded CSV (T045).

        Stub for W3.2a; full implementation lands in W3.2b. The presence
        of this method is part of the wizard contract so callers can
        bind a button to it without conditional checks.
        """
        self.ensure_one()
        self.status_message = _(
            "Apply Merges is not yet implemented (lands in W3.2b).")
        return self._return_form()

    # ------------------------------------------------------------------
    # Anomaly quarantine (T036 / R9)
    # ------------------------------------------------------------------
    def _quarantine_anomalies(self):
        """Export Etsy orders with etsy_price_anomaly=True to /tmp CSV.

        ``etsy_price_anomaly`` is a stored compute on ``sale.order`` set
        to True when ``etsy_order_id`` is set and ``amount_total <= 0``
        — see ``models/sale_order.py``. Idempotent: each call writes a
        timestamped CSV; no order data is mutated.

        Returns the number of anomalies exported.
        """
        anomalies = self.env['sale.order'].search(
            [('etsy_order_id', '!=', False),
             ('etsy_price_anomaly', '=', True)],
            order='id asc')
        if not anomalies:
            return 0

        # mkstemp() creates the file with mode 0o600 and a guaranteed-unique
        # name — avoids the world-readable default of plain open() in /tmp
        # and the microsecond-collision risk from timestamp-only naming.
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        fd, path = tempfile.mkstemp(
            prefix=f'etsy_anomalies_{timestamp}_',
            suffix='.csv')
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(_ANOMALY_CSV_HEADER)
            for order in anomalies:
                line = order.order_line[:1]
                writer.writerow([
                    line.etsy_transaction_id if line else '',
                    order.etsy_order_id or '',
                    order.etsy_shop_id.name if order.etsy_shop_id else '',
                    f'{line.price_unit:.2f}' if line else '0.00',
                ])
        _logger.debug(
            'Anomaly quarantine: wrote %d rows to %s',
            len(anomalies), path)
        return len(anomalies)

    # ------------------------------------------------------------------
    # Per-order orchestration seam (T046 shell)
    # ------------------------------------------------------------------
    def _process_one_order(self, order):
        """Run all enabled fix helpers against a single order.

        This is the per-order seam tests (and W3.2b) hook. Helpers are
        gated by their respective checkbox fields so a no-op run (all
        checkboxes off) advances ``last_processed_id`` and updates
        ``sync.health`` without mutating data.
        """
        self.ensure_one()
        if self.fix_financial_config:
            self._fix_financial_config(order)
        if self.fix_shipping_lines:
            self._fix_shipping_lines(order)
        if self.fix_product_config:
            self._fix_product_config(order.order_line.product_id)
        if self.auto_confirm:
            self._confirm_and_complete(order)

    # ------------------------------------------------------------------
    # Fix-helper stubs — bodies land in W3.2b (T039–T045)
    # ------------------------------------------------------------------
    def _fix_financial_config(self, orders):
        """T039 stub — lands in W3.2b."""

    def _fix_shipping_lines(self, orders):
        """T040 stub — lands in W3.2b."""

    def _fix_prices_from_excel(self, orders):
        """T041 stub — lands in W3.2b."""

    def _fix_product_config(self, products):
        """T042 stub — lands in W3.2b."""

    def _confirm_and_complete(self, orders):
        """T043 stub — lands in W3.2b. Will reuse ``sale.order``'s
        existing ``_etsy_auto_confirm`` helper rather than re-implement.
        """

    def _generate_dedup_report(self, partners):
        """T044 stub — lands in W3.2b."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _return_form(self):
        """Return an action that keeps the wizard form open."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
