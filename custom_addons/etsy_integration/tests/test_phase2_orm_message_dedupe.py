"""Phase 2 ORM tests for etsy.message.dedupe model.

Tests business logic, constraints, ACL, and cron behavior
via the ORM using TransactionCase.

Spec: specs/007-customer-conversations/data-model.md §2
Task: T004 + T010
"""

import logging
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPhase2OrmMessageDedupe(TransactionCase):
    """Phase 2: ORM behavior, constraints, ACL, and retention for etsy.message.dedupe."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for the entire test class."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a test shop
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Shop for Message Dedupe',
        })

        # Create a test partner (for order creation)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Buyer',
            'email': 'buyer@test.com',
        })

        # Create a test sale order
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'etsy_shop_id': cls.shop.id,
        })

    def _create_message_dedupe(self, **kwargs):
        """Factory method to create etsy.message.dedupe records."""
        defaults = {
            'etsy_shop_id': self.shop.id,
            'etsy_message_id': 'test_msg_' + str(kwargs.get('id', 1)),
            'body_sha256_prefix': 'abcd1234efgh5678',
            'channel': 'api',
            'posted_at': fields.Datetime.now(),
            'state': 'posted',
            'payload_excerpt': 'Test message body excerpt',
        }
        defaults.update(kwargs)
        return self.env['etsy.message.dedupe'].create(defaults)

    def test_create_basic_posted_record(self):
        """Test that a basic posted record can be created with all fields."""
        record = self._create_message_dedupe(
            etsy_message_id='msg_basic_001',
            channel='email',
            target_sale_order_id=self.sale_order.id,
        )

        self.assertTrue(record.id)
        self.assertEqual(record.etsy_shop_id, self.shop)
        self.assertEqual(record.etsy_message_id, 'msg_basic_001')
        self.assertEqual(record.channel, 'email')
        self.assertEqual(record.state, 'posted')
        self.assertEqual(record.target_sale_order_id, self.sale_order)
        self.assertFalse(record.target_enquiry_id)
        self.assertFalse(record.pending_target_receipt_id)

    def test_xor_constraint_posted_zero_targets(self):
        """Test C-EMD-001: state='posted' with NO targets raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self._create_message_dedupe(
                etsy_message_id='msg_zero_targets',
                state='posted',
                target_sale_order_id=False,
                target_enquiry_id=False,
                pending_target_receipt_id='',
            )
        self.assertIn('C-EMD-001', str(cm.exception))

    def test_xor_constraint_posted_two_targets(self):
        """Test C-EMD-001: state='posted' with TWO targets raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self._create_message_dedupe(
                etsy_message_id='msg_two_targets',
                state='posted',
                target_sale_order_id=self.sale_order.id,
                pending_target_receipt_id='receipt_123',
            )
        self.assertIn('C-EMD-001', str(cm.exception))

    def test_xor_constraint_buffered_only_pending(self):
        """Test C-EMD-001: state='buffered' with only pending_target_receipt_id succeeds."""
        record = self._create_message_dedupe(
            etsy_message_id='msg_buffered_pending',
            state='buffered',
            pending_target_receipt_id='receipt_pending_001',
            target_sale_order_id=False,
            target_enquiry_id=False,
        )

        self.assertEqual(record.state, 'buffered')
        self.assertEqual(record.pending_target_receipt_id, 'receipt_pending_001')
        self.assertFalse(record.target_sale_order_id)
        self.assertFalse(record.target_enquiry_id)

    def test_xor_constraint_buffered_with_order(self):
        """Test C-EMD-001: state='buffered' with target_sale_order_id raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            self._create_message_dedupe(
                etsy_message_id='msg_buffered_with_order',
                state='buffered',
                target_sale_order_id=self.sale_order.id,
                pending_target_receipt_id='receipt_123',
            )
        self.assertIn('C-EMD-001', str(cm.exception))

    def test_acl_api_log_reader_read_only(self):
        """Test ACL: etsy_integration.group_etsy_api_log_reader has read-only access."""
        # Create a user with the api_log_reader group
        reader_group = self.env.ref('etsy_integration.group_etsy_api_log_reader')
        reader_user = self.env['res.users'].create({
            'name': 'API Log Reader User',
            'login': 'api_reader@test.com',
            'group_ids': [(6, 0, [reader_group.id])],
        })

        # Create a message record as admin
        record = self._create_message_dedupe(
            etsy_message_id='msg_acl_reader_test',
            target_sale_order_id=self.sale_order.id,
        )

        # Verify the reader user CAN read (search succeeds)
        records = self.env['etsy.message.dedupe'].with_user(reader_user).search(
            [('id', '=', record.id)]
        )
        self.assertEqual(len(records), 1, "Reader group should have read access")

        # Verify the reader user CANNOT create
        with self.assertRaises(AccessError):
            self.env['etsy.message.dedupe'].with_user(reader_user).create({
                'etsy_shop_id': self.shop.id,
                'etsy_message_id': 'msg_no_create',
                'channel': 'api',
                'posted_at': fields.Datetime.now(),
                'state': 'posted',
                'target_sale_order_id': self.sale_order.id,
            })

        # Verify the reader user CANNOT write
        with self.assertRaises(AccessError):
            record.with_user(reader_user).write({'payload_excerpt': 'Modified'})

        # Verify the reader user CANNOT unlink
        with self.assertRaises(AccessError):
            record.with_user(reader_user).unlink()

    def test_acl_base_group_system_full(self):
        """Test ACL: base.group_system (admin) has full access."""
        # Get or create system user (typically admin is system member)
        system_user = self.env.ref('base.user_admin')

        # Create a message record as system user
        record = self.env['etsy.message.dedupe'].with_user(system_user).create({
            'etsy_shop_id': self.shop.id,
            'etsy_message_id': 'msg_system_full',
            'body_sha256_prefix': 'sys12345',
            'channel': 'api',
            'posted_at': fields.Datetime.now(),
            'state': 'posted',
            'target_sale_order_id': self.sale_order.id,
        })
        self.assertTrue(record.id, "System user should be able to create")

        # Write as system user
        record.with_user(system_user).write({
            'payload_excerpt': 'Modified by system'
        })
        self.assertEqual(record.payload_excerpt, 'Modified by system')

        # Unlink as system user
        record_id = record.id
        record.with_user(system_user).unlink()
        deleted = self.env['etsy.message.dedupe'].search([('id', '=', record_id)])
        self.assertEqual(len(deleted), 0, "System user should be able to unlink")

    def test_payload_excerpt_truncation(self):
        """Test that payload_excerpt is truncated to 256 characters."""
        long_body = 'x' * 300  # 300 characters
        record = self._create_message_dedupe(
            etsy_message_id='msg_truncate_test',
            target_sale_order_id=self.sale_order.id,  # satisfy C-EMD-001
            payload_excerpt=long_body,
        )

        # Should be truncated to exactly 256 characters
        self.assertEqual(
            len(record.payload_excerpt), 256,
            "payload_excerpt should be truncated to 256 chars"
        )
        self.assertTrue(
            record.payload_excerpt.startswith('x' * 256),
            "Should contain the first 256 chars of input"
        )

    def test_retention_cron_posted_old_deleted(self):
        """Test _cron_dedupe_retention(): posted messages >30 days old are deleted."""
        # Create a record with posted_at 31 days ago
        old_date = fields.Datetime.now() - timedelta(days=31)
        record = self._create_message_dedupe(
            etsy_message_id='msg_old_posted',
            state='posted',
            posted_at=old_date,
            target_sale_order_id=self.sale_order.id,
        )
        record_id = record.id

        # Run the cron
        self.env['etsy.message.dedupe']._cron_dedupe_retention()

        # Verify the record was deleted
        deleted_record = self.env['etsy.message.dedupe'].search(
            [('id', '=', record_id)]
        )
        self.assertEqual(
            len(deleted_record), 0,
            "Posted record older than 30 days should be deleted"
        )

    def test_retention_cron_posted_recent_kept(self):
        """Test _cron_dedupe_retention(): posted messages <30 days old are kept."""
        # Create a record with posted_at 15 days ago
        recent_date = fields.Datetime.now() - timedelta(days=15)
        record = self._create_message_dedupe(
            etsy_message_id='msg_recent_posted',
            state='posted',
            posted_at=recent_date,
            target_sale_order_id=self.sale_order.id,
        )
        record_id = record.id

        # Run the cron
        self.env['etsy.message.dedupe']._cron_dedupe_retention()

        # Verify the record still exists
        kept_record = self.env['etsy.message.dedupe'].search(
            [('id', '=', record_id)]
        )
        self.assertEqual(
            len(kept_record), 1,
            "Posted record younger than 30 days should be kept"
        )

    def test_retention_cron_orphaned_kept_indefinitely(self):
        """Test _cron_dedupe_retention(): orphaned messages are kept regardless of age."""
        # Create a record with posted_at 31 days ago but state=orphaned
        old_date = fields.Datetime.now() - timedelta(days=31)
        record = self._create_message_dedupe(
            etsy_message_id='msg_old_orphaned',
            state='orphaned',
            posted_at=old_date,
            pending_target_receipt_id='orphan_receipt_001',
        )
        record_id = record.id

        # Run the cron
        self.env['etsy.message.dedupe']._cron_dedupe_retention()

        # Verify the record was NOT deleted (kept indefinitely)
        kept_record = self.env['etsy.message.dedupe'].search(
            [('id', '=', record_id)]
        )
        self.assertEqual(
            len(kept_record), 1,
            "Orphaned records should be kept indefinitely"
        )

    def test_retention_cron_buffered_aged_to_orphaned(self):
        """Test _cron_dedupe_retention(): buffered messages >7 days old flip to orphaned."""
        # Create a record with posted_at 8 days ago, state=buffered
        aged_date = fields.Datetime.now() - timedelta(days=8)
        record = self._create_message_dedupe(
            etsy_message_id='msg_aged_buffered',
            state='buffered',
            posted_at=aged_date,
            pending_target_receipt_id='buffered_receipt_aged',
        )
        record_id = record.id

        # Run the cron
        self.env['etsy.message.dedupe']._cron_dedupe_retention()

        # Verify the record's state flipped to orphaned
        aged_record = self.env['etsy.message.dedupe'].search(
            [('id', '=', record_id)]
        )
        self.assertEqual(
            len(aged_record), 1,
            "Aged buffered record should still exist"
        )
        self.assertEqual(
            aged_record.state, 'orphaned',
            "Buffered message >7 days old should be flipped to orphaned"
        )
