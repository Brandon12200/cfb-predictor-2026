#!/usr/bin/env python3
"""Export weekly power ratings from a snapshot (SPEC §6.1, D13).

Writes `data/ratings/YYYY_week_NN.json` — per team: rating, `rating_uncertainty`,
`games_played`, prior source/seed — embedding the `snapshot_id` it derives from.

This is a **derived, inspection/projection artifact**. The engine's prediction path
recomputes ratings from the snapshot on the fly (`engine.matchup_pricer`) and never
reads this file, so the reproducibility contract is untouched. Re-running on the same
snapshot is byte-identical (`generated_at` is frozen from the snapshot's build time).

Usage: python scripts/update_ratings.py --week N [--year 2026]   (offline; no API cost)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.snapshot.store import (  # noqa: E402
    SnapshotNotFoundError,
    latest_snapshot_week,
    load_snapshot,
)
from engine.matchup_pricer import build_ratings_export  # noqa: E402

RATINGS_DIR = Path(__file__).resolve().parent.parent / "data" / "ratings"


def write_ratings(export: dict, year: int, week: int, base: Path | None = None) -> Path:
    root = base or RATINGS_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{year}_week_{week:02d}.json"
    path.write_text(json.dumps(export, indent=2, sort_keys=True) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export weekly power ratings from a snapshot.")
    parser.add_argument("--week", type=int, help="Week to export; defaults to the latest built.")
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

    export = build_ratings_export(snapshot)
    path = write_ratings(export, args.year, week)
    rated = export["ratings"]
    played = sum(1 for r in rated.values() if r["games_played"] > 0)
    print(f"Wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
    print(f"  {len(rated)} teams | {played} with completed games | "
          f"snapshot {export['meta']['snapshot_id']} (week {week})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
