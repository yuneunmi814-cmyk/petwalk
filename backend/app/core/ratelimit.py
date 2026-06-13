"""Per-user sliding-window rate limiter.

In-memory for the local build; swap for Redis in production (the interface is one
`check()` call). Returns False when the caller is over budget — the auth
dependency turns that into a 429 + Retry-After.
"""

import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self, per_min: int = 120):
        self.per_min = per_min
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.time()
        window = self._hits[key]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= self.per_min:
            return False
        window.append(now)
        return True


_limiter: InMemoryRateLimiter | None = None


def get_rate_limiter() -> InMemoryRateLimiter:
    global _limiter
    if _limiter is None:
        from app.core.config import get_settings

        _limiter = InMemoryRateLimiter(get_settings().rate_limit_per_min)
    return _limiter


def set_rate_limiter(limiter: InMemoryRateLimiter | None) -> None:
    """Test seam — reset the limiter between tests."""
    global _limiter
    _limiter = limiter
