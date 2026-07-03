#!/usr/bin/env python3
"""Refresh the committed season team-registry artifacts from CFBD (SPEC §5.5, D7).

The ONLY networked path into the registry. Fetches `/teams` + `/calendar` live,
prints the FBS membership diff vs the committed artifact, and requires an explicit
`yes` before overwriting — a CFBD hiccup or mid-season data error must never silently
rewrite slate scope. Commit the changed `data/registry/*.json` and record the reason
in `docs/DECISIONS.md`.

Usage:
    python scripts/refresh_registry.py [--year 2026] [--yes]

`--yes` skips the confirmation prompt (for non-interactive re-runs); omit it for the
normal review-then-write flow. A `cfb data registry` CLI wrapper lands with the 1c
`cfb data` tooling; this script is the interim operational entry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.clients.cfbd_v2 import get_cfbd_v2_client  # noqa: E402
from data.team_registry import DEFAULT_YEAR, refresh_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh CFBD team-registry artifacts.")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--yes", action="store_true",
                        help="skip the confirm-before-overwrite prompt")
    args = parser.parse_args()

    result = refresh_registry(get_cfbd_v2_client(), year=args.year, confirm=not args.yes)
    return 0 if result.get("written") else 1


if __name__ == "__main__":
    raise SystemExit(main())
