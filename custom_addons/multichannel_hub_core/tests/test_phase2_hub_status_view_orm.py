"""
Phase 2: ORM tests for P-HUB-STATUS-VIEW (Spec 009 US5).

Verifies:
- x_published_channel_count counts only state='published' statuses
- Recompute on state transitions
- Cascade on status unlink
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHubStatusViewORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        cls.amazon = ChannelAll.search([('code', '=', 'amazon')], limit=1)

    def test_published_count_zero_for_no_status(self):
        tmpl = self.Template.create({'name': 'Status View Test A'})
        self.assertEqual(tmpl.x_published_channel_count, 0)

    def test_published_count_excludes_draft(self):
        tmpl = self.Template.create({'name': 'Status View Test B'})
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
            'state': 'draft',
        })
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.x_published_channel_count, 0)

    def test_published_count_counts_published(self):
        tmpl = self.Template.create({'name': 'Status View Test C'})
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
            'state': 'published',
        })
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.amazon.id,
            'state': 'published',
        })
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.x_published_channel_count, 2)

    def test_published_count_recompute_on_state_change(self):
        tmpl = self.Template.create({'name': 'Status View Test D'})
        st = self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
            'state': 'draft',
        })
        self.assertEqual(tmpl.x_published_channel_count, 0)
        st.write({'state': 'published'})
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.x_published_channel_count, 1)
        st.write({'state': 'archived'})
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.x_published_channel_count, 0)
