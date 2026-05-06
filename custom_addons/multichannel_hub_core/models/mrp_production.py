"""mrp.production extension — sync linked sale.order pipeline state at MO boundaries.

P1-MTO-SYNC: when an MO transitions to 'confirmed' or 'done', advance the
linked SO's order.pipeline.state at lifecycle boundaries. Mid-stage transitions
on the SO pipeline (CHỜ DUYỆT, ĐÃ GỬI PROOF, etc.) remain manual — mrp.production's
6-state model cannot represent them.

Sync semantics:
- MO state transitions to 'confirmed' → SO advances to 'pending_file' (CHỜ FILE)
- All MOs on a SO transition to a terminal MO state ('done' or 'cancel') →
  SO advances to 'done' (VN-Fulfilled)
- Forward-only: state regressions (e.g., done → confirmed via direct write)
  do NOT roll back the SO pipeline
- Per FR-017 defense-in-depth, sync calls go through
  sale.order._write_pipeline_state(...) with change_type='automatic';
  direct x_pipeline_state_id writes are forbidden

See:
- Tracker P1-MTO-SYNC entry in `.claude/plans/006-master-plan-tracking.md`
- ADR-010 §"Amendment 2026-05-03" — hybrid Dropship + MTO architecture
- memory `feedback_fr017_write_defense_in_depth.md`
"""
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)

# Codes on order.pipeline.state we sync to from MO boundaries
# (per VN internal production seed in data/order_pipeline_seed.xml).
PIPELINE_INITIAL_CODE = 'pending_file'   # CHỜ FILE
PIPELINE_TERMINAL_CODE = 'done'          # VN-Fulfilled (is_terminal=True)

# mrp.production state values
MO_STATE_CONFIRMED = 'confirmed'
MO_STATE_DONE = 'done'
MO_TERMINAL_STATES = ('done', 'cancel')


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def write(self, vals):
        """Boundary-only forward sync to linked SO pipeline state.

        Detects state transitions where the new state matches a sync boundary
        and the old state did not. Forward-only — regressions are no-ops.
        Sync hooks fire AFTER the underlying write lands so subsequent reads
        observe the post-transition state.
        """
        new_state = vals.get('state')
        if not new_state:
            return super().write(vals)

        # Snapshot transitions per record before super(); state may differ
        # across the recordset.
        to_confirmed = self.filtered(
            lambda mo: mo.state != MO_STATE_CONFIRMED
            and new_state == MO_STATE_CONFIRMED
        )
        to_done = self.filtered(
            lambda mo: mo.state != MO_STATE_DONE
            and new_state == MO_STATE_DONE
        )

        result = super().write(vals)

        for mo in to_confirmed:
            mo._sync_so_pipeline_on_confirmed()
        for mo in to_done:
            mo._sync_so_pipeline_on_done()

        return result

    def _linked_sale_order(self):
        """Walk MO → SO via origin text (MTO procurement populates MO.origin
        with the SO name).

        In Odoo 19 `mrp.production` exposes `production_group_id` (an MRP
        sibling group), not a direct procurement_group_id, so we cannot walk
        sale_ids through a group field. The MTO route always stamps `origin`
        with the SO name; sibling MOs on the same SO share the same origin.
        """
        self.ensure_one()
        if not self.origin:
            return self.env['sale.order']
        return self.env['sale.order'].search(
            [('name', '=', self.origin)], limit=1)

    def _sync_so_pipeline_on_confirmed(self):
        """MO confirmed → advance linked SO to PIPELINE_INITIAL_CODE.

        Idempotent (sequence-compared, forward-only). Calls
        _write_pipeline_state with change_type='automatic' so the
        terminal-stage guard is bypassed for sync paths.
        """
        self.ensure_one()
        so = self._linked_sale_order()
        if not so:
            return
        target = so.x_pipeline_id.state_ids.filtered(
            lambda s: s.code == PIPELINE_INITIAL_CODE)[:1]
        if not target:
            _logger.debug(
                "Pipeline '%s' has no state code='%s'; skipping initial sync",
                so.x_pipeline_id.code, PIPELINE_INITIAL_CODE)
            return
        current = so.x_pipeline_state_id
        if current and current.sequence >= target.sequence:
            return
        so._write_pipeline_state(
            target, change_type='automatic',
            note=_('Auto-sync: MO %s confirmed', self.name))

    def _sync_so_pipeline_on_done(self):
        """All MOs on the SO done → advance SO to PIPELINE_TERMINAL_CODE.

        Boundary semantics: SO advances to terminal only when EVERY MO on the
        SO's procurement group is in a terminal MO state ('done' or 'cancel').
        A single MO finishing does not advance the SO if siblings remain in
        progress.

        Forward-only and idempotent.
        """
        self.ensure_one()
        so = self._linked_sale_order()
        if not so:
            return
        siblings = self._sibling_productions_for_so(so)
        if not siblings or any(mo.state not in MO_TERMINAL_STATES for mo in siblings):
            return
        target = so.x_pipeline_id.state_ids.filtered(
            lambda s: s.code == PIPELINE_TERMINAL_CODE)[:1]
        if not target:
            _logger.debug(
                "Pipeline '%s' has no state code='%s'; skipping terminal sync",
                so.x_pipeline_id.code, PIPELINE_TERMINAL_CODE)
            return
        current = so.x_pipeline_state_id
        if current and current.sequence >= target.sequence:
            return
        so._write_pipeline_state(
            target, change_type='automatic',
            note=_('Auto-sync: all linked MOs done'))

    def _sibling_productions_for_so(self, so):
        """All mrp.production records linked to a given SO via origin match."""
        return self.env['mrp.production'].search(
            [('origin', '=', so.name)])
