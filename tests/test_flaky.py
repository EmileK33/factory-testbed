"""The known-flaky test.

This file is the repository's documented flake. See CLAUDE.md: with
``FACTORY_TESTBED_FLAKE=1`` set, the simulated upstream returns a jittered
latency and this test fails roughly half the time. With the variable unset the
latency is fixed and the test is deterministic, which is the state CI runs in.
"""

import os
import random

FLAKE_ENV = "FACTORY_TESTBED_FLAKE"

RETRY_BUDGET_MS = 50
SETTLED_LATENCY_MS = 5


def _upstream_latency_ms() -> int:
    """Latency of the simulated upstream rate service, in milliseconds."""
    if os.environ.get(FLAKE_ENV) == "1":
        return random.randint(1, 100)
    return SETTLED_LATENCY_MS


def test_rate_service_settles_within_the_retry_budget():
    assert _upstream_latency_ms() <= RETRY_BUDGET_MS
