"""Deterministic unit tests for the in-process token bucket."""
import concurrent.futures
import math
import unittest

from rate_limiter import TokenBucket


class Clock:
    def __init__(self, start=100.0):
        self.value = start

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class TokenBucketTests(unittest.TestCase):
    def test_starts_full(self):
        b = TokenBucket(2, 5)
        self.assertEqual(b.available(), 5)

    def test_capacity_and_exhaustion(self):
        b = TokenBucket(2, 3, clock=Clock())
        self.assertTrue(all(b.try_consume() for _ in range(3)))
        self.assertFalse(b.try_consume())
        self.assertEqual(b.available(), 0)

    def test_refill(self):
        clock = Clock()
        b = TokenBucket(2, 5, initial_tokens=0, clock=clock)
        clock.advance(1.25)
        self.assertAlmostEqual(b.available(), 2.5)
        self.assertTrue(b.try_consume(2))
        self.assertAlmostEqual(b.available(), 0.5)

    def test_cap_refill_at_capacity(self):
        clock = Clock()
        b = TokenBucket(10, 4, initial_tokens=0, clock=clock)
        clock.advance(999)
        self.assertEqual(b.available(), 4)

    def test_fractional_cost(self):
        b = TokenBucket(1, 1, clock=Clock())
        self.assertTrue(b.try_consume(0.25))
        self.assertTrue(b.try_consume(0.75))
        self.assertFalse(b.try_consume(0.01))

    def test_failed_consume_does_not_remove_balance(self):
        b = TokenBucket(1, 4, clock=Clock())
        self.assertFalse(b.try_consume(5))
        self.assertEqual(b.available(), 4)

    def test_start_empty(self):
        b = TokenBucket(1, 4, initial_tokens=0, clock=Clock())
        self.assertFalse(b.try_consume())

    def test_wait_until(self):
        clock = Clock()
        b = TokenBucket(2, 3, initial_tokens=0, clock=clock)
        self.assertAlmostEqual(b.time_until(3), 1.5)
        clock.advance(1)
        self.assertAlmostEqual(b.time_until(3), 0.5)
        clock.advance(1)
        self.assertEqual(b.time_until(3), 0)

    def test_cannot_wait_for_more_than_capacity(self):
        b = TokenBucket(1, 2)
        with self.assertRaises(ValueError):
            b.time_until(3)

    def test_invalid_config(self):
        for rate, capacity in [(0, 1), (-1, 1), (math.inf, 1), (1, math.nan), (1, 0)]:
            with self.subTest(rate=rate, capacity=capacity), self.assertRaises(ValueError):
                TokenBucket(rate, capacity)
        with self.assertRaises(TypeError):
            TokenBucket(True, 2)

    def test_invalid_cost(self):
        b = TokenBucket(1, 2)
        for value in (0, -1, math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                b.try_consume(value)
        with self.assertRaises(TypeError):
            b.try_consume("1")

    def test_invalid_initial_tokens(self):
        for value in (-1, math.inf, 6):
            with self.subTest(value=value), self.assertRaises(ValueError):
                TokenBucket(1, 5, initial_tokens=value)

    def test_backward_clock_no_free_tokens(self):
        clock = Clock()
        b = TokenBucket(2, 3, initial_tokens=0, clock=clock)
        clock.advance(-20)
        self.assertEqual(b.available(), 0)
        clock.advance(21)
        self.assertAlmostEqual(b.available(), 2)

    def test_huge_elapsed_no_overflow(self):
        clock = Clock()
        b = TokenBucket(1e300, 1e300, initial_tokens=0, clock=clock)
        clock.advance(1e300)
        self.assertEqual(b.available(), 1e300)

    def test_thread_safe_atomic_take(self):
        bucket = TokenBucket(1, 10, clock=Clock())
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            results = list(pool.map(lambda _: bucket.try_consume(), range(100)))
        self.assertEqual(results.count(True), 10)
        self.assertEqual(results.count(False), 90)
        self.assertEqual(bucket.available(), 0)


if __name__ == "__main__":
    unittest.main()
