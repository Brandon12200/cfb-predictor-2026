#!/usr/bin/env python3
"""Reproduce the edge-ceiling and confidence-quantization measurements (CALIBRATION_LOG) — offline.

Freeze-exempt. Committed so the CALIBRATION_LOG entry "Edge ceiling vs the `min_edge` ladder" is
**re-verifiable** rather than resting on an ad hoc run: the entry creates a Phase-4 attribution
obligation, and unreproducible evidence in a frozen record is exactly what the calibration audit
exists to catch.

Reports, all from the committed week-1 snapshot (no network):
  1. the max attainable |total_adjustment| under two scenarios;
  2. how often ByeAdvantage and ShortWeek co-fire on the real slate — they are NOT mutually
     exclusive (a first draft of the log entry wrongly assumed they were), so no discount applies;
  3. the confidence_score quantization + tier split over the tracked slate.

Usage: python scripts/measure_edge_ceiling.py   (offline)
"""

from __future__ import annotations

import copy
import logging
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.data_manager as dm  # noqa: E402
from data.schedule_intel import compute_schedule_intel  # noqa: E402
from data.snapshot import load_snapshot  # noqa: E402
from data.team_registry import get_all_tracked_teams  # noqa: E402
from engine.prediction_engine import (  # noqa: E402
    CONFIDENCE_TIER_A_MIN,
    NO_BET_CONFIDENCE_FLOOR,
    PredictionEngine,
)
from factors.base_calculator import FactorConfidence, FactorType  # noqa: E402
from factors.factor_registry import factor_registry as REGISTRY  # noqa: E402

VERY_HIGH = FactorConfidence.VERY_HIGH.value

# Structurally dormant for 2026 by ratified decision — calculate() cannot return non-zero.
DORMANT = {"HeadToHeadRecord", "PressureSituation", "RevengeGame", "StyleMismatch", "MarketSentiment"}
# Cannot fire on the committed vehicle (inputs never populate), though not dormant by decision.
INPUT_DORMANT = {"ExperienceDifferential", "Sandwich"}


def _max_contribution(name: str) -> float:
    f = REGISTRY.factors[name]
    conf = max(VERY_HIGH, 0.5) if f.factor_type == FactorType.PRIMARY else VERY_HIGH
    return abs(f._max_output) * f.weight * conf


def ceilings() -> dict[str, float]:
    live = [n for n, f in REGISTRY.factors.items()
            if n not in DORMANT and not getattr(f, "is_multiplicative", False)]
    theoretical = sum(_max_contribution(n) for n in live)
    # NOTE: an earlier draft subtracted the smaller of ByeAdvantage/ShortWeek on the belief they
    # were mutually exclusive. They are NOT: a single team cannot hold both states, but the
    # factors compare ACROSS teams, and the pairing occurs on the real slate (see
    # `bye_shortweek_cooccurrence`). No such subtraction is made.
    vehicle = theoretical - sum(_max_contribution(n) for n in INPUT_DORMANT)
    return {"theoretical": theoretical, "vehicle": vehicle}


def bye_shortweek_cooccurrence(snap: dict) -> tuple[int, int]:
    """Games where one team is on a bye AND the opponent is on a short week.

    These two factors are **NOT** mutually exclusive by construction: a single team cannot hold both
    states, but the factors compare ACROSS teams, so home-bye + away-short-week co-fires in the same
    direction. Verified constructible, and it occurs on the real slate — so the ceiling takes no
    exclusivity discount. This function is the standing check on that.
    """
    data = snap["data"]
    venues, games = data["venues"], data["games"]
    tracked = get_all_tracked_teams()
    slate = [g for g in games
             if g.get("home_team") in tracked and g.get("away_team") in tracked]
    hits = 0
    for g in slate:
        h, a, wk, gd = g["home_team"], g["away_team"], g.get("week"), g.get("start_date")
        neutral = bool(g.get("neutral_site"))
        gv = None if neutral else venues.get(h)
        hi = compute_schedule_intel(h, a, wk or 1, gd, not neutral, gv, games, venues)
        ai = compute_schedule_intel(a, h, wk or 1, gd, False, gv, games, venues)
        if (hi.get("bye") and ai.get("short_week")) or (ai.get("bye") and hi.get("short_week")):
            hits += 1
    return hits, len(slate)


