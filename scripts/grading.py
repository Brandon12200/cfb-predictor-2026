"""Shared 2025 grading helpers (see docs/DECISIONS.md D17).

Two DISTINCT measurements, kept separate so neither is mistaken for the other:

- **contrarian ATS (the placeable strategy)** — bet the side the model favored
  (`edge_direction`) against the **Vegas** line, graded with the canonical cover rule.
  Reuses `analytics.calibration_evidence.ats_outcome` (single source of truth). This is
  what "against the spread" means and the number these reports headline.

- **home-vs-model-spread diagnostic** — did the **home** team cover the model's **own**
  contrarian number (always betting home, graded against the model's spread). A
  home-rating **bias** signal, NOT a placeable bet — it produced the retired 57.0%
  headline (D17). Kept, honestly named, because it explains where that number came from.
"""

from __future__ import annotations

import glob
import json
import os

from analytics.calibration_evidence import ats_outcome  # single source of truth for ATS


def load_joined(pred_dir: str, result_dir: str) -> list[tuple[dict, dict]]:
    """Join predictions↔results by `game_id` (the contrarian-ATS grade needs `edge_direction`
    from the prediction, which the result files don't carry)."""
    preds: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(pred_dir, "*.json"))):
        for p in json.loads(open(f).read()).get("predictions", []):
            preds[p["game_id"]] = p
    results: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(result_dir, "*.json"))):
        for r in json.loads(open(f).read()).get("results", []):
            results[r["game_id"]] = r
    return [(preds[g], results[g]) for g in sorted(preds) if g in results]


def home_covered_model_spread_diagnostic(result: dict) -> bool | None:
    """DIAGNOSTIC (not ATS, not a bet): did the home team cover the model's OWN contrarian
    spread? Convention: home covers `S` iff `(home-away)+S>0`. `None` if not gradable. This is
    a home-rating bias signal; always-home vs the model's own number produced the retired 57%."""
    cs, hs, as_ = result.get("contrarian_spread"), result.get("home_score"), result.get("away_score")
    if cs is None or hs is None or as_ is None:
        return None
    v = (hs - as_) + cs
    return None if abs(v) < 1e-9 else v > 0


def contrarian_ats(pairs: list[tuple[dict, dict]]) -> list[str]:
    """The placeable strategy's per-bet outcomes (`"win"`/`"loss"`/`"push"`)."""
    return [o for o in (ats_outcome(p, r) for p, r in pairs) if o is not None]
