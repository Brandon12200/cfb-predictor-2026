"""Selectivity report (Phase 4, SPEC §8 item 5) — freeze-exempt.

Was declining to bet the right call? Grades the NO_BET games as **hypothetical** ("what would have
happened") and compares them to the placed bets. Three buckets over the JOIN (predictions ⋈ graded):

- **placed** — real bets (not ``is_hypothetical``): the strategy's actual record.
- **no_bet_hypothetical** — NO_BET games that DID have a lean (a side), graded hypothetically: if
  these underperform the placed bets, the floors are earning their keep (L4 / 3c.5).
- **no_lean** — truly neutral NO_BET games (no side): ``ats_result``/``clv`` null (f3), their own
  bucket, counted but never win-rated.

Dormancy-as-design (3c.9): a preseason slate that is entirely NO_BET is **selectivity working, not
breakage** — the report says so plainly so August doesn't misread the quiet.
"""

from __future__ import annotations

from typing import Any

from analytics.calibration_evidence import wilson_interval


def _rate(records: list[dict]) -> dict[str, Any]:
    graded = [r for r in records if r.get("ats_result") in ("win", "loss", "push")]
    wins = sum(1 for r in graded if r["ats_result"] == "win")
    losses = sum(1 for r in graded if r["ats_result"] == "loss")
    n = wins + losses
    lo, hi = wilson_interval(wins, n)
    return {"n_games": len(records), "n_graded": n, "wins": wins, "losses": losses,
            "ats_win_pct": round(wins / n, 4) if n else None,
            "wilson_95": [round(lo, 4), round(hi, 4)] if n else None}


def selectivity_report(joined: list[dict]) -> dict[str, Any]:
    placed = [r for r in joined if not r.get("is_hypothetical")]
    no_bet = [r for r in joined if r.get("is_hypothetical")]
    no_bet_lean = [r for r in no_bet if r.get("ats_result") in ("win", "loss", "push")]
    no_lean = [r for r in no_bet if r.get("ats_result") is None]

    placed_rate = _rate(placed)
    lean_rate = _rate(no_bet_lean)
    # The skip is validated when the placed bets we DID make beat the NO_BET leans we skipped.
    if not no_bet_lean or not placed or placed_rate["ats_win_pct"] is None or lean_rate["ats_win_pct"] is None:
        skip_validated = None
    else:
        skip_validated = placed_rate["ats_win_pct"] >= lean_rate["ats_win_pct"]

    all_no_bet = len(placed) == 0 and len(no_bet) > 0
    return {
        "placed": placed_rate,
        "no_bet_hypothetical": lean_rate,
        "no_lean": {"n_games": len(no_lean),
                    "note": "neutral no-lean games — no side, no ATS/CLV (f3)"},
        "skip_validated": skip_validated,
        "all_no_bet_slate": all_no_bet,
        "note": ("Entire slate NO_BET — selectivity working as designed (dormancy-as-design, 3c.9), "
                 "not breakage." if all_no_bet else "Mixed slate."),
    }
