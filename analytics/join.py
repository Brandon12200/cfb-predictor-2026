"""The predictions ⋈ graded JOIN (Phase 4, D22) — freeze-exempt.

D22: the "filled" schema-v2 record is a JOIN, produced in memory, never materialized to disk. This
module is that join — it merges each byte-immutable prediction record with its graded fields
(``closing_spread``/``clv``/``ats_result``/``is_hypothetical``/``graded_at``/scores) by ``game_id``.
Every reporting/attribution consumer reads the join, never a "filled" file.
"""

from __future__ import annotations

_GRADED_FIELDS = ("closing_spread", "close_as_of", "clv", "ats_result",
                  "is_hypothetical", "home_score", "away_score", "graded_at")


def join(predictions_env: dict, graded_env: dict | None) -> list[dict]:
    """Merge predictions with graded records by ``game_id``. Every prediction appears; ungraded games
    carry ``None`` graded fields + ``graded: False``. Graded fields override the prediction's on-disk
    ``null`` slots (which stay null on disk — the merge is in memory only)."""
    graded_by_id = {r["game_id"]: r for r in (graded_env or {}).get("graded", [])}
    out: list[dict] = []
    for pred in predictions_env.get("predictions", []):
        merged = dict(pred)
        g = graded_by_id.get(pred.get("game_id"))
        if g:
            for f in _GRADED_FIELDS:
                merged[f] = g.get(f)
            merged["graded"] = True
        else:
            merged["graded"] = False
        out.append(merged)
    return out


def win_probability(rec: dict) -> float | None:
    """The record's confidence as a 0–1 win-probability for calibration/Brier: v2 ``confidence``
    (already 0–1), else the v1-converted ``confidence_pct`` / 100, else ``None``."""
    conf = rec.get("confidence")
    if isinstance(conf, (int, float)):
        return float(conf)
    pct = rec.get("confidence_pct")
    if isinstance(pct, (int, float)):
        return pct / 100.0
    return None
