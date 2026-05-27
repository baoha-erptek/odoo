"""Migration 19.0.1.0.56 — P-PUB-PRICING-STANDARDISE.

Migrate custom x_listing_price field to standard list_price field.
Copy non-zero x_listing_price values to list_price for data continuity.
"""


def migrate(cr, version):
    """Copy non-zero x_listing_price to list_price for backward compat.

    After this migration, x_listing_price becomes a computed field that
    returns list_price. This preserves existing price data.
    """
    # Check if x_listing_price column exists (may not on fresh installs)
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'product_template'
            AND column_name = 'x_listing_price'
        );
    """)
    if not cr.fetchone()[0]:
        return  # Column doesn't exist; nothing to migrate

    # Copy non-zero x_listing_price values to list_price
    cr.execute("""
        UPDATE product_template
        SET list_price = x_listing_price
        WHERE x_listing_price IS NOT NULL
        AND x_listing_price > 0
        AND (list_price IS NULL OR list_price = 0);
    """)
