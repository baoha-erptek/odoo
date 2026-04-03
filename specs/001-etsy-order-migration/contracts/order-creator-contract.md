# Contract: Order Creator Service

**Module**: `addons/etsy_integration/services/order_creator.py`
**Type**: Odoo ORM service (depends on Odoo environment)

## Interface

### Functions

```python
class OrderCreator:
    def __init__(self, env):
        """Initialize with Odoo environment (self.env from a model method)."""

    def process_parse_result(self, parse_result: ParseResult, email_log_id: int) -> sale.order | None:
        """
        Main entry point. Creates or skips an order from a ParseResult.
        Returns the created sale.order record or None if skipped (duplicate).
        Links to the email log record.
        """

    def find_or_create_partner(self, shipping: ShippingAddress, buyer_name: str) -> res.partner:
        """
        Find existing partner by:
          1. Email match (if email provided)
          2. Name + ZIP match (fallback)
        Create new partner if no match found.
        Sets is_etsy_customer=True on new partners.
        Returns partner record.
        """

    def find_or_create_product(self, product_name: str, image_url: str) -> product.product:
        """
        Find existing product by exact name match.
        Create new product if not found.
        Sets is_etsy_product=True, etsy_image_url on new products.
        Returns product record.
        """

    def find_or_create_shop(self, shop_name: str) -> etsy.shop:
        """
        Find existing shop by name.
        Create new shop if not found.
        Returns shop record.
        """

    def is_duplicate_transaction(self, transaction_id: str) -> bool:
        """Check if a sale.order.line with this etsy_transaction_id exists."""

    def is_duplicate_order(self, order_id: str) -> bool:
        """Check if a sale.order with this etsy_order_id exists."""
```

## Behavior

1. **Atomicity**: Each `process_parse_result` call runs in a single database transaction. If any record creation fails, the entire order (including partner and product) is rolled back.
2. **Deduplication**: Checks `etsy_order_id` first (order-level), then `etsy_transaction_id` (line-level). Skips entirely if order exists. Skips individual lines if transaction exists.
3. **Partner matching priority**: email > name+zip > create new. This minimizes duplicates while avoiding false merges.
4. **Product matching**: Exact name match only. Different product options (size, color) are NOT separate products — they're attributes on the sale.order.line.
5. **Country resolution**: Uses `self.env['res.country'].search([('code', '=', code)])` with the ISO code from the parser. Falls back to name search if code is empty.
6. **State resolution**: Uses `self.env['res.country.state'].search([('name', 'ilike', state), ('country_id', '=', country.id)])`. Creates no state records — uses existing Odoo data.
7. **Currency**: All prices stored as-is (EUR). Assumes Odoo company currency is EUR or multi-currency is configured.
8. **Sale order state**: Created orders are in 'draft' state (quotation). Not auto-confirmed.
