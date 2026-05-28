"""P2-03: sale.order.fulfillment production-completion hook.

Extends the mhc fulfillment delegation model (defined in
multichannel_hub_core.models.sale_order_fulfillment) with the
"Đã sản xuất" (produced) transition hook per Spec 004a US3 + FR-016..FR-020.

Hook fires when fulfillment_status transitions TO 'produced' from any
non-final state. Creates exactly one stock.move marked
purpose='production_completion'; idempotent via UNIQUE (sale_order_id, purpose);
fail-open on ICP/xmlid misconfiguration (logs to etsy.sync.health, does NOT
block the stage change); raises UserError on attempts to revert from final
states ('shipped'/'delivered'/'cancelled') to 'produced'.

Spec drift note: spec language predates the mixin landing. References to
"production_stage" / "da_san_xuat" / "warehouse_id" map to the actual code
fields fulfillment_status / 'produced' / warehouse_zone. See findings.md.
"""
import json
import logging

import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Fulfillment_status values that are "final" for production purposes — once
# an order reaches any of these, transitioning back to 'produced' is a
# semantic error (not just a no-op) and must surface to the operator.
_FINAL_FULFILLMENT_STATES = frozenset({'shipped', 'delivered', 'cancelled'})

# ICP key that stores the warehouse-zone → stock-location xmlid mapping.
# Schema: {"<zone>": {"src": "<xmlid>", "dst": "<xmlid>"}, ...}.
_PRODUCTION_LOCATIONS_ICP = 'multichannel_hub_fulfillment.production_locations'


