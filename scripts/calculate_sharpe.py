#!/usr/bin/env python3
"""Sharpe ratio of the contrarian model (see docs/DECISIONS.md D17).

Headlines the **placeable strategy** — per-bet returns on the side the model favored
(`edge_direction`) vs the Vegas line: +0.909 on a win, -1.0 on a loss (pushes excluded) —
and reports the **home-vs-model-spread bias diagnostic** separately, honestly labeled,
because it produced the retired 0.093 figure. Reads `data/predictions/` + `data/results/`.

Sharpe = mean(returns) / stdev(returns).
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.grading import (  # noqa: E402
    contrarian_ats,
    home_covered_model_spread_diagnostic,
    load_joined,
)

WIN_RETURN = 0.909
LOSS_RETURN = -1.0


def _sharpe(returns: list[float]) -> tuple[float, float, float | None]:
    if len(returns) < 2:
        return 0.0, 0.0, None
    mean = statistics.mean(returns)
    std = statistics.stdev(returns)
    return mean, std, (mean / std if std > 0 else None)


def _fmt(v) -> str:
    return "N/A" if v is None else f"{v:+.4f}"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pairs = load_joined(str(root / "data" / "predictions"), str(root / "data" / "results"))
    if not pairs:
        print("No joined predictions/results found under data/predictions + data/results.")
        return 1

    strat = [WIN_RETURN if o == "win" else LOSS_RETURN
             for o in contrarian_ats(pairs) if o in ("win", "loss")]
    mean, std, sharpe = _sharpe(strat)

    diag_flags = [d for d in (home_covered_model_spread_diagnostic(r) for _, r in pairs) if d is not None]
    diag = [WIN_RETURN if d else LOSS_RETURN for d in diag_flags]
    _, _, dsharpe = _sharpe(diag)

    print("=" * 60)
    print("CFB Contrarian Predictor — Sharpe Ratio Report")
    print("=" * 60)
    print()
    print("CONTRARIAN SHARPE  (the placeable strategy: model's side vs the Vegas line)")
    print("-" * 60)
    print(f"Bets:         {len(strat)}   (pushes excluded)")
    print(f"Mean Return:  {_fmt(mean)}")
    print(f"Std Dev:      {std:.4f}")
    print(f"Sharpe:       {_fmt(sharpe)}")
    print()
    print("HOME-vs-MODEL-SPREAD DIAGNOSTIC  (bias signal, NOT a bet — see D17)")
    print("-" * 60)
    print(f"  Always betting home vs the model's own number: Sharpe {_fmt(dsharpe)}   "
          "<- the retired 0.093 headline")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
