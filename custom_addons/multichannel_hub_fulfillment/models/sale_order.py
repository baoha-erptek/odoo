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

P4-01-C added the operator-driven Gearment outbound state machine
(`x_gearment_outbound_state`) and the quote handshake. This is distinct
from `x_gearment_status` which is webhook-driven Gearment-side state
(decision E1.b in `specs/004-fulfillment-routing/p4-01-c-plan.md`).
"""
import json
import logging
from datetime import timedelta

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import gearment_adapter, gearment_payload_builder

_logger = logging.getLogger(__name__)

_ACCEPTABLE_DESIGN_STATES = ('approved', 'proof_sent')

# Forward-only ordering for `_advance_gearment_state` — index in this tuple
# is the state's "sequence number." `cancelled` sits at the end so it's
# only reachable via explicit operator action (E3 invariant: no auto-cancel).
_GEARMENT_OUTBOUND_STATE_SEQUENCE = (
    'draft', 'quoted', 'operator_review', 'confirmed', 'cancelled',
)
# Default quote TTL when adapter response doesn't carry an explicit
# expires-at value. Short enough that operator must review today; long
# enough for back-and-forth with BA. Adjust via ICP later if needed.
_GEARMENT_QUOTE_DEFAULT_TTL_MINUTES = 30


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
        help="Gearment-side fulfillment state — webhook-driven (P0-18b2). "
             "See `x_gearment_outbound_state` for the local push lifecycle.",
    )

    # P4-01-C — local outbound push lifecycle. Distinct from x_gearment_status
    # (webhook-driven, Gearment-side). Decision E1.b: keep both; never reuse.
    x_gearment_outbound_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('quoted', 'Quoted'),
            ('operator_review', 'Operator Review'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Gearment Outbound State',
        default='draft', tracking=True, copy=False,
        help="Operator-driven push lifecycle: draft → quoted → "
             "operator_review → confirmed (or cancelled). Distinct from "
             "Gearment Status which reflects upstream fulfillment state.",
    )

    # P4-01-C — quote handshake fields (E2.a: persist on order, not on
    # the transient wizard, so close+reopen reuses the same quote until
    # it expires). All readonly — only `action_get_gearment_quote` writes.
    x_gearment_quote_total = fields.Float(
        string='Gearment Quote Total', readonly=True, copy=False,
        digits=(12, 4),  # nano-precision retained from proto-Money
    )
    x_gearment_quote_currency = fields.Char(
        string='Gearment Quote Currency', readonly=True, copy=False, size=8,
    )
    x_gearment_quote_expires_at = fields.Datetime(
        string='Gearment Quote Expires At', readonly=True, copy=False,
        help="UTC timestamp after which `action_confirm` raises and the "
             "operator must fetch a fresh quote (E4 invariant).",
    )
    x_gearment_quote_breakdown_json = fields.Text(
        string='Gearment Quote Breakdown (JSON)', readonly=True, copy=False,
        help="JSON-serialised dict of decoded Money fields: "
             "{order_sub_total, order_shipping_fee, order_tax, "
             "order_discount, order_handle_fee, order_gift_message_fee, "
             "order_fee, order_total, currency}.",
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
                response = adapter.push_order(payload, sale_order_id=order.id)
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

    # ------------------------------------------------------------------
    # P4-01-C — Gearment outbound state machine + quote handshake
    # ------------------------------------------------------------------
    def _advance_gearment_state(self, target: str) -> None:
        """Forward-only transition on `x_gearment_outbound_state`.

        No-op when the current state is already at-or-past `target` (compared
        by index in `_GEARMENT_OUTBOUND_STATE_SEQUENCE`). The `cancelled`
        terminal sits at the end so it can only be reached via an explicit
        operator action (the wizard's `action_cancel`), never auto-advanced.
        """
        self.ensure_one()
        if target not in _GEARMENT_OUTBOUND_STATE_SEQUENCE:
            raise ValueError(
                f"Unknown Gearment outbound state '{target}'"
            )
        target_idx = _GEARMENT_OUTBOUND_STATE_SEQUENCE.index(target)
        current = self.x_gearment_outbound_state or 'draft'
        current_idx = _GEARMENT_OUTBOUND_STATE_SEQUENCE.index(current)
        if current_idx >= target_idx:
            return
        self.x_gearment_outbound_state = target

    def _has_gearment_eligible_lines(self) -> bool:
        """E5.b — true iff at least one line has a Gearment SKU set."""
        self.ensure_one()
        return any(
            (line.product_id.product_tmpl_id.x_gearment_sku or '').strip()
            for line in self.order_line
        )

    def _check_ba_shipping_or_raise(self):
        """FR-017 13th confirmation — gate on `group_ba_shipping`. Mirrors
        the helper on `gearment.quote.wizard` and `sale.order.line`. Lives
        here because `action_get_gearment_quote` writes to `x_gearment_*`
        fields on the order; without this gate, an RPC user with mere
        sale.order R/W could bypass the form-button's `groups=` UI gate.
        """
        user = self.env.user
        if (user.has_group('multichannel_hub_fulfillment.group_ba_shipping')
                or user.has_group('base.group_system')):
            return
        raise AccessError(_(
            "Only BA Shipping operators can fetch a Gearment quote."
        ))

    @api.model
    def action_gearment_bulk_push_all_pending(self):
        """P4-01b — server-action recovery: bulk-quote ALL eligible
        Gearment-POD orders in `state='sale'` + `x_gearment_outbound_state='draft'`
        that have at least one Gearment-eligible line. Used when the
        background cron is paused and the operator needs a manual catch-up.

        FR-017 13th confirmation — `_check_ba_shipping_or_raise()` runs
        before the search; the per-order quote method gates again on
        each row as defense-in-depth.

        Per-order savepoint isolates failures: a single 4xx on order N
        does not roll back orders 1..N-1 that already quoted. Bus
        notifications fire per order so the operator sees progress.

        Returns a summary dict — used by the wizard form's notification.
        """
        # FR-017 method-top gate (inlined for @api.model classmethod context).
        if not (
            self.env.user.has_group('multichannel_hub_fulfillment.group_ba_shipping')
            or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(_(
                "Only BA Shipping operators can run the bulk Gearment push."
            ))
        candidates = self.search([
            ('state', 'in', ('sale', 'done')),
            ('x_gearment_outbound_state', '=', 'draft'),
        ])
        # Filter to those with Gearment-eligible lines (can't push via
        # SQL; cheap-enough since "draft" pool is bounded).
        eligible = candidates.filtered(lambda o: o._has_gearment_eligible_lines())
        succeeded = self.env['sale.order']
        failed_msgs = []
        Bus = self.env['bus.bus']
        channel = (self.env.cr.dbname, 'res.partner', self.env.user.partner_id.id)
        for order in eligible:
            try:
                with self.env.cr.savepoint(flush=True):
                    order.action_get_gearment_quote()
                succeeded |= order
                Bus._sendone(channel, 'gearment.bulk.push.all', {
                    'order': order.name,
                    'state': order.x_gearment_outbound_state,
                    'status': 'quoted',
                })
            except Exception as exc:  # noqa: BLE001 — per-order isolation
                _logger.warning(
                    "Bulk Gearment push-all failed for %s: %s",
                    order.name, exc,
                )
                failed_msgs.append(f"{order.name}: {exc}")
                Bus._sendone(channel, 'gearment.bulk.push.all', {
                    'order': order.name,
                    'state': 'failed',
                    'status': 'failed',
                    'error': escape(str(exc)),
                })
        Bus._sendone(channel, 'gearment.bulk.push.all', {
            'summary': True,
            'eligible': len(eligible),
            'succeeded': len(succeeded),
            'failed': len(failed_msgs),
            'failed_msgs': failed_msgs,
        })
        return {
            'eligible': len(eligible),
            'succeeded': len(succeeded),
            'failed': len(failed_msgs),
        }

    def action_get_gearment_quote(self):
        """Fetch a price quote from Gearment and store on the order.

        Transitions `x_gearment_outbound_state` draft→quoted on success.
        E5.b guard: refuses if no order line has `x_gearment_sku` set.
        FR-017 13th confirmation: `_check_ba_shipping_or_raise()` runs
        BEFORE any write, so direct RPC by non-shipping users is rejected.
        """
        self.ensure_one()
        self._check_ba_shipping_or_raise()
        if not self._has_gearment_eligible_lines():
            raise UserError(_(
                "No Gearment-eligible lines on this order. Set "
                "`x_gearment_sku` on at least one product before requesting "
                "a quote."
            ))
        adapter = gearment_adapter.GearmentApiAdapter(env=self.env)
        files = self._all_design_files().filtered(
            lambda f: f.state in _ACCEPTABLE_DESIGN_STATES)
        quote_body = gearment_payload_builder.build_quote_body(self, files)
        quote = adapter.get_quote(quote_body)
        # quote dict carries Decimal totals (P4-01-B). Convert to floats for
        # storage on the Float field; keep full precision in JSON breakdown.
        breakdown = {
            k: str(quote[k]) for k in (
                'order_sub_total', 'order_shipping_fee', 'order_tax',
                'order_discount', 'order_handle_fee',
                'order_gift_message_fee', 'order_fee', 'order_total',
            ) if k in quote
        }
        breakdown['currency'] = quote.get('currency', '')
        expires_at = quote.get('expires_at') or (
            fields.Datetime.now()
            + timedelta(minutes=_GEARMENT_QUOTE_DEFAULT_TTL_MINUTES)
        )
        self.write({
            'x_gearment_quote_total': float(quote.get('order_total') or 0.0),
            'x_gearment_quote_currency': quote.get('currency', '') or '',
            'x_gearment_quote_expires_at': expires_at,
            'x_gearment_quote_breakdown_json': json.dumps(breakdown),
        })
        self._advance_gearment_state('quoted')
        self.message_post(body=_(
            "Quote fetched from Gearment (total %(total)s %(cur)s, expires "
            "%(exp)s).",
            total=quote.get('order_total'),
            cur=quote.get('currency', ''),
            exp=expires_at,
        ))

    def action_open_gearment_quote_wizard(self):
        """Move to operator_review and open the wizard modal."""
        self.ensure_one()
        if self.x_gearment_outbound_state == 'quoted':
            self._advance_gearment_state('operator_review')
        wizard = self.env['gearment.quote.wizard'].create({
            'order_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gearment.quote.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
