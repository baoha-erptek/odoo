"""Phase 2 ORM tests for P-PUB-PERSONALIZATION validator (MP006, Spec 011).

Verifies the @api.constrains('x_is_personalizable', 'x_personalization_char_count')
validator on product.template:
- When x_is_personalizable=False, char_count is unrestricted
- When x_is_personalizable=True, char_count must be in [1, 1024]
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubPersonalizationValidator(TransactionCase):
    """ORM-level tests for personalization constraint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['product.template']

    def _create_template(self, **kwargs):
        """Factory to create product.template with minimal required fields."""
        defaults = {
            'name': 'Test Product',
            'list_price': 10.0,
        }
        defaults.update(kwargs)
        return self.Template.create(defaults)

    def test_char_count_in_range_ok(self):
        """x_is_personalizable=True, char_count=256 creates successfully."""
        tmpl = self._create_template(
            x_is_personalizable=True,
            x_personalization_char_count=256,
        )
        self.assertTrue(tmpl.id)
        self.assertEqual(tmpl.x_personalization_char_count, 256)

    def test_char_count_zero_raises_validation(self):
        """x_is_personalizable=True, char_count=0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_template(
                x_is_personalizable=True,
                x_personalization_char_count=0,
            )

    def test_char_count_above_max_raises_validation(self):
        """x_is_personalizable=True, char_count=1025 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_template(
                x_is_personalizable=True,
                x_personalization_char_count=1025,
            )

    def test_char_count_off_by_one_min(self):
        """x_is_personalizable=True, char_count=1 is allowed (minimum valid)."""
        tmpl = self._create_template(
            x_is_personalizable=True,
            x_personalization_char_count=1,
        )
        self.assertEqual(tmpl.x_personalization_char_count, 1)

    def test_char_count_off_by_one_max(self):
        """x_is_personalizable=True, char_count=1024 is allowed (maximum valid)."""
        tmpl = self._create_template(
            x_is_personalizable=True,
            x_personalization_char_count=1024,
        )
        self.assertEqual(tmpl.x_personalization_char_count, 1024)

    def test_char_count_ignored_when_feature_off(self):
        """x_is_personalizable=False, char_count=0 allowed (feature disabled)."""
        tmpl = self._create_template(
            x_is_personalizable=False,
            x_personalization_char_count=0,
        )
        self.assertTrue(tmpl.id)
        self.assertFalse(tmpl.x_is_personalizable)
        self.assertEqual(tmpl.x_personalization_char_count, 0)
