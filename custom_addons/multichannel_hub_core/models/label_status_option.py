"""label.status.option — configurable master data for sale.order.fulfillment.label_status.

Replaces the fixed Selection field on sale.order.fulfillment with a Many2one
to this model so BA-manager can edit label codes without code releases.

Slice: P1-LBL (Owner directive D2, 2026-05-10).
Spec: specs/003-dashboard-design-multichannel/p1-lbl-plan.md
Seed: 16 records derived from .0temp/2026-05-10_093634.jpg.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


_logger = logging.getLogger(__name__)


def _check_ba_manager_or_raise(env):
    """Raise AccessError if env.user lacks BA-manager (or system) role.

    Module-level helper so sale.order.fulfillment can reuse the same
    gate without circular-import risk. Mirrors the pattern from
    multichannel_hub_fulfillment.models.logistics_partner._check_ba_manager_or_raise.
    """
    user = env.user
    if (user.has_group('multichannel_hub_core.group_ba_manager')
            or user.has_group('base.group_system')):
        return
    raise AccessError(
        _("Editing label statuses requires BA Manager role."))


class LabelStatusOption(models.Model):
    _name = 'label.status.option'
    _description = 'Label Status Option (master data)'
    _inherit = ['mail.thread']
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
        tracking=True,
        help="Operator-visible label, displayed on the Operations Dashboard.",
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help="xmlid-friendly identifier (lowercase, snake_case). "
             "Used in views, server actions, and bus payloads.",
    )
    color = fields.Integer(
        string='Color',
        default=0,
        tracking=True,
        help="Kanban color index (0–15) per Odoo standard palette.",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        tracking=True,
    )
    bucket = fields.Selection(
        [
            ('target', 'MP target'),
            ('pd_selfmake', 'PD self-make'),
            ('done', 'Done'),
            ('approval', 'Approval'),
        ],
        string='Bucket',
        required=True,
        tracking=True,
        help="Coarse grouping reflected on the dashboard kanban + filters.",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )

    _sql_constraints = [
        # Declarative form — also enforced via init() raw SQL because
        # _sql_constraints UNIQUE has been observed to silently fail to
        # deploy on this codebase (drift template 9th confirmation; see
        # memory project_sql_constraints_drift.md and design_file.py:144).
        (
            'label_status_option_code_unique',
            'UNIQUE(code)',
            'A label status with this code already exists.',
        ),
        (
            'label_status_option_name_unique',
            'UNIQUE(name)',
            'A label status with this name already exists.',
        ),
    ]

    def init(self):
        """Drift-template raw-SQL UNIQUE mirror.

        pg_constraint IF NOT EXISTS pre-check (NOT EXCEPTION clause —
        PG raises duplicate_table 42P07 not duplicate_object 42710 on
        re-run).
        """
        self.env.cr.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                     WHERE conname = 'label_status_option_code_unique'
                ) THEN
                    ALTER TABLE label_status_option
                    ADD CONSTRAINT label_status_option_code_unique
                    UNIQUE (code);
                END IF;
            END $$;
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        if any('code' in v or 'name' in v or 'bucket' in v for v in vals_list):
            _check_ba_manager_or_raise(self.env)
        return super().create(vals_list)

    def write(self, vals):
        if {'code', 'name', 'bucket', 'active'} & set(vals.keys()):
            _check_ba_manager_or_raise(self.env)
        return super().write(vals)

    def unlink(self):
        _check_ba_manager_or_raise(self.env)
        return super().unlink()

    @api.model
    def _post_migrate_default_null_rows(self):
        """T-LBL-10 — default fulfillment rows with NULL label_status_id to 'Chờ duyệt'.

        Importable from the migration script; also callable from tests.
        Returns the count of rewritten rows (0 if none).
        """
        target = self.env.ref(
            'multichannel_hub_core.label_status_cho_duyet',
            raise_if_not_found=True,
        )
        cr = self.env.cr
        cr.execute(
            "SELECT id FROM sale_order_fulfillment "
            "WHERE label_status_id IS NULL"
        )
        ids = [row[0] for row in cr.fetchall()]
        if not ids:
            _logger.debug(
                "P1-LBL migration: no NULL label_status_id rows found")
            return 0
        cr.execute(
            "UPDATE sale_order_fulfillment "
            "SET label_status_id = %s "
            "WHERE label_status_id IS NULL",
            (target.id,),
        )
        _logger.warning(
            "P1-LBL migration: rewrote %d sale.order.fulfillment rows "
            "to default 'Chờ duyệt' (id=%s); audit list: %s",
            len(ids), target.id, ids,
        )
        return len(ids)
