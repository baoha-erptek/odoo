"""logistics.partner — GDrive inbox configuration per logistics supplier.

Per Spec 004a US6 + FR-026..FR-035. The GDrive polling cron iterates active
partners, downloads new .xlsx files from each `gdrive_inbox_folder_id`,
imports them via `import_log_from_bytes`, then archives on success.

Constraints:
- UNIQUE(code) — `_sql_constraints` mirrored in `init()` raw SQL per
  `project_sql_constraints_drift.md` template (8th confirmation).
- C-LP-001: poll_interval_minutes >= 1.

Defense-in-depth (FR-017 14th-confirmation pattern):
- ACL: BA-shipping/manager read-only (1,0,0,0); group_system 1,1,1,1.
- `action_toggle_is_active` is the BA-manager escape hatch — calls
  `_check_ba_manager_or_raise()` BEFORE `sudo()` flips `is_active`.
"""
from __future__ import annotations

import logging
import os
import os.path

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.multichannel_hub_core.utils.rate_limiter import TokenBucket

from ..services import tracking_importer

_logger = logging.getLogger(__name__)

# Module-level singleton: shared GDrive quota (1000 req per 100 sec).
# Each cron call to a Drive API consumes one token; if exhausted, the cron
# defers the partner to the next tick instead of blocking the worker.
_RATE_LIMITER = TokenBucket(1000, 100)


