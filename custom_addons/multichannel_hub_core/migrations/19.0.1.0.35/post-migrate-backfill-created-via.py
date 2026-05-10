"""P1-DESIGN-AUTO-CREATE-FROM-EMAIL — backfill design.file.created_via.

Adds the `created_via` Selection field to existing design.file rows.
Newly added column is NULL until the field default fills new rows; existing
rows must be marked explicitly. Mapping:

  - Rows with `is_seed=True` (historical backfill from
    `_seed_from_historical_lines`) -> `'migration_seed'`
  - All other existing rows (operator-created via the upload wizard before
    this slice landed) -> `'operator_wizard'`

Idempotent: safe to re-run. Only touches rows where created_via IS NULL.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill created_via for design.file rows missing the value."""
    cr.execute("""
        UPDATE design_file
           SET created_via = 'migration_seed'
         WHERE created_via IS NULL
           AND is_seed = TRUE
    """)
    seeded = cr.rowcount
    cr.execute("""
        UPDATE design_file
           SET created_via = 'operator_wizard'
         WHERE created_via IS NULL
    """)
    operator = cr.rowcount
    _logger.info(
        "design.file.created_via backfill: %s rows -> 'migration_seed', "
        "%s rows -> 'operator_wizard'",
        seeded, operator,
    )
