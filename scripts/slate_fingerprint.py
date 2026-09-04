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
import contextlib
import copy
import hashlib
import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.data_manager as dm  # noqa: E402
from data.snapshot import load_frozen_vehicle  # noqa: E402
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


# Decimal places for the companion hash. The exact hash is a function of every bit of every float,
# so it also measures the platform's libm: `engine/power_ratings.py` calls math.exp/log/erf, and
# glibc is free to differ by an ULP between builds without any correctly-rounded guarantee. That is
# what moved the gate on 2026-09-02 when the runner image rolled, with the repository byte-identical.
# Why 10 dp, measured on the pinned vehicle rather than asserted: the payload's 14,818 non-zero
# floats span 9.740e-04 (the smallest `edge_size`) to 2.154e+03 (a `home_rating`), and NOTHING sits
# below 1e-8. So the rounding floor is ~7 orders of magnitude under the smallest quantity the model
# actually produces, while still being ~6 above the relative noise of a double. The real evidence
# for the choice is not that arithmetic, though — it is that five environments with four distinct
# exact hashes agree on one rounded hash (D41).
ROUNDING_DP = 10


def _round_floats(obj, dp: int = ROUNDING_DP):
    """Recursively round every float to `dp` places, leaving everything else untouched.

    `bool` is checked before `int`/`float` only for clarity — bools are ints, not floats, so they
    would pass through anyway.

    **`-0.0` is normalised to `0.0`, and that is load-bearing rather than tidy.** `json.dumps`
    renders the two differently (`-0.0` vs `0.0`) while IEEE-754 says they are equal, so a payload
    carrying one hashes differently from the identical payload carrying the other — the exact class
    of platform-dependent difference this function exists to erase. It is not hypothetical here:
    the pinned vehicle's payload holds **exactly one** negative zero, at
    `games["12|INDIANA@WASHINGTON"]["power_rating_spread"]` (measured 2026-09-03, 1 of 37,375
    floats), and the sign of a computed zero depends on the arithmetic path that produced it.
    Rounding alone leaves that one value free to flip the hash on a platform that reaches `+0.0`
    instead, which would defeat the whole point. Measured on this vehicle: plain `round()` gives
    `baf516aa…`, normalised gives `c5def3f1…`.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        r = round(obj, dp)
        return 0.0 if r == 0 else r
    if isinstance(obj, dict):
        return {k: _round_floats(v, dp) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, dp) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_round_floats(v, dp) for v in obj)
    return obj


def _sha256_of(payload) -> str:
    """The one place a payload becomes a hash — both hashes below go through it, so they cannot
    drift onto different serialisation settings."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


@contextlib.contextmanager
def engine_reads(bundle: dict) -> Iterator[dict]:
    """Point the frozen engine's snapshot reader at `bundle` for the duration.

    Load-bearing for every frozen-gate call site. `PredictionEngine` loads its own snapshot
    through `data.data_manager` — so handing a bundle to a caller (e.g.
    `analytics.predictions.build_predictions`, whose docstring says as much) redirects only
    *enumeration*; pricing would still read whatever is on disk. Without this wrapper a gate
    reading the pinned vehicle gets a **split read** — enumeration pinned, pricing live — which
    is worse than either, because it looks correct.
    """
    original = dm.load_snapshot
    try:
        dm.load_snapshot = lambda week, year=2026, base=None: bundle  # noqa: ARG005
        yield bundle
    finally:
        dm.load_snapshot = original


def tracked_slate(snapshot: dict) -> list[dict]:
    tracked = get_all_tracked_teams()
    return sorted(
        (g for g in snapshot["data"]["games"]
         if g.get("home_team") in tracked and g.get("away_team") in tracked),
        key=lambda g: (g.get("week") or 0, g.get("away_team"), g.get("home_team")),
    )


def fingerprint(snapshot: dict | None = None) -> dict:
    """`{"n_games", "sha256", "sha256_rounded"}` over the full engine output for the tracked slate.

    Two hashes over the **same** payload. `sha256` is exact — every bit of every float — and is the
    historical constant the gate has always asserted. `sha256_rounded` is the same payload with
    every float put through `round(x, 10)` first, which makes it independent of the platform's libm
    while staying sensitive to any change large enough to matter. Both are reported so a mismatch
    can be classified rather than guessed at: exact differs and rounded matches means the platform
    moved, both differ means model output moved.

    Defaults to the **pinned** tag-time vehicle (`data/archive/frozen/`, D29), never the live
    `data/snapshots/2026_week_01/` bundle — the Phase-5 pipeline rebuilds that one every week-1
    run, which would make this gate measure whether the pipeline ran rather than whether the
    model moved.
    """
    snap = snapshot or load_frozen_vehicle()
    games = tracked_slate(snap)

    bundle = copy.deepcopy(snap)
    lines = bundle["data"]["betting_lines"]
    for g in games:
        lines.setdefault(f"{g['away_team']}@{g['home_team']}", {
            "home_team": g["home_team"], "away_team": g["away_team"],
            "vegas_spread": PLACEHOLDER_SPREAD, "observation": {"fetched_at": None},
        })
    with engine_reads(bundle):
        engine = PredictionEngine()
        records = {
            f"{g.get('week'):02d}|{g['away_team']}@{g['home_team']}":
                engine.generate_prediction(g["home_team"], g["away_team"], week=g.get("week"))
            for g in games
        }

    payload = {"volatile_excluded": list(VOLATILE),
               "placeholder_spread": PLACEHOLDER_SPREAD,
               "games": _scrub(records)}
    return {"n_games": len(records),
            "sha256": _sha256_of(payload),
            "sha256_rounded": _sha256_of(_round_floats(payload))}


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
        print(f"  ... rounded {ROUNDING_DP}dp : {fp['sha256_rounded']}")
        print("\nIf this moved and you did not intend it, something changed model output — "
              "including via the freeze-exempt data/ seam. That needs a documented SPEC §3 "
              "exception, not a gate update.")
        print(f"If the EXACT hash moved but the {ROUNDING_DP}dp one did not, the difference is "
              "below 1e-10 and the model did not move — that is the platform (libm differs by an "
              "ULP between builds; the engine calls math.exp/log/erf). Report both.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