class LogisticsPartner(models.Model):
    _name = 'logistics.partner'
    _description = 'Logistics Partner — GDrive inbox configuration'
    _inherit = ['mail.thread']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, index=True,
                       help='Unique partner code (folder-path-friendly).')
    gdrive_inbox_folder_id = fields.Char(
        string='GDrive Inbox Folder ID',
        help='Where partner drops .xlsx tracking files.')
    gdrive_archive_folder_id = fields.Char(
        string='GDrive Archive Folder ID',
        help='Where successfully imported files are moved.')
    poll_interval_minutes = fields.Integer(
        string='Poll Interval (minutes)', default=15, required=True,
        help='Minimum minutes between polls for this partner.')
    is_active = fields.Boolean(
        string='Active', default=True, tracking=True,
        help='Cron skips inactive partners.')
    last_poll_at = fields.Datetime(
        string='Last Poll At', readonly=True,
        help='Set after every poll attempt (success or failure).')
    last_success_poll_at = fields.Datetime(
        string='Last Successful Poll At', readonly=True,
        help='Set only on log.state in (ok, warning).')

    _sql_constraints = [
        ('logistics_partner_code_uniq', 'UNIQUE(code)',
         'Partner code must be unique'),
    ]

    # ------------------------------------------------------------------
    # Drift-template UNIQUE mirror (8th confirmation per memory
    # project_sql_constraints_drift.md). _sql_constraints does not always
    # reach Postgres on multi-addon installs; init() ensures it does.
    # ------------------------------------------------------------------
    def init(self):
        # Pre-check via pg_constraint to avoid duplicate_object on re-run.
        self.env.cr.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = %s",
            ('logistics_partner_code_uniq',),
        )
        if not self.env.cr.fetchone():
            self.env.cr.execute(
                "ALTER TABLE logistics_partner "
                "ADD CONSTRAINT logistics_partner_code_uniq UNIQUE (code)"
            )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('poll_interval_minutes')
    def _check_poll_interval_positive(self):
        for rec in self:
            if rec.poll_interval_minutes < 1:
                raise ValidationError(
                    _('Poll interval must be at least 1 minute.'))

    # ------------------------------------------------------------------
    # Defense-in-depth gate
    # ------------------------------------------------------------------
    def _check_ba_manager_or_raise(self):
        """Raise AccessError if user lacks BA-manager (or system) role."""
        user = self.env.user
        if (user.has_group('multichannel_hub_fulfillment.group_ba_manager')
                or user.has_group('base.group_system')):
            return
        raise AccessError(
            _('Toggling logistics partner status requires BA Manager role.'))

    def action_toggle_is_active(self):
        """RPC: BA-manager-only flip of `is_active` (FR-035)."""
        self.ensure_one()
        self._check_ba_manager_or_raise()
        # sudo: BA-manager has read-only ACL; gate has already verified the
        # user, so sudo bypass is bounded to a single boolean field.
        self.sudo().write({'is_active': not self.is_active})
        return True

    # ------------------------------------------------------------------
    # Cron + per-partner polling
    # ------------------------------------------------------------------
    @api.model
    def _cron_poll_inbox(self):
        """Cron entry — iterate active partners with non-empty inbox folder.

        Per-partner errors are caught + logged to sync.health; one partner's
        failure does NOT abort the rest (FR-033/FR-036 contract).
        """
        partners = self.search([
            ('is_active', '=', True),
            ('gdrive_inbox_folder_id', '!=', False),
        ])
        for partner in partners:
            if not partner._is_due():
                continue
            try:
                with self.env.cr.savepoint():
                    partner._poll_partner_inbox()
            except Exception as exc:  # noqa: BLE001 — per-partner isolation
                _logger.warning(
                    "logistics.partner %s poll failed: %s",
                    partner.code, exc)
                partner._record_gdrive_health_error(str(exc))

    def _is_due(self) -> bool:
        """True if enough minutes have elapsed since last_poll_at."""
        self.ensure_one()
        if not self.last_poll_at:
            return True
        now = fields.Datetime.now()
        elapsed = (now - self.last_poll_at).total_seconds() / 60.0
        return elapsed >= self.poll_interval_minutes

    def _poll_partner_inbox(self):
        """Per-partner polling: list → idempotent download → import → archive.

        Idempotency: file_id lookup against existing
        tracking.import.log.source_gdrive_file_id BEFORE download.

        Rate-limit budget: 1 token per Drive API call. On exhaustion, defer
        remaining files to next cron tick.
        """
        self.ensure_one()
        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import (
            GdriveUploader,
        )
        client = GdriveUploader()
        try:
            files = client.list_files(
                self.gdrive_inbox_folder_id,
                modified_after=self.last_poll_at,
            )
        except Exception as exc:  # noqa: BLE001 — auth/IO isolation
            self._record_gdrive_health_error(str(exc))
            self.last_poll_at = fields.Datetime.now()
            return

        log_model = self.env['tracking.import.log'].sudo()
        for entry in files:
            name = entry.get('name', '')
            if not name.lower().endswith('.xlsx'):
                continue
            file_id = entry.get('id')
            if not file_id:
                continue
            if not _RATE_LIMITER.acquire(1):
                # Rate limit is an exceptional condition (operator should know):
                # WARNING-level so quota pressure is visible in standard log feeds.
                _logger.warning(
                    "logistics.partner %s: rate limit exhausted, "
                    "deferring remaining files", self.code)
                break
            existing = log_model.search(
                [('source_gdrive_file_id', '=', file_id)], limit=1)
            if existing:
                continue  # FR-030 file-level idempotency
            self._process_one_file(client, file_id, name)

        self.last_poll_at = fields.Datetime.now()

    def _process_one_file(self, client, file_id: str, name: str):
        """Download, import, and archive (or mark error) one file."""
        self.ensure_one()
        try:
            data = client.download_file(file_id)
        except Exception as exc:  # noqa: BLE001 — per-file isolation; record + skip
            self._record_gdrive_health_error(
                f"download failed for {name}: {exc}")
            return
        try:
            log = tracking_importer.import_log_from_bytes(
                self.env, data, name,
                source='gdrive',
                source_gdrive_file_id=file_id,
            )
        except Exception as exc:  # noqa: BLE001 — import isolation; record + skip
            self._record_gdrive_health_error(
                f"import_log_from_bytes failed for {name}: {exc}")
            return

        if log.state in ('ok', 'warning'):
            try:
                client.move_file(file_id, self.gdrive_archive_folder_id)
            except Exception as exc:  # noqa: BLE001 — archive is best-effort
                _logger.warning(
                    "Archive move failed for %s: %s", name, exc)
            self.last_success_poll_at = fields.Datetime.now()
        else:
            # state == 'error' — leave file in inbox; write best-effort marker
            self._write_error_marker(client, name, log)

    def _write_error_marker(self, client, name: str, log):
        """Write `<filename>.error.txt` next to the failed file (best-effort)."""
        self.ensure_one()
        body = (f"Import {log.name} failed: "
                f"errors={log.error_count}, state={log.state}")
        try:
            client.upload_text(
                self.gdrive_inbox_folder_id,
                f"{name}.error.txt",
                body,
            )
        except Exception as exc:  # noqa: BLE001 — marker is best-effort
            _logger.warning(
                "Error marker upload failed for %s: %s", name, exc)

    def _record_gdrive_health_error(self, message: str):
        """Probe etsy.sync.health and record a gdrive_integration error event."""
        self.ensure_one()
        health = self.env.get('etsy.sync.health')
        if health is None:
            return
        helper = getattr(health.sudo(), '_record_event', None)
        if helper is None:
            return
        try:
            helper(
                kind='gdrive_integration',
                ok_count=0, warning_count=0, error_count=1,
                notes=f"[{self.code}] {message}"[:4096],
            )
        except Exception:  # noqa: BLE001 — audit must not abort poll
            _logger.warning(
                "gdrive_integration sync.health write failed", exc_info=True)
