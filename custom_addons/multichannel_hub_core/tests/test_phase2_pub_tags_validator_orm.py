"""Phase 2 ORM tests for P-PUB-TAGS validator (Spec 011, MP006).

Validates @api.constrains('product_tag_ids') on product.template enforcing
Etsy tag rules: max 13 tags, each <=20 chars, charset [A-Za-z0-9 \\-'].
Reuses standard Odoo 19 CE `product.tag` (base `product` addon).
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubTagsValidatorORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Template = cls.env['product.template']
        cls.Tag = cls.env['product.tag']

    def _tags(self, names):
        return self.Tag.create([{'name': n} for n in names])

    def _tmpl(self, name, tag_ids=None):
        vals = {'name': name, 'default_code': name.upper().replace(' ', '-')}
        if tag_ids is not None:
            vals['product_tag_ids'] = [(6, 0, tag_ids)]
        return self.Template.create(vals)

    def test_passes_with_thirteen_tags(self):
        tags = self._tags([f'tag{i}' for i in range(13)])
        tmpl = self._tmpl('exactly thirteen', tags.ids)
        self.assertEqual(len(tmpl.product_tag_ids), 13)

    def test_raises_over_thirteen_tags(self):
        tags = self._tags([f'tag{i}' for i in range(14)])
        with self.assertRaises(ValidationError) as cm:
            self._tmpl('fourteen fail', tags.ids)
        self.assertIn('13', str(cm.exception))

    def test_raises_tag_over_twenty_chars(self):
        tag = self.Tag.create({'name': 'A' * 21})
        with self.assertRaises(ValidationError) as cm:
            self._tmpl('long tag', [tag.id])
        self.assertIn('20', str(cm.exception))

    def test_passes_tag_exactly_twenty_chars(self):
        tag = self.Tag.create({'name': 'A' * 20})
        tmpl = self._tmpl('twenty char tag', [tag.id])
        self.assertEqual(len(tmpl.product_tag_ids), 1)

    def test_raises_invalid_charset_at_symbol(self):
        tag = self.Tag.create({'name': 'bad@symbol'})
        with self.assertRaises(ValidationError) as cm:
            self._tmpl('bad charset at', [tag.id])
        self.assertIn('invalid', str(cm.exception).lower())

    def test_raises_invalid_charset_underscore(self):
        tag = self.Tag.create({'name': 'snake_case'})
        with self.assertRaises(ValidationError):
            self._tmpl('bad charset underscore', [tag.id])

    def test_passes_allowed_charset_full(self):
        tags = self._tags([
            'Ceramic',
            'Made-To-Order',
            "Customer's Pick",
            'Sizes S M L',
            'Set of 4',
        ])
        tmpl = self._tmpl('valid charset', tags.ids)
        self.assertEqual(len(tmpl.product_tag_ids), 5)

    def test_write_enforces_constraint(self):
        tag1 = self.Tag.create({'name': 'first'})
        tmpl = self._tmpl('starts small', [tag1.id])
        more = self._tags([f't{i}' for i in range(13)])
        with self.assertRaises(ValidationError):
            tmpl.write({'product_tag_ids': [(6, 0, more.ids + [tag1.id])]})

    def test_empty_tags_allowed(self):
        tmpl = self._tmpl('no tags')
        self.assertEqual(len(tmpl.product_tag_ids), 0)
