"""Tests for P1-DESIGN-MULTI-KANBAN — preview_file thumbnail on kanban + auto-generate on create.

Phase 1 (DB introspection):
  - design_file_kanban view references preview_file field

Phase 2 (ORM):
  - Create with non-empty PNG bytes -> preview_file populated (valid JPEG)
  - Create with storage_mode='url' (no blob) -> preview_file remains False
  - Create with garbage bytes -> no exception, preview_file False, no crash
  - Create with explicit preview_file pre-set -> not overwritten
"""
import base64
import logging
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

# 2x2 white JPEG — RGB so the thumbnail generator can re-encode as JPEG
# (a 1x1 transparent PNG fails JPEG re-encoding with "cannot write mode RGBA
# as JPEG" — silent None return; the generator handles RGB cleanly).
_JPEG_2X2 = base64.b64decode(
    b'/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof'
    b'Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh'
    b'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR'
    b'CAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAA'
    b'AgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK'
    b'FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWG'
    b'h4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl'
    b'5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA'
    b'AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYk'
    b'NOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOE'
    b'hYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk'
    b'5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=='
)


@tagged('post_install', '-at_install')
class TestDesignFileKanbanViewArch(TransactionCase):
    """Phase 1 — assert kanban view renders preview_file."""

    def test_kanban_view_references_preview_file(self):
        view = self.env.ref('multichannel_hub_core.design_file_kanban')
        self.assertIn(
            'preview_file',
            view.arch_db,
            "design_file_kanban must include the preview_file field for the thumbnail.",
        )

    def test_kanban_view_uses_image_widget_for_preview(self):
        view = self.env.ref('multichannel_hub_core.design_file_kanban')
        self.assertRegex(
            view.arch_db,
            r'<field\s+name="preview_file"[^/>]*widget="image"',
            "preview_file must render with widget=\"image\" for click-to-zoom.",
        )


@tagged('post_install', '-at_install')
class TestDesignFileEnsurePreview(TransactionCase):
    """Phase 2 — auto-generation of preview_file on create."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Buyer Test'})
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})

    def test_create_with_blob_populates_preview(self):
        df = self.env['design.file'].create({
            'name': 'mock-design.png',
            'order_id': self.order.id,
            'storage_mode': 'small',
            'design_file': base64.b64encode(_JPEG_2X2),
            'state': 'pending',
        })
        self.assertTrue(
            df.preview_file,
            "preview_file must be populated when design_file blob is non-empty.",
        )
        # Decode and check JPEG magic bytes (FF D8 FF).
        decoded = base64.b64decode(df.preview_file)
        self.assertEqual(
            decoded[:3], b'\xff\xd8\xff',
            "preview_file should be a valid JPEG (magic bytes FF D8 FF).",
        )

    def test_create_url_mode_leaves_preview_empty(self):
        df = self.env['design.file'].create({
            'name': 'link-only',
            'order_id': self.order.id,
            'storage_mode': 'url',
            'file_url': 'https://example.com/design.png',
            'state': 'pending',
        })
        self.assertFalse(
            df.preview_file,
            "url-mode files have no blob; preview_file must remain False.",
        )

    def test_create_garbage_bytes_does_not_crash(self):
        with self.assertLogs(
            'odoo.addons.multichannel_hub_core.models.design_file',
            level=logging.WARNING,
        ) as cm:
            df = self.env['design.file'].create({
                'name': 'corrupt.bin',
                'order_id': self.order.id,
                'storage_mode': 'small',
                'design_file': base64.b64encode(b'this-is-not-an-image'),
                'state': 'pending',
            })
        self.assertFalse(
            df.preview_file,
            "Corrupt blob must yield empty preview_file (best-effort).",
        )
        self.assertTrue(
            any('preview' in msg.lower() for msg in cm.output),
            "A WARNING log must mention 'preview' on generator failure.",
        )

    def test_create_with_explicit_preview_not_overwritten(self):
        sentinel = base64.b64encode(b'\xff\xd8\xff\xe0SENTINEL')
        df = self.env['design.file'].create({
            'name': 'pre-thumbed.png',
            'order_id': self.order.id,
            'storage_mode': 'small',
            'design_file': base64.b64encode(_JPEG_2X2),
            'preview_file': sentinel,
            'state': 'pending',
        })
        self.assertEqual(
            df.preview_file, sentinel,
            "Explicit preview_file in vals must not be regenerated.",
        )

    def test_generator_exception_swallowed(self):
        """Even a hard exception inside ThumbnailGenerator must not block create()."""
        with patch(
            'odoo.addons.multichannel_hub_core.services.'
            'design_thumbnail_generator.ThumbnailGenerator.generate_thumbnail',
            side_effect=RuntimeError("forced failure"),
        ):
            df = self.env['design.file'].create({
                'name': 'will-fail.png',
                'order_id': self.order.id,
                'storage_mode': 'small',
                'design_file': base64.b64encode(_JPEG_2X2),
                'state': 'pending',
            })
        self.assertTrue(df.exists(), "create() must succeed even when generator raises.")
        self.assertFalse(df.preview_file, "preview_file must be empty on generator failure.")
