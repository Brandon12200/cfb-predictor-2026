#!/usr/bin/env python3
"""Name the report files a Sunday run actually changed, for the report commit message.

**The defect.** Since PR #58 the Sunday job re-renders every gradable week, not only the current one,
but the commit message was still `report: <year> week <pipeline_week> + season to date`. On
2026-09-13 commit `535d2b9` was titled "report: 2026 week 02 + season to date" and also rewrote
`reports/2026_week_01.md` (8/11 → 11/11). `git log -- reports/` then misdescribes which weeks
moved, which is the one index a reader has to a rendering's history (D23).

This reads what is actually modified or new under `reports/` in the working tree, after rendering
and before the commit stages it, and prints a label naming exactly those files:

    weeks 01, 02 + season to date
    week 02 + season to date
    season to date
    no report changes

The label describes the commit's contents, not the set that was *rendered*: an unchanged re-render
produces identical bytes and is not committed, so naming it would misdescribe the commit the other
way.

Usage: python scripts/changed_report_weeks.py --year 2026
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def label_from_porcelain(porcelain: str, year: int) -> str:
    """Build the label from `git status --porcelain` output. Pure, so it can be tested directly."""
    week_re = re.compile(rf"(?:^|/)reports/{year}_week_(\d{{2}})\.md$")
    season_re = re.compile(rf"(?:^|/)reports/{year}_season\.md$")
    weeks: set[str] = set()
    season = False
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:                       # a rename reports "old -> new"; the new path counts
            path = path.split(" -> ", 1)[1]
        if m := week_re.search(path):
            weeks.add(m.group(1))
        elif season_re.search(path):
            season = True

    parts = []
    if weeks:
        ordered = sorted(weeks)
        parts.append(f"{'weeks' if len(ordered) > 1 else 'week'} {', '.join(ordered)}")
    if season:
        parts.append("season to date")
    return " + ".join(parts) if parts else "no report changes"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args(argv)
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "reports/"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    print(label_from_porcelain(out, args.year))
    return 0


if __name__ == "__main__":
    sys.exit(main())
