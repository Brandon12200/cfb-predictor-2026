#!/usr/bin/env python3
"""ROI of the contrarian model at -110 (see docs/DECISIONS.md D17).

Headlines the **placeable strategy** — flat $100 bets on the side the model favored
(`edge_direction`) against the Vegas line — and reports the **home-vs-model-spread bias
diagnostic** (always betting home vs the model's own number) separately, honestly labeled,
because it produced the retired +8.82% figure. Reads `data/predictions/` + `data/results/`.

Flat $100 bets at -110: a win nets +$90.91, a loss -$100; pushes are no-action.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.grading import (  # noqa: E402
    contrarian_ats,
    home_covered_model_spread_diagnostic,
    load_joined,
)

BET = 100.00
WIN_PROFIT = 90.91


def _roi(wins: int, losses: int) -> tuple[float, float]:
    n = wins + losses
    profit = wins * WIN_PROFIT - losses * BET
    return profit, (profit / (n * BET)) if n else 0.0


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pairs = load_joined(str(root / "data" / "predictions"), str(root / "data" / "results"))
    if not pairs:
        print("No joined predictions/results found under data/predictions + data/results.")
        return 1

    outcomes = contrarian_ats(pairs)
    w, losses = outcomes.count("win"), outcomes.count("loss")
    profit, roi = _roi(w, losses)

    diag = [d for d in (home_covered_model_spread_diagnostic(r) for _, r in pairs) if d is not None]
    dw = sum(1 for d in diag if d)
    _, droi = _roi(dw, len(diag) - dw)

    print("=" * 60)
    print("CFB Contrarian Predictor — ROI Report  (flat $100 @ -110)")
    print("=" * 60)
    print()
    print("CONTRARIAN ROI  (the placeable strategy: model's side vs the Vegas line)")
    print("-" * 60)
    print(f"Wins-Losses:  {w}-{losses}   (pushes = no action)")
    print(f"Wagered:      ${(w + losses) * BET:,.2f}")
    print(f"Profit:       ${profit:+,.2f}")
    print(f"ROI:          {roi:+.2%}")
    print()
    print("HOME-vs-MODEL-SPREAD DIAGNOSTIC  (bias signal, NOT a bet — see D17)")
    print("-" * 60)
    print(f"  Always betting home vs the model's own number: {dw}-{len(diag) - dw}, "
          f"ROI {droi:+.2%}   <- the retired +8.82% headline")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
