"""multichannel.enquiry — pre-sale customer enquiry stub.

Created in slice P3-LEAD-DEDUPE (foundational) so `etsy.message.dedupe` can
declare a Many2one FK to this model. Full schema (state machine, actions,
chatter, ACL surface) lands in slice P3-LEAD-MODEL via classical inheritance
(`_inherit = 'multichannel.enquiry'`).

Per ADR-011: lightweight model on `multichannel_hub_core`, no `crm` dep.
Per data-model.md §1: full field list + state transitions + ACL.
"""

from odoo import fields, models


class MultichannelEnquiry(models.Model):
    _name = 'multichannel.enquiry'
    _description = 'Customer enquiry — pre-sale conversation not yet tied to an order'
    _order = 'id desc'

    name = fields.Char(string='Name', required=True, default='Enquiry')
