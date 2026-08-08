"""The freeze gates' pinned input must be provably the tag-time snapshot (D29).

`verify-phase-3`'s behavioural fingerprint, its L4 all-NO_BET assertion and the schema-v2 golden
reproduction all read `data/archive/frozen/2026_week_01_snapshot.json` instead of the live
`data/snapshots/2026_week_01/` bundle, which the Phase-5 pipeline rebuilds on every week-1 run.

That indirection is only worth anything if the pinned file really is the snapshot the frozen
fingerprint was generated from. `main` has moved since `v2026-frozen`, so a working-tree copy
would rest on the assumption that nothing touched the snapshot in between. These tests remove the
assumption: the pinned SHA-256 is **re-derived from the tag** (`git show v2026-frozen:<path>`) on
every run, so a wrong vehicle fails here with a specific message rather than surfacing later as a
confusing "model output moved".
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from data.snapshot.store import (
    FROZEN_VEHICLE,
    FROZEN_VEHICLE_SHA256,
    FROZEN_VEHICLE_SOURCE,
    frozen_vehicle_sha256,
    load_frozen_vehicle,
)

ROOT = Path(__file__).resolve().parent.parent
TAG, TAGGED_PATH = FROZEN_VEHICLE_SOURCE


def _git_show(ref_path: str) -> bytes | None:
    """Bytes of a path at a ref, or None when git/the tag is unavailable (shallow checkout)."""
    if shutil.which("git") is None:
        return None
    out = subprocess.run(["git", "show", ref_path], capture_output=True, cwd=str(ROOT))
    return out.stdout if out.returncode == 0 else None


def test_vehicle_exists_under_the_append_only_tier():
    """It must live under `data/archive/` — the hook-guarded tier — not under `data/snapshots/`,
    which is rewritten by the pipeline and guarded by nothing."""
    assert FROZEN_VEHICLE.exists(), f"pinned gate vehicle missing at {FROZEN_VEHICLE}"
    rel = FROZEN_VEHICLE.relative_to(ROOT).as_posix()
    assert rel.startswith("data/archive/"), rel
    assert "data/snapshots/" not in rel


def test_vehicle_matches_the_pinned_sha256():
    assert frozen_vehicle_sha256() == FROZEN_VEHICLE_SHA256, (
        "the pinned gate vehicle's bytes changed. The freeze gates read this file; restore it "
        "rather than updating the constant — a moved vehicle is not a moved model."
    )


def test_pinned_sha256_is_the_tag_time_bytes():
    """The constant is re-derived from the tag, so it cannot silently pin the wrong snapshot."""
    tagged = _git_show(f"{TAG}:{TAGGED_PATH}")
    if tagged is None:
        pytest.skip(f"git or {TAG} unavailable (shallow checkout)")
    assert hashlib.sha256(tagged).hexdigest() == FROZEN_VEHICLE_SHA256, (
        f"FROZEN_VEHICLE_SHA256 does not match {TAG}:{TAGGED_PATH}"
    )


def test_vehicle_bytes_equal_the_tagged_snapshot():
    """Byte equality, not just hash equality — the vehicle IS the tag-time snapshot."""
    tagged = _git_show(f"{TAG}:{TAGGED_PATH}")
    if tagged is None:
        pytest.skip(f"git or {TAG} unavailable (shallow checkout)")
    assert FROZEN_VEHICLE.read_bytes() == tagged


def test_vehicle_loads_as_a_snapshot_bundle():
    bundle = load_frozen_vehicle()
    assert set(bundle) == {"data", "meta"}
    assert bundle["meta"]["week"] == 1 and bundle["meta"]["year"] == 2026
    assert bundle["data"]["games"], "vehicle carries no games"
