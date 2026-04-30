# Multichannel Hub Fulfillment module
from . import models

# Import post_init hook for manifest registration
from .__post_init__ import post_init_create_acl_and_cron

# Expose at module level for Odoo to call
__all__ = ['post_init_create_acl_and_cron']
