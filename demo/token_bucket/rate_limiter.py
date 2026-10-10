"""Thread-safe in-process token-bucket rate limiter (stdlib only)."""
from __future__ import annotations

import math
import threading
import time
from typing import Callable


def _positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return numeric


class TokenBucket:
    """Allow bursts up to capacity, refill at rate tokens/second.

    Local to one process; not a distributed or persistent rate limiter.
    A failed consumption never subtracts tokens.
    """

    def __init__(
        self,
        rate: float,
        capacity: float,
        *,
        initial_tokens: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate = _positive_finite(rate, "rate")
        self.capacity = _positive_finite(capacity, "capacity")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock
        self._lock = threading.Lock()
        self._updated = self._now()
        if initial_tokens is None:
            self._tokens = self.capacity
        else:
            if isinstance(initial_tokens, bool) or not isinstance(initial_tokens, (int, float)):
                raise TypeError("initial_tokens must be a number")
            initial = float(initial_tokens)
            if not math.isfinite(initial) or not 0 <= initial <= self.capacity:
                raise ValueError("initial_tokens must be finite and between 0 and capacity")
            self._tokens = initial

    def _now(self) -> float:
        value = self._clock()
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("clock must return a finite number")
        return float(value)

    def _refill(self) -> None:
        now = self._now()
        elapsed = max(0.0, now - self._updated)
        self._updated = max(self._updated, now)
        # Avoid floating-point overflow when elapsed is huge.
        if elapsed >= self.capacity / self.rate:
            self._tokens = self.capacity
        else:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    def try_consume(self, tokens: float = 1.0) -> bool:
        """Atomically consume tokens if available; otherwise return False."""
        amount = _positive_finite(tokens, "tokens")
        if amount > self.capacity:
            return False
        with self._lock:
            self._refill()
            if self._tokens < amount:
                return False
            self._tokens -= amount
            return True

    def available(self) -> float:
        """Return the current token balance after refilling."""
        with self._lock:
            self._refill()
            return self._tokens

    def time_until(self, tokens: float = 1.0) -> float:
        """Seconds until amount is available, or ValueError if impossible."""
        amount = _positive_finite(tokens, "tokens")
        if amount > self.capacity:
            raise ValueError("requested tokens exceed burst capacity")
        with self._lock:
            self._refill()
            return max(0.0, amount - self._tokens) / self.rate
