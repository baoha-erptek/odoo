{
    'name': 'Multichannel Hub - Fulfillment',
    'version': '19.0.1.0.0',
    'category': 'Sales/Fulfillment',
    'summary': 'Fulfillment integration service for multichannel operations',
    'author': 'Etsy Migration Team',
    'depends': [
        'multichannel_hub_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_gearment_api_log_retention.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
