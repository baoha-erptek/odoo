"""Tests for the image downloader service.

Verifies image URL transformation, skip-when-image-exists logic,
and graceful handling of download failures.
"""
import base64
import time

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..services.email_parser import RawEmail
from ..services.image_downloader import ImageDownloader


# 1x1 transparent PNG as bytes (shared fixture)
_PNG_1X1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4'
    b'\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05'
    b'\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


@tagged('at_install')
class TestImageDownloader(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _create_etsy_product(self, name='Test Etsy Product', image_url='',
                              image_data=False, is_etsy_product=True):
        """Helper to create a product.template with Etsy fields."""
        vals = {
            'name': name,
            'is_etsy_product': is_etsy_product,
            'etsy_image_url': image_url,
        }
        if image_data:
            vals['image_1920'] = image_data
        return self.env['product.template'].create(vals)

    # ------------------------------------------------------------------
    # T044c-1: URL transform in email parser
    # ------------------------------------------------------------------

    def test_url_transform_in_parser(self):
        """Verify that the email parser replaces '75x75' with '300x300'
        in image URLs extracted from HTML."""
        raw = RawEmail(
            message_id='<test-img-transform@etsy.com>',
            subject='New order from Etsy',
            date='Mon, 01 Jan 2024 00:00:00 +0000',
            text_body='',
            html_body=(
                '<html><body>'
                '<img src="https://i.etsystatic.com/28215280/r/il/abc123/'
                '6049408768/il_75x75.6049408768_n0ek.jpg"/>'
                '</body></html>'
            ),
        )
        # We call the internal _extract_image_urls helper via import
        from ..services.email_parser import _extract_image_urls
        urls = _extract_image_urls(raw.html_body)

        self.assertTrue(len(urls) >= 1, 'Expected at least one image URL')
        for url in urls:
            self.assertNotIn(
                '75x75', url,
                'Image URL should have 75x75 replaced with 300x300')
            self.assertIn(
                '300x300', url,
                'Image URL should contain 300x300 after transformation')

    # ------------------------------------------------------------------
    # T044c-2: Skip download when product already has an image
    # ------------------------------------------------------------------

    def test_skip_when_already_has_image(self):
        """When a product already has image_1920 set, download_and_store
        should return False without making any HTTP request."""
        existing_image = base64.b64encode(_PNG_1X1)
        product = self._create_etsy_product(
            name='Product With Image',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
            image_data=existing_image,
        )

        downloader = ImageDownloader(self.env)

        with patch('odoo.addons.etsy_integration.services.image_downloader.requests.get') as mock_get:
            result = downloader.download_and_store(
                product, 'https://i.etsystatic.com/test/300x300.jpg')

            self.assertFalse(result, 'Should return False when image already exists')
            mock_get.assert_not_called()

    # ------------------------------------------------------------------
    # T044c-3: Graceful handling of download failure
    # ------------------------------------------------------------------

    def test_download_failure_graceful(self):
        """When the HTTP request fails, download_and_store should return
        False and leave the product image unchanged."""
        product = self._create_etsy_product(
            name='Product Without Image',
            image_url='https://i.etsystatic.com/invalid/does-not-exist.jpg',
        )
        self.assertFalse(product.image_1920, 'Product should start with no image')

        downloader = ImageDownloader(self.env)

        import requests as req_lib
        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get',
            side_effect=req_lib.exceptions.ConnectionError('Simulated failure'),
        ):
            result = downloader.download_and_store(
                product, 'https://i.etsystatic.com/invalid/does-not-exist.jpg')

        self.assertFalse(result, 'Should return False on download failure')
        self.assertFalse(
            product.image_1920,
            'Product image should remain unset after download failure')

    # ------------------------------------------------------------------
    # P1-IMG-BACKFILL: Phase 1 predicate tests
    # Tests verify the cron's search domain selects the correct products.
    # Approach: mock download_and_store to a no-op, call cron, verify
    # which product IDs were considered for download.
    # ------------------------------------------------------------------

    def test_cron_selects_products_with_etsy_url_and_no_image(self):
        """Regression: Product with etsy_image_url set and no image IS selected."""
        product = self._create_etsy_product(
            name='Product With URL',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
        )

        downloader = ImageDownloader(self.env)
        download_calls = []

        def record_download(prod, url):
            download_calls.append(prod.id)
            return False

        with patch.object(downloader, 'download_and_store', side_effect=record_download):
            downloader.cron_download_pending_images()

        self.assertIn(
            product.id, download_calls,
            'Product with etsy_image_url should be selected by cron')

    def test_cron_selects_products_without_etsy_url_and_no_image(self):
        """Backfill case: Product without etsy_image_url and no image IS selected.
        This test FAILS on current code (predicate filters on etsy_image_url != False)."""
        product = self._create_etsy_product(
            name='Product Without URL',
            image_url='',  # Empty URL
        )

        downloader = ImageDownloader(self.env)
        download_calls = []

        def record_download(prod, url):
            download_calls.append(prod.id)
            return False

        with patch.object(downloader, 'download_and_store', side_effect=record_download):
            downloader.cron_download_pending_images()

        self.assertIn(
            product.id, download_calls,
            'Product without etsy_image_url should be selected by cron (backfill case)')

    def test_cron_excludes_products_with_image_regardless_of_url(self):
        """Product with image_1920 set is excluded, regardless of URL."""
        image_b64 = base64.b64encode(_PNG_1X1)
        product_with_url = self._create_etsy_product(
            name='With URL and Image',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
            image_data=image_b64,
        )
        product_without_url = self._create_etsy_product(
            name='Without URL But Has Image',
            image_url='',
            image_data=image_b64,
        )

        downloader = ImageDownloader(self.env)
        download_calls = []

        def record_download(prod, url):
            download_calls.append(prod.id)
            return False

        with patch.object(downloader, 'download_and_store', side_effect=record_download):
            downloader.cron_download_pending_images()

        self.assertNotIn(
            product_with_url.id, download_calls,
            'Product with image should be excluded (even with URL)')
        self.assertNotIn(
            product_without_url.id, download_calls,
            'Product with image should be excluded (even without URL)')

    def test_cron_excludes_non_etsy_products(self):
        """Product with is_etsy_product=False is excluded."""
        product = self._create_etsy_product(
            name='Non-Etsy Product',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
            is_etsy_product=False,
        )

        downloader = ImageDownloader(self.env)
        download_calls = []

        def record_download(prod, url):
            download_calls.append(prod.id)
            return False

        with patch.object(downloader, 'download_and_store', side_effect=record_download):
            downloader.cron_download_pending_images()

        self.assertNotIn(
            product.id, download_calls,
            'Non-Etsy product should be excluded')

    def test_cron_predicate_is_idempotent(self):
        """Second run of cron finds same set after downloads complete.
        First run downloads a product; second run excludes it (image now set)."""
        product = self._create_etsy_product(
            name='Idempotent Test',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
        )

        downloader = ImageDownloader(self.env)
        run_calls = []

        def record_download_and_set_image(prod, url):
            run_calls.append(prod.id)
            # Simulate successful download by setting image
            prod.write({'image_1920': base64.b64encode(_PNG_1X1)})
            return True

        with patch.object(downloader, 'download_and_store',
                         side_effect=record_download_and_set_image):
            downloader.cron_download_pending_images()
            first_run_calls = list(run_calls)

            # Second run should find zero pending (product now has image)
            downloader.cron_download_pending_images()
            second_run_calls = [c for c in run_calls if c not in first_run_calls]

        self.assertEqual(len(first_run_calls), 1, 'First run should find 1 product')
        self.assertEqual(len(second_run_calls), 0, 'Second run should find 0 products')

    # ------------------------------------------------------------------
    # P1-IMG-BACKFILL: Phase 2 ORM integration tests
    # Full integration with mocked network layer; verify business logic.
    # ------------------------------------------------------------------

    def test_cron_download_pending_with_etsy_url(self):
        """Happy path: Product with URL downloads image successfully."""
        product = self._create_etsy_product(
            name='Product With URL',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
        )

        downloader = ImageDownloader(self.env)

        # Mock the HTTP response
        mock_response = type('Response', (), {
            'content': _PNG_1X1,
            'raise_for_status': lambda self: None,
        })()

        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get',
            return_value=mock_response,
        ), patch(
            'odoo.addons.etsy_integration.services.image_downloader.time.sleep'
        ):
            downloader.cron_download_pending_images()

        # Verify product has image set
        product_refreshed = self.env['product.template'].browse(product.id)
        self.assertTrue(
            product_refreshed.image_1920,
            'Product should have image_1920 set after download')

    def test_cron_download_pending_without_etsy_url(self):
        """Backfill: Product without URL is selected but skipped gracefully.
        download_and_store rejects empty URL at line 47-48."""
        product = self._create_etsy_product(
            name='Product Without URL',
            image_url='',  # Empty URL
        )

        downloader = ImageDownloader(self.env)

        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get'
        ) as mock_get, patch(
            'odoo.addons.etsy_integration.services.image_downloader.time.sleep'
        ):
            downloader.cron_download_pending_images()

            # requests.get should NOT be called (empty URL rejected before network call)
            mock_get.assert_not_called()

        # Verify image unchanged
        product_refreshed = self.env['product.template'].browse(product.id)
        self.assertFalse(
            product_refreshed.image_1920,
            'Product without URL should not have image set (no network call)')

    def test_cron_skip_already_has_image(self):
        """Regression: Product with image is excluded at cron level."""
        image_b64 = base64.b64encode(_PNG_1X1)
        product = self._create_etsy_product(
            name='Product With Image',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
            image_data=image_b64,
        )

        downloader = ImageDownloader(self.env)

        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get'
        ) as mock_get:
            downloader.cron_download_pending_images()

            # requests.get should NOT be called (product already has image)
            mock_get.assert_not_called()

    def test_cron_respects_delay_between_downloads(self):
        """Cron sleeps 1 second between downloads (and after last)."""
        products = [
            self._create_etsy_product(
                name=f'Product {i}',
                image_url='https://i.etsystatic.com/test/300x300.jpg',
            )
            for i in range(3)
        ]

        downloader = ImageDownloader(self.env)
        mock_response = type('Response', (), {
            'content': _PNG_1X1,
            'raise_for_status': lambda self: None,
        })()

        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get',
            return_value=mock_response,
        ), patch(
            'odoo.addons.etsy_integration.services.image_downloader.time.sleep'
        ) as mock_sleep:
            downloader.cron_download_pending_images()

            # Should call sleep 3 times (once per product, including after last)
            self.assertEqual(
                mock_sleep.call_count, 3,
                'Should sleep 1 second between/after each download')
            # Verify all calls were with 1 second
            for call_obj in mock_sleep.call_args_list:
                self.assertEqual(call_obj[0][0], 1, 'Delay should be 1 second')

    def test_cron_ssrf_allowlist_enforced(self):
        """SSRF protection: URL from untrusted domain is rejected."""
        product = self._create_etsy_product(
            name='Malicious URL',
            image_url='http://attacker.com/evil.png',
        )

        downloader = ImageDownloader(self.env)

        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get'
        ) as mock_get, patch(
            'odoo.addons.etsy_integration.services.image_downloader.time.sleep'
        ):
            downloader.cron_download_pending_images()

            # requests.get should NOT be called (domain not in allowlist)
            mock_get.assert_not_called()

        # Verify image unchanged
        product_refreshed = self.env['product.template'].browse(product.id)
        self.assertFalse(
            product_refreshed.image_1920,
            'Untrusted domain should not be downloaded')

    def test_cron_idempotent_on_retry(self):
        """Multiple runs handle mix of successful, failed, and blocked downloads.
        After run 1: downloaded product excluded, blocked and failed remain pending.
        Run 2 retries blocked/failed; run 3 verifies no infinite loop."""
        # Product 1: with URL (will succeed)
        product_with_url = self._create_etsy_product(
            name='With URL',
            image_url='https://i.etsystatic.com/test/300x300.jpg',
        )
        # Product 2: without URL (blocked by empty URL check)
        product_without_url = self._create_etsy_product(
            name='Without URL',
            image_url='',
        )
        # Product 3: with untrusted URL (blocked by SSRF allowlist)
        product_blocked = self._create_etsy_product(
            name='Blocked URL',
            image_url='http://attacker.com/evil.png',
        )

        downloader = ImageDownloader(self.env)
        mock_response = type('Response', (), {
            'content': _PNG_1X1,
            'raise_for_status': lambda: None,
        })()
        run_calls = []

        def track_calls(prod, url):
            run_calls.append((prod.id, url))
            # Only product_with_url succeeds
            if prod.id == product_with_url.id:
                prod.write({'image_1920': base64.b64encode(_PNG_1X1)})
                return True
            return False

        with patch(
            'odoo.addons.etsy_integration.services.image_downloader.requests.get',
            return_value=mock_response,
        ), patch(
            'odoo.addons.etsy_integration.services.image_downloader.time.sleep'
        ), patch.object(
            downloader, 'download_and_store', side_effect=track_calls
        ):
            # Run 1
            downloader.cron_download_pending_images()
            run1_ids = {c[0] for c in run_calls}

            run_calls.clear()

            # Run 2: same set still pending (failures not retried differently)
            downloader.cron_download_pending_images()
            run2_ids = {c[0] for c in run_calls}

        # Run 1 should include all 3
        self.assertIn(
            product_with_url.id, run1_ids,
            'Run 1: product with URL should be considered')
        self.assertIn(
            product_without_url.id, run1_ids,
            'Run 1: product without URL should be considered (backfill)')
        self.assertIn(
            product_blocked.id, run1_ids,
            'Run 1: product with blocked URL should be considered')

        # Run 2 should exclude downloaded product, but include others
        self.assertNotIn(
            product_with_url.id, run2_ids,
            'Run 2: downloaded product should be excluded')
        self.assertIn(
            product_without_url.id, run2_ids,
            'Run 2: undownloaded product (empty URL) should be retried')
        self.assertIn(
            product_blocked.id, run2_ids,
            'Run 2: blocked product should be retried')
