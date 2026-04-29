"""
Phase 2: ORM unit tests for design.file model lifecycle.

Tests verify business logic and workflows:
- Constraints on creation (XOR of order_id / order_line_id)
- File size limits enforced by storage_mode
- Storage mode validation (url mode requires file_url)
- State machine transitions (pending -> approved / rejected)
- Parent-version tracking for re-uploads
- Version tracking on reject/re-upload
- Production team ACL and kanban state changes
- Mail tracking on state transitions
- Design status computed on sale.order.line from design.file children
- Historical seed data migration

Tests use TransactionCase for isolation and ORM API verification.
"""

import base64
import logging

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDesignFileConstraints(TransactionCase):
    """Verify design.file constraints: XOR order/order_line, storage_mode rules."""

    @classmethod
    def setUpClass(cls):
        """Set up test data: partner, product, sale.order with lines."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        cls.order_line = cls.order.order_line[0]

    def _create_design_file(self, **kwargs):
        """Factory method to create design.file records."""
        defaults = {
            'name': 'Test Design',
            'storage_mode': 'url',
            'file_url': 'https://example.com/design.tiff',
        }
        defaults.update(kwargs)
        return self.env['design.file'].create(defaults)

    def test_c_df_001_xor_order_id_or_order_line_id(self):
        """Test XOR constraint: exactly one of order_id or order_line_id required."""
        # Both provided should raise ValidationError
        with self.assertRaises(ValidationError):
            self._create_design_file(
                order_id=self.order.id,
                order_line_id=self.order_line.id
            )

        # Neither provided should raise ValidationError
        with self.assertRaises(ValidationError):
            self._create_design_file(
                order_id=None,
                order_line_id=None
            )

        # Only order_id should succeed
        df_order = self._create_design_file(
            name='Design with order',
            order_id=self.order.id,
            order_line_id=None
        )
        self.assertTrue(df_order.id)
        self.assertEqual(df_order.order_id, self.order)

        # Only order_line_id should succeed
        df_line = self._create_design_file(
            name='Design with line',
            order_id=None,
            order_line_id=self.order_line.id
        )
        self.assertTrue(df_line.id)
        self.assertEqual(df_line.order_line_id, self.order_line)

    def test_c_df_002_storage_mode_small_size_cap_via_constrains(self):
        """Test @api.constrains: storage_mode='small' enforces 10 MB file size cap."""
        # 11 MB should raise ValidationError
        large_bytes = b'\x00' * (11 * 1024 * 1024)
        large_b64 = base64.b64encode(large_bytes).decode('utf-8')

        with self.assertRaises(ValidationError):
            self._create_design_file(
                name='Too large',
                storage_mode='small',
                design_file=large_b64,
                order_line_id=self.order_line.id
            )

    def test_c_df_002_storage_mode_small_size_cap_via_ir_attachment_override(self):
        """Test ir.attachment override: 10 MB cap for restricted models."""
        large_bytes = b'\x00' * (11 * 1024 * 1024)
        large_b64 = base64.b64encode(large_bytes).decode('utf-8')

        # Create a design.file record without attachment first
        df = self._create_design_file(
            name='For attachment',
            order_line_id=self.order_line.id
        )

        # Attempt to create ir.attachment with res_model='design.file' and 11 MB
        with self.assertRaises(ValidationError):
            self.env['ir.attachment'].create({
                'name': 'large_design.tiff',
                'res_model': 'design.file',
                'res_id': df.id,
                'datas': large_b64,
            })

        # Verify cap does NOT apply to unrestricted model (res.partner)
        partner = self.env['res.partner'].create({'name': 'Test Partner'})
        attachment = self.env['ir.attachment'].create({
            'name': 'large_partner_file',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'datas': large_b64,
        })
        self.assertTrue(attachment.id)

    def test_c_df_003_storage_mode_url_requires_file_url(self):
        """Test storage_mode='url' requires non-empty file_url."""
        # storage_mode='url' without file_url should raise ValidationError
        with self.assertRaises(ValidationError):
            self._create_design_file(
                name='Missing URL',
                storage_mode='url',
                file_url=False,
                order_line_id=self.order_line.id
            )

        # With file_url should succeed
        df = self._create_design_file(
            name='With URL',
            storage_mode='url',
            file_url='https://example.com/design.tiff',
            order_line_id=self.order_line.id
        )
        self.assertTrue(df.id)
        self.assertEqual(df.storage_mode, 'url')
        self.assertEqual(df.file_url, 'https://example.com/design.tiff')


@tagged('post_install', '-at_install')
class TestDesignFileKanbanACL(TransactionCase):
    """Verify kanban state transitions: ACL, approval, rejection."""

    @classmethod
    def setUpClass(cls):
        """Set up production team user and non-production user."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        cls.order_line = cls.order.order_line[0]

        # Production team user
        cls.prod_team_group = cls.env.ref('multichannel_hub_core.group_production_team')
        cls.prod_user = cls.env['res.users'].create({
            'name': 'Production Team Member',
            'login': 'prod@test.com',
            'email': 'prod@test.com',
            'groups_id': [(6, 0, [cls.prod_team_group.id, cls.env.ref('base.group_user').id])],
        })

        # Non-production user
        cls.regular_user = cls.env['res.users'].create({
            'name': 'Regular User',
            'login': 'regular@test.com',
            'email': 'regular@test.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def _create_design_file(self, **kwargs):
        """Factory method to create design.file records."""
        defaults = {
            'name': 'Test Design',
            'storage_mode': 'url',
            'file_url': 'https://example.com/design.tiff',
            'order_line_id': self.order_line.id,
        }
        defaults.update(kwargs)
        return self.env['design.file'].create(defaults)

    def test_production_team_user_can_set_state(self):
        """Test production team member can approve design via action_approve."""
        df = self._create_design_file(state='pending')
        self.assertEqual(df.state, 'pending')

        # As production user, approve the design
        df_as_prod = df.with_user(self.prod_user)
        df_as_prod.action_approve()

        # Re-read to verify state change
        df.refresh()
        self.assertEqual(df.state, 'approved')
        self.assertEqual(df.approved_by, self.prod_user)
        self.assertIsNotNone(df.approved_at)

    def test_non_production_team_user_cannot_set_state_via_rpc(self):
        """Test non-production user cannot approve; action_approve raises AccessError."""
        df = self._create_design_file(state='pending')

        # As regular user, attempt to approve
        df_as_regular = df.with_user(self.regular_user)
        with self.assertRaises(AccessError):
            df_as_regular.action_approve()

        # Verify direct write also raises AccessError
        with self.assertRaises(AccessError):
            df_as_regular.write({'state': 'approved'})

    def test_action_reject_requires_rejection_reason(self):
        """Test action_reject validates rejection_reason is set."""
        df = self._create_design_file(state='pending')

        # As production user, attempt to reject without reason
        df_as_prod = df.with_user(self.prod_user)
        with self.assertRaises(ValidationError):
            df_as_prod.action_reject()

        # Set reason and reject should succeed
        df_as_prod.action_reject(reason='Blurry image')
        df.refresh()
        self.assertEqual(df.state, 'rejected')
        self.assertEqual(df.rejection_reason, 'Blurry image')


@tagged('post_install', '-at_install')
class TestDesignFileMailThread(TransactionCase):
    """Verify mail.thread tracking on state transitions."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        cls.order_line = cls.order.order_line[0]

        cls.prod_team_group = cls.env.ref('multichannel_hub_core.group_production_team')
        cls.prod_user = cls.env['res.users'].create({
            'name': 'Production Team',
            'login': 'prod@test.com',
            'email': 'prod@test.com',
            'groups_id': [(6, 0, [cls.prod_team_group.id, cls.env.ref('base.group_user').id])],
        })

    def test_state_change_creates_mail_message(self):
        """Test state changes create mail.tracking.value entries."""
        df = self.env['design.file'].create({
            'name': 'Test Design',
            'storage_mode': 'url',
            'file_url': 'https://example.com/design.tiff',
            'order_line_id': self.order_line.id,
            'state': 'pending',
        })

        # Change state to approved
        df_as_prod = df.with_user(self.prod_user)
        df_as_prod.action_approve()

        # Verify mail message exists
        self.assertGreater(
            len(df.message_ids),
            0,
            "design.file should have mail messages after state change"
        )

        # Verify tracking value for state field exists
        tracking_vals = self.env['mail.tracking.value'].search([
            ('mail_message_id', 'in', df.message_ids.ids),
            ('field_id.name', '=', 'state'),
        ])
        self.assertGreater(
            len(tracking_vals),
            0,
            "mail.tracking.value should exist for state field change"
        )


@tagged('post_install', '-at_install')
class TestSaleOrderLineDesignStatus(TransactionCase):
    """Verify sale.order.line.design_status computed field."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        cls.order_line = cls.order.order_line[0]

    def _create_design_file(self, state='approved', order_line=None, **kwargs):
        """Factory method for design.file."""
        if order_line is None:
            order_line = self.order_line

        defaults = {
            'name': 'Test Design',
            'storage_mode': 'url',
            'file_url': 'https://example.com/design.tiff',
            'order_line_id': order_line.id,
            'state': state,
        }
        defaults.update(kwargs)
        return self.env['design.file'].create(defaults)

    def test_design_status_none_when_no_children(self):
        """Test design_status='none' when no design.file children exist."""
        self.order_line.refresh()
        self.assertEqual(
            self.order_line.design_status,
            'none',
            "design_status should be 'none' when no design files exist"
        )

    def test_design_status_approved_when_all_children_approved(self):
        """Test design_status='approved' when all children are approved."""
        self._create_design_file(state='approved', name='Design 1')
        self._create_design_file(state='approved', name='Design 2')

        self.order_line.refresh()
        self.assertEqual(
            self.order_line.design_status,
            'approved',
            "design_status should be 'approved' when all children approved"
        )

    def test_design_status_pending_when_mixed_pending_and_approved(self):
        """Test design_status='pending' when mix of pending and approved children."""
        self._create_design_file(state='pending', name='Pending Design')
        self._create_design_file(state='approved', name='Approved Design')

        self.order_line.refresh()
        self.assertEqual(
            self.order_line.design_status,
            'pending',
            "design_status should be 'pending' when any child is pending"
        )

    def test_design_status_rejected_when_any_child_rejected(self):
        """Test design_status='rejected' when any child is rejected (lowest precedence)."""
        self._create_design_file(state='approved', name='Approved')
        self._create_design_file(state='pending', name='Pending')
        self._create_design_file(state='rejected', name='Rejected')

        self.order_line.refresh()
        self.assertEqual(
            self.order_line.design_status,
            'rejected',
            "design_status should be 'rejected' when any child is rejected"
        )


@tagged('post_install', '-at_install')
class TestHistoricalSeedT078(TransactionCase):
    """Verify T-078 seed: migrate historical etsy design links to design.file."""

    @classmethod
    def setUpClass(cls):
        """Set up test sale.order.line with historical design links."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
        })

        # Line (a): both front and back links
        cls.line_both = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
            'etsy_design_link_front': 'https://design.etsy.com/front.jpg',
            'etsy_design_link_back': 'https://design.etsy.com/back.jpg',
        })

        # Line (b): front-only
        cls.line_front = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
            'etsy_design_link_front': 'https://design.etsy.com/only_front.jpg',
            'etsy_design_link_back': False,
        })

        # Line (c): both empty
        cls.line_empty = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
            'etsy_design_link_front': False,
            'etsy_design_link_back': False,
        })

    def test_seed_creates_design_file_url_rows(self):
        """Test seed creates design.file rows from historical etsy design links."""
        # Call the seed method
        self.env['design.file']._seed_from_historical_lines()

        # Verify 3 rows created (line_both → 2, line_front → 1, line_empty → 0)
        df_both = self.env['design.file'].search([
            ('order_line_id', '=', self.line_both.id),
        ])
        self.assertEqual(len(df_both), 2, "Line with both links should create 2 design files")

        df_front = self.env['design.file'].search([
            ('order_line_id', '=', self.line_front.id),
        ])
        self.assertEqual(len(df_front), 1, "Line with front-only should create 1 design file")

        df_empty = self.env['design.file'].search([
            ('order_line_id', '=', self.line_empty.id),
        ])
        self.assertEqual(len(df_empty), 0, "Line with no links should create 0 design files")

        # Verify all are 'url' mode, is_seed=True, state='approved'
        for df in df_both | df_front:
            self.assertEqual(df.storage_mode, 'url')
            self.assertTrue(df.is_seed)
            self.assertEqual(df.state, 'approved')

    def test_seed_is_idempotent(self):
        """Test seed is idempotent: calling twice does not duplicate rows."""
        self.env['design.file']._seed_from_historical_lines()
        count_after_first = self.env['design.file'].search_count([])

        self.env['design.file']._seed_from_historical_lines()
        count_after_second = self.env['design.file'].search_count([])

        self.assertEqual(
            count_after_first,
            count_after_second,
            "Seed should be idempotent; second call should not create duplicates"
        )

    def test_seed_skips_empty_urls(self):
        """Test seed does not create rows for empty/missing design links."""
        self.env['design.file']._seed_from_historical_lines()

        # Verify no rows with file_url IS NULL
        null_url = self.env['design.file'].search([
            ('file_url', '=', False),
        ])
        self.assertEqual(
            len(null_url),
            0,
            "No design.file should be created with empty file_url"
        )

    def test_seed_name_format(self):
        """Test seeded rows have correct name format."""
        self.env['design.file']._seed_from_historical_lines()

        df_both = self.env['design.file'].search([
            ('order_line_id', '=', self.line_both.id),
        ])

        # Name should contain '[Historical]'
        for df in df_both:
            self.assertIn(
                '[Historical]',
                df.name,
                f"Seeded design file name should contain '[Historical]': {df.name}"
            )


@tagged('post_install', '-at_install')
class TestIrAttachmentCapBoundary(TransactionCase):
    """Verify ir.attachment file size cap for restricted models."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_cap_does_not_apply_to_unrestricted_models(self):
        """Test file size cap does NOT apply to unrestricted models like res.partner."""
        partner = self.env['res.partner'].create({'name': 'Test Partner'})

        # 11 MB should succeed for unrestricted model
        large_bytes = b'\x00' * (11 * 1024 * 1024)
        large_b64 = base64.b64encode(large_bytes).decode('utf-8')

        attachment = self.env['ir.attachment'].create({
            'name': 'large_file',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'datas': large_b64,
        })

        self.assertTrue(
            attachment.id,
            "Large file should be allowed for unrestricted model res.partner"
        )

    def test_cap_threshold_via_config_parameter(self):
        """Test file size cap respects ir.config_parameter threshold."""
        # Get current threshold (default 10 MB)
        cap_bytes = 10 * 1024 * 1024
        config_param = self.env['ir.config_parameter'].get_param(
            'multichannel_hub.large_file_threshold_bytes',
            str(cap_bytes)
        )
        if config_param:
            cap_bytes = int(config_param)

        # Create a design.file record
        partner = self.env['res.partner'].create({'name': 'Test'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        order_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.env['product.product'].create({'name': 'P'}).id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        })

        df = self.env['design.file'].create({
            'name': 'Test',
            'storage_mode': 'url',
            'file_url': 'https://example.com/x.tiff',
            'order_line_id': order_line.id,
        })

        # Attempt to attach file exceeding cap
        too_large = b'\x00' * (cap_bytes + 1)
        too_large_b64 = base64.b64encode(too_large).decode('utf-8')

        with self.assertRaises(ValidationError):
            self.env['ir.attachment'].create({
                'name': 'exceeds_cap',
                'res_model': 'design.file',
                'res_id': df.id,
                'datas': too_large_b64,
            })
