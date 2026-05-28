"""gearment.quote.wizard — operator-facing modal for the Gearment confirm step.

Phase C of P4-01. The wizard surfaces the price quote returned by
`adapter.get_quote()` (stored on `sale.order.x_gearment_quote_*` fields,
decision E2.a) and gates the actual `adapter.confirm()` call behind:

  1. State guard (E3): order must be in `operator_review` — anything past
     that means another operator already confirmed; raise to fail clean.
  2. Expiry guard (E4): `x_gearment_quote_expires_at` must be in the future,
     otherwise the operator must fetch a fresh quote.
  3. FR-017 11th confirmation: only `group_ba_shipping` (or system) users
     can fire `action_confirm` — the gate runs BEFORE any sudo() write.

`action_cancel` rolls the order back to `cancelled` and clears
`x_gearment_outbound_ref` so a fresh push is possible.

Reference: `specs/004-fulfillment-routing/p4-01-c-plan.md` §1 (E1-E5).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class GearmentQuoteWizard(models.TransientModel):
    _name = 'gearment.quote.wizard'
    _description = 'Gearment Quote Confirmation Wizard (P4-01-C)'

    order_id = fields.Many2one(
        'sale.order', string='Order', required=True, readonly=True,
        ondelete='cascade',
    )
    # Read-through mirrors so the form view doesn't have to pierce the M2O.
    quote_total = fields.Float(
        related='order_id.x_gearment_quote_total', string='Quote Total',
        readonly=True,
    )
    quote_currency = fields.Char(
        related='order_id.x_gearment_quote_currency',
        string='Currency', readonly=True,
    )
    quote_expires_at = fields.Datetime(
        related='order_id.x_gearment_quote_expires_at',
        string='Expires At', readonly=True,
    )
    quote_breakdown_json = fields.Text(
        related='order_id.x_gearment_quote_breakdown_json',
        string='Breakdown (JSON)', readonly=True,
    )

    # ------------------------------------------------------------------
    # FR-017 — defense-in-depth gate
    # ------------------------------------------------------------------
    def _check_ba_shipping_or_raise(self):
        """FR-017 (11th confirmation): wizard `action_confirm` must verify
        the user belongs to `group_ba_shipping` BEFORE any sudo() write.

        Mirrors `multichannel_hub_fulfillment.models.tracking_import_line.
        _check_ba_shipping_or_raise`. ACL CSV alone is insufficient because
        the wizard performs sudo() writes on `sale.order` fields outside the
        wizard model's own table — see `feedback_fr017_write_defense_in_depth`.
        """
        user = self.env.user
        if (user.has_group('multichannel_hub_fulfillment.group_ba_shipping')
                or user.has_group('base.group_system')):
            return
        raise AccessError(_(
            "Only BA Shipping operators can confirm a Gearment quote."
        ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Confirm the quote → call Gearment, advance to `confirmed`.

        Order of guards is load-bearing:
          1. _check_ba_shipping_or_raise (FR-017)
          2. state == 'operator_review' (E3 double-click defense)
          3. expires_at > now() (E4)
          4. adapter.confirm()
          5. write `confirmed` + chatter
        """
        self.ensure_one()
        self._check_ba_shipping_or_raise()
        order = self.order_id
        if order.x_gearment_outbound_state != 'operator_review':
            raise UserError(_(
                "Order %(name)s is in state '%(state)s', not "
                "'operator_review'. Refresh the wizard.",
                name=order.name,
                state=order.x_gearment_outbound_state or 'draft',
            ))
        now = fields.Datetime.now()
        if (order.x_gearment_quote_expires_at
                and order.x_gearment_quote_expires_at < now):
            raise UserError(_(
                "Quote for %(name)s expired at %(exp)s. Fetch a new quote.",
                name=order.name, exp=order.x_gearment_quote_expires_at,
            ))
        # Late import dodges the "import-time circular" trap when the
        # wizard module loads before the services package is fully
        # initialised — pattern reused from action_push_to_gearment.
        from ..services import gearment_adapter
        adapter = gearment_adapter.GearmentApiAdapter(env=self.env)
        reference_id = order.channel_order_ref or order.name
        response = adapter.confirm(reference_id)
        order.sudo()._advance_gearment_state('confirmed')
        order.message_post(body=_(
            "Gearment quote confirmed (response status: %s).",
            (response or {}).get('status') or 'ok',
        ))
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """Roll order back to `cancelled` + clear outbound_ref so re-push
        is possible. FR-017 still applies — only BA Shipping can cancel
        (cancellation has the same blast radius as confirm)."""
        self.ensure_one()
        self._check_ba_shipping_or_raise()
        order = self.order_id
        order.sudo().write({
            'x_gearment_outbound_state': 'cancelled',
            'x_gearment_outbound_ref': False,
        })
        order.message_post(body=_(
            "Gearment quote cancelled by operator. Outbound ref cleared."
        ))
        return {'type': 'ir.actions.act_window_close'}
