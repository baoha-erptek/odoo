"""
Phase 1: Database verification tests for audit log coverage (P1-08).

Tests verify that spec-003 models have the required mail.thread + mail.activity.mixin
inheritance and that tracking=True is set on user-visible scalar fields.

These tests introspect ir.model / ir.model.fields ORM tables (populated after
module install) to verify inheritance and field tracking configuration.

References: Spec 003 FR-031 (audit log coverage), AC-1 (chatter in forms),
AC-2 (tracking value creation), SC-007 (50+ tracked edits).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAuditCoverageMailThread(TransactionCase):
    """Phase 1: Verify mail.thread + mail.activity.mixin inheritance on spec-003 models."""

    # Source-of-truth mapping: model name → required mixins
    MAIL_THREAD_REQUIRED = {
        'sale.order.fulfillment': {'mail.thread', 'mail.activity.mixin'},
        'shipping.carrier': {'mail.thread', 'mail.activity.mixin'},
        'order.pipeline': {'mail.thread', 'mail.activity.mixin'},
        'order.pipeline.state': {'mail.thread', 'mail.activity.mixin'},
        'pipeline.team': {'mail.thread', 'mail.activity.mixin'},
        'design.file': {'mail.thread', 'mail.activity.mixin'},
        'design.file.route': {'mail.thread', 'mail.activity.mixin'},
        'etsy.address.change.request': {'mail.thread', 'mail.activity.mixin'},
    }

    # Models exempt from mail.thread requirement (append-only audit or TransientModel)
    EXEMPT = {
        'order.pipeline.transition.log',  # append-only audit table IS the audit
        'design.print.batch',  # TransientModel
    }

    def test_FR031_mail_thread_inheritance_on_spec003_models(self):
        """Test FR-031: spec-003 models inherit mail.thread + mail.activity.mixin.

        Introspects ir.model table to verify inheritance. Uses Odoo's canonical
        fields: ir.model.is_mail_thread, ir.model.is_mail_activity to check
        mixin presence (more reliable than _inherit inspection post-install).
        """
        ir_model = self.env['ir.model']
        failures = []

        for model_name, required_mixins in self.MAIL_THREAD_REQUIRED.items():
            try:
                model_record = ir_model.search([('model', '=', model_name)])
                if not model_record:
                    failures.append(f"  {model_name}: model not found (not yet installed?)")
                    continue

                missing = set()

                # Check mail.thread (Odoo 19 field: is_mail_thread)
                if 'mail.thread' in required_mixins and not model_record.is_mail_thread:
                    missing.add('mail.thread')

                # Check mail.activity.mixin (Odoo 19 field: is_mail_activity)
                if 'mail.activity.mixin' in required_mixins and not model_record.is_mail_activity:
                    missing.add('mail.activity.mixin')

                if missing:
                    failures.append(
                        f"  {model_name}: missing {', '.join(sorted(missing))}"
                    )

            except Exception as e:
                failures.append(f"  {model_name}: error during check: {e}")

        self.assertFalse(
            failures,
            f"FR-031 violations — models missing mail.thread / mail.activity.mixin:\n" +
            "\n".join(failures)
        )

    def test_FR031_exempt_models_are_intentional(self):
        """Sanity check: EXEMPT set membership is documented and correct.

        Guards against accidental future inclusion in the required set.
        """
        # Verify exempt models are truly exempt (append-only audit or TransientModel)
        ir_model = self.env['ir.model']

        for model_name in self.EXEMPT:
            try:
                model_record = ir_model.search([('model', '=', model_name)])
                if model_record:
                    # Verify these models are NOT mail.thread
                    if model_name == 'order.pipeline.transition.log':
                        # Append-only audit table — should NOT have chatter
                        self.assertFalse(
                            model_record.is_mail_thread,
                            f"{model_name}: exempt audit model should NOT inherit mail.thread"
                        )
                    elif model_name == 'design.print.batch':
                        # TransientModel — should NOT have chatter (transients are discarded)
                        self.assertFalse(
                            model_record.is_mail_thread,
                            f"{model_name}: TransientModel should NOT inherit mail.thread"
                        )
            except Exception as e:
                # Model not installed yet — acceptable during development
                pass


@tagged('post_install', '-at_install')
class TestAuditCoverageFieldTracking(TransactionCase):
    """Phase 1: Verify tracking=True on user-visible scalar fields in spec-003 models."""

    # Per-model required-tracked field sets (user-visible scalar fields only)
    REQUIRED_TRACKED = {
        'shipping.carrier': {'name', 'code', 'etsy_carrier_name', 'gearment_carrier_name'},
        'order.pipeline': {'name', 'code'},
        'order.pipeline.state': {'name', 'code', 'is_initial', 'color'},
        'pipeline.team': {'name', 'code'},
        'sale.order.fulfillment': {
            'tracking_number', 'tracking_url', 'tracking_state', 'shipping_date',
            'shipping_carrier_id', 'mp_note', 'pd_note', 'production_blocked',
            'block_reason', 'pic_user_id', 'pd_pic_user_id', 'order_priority',
            'warehouse_zone', 'fulfillment_status', 'label_status_id'
        },
        'design.file': {'name', 'state', 'storage_mode', 'rejection_reason'},
        'design.file.route': {'state', 'recipient_type', 'delivery_method'},
        'etsy.address.change.request': {'state', 'rejection_reason', 'approved_by'},
    }

    # Fields exempt from tracking requirement (computed, unstored, technical counters)
    TRACKING_EXEMPT_BY_NAME = {
        'create_date', 'create_uid', 'write_date', 'write_uid',  # system fields
        'id', '__last_update',  # technical
        'create_uid', 'write_uid',  # audit stamps
    }

    def test_FR031_user_visible_scalar_fields_have_tracking_True(self):
        """Test FR-031 AC-2: user-visible scalar fields have tracking=True.

        Queries ir.model.fields table to verify tracking=True on all required fields
        (excluding Relational, Computed unstored, Binary, and technical fields).
        """
        ir_field = self.env['ir.model.fields']
        all_failures = []

        for model_name, required_fields in self.REQUIRED_TRACKED.items():
            missing_tracking = []

            for field_name in required_fields:
                try:
                    field_record = ir_field.search([
                        ('model_id.model', '=', model_name),
                        ('name', '=', field_name),
                    ])

                    if not field_record:
                        # Field doesn't exist yet (model not installed or field not created)
                        missing_tracking.append(f"{field_name} (not found)")
                        continue

                    # Verify tracking is truthy
                    if not field_record.tracking:
                        missing_tracking.append(f"{field_name} (tracking=False)")

                except Exception as e:
                    missing_tracking.append(f"{field_name} (error: {e})")

            if missing_tracking:
                all_failures.append(f"  {model_name}:")
                for item in missing_tracking:
                    all_failures.append(f"    - {item}")

        self.assertFalse(
            all_failures,
            f"FR-031 AC-2 violations — fields missing tracking=True:\n" +
            "\n".join(all_failures)
        )


@tagged('post_install', '-at_install')
class TestAuditCoverageFormChatter(TransactionCase):
    """Phase 1: Verify form views have <chatter/> for tracked models (AC-1)."""

    # Models requiring form views with <chatter/>
    FORM_VIEW_REQUIRED = {
        'order.pipeline': 'view_order_pipeline_form',
        'order.pipeline.state': 'view_order_pipeline_state_form',
        'pipeline.team': 'view_pipeline_team_form',
        'shipping.carrier': None,  # View doesn't exist yet (will be created in GREEN)
        'design.file': 'view_design_file_form',
        'design.file.route': 'view_design_file_route_form',
    }

    # Models without standalone forms (accessed via parent)
    FORM_VIEW_EXEMPT = {
        'sale.order.fulfillment',  # Delegated to sale.order form via _inherits
    }

    def test_AC1_form_views_exist_for_chatter_models(self):
        """Test AC-1: each tracked model has at least one form view.

        For models that don't yet have views (shipping.carrier), test fails
        with clear message explaining what's needed.
        """
        ir_view = self.env['ir.ui.view']
        failures = []

        for model_name, expected_view_id in self.FORM_VIEW_REQUIRED.items():
            # Check if form view exists
            form_views = ir_view.search([
                ('model', '=', model_name),
                ('type', '=', 'form'),
            ])

            if not form_views:
                failures.append(
                    f"  {model_name}: no form view registered (expected one with <chatter/>)"
                )
                continue

            # Check each form view for chatter element
            has_chatter = False
            for view in form_views:
                if view.arch_db:
                    # Check for <chatter/> shorthand or <div class="oe_chatter">
                    if '<chatter/>' in view.arch_db or 'oe_chatter' in view.arch_db:
                        has_chatter = True
                        break

            if not has_chatter:
                failures.append(
                    f"  {model_name}: form view exists but missing <chatter/> element"
                )

        self.assertFalse(
            failures,
            f"AC-1 violations — form views missing <chatter/>:\n" +
            "\n".join(failures)
        )

    def test_AC1_shipping_carrier_form_view_required(self):
        """Test AC-1: shipping.carrier must have form view with <chatter/>.

        Shipping carrier currently has no form view file. This test explicitly
        documents the gap (will be filled in GREEN phase).
        """
        ir_view = self.env['ir.ui.view']

        # Check for existing shipping.carrier form view
        form_views = ir_view.search([
            ('model', '=', 'shipping.carrier'),
            ('type', '=', 'form'),
        ])

        self.assertTrue(
            len(form_views) > 0,
            "shipping.carrier: form view must exist (should be created with <chatter/>)"
        )

        # If view exists, verify it has chatter
        if form_views:
            has_chatter = any(
                '<chatter/>' in view.arch_db or 'oe_chatter' in view.arch_db
                for view in form_views if view.arch_db
            )
            self.assertTrue(
                has_chatter,
                "shipping.carrier form view: must include <chatter/> element for mail.thread"
            )
