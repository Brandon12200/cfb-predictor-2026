#!/usr/bin/env python3
"""Grade the contrarian model's against-the-spread accuracy (see docs/DECISIONS.md D17).

Two numbers, clearly separated:

- **Contrarian ATS (the headline)** — the placeable strategy: bet the side the model favored
  (`edge_direction`) against the **Vegas** line. This is what "against the spread" means.
- **Home-vs-model-spread diagnostic** — did the home team cover the model's OWN contrarian
  number (always betting home, graded against the model's spread). A home-rating **bias**
  signal, NOT a placeable bet. It is the source of the retired 57.0% headline (D17); kept and
  honestly labeled because it explains that number.

Reads `data/predictions/` + `data/results/`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.grading import (  # noqa: E402
    contrarian_ats,
    home_covered_model_spread_diagnostic,
    load_joined,
)


def _pct(wins: int, n: int) -> str:
    return f"{wins / n:.1%}" if n else "n/a"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pairs = load_joined(str(root / "data" / "predictions"), str(root / "data" / "results"))
    if not pairs:
        print("No joined predictions/results found under data/predictions + data/results.")
        return 1

    outcomes = contrarian_ats(pairs)
    wins = outcomes.count("win")
    losses = outcomes.count("loss")
    pushes = outcomes.count("push")
    graded = wins + losses

    diag = [home_covered_model_spread_diagnostic(r) for _, r in pairs]
    dv = [d for d in diag if d is not None]
    dcov = sum(1 for d in dv if d)

    print("=" * 60)
    print("CFB Contrarian Predictor — Accuracy Report")
    print("=" * 60)
    print()
    print("CONTRARIAN ATS  (the placeable strategy: model's side vs the Vegas line)")
    print("-" * 60)
    print(f"Graded bets:  {graded}   (of {len(pairs)} joined; {pushes} pushes excluded)")
    print(f"Wins-Losses:  {wins}-{losses}")
    print(f"ATS:          {_pct(wins, graded)}   (break-even ~52.4% at -110)")
    print()
    print("HOME-vs-MODEL-SPREAD DIAGNOSTIC  (bias signal, NOT a bet — see D17)")
    print("-" * 60)
    print("  Did the home team cover the model's OWN contrarian number (always betting home)?")
    print(f"  Home covered: {dcov}/{len(dv)} = {_pct(dcov, len(dv))}   <- the retired 57% headline")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
