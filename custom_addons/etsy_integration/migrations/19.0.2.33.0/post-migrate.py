"""Odoo discovery shim for P-BUG-ESTY-188 readiness-state bootstrap.

Odoo scans ``migrations/<version>/<phase>-<name>.py`` by filename and looks
for ``migrate(cr, version)``. The actual logic lives in the importable
sibling package ``migrations/_19_0_2_33_0/`` so Phase 2 ORM tests can call it
directly without going through Odoo's upgrade pipeline.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.etsy_integration.migrations._19_0_2_33_0 import post_migrate


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    post_migrate(cr, env)
