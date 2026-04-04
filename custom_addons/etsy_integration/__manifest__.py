{
    'name': 'Etsy Integration',
    'version': '19.0.1.0.0',
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
- Customer deduplication (email > name+zip)
- Product auto-creation with Etsy image download
- Historical order import from Excel
- Parse failure monitoring and raw email audit trail
- Design queue for personalized orders
    """,
    'author': 'Etsy Migration Team',
    'depends': [
        'sale_management',
        'stock',
        'contacts',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/etsy_security.xml',
        'data/ir_cron_data.xml',
        'views/etsy_design_queue_views.xml',
        'views/etsy_dashboard_views.xml',
        'views/menu.xml',
        'views/etsy_shop_views.xml',
        'views/etsy_email_log_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/import_orders_wizard_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/oauth_templates.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
