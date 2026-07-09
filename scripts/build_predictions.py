#!/usr/bin/env python3
"""Build a schema-v2 prediction slate from a snapshot (SPEC §7 item 6) — freeze-exempt.

Runs the frozen engine over a snapshot's bettable slate (games with a prediction-time line) and
writes the schema-v2 JSON — every game, including NO_BET. Pure computation over the snapshot
(offline, zero API cost); re-running on the same snapshot is byte-identical modulo the VOLATILE
fields (`model_version`, `generated_at`).

Usage:
  python scripts/build_predictions.py [--week N] [--year 2026] [--out PATH]

`--out` writes elsewhere than the default `data/predictions/YYYY_week_NN.json`; it is used to
regenerate the committed schema-v2 golden example under `docs/examples/` (kept OUT of
`data/predictions/` so it never collides with the real in-season week run, which the append-only
hook would otherwise block).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.predictions import build_predictions  # noqa: E402
from data.snapshot.store import (  # noqa: E402
    SnapshotNotFoundError,
    latest_snapshot_week,
    load_snapshot,
)
from utils.version import model_version  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"


def write_predictions(predictions: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(predictions, indent=2, sort_keys=True) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a schema-v2 prediction slate from a snapshot.")
    parser.add_argument("--week", type=int, help="Week to predict; defaults to the latest built.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--out", type=str, help="Output path (default data/predictions/YYYY_week_NN.json).")
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

    predictions = build_predictions(snapshot, week=week, model_version=model_version())
    out = Path(args.out) if args.out else PREDICTIONS_DIR / f"{args.year}_week_{week:02d}.json"
    path = write_predictions(predictions, out)
    meta = predictions["meta"]
    rel = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
    print(f"Wrote {rel}")
    print(f"  schema v{meta['schema_version']} | model {meta['model_version']} | "
          f"{meta['prediction_count']} predictions | snapshot {meta['snapshot_id']} (week {week})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
