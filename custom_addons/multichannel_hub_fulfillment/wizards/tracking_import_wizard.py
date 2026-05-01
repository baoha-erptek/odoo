"""tracking.import.wizard — 3-stage operator wizard.

draft → previewed → done

Actions:
- action_preview()        — gated BA-shipping; parses + creates log + lines
- action_approve_schema() — gated BA-MANAGER (FR-017); appends ICP whitelist
- action_import()         — gated BA-shipping; per-row savepoint; writes fulfillment
- action_cancel()         — drops the preview log

Schema-hash whitelist ICP: `multichannel_hub_fulfillment.gke_schema_hashes`
File-size cap ICP:        `multichannel_hub.large_file_threshold_bytes`
"""
from __future__ import annotations

import base64
import json
import logging
import os
from html import escape

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..services import gke_excel_parser, tracking_importer

_logger = logging.getLogger(__name__)

ICP_SCHEMA_HASHES = 'multichannel_hub_fulfillment.gke_schema_hashes'
ICP_FILE_SIZE_CAP = 'multichannel_hub.large_file_threshold_bytes'
ICP_BATCH_SIZE = 'multichannel_hub_fulfillment.import_batch_size'
DEFAULT_FILE_SIZE_CAP = 10 * 1024 * 1024
DEFAULT_BATCH_SIZE = 200


