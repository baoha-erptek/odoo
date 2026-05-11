"""Tests for P1-DESIGN-WIZ-ATTACH-SCOPE — attachment-ownership gate.

Defense-in-depth follow-up to P1-DESIGN-MULTI-UPLOAD: ensure
`design.file.upload.wizard._do_upload_for_attachment` only accepts
attachments that the current user owns OR that were auto-created by
the wizard's own many2many_binary widget (`res_model == 'design.file.upload.wizard'`).

Threat model: production-team user A uploads a file via the wizard; the
many2many_binary widget creates an `ir.attachment` row owned by user A.
A second production-team user B should not be able to construct a
wizard with user A's pre-existing attachment and submit it. Odoo's base
`ir.attachment` record rules already filter out cross-tenant reads on
M2M descriptors, but FR-017 defense-in-depth (memory
`feedback_fr017_write_defense_in_depth.md`) demands an explicit per-model
ownership gate so that any upstream bypass (e.g., a future sudo() write
path or a relaxed record rule) cannot smuggle attachments into a
production-team user's design pipeline.

Test strategy:
- Positive integration test: user A uploads their own attachment via
  ``action_upload`` end-to-end → succeeds.
- Gate-logic unit tests: call ``_do_upload_for_attachment`` directly with
  attachments constructed via sudo (simulates the bypass) and verify the
  gate raises AccessError on cross-user / accepts the wizard res_model
  carve-out.
- Atomicity is already covered by the FR-017 gate test in the sibling
  file ``test_design_file_upload_wizard_multi.py``; not repeated here.
"""

import base64
import logging

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)

# 2x2 white JPEG — RGB mode (canonical fixture from sibling tests).
_JPEG_2X2 = base64.b64decode(
    b'/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgKCQoMFA0MCwsMGRITDxQdGh8eHRoc'
    b'HCAkLicgIiwjHBwoNykuMDE0NDQfJzk9ODI8LjM0Mv/bAEMBCQkJDAsMGA0NGDIhHCEyMjIy'
    b'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAID'
    b'ASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIE'
    b'AwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRol'
    b'JicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKT'
    b'lJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx'
    b'8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQD'
    b'BAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcY'
    b'GRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImK'
    b'kpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq'
    b'8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=='
)


