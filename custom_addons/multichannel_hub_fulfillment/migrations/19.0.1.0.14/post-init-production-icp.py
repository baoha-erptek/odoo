"""Post-init migration for 19.0.1.0.14 — initialize production-locations ICP.

P2-03: ensures the ICP key exists with an empty JSON object so the hook's
ICP-read path encounters a valid (if empty) JSON document on first invocation
rather than False/None. The data file declares the same default, but
post-init avoids overwriting an operator-populated value during -u upgrades.
"""


def migrate(cr, version):
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        SELECT 'multichannel_hub_fulfillment.production_locations',
               '{}',
               NOW() AT TIME ZONE 'UTC',
               NOW() AT TIME ZONE 'UTC'
        WHERE NOT EXISTS (
            SELECT 1 FROM ir_config_parameter
            WHERE key = 'multichannel_hub_fulfillment.production_locations'
        )
        """
    )
