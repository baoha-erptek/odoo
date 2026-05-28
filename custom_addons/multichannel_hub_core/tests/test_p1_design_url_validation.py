"""P1-DESIGN-URL-VALIDATION — RED tests for URL/file-id input validation.

Surfaced by security-reviewer on P4-01-FIX-PAYLOAD-SCHEMA (2026-05-10):
`design.file.file_url` and `design.file.gdrive_file_id` are user-editable
by `production_team` and feed into outbound HTTPS POST bodies to Gearment
+ chatter rendering. Without scheme/format validation, a malicious operator
could inject `javascript:`, `file:`, `data:` URLs (XSS surface in chatter,
SSRF via outbound payload echo) or arbitrary strings as `gdrive_file_id`.

Defense-in-depth on top of Odoo's base ACL — production-team has write
access by design (they paste real Drive links); this slice forces those
writes to be syntactically safe.
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'p1_design_url_validation')
class TestFileUrlSchemeValidation(TransactionCase):
    """`design.file.file_url` must be empty OR start with `https://` (or
    `http://` for backward compatibility on internal staging links)."""

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'BuyerURL'})
        self.product = self.env['product.product'].create({
            'name': 'P', 'type': 'consu', 'list_price': 5.0,
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })

    def _make(self, **kwargs):
        defaults = dict(
            name='design',
            order_line_id=self.order.order_line[0].id,
            storage_mode='url',
            file_url='https://drive.google.com/file/d/abc/view',
        )
        defaults.update(kwargs)
        return self.env['design.file'].create(defaults)

    def test_https_url_accepted(self):
        df = self._make(file_url='https://drive.google.com/file/d/abc/view')
        self.assertEqual(df.file_url, 'https://drive.google.com/file/d/abc/view')

    def test_http_url_accepted(self):
        """Internal/staging links may be plain http; not a hard reject."""
        df = self._make(file_url='http://internal-staging/foo.png')
        self.assertEqual(df.file_url, 'http://internal-staging/foo.png')

    def test_javascript_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(file_url='javascript:alert(1)')

    def test_data_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(file_url='data:text/html,<script>alert(1)</script>')

    def test_file_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(file_url='file:///etc/passwd')

    def test_relative_url_rejected(self):
        """Relative URLs (no scheme) cannot be safely rendered nor pushed."""
        with self.assertRaises(ValidationError):
            self._make(file_url='/some/path.png')

    def test_empty_file_url_allowed_when_storage_mode_not_url(self):
        """Other storage modes don't require file_url; empty must pass."""
        df = self._make(
            file_url=False,
            storage_mode='small',
        )
        self.assertFalse(df.file_url)

    def test_write_to_unsafe_url_rejected(self):
        """Constraint must trigger on write(), not just create."""
        df = self._make(file_url='https://drive.example/x.png')
        with self.assertRaises(ValidationError):
            df.write({'file_url': 'javascript:alert(1)'})


@tagged('post_install', '-at_install', 'p1_design_url_validation')
class TestGdriveFileIdFormatValidation(TransactionCase):
    """`design.file.gdrive_file_id` must match Drive's id format `[A-Za-z0-9_-]+`.

    Real Drive file IDs are 33+ alphanumeric chars; allow any non-empty
    `[A-Za-z0-9_-]+` to stay forward-compatible with id-format changes.
    Reject anything containing path separators, whitespace, or punctuation
    that could enable URL injection in the computed `gdrive_preview_url`.
    """

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'BuyerGD'})
        self.product = self.env['product.product'].create({
            'name': 'PG', 'type': 'consu', 'list_price': 5.0,
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })

    def _make(self, **kwargs):
        defaults = dict(
            name='design',
            order_line_id=self.order.order_line[0].id,
            storage_mode='gdrive',
            gdrive_file_id='1AbcDefGhi_jklmNopQrsTuvWxyz0_123',
            gdrive_folder_id='folder123',
        )
        defaults.update(kwargs)
        return self.env['design.file'].create(defaults)

    def test_real_format_id_accepted(self):
        df = self._make(gdrive_file_id='1AbcDefGhi_jklmNopQrsTuvWxyz0_123')
        self.assertTrue(df)

    def test_id_with_path_separator_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(gdrive_file_id='abc/../etc/passwd')

    def test_id_with_whitespace_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(gdrive_file_id='abc def')

    def test_id_with_url_query_rejected(self):
        """`abc?injection=1` would let an attacker append URL params on the
        computed gdrive_preview_url and exfiltrate cookies on click."""
        with self.assertRaises(ValidationError):
            self._make(gdrive_file_id='abc?injection=1')

    def test_id_with_html_tag_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(gdrive_file_id='<script>alert(1)</script>')

    def test_empty_id_accepted_when_storage_mode_not_gdrive(self):
        """gdrive_file_id is only meaningful when storage_mode='gdrive'."""
        df = self._make(gdrive_file_id=False, storage_mode='small')
        self.assertFalse(df.gdrive_file_id)
