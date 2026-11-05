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
  claim_window_open  — `week`'s claim is DUE: its start is within one predict cadence (D38). False
                       means the Tuesday job must not write a claim yet. `pipeline_week` returns 1
                       from before the season onward, so without this the first live Tuesday claims
                       the slot weeks early — which is exactly what happened on 2026-08-11.
  grade_weeks        — space-separated weeks that have a predictions file and can therefore be
                       graded; `scripts/grade.py` exits 1 on a week with no claim, so the caller
                       filters here instead of treating that exit as a failure
  catchup_weeks      — the subset of `grade_weeks` whose graded file does NOT yet cover every
                       claimed game (D48). The Tuesday catch-up loop iterates THIS, because it
                       calls CFBD once per week and a fully-graded week has no late finisher to
                       find; `grade_weeks` stays the full set, because Sunday re-renders all of
                       them (#58) and that is what makes a stale report self-healing
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.season_calendar import (  # noqa: E402
    claim_window_open,
    load_calendar,
    pipeline_timezone,
    pipeline_today,
    pipeline_week,
)

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"
GRADED_DIR = ROOT / "data" / "graded"


def predictions_path(week: int, year: int) -> Path:
    return PREDICTIONS_DIR / f"{year}_week_{week:02d}.json"


def graded_path(week: int, year: int) -> Path:
    return GRADED_DIR / f"{year}_week_{week:02d}.json"


def gradable_weeks(through: int, year: int) -> list[int]:
    """Weeks up to and including ``through`` that have a claim on disk.

    **Deliberately unchanged by D48's catch-up narrowing.** The Sunday job re-renders *every* week
    in this set (#58), which is what makes a report whose data moved beneath it self-healing: a week
    graded by Tuesday's catch-up is re-rendered the following Sunday without anyone remembering to.
    Narrowing this would have silently retired that. The catch-up loop uses
    ``weeks_needing_grade`` instead.
    """
    return [w for w in range(1, through + 1) if predictions_path(w, year).exists()]


def _game_ids(path: Path, key: str) -> set[str] | None:
    """The ``game_id`` set from a claim or graded envelope. ``None`` if it cannot be read.

    Unreadable means "assume there is work to do": a week whose files cannot be parsed is exactly a
    week somebody needs to look at, and silently skipping it would hide that behind an optimisation.
    """
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text()).get(key) or []
        return {r["game_id"] for r in rows if isinstance(r, dict) and "game_id" in r}
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def weeks_needing_grade(through: int, year: int) -> list[int]:
    """Weeks with a claim whose graded file does **not** yet cover every claimed game (D48).

    Why this exists: the Tuesday catch-up loop calls CFBD once per week it iterates, and it iterated
    every claimed week — seven CFBD calls in front of the week-8 claim on 2026-10-20, fourteen by
    week 15. Each one can fail the job that writes the season's pre-registration artifact, and one
    did (#71). A week whose every claimed game already has a graded row has no late finisher left to
    find, so calling CFBD for it buys nothing and risks the claim.

    What it does NOT change: grading still runs before the claim, and still fails the whole job on a
    CLV sign disagreement (D43). Only the set of weeks shrinks.

    A week with a genuinely unplayed game — a postponement — stays in the set indefinitely, which is
    correct: that is precisely a week that could still have a late finisher.
    """
    out: list[int] = []
    for wk in gradable_weeks(through, year):
        claimed = _game_ids(predictions_path(wk, year), "predictions")
        graded = _game_ids(graded_path(wk, year), "graded")
        if claimed is None or graded is None or not claimed <= graded:
            out.append(wk)
    return out


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
        "claim_window_open": "true" if claim_window_open(wk, today, cal) else "false",
        "grade_weeks": " ".join(str(w) for w in gradable_weeks(wk, year)),
        "catchup_weeks": " ".join(str(w) for w in weeks_needing_grade(wk, year)),
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
