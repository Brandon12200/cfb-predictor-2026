#!/usr/bin/env python3
"""Two-check CLV sign validator — runs in the pipeline between grading and the grading commit.

CLV is defined from the bet side's perspective (`utils/prediction_schema.py::clv`): positive means
the model's number beat the close. The formula inverts between sides —

    home lean:  clv = vegas_spread - closing_spread
    away lean:  clv = closing_spread - vegas_spread

— and an inverted sign would not look like an error. It would look like a plausible, consistently
wrong result. So every graded lean is checked two independent ways:

1. **Formula.** Recompute CLV from the side's definition and require it to equal the value grading
   stored. Catches a stored value that disagrees with the documented convention.

2. **Movement.** Derive the expected SIGN from which way the line moved, without using the formula:
   the close below the claim number means the market moved toward HOME, above it toward AWAY. If it
   moved toward the side the model leaned, the model held the better number early and CLV must be
   positive; away from it, negative; unmoved, zero. Catches a convention inverted *consistently* —
   which the formula check alone would pass, because a wrong formula agrees with itself.

**Why it runs before the commit.** Owner ruling 2026-09-13: this check was a human step after the
Sunday report, and the scheduled job commits the grades about thirty seconds after grading, so a
disagreement would already have been on `main` before anyone could look. `data/graded/` is
append-only, so a wrong value committed there cannot be quietly corrected. Failing here keeps it out.

Exit 0: every graded lean agrees (or there is nothing graded to check).
Exit 1: at least one lean disagrees on either check — the grading commit must not happen.

Usage: python scripts/check_clv.py --week N [--year 2026]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXIT_OK = 0
EXIT_DISAGREE = 1
_EPS = 1e-9


def _sign(x: float) -> int:
    return 0 if abs(x) < _EPS else (1 if x > 0 else -1)


def expected_clv(side: str, vegas: float, close: float) -> float:
    return (vegas - close) if side == "home" else (close - vegas)


def moved_toward(vegas: float, close: float) -> str:
    """Which side the market moved toward between the claim and the close."""
    if abs(close - vegas) < _EPS:
        return "none"
    return "home" if close < vegas else "away"


def check_lean(side: str, vegas: float, close: float, stored: float) -> tuple[bool, bool, str]:
    """(formula_ok, movement_ok, moved) for one graded lean."""
    formula_ok = abs(round(expected_clv(side, vegas, close), 2) - stored) < _EPS
    moved = moved_toward(vegas, close)
    want = 0 if moved == "none" else (1 if moved == side else -1)
    return formula_ok, _sign(stored) == want, moved


def validate(predictions_env: dict, graded_env: dict) -> list[dict]:
    """One row per graded lean with a close and a CLV. `ok` is False on any disagreement."""
    graded = {r["game_id"]: r for r in graded_env.get("graded", [])}
    rows = []
    for p in predictions_env.get("predictions", []):
        side = p.get("edge_direction")
        if side not in ("home", "away"):
            continue                              # no side taken — CLV is undefined (D22 f3)
        r = graded.get(p.get("game_id"))
        if r is None:
            continue                              # not graded yet
        vegas, close, stored = p.get("vegas_spread"), r.get("closing_spread"), r.get("clv")
        if vegas is None or close is None or stored is None:
            continue                              # honest-missing close — nothing to validate
        formula_ok, movement_ok, moved = check_lean(side, vegas, close, stored)
        rows.append({"game_id": p["game_id"], "side": side, "vegas": vegas, "close": close,
                     "clv": stored, "moved": moved, "formula_ok": formula_ok,
                     "movement_ok": movement_ok, "ok": formula_ok and movement_ok})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--base", type=Path, default=ROOT, help="repository root (tests only)")
    args = ap.parse_args(argv)

    stem = f"{args.year}_week_{args.week:02d}.json"
    pred_path = args.base / "data" / "predictions" / stem
    graded_path = args.base / "data" / "graded" / stem
    if not graded_path.exists():
        print(f"check_clv: no graded file for {args.year} week {args.week} — nothing to validate.")
        return EXIT_OK
    if not pred_path.exists():
        print(f"::error::check_clv: graded file exists but no claim at {pred_path}")
        return EXIT_DISAGREE

    rows = validate(json.loads(pred_path.read_text()), json.loads(graded_path.read_text()))
    print(f"CLV sign check — {args.year} week {args.week}: {len(rows)} graded lean(s)")
    print(f"  {'side':5} {'game':40} {'claim':>7} {'close':>7} {'CLV':>6}  {'moved':6} formula movement")
    for r in rows:
        print(f"  {r['side']:5} {r['game_id']:40} {r['vegas']:+7.1f} {r['close']:+7.1f} "
              f"{r['clv']:+6.2f}  {r['moved']:6} {'ok' if r['formula_ok'] else 'FAIL':7} "
              f"{'ok' if r['movement_ok'] else 'FAIL'}")

    bad = [r for r in rows if not r["ok"]]
    if bad:
        for r in bad:
            print(f"::error::CLV sign disagreement on {r['game_id']} ({r['side']} lean): "
                  f"stored {r['clv']:+.2f}, claim {r['vegas']:+.1f}, close {r['close']:+.1f}, "
                  f"market moved toward {r['moved']} — "
                  f"formula {'ok' if r['formula_ok'] else 'FAILS'}, "
                  f"movement {'ok' if r['movement_ok'] else 'FAILS'}")
        print(f"check_clv: {len(bad)} lean(s) disagree — refusing to let these grades be committed.")
        return EXIT_DISAGREE
    print("check_clv: all signs agree.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
