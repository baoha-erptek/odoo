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
import json
import logging
from decimal import ROUND_HALF_UP, Decimal

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import gearment_adapter

_logger = logging.getLogger(__name__)

_GEARMENT_PARTNER_REF = 'multichannel_hub_fulfillment.partner_gearment_vendor'


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_gearment_dropship_po = fields.Boolean(
        string='Is Gearment Dropship PO',
        compute='_compute_is_gearment_dropship_po',
        help="True when this PO is a dropship procurement against the Gearment "
             "vendor. Drives the 'Request Gearment Quote' button visibility.",
    )
    x_gearment_quote_breakdown_json = fields.Text(
        string='Gearment Quote Breakdown (JSON)', readonly=True, copy=False,
        help="Audit trail of the last Gearment quote request: per-source-order "
             "totals and the shipping/fees split written onto this PO.",
    )

    @api.depends('picking_type_id.code', 'partner_id')
    def _compute_is_gearment_dropship_po(self):
        gearment_partner = self.env.ref(
            _GEARMENT_PARTNER_REF, raise_if_not_found=False)
        for po in self:
            po.is_gearment_dropship_po = bool(
                gearment_partner
                and po._is_gearment_dropship_po(gearment_partner))

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

    # ------------------------------------------------------------------
    # ESTY-246 — Request Gearment quote (cost) on a dropship PO
    # ------------------------------------------------------------------
    _GEARMENT_FEES_PRODUCT_REF = (
        'multichannel_hub_fulfillment.product_gearment_fees')

    def _check_purchase_or_shipping_or_raise(self):
        """FR-017 defense-in-depth gate for the Gearment quote action.

        Allows purchasing OR BA-shipping operators (or system). Runs BEFORE any
        write, because the action performs sudo() writes on PO lines outside the
        caller's own ACL scope — mirrors
        `gearment_quote_wizard._check_ba_shipping_or_raise`.
        """
        user = self.env.user
        if (user.has_group('purchase.group_purchase_user')
                or user.has_group(
                    'multichannel_hub_fulfillment.group_ba_shipping')
                or user.has_group('base.group_system')):
            return
        raise AccessError(_(
            "Only Purchasing or BA Shipping users can request a Gearment "
            "quote on a purchase order."))

    def action_request_gearment_quote(self):
        """Fetch the Gearment price quote and bind it onto this dropship PO.

        Per source sale order: allocate `order_sub_total` across that SO's
        product lines (`price_unit`) and add one "Gearment shipping & fees"
        line for the remainder (`order_total - order_sub_total`). The PO total
        then equals the Gearment cost, so standard Purchase reporting tracks
        Gearment spend. Re-request overwrites prices and replaces the fee lines.
        """
        self.ensure_one()
        self._check_purchase_or_shipping_or_raise()
        # FR-017: the group gate above is the security boundary. Everything below
        # reads/writes via sudo so BA-shipping users (who lack purchase.order /
        # purchase.order.line write and cross-model sale.order read) can still run
        # the action after passing the gate.
        po = self.sudo()
        gearment_partner = po.env.ref(
            _GEARMENT_PARTNER_REF, raise_if_not_found=False)
        if not gearment_partner or not po._is_gearment_dropship_po(
                gearment_partner):
            raise UserError(_(
                "The Gearment quote is only available on a dropship purchase "
                "order against the Gearment vendor."))
        if po.state not in ('draft', 'sent'):
            raise UserError(_(
                "Request the Gearment quote before confirming the purchase "
                "order (draft / RFQ only)."))
        fees_product = po.env.ref(
            self._GEARMENT_FEES_PRODUCT_REF, raise_if_not_found=False)
        if not fees_product:
            raise UserError(_(
                "The Gearment fees product is not configured. Update the "
                "module to restore the seed."))
        source_sos = po._get_source_sale_orders()
        if not source_sos:
            raise UserError(_(
                "This purchase order has no source sale order lines to quote."))

        old_total = po.amount_total
        is_requote = bool(po.x_gearment_quote_breakdown_json)
        # Replace any prior fee lines so re-request does not stack them.
        po.order_line.filtered(
            lambda line: line.product_id == fees_product).unlink()

        lines_by_so = {}
        for line in po.order_line:
            if line.sale_line_id and line.product_id != fees_product:
                so = line.sale_line_id.order_id
                lines_by_so.setdefault(
                    so, po.env['purchase.order.line'])
                lines_by_so[so] |= line

        adapter = gearment_adapter.GearmentApiAdapter(env=po.env)
        breakdown = {}
        for so in source_sos:
            product_lines = lines_by_so.get(so)
            if not product_lines:
                continue
            reference_id = so.channel_order_ref or so.name
            try:
                quote = adapter.get_quote(reference_id)
            except Exception as exc:
                raise UserError(_(
                    "Gearment quote failed for %(so)s: %(err)s",
                    so=so.name, err=str(exc)[:200])) from exc
            price_map, fees_total = po._allocate_gearment_costs_to_lines(
                quote, product_lines)
            for line in product_lines:
                line.price_unit = price_map[line.id]
            po._create_gearment_fees_line(fees_product, fees_total, so)
            breakdown[so.name] = {
                'reference_id': reference_id,
                'order_sub_total': str(quote.get('order_sub_total')),
                'order_total': str(quote.get('order_total')),
                'fees_total': f"{fees_total:.2f}",
                'currency': quote.get('currency', ''),
            }

        po.x_gearment_quote_breakdown_json = json.dumps(breakdown)
        new_total = po.amount_total
        if is_requote:
            po.message_post(body=_(
                "Gearment quote updated: %(old).2f -> %(new).2f.",
                old=old_total, new=new_total))
        else:
            po.message_post(body=_(
                "Gearment quote fetched: total %(new).2f.", new=new_total))
        return True

    def _allocate_gearment_costs_to_lines(self, quote, product_lines):
        """Allocate one order-level Gearment quote across a SO's product lines.

        Returns ``(price_map, fees_total)`` where ``price_map`` maps
        ``purchase.order.line`` id -> new ``price_unit`` (item cost only) and
        ``fees_total`` is ``order_total - order_sub_total`` for the fees line.

        ``order_sub_total`` is split proportionally to each line's current
        subtotal (falling back to quantity when all are zero). The rounding
        residual is placed on the largest line so the summed item cost equals
        ``order_sub_total`` exactly and the PO total matches ``order_total``.
        """
        sub_total = Decimal(str(quote.get('order_sub_total') or '0'))
        order_total = Decimal(str(quote.get('order_total') or '0'))
        fees_total = order_total - sub_total

        lines = list(product_lines)
        weights = [Decimal(str(line.price_subtotal or 0)) for line in lines]
        if sum(weights) <= 0:
            weights = [Decimal(str(line.product_qty or 0)) for line in lines]
        weight_sum = sum(weights) or Decimal('1')

        cents = Decimal('0.01')
        extended = [
            (sub_total * weight / weight_sum).quantize(cents, ROUND_HALF_UP)
            for weight in weights
        ]
        if lines:
            residual = sub_total - sum(extended)
            largest = max(range(len(lines)), key=lambda i: weights[i])
            extended[largest] += residual

        price_map = {}
        for line, ext in zip(lines, extended):
            qty = Decimal(str(line.product_qty or 1))
            price_map[line.id] = float(
                (ext / qty).quantize(Decimal('0.0001'), ROUND_HALF_UP))
        return price_map, float(fees_total)

    def _create_gearment_fees_line(self, fees_product, fees_total, sale_order):
        """Create the per-SO 'Gearment shipping & fees' PO line (qty 1)."""
        self.ensure_one()
        self.env['purchase.order.line'].create({
            'order_id': self.id,
            'product_id': fees_product.id,
            'product_qty': 1.0,
            'product_uom_id': fees_product.uom_id.id,
            'name': _("Gearment shipping & fees (%s)", sale_order.name),
            'price_unit': float(fees_total),
            'date_planned': fields.Datetime.now(),
        })
