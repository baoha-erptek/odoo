"""Migration 19.0.2.30.0 — apply Etsy variation-property defaults to existing DBs.

`data/etsy_attribute_defaults.xml` is noupdate="1" so admin edits persist. But
on DBs where the seeded product.attribute rows pre-existed the introduction of
that file, the `-u` load skipped the noupdate records and the
x_publish_as_property / x_etsy_property_id / x_etsy_property_name values were
NEVER applied (confirmed on staging 2026-05-28: every axis publish=False). With
those unset, push_inventory emits no variation property_values and Etsy listings
get a single empty offering instead of real variations.

This migration writes the intended config idempotently for existing records,
matching data/etsy_attribute_defaults.xml. Fresh installs still get it from the
seed at first load; this only repairs already-installed DBs.

Property IDs were discovered via the Etsy seller-taxonomy properties endpoint
for JaHandmadeArt and verified live (Primary color=200 accepts free-text value
names; Custom1=513 is the size-slot custom property). property_name is REQUIRED
by Etsy's inventory PUT.
"""

from odoo import api, SUPERUSER_ID

# xmlid -> (x_publish_as_property, x_etsy_property_id, x_etsy_property_name)
_CONFIG = {
    'multichannel_hub_core.attribute_color': (True, '200', 'Primary color'),
    'multichannel_hub_core.attribute_shape': (True, '513', 'Shape'),
    'multichannel_hub_core.attribute_size': (True, '513', 'Size'),
    'multichannel_hub_core.attribute_fluid_oz': (True, '513', 'Fluid oz'),
    'multichannel_hub_core.attribute_apparel_size': (True, '513', 'Apparel size'),
    # Material is conveyed via the listing-level materials[] array, not a
    # variation property — keep it out of property_values.
    'multichannel_hub_core.attribute_material': (False, False, False),
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, (publish, pid, pname) in _CONFIG.items():
        attr = env.ref(xmlid, raise_if_not_found=False)
        if not attr:
            continue
        attr.write({
            'x_publish_as_property': publish,
            'x_etsy_property_id': pid,
            'x_etsy_property_name': pname,
        })
