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

from analytics.calibration_evidence import wilson_interval


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