@tagged('post_install', '-at_install')
class TestDesignFileUploadWizardAttachScope(TransactionCase):
    """Phase 2 — attachment-ownership gate behavior (P1-DESIGN-WIZ-ATTACH-SCOPE)."""

    @classmethod
    def setUpClass(cls):
        """Two production-team users + minimal sale.order fixture."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        prod_team_group = cls.env.ref(
            'multichannel_hub_core.group_production_team'
        )
        cls.user_a = cls.env['res.users'].create({
            'name': 'Attach Scope User A',
            'login': 'attach_scope_user_a@example.com',
            'group_ids': [(6, 0, [prod_team_group.id])],
        })
        cls.user_b = cls.env['res.users'].create({
            'name': 'Attach Scope User B',
            'login': 'attach_scope_user_b@example.com',
            'group_ids': [(6, 0, [prod_team_group.id])],
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Attach Scope',
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
        })

    def _make_owned_attachment(self, owner_user, name='design.jpg', res_model=False, res_id=0):
        """Create an orphan ir.attachment under owner_user's session.

        Uses ``with_user(owner_user).create()`` (NOT sudo) so the auto-stamped
        ``create_uid`` is owner_user — sudo would stamp superuser. Orphan
        attachments (no res_model) bypass the linked-record write check at
        ``ir.attachment.create``.
        """
        return self.env['ir.attachment'].with_user(owner_user).create({
            'name': name,
            'type': 'binary',
            'datas': base64.b64encode(_JPEG_2X2),
            'res_model': res_model or False,
            'res_id': res_id,
        })

    def _make_wizard_for(self, caller_user):
        """Construct a wizard bound to caller_user's env (no attachment_ids
        assignment — direct gate tests don't need the M2M)."""
        return self.env['design.file.upload.wizard'].with_user(caller_user).create({
            'order_id': self.order.id,
            'file_name': 'attach_scope_test',
            'storage_mode': 'small',
        })

    def test_upload_own_attachment_succeeds_end_to_end(self):
        """Positive integration: user A uploads an attachment owned by user A
        via action_upload → succeeds, one design.file row created."""
        attachment = self._make_owned_attachment(self.user_a, name='own.jpg')

        wizard = self.env['design.file.upload.wizard'].with_user(self.user_a).create({
            'order_id': self.order.id,
            'file_name': 'attach_scope_own',
            'storage_mode': 'small',
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        wizard.action_upload()

        design_files = self.env['design.file'].sudo().search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'own.jpg'),
        ])
        self.assertEqual(len(design_files), 1)
        self.assertEqual(design_files[0].state, 'pending')

    def test_gate_blocks_cross_user_attachment(self):
        """Direct gate-logic test: when the gate sees an attachment owned by
        a different user (no res_model carve-out), it raises AccessError.

        Constructs the cross-user attachment via sudo (simulates an upstream
        bypass of base ir.attachment record rules — the realistic threat
        model). Calls _do_upload_for_attachment directly so M2M filtering
        cannot pre-empt the gate.
        """
        # Attachment owned by user A (verified via with_user)
        attachment = self._make_owned_attachment(
            self.user_a, name='cross_user.jpg'
        )
        # Wizard bound to user B's env
        wizard = self._make_wizard_for(self.user_b)
        # sudo() the attachment recordset so user B's env can iterate it
        # (simulates the upstream bypass)
        attachment_in_user_b_env = attachment.sudo().with_user(self.user_b)

        with self.assertRaises(AccessError):
            wizard._do_upload_for_attachment(attachment_in_user_b_env)

        # Atomic: zero design.file rows created
        design_files = self.env['design.file'].sudo().search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'cross_user.jpg'),
        ])
        self.assertEqual(len(design_files), 0)

    def test_gate_allows_wizard_res_model_carve_out(self):
        """Carve-out: attachment with res_model='design.file.upload.wizard' AND
        res_id pointing at the CURRENT wizard is accepted regardless of
        create_uid mismatch (the many2many_binary widget creates these on
        behalf of any production-team user driving the wizard form)."""
        wizard = self._make_wizard_for(self.user_b)
        attachment = self._make_owned_attachment(
            self.user_a,
            name='wizard_scoped.jpg',
            res_model='design.file.upload.wizard',
            res_id=wizard.id,
        )
        attachment_in_user_b_env = attachment.sudo().with_user(self.user_b)

        # Should NOT raise — carve-out allows
        wizard._do_upload_for_attachment(attachment_in_user_b_env)

        design_files = self.env['design.file'].sudo().search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'wizard_scoped.jpg'),
        ])
        self.assertEqual(
            len(design_files),
            1,
            "Carve-out for res_model='design.file.upload.wizard' (with matching res_id) must allow upload.",
        )

    def test_gate_rejects_orphan_with_wizard_res_model_spoofed(self):
        """Bypass-attempt regression: an attacker writes
        res_model='design.file.upload.wizard' on an orphan attachment they
        own and donates it to another user's wizard. Must be rejected.

        Surfaced by security-reviewer on this slice (CRITICAL-1):
        the original carve-out condition was just
        ``res_model == 'design.file.upload.wizard'`` and would have accepted
        any attachment with that res_model regardless of res_id — letting an
        attacker re-tag an orphan attachment to bypass the gate. Tightened
        carve-out requires ``res_id == self.id`` (the current wizard)."""
        wizard = self._make_wizard_for(self.user_b)
        # User A crafts an attachment whose res_model spoofs the wizard
        # but res_id is 0 (orphan) or points at a different wizard (not self.id).
        attachment = self._make_owned_attachment(
            self.user_a,
            name='spoofed_orphan.jpg',
            res_model='design.file.upload.wizard',
            res_id=0,  # NOT pointing at the current wizard
        )
        attachment_in_user_b_env = attachment.sudo().with_user(self.user_b)

        with self.assertRaises(AccessError):
            wizard._do_upload_for_attachment(attachment_in_user_b_env)

        design_files = self.env['design.file'].sudo().search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'spoofed_orphan.jpg'),
        ])
        self.assertEqual(len(design_files), 0)

    def test_gate_allows_caller_owned_attachment(self):
        """Positive control for the gate: when env.user owns the attachment,
        the gate does NOT raise."""
        attachment = self._make_owned_attachment(self.user_a, name='own_direct.jpg')
        wizard = self._make_wizard_for(self.user_a)

        # Should NOT raise — caller is the owner
        wizard._do_upload_for_attachment(attachment)

        design_files = self.env['design.file'].sudo().search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'own_direct.jpg'),
        ])
        self.assertEqual(len(design_files), 1)
