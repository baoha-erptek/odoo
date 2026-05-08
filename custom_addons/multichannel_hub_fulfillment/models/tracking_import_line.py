"""tracking.import.line — per-row record of a GKE Excel import.

Per Spec 004a §2. Constraints:
- C-TIL-003: state='matched' requires sale_order_id
- C-TIL-004: state='error' requires error_message

UNIQUE(log_id, source_row_hash) mirrored in init() drift template.
Composite (log_id, state) index for log-detail view.
No mail.thread (high-volume; 500+ rows per import).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class TrackingImportLine(models.Model):
    _name = 'tracking.import.line'
    _description = 'GKE tracking import — line'
    _order = 'log_id, row_number, id'

    log_id = fields.Many2one(
        'tracking.import.log',
        string='Import Log',
        required=True,
        ondelete='cascade',
        index=True,
    )
    row_number = fields.Integer(string='Row Number', default=0)
    source_row_hash = fields.Char(
        string='Source Row Hash',
        size=64,
        required=True,
        index=True,
        help='SHA-256 of `|`-joined raw cell values; idempotency key.',
    )
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('matched', 'Matched'),
            ('unmatched', 'Unmatched'),
            ('conflict', 'Conflict'),
            ('imported', 'Imported'),
            ('error', 'Error'),
        ],
        string='State',
        required=True,
        default='pending',
    )

    raw_order_number = fields.Char(string='Raw Order Number', required=True)
    raw_tracking_number = fields.Char(string='Raw Tracking Number')
    raw_carrier_label = fields.Char(string='Raw Carrier Label')
    raw_shipping_date = fields.Char(string='Raw Shipping Date')
    raw_payload = fields.Text(
        string='Raw Payload (JSON)',
        required=True,
        help='Forensic JSON of all cells for this row.',
    )

    parsed_shipping_date = fields.Date(string='Parsed Shipping Date')

    sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order',
        ondelete='set null', index=True)
    fulfillment_id = fields.Many2one(
        'sale.order.fulfillment', string='Fulfillment',
        ondelete='set null')
    detected_carrier_id = fields.Many2one(
        'shipping.carrier', string='Detected Carrier',
        ondelete='set null',
        help='Populated by P2-02 carrier auto-detector.')
    applied_carrier_id = fields.Many2one(
        'shipping.carrier', string='Applied Carrier',
        ondelete='set null',
        help="Written if order's existing carrier was empty.")

    address_change_flag = fields.Boolean(
        string='Address-Change Flagged', default=False)
    needs_review = fields.Boolean(
        string='Needs Review',
        default=False,
        index=True,
        help="P2-02: True when carrier auto-detection fell back to "
             "`other` or could not match any prefix regex.",
    )
    error_message = fields.Text(string='Error Message')
    notes = fields.Char(string='Notes')

    _sql_constraints = [
        ('tracking_import_line_idempotency_uniq',
         'UNIQUE(log_id, source_row_hash)',
         'Duplicate row detected for the same import (log_id, source_row_hash).'),
    ]

    def init(self):
        """Composite (log_id, state) + UNIQUE drift mirror."""
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS tracking_import_line_log_state_idx
            ON tracking_import_line (log_id, state)
        """)
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'tracking_import_line_idempotency_uniq'
                ) THEN
                    ALTER TABLE tracking_import_line
                    ADD CONSTRAINT tracking_import_line_idempotency_uniq
                    UNIQUE (log_id, source_row_hash);
                END IF;
            END
            $$;
        """)

    @api.constrains('state', 'sale_order_id')
    def _check_matched_requires_order(self):
        """C-TIL-003: state='matched' requires sale_order_id."""
        for line in self:
            if line.state == 'matched' and not line.sale_order_id:
                raise ValidationError(_(
                    "Line on row %(row)s is 'matched' but has no sale order.",
                    row=line.row_number,
                ))

    @api.constrains('state', 'error_message')
    def _check_error_requires_message(self):
        """C-TIL-004: state='error' requires error_message."""
        for line in self:
            if line.state == 'error' and not line.error_message:
                raise ValidationError(_(
                    "Line on row %(row)s is 'error' but has no error_message.",
                    row=line.row_number,
                ))

    # ------------------------------------------------------------------
    # P2-02 — bulk re-detect carrier action.
    # ------------------------------------------------------------------
    def _check_ba_shipping_or_raise(self):
        """FR-017 (8th confirmation): re-detect must be RPC-gated."""
        if not (self.env.user.has_group(
                'multichannel_hub_fulfillment.group_ba_shipping')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_(
                "Only BA Shipping operators can re-detect carriers."))

    def action_re_detect_carriers(self):
        """Re-run carrier auto-detection on the selected lines.

        Updates `detected_carrier_id` + `needs_review` only. **Never**
        writes to `sale.order.fulfillment.shipping_carrier_id` (per
        Spec 004a US2 AC: detection is advisory after manual selection).
        """
        self._check_ba_shipping_or_raise()
        from ..services import carrier_detector
        compiled = carrier_detector._compiled_cache_for(self.env)
        other = carrier_detector._other_carrier(self.env)
        for line in self:
            carrier, needs_review = carrier_detector.detect_carrier(
                self.env, line.raw_tracking_number,
                compiled=compiled, other=other)
            line.write({
                'detected_carrier_id': carrier.id if carrier else False,
                'needs_review': needs_review,
            })
        return True

    # ------------------------------------------------------------------
    # P2-04 — replay + conflict resolution actions.
    # ------------------------------------------------------------------
    def action_replay_line(self):
        """Re-run the import pipeline (resolve → detect → apply) per line.

        Each line is processed in its own savepoint so a failure on one
        line does not abort the others. After all lines are processed,
        the parent log's summary counts are recomputed via
        `_recount_summary`. Skips lines already in `'imported'` terminal
        state.

        FR-017 (13th confirmation): RPC-gated to BA Shipping operators.

        sudo: replay touches sale.order + sale.order.fulfillment for
        data reconciliation; BA Shipping group does not grant Sales/User
        directly. Bypass is bounded — caller is already gated by
        `_check_ba_shipping_or_raise`, and writes are restricted to the
        same fields the original wizard import touches.
        """
        self._check_ba_shipping_or_raise()
        from ..services import (
            tracking_importer, carrier_detector,
        )
        sudo_env = self.env(su=True)
        compiled = carrier_detector._compiled_cache_for(sudo_env)
        other = carrier_detector._other_carrier(sudo_env)

        # Batch resolve the whole recordset first — `resolve_orders` does
        # two bulk searches regardless of input size, so calling it once
        # on N lines is O(2 queries), vs N×2 queries when called per line.
        replayable = self.sudo().filtered(lambda l: l.state != 'imported')
        if replayable:
            tracking_importer.resolve_orders(sudo_env, replayable)

        for line in replayable:
            try:
                with self.env.cr.savepoint():
                    if line.state == 'matched' and line.raw_tracking_number:
                        carrier, needs_review = carrier_detector.detect_carrier(
                            sudo_env, line.raw_tracking_number,
                            compiled=compiled, other=other)
                        line.write({
                            'detected_carrier_id': (
                                carrier.id if carrier else False),
                            'needs_review': needs_review,
                        })
                    if line.state == 'matched':
                        tracking_importer.apply_to_fulfillment(
                            sudo_env, line)
            except Exception as exc:  # noqa: BLE001 — per-row isolation
                # Post-savepoint write: cursor is still valid after rollback;
                # only the DB state inside the `with` block was discarded, so
                # this `line.write` reaches the parent transaction safely.
                line.write({
                    'state': 'error',
                    'error_message': tracking_importer._scrub(str(exc)),
                })

        self.mapped('log_id').sudo()._recount_summary()
        return True

    def action_resolve_conflict(self, selected_order_id):
        """Operator picks one of N candidate orders for a conflict line.

        Writes `sale_order_id` + flips state to `'matched'`. Posts an
        audit message to the **parent log's** chatter (line itself has
        no `mail.thread` by design — high volume).

        FR-017 (13th confirmation): RPC-gated to BA Shipping operators.

        sudo: candidate enumeration reads sale.order; BA Shipping does
        not grant Sales/User. Bypass is bounded — caller is already
        gated by `_check_ba_shipping_or_raise`, only the M2O link is
        written, and the chatter post records the choice for audit.
        """
        self._check_ba_shipping_or_raise()
        self.ensure_one()
        if self.state != 'conflict':
            raise ValidationError(_(
                "Line on row %(row)s is not in 'conflict' state.",
                row=self.row_number,
            ))
        SaleOrder = self.env['sale.order'].sudo()
        selected = SaleOrder.browse(selected_order_id)
        if not selected.exists():
            raise ValidationError(_(
                "Selected order %(id)s does not exist.",
                id=selected_order_id,
            ))
        candidates = SaleOrder.search([
            ('channel_order_ref', '=', self.raw_order_number)
        ])
        candidate_names = ', '.join(candidates.mapped('display_name')) or '—'

        fulfillment = (
            selected.fulfillment_id
            if 'fulfillment_id' in selected._fields
            else False
        )
        vals = {
            'sale_order_id': selected.id,
            'state': 'matched',
        }
        if fulfillment:
            vals['fulfillment_id'] = fulfillment.id
        self.sudo().write(vals)

        self.log_id.sudo().message_post(body=_(
            "Row %(row)s: conflict resolved → %(sel)s "
            "(candidates were: %(c)s)",
            row=self.row_number,
            sel=selected.display_name,
            c=candidate_names,
        ))
        return True
