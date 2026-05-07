"""multichannel.enquiry.close.wizard — TransientModel for capturing close reason + notes.

Per spec 007 tasks T042 + T046. Calls the host enquiry's action_close(reason)
then appends `notes` to chatter as a separate message_post so the audit
trail keeps the close-action chatter and the operator's free-form note as
distinct entries.
"""

import logging

from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_CLOSED_REASON_SELECTION = [
    ('no_response', 'No Response'),
    ('not_interested', 'Not Interested'),
    ('spam', 'Spam'),
    ('duplicate', 'Duplicate'),
    ('other', 'Other'),
]


class MultichannelEnquiryCloseWizard(models.TransientModel):
    _name = 'multichannel.enquiry.close.wizard'
    _description = 'Close Enquiry Wizard'

    enquiry_id = fields.Many2one(
        'multichannel.enquiry', string='Enquiry',
        required=True, ondelete='cascade',
    )
    reason = fields.Selection(
        _CLOSED_REASON_SELECTION, string='Close Reason', required=True,
    )
    notes = fields.Text(string='Notes')

    def action_close(self):
        """Delegate to enquiry.action_close(reason); append notes to chatter."""
        self.ensure_one()
        if not self.enquiry_id:
            raise UserError(_("No enquiry selected."))
        self.enquiry_id.action_close(reason=self.reason)
        if self.notes:
            # Security: escape user-controlled notes before posting to chatter
            # to prevent HTML/JS injection (security-reviewer HIGH 2026-05-07).
            safe_notes = Markup("<p>{}</p>").format(escape(self.notes))
            self.enquiry_id.message_post(
                body=Markup(_("Close notes: ")) + safe_notes,
            )
        return {'type': 'ir.actions.act_window_close'}
