"""Phase 1 (DB) tests for P-LIST-STATUSBAR-CLICKABLE.

Locks the statusbar widget on the multichannel.listing form so that:
- Draft and Ready render as clickable pills (options clickable)
- Published is NOT in statusbar_visible (so it doesn't render as a
  clickable workflow step; the publisher service owns that transition)
"""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestListingStatusbarClickable(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.view = cls.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form',
            raise_if_not_found=False,
        )

    def _state_field(self):
        self.assertTrue(self.view, "base listing form view missing")
        root = etree.fromstring(self.view.arch_db.encode('utf-8'))
        nodes = root.xpath("//header/field[@name='state']")
        self.assertEqual(
            len(nodes), 1,
            "expected exactly one <field name='state'> under header",
        )
        return nodes[0]

    def test_statusbar_widget_is_clickable(self):
        node = self._state_field()
        options = node.get('options') or ''
        self.assertIn(
            "'clickable': '1'", options,
            "state field must declare options={'clickable':'1'}; got %r"
            % options,
        )

    def test_statusbar_visible_includes_draft_and_ready(self):
        node = self._state_field()
        visible = node.get('statusbar_visible') or ''
        steps = [s.strip() for s in visible.split(',')]
        self.assertIn('draft', steps)
        self.assertIn('ready', steps)

    def test_statusbar_visible_excludes_published(self):
        node = self._state_field()
        visible = node.get('statusbar_visible') or ''
        steps = [s.strip() for s in visible.split(',')]
        self.assertNotIn(
            'published', steps,
            "published must be set by the publisher service, not via "
            "manual statusbar click; statusbar_visible=%r" % visible,
        )
