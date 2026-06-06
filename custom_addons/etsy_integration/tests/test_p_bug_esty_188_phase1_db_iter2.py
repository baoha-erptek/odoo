"""
Phase 1 Database Verification Tests for P-BUG-ESTY-188 Iteration 2: Currency Conversion.

Tests verify data structure (columns, indexes, constraints, migration files) at the database level.
This phase ensures the new listing_currency_id field and migration 19.0.2.34.0 exist
before Phase 2 ORM tests run.

Scope:
1. listing_currency_id field: Many2one to res.currency (stored as integer FK)
2. FK constraint: etsy_shop.listing_currency_id → res_currency(id)
3. Migration 19.0.2.34.0: both post-migrate.py and _19_0_2_34_0/__init__.py files exist
   with callable post_migrate function

RED: These tests FAIL because:
- Field listing_currency_id does not yet exist on etsy.shop (Phase 3 GREEN adds it)
- Migration files do not yet exist (Phase 3 GREEN writes them)
"""

import importlib
import logging
import os

from odoo.tests.common import TransactionCase, tagged
import odoo

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p_bug_esty_188_iter2')
class TestP_BUG_ESTY_188_Phase1_DB_Columns(TransactionCase):
    """Phase 1: Verify listing_currency_id column and FK constraint on database.

    RED: Column does not exist; FK constraint does not exist.
    GREEN will add the field via migration.
    """

    def test_listing_currency_id_column_exists(self):
        """RED: listing_currency_id column does not yet exist on etsy_shop table.

        Expected RED reason: psql query returns 0 rows or AssertionError on fetchone.
        """
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'listing_currency_id'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "listing_currency_id column must exist on etsy_shop table"
        )
        # Many2one stores as integer (FK to res_currency.id)
        self.assertEqual(
            result[1],
            'integer',
            "listing_currency_id must be integer (Many2one FK to res_currency)"
        )

    def test_listing_currency_id_fk_constraint_exists(self):
        """RED: FK constraint from etsy_shop.listing_currency_id → res_currency.id missing.

        Expected RED reason: psql referential_constraints query returns 0 rows or AssertionError.
        """
        self.env.cr.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'etsy_shop'
              AND constraint_type = 'FOREIGN KEY'
              AND constraint_name LIKE '%listing_currency_id%'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "FK constraint must exist from etsy_shop.listing_currency_id → res_currency.id"
        )


@tagged('post_install', '-at_install', 'p_bug_esty_188_iter2')
class TestP_BUG_ESTY_188_Phase1_Migration_Files(TransactionCase):
    """Phase 1: Verify migration 19.0.2.34.0 files exist and are importable.

    RED: Migration files do not exist.
    GREEN will create migrations/19.0.2.34.0/post-migrate.py and
    migrations/_19_0_2_34_0/__init__.py with callable post_migrate function.
    """

    def test_migration_19_0_2_34_0_files_exist(self):
        """RED: Migration directory and files missing.

        Expected RED reason: ImportError or ModuleNotFoundError when importing
        the underscored package or AssertionError if post_migrate is not callable.
        """
        # Verify both directory structures exist
        base = os.path.dirname(odoo.addons.etsy_integration.__file__)
        dotted_path = os.path.join(base, 'migrations', '19.0.2.34.0', 'post-migrate.py')
        underscored_path = os.path.join(base, 'migrations', '_19_0_2_34_0')

        self.assertTrue(
            os.path.exists(dotted_path),
            f"Dotted migration file missing: {dotted_path}"
        )
        self.assertTrue(
            os.path.isdir(underscored_path),
            f"Underscored package directory missing: {underscored_path}"
        )

        # Verify __init__.py exists in underscored package
        init_path = os.path.join(underscored_path, '__init__.py')
        self.assertTrue(
            os.path.exists(init_path),
            f"Underscored package __init__.py missing: {init_path}"
        )

        # Verify post_migrate is importable and callable
        try:
            mod = importlib.import_module('odoo.addons.etsy_integration.migrations._19_0_2_34_0')
        except ModuleNotFoundError:
            self.fail(
                "Migration package _19_0_2_34_0 not importable; "
                "ensure __init__.py exists and is syntactically correct"
            )

        post_migrate_func = getattr(mod, 'post_migrate', None)
        self.assertIsNotNone(
            post_migrate_func,
            "_19_0_2_34_0.__init__.py must expose callable post_migrate(cr, env)"
        )
        self.assertTrue(
            callable(post_migrate_func),
            "post_migrate must be callable"
        )
