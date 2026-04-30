{
    'name': 'Multichannel Hub - Fulfillment',
    'version': '19.0.1.0.0',
    'category': 'Sales/Fulfillment',
    'summary': 'Fulfillment integration service for multichannel operations',
    'author': 'Etsy Migration Team',
    'depends': [
        # 'multichannel_hub_core',  # TEMP: Blocked by broken menu.xml load order. Restore after P1-xx fixes.
        'sale_management',  # Provides sale.order base
        'stock',
    ],
    'data': [
    ],
    'post_init_hook': 'post_init_create_acl_and_cron',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
