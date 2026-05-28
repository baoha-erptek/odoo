"""Migration 19.0.2.15.0 — convert etsy_shop publisher default IDs from int4 to varchar.

Real Etsy IDs are int64 — e.g. shipping_profile_id=285149016922 overflows PG
int4 by 100x. The Integer→Char model change accompanies this migration.

Pre-migrate runs before Odoo updates the schema from the new field definitions,
so we explicitly ALTER the columns first. USING <col>::text preserves any
existing values (they fit varchar trivially since they fit int4 by definition
before the change).

Idempotent: skips if the column is already varchar (e.g. running --reinit or
on a fresh DB where the new model already created varchar columns).
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'etsy_shop'
          AND column_name IN (
              'default_taxonomy_id',
              'default_shipping_profile_id',
              'default_return_policy_id'
          )
    """)
    rows = {r[0]: r[1] for r in cr.fetchall()}
    for col, dtype in rows.items():
        if dtype == 'integer':
            cr.execute(
                f'ALTER TABLE etsy_shop ALTER COLUMN {col} TYPE varchar USING {col}::text'
            )
