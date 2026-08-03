"""Phase 3d — prediction schema v2, 2025 converter, CLV convention, model_version, and the
StyleMismatch pre-freeze resolution (3c.10). Offline, deterministic."""

import json
from pathlib import Path

from factors.style_mismatch import StyleMismatchCalculator
from utils import version
from utils.prediction_schema import (
    PREDICTION_SCHEMA_VERSION,
    V2_RECORD_KEYS,
    build_v2_record,
    clv,
    convert_v1_to_v2,
    game_id,
)

ROOT = Path(__file__).resolve().parent.parent


# ── Schema-v2 record builder ──────────────────────────────────────────────────────────────────

def _engine_result():
    return {
        "home_team": "GEORGIA", "away_team": "ALABAMA", "vegas_spread": -3.0,
        "contrarian_spread": -2.85, "edge_size": 0.15, "edge_direction": "away",
        "prediction_type": "NO_BET", "no_bet": True, "no_bet_reason": "edge 0.15 below threshold 1.00",
        "confidence_tier": "B", "confidence_score": 0.61, "power_rating_spread": -4.2,
        "data_quality": 0.8,
        "factor_breakdown": {
            "ByeAdvantage": {"value": 0.0, "weighted_value": 0.0, "activated": False, "category": "physical"},
            "DesperationIndex": {"value": 0.0, "weighted_value": 0.0, "activated": False,
                                 "category": "situational_context"},
        },
    }


def test_v2_record_has_exact_key_inventory():
    rec = build_v2_record(_engine_result(), week=5, line_as_of="2026-10-01T12:00:00Z")
    assert set(rec) == set(V2_RECORD_KEYS)


def test_v2_record_grading_fields_null_at_write():
    rec = build_v2_record(_engine_result(), week=5, line_as_of=None)
    assert rec["closing_spread"] is None and rec["clv"] is None and rec["graded_at"] is None


def test_v2_record_per_sub_signal_breakdown_and_fields():
    rec = build_v2_record(_engine_result(), week=5, line_as_of="2026-10-01T12:00:00Z")
    assert rec["no_bet"] is True and rec["confidence_tier"] == "B"
    assert rec["confidence"] == 0.61  # 0–1 scale
    assert rec["power_rating_spread"] == -4.2
    # per-sub-signal (each factor present), not the v1 flat {category: float}
    assert "ByeAdvantage" in rec["factor_breakdown"] and "DesperationIndex" in rec["factor_breakdown"]
    assert rec["factor_breakdown"]["ByeAdvantage"]["category"] == "physical"
    assert rec["game_id"] == game_id("GEORGIA", "ALABAMA", 5)


# ── CLV convention (positive = our number beat the close) ─────────────────────────────────────

def test_clv_home_bet_positive_when_vegas_beats_close():
    # home bet at -3.0; closes at -4.0 -> we got the more home-favourable number -> +1.0
    assert clv(-3.0, -4.0, "home") == 1.0
    assert clv(-4.0, -3.0, "home") == -1.0


def test_clv_away_bet_positive_when_close_beats_vegas():
    # away bet at -3.0 (home line); closes at -2.0 -> better for away -> +1.0
    assert clv(-3.0, -2.0, "away") == 1.0
    assert clv(-2.0, -3.0, "away") == -1.0


def test_clv_null_when_not_graded():
    assert clv(-3.0, None, "home") is None
    assert clv(None, -3.0, "away") is None


# ── 2025 v1→v2 converter (pure, read-only) ────────────────────────────────────────────────────

def _v1_entry():
    return json.loads(
        (ROOT / "data" / "archive" / "2025" / "predictions" / "2025_week_01.json").read_text()
    )["predictions"][0]


def test_converter_round_trips_real_archive_entry():
    v1 = _v1_entry()
    v2 = convert_v1_to_v2(v1)
    assert v2["schema_version"] == PREDICTION_SCHEMA_VERSION
    assert v2["game_id"] == v1["game_id"]          # join key kept (v1 format)
    assert v2["no_bet"] is False                   # v1 predates NO_BET
    assert v2["confidence_tier"] in ("A", "B", "C")
    assert v2["confidence_pct"] == v1["confidence"] and v2["confidence"] is None
    assert v2["factor_breakdown"].get("_v1_flat") is True
    assert v2["power_rating_spread"] is None and v2["clv"] is None


def test_converter_is_read_only_on_input():
    v1 = _v1_entry()
    before = json.dumps(v1, sort_keys=True)
    convert_v1_to_v2(v1)
    assert json.dumps(v1, sort_keys=True) == before  # input dict not mutated


# ── model_version helper ──────────────────────────────────────────────────────────────────────

def test_model_version_returns_nonempty():
    assert isinstance(version.model_version(), str) and version.model_version()


