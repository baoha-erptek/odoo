{
    'name': 'Multichannel Hub Core',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Foundation models and services shared across all sales channels and fulfillment partners',
    'description': """
Multichannel Hub Core
=====================
Foundation module for the multichannel order pipeline. Hosts the shared
building blocks consumed by per-channel modules (etsy_channel, future
amazon_channel, website_channel) and by the fulfillment module
(multichannel_hub_fulfillment).

This is the first module landed under ADR-003 (four-module decomposition
of the original etsy_integration monolith). The module is currently an
empty installable skeleton; subsequent slices will populate it:

- P1-05: sale.order.fulfillment delegation mixin (ADR-007)
- P1-06: unified shipping.carrier model + initial seed (ADR-005)
- Phase 1+: order.design.file, dashboards, sync.health, carrier_detector
    """,
    'author': 'Etsy Migration Team',
    'website': 'https://github.com/baoha/odoo19_esty',
    'depends': [
        'sale_management',
        'stock',
        'contacts',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
