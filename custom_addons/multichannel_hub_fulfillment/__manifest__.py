{
    'name': 'Multichannel Hub - Fulfillment',
    'version': '19.0.1.0.6',
    'category': 'Sales/Fulfillment',
    'summary': 'Fulfillment integration service for multichannel operations',
    'author': 'Etsy Migration Team',
    'depends': [
        'multichannel_hub_core',
    ],
    'data': [
        'security/tracking_import_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_gearment_api_log_retention.xml',
        'data/ir_cron_gearment_retry.xml',
        'data/tracking_import_data.xml',
        'views/tracking_import_views.xml',
    ],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
