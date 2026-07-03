#!/usr/bin/env python3
"""Reproducibly rerun a prediction against a stored snapshot (SPEC §5.3, SCHEMA §3).

The engine reads only the week's snapshot bundle and runs in frozen-clock mode — the
prediction's wall-clock fields come from the snapshot's build time, not `datetime.now()`
— so repeated runs on the same snapshot are byte-for-byte identical. Requires the
snapshot to exist (`python scripts/build_snapshot.py --week N`).

Usage: python scripts/rerun_prediction.py --home GEORGIA --away CLEMSON --week N
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.prediction_engine import prediction_engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun a prediction from a snapshot.")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    result = prediction_engine.generate_prediction(args.home, args.away, week=args.week)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
