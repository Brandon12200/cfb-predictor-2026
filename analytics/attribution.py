"""Per-factor attribution (Phase 4, SPEC §8 item 4) — freeze-exempt. **The 2027 payoff.**

For each factor, over the games where it **activated** (fired ≥ its threshold — the v2
``factor_breakdown[factor]['activated']`` flag), report the ATS% and average CLV of those games.
This is what converts the Phase-3 `reasoned` CALIBRATION_LOG entries → `measured`: e.g. "when
``DesperationIndex`` fired (3c.3), what did those bets do?", "did ``TravelBurden`` at its 60%-of-HFA
cap (3b.1) earn its keep?". Next July's recalibration reads this like a lab notebook with results in.

Per-sub-signal breakdown requires the v2 ``factor_breakdown``; v1-converted 2025 records are flat
(``_v1_flat``) and cannot be attributed per-signal — reported honestly as unavailable, not faked.
"""

from __future__ import annotations

import statistics
from typing import Any

from analytics.calibration_evidence import ats_outcome, wilson_interval
from utils.prediction_schema import clv as clv_from_close


def _rate_and_clv(records: list[dict], *, clv_key: str = "clv") -> dict[str, Any]:
    """ATS record + Wilson + CLV aggregate over a set of joined records."""
    graded = [r for r in records if r.get("ats_result") in ("win", "loss", "push")]
    wins = sum(1 for r in graded if r["ats_result"] == "win")
    losses = sum(1 for r in graded if r["ats_result"] == "loss")
    pushes = sum(1 for r in graded if r["ats_result"] == "push")
    n = wins + losses
    lo, hi = wilson_interval(wins, n)
    clvs = [r[clv_key] for r in records if isinstance(r.get(clv_key), (int, float))]
    beat = sum(1 for c in clvs if c > 0)
    # Placed vs hypothetical, on the same convention as kpis/calibration/selectivity. Preseason
    # every game is NO_BET, so a lean-split cell can be 100% "what would have happened" — and an
    # unlabeled measurement being read as a track record is the D17 failure in miniature.
    hypothetical = sum(1 for r in records if r.get("is_hypothetical"))
    return {
        "n_games": len(records), "n_graded": n, "wins": wins, "losses": losses, "pushes": pushes,
        "n_placed": len(records) - hypothetical, "n_hypothetical": hypothetical,
        "ats_win_pct": round(wins / n, 4) if n else None,
        "wilson_95": [round(lo, 4), round(hi, 4)] if n else None,
        "avg_clv": round(statistics.mean(clvs), 3) if clvs else None,
        "n_clv": len(clvs),
        "clv_positive_pct": round(beat / len(clvs), 4) if clvs else None,
    }


