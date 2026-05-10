"""sale.order.line extension — bulk Gearment sync action (P4-01-D).

The Operations Dashboard (P1-01b) lists `sale.order.line` records — the
operator selects N lines (any orders, any label_status) and clicks
**Sync to Gearment** (D3 server action). This module owns the bulk
fan-out method:

    1. Dedupe parent orders via `mapped('order_id')`
    2. FR-017 12th confirmation: gate on `group_ba_shipping`
    3. Per-order `cr.savepoint(flush=True)` so one failure doesn't roll
       back the whole batch
    4. `bus.bus._sendone` progress notification per unique order
    5. Final summary bus notification (chatter ping deferred — operator
       UI consumes the bus channel directly).

Reference: `specs/004-fulfillment-routing/p4-01-d-plan.md` §1 (DD1.a /
DD3.c) and `feedback_fr017_write_defense_in_depth.md` (12th confirmation).
"""
import logging
from html import escape

from odoo import _, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ------------------------------------------------------------------
    # FR-017 12th confirmation — gate
    # ------------------------------------------------------------------
    def _check_ba_shipping_or_raise(self):
        """Mirrors `gearment.quote.wizard._check_ba_shipping_or_raise`
        (11th confirmation). The bulk-action server action is bound to
        the Operations Dashboard list view and dispatches to this method;
        the gate runs BEFORE any sudo() write.
        """
        user = self.env.user
        if (user.has_group('multichannel_hub_fulfillment.group_ba_shipping')
                or user.has_group('base.group_system')):
            return
        raise AccessError(_(
            "Only BA Shipping operators can bulk-sync orders to Gearment."
        ))

    # ------------------------------------------------------------------
    # D3 — bulk Gearment sync
    # ------------------------------------------------------------------
    def action_gearment_bulk_sync(self):
        """Sync the parent orders of the selected lines to Gearment.

        - Dedupes via `mapped('order_id')` so a multi-line selection on a
          single order calls `action_get_gearment_quote()` ONCE, not once
          per line.
        - Per-order savepoint (DD3.c): if order N fails, orders 1..N-1
          stay quoted and orders N+1.. proceed normally.
        - Bus notification fires per unique order with status
          (`queued` / `failed`) so the operator sees live progress.
        """
        self._check_ba_shipping_or_raise()
        orders = self.mapped('order_id')
        if not orders:
            return False
        succeeded = self.env['sale.order']
        failed_msgs = []
        Bus = self.env['bus.bus']
        channel = (self.env.cr.dbname, 'res.partner', self.env.user.partner_id.id)
        for order in orders:
            try:
                with self.env.cr.savepoint(flush=True):
                    order.action_get_gearment_quote()
                succeeded |= order
                Bus._sendone(channel, 'gearment.bulk.sync', {
                    'order': order.name,
                    'state': order.x_gearment_outbound_state,
                    'status': 'queued',
                })
            except Exception as exc:  # noqa: BLE001
                # DD3.c — per-order error isolation. Catching everything
                # is intentional: any adapter / network / ORM failure on
                # one order must NOT roll back orders 1..N-1 that already
                # quoted successfully. The savepoint above scopes the
                # rollback. Detailed `exc` in log + bus payload (escaped)
                # surfaces the failure to the operator without breaking
                # the batch.
                _logger.warning(
                    "Bulk Gearment sync failed for %s: %s",
                    order.name, exc,
                )
                failed_msgs.append(f"{order.name}: {exc}")
                Bus._sendone(channel, 'gearment.bulk.sync', {
                    'order': order.name,
                    'state': 'failed',
                    'status': 'failed',
                    # html-escape the exception text in case the upstream
                    # response contains tags that would confuse a JS
                    # consumer of the bus channel.
                    'error': escape(str(exc)),
                })
        # Final summary
        Bus._sendone(channel, 'gearment.bulk.sync', {
            'summary': True,
            'succeeded': len(succeeded),
            'failed': len(failed_msgs),
            'failed_msgs': failed_msgs,
        })
        if failed_msgs:
            _logger.warning(
                "Bulk Gearment sync: %d succeeded, %d failed; failures: %s",
                len(succeeded), len(failed_msgs), failed_msgs,
            )
        return True
