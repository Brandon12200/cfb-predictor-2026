#!/usr/bin/env python3
"""Render a snapshot's provenance manifest (SPEC §5.3).

`cfb data inspect` (the CLI wrapper lands in Phase 4.5) — shows, per field-group,
which source answered vs `missing`, fetch timestamps, and coverage. With `--game`,
drills into one matchup's line observations, both teams' coverage, and schedule intel.

Usage: python scripts/inspect_snapshot.py --week N [--game "AWAY@HOME"] [--year 2026]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.snapshot.store import load_manifest, load_snapshot  # noqa: E402


def render_manifest(manifest: dict, snapshot: dict, game: str | None = None) -> str:
    meta, summary = manifest["meta"], manifest["summary"]
    lines = [
        f"snapshot {meta['snapshot_id']}  ({meta['year']} week {meta['week']}, built {meta['built_at']})",
        f"coverage: {summary['fields_present']}/{summary['fields_total']} present "
        f"({summary['coverage_pct']}%), {summary['fields_missing']} missing",
        "",
        "sources:",
    ]
    for group, s in sorted(manifest["sources"].items()):
        extra = f" quota={s['quota']}" if s.get("quota") else ""
        lines.append(f"  {group:16} source={s.get('source')!s:8} "
                     f"count={s.get('count', '-')!s:5} fetched={str(s.get('fetched_at'))[:19]}{extra}")

    # Per-field-group present/missing tallies across teams.
    from collections import Counter
    tallies: dict[str, Counter] = {}
    for cov in manifest["coverage"]["teams"].values():
        for grp, val in cov.items():
            tallies.setdefault(grp, Counter())[val] += 1
    lines.append("")
    lines.append("team field-group coverage:")
    for grp, c in sorted(tallies.items()):
        lines.append(f"  {grp:16} {dict(c)}")

    lines += _render_reconciliation(manifest)

    if game:
        lines += _render_game(manifest, snapshot, game)
    else:
        gc = manifest["coverage"]["games"]
        lines.append("")
        lines.append(f"slate games ({len(gc)}):")
        for key, cov in sorted(gc.items()):
            lines.append(f"  {key:28} {cov}")
    return "\n".join(lines)


def _render_reconciliation(manifest: dict) -> list[str]:
    """Slate reconciliation (SPEC §5.5.3) — what was excluded, and why.

    Reads `.get` throughout: snapshots built before the detector existed carry no reconciliation
    block, and an older bundle must still inspect cleanly rather than raise.
    """
    rec = manifest.get("reconciliation") or {}
    if not rec:
        return ["", "reconciliation: (not recorded — snapshot predates the detector)"]

    exc = rec.get("excluded_from_normalization", {})
    slate = rec.get("week_slate", {})
    odds = rec.get("odds_cross_reference", {})
    out = [
        "",
        f"reconciliation: {rec.get('cfbd_rows_fetched', '?')} CFBD rows → "
        f"{rec.get('games_normalized', '?')} games → {slate.get('tracked_games', '?')} on the "
        f"week-{slate.get('week', '?')} slate",
    ]
    for reason, count in sorted((exc.get("by_reason") or {}).items()):
        flag = "  ⚠" if reason == "unresolved_team_name" else "   "
        out.append(f"{flag} excluded {count:5} — {reason}")
    for key in exc.get("unresolved_team_name", []):
        out.append(f"     ⚠ unresolved: {key}  (an FBS game lost here would be a real defect)")
    if slate.get("out_of_scope"):
        out.append(f"    out of scope this week: {slate['out_of_scope']} "
                   f"(not both teams tracked)")
    out.append(f"    odds: {odds.get('events_normalized', '?')} events, "
               f"{odds.get('matched_to_slate', '?')} matched to the slate")
    for key in odds.get("unmatched_odds_events", []):
        out.append(f"    ⚠ odds event with no tracked slate game: {key}")
    for key in odds.get("slate_games_without_a_line", []):
        out.append(f"    slate game with no line (honest-missing): {key}")
    for key in odds.get("unresolved_events", []):
        out.append(f"    ⚠ odds event name unresolved: {key}")
    return out


def _render_game(manifest: dict, snapshot: dict, game: str) -> list[str]:
    out = ["", f"game {game}:"]
    gc = manifest["coverage"]["games"].get(game)
    if gc is None:
        return out + [f"  (not in slate — available: {sorted(manifest['coverage']['games'])})"]
    out.append(f"  coverage: {gc}")
    bl = snapshot["data"]["betting_lines"].get(game, {})
    out.append(f"  betting: vegas_spread={bl.get('vegas_spread')} kickoff={bl.get('kickoff')} "
               f"books={len((bl.get('observation') or bl).get('lines', []))}")
    for team in game.replace("@", " ").split():
        si = snapshot["data"].get("schedule_intel", {}).get(team)
        if si:
            # `alt` is read from the snapshot's STORED intel blob, which is frozen at build time.
            # Snapshots built before the A6 unit fix hold the raw metres-scale value, not feet —
            # the live prediction path recomputes intel and is unaffected, but this diagnostic
            # shows what was stored. Labelled so a pre-A6 snapshot can't be misread as feet.
            alt = si["altitude"]
            alt_label = "alt" if snapshot["meta"].get("schedule_intel_altitude_unit") == "ft" else "alt(as-stored)"
            out.append(f"  intel[{team}]: rest={si['rest_days']} travel={si['travel_distance']} "
                       f"tz={si['time_zones_crossed']}{si['tz_direction'] and ' '+si['tz_direction'] or ''} "
                       f"{alt_label}={alt} sandwich={si['sandwich_spot']}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a snapshot's provenance manifest.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--game", default=None, help='e.g. "CLEMSON@GEORGIA"')
    args = parser.parse_args(argv)

    manifest = load_manifest(args.week, args.year)
    snapshot = load_snapshot(args.week, args.year)
    print(render_manifest(manifest, snapshot, game=args.game))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
