"""Shared test fixtures (Phase 0, decision D4).

The 2025 suite makes real network calls through a rate limiter that sleeps,
so incompletely-mocked tests hang instead of failing. Neutralizing the sleep
turns hangs into fast, visible results; a network block turns any un-mocked
live call into a clear error instead of a real HTTP request. Together these let
the full suite run deterministically offline.
"""

import time
from pathlib import Path

import pytest

# The real, committed artifact directories. A test must never write here — `data/predictions/`
# holds byte-immutable claims (D22) and the rest are append-only history (D23). Tests that
# exercise a writer point it at `tmp_path` instead (see `test_predict_week_save_refuses_overwrite_d22`,
# which monkeypatches `build_predictions.PREDICTIONS_DIR`).
# Kept in step with `.claude/hooks/protect_immutable.py`'s PROTECTED tuple — deliberately EXCLUDING
# `reports/`, which is a regenerable rendering (D23), not history. The hook only intercepts an
# agent's own Edit/Write calls; this guard covers runtime file I/O executed inside a test, so the
# two need the same coverage to be a complete net.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROTECTED_ARTIFACT_DIRS = tuple(
    _REPO_ROOT / "data" / name
    for name in ("predictions", "results", "archive", "lines", "ratings", "projections", "graded")
)

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


def _artifact_fingerprint(dirs: tuple[Path, ...] | None = None) -> dict[str, float]:
    """Path -> mtime for every file under `dirs` (default: the protected artifact dirs)."""
    seen: dict[str, float] = {}
    for d in (_PROTECTED_ARTIFACT_DIRS if dirs is None else dirs):
        if d.is_dir():
            for f in d.rglob("*"):
                if f.is_file():
                    seen[str(f)] = f.stat().st_mtime
    return seen


@pytest.fixture(autouse=True)
def _no_writes_to_real_artifact_dirs():
    """Fail any test that creates, deletes, or modifies a real committed artifact.

    A reviewer's manual `--save` run once left a stray file under `data/predictions/`. The
    existing save test patches `PREDICTIONS_DIR` to `tmp_path`, and that patch only binds because
    `cli/app`'s save path imports the constant at call time — a refactor to a module-level import
    would silently re-point the test at the real directory. This guard makes that failure loud
    instead of leaving an untracked prediction claim in the working tree.
    """
    # Bind the directory list at setup: a test that monkeypatches the module tuple (the guard's
    # own regression pin does) must not redirect this comparison.
    dirs = tuple(_PROTECTED_ARTIFACT_DIRS)
    before = _artifact_fingerprint(dirs)
    yield
    after = _artifact_fingerprint(dirs)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    if added or removed or changed:
        raise AssertionError(
            "test wrote to a real committed artifact directory (use tmp_path instead) — "
            f"added={added} removed={removed} modified={changed}"
        )
