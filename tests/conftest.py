"""Shared test fixtures (Phase 0, decision D4).

The 2025 suite makes real network calls through a rate limiter that sleeps,
so incompletely-mocked tests hang instead of failing. Neutralizing the sleep
turns hangs into fast, visible results; a network block turns any un-mocked
live call into a clear error instead of a real HTTP request. Together these let
the full suite run deterministically offline.
"""

import time

import pytest

# Files that assert on real timing/HTTP behavior and must keep real time.sleep
# and real (mocked-per-test) request handling — do not apply the global patches.
_TIMING_SENSITIVE = (
    "test_performance_tracker",
    "test_cache_manager",
)


def _is_timing_sensitive(request) -> bool:
    return any(name in request.node.nodeid for name in _TIMING_SENSITIVE)


@pytest.fixture(autouse=True)
def _neutralize_rate_limit_sleep(request, monkeypatch):
    """No-op time.sleep so rate-limiter waits never hang the suite.

    Skipped for timing-sensitive files that legitimately assert on elapsed time.
    """
    if _is_timing_sensitive(request):
        return
    monkeypatch.setattr(time, "sleep", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _block_real_network(request, monkeypatch):
    """Fail fast (not hang, not hit the network) on any un-mocked HTTP call."""
    if _is_timing_sensitive(request):
        return
    try:
        import requests.sessions
    except Exception:
        return

    def _blocked(self, method, url, *args, **kwargs):
        raise RuntimeError(
            f"Real network call blocked in tests: {method} {url}. "
            "Mock the client method instead (see tests/conftest.py)."
        )

    monkeypatch.setattr(requests.sessions.Session, "request", _blocked)
