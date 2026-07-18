#!/usr/bin/env python3
"""Grade a week's predictions → the append-only graded artifact (Phase 4, SPEC §8, D22) — freeze-exempt.

Joins ``data/predictions/YYYY_week_NN.json`` (byte-immutable claims — NEVER edited, D22) with
``data/results/YYYY_week_NN.json`` (final scores) and the per-game ``data/lines/`` closing
observations, computes ``closing_spread``/``clv``/``ats_result``/``graded_at`` per game, and writes
``data/graded/YYYY_week_NN.json``.

**Idempotent + catch-up** (the Phase-5 Tuesday shape): re-running preserves already-graded entries
(immutable once graded) and appends only games that have completed since — so it is safe to run
repeatedly and grades whatever is now finishable. If nothing new is gradable, the file is left
untouched (a true no-op).

Usage:
  python scripts/grade.py --week N [--year 2026]

The append-only immutability hook guards ``data/graded/``; this script writes via the pipeline path
(not the guarded Edit tool), appending — never mutating an existing graded entry.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.grading import build_graded, merge_graded  # noqa: E402
from data.snapshot.lines import load_lines  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"
RESULTS_DIR = ROOT / "data" / "results"
GRADED_DIR = ROOT / "data" / "graded"


def graded_path(week: int, year: int) -> Path:
    return GRADED_DIR / f"{year}_week_{week:02d}.json"


def _load_json(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade a week's predictions into data/graded/.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()
    week, year = args.week, args.year

    predictions_env = _load_json(PREDICTIONS_DIR / f"{year}_week_{week:02d}.json")
    if predictions_env is None:
        print(f"No predictions for {year} week {week:02d} (data/predictions/). Nothing to grade.")
        return 1
    results_env = _load_json(RESULTS_DIR / f"{year}_week_{week:02d}.json")
    results = (results_env or {}).get("results", []) if results_env else []
    lines_store = load_lines(week, year)  # {} if no line file yet

    graded_at = datetime.now(UTC).isoformat()
    fresh = build_graded(predictions_env, results, lines_store, graded_at=graded_at)
    existing = _load_json(graded_path(week, year))
    merged, added = merge_graded(existing, fresh)

    cov = merged["meta"]["coverage"]
    if added == 0 and existing is not None:
        print(f"No new games to grade for {year} week {week:02d} "
              f"({cov['graded']}/{cov['predicted']} graded already). No-op.")
        return 0

    out = graded_path(week, year)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    rel = out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out
    print(f"Wrote {rel}")
    print(f"  graded {cov['graded']}/{cov['predicted']} (+{added} new) | "
          f"no closing line: {len(cov['no_closing_line'])} | ungraded: {len(cov['ungraded'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
