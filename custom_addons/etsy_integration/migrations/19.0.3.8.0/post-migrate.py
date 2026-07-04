"""Odoo discovery shim for P-ENH-ESTY-195 etsy_shop_id backfill.

Logic lives in the importable sibling package
``migrations/_19_0_3_8_0/`` so Phase 2 ORM tests can call it directly.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.etsy_integration.migrations._19_0_3_8_0.post_migrate import post_migrate


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    post_migrate(cr, env)
