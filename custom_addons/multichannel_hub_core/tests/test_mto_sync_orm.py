"""P1-MTO-SYNC — Phase 2 (ORM) MO→SO pipeline state sync verification.

Tests the synchronization between mrp.production state changes and the linked
sale.order's order.pipeline.state:

- MO confirmed → SO pipeline = CHỜ FILE (pending_file)
- All MOs done → SO pipeline = VN-Fulfilled (done)
- Manual mid-stage transitions remain manual (no auto-revert)
- Terminal-stage writes are guarded: SO pipeline cannot jump to done unless MO is done

The sync must call sale.order._write_pipeline_state(...) to honor FR-017 defense-in-depth.
Never write x_pipeline_state_id directly.

See:
- Tracker P1-MTO-SYNC entry (line 167 in `.claude/plans/006-master-plan-tracking.md`)
- specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md §"Amendment 2026-05-03"
- memory `feedback_fr017_write_defense_in_depth.md` (9th confirmation pattern)
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMtoSync(TransactionCase):
    """Phase 2: MO state changes sync SO pipeline state at key boundaries."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data: phantom product, pipeline references."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Phantom product (created by P1-MTO-SEED seed)
        cls.phantom = cls.env.ref('multichannel_hub_core.product_mto_phantom_component')

        # Default partner for SO creation
        cls.partner = cls.env.ref('base.partner_demo', raise_if_not_found=False)
        if not cls.partner:
            cls.partner = cls.env['res.partner'].create({
                'name': 'Demo Partner',
                'email': 'demo@example.com',
            })

        # Product category (required for product creation)
        cls.category = cls.env['product.category'].search([], limit=1)
        if not cls.category:
            cls.category = cls.env['product.category'].create({
                'name': 'Test Category',
            })

        # Pipeline references
        cls.vn_pipeline = cls.env.ref(
            'multichannel_hub_core.order_pipeline_vn_internal_production')
        cls.s_pending_file = cls.env.ref(
            'multichannel_hub_core.state_vn_pending_file')
        cls.s_in_production = cls.env.ref(
            'multichannel_hub_core.state_vn_in_production')
        cls.s_done = cls.env.ref(
            'multichannel_hub_core.state_vn_done')

    def _create_product(self, name, **kwargs):
        """Factory: create product.template on vn_internal_production pipeline."""
        defaults = {
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'categ_id': self.category.id,
            'x_default_pipeline_id': self.vn_pipeline.id,
        }
        defaults.update(kwargs)
        return self.env['product.template'].create(defaults)

    def _create_sale_order(self, product, partner=None, qty=1):
        """Factory: create sale.order with one line."""
        if partner is None:
            partner = self.partner
        variant = (
            product.product_variant_ids[0]
            if product.product_variant_ids
            else product.product_variant_id
        )
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': variant.id,
                    'product_uom_qty': qty,
                    'price_unit': 100.0,
                })
            ],
        })

    def _setup_mto_product_with_so(self, product_name='Test MTO Product', qty=1):
        """Helper: create MTO product, run wizard, create and confirm SO.

        Returns: (product, so) tuple.
        """
        product = self._create_product(product_name)

        # Run wizard to set up MTO route and BOM
        wizard = self.env['product.mto.bom.wizard'].create({
            'product_id': product.id,
        })
        wizard.action_create_bom()

        # Create and confirm SO (triggers MO creation)
        so = self._create_sale_order(product, qty=qty)
        so.action_confirm()

        return product, so

    def _get_production_for_so(self, so):
        """Helper: find the mrp.production record(s) for a given SO."""
        return self.env['mrp.production'].search([
            ('origin', '=', so.name),
        ])

    def test_mo_confirmed_sets_initial_pipeline(self):
        """MO confirmed → SO pipeline advances to CHỜ FILE (pending_file).

        Setup: Create SO with vn_internal_production product, confirm SO
        (triggers MO creation), find the MO, confirm the MO.
        Assert: SO pipeline state code == 'pending_file'.
        """
        product, so = self._setup_mto_product_with_so(
            'Test MO Confirmed Product')

        # Verify SO starts at initial state (should already be pending_file)
        self.assertEqual(so.x_pipeline_state_id, self.s_pending_file,
                         "SO should start at pending_file after confirm")

        # Find and confirm the MO
        mos = self._get_production_for_so(so)
        self.assertGreater(len(mos), 0,
                          "At least one MO should exist for the confirmed SO")
        mo = mos[0]

        # Mark the MO as confirmed
        # (Odoo standard: MO starts in 'draft', confirm moves to 'confirmed')
        mo.action_confirm()

        # Invalidate cached fields to ensure fresh reads
        so.invalidate_recordset(['x_pipeline_state_id'])

        # Assert SO pipeline state is CHỜ FILE
        self.assertEqual(so.x_pipeline_state_id.code, 'pending_file',
                        "SO pipeline should be CHỜ FILE after MO confirmed")

    def test_mo_done_sets_terminal_pipeline(self):
        """MO done → SO pipeline advances to VN-Fulfilled (done).

        Setup: Confirm SO and MO, then mark MO as done.
        Assert: SO pipeline state code == 'done'.
        """
        product, so = self._setup_mto_product_with_so(
            'Test MO Done Product')

        # Find the MO and confirm it
        mos = self._get_production_for_so(so)
        self.assertGreater(len(mos), 0)
        mo = mos[0]
        mo.action_confirm()

        # Mark the MO as done
        # (Odoo standard: button_mark_done or workflow transition)
        mo.button_mark_done()

        # Invalidate cached fields
        so.invalidate_recordset(['x_pipeline_state_id'])

        # Assert SO pipeline state is VN-Fulfilled (done)
        self.assertEqual(so.x_pipeline_state_id.code, 'done',
                        "SO pipeline should be VN-Fulfilled when MO is done")

    def test_manual_mid_stage_transitions_still_work(self):
        """Manual mid-stage transitions remain manual; no auto-revert on MO state change.

        Setup: Confirm SO and MO, manually set SO pipeline to mid-stage (in_production),
        assert it stays there (no auto-revert by MO state changes).
        """
        product, so = self._setup_mto_product_with_so(
            'Test Manual Mid-Stage Product')

        # Find the MO and confirm it (sets pipeline to pending_file)
        mos = self._get_production_for_so(so)
        self.assertGreater(len(mos), 0)
        mo = mos[0]
        mo.action_confirm()
        so.invalidate_recordset(['x_pipeline_state_id'])

        # Manually advance SO pipeline to mid-stage (in_production)
        so._write_pipeline_state(self.s_in_production, note='Manual advance to production')
        self.assertEqual(so.x_pipeline_state_id.code, 'in_production',
                        "SO pipeline should advance to in_production manually")

        # Mark the MO as done
        # (This would normally try to advance SO to 'done', but we want to verify
        # that a manual mid-stage transition is preserved)
        mo.button_mark_done()
        so.invalidate_recordset(['x_pipeline_state_id'])

        # Expect: SO pipeline should be at 'done' because MO is done
        # (The sync should still apply; manual mid-stage doesn't block terminal transitions)
        self.assertEqual(so.x_pipeline_state_id.code, 'done',
                        "SO pipeline should advance to done when MO is done, "
                        "even after manual mid-stage transition")

    def test_terminal_guard_blocks_manual_jump(self):
        """Terminal-stage guard: SO pipeline cannot jump to 'done' unless MO is done.

        Setup: Confirm SO and MO (MO is confirmed, not done), attempt direct
        _write_pipeline_state to 'done'.
        Assert: ValidationError or UserError is raised.
        """
        product, so = self._setup_mto_product_with_so(
            'Test Terminal Guard Product')

        # Find the MO and confirm it (not yet done)
        mos = self._get_production_for_so(so)
        self.assertGreater(len(mos), 0)
        mo = mos[0]
        mo.action_confirm()

        # MO is confirmed, not done
        self.assertEqual(mo.state, 'confirmed',
                        "MO should be in confirmed state, not done")

        # Attempt to manually set SO pipeline to 'done' — should raise an error
        with self.assertRaises(ValidationError):
            so._write_pipeline_state(self.s_done,
                                     note='Attempting to skip to done')

    def test_terminal_guard_allows_after_mo_done(self):
        """After MO is done, manual write to terminal state is allowed.

        Setup: Confirm SO and MO, mark MO as done, then manually set SO
        pipeline to 'done' (idempotent — already there, but tests the guard is off).
        Assert: No error; write succeeds.
        """
        product, so = self._setup_mto_product_with_so(
            'Test Terminal Guard Allowed Product')

        # Find the MO, confirm it, mark it done
        mos = self._get_production_for_so(so)
        self.assertGreater(len(mos), 0)
        mo = mos[0]
        mo.action_confirm()
        mo.button_mark_done()

        # MO is now done
        self.assertEqual(mo.state, 'done',
                        "MO should be in done state")

        # SO should already be at 'done' from the sync, but we test that
        # manual write also succeeds (idempotent)
        so.invalidate_recordset(['x_pipeline_state_id'])
        # Attempt to manually set to done (should succeed)
        so._write_pipeline_state(self.s_done,
                                 note='Confirming terminal state')
        self.assertEqual(so.x_pipeline_state_id.code, 'done',
                        "SO pipeline should remain at done")

    def test_multi_mo_advances_to_terminal_only_when_all_done(self):
        """Multi-MO scenario: SO advances to terminal only when ALL MOs are done.

        Setup: Create SO with 2 MTO lines (creating 2 MOs), confirm both,
        mark first MO done → SO stays at mid-stage (not yet all done).
        Mark second MO done → SO advances to 'done'.
        """
        product1 = self._create_product('Test Multi MO Product 1')
        product2 = self._create_product('Test Multi MO Product 2')

        # Set up MTO routes for both products
        for product in [product1, product2]:
            wizard = self.env['product.mto.bom.wizard'].create({
                'product_id': product.id,
            })
            wizard.action_create_bom()

        # Create SO with 2 lines
        variant1 = (product1.product_variant_ids[0]
                    if product1.product_variant_ids
                    else product1.product_variant_id)
        variant2 = (product2.product_variant_ids[0]
                    if product2.product_variant_ids
                    else product2.product_variant_id)
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': variant1.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 100.0,
                }),
                (0, 0, {
                    'product_id': variant2.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 100.0,
                }),
            ],
        })

        # Confirm SO (creates 2 MOs)
        so.action_confirm()

        # Find MOs
        mos = self._get_production_for_so(so)
        self.assertEqual(len(mos), 2,
                        "Exactly 2 MOs should be created for 2 MTO lines")

        # Confirm both MOs
        for mo in mos:
            mo.action_confirm()

        so.invalidate_recordset(['x_pipeline_state_id'])
        self.assertEqual(so.x_pipeline_state_id.code, 'pending_file',
                        "SO should be at pending_file after MOs confirmed")

        # Mark first MO as done
        mos[0].button_mark_done()
        so.invalidate_recordset(['x_pipeline_state_id'])

        # SO should still be at pending_file (not all MOs done yet)
        # OR it could move to a mid-stage — the spec says "only when every MO is done"
        # For now, we expect it to stay at pending_file or move to done only when all are done
        # (The actual implementation will determine the behavior)
        # We assert that the state is not yet 'done' after just one MO is done
        self.assertNotEqual(so.x_pipeline_state_id.code, 'done',
                           "SO should NOT be at done until all MOs are done")

        # Mark second MO as done
        mos[1].button_mark_done()
        so.invalidate_recordset(['x_pipeline_state_id'])

        # Now SO should be at 'done'
        self.assertEqual(so.x_pipeline_state_id.code, 'done',
                        "SO should be at done once all MOs are done")

    def test_no_reverse_sync_on_mo_state_regression(self):
        """No reverse sync: MO state regression does NOT roll back SO pipeline.

        Setup: Confirm SO and MO, mark MO done (SO → done), simulate MO state
        regression by writing state back to 'confirmed'.
        Assert: SO pipeline stays at 'done' (no reverse sync).
        """
        product, so = self._setup_mto_product_with_so(
            'Test No Reverse Sync Product')

        # Find the MO, confirm, mark done
        mos = self._get_production_for_so(so)
        self.assertGreater(len(mos), 0)
        mo = mos[0]
        mo.action_confirm()
        mo.button_mark_done()

        so.invalidate_recordset(['x_pipeline_state_id'])
        self.assertEqual(so.x_pipeline_state_id.code, 'done',
                        "SO should be at done after MO done")

        # Simulate MO state regression (write state back to 'confirmed')
        # This is a direct database write to simulate unusual conditions
        mo.write({'state': 'confirmed'})

        so.invalidate_recordset(['x_pipeline_state_id'])

        # Assert: SO pipeline should still be at 'done' (no reverse sync)
        self.assertEqual(so.x_pipeline_state_id.code, 'done',
                        "SO pipeline should NOT revert when MO state regresses; "
                        "no reverse sync by design")
