#!/usr/bin/env python3
"""Build a weekly data snapshot from CFBD + Odds (SPEC §5.2, D7).

Fetches league-wide, normalizes, and writes `data/snapshots/YYYY_week_NN/` with a
100%-coverage provenance manifest. Runs registry validation first (hard-fail on
membership drift). This is a networked entry; the polished `cfb data snapshot` CLI
lands with the Phase-4.5 CLI rewrite.

Usage: python scripts/build_snapshot.py --week N [--year 2026]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.clients.cfbd_v2 import get_cfbd_v2_client  # noqa: E402
from data.clients.odds import get_odds_client  # noqa: E402
from data.snapshot import SnapshotBuilder  # noqa: E402
from data.team_registry import registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a weekly data snapshot.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    if registry is None:
        print("Team registry not loaded — run `python scripts/refresh_registry.py` first.")
        return 1

    builder = SnapshotBuilder(get_cfbd_v2_client(), get_odds_client(), registry)
    manifest = builder.build(args.week, year=args.year)
    print(json.dumps(manifest["summary"], indent=2))
    if manifest["calendar_warnings"]:
        print(f"\ncalendar corroboration: {len(manifest['calendar_warnings'])} warning(s) (D1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
