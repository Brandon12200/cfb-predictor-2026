"""Snapshot bundle disk I/O + content-addressed id.

A bundle is a directory `data/snapshots/YYYY_week_NN/` holding `snapshot.json`
(canonical data) and `manifest.json` (provenance). The `snapshot_id` is a content
hash over the canonical **data** only (not the volatile build time), so identical
inputs yield an identical id — the anchor for reproducible `predict rerun`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "snapshots"

# The freeze gates' pinned input. `data/snapshots/2026_week_01/` is a LIVE bundle: the Phase-5
# pipeline rebuilds it every week-1 run, and `write_snapshot` overwrites unconditionally. The
# behavioural fingerprint, the L4 all-NO_BET assertion and the schema-v2 golden reproduction all
# need the snapshot *as it stood at the tag*, so they read this byte-for-byte copy under the
# append-only tier instead. Moving the gate's read path is not weakening it — the fingerprint
# constant is untouched, and any change reaching model output through the freeze-exempt read seam
# (`data/normalize`, `data/schedule_intel`, the registry) still trips it, because the gate re-runs
# the engine over this input rather than replaying a stored result. See DECISIONS D29.
FROZEN_VEHICLE = Path(__file__).resolve().parent.parent / "archive" / "frozen" / \
    "2026_week_01_snapshot_v2026-frozen-3.json"

# Every superseded vehicle is KEPT as the historical record of what that freeze measured. None is
# deleted or overwritten — `data/archive/` is append-only, and a superseded tag's vehicle is
# exactly the kind of thing the audit trail exists to preserve. Each entry is the input its own
# tag's fingerprint was computed over, so an old exception entry stays reproducible.
#   v2026-frozen   — the season's FIRST freeze. Known to contain ~10 fabricated games
#                    (SPEC §3.1 exception 1); that is why it was superseded.
#   v2026-frozen-2 — the returning-production transition (exception 1). Superseded by exception 2
#                    when preseason SP+ published, waking `Sandwich` and re-sourcing every prior.
SUPERSEDED_VEHICLES = {
    "v2026-frozen": Path(__file__).resolve().parent.parent / "archive" / "frozen" /
    "2026_week_01_snapshot.json",
    "v2026-frozen-2": Path(__file__).resolve().parent.parent / "archive" / "frozen" /
    "2026_week_01_snapshot_v2026-frozen-2.json",
}

# SHA-256 of the vehicle's bytes, derived from `git show v2026-frozen:<snapshot path>` — NOT from
# the working tree, which has moved since the tag. `tests/test_frozen_vehicle.py` re-derives this
# from the tag on every run, so the claim "these are the tag-time bytes" is proven rather than
# asserted. One definition, imported by the gate and the test (no second copy to drift).
FROZEN_VEHICLE_SHA256 = "b50ba7ecb639add9c51060f331eebad668333cdac620656fd8fa90ef83adb1b1"
FROZEN_VEHICLE_SOURCE = ("v2026-frozen-3", "data/snapshots/2026_week_01/snapshot.json")


class SnapshotNotFoundError(RuntimeError):
    """Raised when a requested snapshot bundle does not exist on disk."""


def snapshot_dir(week: int, year: int = 2026, base: Path | None = None) -> Path:
    return (base or _SNAPSHOTS_DIR) / f"{year}_week_{week:02d}"


def compute_snapshot_id(data: dict[str, Any]) -> str:
    """Deterministic 16-hex id over the canonical data (order-independent)."""
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def write_snapshot(week: int, snapshot: dict[str, Any], manifest: dict[str, Any],
                   year: int = 2026, base: Path | None = None) -> Path:
    d = snapshot_dir(week, year, base)
    d.mkdir(parents=True, exist_ok=True)
    _write_json(d / "snapshot.json", snapshot)
    _write_json(d / "manifest.json", manifest)
    return d


def load_snapshot(week: int, year: int = 2026, base: Path | None = None) -> dict[str, Any]:
    path = snapshot_dir(week, year, base) / "snapshot.json"
    if not path.exists():
        raise SnapshotNotFoundError(
            f"No snapshot for {year} week {week} at {path} — "
            f"run `python scripts/build_snapshot.py --week {week}`."
        )
    return json.loads(path.read_text())


def load_frozen_vehicle(path: Path | None = None) -> dict[str, Any]:
    """The tag-time week-1 snapshot, pinned as the immutable input to the freeze gates (D29).

    Single accessor so the fingerprint gate, the L4 slate assertion, the schema-v2 golden
    reproduction and their tests cannot drift onto different inputs.
    """
    p = path or FROZEN_VEHICLE
    if not p.exists():
        # Tag name derived, never hardcoded — a retag must move one place (SPEC §3.1).
        raise SnapshotNotFoundError(
            f"Frozen gate vehicle missing at {p}. It is a byte-for-byte copy of the "
            f"`{FROZEN_VEHICLE_SOURCE[0]}` week-1 snapshot and is required by the freeze "
            f"gates (D29)."
        )
    return json.loads(p.read_text())


def frozen_vehicle_sha256(path: Path | None = None) -> str:
    """SHA-256 of the pinned vehicle's bytes — asserted separately from the behavioural
    fingerprint so 'the gate's input changed' reports differently from 'model output moved'."""
    return hashlib.sha256((path or FROZEN_VEHICLE).read_bytes()).hexdigest()


def available_weeks(year: int = 2026, base: Path | None = None) -> list[int]:
    """Sorted week numbers that have a built snapshot on disk."""
    root = base or _SNAPSHOTS_DIR
    weeks: list[int] = []
    for p in root.glob(f"{year}_week_*"):
        if (p / "snapshot.json").exists():
            try:
                weeks.append(int(p.name.split("_week_")[1]))
            except (ValueError, IndexError):
                continue
    return sorted(weeks)


def latest_snapshot_week(year: int = 2026, base: Path | None = None,
                         not_after: int | None = None) -> int | None:
    """The most recent built week (≤ `not_after` if given), or None if none exist.
    Used to price hypotheticals/projections off the freshest available ratings."""
    weeks = available_weeks(year, base)
    if not_after is not None:
        weeks = [w for w in weeks if w <= not_after]
    return weeks[-1] if weeks else None


def load_manifest(week: int, year: int = 2026, base: Path | None = None) -> dict[str, Any]:
    path = snapshot_dir(week, year, base) / "manifest.json"
    if not path.exists():
        raise SnapshotNotFoundError(f"No manifest for {year} week {week} at {path}.")
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
