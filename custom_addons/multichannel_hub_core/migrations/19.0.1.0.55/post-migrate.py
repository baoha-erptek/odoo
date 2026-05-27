"""Post-migration for P-HUB-SKU-AUTODERIVE (Spec 009).

Populates product_category.x_sku_family_id on existing rows via best-effort
name matching against mhc_sku_family.code. Unmatched categories are left
with NULL and flagged for manual review in findings.md.

Spec 009 P-HUB-SKU-AUTODERIVE: seed x_sku_family_id on existing product.category
rows via migrations/19.0.1.0.55/post-migrate.py (best-effort name match against
mhc.sku.family.code; unmatched rows flagged for manual review).
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate x_sku_family_id on existing product.category rows.

    Best-effort matching: category.name (case-insensitive) against
    mhc.sku.family.code.
    """
    if version is None:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Fetch all families to build a name→id map
    families = env['mhc.sku.family'].search([])
    family_map = {}
    for fam in families:
        # Map both code and name to family id
        family_map[fam.code.lower()] = fam.id
        if fam.name:
            family_map[fam.name.lower()] = fam.id

    # Fetch all categories without a family set
    categories = env['product.category'].search([
        ('x_sku_family_id', '=', False),
    ])

    matched = 0
    unmatched = []

    for cat in categories:
        cat_name_lower = (cat.name or '').lower().strip()
        if not cat_name_lower:
            unmatched.append(cat.id)
            continue

        # Exact match on code/name
        matched_family_id = family_map.get(cat_name_lower)

        if matched_family_id:
            cat.x_sku_family_id = matched_family_id
            matched += 1
        else:
            unmatched.append(cat.id)

    env.cr.commit()

    # Log summary
    _logger.info(
        'P-HUB-SKU-AUTODERIVE: seeded x_sku_family_id on %d categories. '
        'Unmatched: %d category IDs %s. Manual review needed for unmatched rows.',
        matched, len(unmatched), unmatched,
    )
