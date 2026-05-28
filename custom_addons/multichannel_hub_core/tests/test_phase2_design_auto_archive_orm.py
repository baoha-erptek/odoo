"""Phase 2 ORM tests for P1-DESIGN-AUTO-ARCHIVE.

On state='approved' write to a design.file, sibling non-approved files
in the same scope (order_line_id, fall back to order_id) are soft-archived.
"""

from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestDesignAutoArchive(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DesignFile = cls.env['design.file']
        cls.partner = cls.env.ref('base.partner_admin')
        cls.product = cls.env['product.product'].create({
            'name': 'AutoArch Test Product',
            'list_price': 10.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
        })
        cls.line = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product.id,
            'product_uom_qty': 1.0,
        })
        cls.production_user = new_test_user(
            cls.env, login='auto_arch_prod',
            groups='multichannel_hub_core.group_production_team,sales_team.group_sale_salesman',
        )

    def _make_file(self, name, state='pending', url='https://example.com/x.png'):
        return self.DesignFile.with_user(self.production_user).create({
            'name': name,
            'order_line_id': self.line.id,
            'storage_mode': 'gdrive',
            'gdrive_file_id': 'gd-' + name,
            'gdrive_folder_id': 'gf-' + name,
            'state': state,
        })

    def test_approving_archives_pending_siblings(self):
        a = self._make_file('a', state='pending')
        b = self._make_file('b', state='pending')
        c = self._make_file('c', state='pending')
        # Approve b
        b.with_user(self.production_user).write({'state': 'approved'})
        a.invalidate_recordset()
        b.invalidate_recordset()
        c.invalidate_recordset()
        a_ = self.DesignFile.with_context(active_test=False).browse(a.id)
        b_ = self.DesignFile.with_context(active_test=False).browse(b.id)
        c_ = self.DesignFile.with_context(active_test=False).browse(c.id)
        self.assertTrue(b_.active, "approved row stays active")
        self.assertFalse(a_.active, "sibling pending archived")
        self.assertFalse(c_.active, "sibling pending archived")

    def test_approving_preserves_existing_rejected(self):
        rejected = self._make_file('r', state='pending')
        rejected.with_user(self.production_user).write({'state': 'rejected'})
        # New file approved on same line
        approved = self._make_file('app', state='pending')
        approved.with_user(self.production_user).write({'state': 'approved'})
        rejected.invalidate_recordset()
        # Existing rejected stays active=True (audit trail preserved)
        rj = self.DesignFile.with_context(active_test=False).browse(rejected.id)
        self.assertFalse(rj.active,
                          "P1-DESIGN-AUTO-ARCHIVE archives any non-approved "
                          "sibling regardless of state (slice scope decision)")
