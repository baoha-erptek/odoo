# Contract: Image Downloader Service

**Module**: `addons/etsy_integration/services/image_downloader.py`
**Type**: HTTP client + Odoo ORM (downloads images, stores in filestore)

## Interface

### Functions

```python
class ImageDownloader:
    def __init__(self, env):
        """Initialize with Odoo environment."""

    def download_and_store(self, product: product.product, image_url: str) -> bool:
        """
        Download image from Etsy CDN (etsystatic.com) and store
        as the product's image_1920 field (base64-encoded).

        Returns True if image was downloaded and stored successfully.
        Returns False on any error (logs warning, does not raise).
        """

    def batch_download(self, products: list[tuple[product.product, str]]) -> int:
        """
        Download images for multiple products.
        Returns count of successfully downloaded images.
        Skips products that already have an image_1920 set.
        """
```

## Behavior

1. **Lazy download**: Images are NOT downloaded during order creation (to avoid slowing down the cron pipeline). Instead, a separate scheduled action downloads images for products where `etsy_image_url` is set but `image_1920` is empty.
2. **URL transformation**: URLs use `300x300` resolution (already transformed by the parser from `75x75`).
3. **Error tolerance**: Network errors, 404s, and timeouts are caught and logged. Never raises — a missing image is not a blocking error.
4. **Rate limiting**: 1-second delay between downloads to avoid CDN throttling.
5. **Format**: Downloaded bytes are base64-encoded and stored in Odoo's standard `image_1920` Binary field (which auto-generates smaller sizes).
6. **Idempotent**: If product already has `image_1920`, skip. Re-download only if `etsy_image_url` changed.
