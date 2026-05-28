"""P2-03: stock.move extension for production-completion idempotency marker.

Adds:
- `purpose` Char (indexed) — semantic marker for hook-generated moves.
- `sale_order_id` Many2one — direct link for fast filter/search by order.
- UNIQUE (sale_order_id, purpose) — prevents duplicate hook output under
  concurrent BA writes; hook catches IntegrityError for race-idempotency.

The UNIQUE drift-mirror in init() follows project_sql_constraints_drift:
PostgreSQL multi-addon installs do not always materialize _sql_constraints,
so we replay the constraint in init() with pg_constraint IF NOT EXISTS pre-check.
"""
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    purpose = fields.Char(
        string='Move Purpose',
        index=True,
        help="Semantic marker identifying which subsystem generated this move. "
             "Used by P2-03 production-completion hook for idempotency: value "
             "'production_completion' is reserved for the fulfillment_status "
             "transition hook.",
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        index=True,
        ondelete='set null',
        help="Direct link to the originating sale.order for hook-generated "
             "moves. Enables fast filter without joining through sale_line_id.",
    )

    _sql_constraints = [
        (
            'stock_move_order_purpose_uniq',
            'UNIQUE(sale_order_id, purpose)',
            'A stock.move with the same purpose already exists for this sale order.',
        ),
    ]

    def init(self):
        """UNIQUE drift mirror — see project_sql_constraints_drift memory.

        _sql_constraints alone is unreliable in multi-addon installs; replay
        with pg_constraint IF NOT EXISTS pre-check (NOT EXCEPTION clause —
        PG raises duplicate_table 42P07 on re-run, not duplicate_object).
        """
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'stock_move_order_purpose_uniq'
                ) THEN
                    ALTER TABLE stock_move
                    ADD CONSTRAINT stock_move_order_purpose_uniq
                    UNIQUE (sale_order_id, purpose);
                END IF;
            END
            $$;
        """)
