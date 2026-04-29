"""ir.attachment — 10 MB hard cap on writes for restricted models.

Per ADR-006 §2 / FR-019. Defence in depth alongside the @api.constrains
on design.file: this layer catches direct ir.attachment writes (chatter
uploads, REST API, manual XML-RPC) that bypass the design.file model.

Restricted set is a static string set so it works even when
tracking.import.line (P2-01) hasn't been added yet — no env[...] lookup,
no install-order coupling.
"""
import base64
import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_LARGE_FILE_THRESHOLD_BYTES = 10 * 1024 * 1024
_RESTRICTED_RES_MODELS = frozenset({
    'design.file',
    'sale.order',
    'tracking.import.line',  # exists once P2-01 lands; harmless in the meantime
})


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        threshold = self._mhc_size_threshold()
        for vals in vals_list:
            res_model = vals.get('res_model')
            if res_model not in _RESTRICTED_RES_MODELS:
                continue
            datas = vals.get('datas')
            if not datas:
                continue
            actual_size = self._mhc_decoded_size(datas)
            if actual_size > threshold:
                raise ValidationError(_(
                    "Attachment '%(name)s' (%(size).1f MB) exceeds the "
                    "%(threshold).1f MB limit on %(model)s. Use URL mode or "
                    "upload to Drive/S3 and paste the link instead.",
                    name=vals.get('name', '?'),
                    size=actual_size / 1024 / 1024,
                    threshold=threshold / 1024 / 1024,
                    model=res_model,
                ))
        return super().create(vals_list)

    @api.model
    def _mhc_size_threshold(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.large_file_threshold_bytes',
            str(_DEFAULT_LARGE_FILE_THRESHOLD_BYTES),
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            _logger.warning(
                "multichannel_hub.large_file_threshold_bytes=%r not an int; "
                "falling back to %s",
                param, _DEFAULT_LARGE_FILE_THRESHOLD_BYTES,
            )
            return _DEFAULT_LARGE_FILE_THRESHOLD_BYTES

    @staticmethod
    def _mhc_decoded_size(value):
        try:
            return len(base64.b64decode(value))
        except (TypeError, ValueError, base64.binascii.Error):
            return len(value or b'')
