"""P-ENH-ESTY-195 / ADR-016 — backfill multichannel.listing.etsy_shop_id.

Testable Python entry point. Odoo's standard discovery path at
``migrations/19.0.3.8.0/post-migrate.py`` is a thin shim that constructs
an ``Environment`` and delegates here. The underscore-prefixed mirror
gives us import-stability for Phase 2 ORM tests (dotted dir is not a
valid Python identifier).

Root cause being closed: ``multichannel.listing.etsy_shop_id`` is a new
typed Many2one introduced in 19.0.3.8.0. Existing listings carry a legacy
``shop_ref`` Char that the publisher's ``_resolve_listing_intent`` parses
by name-lookup. The typed FK needs the same backfill so the new computed
price-display widget can resolve the shop without re-parsing ``shop_ref``.
"""

from . import post_migrate  # noqa: F401
