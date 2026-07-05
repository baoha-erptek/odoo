"""Extends product.document to tag original design files (ESTY-250).

Standard-Odoo-First: reuses the core `product.document` file-attachment
model (arbitrary mimetypes, existing ACLs, existing "Documents" smart
button) instead of a new custom model. The Boolean tag lets the new
"Original Design" tab on product.template (see product_template.py
x_original_design_ids) show only files uploaded through that tab, keeping
them distinct from files attached via the generic Documents button.

The size cap below only applies to x_is_original_design=True rows — the
generic Documents button (untagged rows) is left at Odoo's standard
unlimited size, unchanged. ir_attachment.py's module-wide restriction list
is keyed on ir.attachment.res_model, which for product.document rows is
always the owning model ('product.template'), not 'product.document' —
so that mechanism can't target just this tab without also capping every
other product-template attachment. Reuses the same
multichannel_hub.large_file_threshold_bytes config parameter for
consistency with design.file's own cap (see design_file.py).
"""

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_LARGE_FILE_THRESHOLD_BYTES = 10 * 1024 * 1024


class ProductDocument(models.Model):
    _inherit = 'product.document'

    x_is_original_design = fields.Boolean(
        default=False,
        index=True,
        help="Tags this document as an original design file, shown on the "
             "product's 'Original Design' tab. Documents attached via the "
             "standard Documents button are not tagged and stay excluded.",
    )

    @api.constrains('x_is_original_design', 'datas')
    def _check_original_design_size_cap(self):
        """Cap Original Design uploads (ESTY-250); untagged rows unaffected."""
        threshold = self._get_original_design_size_threshold()
        for rec in self:
            if not rec.x_is_original_design or not rec.datas:
                continue
            actual_size = len(base64.b64decode(rec.datas))
            if actual_size > threshold:
                raise ValidationError(_(
                    "Design file '%(name)s' (%(size).1f MB) exceeds the "
                    "%(threshold).1f MB limit.",
                    name=rec.name or '?',
                    size=actual_size / 1024 / 1024,
                    threshold=threshold / 1024 / 1024,
                ))

    def _get_original_design_size_threshold(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.large_file_threshold_bytes',
            str(_DEFAULT_LARGE_FILE_THRESHOLD_BYTES),
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            _logger.warning(
                "multichannel_hub.large_file_threshold_bytes=%r is not an int; "
                "falling back to default %s",
                param, _DEFAULT_LARGE_FILE_THRESHOLD_BYTES,
            )
            return _DEFAULT_LARGE_FILE_THRESHOLD_BYTES
