import asyncio

from retry_policy_kit import RetryPolicy


def _always_retryable(exc):
    return True


def _never_retryable(exc):
    return False


def test_succeeds_on_first_try_without_sleeping(monkeypatch):
    sleeps = []
    monkeypatch.setattr("retry_policy_kit.retry.time.sleep", lambda s: sleeps.append(s))
    policy = RetryPolicy(max_attempts=3)

    result = policy.run(lambda: "ok", _always_retryable)

    assert result.passed
    assert result.value == "ok"
    assert result.attempts == 1
    assert sleeps == []


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("retry_policy_kit.retry.time.sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("not yet")
        return "eventually"

    policy = RetryPolicy(max_attempts=5)
    result = policy.run(flaky, _always_retryable)

    assert result.passed
    assert result.value == "eventually"
    assert result.attempts == 3


def test_non_retryable_exception_aborts_immediately(monkeypatch):
    sleeps = []
    monkeypatch.setattr("retry_policy_kit.retry.time.sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise PermissionError("nope")

    policy = RetryPolicy(max_attempts=5)
    result = policy.run(always_fails, _never_retryable)

    assert not result.passed
    assert result.attempts == 1
    assert calls["n"] == 1
    assert sleeps == []


def test_exhausts_max_attempts_when_always_retryable(monkeypatch):
    monkeypatch.setattr("retry_policy_kit.retry.time.sleep", lambda s: None)
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise TimeoutError("slow")

    policy = RetryPolicy(max_attempts=3)
    result = policy.run(always_fails, _always_retryable)

    assert not result.passed
    assert result.attempts == 3
    assert calls["n"] == 3


def test_delay_grows_exponentially(monkeypatch):
    delays = []
    monkeypatch.setattr("retry_policy_kit.retry.time.sleep", lambda s: delays.append(s))
    monkeypatch.setattr("retry_policy_kit.retry.random.uniform", lambda a, b: 0)
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise TimeoutError("slow")

    policy = RetryPolicy(max_attempts=4, base_delay=1.0, jitter=0)
    policy.run(always_fails, _always_retryable)

    assert delays == [1.0, 2.0, 4.0]


def test_arun_succeeds_on_first_try():
    policy = RetryPolicy(max_attempts=3)

    async def call():
        return "ok"

    result = asyncio.run(policy.arun(call, _always_retryable))
    assert result.passed
    assert result.value == "ok"
    assert result.attempts == 1


def test_arun_retries_then_succeeds(monkeypatch):
    async def _sleep(_):
        return None

    monkeypatch.setattr("retry_policy_kit.retry.asyncio.sleep", _sleep)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("not yet")
        return "eventually"

    policy = RetryPolicy(max_attempts=3)
    result = asyncio.run(policy.arun(flaky, _always_retryable))

    assert result.passed
    assert result.attempts == 2
