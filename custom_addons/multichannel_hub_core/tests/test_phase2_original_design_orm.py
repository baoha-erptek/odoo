"""Phase 2: ORM unit tests for ESTY-250 (Original Design tab).

Covers:
- product.document.x_is_original_design create/read
- product.template.x_original_design_ids domain filter
- tag excludes documents from the generic Documents button
- sequence ordering
- delegated ir.attachment fields (name, datas) readable through product.document
"""

import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

_DUMMY_DATAS = base64.b64encode(b'dummy design file content')
_OVERSIZED_DATAS = base64.b64encode(b'\x00' * (11 * 1024 * 1024))


@tagged('post_install', '-at_install')
class TestPhase2OriginalDesignORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['product.template']
        cls.Document = cls.env['product.document']
        cls.product = cls.Template.create({'name': 'ESTY-250 Test Product', 'type': 'consu'})

    def test_create_design_document_tagged(self):
        doc = self.Document.create({
            'name': 'front-print.ai',
            'datas': _DUMMY_DATAS,
            'res_model': 'product.template',
            'res_id': self.product.id,
            'x_is_original_design': True,
        })
        self.assertTrue(doc.x_is_original_design)
        self.assertIn(doc.id, self.product.x_original_design_ids.ids)

    def test_untagged_document_excluded(self):
        doc = self.Document.create({
            'name': 'spec-sheet.pdf',
            'datas': _DUMMY_DATAS,
            'res_model': 'product.template',
            'res_id': self.product.id,
            'x_is_original_design': False,
        })
        self.assertNotIn(doc.id, self.product.x_original_design_ids.ids)

    def test_sequence_ordering(self):
        doc_a = self.Document.create({
            'name': 'back-print.ai', 'datas': _DUMMY_DATAS,
            'res_model': 'product.template', 'res_id': self.product.id,
            'x_is_original_design': True, 'sequence': 20,
        })
        doc_b = self.Document.create({
            'name': 'front-print.ai', 'datas': _DUMMY_DATAS,
            'res_model': 'product.template', 'res_id': self.product.id,
            'x_is_original_design': True, 'sequence': 10,
        })
        ordered_ids = self.product.x_original_design_ids.ids
        self.assertEqual(
            ordered_ids.index(doc_b.id), ordered_ids.index(doc_a.id) - 1,
            "lower sequence must sort first",
        )

    def test_delegated_attachment_fields_readable(self):
        doc = self.Document.create({
            'name': 'label-art.psd',
            'datas': _DUMMY_DATAS,
            'res_model': 'product.template',
            'res_id': self.product.id,
            'x_is_original_design': True,
        })
        self.assertEqual(doc.name, 'label-art.psd')
        self.assertEqual(doc.datas, _DUMMY_DATAS)

    def test_create_via_o2m_command_applies_default_tag(self):
        product = self.Template.create({'name': 'ESTY-250 O2M Product', 'type': 'consu'})
        product.write({
            'x_original_design_ids': [(0, 0, {
                'name': 'via-o2m.ai',
                'datas': _DUMMY_DATAS,
            })],
        })
        created = product.x_original_design_ids
        self.assertEqual(len(created), 1)
        self.assertTrue(created.x_is_original_design)
        self.assertEqual(created.res_model, 'product.template')
        self.assertEqual(created.res_id, product.id)

    def test_oversized_original_design_file_rejected(self):
        with self.assertRaises(ValidationError):
            self.Document.create({
                'name': 'huge.ai',
                'datas': _OVERSIZED_DATAS,
                'res_model': 'product.template',
                'res_id': self.product.id,
                'x_is_original_design': True,
            })

    def test_oversized_untagged_document_not_capped(self):
        """Standard Documents-button uploads (untagged) keep Odoo's default: no cap."""
        doc = self.Document.create({
            'name': 'huge-catalog.pdf',
            'datas': _OVERSIZED_DATAS,
            'res_model': 'product.template',
            'res_id': self.product.id,
            'x_is_original_design': False,
        })
        self.assertTrue(doc.id)
