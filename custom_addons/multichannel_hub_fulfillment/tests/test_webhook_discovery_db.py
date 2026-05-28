"""P0-18b2a Phase 1 — Database schema verification for webhook discovery.

Tests verify new fields added to gearment.api.log to support webhook discovery:
- `direction` (Selection: outbound/inbound, nullable for backward compat)
- `request_headers` (Text: JSON dict, Authorization scrubbed)
- `request_body` (Text: capped at 4 KB)
- `signature_header_seen` (Char: heuristic capture of signature header name)
- `topic_seen` (Char: extracted from body event/topic or header)
- `source` Selection extended with 'inbound_webhook' value

Uses direct SQL queries via information_schema to verify persistence
and avoid ORM caching/field resolution order gotchas.
"""

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGearmentApiLogWebhookDiscoveryDatabase(TransactionCase):
    """Phase 1: Direct database verification for webhook discovery fields."""

    def test_gearment_api_log_columns_added(self):
        """Verify 5 new columns exist: direction, request_headers, request_body,
        signature_header_seen, topic_seen."""
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'gearment_api_log'
        """)
        existing_columns = {row[0] for row in self.env.cr.fetchall()}

        required_new_columns = {
            'direction',
            'request_headers',
            'request_body',
            'signature_header_seen',
            'topic_seen',
        }

        for col in required_new_columns:
            self.assertIn(
                col,
                existing_columns,
                f"Column '{col}' must exist in gearment_api_log table"
            )

    def test_direction_nullable(self):
        """Verify direction column is nullable for backward compat with
        P0-18b1 outbound rows that have no direction value."""
        self.env.cr.execute("""
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'gearment_api_log'
            AND column_name = 'direction'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "direction column must exist")
        is_nullable = result[0]
        self.assertEqual(
            is_nullable,
            'YES',
            "direction column must be nullable (is_nullable = 'YES')"
        )

    def test_source_selection_inbound_webhook(self):
        """Verify source Selection field has been extended with
        'inbound_webhook' key while preserving original 6 values:
        probe, draft, quote, confirm, callback, health_check."""
        model = self.env['gearment.api.log']
        source_field = model._fields['source']
        selection_values = dict(source_field.selection)

        # Check original 6 values still present
        original_sources = {'probe', 'draft', 'quote', 'confirm', 'callback', 'health_check'}
        actual_keys = set(selection_values.keys())

        for source in original_sources:
            self.assertIn(
                source,
                actual_keys,
                f"Original source '{source}' must still be present"
            )

        # Check new value
        self.assertIn(
            'inbound_webhook',
            actual_keys,
            "Source selection must include new 'inbound_webhook' value"
        )

    def test_existing_outbound_rows_unchanged(self):
        """Verify that existing outbound log rows (created before
        webhook discovery fields) can still be read and direction
        field handles None/False correctly (Odoo Selection NULL idiom)."""
        # Create a log row with only original fields (pre-webhook era)
        model = self.env['gearment.api.log']
        row = model.create({
            'endpoint': 'GET /api/v3/orders',
            'http_status': 200,
            'source': 'probe',
            'request_started_at': fields.Datetime.now(),
            # Do NOT set direction, request_headers, request_body, etc.
        })

        # Verify row persisted
        self.assertIsNotNone(row.id, "Old-style row should persist")

        # Verify read back
        read_row = model.browse(row.id)
        self.assertEqual(read_row.endpoint, 'GET /api/v3/orders')
        self.assertEqual(read_row.source, 'probe')

        # Verify direction is either False or None (Odoo's Selection NULL idiom)
        # Both are acceptable; the assertion is flexible to handle both cases
        self.assertIn(
            read_row.direction,
            (False, None),
            f"direction on old row should be False or None, got {read_row.direction}"
        )
