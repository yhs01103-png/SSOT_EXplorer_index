# Retry Policy Kit

Exponential-backoff retry, sync and async, where *what counts as
retryable* is a callback the caller supplies -- not guessed from
exception type. Generalized from a Gemini-calling pipeline's retry
loop, whose original version decided retryable-vs-abort from a
`{"success", "retryable", ...}` dict a specific logging wrapper
returned.

## What this is

One class, `RetryPolicy`, with two methods:

- **`run(call, is_retryable)`** — `call` is a zero-argument function
  that returns a value or raises. Retries up to `max_attempts` times
  (first try counts as attempt 1), sleeping
  `base_delay * 2**(attempt-1) + random.uniform(0, jitter)` between
  attempts. Stops immediately -- no further sleep -- the moment
  `is_retryable(exc)` returns `False` for a raised exception.
- **`arun(call, is_retryable)`** — same contract, `call` is a
  zero-argument coroutine function, waits use `asyncio.sleep` instead
  of `time.sleep` so the event loop isn't blocked.

Both return a `RetryResult(passed, value, attempts, reason)` --
`passed=False` is a normal return value, not an exception, so a
caller that wants to distinguish "gave up after retrying" from
"never worth retrying at all" can look at `attempts`.

## What this is not

`is_retryable` is always the caller's own decision -- a 429 is
usually retryable, a 401 usually isn't, and only the caller's client
library actually knows which is which for its own errors. This kit
doesn't inspect exception types, HTTP status codes, or error
messages to guess.

Not a circuit breaker, not a rate limiter, not a queue -- it retries
*one* call inline and returns. No persistence across process
restarts, no cross-process coordination.

## Install

```bash
pip install -e .
```

## Quick start

```python
from retry_policy_kit import RetryPolicy

policy = RetryPolicy(max_attempts=3, base_delay=1.0, jitter=0.5)

def is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (TimeoutError, ConnectionError))

result = policy.run(lambda: call_flaky_api(), is_retryable)
if not result.passed:
    raise RuntimeError(f"gave up after {result.attempts} attempts: {result.reason}")
value = result.value
```

Async version is identical except `call` is a coroutine function and
you `await policy.arun(...)`.

## What's *not* included

No default `is_retryable` (an empty policy retries nothing without
one -- deliberate, so you don't ship with a false sense of coverage).
No HTTP client, no circuit breaker, no metrics/logging hook. No
license-key or activation logic.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
