"""Unit tests for TokenBucket rate limiter.

RED phase: These tests define the contract for TokenBucket.
All tests MUST FAIL until implementation is complete.
"""

import time
from unittest import mock

from odoo.tests.common import TransactionCase

from ..utils.rate_limiter import TokenBucket


class TestTokenBucketInitialization(TransactionCase):
    """Test TokenBucket initialization and state."""

    def test_initial_bucket_full(self):
        """Fresh bucket starts full and first acquire(rate) succeeds."""
        bucket = TokenBucket(rate=100, period=10.0)
        # Bucket should start full with 100 tokens
        self.assertTrue(bucket.acquire(100), "Should acquire all 100 tokens from fresh bucket")

    def test_acquire_decrements_available_tokens(self):
        """Tokens are decremented on acquire."""
        bucket = TokenBucket(rate=5, period=10.0)

        # Take 2 tokens
        self.assertTrue(bucket.acquire(2), "Should acquire 2 tokens")

        # Try to take 4 more, should fail (only 3 remain)
        self.assertFalse(bucket.acquire(4), "Should fail to acquire 4 tokens when only 3 remain")

    def test_acquire_default_count_is_one(self):
        """acquire() with no arguments defaults to count=1."""
        bucket = TokenBucket(rate=2, period=10.0)

        # Exhaust bucket minus 1
        bucket.acquire(1)

        # Call without args should take 1 token
        self.assertTrue(bucket.acquire(), "Should acquire 1 token when no count specified")

    def test_acquire_zero_count_does_not_change_state(self):
        """acquire(0) returns True without changing token count."""
        bucket = TokenBucket(rate=5, period=10.0)

        # Check initial state
        self.assertTrue(bucket.acquire(5), "Should exhaust bucket")

        # acquire(0) should succeed but not add tokens
        self.assertTrue(bucket.acquire(0), "acquire(0) should return True")

        # Still no tokens available
        self.assertFalse(bucket.acquire(1), "Should still have no tokens after acquire(0)")

    def test_exhausted_acquire_returns_false(self):
        """Acquiring more than available returns False without dequeueing."""
        bucket = TokenBucket(rate=5, period=10.0)

        # Exhaust the bucket
        bucket.acquire(5)

        # Next acquire should fail
        self.assertFalse(bucket.acquire(1), "Should fail to acquire when bucket is empty")

        # State should remain empty
        self.assertFalse(bucket.acquire(1), "Should still be empty after failed acquire")

    def test_acquire_negative_count_raises_value_error(self):
        """acquire(-1) raises ValueError."""
        bucket = TokenBucket(rate=5, period=10.0)

        with self.assertRaises(ValueError):
            bucket.acquire(-1)

    def test_time_until_refill_zero_when_tokens_available(self):
        """time_until_refill() returns 0.0 when tokens are available."""
        bucket = TokenBucket(rate=100, period=10.0)

        # Fresh bucket has tokens
        self.assertEqual(bucket.time_until_refill(), 0.0, "Should be 0.0 when tokens available")

        # Even after acquiring some tokens
        bucket.acquire(50)
        self.assertEqual(bucket.time_until_refill(), 0.0, "Should be 0.0 while tokens remain")

    def test_time_until_refill_positive_when_empty(self):
        """time_until_refill() returns positive value when bucket is empty."""
        bucket = TokenBucket(rate=5, period=10.0)

        # Exhaust bucket
        bucket.acquire(5)

        # Check time until refill
        time_until_refill = bucket.time_until_refill()
        self.assertGreater(time_until_refill, 0.0, "Should be positive when bucket empty")
        self.assertLessEqual(
            time_until_refill,
            10.0 / 5,  # period / rate = 2.0 seconds
            "Should not exceed period/rate"
        )

    @mock.patch('odoo.addons.multichannel_hub_core.utils.rate_limiter.time.monotonic')
    def test_refill_after_time_passes(self, mock_monotonic):
        """Bucket refills tokens after period elapses."""
        # Start at time 0
        mock_monotonic.return_value = 0.0

        bucket = TokenBucket(rate=2, period=10.0)

        # Exhaust bucket
        bucket.acquire(2)
        self.assertFalse(bucket.acquire(1), "Bucket should be empty")

        # Advance time by period + 1ms (enough for 2 new tokens)
        mock_monotonic.return_value = 10.0 + 0.001

        # Should now be able to acquire the refilled token(s)
        self.assertTrue(bucket.acquire(1), "Should acquire token after refill time passes")

    @mock.patch('odoo.addons.multichannel_hub_core.utils.rate_limiter.time.monotonic')
    def test_refill_calculates_tokens_correctly(self, mock_monotonic):
        """Refill calculates the correct number of new tokens."""
        mock_monotonic.return_value = 0.0

        bucket = TokenBucket(rate=10, period=5.0)  # 2 tokens per second

        # Exhaust bucket
        bucket.acquire(10)

        # Advance time by 2.5 seconds (should refill 5 tokens)
        mock_monotonic.return_value = 2.5

        # Should be able to acquire 5 new tokens
        self.assertTrue(bucket.acquire(5), "Should have 5 refilled tokens after 2.5 seconds")
        self.assertFalse(bucket.acquire(1), "Should not have a 6th token")

    @mock.patch('odoo.addons.multichannel_hub_core.utils.rate_limiter.time.monotonic')
    def test_partial_refill_accumulates(self, mock_monotonic):
        """Partial token refills accumulate over time."""
        mock_monotonic.return_value = 0.0

        bucket = TokenBucket(rate=10, period=5.0)  # 2 tokens per second

        # Exhaust bucket
        bucket.acquire(10)

        # Advance by 0.6 seconds (only 1.2 tokens, rounds down to 1)
        mock_monotonic.return_value = 0.6

        # Should have 1 token
        self.assertTrue(bucket.acquire(1), "Should have 1 refilled token after 0.6 seconds")

        # Advance by another 0.5 seconds (total 1.1 seconds = 2.2 tokens)
        mock_monotonic.return_value = 1.1

        # Should now have 1 more token (total 2 from 2.2 tokens, one already taken)
        self.assertTrue(bucket.acquire(1), "Should accumulate another token")

    @mock.patch('odoo.addons.multichannel_hub_core.utils.rate_limiter.time.monotonic')
    def test_bucket_does_not_exceed_max_capacity(self, mock_monotonic):
        """Bucket never exceeds initial rate capacity."""
        mock_monotonic.return_value = 0.0

        bucket = TokenBucket(rate=5, period=10.0)

        # Exhaust bucket
        bucket.acquire(5)

        # Advance by 100 seconds (way more than period)
        mock_monotonic.return_value = 100.0

        # Should still only be able to acquire 5 tokens (the original capacity)
        self.assertTrue(bucket.acquire(5), "Should acquire max 5 tokens after long time")
        self.assertFalse(bucket.acquire(1), "Should not exceed capacity of 5")
