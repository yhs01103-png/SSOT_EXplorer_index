"""Exponential-backoff retry wrapper where *retryability* is a decision
the caller supplies, not something guessed from exception type.

Generalized from a Gemini-calling pipeline's retry loop: the original
decided retryable-vs-abort from a `{"success", "retryable", ...}` dict a
specific logging wrapper returned. That's backwards for a general kit --
the *loop* (how many attempts, how long to wait between them) is the
reusable part; *what counts as retryable* is inherently caller-specific
(a 429 is retryable, a 401 usually isn't, and only the caller's client
library knows which is which), so it's a plain callback here instead of
being baked in.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class RetryResult:
    passed: bool
    value: Optional[T] = None
    attempts: int = 0
    reason: str = ""


class RetryPolicy:
    """`max_attempts` includes the first try (max_attempts=3 means up to 2
    retries). Delay before attempt N (N>1) is
    `base_delay * 2**(N-2) + random.uniform(0, jitter)` -- attempt 2 waits
    ~base_delay, attempt 3 waits ~2x base_delay, and so on."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        jitter: float = 0.5,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.jitter = jitter

    def _delay(self, attempt: int) -> float:
        return self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, self.jitter)

    def run(
        self,
        call: Callable[[], T],
        is_retryable: Callable[[Exception], bool],
    ) -> RetryResult:
        """`call` runs with no arguments and either returns a value or
        raises. `is_retryable(exc)` decides whether a raised exception is
        worth retrying at all -- return False for anything that will
        never succeed on its own (bad auth, malformed request)."""
        last_reason = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                return RetryResult(passed=True, value=call(), attempts=attempt)
            except Exception as exc:
                last_reason = str(exc)
                if not is_retryable(exc) or attempt >= self.max_attempts:
                    return RetryResult(passed=False, attempts=attempt, reason=last_reason)
                time.sleep(self._delay(attempt))
        return RetryResult(passed=False, attempts=self.max_attempts, reason=last_reason)

    async def arun(
        self,
        call: Callable[[], Awaitable[T]],
        is_retryable: Callable[[Exception], bool],
    ) -> RetryResult:
        """Async twin of run() -- `call` is a zero-argument coroutine
        function, waits between attempts use `asyncio.sleep` so the event
        loop isn't blocked."""
        last_reason = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                value = await call()
                return RetryResult(passed=True, value=value, attempts=attempt)
            except Exception as exc:
                last_reason = str(exc)
                if not is_retryable(exc) or attempt >= self.max_attempts:
                    return RetryResult(passed=False, attempts=attempt, reason=last_reason)
                await asyncio.sleep(self._delay(attempt))
        return RetryResult(passed=False, attempts=self.max_attempts, reason=last_reason)
