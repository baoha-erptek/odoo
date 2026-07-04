"""Phase C — product.template Tier-3 curation (Flow 1 mockup screen 1).

Hides standard "clutter" — Routes/MTO (the stock ``operations`` group),
``responsible_id``, and the receipt/delivery note blocks
(``description_pickingin`` / ``description_pickingout``) — behind
``groups="base.group_no_one"`` so a BA / BA-Lead-Marketing user sees a focused
product form. ``base.group_no_one`` only resolves true in developer mode, so in
the live web client these nodes vanish for normal users (the screenshot gate in
Phase E is the visual proof).

This test asserts at the *combined-arch* level — the inheritance-merged view
before per-user post-processing — which deterministically proves each curation
xpath resolved to the intended node and stamped ``base.group_no_one`` on it. It
avoids the per-user ``get_view`` path, whose ``group_no_one`` handling depends on
debug-mode session context and is not a reliable unit-test surface.

See ``docs/owner/design-system/MOCKUP_product_template.md`` (the
``odoo-functional-mockup`` deliverable that drives these edits).
"""

import re

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductFormCuration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The primary product.template form; all curated nodes merge into it.
        cls.arch = cls.env.ref(
            'product.product_template_only_form_view').get_combined_arch()

    def _node_has_no_one(self, opening_tag_pattern):
        """True when the matched opening tag carries groups=base.group_no_one."""
        m = re.search(opening_tag_pattern, self.arch)
        self.assertTrue(m, 'expected node not found in combined arch: %s'
                        % opening_tag_pattern)
        tag = self.arch[m.start():self.arch.index('>', m.start())]
        return 'groups="base.group_no_one"' in tag

    def test_operations_group_curated(self):
        # Routes / MTO / dropship buy-sell setup group.
        self.assertTrue(self._node_has_no_one(r'<group[^>]*name="operations"'))

    def test_receipt_delivery_notes_curated(self):
        # The note blocks sit in unnamed <group string="Description for ...">
        # wrappers; assert the wrapper enclosing each field carries the group.
        for field in ('description_pickingin', 'description_pickingout'):
            idx = self.arch.index('name="%s"' % field)
            preceding_group = self.arch.rfind('<group', 0, idx)
            tag = self.arch[preceding_group:self.arch.index('>', preceding_group)]
            self.assertIn('groups="base.group_no_one"', tag,
                          '%s note block not curated' % field)

    def test_responsible_id_curated(self):
        self.assertTrue(self._node_has_no_one(r'<field[^>]*name="responsible_id"'))

    def test_weight_kept_visible(self):
        # Etsy / dropship need physical dimensions — weight must NOT be curated.
        self.assertFalse(self._node_has_no_one(r'<field[^>]*name="weight"'))
