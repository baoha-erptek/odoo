"""etsy.shop GDrive folder cache extension (P1-09).

Extends etsy.shop with x_gdrive_design_folder_id to avoid repeating Drive API
queries for folder discovery/creation per shop, per year.
"""
from odoo import fields, models


class EtsyShopGdrive(models.Model):
    _inherit = 'etsy.shop'

    x_gdrive_design_folder_id = fields.Char(
        string='GDrive Design Folder ID',
        help='Cached GDrive folder ID for design uploads (internal system field)',
    )
