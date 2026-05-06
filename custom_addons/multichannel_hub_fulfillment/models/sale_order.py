"""sale.order extension — Gearment outbound bookkeeping fields and helpers.

Per ADR-010 Amendment 2026-05-03 + Clarifications 2026-05-04, the auto-push
trigger is the standard `purchase.order.button_confirm` boundary (see
`purchase_order.py`), not a private pipeline-state hook. This module owns:

- The Gearment outbound stamp fields (`x_gearment_outbound_ref`, etc.)
- `action_push_to_gearment` — the actual REST call wrapper, called by the
  PO override on success and by the manual button on the SO form. Raises
  on failure so the caller (PO override) can roll back the transaction.
- `_advance_pipeline_to(code)` — public helper to move the SO pipeline to
  a target state code. Idempotent: no-op if already at-or-after target.
"""
import logging

from odoo import _, api, fields, models

from ..services import gearment_adapter, gearment_payload_builder

_logger = logging.getLogger(__name__)

_ACCEPTABLE_DESIGN_STATES = ('approved', 'proof_sent')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_gearment_outbound_ref = fields.Char(
        string='Gearment Outbound Reference',
        readonly=True,
        index=True,
        copy=False,
        help="Gearment-side ID returned by push_order(). Empty until "
             "the order has been successfully pushed.",
    )
    x_gearment_pushed_at = fields.Datetime(
        string='Gearment Pushed At', readonly=True, copy=False)
    x_gearment_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('in_production', 'In Production'),
            ('shipped', 'Shipped'),
            ('failed', 'Failed'),
        ],
        string='Gearment Status',
        readonly=True, copy=False, tracking=True,
    )

    # ------------------------------------------------------------------
    # Pipeline transition helper
    # ------------------------------------------------------------------
    def _advance_pipeline_to(self, target_code: str) -> None:
        """Move the SO pipeline to the state with the given code.

        Idempotent: no-op if the SO is already at-or-after the target state
        (compared by `sequence`). Always uses the audited `_write_pipeline_state`
        path with `change_type='automatic'`.

        Caller is responsible for transactional context (this method does not
        catch its own ValidationError — let the surrounding savepoint or
        UserError propagation handle it).

        TODO: `_write_pipeline_state` is private to mhc; callers across module
        boundaries currently rely on it. Promote a public `action_advance_pipeline`
        wrapper to mhc and switch this helper over (tracker: P1-PIPELINE-PUBLIC-ADVANCE).
        """
        self.ensure_one()
        if not self.x_pipeline_id:
            return
        target = self.x_pipeline_id.state_ids.filtered(
            lambda s: s.code == target_code)[:1]
        if not target:
            _logger.warning(
                "Pipeline '%s' has no state with code='%s'; skipping advance",
                self.x_pipeline_id.code, target_code)
            return
        current = self.x_pipeline_state_id
        if current and current.sequence >= target.sequence:
            return
        self._write_pipeline_state(target, change_type='automatic')

    # ------------------------------------------------------------------
    # Push action (called by PO override + manual button)
    # ------------------------------------------------------------------
    def action_push_to_gearment(self):
        """Push the order to Gearment via the P0-18b1 adapter.

        On success: stamps `x_gearment_outbound_ref` + `x_gearment_pushed_at`
        + `x_gearment_status='pending'`, then advances the pipeline to
        'confirmed'.

        On failure: raises a `UserError` with the underlying error so the
        caller (PO `button_confirm`) can roll the outer transaction back.
        Audit chatter is posted via `savepoint(flush=False)` *by the caller*
        so the message survives the rollback.

        Idempotent at the per-record level: skips records that already carry
        `x_gearment_outbound_ref`.
        """
        adapter_cls = gearment_adapter.GearmentApiAdapter
        for order in self:
            if order.x_gearment_outbound_ref:
                _logger.debug(
                    "Skipping Gearment push for %s — already pushed (%s)",
                    order.name, order.x_gearment_outbound_ref)
                continue
            files = order._all_design_files().filtered(
                lambda f: f.state in _ACCEPTABLE_DESIGN_STATES)
            payload = gearment_payload_builder.build_payload(order, files)
            try:
                adapter = adapter_cls(env=order.env)
                response = adapter.push_order(payload)
            except Exception as exc:
                _logger.warning(
                    "Gearment push failed for order %s: %s",
                    order.name, exc, exc_info=True)
                raise
            ref = (response or {}).get('id') or (response or {}).get('order_id')
            if not ref:
                raise ValueError(_(
                    "Gearment response has no id field: %s", response))
            order.write({
                'x_gearment_outbound_ref': str(ref),
                'x_gearment_pushed_at': fields.Datetime.now(),
                'x_gearment_status': 'pending',
            })
            order.message_post(body=_(
                "Order pushed to Gearment (ref %s).", ref))
            order._advance_pipeline_to('confirmed')