def by_lean_side(joined: list[dict]) -> dict[str, Any]:
    """**D27's obligation, and the primary result.** ATS% and CLV split by which side the model
    leaned, plus a naive always-lean-home baseline over the same games.

    Why this is not optional, and why a blended headline is not acceptable: the model's live signal
    is dominated by physical factors that are **asymmetric by construction** — `TravelBurden` and
    `ConsecutiveRoad` can only ever penalise the visitor, `Altitude` only advantages the host — so
    preseason leans ran **195 home / 35 away (5.57:1)**. A single blended number over that skew is
    dominated by how home teams happened to do against the spread, and is uninterpretable as
    evidence about the model.

    **This is D17 pre-empted.** D17's retired "57.0% ATS" headline was exactly this failure: the
    harness graded "the home team covered the model's own number", measured a systematic home lean,
    and reported it as skill. Honest regrade: 46.6%. Splitting by side, and differencing against the
    naive baseline, is what makes the number mean something.

    The baseline is graded **against the Vegas line** — it is NOT the retired D17 diagnostic
    (always-home vs the model's *own* contrarian number), which survives under its honest name in
    `scripts/grading.py::home_covered_model_spread_diagnostic` and must never be confused with this.
    """
    with_side = [r for r in joined if r.get("edge_direction") in ("home", "away")]
    neutral = [r for r in joined if r.get("edge_direction") not in ("home", "away")]
    sides = {side: _rate_and_clv([r for r in with_side if r["edge_direction"] == side])
             for side in ("home", "away")}

    # Matched set: the games the model actually graded. Comparing the baseline over a different
    # game set would confound side-selection skill with slate composition.
    matched = [r for r in joined if r.get("ats_result") in ("win", "loss", "push")]
    baseline_records = []
    for rec in matched:
        outcome = ats_outcome({**rec, "edge_direction": "home"}, rec)
        baseline_records.append({
            **rec,
            "ats_result": outcome,
            # CLV from the always-home perspective, via the same ratified convention (D21.3).
            "baseline_clv": clv_from_close(rec.get("vegas_spread"), rec.get("closing_spread"), "home"),
        })
    baseline = _rate_and_clv(baseline_records, clv_key="baseline_clv")

    model_overall = _rate_and_clv(matched)
    delta = (None if model_overall["ats_win_pct"] is None or baseline["ats_win_pct"] is None
             else round(model_overall["ats_win_pct"] - baseline["ats_win_pct"], 4))

    n_home, n_away = sides["home"]["n_games"], sides["away"]["n_games"]
    n_hypothetical = sum(1 for r in matched if r.get("is_hypothetical"))
    return {
        "meta": {
            "n_games": len(joined),
            "n_with_side": len(with_side),
            "n_neutral": len(neutral),
            "home_away_ratio": round(n_home / n_away, 2) if n_away else None,
            "n_graded": len(matched),
            "n_placed": len(matched) - n_hypothetical,
            "n_hypothetical": n_hypothetical,
            "all_hypothetical": bool(matched) and n_hypothetical == len(matched),
            "note": ("Leans are structurally home-skewed: TravelBurden/ConsecutiveRoad only "
                     "penalise the visitor and Altitude only advantages the host (D27). Read the "
                     "away cell's Wilson interval before drawing anything from it."),
        },
        "sides": sides,
        "neutral": {
            "n_games": len(neutral),
            "reason": ("no side taken — CLV is defined from the bet side's perspective, so it is "
                       "null rather than 0.0 (D22 f3). Their own selectivity bucket, never win-rated."),
        },
        "model_overall": model_overall,
        "baseline_always_home": baseline,
        "vs_baseline": {
            "ats_delta": delta,
            "note": ("Model ATS% minus a naive always-lean-home bet on the same games, graded "
                     "against the Vegas line. A delta at or below zero means the model's "
                     "side-selection added nothing over 'always take the home team'."),
        },
    }


def _is_v2_breakdown(fb: Any) -> bool:
    return isinstance(fb, dict) and not fb.get("_v1_flat") and all(
        isinstance(v, dict) for k, v in fb.items() if k != "_v1_flat")


def per_factor(joined: list[dict], *, min_n: int = 1) -> dict[str, Any]:
    """{factor: {n_activated, ats(win/loss/pct/wilson), avg_clv, n_clv}} over games where the factor
    activated. ``meta.attributable`` flags whether the slate carries per-sub-signal breakdowns."""
    v2 = [r for r in joined if _is_v2_breakdown(r.get("factor_breakdown"))]
    if not v2:
        return {"meta": {"attributable": False,
                         "reason": "no per-sub-signal factor_breakdown (v1-flat archive / empty slate)"},
                "factors": {}}

    factor_names = sorted({name for r in v2 for name in r["factor_breakdown"] if name != "_v1_flat"})
    factors: dict[str, Any] = {}
    for name in factor_names:
        fired = [r for r in v2 if r["factor_breakdown"].get(name, {}).get("activated")]
        graded = [r for r in fired if r.get("ats_result") in ("win", "loss", "push")]
        wins = sum(1 for r in graded if r["ats_result"] == "win")
        losses = sum(1 for r in graded if r["ats_result"] == "loss")
        n = wins + losses
        clvs = [r["clv"] for r in fired if isinstance(r.get("clv"), (int, float))]
        lo, hi = wilson_interval(wins, n)
        factors[name] = {
            "n_activated": len(fired),
            "n_graded": n, "wins": wins, "losses": losses,
            "ats_win_pct": round(wins / n, 4) if n else None,
            "wilson_95": [round(lo, 4), round(hi, 4)] if n else None,
            "avg_clv": round(statistics.mean(clvs), 3) if clvs else None,
            "n_clv": len(clvs),
        }
    return {"meta": {"attributable": True, "n_games": len(v2),
                     "note": "read the Wilson intervals — first-season per-factor cells are small"},
            "factors": {k: v for k, v in factors.items() if v["n_activated"] >= min_n}}
