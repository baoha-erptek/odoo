"""Phase 2 (ORM) tests for the design module — ESTY-244."""
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install', 'design')
class TestDesignOrderORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'ESTY-244 Buyer'})
        cls.product = cls.env['product.product'].create({
            'name': 'ESTY-244 Tee', 'type': 'consu', 'list_price': 20.0})
        cls.ICP = cls.env['ir.config_parameter'].sudo()

    def _new_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1})],
        })

    # ------------------------------------------------------------- model
    def test_create_assigns_sequence(self):
        so = self._new_order()
        do = self.env['design.order'].create({'sale_order_id': so.id})
        self.assertNotIn(do.name, ('New', '/', False))
        self.assertTrue(do.name.startswith('DO'))
        self.assertEqual(do.state, 'pending')

    def test_one_design_order_per_sale_order(self):
        so = self._new_order()
        self.env['design.order'].create({'sale_order_id': so.id})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env['design.order'].create({'sale_order_id': so.id})

    # ------------------------------------------------------------- auto-create
    def test_auto_create_on_confirm(self):
        self.ICP.set_param('design.auto_create_on_confirm', 'True')
        so = self._new_order()
        self.assertFalse(so.design_order_ids)
        so.action_confirm()
        self.assertEqual(len(so.design_order_ids), 1)
        self.assertEqual(so.design_order_ids.sale_order_id, so)

    def test_auto_create_disabled(self):
        self.ICP.set_param('design.auto_create_on_confirm', 'False')
        so = self._new_order()
        so.action_confirm()
        self.assertFalse(so.design_order_ids)
        self.ICP.set_param('design.auto_create_on_confirm', 'True')

    def test_auto_create_idempotent(self):
        self.ICP.set_param('design.auto_create_on_confirm', 'True')
        so = self._new_order()
        so.action_confirm()
        so._ensure_design_order()  # second pass must not duplicate
        self.assertEqual(len(so.design_order_ids), 1)

    def test_confirm_links_existing_design_files(self):
        self.ICP.set_param('design.auto_create_on_confirm', 'True')
        so = self._new_order()
        df = self.env['design.file'].create({
            'name': 'mockup', 'order_id': so.id,
            'storage_mode': 'url', 'file_url': 'https://example.com/a.png'})
        self.assertFalse(df.design_order_id)
        so.action_confirm()
        self.assertEqual(df.design_order_id, so.design_order_ids)

    # ------------------------------------------------------------- approval
    def test_approve_stamps_state(self):
        so = self._new_order()
        do = self.env['design.order'].create({'sale_order_id': so.id})
        do.action_approve()
        self.assertEqual(do.state, 'approved')
        self.assertEqual(do.approved_by, self.env.user)
        self.assertTrue(do.approved_at)

    def test_approve_advances_pipeline_when_resolved(self):
        so = self._new_order()
        so.action_confirm()
        do = so.design_order_ids
        do.action_approve()
        pipeline = so.x_pipeline_id
        if pipeline and pipeline.state_ids.filtered(
                lambda s: s.code == 'design_ready'):
            self.assertEqual(so.x_pipeline_state_id.code, 'design_ready')
        else:
            # No pipeline resolved / no design_ready code → graceful no-op.
            self.assertEqual(do.state, 'approved')

    def test_reject_requires_reason(self):
        so = self._new_order()
        do = self.env['design.order'].create({'sale_order_id': so.id})
        with self.assertRaises(ValidationError):
            do.action_reject()
        do.rejection_reason = 'blurry'
        do.action_reject()
        self.assertEqual(do.state, 'rejected')

    def test_approve_attaches_files_to_mo(self):
        so = self._new_order()
        so.action_confirm()
        do = so.design_order_ids
        self.env['design.file'].create({
            'name': 'final', 'design_order_id': do.id, 'order_id': so.id,
            'storage_mode': 'url', 'file_url': 'https://example.com/final.png',
            'state': 'approved'})
        try:
            mo = self.env['mrp.production'].create({
                'product_id': self.product.id, 'product_qty': 1,
                'origin': so.name})
        except Exception:  # pragma: no cover - env-dependent MO setup
            self.skipTest("mrp.production could not be created in this env")
        do.action_approve()
        att = self.env['ir.attachment'].search([
            ('res_model', '=', 'mrp.production'), ('res_id', '=', mo.id),
            ('description', 'like', 'design.file:')])
        self.assertTrue(att, "approved design file should attach to the MO")

    # ------------------------------------------------------------- backfill
    def test_infer_state_helper(self):
        from odoo.addons.design.hooks import _infer_state
        DF = self.env['design.file']
        so = self._new_order()
        approved = DF.create({
            'name': 'a', 'order_id': so.id, 'storage_mode': 'url',
            'file_url': 'https://example.com/x.png', 'state': 'approved'})
        pending = DF.new({'state': 'pending'})
        self.assertEqual(_infer_state(approved | DF.browse()), 'approved')
        self.assertEqual(_infer_state(DF.concat(pending)), 'pending')
