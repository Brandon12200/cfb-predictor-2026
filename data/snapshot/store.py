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
