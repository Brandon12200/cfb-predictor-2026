"""Classic betting KPIs (Phase 4, SPEC §8 item 3) — freeze-exempt.

ATS%, ROI @ -110, Sharpe, max drawdown, longest losing streak, and CLV aggregates — all with Wilson
95% intervals — over a set of **graded records** (the ``ats_result``/``clv`` fields from
``analytics.grading``). These operate on the **placeable strategy** only (real bets: not
``is_hypothetical``, a side taken); NO_BET selectivity lives in ``analytics.selectivity``.

The D17 "where the 57% came from" diagnostic (always-home vs the model's own number) is deliberately
NOT here — it survives, honestly labeled, in ``scripts/grading.py`` +
``scripts/calculate_accuracy.py`` (the relabeled D17 artifact). This module is the placeable-strategy
math those scripts headline; ``ats_outcome``/``wilson_interval`` remain the single sources of truth.
"""

from __future__ import annotations

import statistics
from typing import Any

from analytics.calibration_evidence import wilson_interval

# Flat $100 bet at -110: a win nets +$90.91, a loss -$100, a push is no-action (matches
# scripts/calculate_roi.py / calculate_sharpe.py — the single -110 convention).
BET = 100.00
WIN_PROFIT = 90.91
WIN_RETURN = 0.909
LOSS_RETURN = -1.0


def placed_outcomes(graded: list[dict]) -> list[str]:
    """ATS outcomes for the placeable strategy: real bets (not ``is_hypothetical``) that were
    gradable (``ats_result`` win/loss/push)."""
    return [r["ats_result"] for r in graded
            if not r.get("is_hypothetical") and r.get("ats_result") in ("win", "loss", "push")]


def ats_summary(outcomes: list[str]) -> dict[str, Any]:
    wins, losses, pushes = outcomes.count("win"), outcomes.count("loss"), outcomes.count("push")
    n = wins + losses
    lo, hi = wilson_interval(wins, n)
    return {"n_graded": n, "wins": wins, "losses": losses, "pushes": pushes,
            "ats_win_pct": round(wins / n, 4) if n else None,
            "wilson_95": [round(lo, 4), round(hi, 4)] if n else None}


def roi_at_110(outcomes: list[str]) -> dict[str, Any]:
    wins, losses = outcomes.count("win"), outcomes.count("loss")
    n = wins + losses
    profit = wins * WIN_PROFIT - losses * BET
    return {"n": n, "profit": round(profit, 2), "roi": round(profit / (n * BET), 4) if n else None}


def sharpe(outcomes: list[str]) -> dict[str, Any]:
    """Sharpe of per-bet returns (+0.909 win / -1.0 loss; pushes excluded). None if < 2 bets."""
    returns = [WIN_RETURN if o == "win" else LOSS_RETURN for o in outcomes if o in ("win", "loss")]
    if len(returns) < 2:
        return {"n": len(returns), "sharpe": None, "mean_return": round(statistics.mean(returns), 4) if returns else None}
    sd = statistics.stdev(returns)
    mean = statistics.mean(returns)
    return {"n": len(returns), "mean_return": round(mean, 4),
            "sharpe": round(mean / sd, 4) if sd else None}


def max_drawdown(outcomes: list[str]) -> float:
    """Largest peak-to-trough drop of the cumulative unit-return equity curve (pushes = flat)."""
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for o in outcomes:
        equity += WIN_RETURN if o == "win" else (LOSS_RETURN if o == "loss" else 0.0)
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return round(worst, 4)


def longest_losing_streak(outcomes: list[str]) -> int:
    """Longest run of consecutive losses (pushes don't break or extend a streak)."""
    streak = worst = 0
    for o in outcomes:
        if o == "loss":
            streak += 1
            worst = max(worst, streak)
        elif o == "win":
            streak = 0
    return worst


def clv_summary(graded: list[dict]) -> dict[str, Any]:
    """CLV aggregates over records with a computed CLV (a side taken + a closing line): average CLV
    points + the share that beat the close (CLV > 0). Records with ``clv is None`` (no side /
    honest-missing close) are excluded from the denominator and reported as ``n_no_clv``."""
    vals = [r["clv"] for r in graded if not r.get("is_hypothetical") and isinstance(r.get("clv"), (int, float))]
    n_no = sum(1 for r in graded if not r.get("is_hypothetical") and r.get("clv") is None)
    if not vals:
        return {"n": 0, "n_no_clv": n_no, "avg_clv": None, "clv_positive_pct": None}
    positive = sum(1 for v in vals if v > 0)
    return {"n": len(vals), "n_no_clv": n_no,
            "avg_clv": round(statistics.mean(vals), 3),
            "clv_positive_pct": round(positive / len(vals), 4)}


def kpi_pack(graded: list[dict]) -> dict[str, Any]:
    """The full placeable-strategy KPI pack for a set of graded records."""
    o = placed_outcomes(graded)
    return {
        "ats": ats_summary(o),
        "roi_at_110": roi_at_110(o),
        "sharpe": sharpe(o),
        "max_drawdown": max_drawdown(o),
        "longest_losing_streak": longest_losing_streak(o),
        "clv": clv_summary(graded),
    }
