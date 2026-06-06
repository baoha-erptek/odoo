"""Odoo discovery shim for P-LIST-MODEL backfill.

Odoo can't import a directory whose name contains dots
(``19.0.1.0.65`` is not a valid Python identifier), so the testable
helper lives in the sibling package ``_19_0_1_0_65/``. This shim does
the discovery file's only job: call ``backfill_listings(env)``.

Same pattern as the etsy_integration migration directories landed in
P-BUG-ESTY-188 iter1/iter2.
"""

from odoo.addons.multichannel_hub_core.migrations._19_0_1_0_65 import (
    backfill_listings,
)


def migrate(cr, version):
    from odoo.api import Environment
    from odoo import SUPERUSER_ID
    env = Environment(cr, SUPERUSER_ID, {})
    backfill_listings(env)
