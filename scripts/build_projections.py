#!/usr/bin/env python3
"""Build weekly season projections from a snapshot (SPEC §6.5) — freeze-exempt.

Prices every remaining game with the 2a matchup pricer and rolls up per-team projected
win totals, writing `data/projections/YYYY_week_NN.json`. Pure computation over the
snapshot (zero API cost); re-running on the same snapshot is byte-identical (`generated_at`
frozen from the snapshot's build time). Projections are **experimental** and never drive
bet recommendations (SPEC §6.5).

Usage: python scripts/build_projections.py [--week N] [--year 2026]   (offline)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.projections import build_projections  # noqa: E402
from data.snapshot.store import (  # noqa: E402
    SnapshotNotFoundError,
    latest_snapshot_week,
    load_snapshot,
)

PROJECTIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "projections"


def write_projections(projections: dict, year: int, week: int, base: Path | None = None) -> Path:
    root = base or PROJECTIONS_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{year}_week_{week:02d}.json"
    path.write_text(json.dumps(projections, indent=2, sort_keys=True) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build weekly season projections from a snapshot.")
    parser.add_argument("--week", type=int, help="Week to project; defaults to the latest built.")
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    week = args.week if args.week is not None else latest_snapshot_week(args.year)
    if week is None:
        print(f"No snapshot built for {args.year}. Run `python scripts/build_snapshot.py --week N`.")
        return 1
    try:
        snapshot = load_snapshot(week, args.year)
    except SnapshotNotFoundError as exc:
        print(str(exc))
        return 1

    projections = build_projections(snapshot)
    path = write_projections(projections, args.year, week)
    teams = projections["teams"]
    played = sum(1 for r in teams.values() if r["wins_so_far"] + r["losses_so_far"] > 0)
    rel = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
    print(f"Wrote {rel}")
    print(f"  {len(teams)} FBS teams | {played} with completed games | "
          f"snapshot {projections['meta']['snapshot_id']} (week {week})")
    print("  (experimental — never drives bet recommendations; SPEC §6.5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
