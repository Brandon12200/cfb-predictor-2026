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
from utils.season_calendar import (  # noqa: E402
    CLAIM_LEAD_DAYS,
    claim_window_open,
    load_calendar,
    pipeline_today,
)
from utils.version import model_version  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"

# A refusal, not a crash: distinct from 1 (no snapshot / write refused) so a caller can tell
# "too early to claim" from "something is broken" without parsing stdout.
EXIT_CLAIM_WINDOW_CLOSED = 5


class ClaimWindowError(Exception):
    """A claim would be written before its season window opens (D38)."""


def write_predictions(predictions: dict, path: Path, *, force: bool = False,
                      ignore_window: bool = False) -> Path:
    """Write a slate. **Refuses to overwrite an existing file under `data/predictions/`** (D22).

    The refusal lives here, at the shared seam, rather than only in `cli/cfb.py::_save_slate`:
    Phase 5 wires this writer into unattended automation, where the only other guard is a
    workflow-level `if:` condition and the `protect_immutable` hook does not run at all (it
    intercepts an agent's Edit/Write tool calls, not a script executing on a runner). A claim is
    byte-immutable forever, so an accidental overwrite is unrecoverable.

    The guard is scoped to the claim tier, so `--out` to a scratch path (e.g. regenerating
    `docs/examples/`'s golden) is unaffected.

    **The season-aware claim gate (D38) lives here too, and here is the point.** It was first put in
    `main()` — the automated caller — which left `cli/cfb.py::_save_slate` (`cfb predict week N
    --save`, the *documented canonical* way a human writes a claim) completely ungated. Review
    reproduced the original 2026-08-11 incident through it in one command. `docs/2027_NOTES.md`
    records that the D22 overwrite guard had exactly this asymmetry once and was fixed by moving it
    to the shared seam; putting D38's gate anywhere else reintroduced the same bug shape in the
    opposite direction. **Both writers reach the disk through this function, so the guard belongs
    in it.**
    """
    path = Path(path)
    in_claim_tier = path.parent.resolve() == PREDICTIONS_DIR.resolve()

    # **D22 is checked FIRST, deliberately.** An existing claim is the more specific condition and
    # its message is the one the caller needs: "this week is already pre-registered" answers the
    # question, where "the window is not open" would be true but beside the point and would mask a
    # byte-immutability violation behind a scheduling message.
    if path.exists() and in_claim_tier and not force:
        raise FileExistsError(
            f"{path} already exists — predictions are byte-immutable (D22). Grading writes a "
            f"separate artifact; re-deriving a claim is not a normal operation. Pass --force only "
            f"to deliberately replace an uncommitted claim."
        )

    if in_claim_tier and not ignore_window:
        cal = load_calendar()
        meta = predictions.get("meta", {})
        week, year = meta.get("week"), meta.get("year")
        if week is not None and int(year or 0) == int(cal["season"]):
            if not claim_window_open(int(week), pipeline_today(cal), cal):
                start = cal["weeks"][str(int(week))]["start"]
                raise ClaimWindowError(
                    f"Refusing to write the week {week} claim: its window is not open yet. Week "
                    f"{week} starts {start}, and a claim may only be written within "
                    f"{CLAIM_LEAD_DAYS} days of that — one predict cadence (D38). Writing early "
                    f"locks a byte-immutable claim built from a preseason snapshot, which is "
                    f"exactly what happened on 2026-08-11 and had to be voided."
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
    parser.add_argument("--ignore-claim-window", action="store_true",
                        help="write a claim before its window opens (D38 — normally refused)")
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

    out = Path(args.out) if args.out else PREDICTIONS_DIR / f"{args.year}_week_{week:02d}.json"
    predictions = build_predictions(snapshot, week=week, model_version=model_version())
    try:
        path = write_predictions(predictions, out, force=args.force,
                                 ignore_window=args.ignore_claim_window)
    except ClaimWindowError as exc:
        print(f"{exc}\nPass --ignore-claim-window only with a recorded reason.")
        return EXIT_CLAIM_WINDOW_CLOSED
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
