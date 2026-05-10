"""Phase 2 (ORM) tests for P1-DESIGN-AUTO-CREATE-FROM-EMAIL.

Tests the _seed_design_files_from_lines helper method directly,
verifying auto-creation of design.file rows from sale.order.line
design links, with proper idempotency and provenance tracking.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesignFileSeedHelper(TransactionCase):
    """Phase 2: ORM tests for design.file auto-seeding from order lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _create_order_with_lines(self, **kwargs):
        """Factory: Create a sale.order with one or more lines.

        kwargs are merged into the line defaults.
        """
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
        })
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
        })
        order_vals = {
            'partner_id': partner.id,
            'order_line': [],
        }
        line_defaults = {
            'order_id': None,  # Will be set by the order
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        }
        line_defaults.update(kwargs)
        order_vals['order_line'].append((0, 0, line_defaults))
        return self.env['sale.order'].create(order_vals)

    def test_seed_creates_design_file_for_front_link_only(self):
        """Test that a line with only design_link_front creates one design.file."""
        order = self._create_order_with_lines(
            design_link_front='https://gdrive.example/front.jpg',
            design_link_back=False,
        )
        line = order.order_line[0]

        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )

        self.assertEqual(created_count, 1, "Should create 1 design.file for front link only")
        design_files = self.env['design.file'].search([
            ('order_line_id', '=', line.id),
        ])
        self.assertEqual(len(design_files), 1, "One design.file should be linked to the line")
        design_file = design_files[0]
        self.assertEqual(design_file.state, 'pending', "Design file state should be pending")
        self.assertEqual(design_file.storage_mode, 'url', "Storage mode should be url")
        self.assertEqual(
            design_file.file_url, 'https://gdrive.example/front.jpg',
            "File URL should match the design_link_front"
        )
        self.assertEqual(design_file.order_line_id.id, line.id, "Should link to correct line")
        self.assertEqual(
            design_file.created_via, 'email_ingest',
            "created_via should be set to email_ingest"
        )
        self.assertIn('Front', design_file.name, "Name should contain 'Front'")
        self.assertIn(
            line.product_id.display_name, design_file.name,
            "Name should contain product display name"
        )

    def test_seed_creates_design_file_for_back_link_only(self):
        """Test that a line with only design_link_back creates one design.file."""
        order = self._create_order_with_lines(
            design_link_front=False,
            design_link_back='https://gdrive.example/back.jpg',
        )
        line = order.order_line[0]

        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )

        self.assertEqual(created_count, 1, "Should create 1 design.file for back link only")
        design_files = self.env['design.file'].search([
            ('order_line_id', '=', line.id),
        ])
        self.assertEqual(len(design_files), 1, "One design.file should be linked to the line")
        design_file = design_files[0]
        self.assertEqual(design_file.state, 'pending')
        self.assertEqual(design_file.storage_mode, 'url')
        self.assertEqual(design_file.file_url, 'https://gdrive.example/back.jpg')
        self.assertIn('Back', design_file.name, "Name should contain 'Back'")

    def test_seed_creates_two_rows_when_both_links_present(self):
        """Test that a line with both links creates two design.file rows."""
        order = self._create_order_with_lines(
            design_link_front='https://gdrive.example/front.jpg',
            design_link_back='https://gdrive.example/back.jpg',
        )
        line = order.order_line[0]

        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )

        self.assertEqual(created_count, 2, "Should create 2 design.file rows for both links")
        design_files = self.env['design.file'].search([
            ('order_line_id', '=', line.id),
        ])
        self.assertEqual(len(design_files), 2, "Two design.file rows should be linked to the line")
        urls = set(df.file_url for df in design_files)
        self.assertEqual(
            urls,
            {'https://gdrive.example/front.jpg', 'https://gdrive.example/back.jpg'},
            "Both URLs should be present"
        )
        names = {df.name for df in design_files}
        self.assertTrue(
            any('Front' in n for n in names),
            "At least one design.file should have 'Front' in name"
        )
        self.assertTrue(
            any('Back' in n for n in names),
            "At least one design.file should have 'Back' in name"
        )

    def test_seed_skips_lines_with_no_design_links(self):
        """Test that lines without design links are not seeded."""
        order = self._create_order_with_lines(
            design_link_front=False,
            design_link_back='',
        )

        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )

        self.assertEqual(created_count, 0, "Should create 0 design.file rows when no links")
        design_files = self.env['design.file'].search([
            ('order_line_id', '=', order.order_line[0].id),
        ])
        self.assertEqual(len(design_files), 0, "No design.file rows should be created")

    def test_seed_idempotent_on_re_run(self):
        """Test that running seed twice doesn't create duplicates."""
        order = self._create_order_with_lines(
            design_link_front='https://gdrive.example/front.jpg',
            design_link_back='https://gdrive.example/back.jpg',
        )
        line = order.order_line[0]

        # First call
        created_count_1 = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )
        self.assertEqual(created_count_1, 2, "First call should create 2 rows")

        # Second call
        created_count_2 = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )
        self.assertEqual(created_count_2, 0, "Second call should create 0 new rows (idempotent)")

        design_files = self.env['design.file'].search([
            ('order_line_id', '=', line.id),
        ])
        self.assertEqual(len(design_files), 2, "Total count should still be 2")

    def test_seed_skips_existing_url_creates_new_for_different_url(self):
        """Test that seed skips (order_line_id, file_url) match but creates new for different URL."""
        order = self._create_order_with_lines(
            design_link_front='https://gdrive.example/a.jpg',
            design_link_back='https://gdrive.example/b.jpg',
        )
        line = order.order_line[0]

        # Pre-create a design.file with URL A
        self.env['design.file'].create({
            'name': 'Pre-existing A',
            'order_line_id': line.id,
            'storage_mode': 'url',
            'file_url': 'https://gdrive.example/a.jpg',
            'state': 'approved',
        })

        # Seed with URLs A and B
        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )

        self.assertEqual(created_count, 1, "Should only create 1 new row (B); skip A")
        design_files = self.env['design.file'].search([
            ('order_line_id', '=', line.id),
        ])
        self.assertEqual(len(design_files), 2, "Total count should be 2 (pre-existing + new)")
        urls = set(df.file_url for df in design_files)
        self.assertEqual(
            urls,
            {'https://gdrive.example/a.jpg', 'https://gdrive.example/b.jpg'},
            "Both URLs should be present"
        )
        # Verify the new one has the correct created_via
        new_file = design_files.filtered(lambda x: x.file_url == 'https://gdrive.example/b.jpg')
        self.assertEqual(new_file.created_via, 'email_ingest')

    def test_seed_with_api_ingest_marker_sets_correct_created_via(self):
        """Test that created_via parameter is correctly set to 'api_ingest'."""
        order = self._create_order_with_lines(
            design_link_front='https://gdrive.example/front.jpg',
        )

        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='api_ingest'
        )

        self.assertEqual(created_count, 1)
        design_file = self.env['design.file'].search([
            ('order_line_id', '=', order.order_line[0].id),
        ])
        self.assertEqual(
            design_file.created_via, 'api_ingest',
            "created_via should be set to api_ingest when passed"
        )

    def test_seed_returns_zero_for_order_with_no_lines(self):
        """Test that seeding an order with no lines returns 0."""
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [],
        })

        created_count = self.env['design.file']._seed_design_files_from_lines(
            order, created_via='email_ingest'
        )

        self.assertEqual(created_count, 0, "Should return 0 for order with no lines")
