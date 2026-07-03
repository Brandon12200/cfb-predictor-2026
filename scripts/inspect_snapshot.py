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

    if game:
        lines += _render_game(manifest, snapshot, game)
    else:
        gc = manifest["coverage"]["games"]
        lines.append("")
        lines.append(f"slate games ({len(gc)}):")
        for key, cov in sorted(gc.items()):
            lines.append(f"  {key:28} {cov}")
    return "\n".join(lines)


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
            out.append(f"  intel[{team}]: rest={si['rest_days']} travel={si['travel_distance']} "
                       f"tz={si['time_zones_crossed']}{si['tz_direction'] and ' '+si['tz_direction'] or ''} "
                       f"alt={si['altitude']} sandwich={si['sandwich_spot']}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a snapshot's provenance manifest.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--game", default=None, help='e.g. "CLEMSON@GEORGIA"')
    args = parser.parse_args()

    manifest = load_manifest(args.week, args.year)
    snapshot = load_snapshot(args.week, args.year)
    print(render_manifest(manifest, snapshot, game=args.game))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
