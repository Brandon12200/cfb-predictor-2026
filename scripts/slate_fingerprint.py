#!/usr/bin/env python3
"""Behavioural fingerprint of the frozen model over the tracked slate — offline, freeze-exempt.

**Why this exists.** The `v2026-frozen` tag freezes `factors/` and `engine/`, and the immutability
hook refuses edits there. But a prediction is a function of the frozen code AND the freeze-EXEMPT
`data/` seam — and that seam has already moved model output twice after ratification (A6's
metres/feet conversion, the venue-timezone fallback). Path-based protection cannot see that class of
change. This closes the gap **behaviourally**: it hashes what the model actually produces, so any
change anywhere — frozen or exempt — that moves a prediction fails the gate loudly and forces a
documented SPEC §3 exception rather than passing silently.

Script computes, `verify-phase-3` asserts (the same split as the edge ceiling).

The fingerprint covers all 330 both-teams-tracked games driven at their own week, hashing the
ENTIRE engine result per game — factor values, confidence internals, variance analysis, power
rating — not merely the persisted schema-v2 fields. Wall-clock/build-identity keys are excluded by
name and the exclusion list is part of the hashed payload, so it cannot be widened silently.

Usage: python scripts/slate_fingerprint.py [--json]   (offline)
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.data_manager as dm  # noqa: E402
from data.snapshot import load_snapshot  # noqa: E402
from data.team_registry import get_all_tracked_teams  # noqa: E402
from engine.prediction_engine import PredictionEngine  # noqa: E402

# Wall-clock / build identity — not model behaviour. Hashed as part of the payload (see
# `fingerprint`) so widening this set changes the hash and trips the gate.
VOLATILE = ("built_at", "generated_at", "model_version", "prediction_time", "timestamp")

# Deterministic stand-in for games with no prediction-time line. The engine refuses to price
# without one; the value is irrelevant to the fingerprint's purpose so long as it is fixed.
PLACEHOLDER_SPREAD = -3.0


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in sorted(obj.items()) if k not in VOLATILE}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def tracked_slate(snapshot: dict) -> list[dict]:
    tracked = get_all_tracked_teams()
    return sorted(
        (g for g in snapshot["data"]["games"]
         if g.get("home_team") in tracked and g.get("away_team") in tracked),
        key=lambda g: (g.get("week") or 0, g.get("away_team"), g.get("home_team")),
    )


def fingerprint(snapshot: dict | None = None) -> dict:
    """`{"n_games", "sha256"}` over the full engine output for the tracked slate."""
    snap = snapshot or load_snapshot(1, 2026)
    games = tracked_slate(snap)

    bundle = copy.deepcopy(snap)
    lines = bundle["data"]["betting_lines"]
    for g in games:
        lines.setdefault(f"{g['away_team']}@{g['home_team']}", {
            "home_team": g["home_team"], "away_team": g["away_team"],
            "vegas_spread": PLACEHOLDER_SPREAD, "observation": {"fetched_at": None},
        })
    original = dm.load_snapshot
    try:
        dm.load_snapshot = lambda week, year=2026, base=None: bundle  # noqa: ARG005
        engine = PredictionEngine()
        records = {
            f"{g.get('week'):02d}|{g['away_team']}@{g['home_team']}":
                engine.generate_prediction(g["home_team"], g["away_team"], week=g.get("week"))
            for g in games
        }
    finally:
        dm.load_snapshot = original

    payload = {"volatile_excluded": list(VOLATILE),
               "placeholder_spread": PLACEHOLDER_SPREAD,
               "games": _scrub(records)}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return {"n_games": len(records), "sha256": hashlib.sha256(blob).hexdigest()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    logging.disable(logging.CRITICAL)

    fp = fingerprint()
    if args.json:
        print(json.dumps(fp, indent=2, sort_keys=True))
    else:
        print(f"tracked-slate games : {fp['n_games']}")
        print(f"behavioural sha256  : {fp['sha256']}")
        print("\nIf this moved and you did not intend it, something changed model output — "
              "including via the freeze-exempt data/ seam. That needs a documented SPEC §3 "
              "exception, not a gate update.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
