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


def write_predictions(predictions: dict, path: Path, *, force: bool = False) -> Path:
    """Write a slate. **Refuses to overwrite an existing file under `data/predictions/`** (D22).

    The refusal lives here, at the shared seam, rather than only in `cli/cfb.py::_save_slate`:
    Phase 5 wires this writer into unattended automation, where the only other guard is a
    workflow-level `if:` condition and the `protect_immutable` hook does not run at all (it
    intercepts an agent's Edit/Write tool calls, not a script executing on a runner). A claim is
    byte-immutable forever, so an accidental overwrite is unrecoverable.

    The guard is scoped to the claim tier, so `--out` to a scratch path (e.g. regenerating
    `docs/examples/`'s golden) is unaffected.
    """
    path = Path(path)
    in_claim_tier = path.parent.resolve() == PREDICTIONS_DIR.resolve()
    if path.exists() and in_claim_tier and not force:
        raise FileExistsError(
            f"{path} already exists — predictions are byte-immutable (D22). Grading writes a "
            f"separate artifact; re-deriving a claim is not a normal operation. Pass --force only "
            f"to deliberately replace an uncommitted claim."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(predictions, indent=2, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a schema-v2 prediction slate from a snapshot.")
    parser.add_argument("--week", type=int, help="Week to predict; defaults to the latest built.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--out", type=str, help="Output path (default data/predictions/YYYY_week_NN.json).")
    parser.add_argument("--force", action="store_true",
                        help="deliberately replace an existing claim (D22 — normally refused)")
    args = parser.parse_args(argv)

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
    try:
        path = write_predictions(predictions, out, force=args.force)
    except FileExistsError as exc:
        print(str(exc))
        return 1
    meta = predictions["meta"]
    rel = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
    print(f"Wrote {rel}")
    print(f"  schema v{meta['schema_version']} | model {meta['model_version']} | "
          f"{meta['prediction_count']} predictions | snapshot {meta['snapshot_id']} (week {week})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
