#!/usr/bin/env python3
"""Fetch a week's final scores → the append-only results artifact (Phase 5, SPEC §10.3).

The Sunday grade job's missing input: `scripts/grade.py` joins
``data/predictions/YYYY_week_NN.json`` (byte-immutable claims, D22) with
``data/results/YYYY_week_NN.json`` (finals) by ``game_id``, and until now nothing wrote the second
file for 2026. (``scripts/fetch_week1_results.py`` is 2025-era, hardcoded to 2025 paths, on the
pre-Phase-1 ``utils/results_fetcher``, and writes a different filename convention.)

**Results are scoped to the CLAIMS, and keyed by the claim's own ``game_id``.** The alternative —
re-deriving an id from the CFBD row — means two independent constructions have to agree, and when
they don't, `grade.py` reports a fully-ungraded week that reads as "no games completed" rather than
as an error. Taking the id from the prediction makes the join exact by construction, so that
failure mode cannot occur.

**Postponements are handled, and visible.** The fetch pulls the whole season in one CFBD call (the
same call `SnapshotBuilder` makes) and matches each claim by canonical ``(away, home)``, not by
CFBD's week number. A game moved to a later week therefore still grades against the week it was
predicted in, and the week it actually completed in is recorded as ``completed_in_week`` rather
than silently discarded.

**Merge, never clobber.** ``data/results/`` is append-only (D23): an existing entry is preserved
byte-for-byte, only new games are appended, and the file is not rewritten when nothing was added.
This mirrors ``analytics.grading.merge_graded`` and ``data.snapshot.lines.record_observation``, and
it is what makes the week safe to fetch repeatedly — Sunday, then again on the Tuesday catch-up.

Usage:
  python scripts/fetch_results.py --week N [--year 2026] [--dry-run]

Exit codes: 0 ok (including "nothing new"), 1 error, 3 no completed games yet (not a failure —
the caller commits nothing and tries again on the next run).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.normalize.cfbd import normalize_games  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"
RESULTS_DIR = ROOT / "data" / "results"

EXIT_OK, EXIT_ERROR, EXIT_NOTHING_COMPLETED = 0, 1, 3

# Fields carried per result record. `game_id`, `home_score` and `away_score` are the contract
# `analytics.grading` actually reads (`_gradable` + the id join); the rest is provenance so a
# graded week can be audited without re-fetching.
RESULT_KEYS = ("game_id", "home_team", "away_team", "week", "home_score", "away_score",
               "completed_in_week", "start_date", "neutral_site", "source", "fetched_at")


def results_path(week: int, year: int) -> Path:
    return RESULTS_DIR / f"{year}_week_{week:02d}.json"


def predictions_path(week: int, year: int) -> Path:
    return PREDICTIONS_DIR / f"{year}_week_{week:02d}.json"


def _load_json(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def build_results(predictions_env: dict, games: list, *, week: int, year: int,
                  fetched_at: str, source: str = "cfbd_v2") -> dict[str, Any]:
    """Join claims to normalized season games → the results envelope. Pure; no I/O."""
    by_pair: dict[tuple[str, str], Any] = {}
    for g in games:
        # Keep the EARLIEST-week occurrence of a matchup so a rematch later in the season cannot
        # overwrite the game a week-N claim refers to.
        key = (g.away_team, g.home_team)
        if key not in by_pair or (g.week or 0) < (by_pair[key].week or 0):
            by_pair[key] = g

    records: list[dict] = []
    pending: list[str] = []
    unmatched: list[str] = []

    for pred in predictions_env.get("predictions", []):
        home, away = pred.get("home_team"), pred.get("away_team")
        gid = pred.get("game_id")
        game = by_pair.get((away, home))
        if game is None:
            unmatched.append(f"{away}@{home}")
            continue
        if not game.completed or game.home_points is None or game.away_points is None:
            pending.append(f"{away}@{home}")
            continue
        records.append({
            "game_id": gid,
            "home_team": home,
            "away_team": away,
            "week": week,
            "home_score": game.home_points,
            "away_score": game.away_points,
            # Surfaced, not silently normalized away: a value != `week` means the game moved.
            "completed_in_week": game.week,
            "start_date": game.start_date,
            "neutral_site": game.neutral_site,
            "source": source,
            "fetched_at": fetched_at,
        })

    records.sort(key=lambda r: r["game_id"])
    return {
        "week": week,
        "season": year,
        "recorded_date": fetched_at[:10],
        "coverage": {
            "predicted": len(predictions_env.get("predictions", [])),
            "completed": len(records),
            "pending": sorted(pending),
            "unmatched": sorted(unmatched),
            "postponed": sorted(r["game_id"] for r in records
                                if r["completed_in_week"] not in (None, week)),
        },
        "results": records,
    }


def merge_results(existing: dict | None, fresh: dict) -> tuple[dict, int]:
    """Append-only merge: an already-recorded final is immutable; only new games are added."""
    if existing is None:
        return fresh, len(fresh["results"])

    seen = {r.get("game_id") for r in existing.get("results", [])}
    added = [r for r in fresh["results"] if r.get("game_id") not in seen]
    merged = dict(existing)
    merged["results"] = sorted(existing.get("results", []) + added,
                               key=lambda r: r.get("game_id") or "")
    # Coverage is a live view of the latest fetch, not history.
    merged["coverage"] = fresh["coverage"]
    merged["recorded_date"] = existing.get("recorded_date", fresh["recorded_date"])
    merged["last_fetch"] = fresh["recorded_date"]
    return merged, len(added)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a week's finals into data/results/.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written; write nothing")
    args = parser.parse_args(argv)
    week, year = args.week, args.year

    predictions_env = _load_json(predictions_path(week, year))
    if predictions_env is None:
        print(f"No predictions for {year} week {week:02d} — nothing to fetch results against. "
              f"Run the predict job first.")
        return EXIT_ERROR

    from data.clients.cfbd_v2 import get_cfbd_v2_client
    fetched_at = datetime.now(UTC).isoformat()
    try:
        # One league-wide call for the whole season — the same shape SnapshotBuilder uses, and
        # what lets a postponed game still be found under a different CFBD week.
        raw = get_cfbd_v2_client().get_games(year)
    except Exception as exc:
        print(f"CFBD fetch failed: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    fresh = build_results(predictions_env, normalize_games(raw),
                          week=week, year=year, fetched_at=fetched_at)
    cov = fresh["coverage"]

    if not fresh["results"]:
        print(f"No completed games yet for {year} week {week:02d} "
              f"({cov['predicted']} predicted, {len(cov['pending'])} pending). Nothing written.")
        return EXIT_NOTHING_COMPLETED

    existing = _load_json(results_path(week, year))
    merged, added = merge_results(existing, fresh)

    if added == 0 and existing is not None:
        print(f"No new finals for {year} week {week:02d} "
              f"({len(existing.get('results', []))} already recorded). No-op.")
        return EXIT_OK

    if args.dry_run:
        print(f"[dry-run] would add {added} final(s) to {results_path(week, year).name}")
        return EXIT_OK

    out = results_path(week, year)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {out.relative_to(ROOT)}")
    print(f"  {cov['completed']}/{cov['predicted']} completed (+{added} new) | "
          f"pending: {len(cov['pending'])} | unmatched: {len(cov['unmatched'])}")
    if cov["postponed"]:
        print(f"  postponed (completed in another CFBD week): {', '.join(cov['postponed'])}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
