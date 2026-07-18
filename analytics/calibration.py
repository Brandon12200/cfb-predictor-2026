"""Confidence calibration (Phase 4, SPEC §8 item 2) — freeze-exempt.

Brier score + a calibration table by A/B/C tier: did tier-A picks win at the rate their confidence
implies? Over the JOIN (predictions ⋈ graded), on placed bets with a win/loss outcome (pushes/no-side
excluded). The tier boundaries themselves are the ratified 3c.6 `reasoned` first cuts — Phase-4
measurement is exactly what tells 2027 whether they *separate* anything (owner: "hold them loosely").
"""

from __future__ import annotations

from typing import Any

from analytics.calibration_evidence import wilson_interval
from analytics.join import win_probability


def _placed_bets(joined: list[dict]) -> list[dict]:
    return [r for r in joined
            if not r.get("is_hypothetical") and r.get("ats_result") in ("win", "loss")]


def brier_score(joined: list[dict]) -> dict[str, Any]:
    """Mean squared error of confidence-as-win-probability vs the ATS win/loss outcome (0/1). Lower
    is better; 0.25 is the no-skill baseline for a 50/50 coin at p=0.5."""
    pairs: list[tuple[float, float]] = []
    for r in _placed_bets(joined):
        p = win_probability(r)
        if p is None:
            continue
        pairs.append((p, 1.0 if r["ats_result"] == "win" else 0.0))
    if not pairs:
        return {"n": 0, "brier": None}
    return {"n": len(pairs), "brier": round(sum((p - o) ** 2 for p, o in pairs) / len(pairs), 4)}


def calibration_table(joined: list[dict]) -> list[dict]:
    """Per-tier (A/B/C) ATS win% + mean confidence + Wilson 95% — the calibration curve as a table."""
    bets = _placed_bets(joined)
    rows: list[dict] = []
    for tier in ("A", "B", "C"):
        cell = [r for r in bets if r.get("confidence_tier") == tier]
        wins = sum(1 for r in cell if r["ats_result"] == "win")
        n = len(cell)
        probs = [wp for r in cell if (wp := win_probability(r)) is not None]
        lo, hi = wilson_interval(wins, n)
        rows.append({
            "tier": tier, "n": n, "wins": wins, "losses": n - wins,
            "ats_win_pct": round(wins / n, 4) if n else None,
            "mean_confidence": round(sum(probs) / len(probs), 4) if probs else None,
            "wilson_95": [round(lo, 4), round(hi, 4)] if n else None,
        })
    return rows