def test_model_version_fallback_when_git_unavailable(monkeypatch):
    def _boom(*a, **k):
        raise FileNotFoundError("git not found")
    monkeypatch.setattr(version.subprocess, "run", _boom)
    assert version.model_version() == "unknown"


# ── StyleMismatch pre-freeze resolution (3c.10) ───────────────────────────────────────────────

def test_style_mismatch_range_tightened_below_hfa():
    lo, hi = StyleMismatchCalculator().get_output_range()
    assert (lo, hi) == (-1.5, 1.5)
    assert max(abs(lo), abs(hi)) < 2.5  # < 1.0× the ~2.5-pt HFA


def test_style_mismatch_pace_component_dormant():
    # Pace neutralized (per-game data not in the payload) — returns 0.0 without reading plays.
    assert StyleMismatchCalculator()._calculate_pace_mismatch({}, {}) == 0.0


def test_style_mismatch_dormant_without_advanced_stats():
    # Empty advanced_stats (the preseason state) -> honest-missing 0.0.
    assert StyleMismatchCalculator().calculate("GEORGIA", "ALABAMA", {"advanced_stats": {}}) == 0.0


def _adv(sr_off, plays):
    """Minimal advanced-stats block with a real style signal + a controllable raw `plays` total."""
    return {
        "offense": {"successRate": sr_off, "explosiveness": 1.3, "ppa": 0.25, "plays": plays,
                    "standardDowns": {"successRate": 0.50}, "passingDowns": {"successRate": 0.30},
                    "rushingPlays": {"successRate": 0.45}, "passingPlays": {"successRate": 0.52},
                    "powerSuccess": 0.72},
        "defense": {"successRate": 0.42, "explosiveness": 1.0, "ppa": 0.10,
                    "havoc": {"total": 0.18}, "standardDowns": {"successRate": 0.45},
                    "passingDowns": {"successRate": 0.25}, "rushingPlays": {"successRate": 0.40},
                    "passingPlays": {"successRate": 0.50}, "stuffRate": 0.15},
    }


def test_style_mismatch_is_pace_invariant():
    """Regression pin on the *meaning* (3d.2): the factor must not respond to raw play-count / pace
    differences — a huge `plays` gap that the old phantom would have fired on leaves the output
    unchanged, while the genuine style signal (success-rate gap) still produces a non-zero value.

    **Repointed at `_calculate_2027_reference` (B-1, owner 2026-08-03).** `calculate()` is now
    dormant for all of 2026 and returns 0.0 unconditionally, which would make this assertion pass
    vacuously and silently retire the 3d.2 protection. The pace-phantom fix is a property of the
    *implementation*, which is preserved verbatim — so the pin follows it there and keeps its teeth
    for the 2027 reactivation. The dormancy itself is pinned separately, below.
    """
    f = StyleMismatchCalculator()
    balanced = {"advanced_stats": {"HOME": _adv(0.58, 200), "AWAY": _adv(0.40, 200)}}
    lopsided_pace = {"advanced_stats": {"HOME": _adv(0.58, 1000), "AWAY": _adv(0.40, 150)}}
    out = f._calculate_2027_reference("HOME", "AWAY", balanced)
    assert out == f._calculate_2027_reference("HOME", "AWAY", lopsided_pace)  # pace-invariant
    assert out != 0.0                                          # real (non-pace) style signal present


def test_style_mismatch_dormant_for_2026_even_with_populated_advanced_stats():
    """B-1 dormancy pin, asserting the MEANING, not a stored value (the LARAMIE doctrine).

    The load-bearing case: `advanced_stats` POPULATED with a strong, genuine style mismatch — the
    exact input that *would* produce a large value if the unratified internals ran — must still
    yield 0.0 in 2026. A test that only checked the empty-stats case would pass for the entire life
    of an accidental reactivation, which is precisely how the LARAMIE units bug survived.

    This fails the moment someone removes the dormancy gate, which is the point: blocker (1) cannot
    be cleared silently. Blocker (2) — the ~20 unratified branch constants — is not testable and is
    stated in `calculate()`'s docstring and the log instead.
    """
    f = StyleMismatchCalculator()
    strong_mismatch = {"advanced_stats": {"HOME": _adv(0.58, 200), "AWAY": _adv(0.40, 200)}}

    # The reference implementation demonstrates the signal is real and non-trivial...
    assert f._calculate_2027_reference("HOME", "AWAY", strong_mismatch) != 0.0
    # ...and the live factor must nonetheless stay silent for all of 2026.
    assert f.calculate("HOME", "AWAY", strong_mismatch) == 0.0

    # Honest-missing still holds, and is a DIFFERENT case from dormancy (binding principle #4).
    assert f.calculate("HOME", "AWAY", {"advanced_stats": {}}) == 0.0
    assert f.calculate("HOME", "AWAY", None) == 0.0

    # The ratified ±1.5 range (3d.3) is untouched by the dormancy.
    assert f.get_output_range() == (-1.5, 1.5)
