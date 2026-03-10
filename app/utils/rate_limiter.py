import time


class TokenBucketRateLimiter:
    """Token bucket rate limiter per chat_id."""

    def __init__(self, rate: float, capacity: int):
        self._rate = rate  # tokens per second
        self._capacity = capacity
        self._tokens: dict[int, float] = {}
        self._last_check: dict[int, float] = {}

    def try_consume(self, chat_id: int) -> bool:
        now = time.monotonic()
        if chat_id not in self._tokens:
            self._tokens[chat_id] = self._capacity
            self._last_check[chat_id] = now

        elapsed = now - self._last_check[chat_id]
        self._last_check[chat_id] = now

        self._tokens[chat_id] = min(
            self._capacity,
            self._tokens[chat_id] + elapsed * self._rate,
        )

        if self._tokens[chat_id] >= 1.0:
            self._tokens[chat_id] -= 1.0
            return True
        return False
