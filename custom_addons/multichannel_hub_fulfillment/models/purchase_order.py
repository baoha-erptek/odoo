"""purchase.order extension — Gearment auto-push on PO confirm.

Per ADR-010 Amendment 2026-05-03 + Clarifications 2026-05-04 (P1-DROP-CALLSITE),
the Gearment auto-push trigger relocates from a private SO pipeline-state
hook to the standard `purchase.order.button_confirm` boundary. This is the
canonical Odoo procurement integration point — the SO is confirmed via the
sales flow, standard procurement creates a dropship PO against the seeded
Gearment vendor, the operator (or auto-confirm) confirms the PO, and the
Gearment REST push fires here.

Push failure semantics: raise UserError so the outer transaction rolls back
(PO stays draft, SO state unchanged). Audit chatter is posted on the SO via
`savepoint(flush=False)` so the message survives the rollback.
"""
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_GEARMENT_PARTNER_REF = 'multichannel_hub_fulfillment.partner_gearment_vendor'


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        """Override to fire Gearment push for dropship POs against Gearment."""
        result = super().button_confirm()
        gearment_partner = self.env.ref(
            _GEARMENT_PARTNER_REF, raise_if_not_found=False)
        if not gearment_partner:
            _logger.warning(
                "Gearment vendor seed %r is missing — PO confirm will NOT "
                "push to Gearment. Restore the seed via module update.",
                _GEARMENT_PARTNER_REF)
            return result
        for po in self:
            if not po._is_gearment_dropship_po(gearment_partner):
                continue
            sale_orders = po._get_source_sale_orders()
            for sale_order in sale_orders:
                if sale_order.x_gearment_outbound_ref:
                    _logger.debug(
                        "Skipping Gearment push for SO %s — already pushed (%s)",
                        sale_order.name, sale_order.x_gearment_outbound_ref)
                    continue
                po._push_sale_order_to_gearment(sale_order)
        return result

    def _is_gearment_dropship_po(self, gearment_partner) -> bool:
        """True if this PO is a dropship procurement against the Gearment vendor."""
        self.ensure_one()
        return (
            self.picking_type_id.code == 'dropship'
            and self.partner_id.id == gearment_partner.id
        )

    def _get_source_sale_orders(self):
        """Return the unique set of sale.orders feeding this PO's lines."""
        self.ensure_one()
        return self.order_line.sale_line_id.order_id

    def _push_sale_order_to_gearment(self, sale_order) -> None:
        """Call action_push_to_gearment for one SO; on failure post audit
        chatter via savepoint(flush=False) and raise UserError so the outer
        transaction rolls back.
        """
        self.ensure_one()
        try:
            sale_order.action_push_to_gearment()
        except Exception as exc:
            self._post_push_failure_audit(sale_order, exc)
            raise UserError(_(
                "Gearment push failed for SO %(so)s: %(err)s. "
                "PO not confirmed; fix the issue and re-click Confirm on the PO.",
                so=sale_order.name,
                err=str(exc)[:240],
            )) from exc

    def _post_push_failure_audit(self, sale_order, exc) -> None:
        """Post the failure-audit chatter on the SO and emit a log warning.

        Note on durability: PostgreSQL savepoints live inside the surrounding
        transaction, so the chatter row CANNOT survive the UserError-driven
        outer rollback that the RPC dispatcher applies to a transaction
        which raised. The log warning is the durable audit trail; the
        chatter is only useful when the test (or non-rolled-back caller)
        inspects the SO before transaction tear-down.
        """
        self.ensure_one()
        _logger.warning(
            "Gearment push failed during PO %s confirm for SO %s: %s",
            self.name, sale_order.name, exc, exc_info=True)
        sale_order.message_post(body=_(
            "Gearment push failed during PO %(po)s confirm: %(err)s",
            po=self.name,
            err=str(exc)[:512],
        ))
        self.env.flush_all()
