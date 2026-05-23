"""Phase 1: verify P0-13 indexes exist after install/upgrade.

- Composite index on sale_order (etsy_shop_id, etsy_last_modified DESC) for
  the OrderSyncer "since" cursor and dashboards filtering on shop + recency.
- tracking_number is index=True on sale.order.fulfillment from P1-05; this
  test pins it so a future refactor doesn't drop the property.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1P013IndexesDB(TransactionCase):

    def test_composite_etsy_shop_last_modified_index_exists(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'sale_order'
              AND indexname = 'sale_order_etsy_shop_last_modified_idx'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "composite (etsy_shop_id, etsy_last_modified DESC) index must exist",
        )

    def test_composite_index_is_descending(self):
        """The index definition must include DESC on etsy_last_modified."""
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'sale_order'
              AND indexname = 'sale_order_etsy_shop_last_modified_idx'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row)
        self.assertIn('DESC', row[0],
                       "index must order etsy_last_modified DESC")

    def test_tracking_number_index_preserved(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'sale_order_fulfillment'
              AND indexdef LIKE '%tracking_number%'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "tracking_number index on sale_order_fulfillment must remain (from P1-05)",
        )
