"""Phase 1 DB tests for etsy.message.dedupe model.

Tests database-level constraints, indexes, and foreign keys
using direct SQL queries (information_schema, pg_constraint, pg_indexes).

Spec: specs/007-customer-conversations/data-model.md §2
Task: T003
"""

import logging

import psycopg2.errors
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPhase1DbMessageDedupe(TransactionCase):
    """Phase 1: Direct database verification for etsy.message.dedupe."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for the entire test class."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_table_exists(self):
        """Test that etsy_message_dedupe table exists in the database."""
        cr = self.env.cr
        cr.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'etsy_message_dedupe'"
        )
        result = cr.fetchone()
        self.assertIsNotNone(
            result,
            "Table 'etsy_message_dedupe' should exist in the public schema"
        )

    def test_columns_exist_and_types(self):
        """Test that all 10 required columns exist with correct types."""
        cr = self.env.cr
        cr.execute(
            """
            SELECT column_name, data_type, is_nullable, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'etsy_message_dedupe'
            ORDER BY ordinal_position
            """
        )
        columns = {row[0]: row[1:] for row in cr.fetchall()}

        # Verify all required columns exist
        required = [
            'id',  # Odoo primary key
            'etsy_shop_id',
            'etsy_message_id',
            'body_sha256_prefix',
            'channel',
            'posted_at',
            'target_sale_order_id',
            'target_enquiry_id',
            'pending_target_receipt_id',
            'state',
            'payload_excerpt',
        ]
        for col in required:
            self.assertIn(
                col, columns,
                f"Required column '{col}' is missing from etsy_message_dedupe"
            )

        # Verify data types. Odoo 19 uses `integer` (int4) for `id` and
        # Many2one FK columns; Char fields become `character varying`.
        self.assertEqual(columns['id'][0], 'integer',
                         "id should be integer (Odoo 19 default PK)")

        # Many2one FK columns
        self.assertEqual(columns['etsy_shop_id'][0], 'integer',
                         "etsy_shop_id should be integer (Many2one)")
        self.assertEqual(columns['target_sale_order_id'][0], 'integer',
                         "target_sale_order_id should be integer (Many2one)")
        self.assertEqual(columns['target_enquiry_id'][0], 'integer',
                         "target_enquiry_id should be integer (Many2one)")

        # Char fields -> character varying (varchar)
        for char_col in ['etsy_message_id', 'body_sha256_prefix', 'channel',
                         'pending_target_receipt_id', 'state', 'payload_excerpt']:
            self.assertEqual(columns[char_col][0], 'character varying',
                             f"{char_col} should be character varying (Char field)")

        # Datetime -> timestamp without time zone
        self.assertEqual(columns['posted_at'][0], 'timestamp without time zone',
                         "posted_at should be timestamp without time zone (Datetime)")

    def test_unique_constraint_enforced(self):
        """Test that UNIQUE(etsy_shop_id, etsy_message_id) constraint is enforced."""
        cr = self.env.cr

        # Verify constraint exists in pg_constraint
        cr.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conname = 'etsy_message_dedupe_uniq_emd_shop_message_id'
            """
        )
        constraint = cr.fetchone()
        self.assertIsNotNone(
            constraint,
            "UNIQUE constraint 'etsy_message_dedupe_uniq_emd_shop_message_id' "
            "should exist"
        )

        # Create a test shop to get a real shop_id
        shop = self.env['etsy.shop'].create({'name': 'Test Shop'})
        shop_id = shop.id

        # Get the max id for etsy_message_dedupe to ensure we insert beyond it
        cr.execute("SELECT COALESCE(MAX(id), 0) FROM etsy_message_dedupe")
        next_id = cr.fetchone()[0] + 1

        # Insert first row inside a savepoint (cr.commit forbidden in tests).
        # The TransactionCase rollback at tearDown undoes both inserts.
        with cr.savepoint():
            cr.execute(
                """
                INSERT INTO etsy_message_dedupe (
                    id, etsy_shop_id, etsy_message_id, body_sha256_prefix,
                    channel, posted_at, state, payload_excerpt
                )
                VALUES (
                    %s, %s, 'unique_test_msg_001', 'abcd1234',
                    'api', NOW(), 'posted', 'Test message 1'
                )
                """,
                (next_id, shop_id)
            )

        # Second insert with same (shop_id, message_id) → UniqueViolation
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            with cr.savepoint():
                cr.execute(
                    """
                    INSERT INTO etsy_message_dedupe (
                        id, etsy_shop_id, etsy_message_id, body_sha256_prefix,
                        channel, posted_at, state, payload_excerpt
                    )
                    VALUES (
                        %s, %s, 'unique_test_msg_001', 'efgh5678',
                        'email', NOW(), 'posted', 'Test message 2'
                    )
                    """,
                    (next_id + 1, shop_id)
                )

    def test_partial_index_idx_emd_pending_exists(self):
        """Test that partial index idx_emd_pending exists with WHERE state='buffered'."""
        cr = self.env.cr
        cr.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'etsy_message_dedupe'
            AND indexname = 'idx_emd_pending'
            """
        )
        result = cr.fetchone()
        self.assertIsNotNone(
            result,
            "Partial index 'idx_emd_pending' should exist on etsy_message_dedupe"
        )

        # PG normalizes the WHERE clause; format varies across versions.
        # Assert the buffered predicate is present without pinning the cast format.
        index_def = result[0]
        self.assertIn('WHERE', index_def, "Index should be partial (have a WHERE)")
        self.assertIn("'buffered'", index_def,
                      "Index predicate should match state='buffered'")
        self.assertIn('state', index_def,
                      "Index predicate should reference state column")
        self.assertIn(
            'etsy_shop_id',
            index_def,
            "Index should include etsy_shop_id"
        )
        self.assertIn(
            'pending_target_receipt_id',
            index_def,
            "Index should include pending_target_receipt_id"
        )

    def test_foreign_keys(self):
        """Test foreign key constraints on etsy_shop, sale_order, multichannel.enquiry."""
        cr = self.env.cr

        # Query referential_constraints and key_column_usage to verify FKs
        # Per memory feedback_odoo19_test_gotchas.md entry #54:
        # information_schema.referential_constraints lacks table_name/column_name,
        # so JOIN with key_column_usage.
        cr.execute(
            """
            SELECT
                rc.constraint_name,
                kcu.column_name,
                rc.delete_rule,
                ccu.table_name as foreign_table_name
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu
                ON rc.constraint_name = kcu.constraint_name
                AND rc.constraint_schema = kcu.constraint_schema
            JOIN information_schema.constraint_column_usage ccu
                ON rc.unique_constraint_name = ccu.constraint_name
                AND rc.unique_constraint_schema = ccu.constraint_schema
            WHERE kcu.table_name = 'etsy_message_dedupe'
            ORDER BY kcu.column_name
            """
        )
        fks = {row[1]: (row[0], row[2], row[3]) for row in cr.fetchall()}

        # FK on etsy_shop_id -> etsy_shop, ondelete CASCADE
        self.assertIn('etsy_shop_id', fks, "Missing FK for etsy_shop_id")
        fk_constraint, delete_rule, foreign_table = fks['etsy_shop_id']
        self.assertEqual(delete_rule, 'CASCADE',
                         "etsy_shop_id FK should have ondelete='cascade'")
        self.assertEqual(foreign_table, 'etsy_shop',
                         "etsy_shop_id should reference etsy_shop table")

        # FK on target_sale_order_id -> sale_order, ondelete SET NULL
        self.assertIn('target_sale_order_id', fks, "Missing FK for target_sale_order_id")
        fk_constraint, delete_rule, foreign_table = fks['target_sale_order_id']
        self.assertEqual(delete_rule, 'SET NULL',
                         "target_sale_order_id FK should have ondelete='set null'")
        self.assertEqual(foreign_table, 'sale_order',
                         "target_sale_order_id should reference sale_order table")

        # FK on target_enquiry_id -> multichannel_enquiry, ondelete SET NULL
        # Note: multichannel.enquiry model doesn't exist yet (P3-LEAD-MODEL future slice)
        # So we only assert the FK column exists and is nullable (if the table exists at all)
        # If multichannel_enquiry table exists, verify FK; if not, just verify column is nullable
        cr.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'multichannel_enquiry'"
        )
        enquiry_table_exists = cr.fetchone() is not None

        if enquiry_table_exists:
            self.assertIn('target_enquiry_id', fks,
                          "Missing FK for target_enquiry_id")
            fk_constraint, delete_rule, foreign_table = fks['target_enquiry_id']
            self.assertEqual(delete_rule, 'SET NULL',
                             "target_enquiry_id FK should have ondelete='set null'")
            self.assertEqual(foreign_table, 'multichannel_enquiry',
                             "target_enquiry_id should reference multichannel_enquiry table")
        else:
            # Just verify the column is nullable (it will accept NULL when the FK is added later)
            cr.execute(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_name = 'etsy_message_dedupe' AND column_name = 'target_enquiry_id'
                """
            )
            is_nullable = cr.fetchone()[0]
            self.assertEqual(is_nullable, 'YES',
                             "target_enquiry_id should be nullable (for future FK to multichannel.enquiry)")
