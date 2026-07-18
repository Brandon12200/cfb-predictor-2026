#!/usr/bin/env python3
"""Generate analytics reports (Phase 4, SPEC §8 item 6) — freeze-exempt.

Renders plain-markdown reports from committed JSON (predictions ⋈ graded); no API, no external
services. Reports are **regenerable renderings** (D23), not append-only history: a pure function over
the claims/outcomes/derived artifacts, reproduced by re-running this generator (deterministically for
frozen inputs like the 2025 retro; freshly for in-season reports as data accrues). A rendering's audit
trail is git history — so `reports/` is NOT guarded by the immutability hook; overwriting is expected.
The pipeline (Phase 5) regenerates + commits them each run.

Usage:
  python scripts/build_reports.py --week N [--year 2026]   -> reports/2026_week_NN.md
  python scripts/build_reports.py --season   [--year 2026] -> reports/2026_season.md
  python scripts/build_reports.py --retro                  -> reports/2025_retro.md

The 2025 retro (SPEC §8 acceptance) converts the read-only 2025 archive v1→v2 in memory and grades it
with no closing lines (2025 has none — CLV honest-missing throughout, never faked). It validates the
whole analytics stack and doubles as README material.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.grading import build_graded  # noqa: E402
from analytics.reports import render_season, render_week  # noqa: E402
from utils.prediction_schema import convert_v1_to_v2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = ROOT / "data" / "predictions"
RESULTS_DIR = ROOT / "data" / "results"
GRADED_DIR = ROOT / "data" / "graded"
REPORTS_DIR = ROOT / "reports"
ARCHIVE = ROOT / "data" / "archive" / "2025"


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _report_week(week: int, year: int) -> None:
    predictions_env = _load(PREDICTIONS_DIR / f"{year}_week_{week:02d}.json")
    if predictions_env is None:
        print(f"No predictions for {year} week {week:02d}.")
        raise SystemExit(1)
    graded_env = _load(GRADED_DIR / f"{year}_week_{week:02d}.json")
    out = _write(REPORTS_DIR / f"{year}_week_{week:02d}.md", render_week(predictions_env, graded_env))
    print(f"Wrote {out.relative_to(ROOT)}")


def _season_weeks(year: int) -> list[tuple[dict, dict | None]]:
    weeks: list[tuple[dict, dict | None]] = []
    for pf in sorted(glob.glob(str(PREDICTIONS_DIR / f"{year}_week_*.json"))):
        wk = int(Path(pf).stem.split("_week_")[1])
        weeks.append((json.loads(Path(pf).read_text()),
                      _load(GRADED_DIR / f"{year}_week_{wk:02d}.json")))
    return weeks


def _report_season(year: int) -> None:
    weeks = _season_weeks(year)
    if not weeks:
        print(f"No predictions for {year}.")
        raise SystemExit(1)
    text = render_season(weeks, title=f"{year} Season Report — to date")
    out = _write(REPORTS_DIR / f"{year}_season.md", text)
    print(f"Wrote {out.relative_to(ROOT)}  ({len(weeks)} weeks)")


def _report_retro() -> None:
    """2025 retro: convert the read-only archive v1→v2 in memory, grade (no closing lines), render."""
    weeks: list[tuple[dict, dict | None]] = []
    for pf in sorted(glob.glob(str(ARCHIVE / "predictions" / "*.json"))):
        stem = Path(pf).stem  # 2025_week_NN
        wk = int(stem.split("_week_")[1])
        v1 = json.loads(Path(pf).read_text())
        pred_env = {"meta": {"week": wk, "year": 2025, "model_version": "2025-archive (v1→v2)",
                             "schema_version": 2},
                    "predictions": [convert_v1_to_v2(p) for p in v1.get("predictions", [])]}
        res_f = ARCHIVE / "results" / f"2025_week_{wk:02d}_results.json"
        results = (_load(res_f) or {}).get("results", [])
        graded = build_graded(pred_env, results, None, graded_at="2025-archive")
        weeks.append((pred_env, graded))
    if not weeks:
        print("No 2025 archive predictions found.")
        raise SystemExit(1)
    text = render_season(
        weeks, title="2025 Retro — Honest Regrade (D17 baseline)",
        subtitle=("Read-only over the 2025 archive (v1→v2 in memory). 2025 has NO closing lines → CLV "
                  "honest-missing throughout (never faked). Baseline: the placeable contrarian strategy "
                  "graded ~46.6% ATS / negative ROI (D17) — the honest slightly-losing season this "
                  "rebuild starts from. Per-sub-signal attribution is unavailable (v1 flat breakdown)."))
    out = _write(REPORTS_DIR / "2025_retro.md", text)
    print(f"Wrote {out.relative_to(ROOT)}  ({len(weeks)} weeks)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase-4 analytics reports.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--week", type=int)
    g.add_argument("--season", action="store_true")
    g.add_argument("--retro", action="store_true")
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    if args.retro:
        _report_retro()
    elif args.season:
        _report_season(args.year)
    else:
        _report_week(args.week, args.year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