class TrackingImportWizard(models.TransientModel):
    _name = 'tracking.import.wizard'
    _description = 'GKE tracking import wizard'

    excel_file = fields.Binary(
        string='Excel File',
        required=True,
        attachment=False,
    )
    excel_filename = fields.Char(string='Filename', required=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('previewed', 'Previewed'),
         ('done', 'Done')],
        string='Wizard State', required=True, default='draft')
    schema_hash = fields.Char(
        string='Schema Hash', size=64,
        compute='_compute_schema_hash', store=True)
    is_new_schema = fields.Boolean(
        string='New Schema', compute='_compute_schema_hash', store=True)
    header_diff_html = fields.Html(
        string='Header Diff', compute='_compute_schema_hash', store=True,
        sanitize=True)
    preview_log_id = fields.Many2one(
        'tracking.import.log', string='Preview Log',
        ondelete='set null', readonly=True)
    preview_line_ids = fields.One2many(
        related='preview_log_id.line_ids',
        string='Preview Lines',
        readonly=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_ba_shipping_or_raise(self):
        """FR-017: any BA-shipping (or BA-manager via implied_ids) may proceed."""
        if not (self.env.user.has_group(
                'multichannel_hub_fulfillment.group_ba_shipping')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_(
                "Only BA Shipping operators can run the tracking import."))

    def _check_ba_manager_or_raise(self):
        """FR-017: schema approval gated to BA-manager only."""
        if not (self.env.user.has_group(
                'multichannel_hub_fulfillment.group_ba_manager')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_(
                "Only BA Shipping Managers can approve a new schema fingerprint."))

    def _file_size_cap(self) -> int:
        raw = self.env['ir.config_parameter'].sudo().get_param(
            ICP_FILE_SIZE_CAP, str(DEFAULT_FILE_SIZE_CAP))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_FILE_SIZE_CAP

    def _approved_schema_hashes(self) -> list[str]:
        raw = self.env['ir.config_parameter'].sudo().get_param(
            ICP_SCHEMA_HASHES, '[]')
        try:
            return list(json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            _logger.warning(
                "Malformed %s ICP value: %r — treating as empty list",
                ICP_SCHEMA_HASHES, raw)
            return []

    def _decode_file(self) -> bytes:
        """Return the wizard's binary as raw bytes.

        Tests pass raw XLSX bytes directly; the form passes a base64 str.
        Detect XLSX magic ('PK\\x03\\x04') to skip decoding when bytes are
        already raw.
        """
        self.ensure_one()
        data = self.excel_file
        if not data:
            raise ValidationError(_("No Excel file provided."))
        if isinstance(data, bytes) and data[:2] == b'PK':
            return data
        try:
            return base64.b64decode(data)
        except (ValueError, TypeError) as exc:
            raise ValidationError(_(
                "Invalid Excel file binary: %s") % exc) from exc

    def _safe_filename(self) -> str:
        """Sanitize filename to a basename — no path traversal."""
        return os.path.basename(self.excel_filename or 'gke_import.xlsx')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('excel_file', 'excel_filename')
    def _compute_schema_hash(self):
        for wiz in self:
            wiz.schema_hash = False
            wiz.is_new_schema = False
            wiz.header_diff_html = False
            if not wiz.excel_file:
                continue
            try:
                data = wiz.excel_file
                if isinstance(data, bytes) and data[:2] == b'PK':
                    file_bytes = data
                else:
                    file_bytes = base64.b64decode(data)
                result = gke_excel_parser.parse(file_bytes)
            except Exception as exc:  # noqa: BLE001 — preview must not crash form
                _logger.debug("Schema preview parse failed: %s", exc)
                continue
            wiz.schema_hash = result.schema_hash
            wiz.is_new_schema = result.schema_hash not in wiz._approved_schema_hashes()
            wiz.header_diff_html = wiz._render_header_diff(result.headers)

    def _render_header_diff(self, headers) -> str:
        # Operator-supplied header strings → escape before embedding in HTML.
        items = ''.join(
            f'<li>{escape(str(h or ""))}</li>' for h in headers
        )
        return Markup(f'<div class="o_header_diff"><ul>{items}</ul></div>')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_preview(self):
        self.ensure_one()
        self._check_ba_shipping_or_raise()
        file_bytes = self._decode_file()
        size = len(file_bytes)
        cap = self._file_size_cap()
        if size > cap:
            raise ValidationError(_(
                "Uploaded file is %(size)s bytes; cap is %(cap)s bytes.",
                size=size, cap=cap))

        result = gke_excel_parser.parse(file_bytes)

        approved = self._approved_schema_hashes()
        is_new = result.schema_hash not in approved

        Log = self.env['tracking.import.log']
        log = Log.create({
            'filename': self._safe_filename(),
            'file_size_bytes': size,
            'schema_hash': result.schema_hash,
            'header_columns': json.dumps(list(result.headers)),
            'is_new_schema': is_new,
            'state': 'pending',
            'source': 'manual',
            'total_rows': len(result.rows),
        })

        Line = self.env['tracking.import.line']
        payloads = tracking_importer.build_lines_payload(result, log.id)
        if payloads:
            Line.create(payloads)

        # Resolve in same transaction so preview shows match counts.
        counts = tracking_importer.resolve_orders(self.env, log.line_ids)
        log.write({
            'matched_count': counts.get('matched', 0),
            'unmatched_count': counts.get('unmatched', 0),
            'conflict_count': counts.get('conflict', 0),
            'address_change_flagged_count': sum(
                1 for line in log.line_ids if line.address_change_flag),
        })

        self.write({
            'state': 'previewed',
            'preview_log_id': log.id,
        })
        return self._reload_action()

    def action_approve_schema(self):
        self.ensure_one()
        self._check_ba_manager_or_raise()
        if not self.preview_log_id:
            raise ValidationError(_("Run preview before approving the schema."))
        log = self.preview_log_id

        icp = self.env['ir.config_parameter'].sudo()
        approved = self._approved_schema_hashes()
        if log.schema_hash not in approved:
            approved.append(log.schema_hash)
            icp.set_param(ICP_SCHEMA_HASHES, json.dumps(approved))

        # `is_new_schema` is tracked → automatic chatter line via mail.thread.
        log.is_new_schema = False

        tracking_importer.record_sync_health(
            self.env, kind='gke_schema_approved',
            ok=1, warning=0, error=0,
            notes=f"hash={log.schema_hash[:12]}")
        return self._reload_action()

    def action_import(self):
        self.ensure_one()
        self._check_ba_shipping_or_raise()
        if not self.preview_log_id:
            raise ValidationError(_("Run preview before importing."))
        log = self.preview_log_id

        approved = self._approved_schema_hashes()
        if log.schema_hash not in approved:
            raise ValidationError(_(
                "Schema fingerprint not approved. Ask a BA Manager to approve "
                "this header layout before importing."))

        # File-size cap re-check (defense-in-depth; preview already enforced).
        if log.file_size_bytes > self._file_size_cap():
            raise ValidationError(_(
                "File exceeds the configured size cap."))

        log.write({'state': 'processing', 'start_at': fields.Datetime.now()})
        write_counts = tracking_importer.apply_to_fulfillment(
            self.env, log.line_ids)

        imported = write_counts.get('imported', 0)
        errors = write_counts.get('error', 0)
        warnings = log.unmatched_count + log.conflict_count
        if errors:
            new_state = 'error'
        elif warnings:
            new_state = 'warning'
        else:
            new_state = 'ok'

        log.write({
            'imported_count': imported,
            'error_count': errors,
            'finish_at': fields.Datetime.now(),
            'state': new_state,
        })

        tracking_importer.record_sync_health(
            self.env, kind='gke_tracking_import',
            ok=imported, warning=warnings, error=errors,
            notes=f"log={log.name}")

        self.state = 'done'
        return self._reload_action()

    def action_cancel(self):
        self.ensure_one()
        if self.preview_log_id and self.preview_log_id.state == 'pending':
            # sudo: cleanup of the user's own preview log; ACL grants
            # BA-shipping create+write but not unlink (audit-immutability for
            # processed/finalized logs). Bypass bounded to pending preview rows.
            self.preview_log_id.sudo().line_ids.unlink()
            self.preview_log_id.sudo().unlink()
        return {'type': 'ir.actions.act_window_close'}

    def _reload_action(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
