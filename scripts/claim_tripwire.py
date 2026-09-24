#!/usr/bin/env python3
"""Claim tripwire: from Wednesday to Saturday, a week whose claim is due must have a valid claim.

**Why it exists (owner ruling 2026-09-15, D44).** The three cadence workflows share one concurrency
group, and under the queue default (`single`) GitHub keeps at most one *pending* run per group: a
newer pending run cancels the older one, whatever `cancel-in-progress` says. A cancelled run's
conclusion is `cancelled`, which never fires `if: failure()`. With the Tuesday 12:50 capture in the
group, a Tuesday predict could be lost without a trace — pending behind a running capture when a
third group run (in practice a manual dispatch) was created. The cost is no claim for the week, and
nothing alarmed until Wednesday's capture failed on a missing snapshot, about a day later and with
the wrong diagnosis.

**That specific cause was removed by D46**, which sets `queue: max` on the group: up to 100 pending
runs, FIFO, no silent replacement. **This check stays, and its premise is now broader rather than
narrower** — queueing was never the only way a week loses its claim. GitHub drops scheduled runs
under load; a predict can fail outright; a claim can land `-dirty`; and a tripwire that only ever
fires for the one cause it was written against is a tripwire nobody can trust for the others. It
remains **detection only**: whether capture should leave the shared group is still a 2027 question
(`docs/2027_NOTES.md` §8 item 33).

It runs in the daily freeze-integrity job, which has its own concurrency group, so no cadence run
can cancel it. Wednesday's run leaves time to re-dispatch predict before evening kickoffs.

**What counts as no claim:**
- the week's `data/predictions` file is absent;
- the file is not readable JSON;
- its `meta.model_version` is missing or carries `-dirty`. A claim stamped from a modified working
  tree is not a claim of the frozen model (owner ruling), so it fires exactly as a missing one does.

It is silent:
- outside Wednesday to Saturday in the pipeline timezone;
- when the claim is not yet **due**. A claim is due once the most recent Tuesday was that week's own
  predict day: `pipeline_week` resolved to this week and the claim window (D38) was open. The window
  alone is the wrong gate. It says a claim *may* be written, not that one *should* exist, and it
  opened on Saturday 2026-08-22, three days before week 1's first predict on 08-25 (review of the
  tripwire PR).

Exit 0: a valid claim exists, or the check does not apply today.
Exit 2: the claim is due and **missing or unreadable**. Re-dispatching `weekly-predict` for that week
writes it, so the workflow opens an ordinary `pipeline-failure` issue, which that successful run clears.
Exit 3: the claim exists and is **`-dirty`**. This is NOT recoverable by re-running anything. A claim
is byte-immutable (D22: `write_predictions` refuses to overwrite), so the week's pre-registration
carries that stamp permanently; a re-dispatched predict skips the claim, succeeds, and would close an
ordinary failure issue while nothing had been fixed. It therefore opens `pipeline-dirty-claim`, a kind
`clear-failure` never clears: the fact stands until the owner decides what to do with it.
Exit 1: the check itself failed.

Usage: python scripts/claim_tripwire.py [--today YYYY-MM-DD] [--base DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.season_calendar import (  # noqa: E402
    claim_window_open,
    load_calendar,
    pipeline_today,
    pipeline_week,
)

ROOT = Path(__file__).resolve().parent.parent
EXIT_OK, EXIT_ERROR, EXIT_NO_VALID_CLAIM, EXIT_DIRTY_CLAIM = 0, 1, 2, 3
# Wednesday..Saturday: the predict job runs Tuesday, so from Wednesday a missing claim is not "not
# yet". Sunday and Monday are after the week's games.
_ACTIVE_WEEKDAYS = {2, 3, 4, 5}


def claim_problem(path: Path, shown: str | None = None) -> str | None:
    """None if ``path`` is a valid claim; otherwise why it is not one (naming it as ``shown``)."""
    name = shown or path.as_posix()
    if not path.exists():
        return f"no claim file at {name}"
    try:
        meta = json.loads(path.read_text()).get("meta") or {}
    except (OSError, ValueError) as exc:
        return f"claim file {name} is not readable JSON ({type(exc).__name__})"
    mv = meta.get("model_version")
    if not mv:
        return f"claim {name} has no meta.model_version"
    if "-dirty" in str(mv):
        return (f"claim {name} is stamped {mv}: built from a modified working tree, "
                f"so not a claim of the frozen model")
    return None


def is_dirty(problem: str) -> bool:
    """A dirty claim is permanent; a missing one is fixable. They need different issue kinds."""
    return "-dirty" in problem


def claim_due(week: int, today: date, calendar: dict) -> bool:
    """True once the most recent Tuesday before ``today`` was ``week``'s own predict day."""
    tuesday = today - timedelta(days=(today.weekday() - 1) % 7 or 7)
    return (pipeline_week(tuesday, calendar) == week
            and claim_window_open(week, tuesday, calendar))


def evaluate(today: date, calendar: dict, base: Path) -> tuple[int, int | None, str]:
    """(exit code, week or None, reason)."""
    if today.weekday() not in _ACTIVE_WEEKDAYS:
        return EXIT_OK, None, f"{today:%a}: the tripwire only runs Wednesday to Saturday"
    week = pipeline_week(today, calendar)
    if not claim_due(week, today, calendar):
        return EXIT_OK, week, f"week {week}'s claim is not due yet on {today} (no predict day for it has passed)"
    year = int(calendar["season"])
    rel = f"data/predictions/{year}_week_{week:02d}.json"
    problem = claim_problem(base / rel, rel)
    if problem is None:
        return EXIT_OK, week, f"week {week} has a valid claim"
    return (EXIT_DIRTY_CLAIM if is_dirty(problem) else EXIT_NO_VALID_CLAIM), week, problem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", type=date.fromisoformat, default=None, help="tests only")
    ap.add_argument("--base", type=Path, default=ROOT, help="repository root (tests only)")
    args = ap.parse_args(argv)
    calendar = load_calendar()
    today = args.today or pipeline_today(calendar)
    rc, week, reason = evaluate(today, calendar, args.base)
    if rc == EXIT_NO_VALID_CLAIM:
        print(f"::error::claim tripwire: week {week} is due a claim and has none: {reason}. "
              f"Re-dispatch weekly-predict for week {week} before its first kickoff.")
    elif rc == EXIT_DIRTY_CLAIM:
        print(f"::error::claim tripwire: week {week}'s claim is dirty and cannot be repaired: "
              f"{reason}. Claims are byte-immutable (D22), so re-running predict will NOT replace it "
              f"— it skips the existing claim and succeeds. This is a permanent fact about week "
              f"{week}'s pre-registration, for the owner to rule on.")
    else:
        print(f"claim tripwire: {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out and week is not None and args.today is None:
        with open(out, "a") as fh:
            fh.write(f"week_padded={week:02d}\n")
            fh.write(f"reason={reason}\n")
            # No `kind` output: the workflow routes rc 2 and rc 3 to their own steps, each naming its
            # kind literally, so a second source of that decision would be one that could drift.
    return rc


if __name__ == "__main__":
    sys.exit(main())
