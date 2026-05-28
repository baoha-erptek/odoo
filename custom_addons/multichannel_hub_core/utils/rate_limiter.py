"""Token bucket rate limiter for API clients."""

import time


class TokenBucket:
    """Token bucket rate limiter.

    Bucket starts full with `rate` tokens. Tokens regenerate at `rate / period`
    per second up to a cap of `rate`. Non-blocking: callers check the boolean
    return of `acquire()` and decide whether to retry, backoff, or fail.
    """

    def __init__(self, rate: int, period: float):
        self.rate = rate
        self.period = period
        self._tokens = float(rate)
        self._last = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.rate, self._tokens + elapsed * self.rate / self.period)
            self._last = now

    def acquire(self, count: int = 1) -> bool:
        if count < 0:
            raise ValueError("count must be >= 0")
        if count == 0:
            return True
        self._refill()
        if self._tokens >= count:
            self._tokens -= count
            return True
        return False

    def time_until_refill(self) -> float:
        self._refill()
        if self._tokens >= 1:
            return 0.0
        deficit = 1.0 - self._tokens
        return deficit * self.period / self.rate