class SaleOrderFulfillment(models.Model):
    _inherit = 'sale.order.fulfillment'

    def write(self, vals):
        """Detect fulfillment_status transition to 'produced' and dispatch hook.

        FR-020: refuse final-state → 'produced' with UserError.
        FR-016/017: fire hook exactly once per transition (idempotency at the
        UNIQUE constraint, not here — race-safe).
        """
        if 'fulfillment_status' in vals and vals['fulfillment_status'] == 'produced':
            blocked = self.filtered(
                lambda r: r.fulfillment_status in _FINAL_FULFILLMENT_STATES
            )
            if blocked:
                raise UserError(_(
                    "Cannot revert fulfillment status to 'produced' from a "
                    "final state. Affected orders are currently in: %s",
                    ', '.join(sorted({r.fulfillment_status for r in blocked})),
                ))

        # Capture pre-write state to detect actual transitions (vs. idempotent
        # writes where status was already 'produced'). Captured BEFORE
        # super().write() mutates the recordset; the post-write loop reads
        # the pre-write snapshot from this dict, not from `record`.
        will_transition_to_produced = (
            vals.get('fulfillment_status') == 'produced'
        )
        pre_state_by_id = (
            {r.id: r.fulfillment_status for r in self}
            if will_transition_to_produced else {}
        )

        result = super().write(vals)

        if will_transition_to_produced:
            for record in self:
                # Only fire hook on records that actually changed state into
                # 'produced'. Re-writes where state was already 'produced'
                # are no-ops at the hook level too — the UNIQUE constraint
                # would catch them, but skipping avoids the spurious INSERT
                # attempt + rollback noise in pg logs.
                if pre_state_by_id.get(record.id) != 'produced':
                    record._action_complete_production()
        return result

    def _action_complete_production(self):
        """Create the production-completion stock.move for one fulfillment.

        FR-016..FR-019:
        - Resolves (src, dst) locations from ICP keyed by warehouse_zone.
        - Computes quantity from storable order lines only.
        - Fails open (logs + skips) on missing/unresolvable config.
        - Returns the created move record, or False on fail-open.
        """
        self.ensure_one()
        order = self.order_id
        if not order:
            self._record_production_health(
                kind='warning', ok=0, warning=1, error=0,
                message=_("Fulfillment %s has no linked order; skipping move.",
                          self.id),
            )
            return False

        # Compute storable lines once. Prefetch product records via mapped()
        # to avoid N+1 reads when checking is_storable on each line. Odoo 19
        # storable = is_storable=True (replaces legacy type='product').
        order.order_line.mapped('product_id')  # prefetch
        storable_lines = [
            line for line in order.order_line
            if line.product_id and line.product_id.is_storable
        ]
        storable_qty = sum(line.product_uom_qty for line in storable_lines)
        if not storable_qty:
            self._record_production_health(
                kind='info', ok=1, warning=0, error=0,
                message=_("No stock move: no storable products on order %s.",
                          order.name),
            )
            return False

        # Resolve locations from ICP keyed by warehouse_zone.
        src_loc, dst_loc = self._resolve_production_locations()
        if not src_loc or not dst_loc:
            self._record_production_health(
                kind='warning', ok=0, warning=1, error=0,
                message=_("Production-locations ICP missing or unresolved for "
                          "zone %s on order %s; transition succeeded but no "
                          "stock.move created.",
                          self.warehouse_zone or '<empty>', order.name),
            )
            return False

        # Representative storable line for product_id + product_uom on the
        # move. stock.move requires a product_id even though we're tracking
        # a virtual production-completion event aggregated across lines.
        first_storable_line = storable_lines[0]

        # Odoo 19: stock.move dropped the `name` field; use
        # description_picking_manual to record the human-readable label.
        move_vals = {
            'description_picking_manual': _(
                "Production Completion: %s", order.name),
            'product_id': first_storable_line.product_id.id,
            'product_uom_qty': storable_qty,
            'product_uom': first_storable_line.product_uom_id.id,
            'location_id': src_loc.id,
            'location_dest_id': dst_loc.id,
            'purpose': 'production_completion',
            'sale_order_id': order.id,
            'origin': order.name,
        }

        # Race-idempotency: catch the UNIQUE constraint violation on
        # (sale_order_id, purpose). Wrap in savepoint so a race-loser does
        # not abort the surrounding transaction.
        # sudo() rationale: the hook is a system-derived effect of a user
        # transition write. Production-team users hold sale.order.fulfillment
        # write ACL but are NOT guaranteed stock.move create ACL (stock.user
        # is a separate group). Bypass scoped to creation of one move with a
        # fixed purpose marker; no user-supplied data flows into the bypass.
        try:
            with self.env.cr.savepoint():
                move = self.env['stock.move'].sudo().create(move_vals)
        except psycopg2.IntegrityError:
            # Another concurrent write won the race. The move exists — this
            # call is the idempotent no-op, not a failure.
            _logger.debug(
                "P2-03 hook: race-idempotent skip for order %s "
                "(purpose='production_completion' already present).",
                order.name,
            )
            return False

        self._record_production_health(
            kind='ok', ok=1, warning=0, error=0,
            message=_("Production stock.move created for order %s: qty=%s.",
                      order.name, storable_qty),
        )
        return move

    def _resolve_production_locations(self):
        """Resolve (src, dst) stock.location records from the production ICP.

        Returns (False, False) on missing/invalid config — caller treats
        this as fail-open per FR-018.
        """
        zone = self.warehouse_zone
        if not zone:
            return False, False
        icp_raw = self.env['ir.config_parameter'].sudo().get_param(
            _PRODUCTION_LOCATIONS_ICP, '{}',
        )
        try:
            mapping = json.loads(icp_raw or '{}')
        except (TypeError, ValueError):
            _logger.warning(
                "P2-03 hook: ICP %s contains invalid JSON; treating as empty.",
                _PRODUCTION_LOCATIONS_ICP,
            )
            return False, False
        zone_cfg = mapping.get(zone) or {}
        src_xmlid = zone_cfg.get('src')
        dst_xmlid = zone_cfg.get('dst')
        if not src_xmlid or not dst_xmlid:
            return False, False
        src = self.env.ref(src_xmlid, raise_if_not_found=False)
        dst = self.env.ref(dst_xmlid, raise_if_not_found=False)
        if not src or not dst:
            return False, False
        return src, dst

    def _record_production_health(self, kind, ok, warning, error, message):
        """Optional sync.health write — etsy.sync.health may be absent.

        Mirrors the optional-discovery pattern in
        services/tracking_importer.py:198 record_sync_health: probe model
        AND target method via getattr — both etsy_integration AND a future
        _record_event helper may be missing without disabling the hook.

        sudo() rationale: cross-module audit write, the production-team
        user holding fulfillment write ACL is not guaranteed to hold
        etsy.sync.health write ACL.
        """
        health_model = self.env.get('etsy.sync.health')
        if health_model is None:
            return
        helper = getattr(health_model.sudo(), '_record_event', None)
        if helper is None:
            return
        try:
            helper(
                name='production_completion',
                kind=kind, ok=ok, warning=warning, error=error,
                message=str(message),
            )
        except Exception:  # noqa: BLE001 — audit failure must not abort hook
            _logger.warning(
                "P2-03 hook: etsy.sync.health._record_event failed",
                exc_info=True,
            )
