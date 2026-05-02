"""sale.order extension — wire Gearment-POD pipeline transitions to the
`gearment_adapter.push_order` call site (memory #64: every adapter
must have a named caller).

Per ADR-003, this extension lives in mhf because Gearment is a
fulfillment partner and must not pollute mhc.

Behavior:
- When `_write_pipeline_state` flips a sale.order to `gearment_pod /
  confirmed` AND `x_gearment_outbound_ref` is empty AND the kill-switch
  ICP is on → enqueue (or run synchronously inside a savepoint) a push
  call to Gearment.
- Success: stamp `x_gearment_outbound_ref` + `x_gearment_pushed_at` +
  `x_gearment_status='pending'`. Pipeline stays at `confirmed` waiting
  for the P0-18b2 webhook to advance to `shipped`.
- Failure: roll the pipeline back to `quoted` via _write_pipeline_state
  (change_type='rollback'); chatter the error; status='failed'.

Cron `_cron_retry_stalled_gearment_pushes` re-enqueues confirmed
orders that lost their push attempt for >24h.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from ..services import gearment_adapter, gearment_payload_builder

_logger = logging.getLogger(__name__)

_ICP_KILLSWITCH = 'multichannel_hub_fulfillment.gearment_auto_push_enabled'
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
    # Pipeline transition hook
    # ------------------------------------------------------------------
    def _write_pipeline_state(self, new_state, note=None,
                              change_type='manual'):
        """Extend mhc helper: after the standard transition, fire the
        Gearment auto-push when entering the gearment_pod 'confirmed'
        state for the first time.
        """
        super()._write_pipeline_state(new_state, note=note, change_type=change_type)
        for order in self:
            if order._gearment_push_should_fire(new_state):
                order._enqueue_gearment_push()

    def _gearment_push_should_fire(self, new_state) -> bool:
        self.ensure_one()
        if not new_state:
            return False
        if new_state.code != 'confirmed':
            return False
        if not new_state.pipeline_id or new_state.pipeline_id.code != 'gearment_pod':
            return False
        if self.x_gearment_outbound_ref:
            return False  # idempotent — already pushed.
        flag = self.env['ir.config_parameter'].sudo().get_param(
            _ICP_KILLSWITCH, 'True')
        if str(flag).strip().lower() in ('false', '0', ''):
            return False
        return True

    def _enqueue_gearment_push(self):
        """Run the push asynchronously if queue_job is installed,
        else inside a savepoint so a failure does not abort the
        caller's transaction.
        """
        self.ensure_one()
        if hasattr(self, 'with_delay'):
            try:
                self.with_delay(
                    description=f"Gearment push {self.name}",
                ).action_push_to_gearment()
                return
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "with_delay failed; falling back to synchronous push",
                    exc_info=True)
        try:
            with self.env.cr.savepoint():
                self.action_push_to_gearment()
        except Exception:  # noqa: BLE001 — must not abort the outer txn
            _logger.exception("Gearment auto-push synchronous fallback failed")

    # ------------------------------------------------------------------
    # Push action (called by hook + cron + manual)
    # ------------------------------------------------------------------
    def action_push_to_gearment(self):
        """Push the order to Gearment via the P0-18b1 adapter.

        Idempotent: skips orders that already carry an outbound ref.
        """
        adapter_cls = gearment_adapter.GearmentApiAdapter
        for order in self:
            if order.x_gearment_outbound_ref:
                _logger.info(
                    "Skipping Gearment push for %s — already pushed (%s)",
                    order.name, order.x_gearment_outbound_ref)
                continue
            files = order._all_design_files().filtered(
                lambda f: f.state in _ACCEPTABLE_DESIGN_STATES)
            payload = gearment_payload_builder.build_payload(order, files)
            try:
                adapter = adapter_cls(env=order.env)
                response = adapter.push_order(payload)
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
            except Exception as exc:  # noqa: BLE001 — boundary
                _logger.warning(
                    "Gearment push failed for order %s: %s",
                    order.name, exc, exc_info=True)
                order.write({'x_gearment_status': 'failed'})
                order.message_post(body=_(
                    "Gearment push failed: %s. Pipeline rolled back to "
                    "Quoted; please review and retry.",
                    str(exc)[:512]))
                quoted = order.x_pipeline_id.state_ids.filtered(
                    lambda s: s.code == 'quoted')[:1]
                if quoted:
                    super(SaleOrder, order)._write_pipeline_state(
                        quoted,
                        note=f"auto-push failed: {str(exc)[:240]}",
                        change_type='rollback',
                    )

    # ------------------------------------------------------------------
    # Cron: retry stalled
    # ------------------------------------------------------------------
    @api.model
    def _cron_retry_stalled_gearment_pushes(self):
        """Find gearment_pod orders stuck at confirmed without a ref
        for >24h and retry the push."""
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        # Use date_order (operator-set) rather than write_date (bumped by
        # any field write incl. our own state move) so a confirmed order
        # gets retried even if some other field was touched recently.
        domain = [
            ('x_pipeline_id.code', '=', 'gearment_pod'),
            ('x_pipeline_state_id.code', '=', 'confirmed'),
            ('x_gearment_outbound_ref', '=', False),
            ('date_order', '<', cutoff),
        ]
        stalled = self.search(domain, limit=100)
        if not stalled:
            return
        _logger.warning(
            "Retrying %s stalled Gearment pushes", len(stalled))
        for order in stalled:
            order._enqueue_gearment_push()