def confidence_profile(snap: dict) -> dict:
    data = snap["data"]
    tracked = get_all_tracked_teams()
    slate = [g for g in data["games"]
             if g.get("home_team") in tracked and g.get("away_team") in tracked]
    bundle = copy.deepcopy(snap)
    for g in slate:
        bundle["data"]["betting_lines"].setdefault(f"{g['away_team']}@{g['home_team']}", {
            "home_team": g["home_team"], "away_team": g["away_team"],
            "vegas_spread": -3.0, "observation": {"fetched_at": None}})
    dm.load_snapshot = lambda week, year=2026, base=None: bundle  # noqa: ARG005

    eng = PredictionEngine()
    vals, tiers = [], Counter()
    for g in slate:
        r = eng.generate_prediction(g["home_team"], g["away_team"], week=g.get("week"))
        cs = r.get("confidence_score")
        if cs is None:
            continue
        vals.append(round(cs, 4))
        tiers[r.get("confidence_tier")] += 1
    c = Counter(vals)
    return {"n": len(vals), "distinct": len(set(vals)), "min": min(vals), "max": max(vals),
            "stdev": statistics.pstdev(vals), "tiers": dict(tiers),
            "modal_value": c.most_common(1)[0][0],
            "modal_share": c.most_common(1)[0][1] / len(vals)}


def main() -> int:
    # Scoped to the CLI entry: `verify_phase_3.py` imports `ceilings()` from this module, and a
    # module-scope disable would silently mute logging for that whole process.
    logging.disable(logging.CRITICAL)

    snap = load_snapshot(1, 2026)

    raw_sum = sum(f.original_weight for f in REGISTRY.factors.values())
    dormant_raw = sum(f.original_weight for n, f in REGISTRY.factors.items()
                      if n in DORMANT or getattr(f, "is_multiplicative", False))
    print(f"registry: {len(REGISTRY.factors)} factors, raw weight sum {raw_sum:.4f}")
    print(f"dormant + multiplicative raw share: {dormant_raw:.4f} "
          f"= {100 * dormant_raw / raw_sum:.1f}%")
    print(f"live normalized weights sum to {100 * (1 - dormant_raw / raw_sum):.1f}% of unity\n")

    c = ceilings()
    print("max attainable |total_adjustment|:")
    for label, key in (("theoretical (all live aligned)", "theoretical"),
                       ("this vehicle (minus input-dormant)", "vehicle")):
        v = c[key]
        marks = " ".join(f"{t}:{'YES' if v >= t else 'no'}" for t in (0.75, 1.0, 1.5))
        print(f"  {label:<52} {v:.4f}   {marks}")
    print(f"\n  0.75 needs {100 * 0.75 / c['theoretical']:.1f}% of the theoretical ceiling")
    print(f"  1.00 needs {100 * 1.0 / c['theoretical']:.1f}% of the theoretical ceiling")

    hits, total = bye_shortweek_cooccurrence(snap)
    print(f"\nbye + opponent-short-week co-occurrence on the tracked slate: {hits} of {total}")
    print("  (co-firing is constructible AND occurs; no exclusivity discount is applied)")

    p = confidence_profile(snap)
    print(f"\nconfidence_score over {p['n']} tracked games:")
    print(f"  distinct values {p['distinct']}   range {p['min']:.4f}..{p['max']:.4f}   "
          f"stdev {p['stdev']:.4f}")
    print(f"  modal value {p['modal_value']} covering {100 * p['modal_share']:.1f}% of games")
    print(f"  tiers {p['tiers']}   (A min {CONFIDENCE_TIER_A_MIN}, NO_BET floor {NO_BET_CONFIDENCE_FLOOR})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
