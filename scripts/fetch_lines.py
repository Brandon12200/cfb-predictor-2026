#!/usr/bin/env python3
"""Append a line observation for a week's SLATE to the append-only store (SPEC §5.4.3).

Fetches current NCAAF spreads and appends one "as-of T" observation per **slate game**
(the games in that week's snapshot, so nothing is filed under the wrong week) to
`data/lines/YYYY_week_NN.json` — the append-only series used for closing-line / CLV.
It NEVER touches the week's snapshot (immutability: `snapshot_id` is unaffected).
Phase 5 schedules the cadence.

Budget: the Odds API is a monthly-credit model (D5). This refuses to fetch when the
last-known remaining credits (persisted from the prior fetch, or the latest snapshot's
build-time balance) are below `--min-credits` — an honest pre-spend stop, not an overrun.

Usage: python scripts/fetch_lines.py --week N [--year 2026] [--min-credits 20]

Exit codes (Phase 5): 0 appended, 1 error (no snapshot / fetch failed), **3 budget refusal**,
**4 snapshot not built yet (a scheduled Tuesday capture slot only)**, **5 observation recorded,
accounting failed**. Budget stops and a Tuesday capture that beats the predict job are designed
outcomes, not failures — the scheduled capture job commits nothing and stays green on 3 or 4, but
alarms on 1. They shared exit 1 until Phase 5, which left the workflow string-matching stdout to
tell them apart.

**Exit 5 (D46).** 5 is neither designed nor ordinary: the observation IS on disk and must be
committed, and the run must still end red because a spent credit went unrecorded. D44's review
found the accounting running *before* `record_observation`, so a ledger failure threw away an
observation already paid for; the order was reversed, but the outcome did not change — an uncaught
ledger exception exited 1, `daily-capture.yml` failed the job, and `cfb-commit` (gated on
`rc == '0'`) never staged `data/lines`, so the runner was discarded with the observation on it.
That is why D44 records finding 1 as PARTIAL. Exit 5 is the completion: the workflow commits on 0
**or** 5, and the failure step runs *after* the commit, so the observation reaches `main` and the
alarm still fires. The ledger is re-derivable from the next response header; the observation is not
— the market moves on and that instant never comes back.

**Exit 4 (owner ruling 2026-09-15, D44).** The Tuesday 12:50 ET capture resolves the week being
claimed that day. The predict job builds that week's snapshot, and both share one concurrency group.
If the scheduler delays predict more than **213 minutes** (3 h 33 min) beyond the capture, the
capture runs first and finds no snapshot. That is the gap between the two slots in `season.json`
(predict 09:17 ET, capture 12:50 ET); it was 4.5 h against the 13:50 slot the 310-minute guarantee
lead produced, and moved when the lead became 370. On a run fired by the *scheduled Tuesday capture slot* that is a designed state:
no credit is spent, and a failed predict files its own issue. Any other day, or a manual run, a
missing snapshot is still exit 1 and alarms.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.normalize import odds as odds_norm  # noqa: E402
from data.odds_budget import append_ledger, last_remaining, record_quota  # noqa: E402
from data.snapshot.lines import record_observation  # noqa: E402
from data.snapshot.store import SnapshotNotFoundError, load_snapshot  # noqa: E402
from utils.season_calendar import load_calendar  # noqa: E402


EXIT_OK, EXIT_ERROR, EXIT_BUDGET_REFUSAL, EXIT_SNAPSHOT_PENDING = 0, 1, 3, 4
EXIT_ACCOUNTING_FAILED = 5  # observation written, spend unrecorded — commit it, then fail (D46)


def snapshot_pending_is_designed(calendar: dict | None = None) -> bool:
    """True only for a run fired by a scheduled TUESDAY capture slot (see exit 4 above).

    Keyed on the slot (`CFB_EVENT_SCHEDULE`, the cron that fired the run), not on the run's own clock.
    A Tuesday capture delayed past midnight runs on Wednesday, and a weekday check would turn the
    designed state into a false failure (D44 audit). No cron, or one that is not a Tuesday capture
    slot, is never designed: fail loud.
    """
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    fired = " ".join(os.environ.get("CFB_EVENT_SCHEDULE", "").split())
    if not fired:
        return False
    cal = calendar if calendar is not None else load_calendar()
    slots = ((cal.get("pipeline") or {}).get("schedule_et") or {}).get("capture", [])
    return any(" ".join(e["cron_utc"].split()) == fired and e["days"] == ["tue"] for e in slots)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a slate line observation to the store.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--min-credits", type=int, default=20,
                        help="refuse the fetch if last-known Odds credits fall below this")
    args = parser.parse_args(argv)

    # The snapshot defines the slate we predict — only its games belong in this week's
    # line store (never the whole season's currently-listed odds).
    try:
        slate = set(load_snapshot(args.week, args.year)["data"]["betting_lines"])
    except SnapshotNotFoundError:
        if snapshot_pending_is_designed():
            print(f"No snapshot for {args.year} week {args.week} yet: this scheduled Tuesday capture "
                  f"ran before the predict job built it. Designed state (exit 4); nothing fetched, "
                  f"no credit spent.")
            return EXIT_SNAPSHOT_PENDING
        print(f"No snapshot for {args.year} week {args.week} — "
              f"run `python scripts/build_snapshot.py --week {args.week}` first.")
        return EXIT_ERROR

    # Budget guard: honest pre-spend check against the last-known remaining credits.
    remaining, source = last_remaining()
    if remaining is not None and remaining < args.min_credits:
        print(f"Refusing fetch: {remaining} Odds credits remain ({source}) < --min-credits "
              f"{args.min_credits}. Monthly budget guard (D5).")
        return EXIT_BUDGET_REFUSAL

    from data.clients.odds import get_odds_client
    client = get_odds_client()
    fetched_at = datetime.now(UTC).isoformat()
    try:
        raw = client.get_ncaaf_spreads()
    except Exception as exc:
        # A clean message rather than a raw traceback: this runs unattended, and the last 120 log
        # lines are what land in the auto-Issue. Matches fetch_results.py's handling.
        print(f"Odds fetch failed: {type(exc).__name__}: {exc}")
        return EXIT_ERROR
    # Both stores: the committed append-only ledger (the SPEC §10.5 record, survives a fresh
    # checkout) and the legacy single-value cache (gitignored, kept as a fallback).
    # ORDER MATTERS: the observation first, then the accounting. The credit is already spent by the
    # time this line runs, and the observation is the only thing that cannot be reconstructed — the
    # market moves on, and this instant never comes back. The balance can be re-read from the next
    # response header. With the accounting first, a ledger failure threw away an observation we had
    # already paid for (review of the D44 PR, finding 1). A ledger failure after this point still
    # fails the run loudly: the spend must never go unrecorded silently.
    gamelines = odds_norm.normalize_lines(raw, fetched_at)
    games = {key: asdict(gl) for gl in gamelines.values()
             if (key := f"{gl.away_team}@{gl.home_team}") in slate}
    added = record_observation(args.week, games, year=args.year)

    # Neither store may take the observation down with it. Reversing the order (D44 finding 1) kept
    # the observation on disk but not in the repository: the exception escaped, the run exited 1,
    # and the commit step — gated on rc == '0' — never ran. Exit 5 carries the fact that the
    # observation is committable, and `daily-capture.yml` commits before it fails the job (D46).
    accounting_error: str | None = None
    try:
        record_quota(client.last_quota)
        append_ledger(client.last_quota, caller="fetch_lines", week=args.week,
                      run_id=os.environ.get("GITHUB_RUN_ID"))
    except Exception as exc:                       # noqa: BLE001
        accounting_error = f"{type(exc).__name__}: {exc}"

    print(f"Appended {added} slate observation(s) at {fetched_at} "
          f"({len(games)}/{len(slate)} slate games had lines). "
          f"Odds credits remaining: {(client.last_quota or {}).get('remaining')}")
    if accounting_error is not None:
        print(f"::error::the Odds spend was NOT recorded ({accounting_error}). The observation is "
              f"on disk and is committed by the step after this one; this run still ends red, "
              f"because an unrecorded spend must never be silent. The balance re-derives from the "
              f"next response header — the observation would not (D46).")
        return EXIT_ACCOUNTING_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
