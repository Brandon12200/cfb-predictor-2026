"""Calibration-evidence harness tests (Phase 3): the ATS convention matches the canonical
grader, Wilson math is correct, bucketing works, and the pack is deterministic."""

from __future__ import annotations

import json

from analytics.calibration_evidence import (
    ats_outcome,
    build_calibration_evidence,
    wilson_interval,
)


def test_wilson_interval_known_and_edge_cases():
    lo, hi = wilson_interval(50, 100)
    assert lo < 0.5 < hi and 0.39 < lo < 0.41 and 0.59 < hi < 0.61
    assert wilson_interval(0, 0) == (0.0, 0.0)
    # tiny sample → wide interval (the honesty the harness is built to preserve)
    lo1, hi1 = wilson_interval(0, 1)
    assert lo1 == 0.0 and hi1 > 0.7


def test_ats_outcome_canonical_convention():
    # home covers S iff (home-away)+S > 0 (scripts/calculate_accuracy.py).
    res = {"home_score": 30, "away_score": 20}          # home margin +10
    assert ats_outcome({"edge_direction": "home", "vegas_spread": 3.0}, res) == "win"   # 10+3>0
    assert ats_outcome({"edge_direction": "away", "vegas_spread": 3.0}, res) == "loss"
    # home a big favorite that fails to cover → away bet wins
    assert ats_outcome({"edge_direction": "away", "vegas_spread": -14.0}, res) == "win"  # 10-14<0
    # push
    assert ats_outcome({"edge_direction": "home", "vegas_spread": -10.0}, res) == "push"  # 10-10==0
    # ungradable
    assert ats_outcome({"edge_direction": "neutral", "vegas_spread": 3.0}, res) is None


def _write_archive(root, preds, results):
    (root / "predictions").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    (root / "predictions" / "2025_week_01.json").write_text(json.dumps({"predictions": preds}))
    (root / "results" / "2025_week_01.json").write_text(json.dumps({"results": results}))


def test_build_evidence_buckets_and_join(tmp_path):
    preds = [
        {"game_id": "A_B_w1", "edge_direction": "home", "vegas_spread": 3.0,
         "confidence": 72.0, "predicted_edge": 1.5, "prediction_type": "SLIGHT_CONTRARIAN"},
        {"game_id": "C_D_w1", "edge_direction": "away", "vegas_spread": 3.0,
         "confidence": 55.0, "predicted_edge": 0.5, "prediction_type": "CONSENSUS_ALIGNMENT"},
        {"game_id": "NO_RESULT_w1", "edge_direction": "home", "vegas_spread": 1.0,
         "confidence": 60.0, "predicted_edge": 1.0, "prediction_type": "SLIGHT_CONTRARIAN"},
    ]
    results = [
        {"game_id": "A_B_w1", "home_score": 30, "away_score": 20},  # home covers → home bet WIN
        {"game_id": "C_D_w1", "home_score": 30, "away_score": 20},  # home covers → away bet LOSS
    ]
    _write_archive(tmp_path, preds, results)
    ev = build_calibration_evidence(str(tmp_path))
    assert ev["meta"]["games_joined"] == 2 and ev["meta"]["graded"] == 2  # 3rd has no result
    assert ev["overall"]["wins"] == 1 and ev["overall"]["losses"] == 1
    # confidence bucketing: 72 → "70-80", 55 → "50-60"
    b70 = next(b for b in ev["by_confidence"] if b["bucket"] == "70-80")
    assert b70["n_graded"] == 1 and b70["wins"] == 1


def test_build_evidence_is_deterministic(tmp_path):
    preds = [{"game_id": "A_B_w1", "edge_direction": "home", "vegas_spread": 3.0,
              "confidence": 65.0, "predicted_edge": 1.0, "prediction_type": "SLIGHT_CONTRARIAN"}]
    results = [{"game_id": "A_B_w1", "home_score": 30, "away_score": 20}]
    _write_archive(tmp_path, preds, results)
    a = json.dumps(build_calibration_evidence(str(tmp_path)), sort_keys=True)
    b = json.dumps(build_calibration_evidence(str(tmp_path)), sort_keys=True)
    assert a == b


def test_real_2025_archive_overall_is_plausible():
    # Guards the convention against silent inversion: a real contrarian season lands near 50%,
    # not 15% (the flipped convention) or 100%.
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "data" / "archive" / "2025"
    ev = build_calibration_evidence(str(root))
    assert ev["meta"]["graded"] > 250
    assert 0.35 < ev["overall"]["ats_win_pct"] < 0.55
