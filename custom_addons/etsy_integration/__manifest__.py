{
    'name': 'Etsy Integration',
    'version': '19.0.2.13.0',
    'category': 'Sales',
    'summary': 'Import Etsy orders from Gmail notifications into Odoo sale orders',
    'description': """
Etsy Order Integration
======================
Monitors a Gmail inbox for Etsy order notification emails, parses them using
regex patterns, and creates sale.order records with full customer, product,
and shipping data.

Features:
- Automated email fetching via Gmail API (OAuth2)
- Regex-based email parsing for 34 order fields
- Multi-shop support with dynamic shop creation
- 3-tier customer deduplication (email > normalized name+address+city+zip > name+zip)
- Product auto-creation as storable with keyword-based category assignment
- Historical order import from Excel
- Parse failure monitoring and raw email audit trail
- Design queue for personalized orders
- ISO state-code-first resolution; ~50 country-name overrides for buyer-country variations
    """,
    'author': 'Etsy Migration Team',
    'depends': [
        'sale_management',
        'stock',
        'contacts',
        'mail',
        'multichannel_hub_core',
    ],
    'data': [
        'security/etsy_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/ir_config_parameter.xml',
        'data/etsy_shipping_product.xml',
        'data/etsy_fiscal_data.xml',
        'data/etsy_product_categories.xml',
        'views/etsy_design_queue_views.xml',
        'views/etsy_dashboard_views.xml',
        'views/menu.xml',
        'views/etsy_sync_health_views.xml',
        'views/etsy_shop_views.xml',
        'views/etsy_listing_product_views.xml',
        'views/etsy_email_log_views.xml',
        'views/etsy_api_log_views.xml',
        'views/sale_order_views.xml',
        'views/etsy_address_change_request_views.xml',
        'views/res_config_settings_views.xml',
        'views/import_orders_wizard_views.xml',
        'views/data_migration_wizard_views.xml',
        'wizards/etsy_listing_backfill_wizard_views.xml',
        'wizards/etsy_publish_wizard_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/oauth_templates.xml',
        'views/multichannel_enquiry_etsy_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
