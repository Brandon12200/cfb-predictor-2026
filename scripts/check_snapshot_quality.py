#!/usr/bin/env python3
"""Gate a freshly-built snapshot against the `season.json` data-quality thresholds (SPEC §10.6).

Runs after `build_snapshot.py` and before the week's predictions are built, so a degraded slate is
caught while it is still cheap — a claim, once committed, is byte-immutable forever (D22).

**Per-threshold severity, from `season.json` `pipeline.data_quality.on_breach`.** Coverage is
`warn`, not `fail`, and that is deliberate: the committed preseason manifest reports **39%** field
coverage over 10 slate games, because most inputs genuinely do not exist yet. An honestly-low
snapshot is still evidence and must still be committed — a gate that fails every August build is a
gate an operator learns to route around. What `fail` is reserved for is a slate that is *empty* or
a registry that has *collapsed*, which mean the fetch is broken rather than the data being early.

Usage: python scripts/check_snapshot_quality.py --week N [--year 2026]
Exit codes: 0 ok (warnings allowed), 1 a `fail`-severity threshold was breached.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.snapshot.store import SnapshotNotFoundError, load_manifest  # noqa: E402
from data.team_registry import get_fbs_canonical_names  # noqa: E402
from utils.season_calendar import load_calendar  # noqa: E402

EXIT_OK, EXIT_FAIL = 0, 1


def evaluate(summary: dict, fbs_count: int, thresholds: dict) -> list[tuple[str, str, str]]:
    """→ [(severity, key, message)] for every breached threshold. Pure."""
    on_breach = thresholds.get("on_breach", {})
    checks = [
        ("min_slate_games", summary.get("slate_games", 0),
         "slate games in the snapshot"),
        ("min_registry_teams", fbs_count,
         "FBS teams in the season registry"),
        ("min_snapshot_coverage_pct", summary.get("coverage_pct", 0.0),
         "percent of manifest fields present"),
    ]
    breaches = []
    for key, actual, label in checks:
        floor = thresholds.get(key)
        if floor is None or actual >= floor:
            continue
        breaches.append((on_breach.get(key, "fail"), key,
                         f"{label}: {actual} < {floor}"))
    return breaches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a snapshot against season.json thresholds.")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args(argv)

    thresholds = ((load_calendar().get("pipeline") or {}).get("data_quality") or {})
    try:
        manifest = load_manifest(args.week, args.year)
    except SnapshotNotFoundError as exc:
        print(f"ABORT: {exc}")
        return EXIT_FAIL

    summary = manifest.get("summary", {})
    breaches = evaluate(summary, len(get_fbs_canonical_names()), thresholds)

    lines = [f"### Snapshot quality — {args.year} week {args.week:02d}",
             f"- slate games: {summary.get('slate_games')}",
             f"- teams covered: {summary.get('teams')}",
             f"- field coverage: {summary.get('coverage_pct')}% "
             f"({summary.get('fields_present')}/{summary.get('fields_total')})"]
    for warning in manifest.get("calendar_warnings", []) or []:
        lines.append(f"- **calendar warning**: {warning}")
    for severity, key, message in breaches:
        lines.append(f"- **{severity.upper()}** {key} — {message}")
    if not breaches:
        lines.append("- all thresholds met")

    body = "\n".join(lines)
    print(body)
    if (summary_path := os.environ.get("GITHUB_STEP_SUMMARY")):
        with open(summary_path, "a") as fh:
            fh.write(body + "\n")

    return EXIT_FAIL if any(s == "fail" for s, _, _ in breaches) else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
