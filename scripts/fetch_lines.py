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

Exit codes (Phase 5): 0 appended, 1 error (no snapshot / fetch failed), **3 budget refusal**.
A budget stop is a designed outcome, not a failure — the scheduled capture job commits nothing
and stays green on 3, but alarms on 1. They shared exit 1 until Phase 5, which left the workflow
string-matching stdout to tell them apart.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.normalize import odds as odds_norm  # noqa: E402
from data.odds_budget import last_remaining, record_quota  # noqa: E402
from data.snapshot.lines import record_observation  # noqa: E402
from data.snapshot.store import SnapshotNotFoundError, load_snapshot  # noqa: E402


EXIT_OK, EXIT_ERROR, EXIT_BUDGET_REFUSAL = 0, 1, 3


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
    raw = client.get_ncaaf_spreads()
    record_quota(client.last_quota)  # persist the fresh balance for the next run's guard

    gamelines = odds_norm.normalize_lines(raw, fetched_at)
    games = {key: asdict(gl) for gl in gamelines.values()
             if (key := f"{gl.away_team}@{gl.home_team}") in slate}
    added = record_observation(args.week, games, year=args.year)

    print(f"Appended {added} slate observation(s) at {fetched_at} "
          f"({len(games)}/{len(slate)} slate games had lines). "
          f"Odds credits remaining: {(client.last_quota or {}).get('remaining')}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
