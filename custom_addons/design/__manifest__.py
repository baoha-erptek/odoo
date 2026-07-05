# ESTY-244 — Design order module.
{
    'name': 'Design Orders',
    'version': '19.0.1.1.0',
    'category': 'Sales/Design',
    'summary': 'Independent design-order document (phiếu design) with its own '
               'approval flow, auto-created from sale orders.',
    'description': """
Design Orders (ESTY-244)
========================
Promotes design work into a first-class document (``design.order``) with its
own number, statusbar and chatter — parallel to ``sale.order`` /
``mrp.production``.

- Config toggle (default ON): confirming a sale order auto-creates a design
  order and links the order's existing design files to it.
- On approval ('Duyệt') the linked sale order advances to the ``design_ready``
  pipeline stage and every approved design file is attached to the linked
  manufacturing order(s).
- ESTY-249: the manufacturing order (``mrp.production``) surfaces an
  informational 'Design Ready' badge + smart button (computed from the linked
  design order's approval), so production sees readiness without a new MO state.

Depends on ``multichannel_hub_core`` (owns ``design.file``, the pipeline model
and ``group_production_team``). See ADR-019 for the module-topology decision
(design sits ON TOP of mhc; the legacy ``design.file`` storage code is not
physically relocated).
""",
    'author': 'ERPTEK',
    'website': 'https://github.com/baoha/odoo19_esty',
    'depends': [
        'multichannel_hub_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/design_security.xml',
        'data/design_order_sequence.xml',
        'data/design_config_params.xml',
        'data/design_pipeline_state_seed.xml',
        'views/design_order_views.xml',
        'views/mrp_production_views.xml',
        'views/design_menu.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
