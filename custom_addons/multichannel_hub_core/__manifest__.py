{
    'name': 'Multichannel Hub Core',
    'version': '19.0.1.0.52',
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
of the original etsy_integration monolith). Active — Phase 1 dashboards +
fulfillment delegation landed:

- P1-05: sale.order.fulfillment delegation mixin (ADR-007)
- P1-06: unified shipping.carrier model + 7-row seed (ADR-005)
- P1-01a: Order Dashboard + sales_channel + row decorations
- P1-02a: design.file MVP + 3-col kanban + 10MB cap
- P1-03: Tracking Dashboard + Mark-Shipped + bus.bus channel
- P1-DASH-MERGE: unified Operations Dashboard (ADR-DASH-MERGE)
- P1-LBL: label_status Selection -> Many2one + 16-record seed
- P1-01b: dashboard refactor sale.order -> sale.order.line + 34 Excel cols
- Remaining Phase 1+: design.file routing/GDrive/bulk-print, sync.health,
  Process Dashboard, carrier_detector
    """,
    'author': 'Etsy Migration Team',
    'website': 'https://github.com/baoha/odoo19_esty',
    'depends': [
        'sale_management',
        'stock',
        'stock_dropshipping',
        'mrp',
        'contacts',
        'mail',
    ],
    'data': [
        'security/multichannel_hub_security.xml',
        'security/ir.model.access.csv',
        'data/shipping_carrier_data.xml',
        'data/multichannel_sales_channel_seed.xml',
        'data/sku_family_seed.xml',
        'data/sku_attribute_seed.xml',
        'data/product_catalog_sequence.xml',
        'data/product_catalog_config_parameters.xml',
        'data/product_catalog_cron.xml',
        'views/multichannel_sync_health_views.xml',
        'data/label_status_data.xml',
        'data/order_pipeline_seed.xml',
        'data/order_pipeline_state_seed.xml',
        'data/mto_phantom_product_seed.xml',
        'data/ir_cron_data.xml',
        'views/operations_dashboard_views.xml',
        'data/operations_dashboard_saved_filters.xml',
        'views/menu.xml',
        'views/order_pipeline_views.xml',
        'views/shipping_carrier_views.xml',
        'views/design_file_views.xml',
        'views/design_file_route_views.xml',
        'views/design_file_upload_wizard.xml',
        'views/product_mto_bom_wizard_views.xml',
        'views/sale_order_form.xml',
        'wizards/multichannel_enquiry_close_wizard_views.xml',
        'wizards/product_creation_wizard_views.xml',
        'wizards/product_sku_builder_wizard_views.xml',
        'wizards/catalog_import_run_wizard_views.xml',
        'views/product_sku_drift_views.xml',
        'views/product_template_views.xml',
        'views/sku_family_views.xml',
        'views/multichannel_enquiry_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
