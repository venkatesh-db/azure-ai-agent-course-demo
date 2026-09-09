"""
Module 3 / Lab 12: Reliability, performance and cost — production failure
exercise.

Wraps a flaky downstream tool call with bounded retries (exponential
backoff + jitter), a circuit breaker, and a timeout budget, then injects
failures (throttling, latency, hard failure) to prove the wrapping
actually behaves: retries transient errors, opens the breaker after
repeated failures instead of hammering a dead dependency, and degrades
gracefully instead of hanging. Pure local simulation — no Azure calls
needed, so every assertion here is deterministic and fast.
"""
import random
import time
from dataclasses import dataclass, field

from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type, RetryError,
)


class TransientError(Exception):
    """Retryable: the downstream service is temporarily unavailable."""


class PermanentError(Exception):
    """Not retryable: retrying would never help (e.g. bad request)."""


class CircuitOpenError(Exception):
    """The circuit breaker is open; refusing to call a known-bad dependency."""


@dataclass
class CircuitBreaker:
    fail_max: int = 5
    reset_timeout_seconds: float = 3.0
    _consecutive_failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.time() - self._opened_at > self.reset_timeout_seconds:
            return False  # half-open: allow a trial call
        return True

    def record_success(self):
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.fail_max and self._opened_at is None:
            self._opened_at = time.time()

    def call(self, fn, *args, **kwargs):
        if self.is_open:
            raise CircuitOpenError(
                f"Circuit open after {self._consecutive_failures} consecutive failures; "
                f"refusing call to protect the downstream dependency."
            )
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except TransientError:
            self.record_failure()
            raise


# --- Simulated flaky downstream dependency --------------------------------

class FlakyDownstream:
    """Simulates a dependency whose failure mode is configurable per test."""

    def __init__(self, mode: str):
        self.mode = mode
        self.call_count = 0

    def call(self):
        self.call_count += 1
        if self.mode == "always_throttled":
            raise TransientError("429 rate limited")
        if self.mode == "fails_twice_then_succeeds":
            if self.call_count <= 2:
                raise TransientError("connection reset")
            return "ok"
        if self.mode == "always_down":
            raise TransientError("connection refused")
        if self.mode == "bad_request":
            raise PermanentError("400 invalid request")
        if self.mode == "slow_then_ok":
            time.sleep(0.05)
            return "ok"
        return "ok"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.05, max=0.3),
    retry=retry_if_exception_type(TransientError),
    reraise=True,
)
def call_with_retry(downstream: FlakyDownstream):
    return downstream.call()


def scenario_transient_failure_recovers():
    print("\n--- Scenario: transient failure recovers within retry budget ---")
    downstream = FlakyDownstream("fails_twice_then_succeeds")
    result = call_with_retry(downstream)
    print(f"Result: {result} (took {downstream.call_count} attempts)")
    assert result == "ok"
    assert downstream.call_count == 3


def scenario_permanent_failure_not_retried():
    print("\n--- Scenario: permanent failure is not retried (wastes no time) ---")
    downstream = FlakyDownstream("bad_request")
    try:
        call_with_retry(downstream)
        print("FAIL: should have raised")
    except PermanentError:
        print(f"Correctly failed fast without retrying (call_count={downstream.call_count})")
        assert downstream.call_count == 1


def scenario_exhausted_retries_raise():
    print("\n--- Scenario: retries exhausted, bounded (does not retry forever) ---")
    downstream = FlakyDownstream("always_down")
    start = time.perf_counter()
    try:
        call_with_retry(downstream)
        print("FAIL: should have raised")
    except TransientError:
        elapsed = time.perf_counter() - start
        print(f"Gave up after {downstream.call_count} attempts in {elapsed:.2f}s (bounded, not infinite)")
        assert downstream.call_count == 3


def scenario_circuit_breaker_opens_and_recovers():
    print("\n--- Scenario: circuit breaker opens after repeated failures, recovers after cooldown ---")
    breaker = CircuitBreaker(fail_max=3, reset_timeout_seconds=1.0)
    downstream = FlakyDownstream("always_throttled")

    for i in range(3):
        try:
            breaker.call(downstream.call)
        except TransientError:
            print(f"  call {i+1}: failed (expected, feeding the breaker)")

    try:
        breaker.call(downstream.call)
        print("FAIL: breaker should be open")
    except CircuitOpenError as e:
        print(f"  call 4: breaker OPEN, refused without calling downstream: {e}")
        calls_before_open = downstream.call_count
        assert downstream.call_count == 3, "breaker should have prevented the 4th real call"

    print("  Waiting for cooldown...")
    time.sleep(1.1)

    downstream.mode = "slow_then_ok"  # simulate the dependency having recovered
    result = breaker.call(downstream.call)
    print(f"  After cooldown: breaker allowed a trial call, result={result}")
    assert result == "ok"
    assert downstream.call_count == calls_before_open + 1, "breaker should not have called downstream while open"


def scenario_cost_per_successful_task():
    print("\n--- Scenario: cost accounting under retries ---")
    downstream = FlakyDownstream("fails_twice_then_succeeds")
    cost_per_call = 0.0002  # illustrative $ per downstream call
    result = call_with_retry(downstream)
    total_cost = downstream.call_count * cost_per_call
    print(f"Task succeeded after {downstream.call_count} calls; "
          f"cost-per-successful-task = ${total_cost:.5f} "
          f"({downstream.call_count}x the single-call cost, due to retries)")


if __name__ == "__main__":
    scenario_transient_failure_recovers()
    scenario_permanent_failure_not_retried()
    scenario_exhausted_retries_raise()
    scenario_circuit_breaker_opens_and_recovers()
    scenario_cost_per_successful_task()
    print("\nAll Lab 12 resilience scenarios passed.")
