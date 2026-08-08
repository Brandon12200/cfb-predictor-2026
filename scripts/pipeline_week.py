#!/usr/bin/env python3
"""Resolve the week (and its context) a pipeline run should operate on — offline, freeze-exempt.

Emits ``key=value`` lines for ``$GITHUB_OUTPUT``, so every workflow step names the same week and
no step re-derives it. The date comes from the **pipeline timezone** (``season.json``
``pipeline.timezone``), never the runner's UTC clock — see ``utils.season_calendar.pipeline_today``.

Usage:
  python scripts/pipeline_week.py                 # resolve from today (ET)
  python scripts/pipeline_week.py --week 1        # explicit; always wins (rehearsals, backfills)
  python scripts/pipeline_week.py --format human  # readable, for local inspection

Outputs:
  week, week_padded, year, et_now, et_date,
  prediction_exists  — the byte-immutable claim for `week` is already on disk (D22), so the
                       Tuesday job must SKIP predicting rather than attempt an overwrite
  grade_weeks        — space-separated weeks that have a predictions file and can therefore be
                       graded; `scripts/grade.py` exits 1 on a week with no claim, so the caller
                       filters here instead of treating that exit as a failure
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.season_calendar import (  # noqa: E402
    load_calendar,
    pipeline_timezone,
    pipeline_today,
    pipeline_week,
)

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"


def predictions_path(week: int, year: int) -> Path:
    return PREDICTIONS_DIR / f"{year}_week_{week:02d}.json"


def gradable_weeks(through: int, year: int) -> list[int]:
    """Weeks up to and including ``through`` that have a claim on disk."""
    return [w for w in range(1, through + 1) if predictions_path(w, year).exists()]


def resolve(week: int | None, year: int, calendar: dict | None = None) -> dict[str, str]:
    cal = calendar if calendar is not None else load_calendar()
    now = datetime.now(ZoneInfo(pipeline_timezone(cal)))
    today = pipeline_today(cal, now=now)
    wk = week if week is not None else pipeline_week(today, cal)

    return {
        "week": str(wk),
        "week_padded": f"{wk:02d}",
        "year": str(year),
        "et_now": now.isoformat(timespec="seconds"),
        "et_date": today.isoformat(),
        "timezone": pipeline_timezone(cal),
        "prediction_exists": "true" if predictions_path(wk, year).exists() else "false",
        "grade_weeks": " ".join(str(w) for w in gradable_weeks(wk, year)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve the pipeline's target week.")
    parser.add_argument("--week", type=int, help="explicit week; always wins over the date")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--format", choices=("github", "human"), default="github")
    args = parser.parse_args(argv)

    out = resolve(args.week, args.year)
    if args.format == "human":
        width = max(len(k) for k in out)
        for k, v in out.items():
            print(f"{k.ljust(width)} : {v}")
    else:
        for k, v in out.items():
            print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
