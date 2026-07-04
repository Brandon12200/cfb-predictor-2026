"""Physical factor tests (Phase 3b, SPEC §7.2 acceptance) — each schedule-intel sub-signal is a
separate PRIMARY factor with threshold-boundary behaviour, missing intel → 0 (never fabricated),
and each appears separately in `factor_breakdown`."""

from __future__ import annotations

from factors.scheduling_fatigue import (
    AltitudeCalculator,
    ByeAdvantageCalculator,
    ConsecutiveRoadCalculator,
    SandwichCalculator,
    ShortWeekCalculator,
    TravelBurdenCalculator,
)

_ALL = (ByeAdvantageCalculator, ShortWeekCalculator, TravelBurdenCalculator,
        AltitudeCalculator, ConsecutiveRoadCalculator, SandwichCalculator)


def _ctx(home_intel, away_intel, neutral=False):
    return {"home_intel": home_intel, "away_intel": away_intel, "neutral_site": neutral}


def test_all_physical_factors_are_primary_physical():
    for F in _ALL:
        f = F()
        assert f.category == "physical"
        assert f.factor_type.value == "primary"


def test_bye_fires_with_direction_and_activation():
    f = ByeAdvantageCalculator()
    ctx = _ctx({"bye": True}, {"bye": False})
    assert f.calculate("H", "A", ctx) > 0  # home off a bye favors home
    r = f.safe_calculate("H", "A", ctx)
    assert r["activated"] and r["value"] > 0 and r["success"]
    # absent → 0, not activated
    r0 = f.safe_calculate("H", "A", _ctx({"bye": False}, {"bye": False}))
    assert not r0["activated"] and r0["value"] == 0.0


def test_threshold_boundary_each_factor():
    # activation just-below zeros out; just-above passes through (SPEC §7 acceptance).
    for F in _ALL:
        f = F()
        t = f.activation_threshold
        assert f.apply_threshold(t - 0.01) == 0.0
        assert f.apply_threshold(t + 0.01) == t + 0.01


def test_signals_fire_with_correct_sign():
    assert TravelBurdenCalculator().calculate("H", "A", _ctx({"time_zones_crossed": 0},
                                                             {"time_zones_crossed": 3})) > 0
    assert AltitudeCalculator().calculate("H", "A", _ctx({"altitude": 7000.0}, {})) > 0
    # neutral site has no home acclimation edge
    assert AltitudeCalculator().calculate("H", "A", _ctx({"altitude": 7000.0}, {}, neutral=True)) == 0.0
    assert ConsecutiveRoadCalculator().calculate("H", "A", _ctx({"consecutive_road_games": 0},
                                                                {"consecutive_road_games": 3})) > 0
    # home in a sandwich spot may underperform → favors away (negative)
    assert SandwichCalculator().calculate("H", "A", _ctx({"sandwich_spot": True},
                                                         {"sandwich_spot": False})) < 0


def test_missing_intel_is_zero_not_fabricated():
    for F in _ALL:
        f = F()
        assert f.calculate("H", "A", {}) == 0.0            # no context intel at all
        assert f.calculate("H", "A", _ctx({}, {})) == 0.0  # empty intel dicts


def test_each_physical_subsignal_separate_in_factor_breakdown():
    from factors.factor_registry import factor_registry
    # A context firing several physical signals; the registry breakdown lists each factor by name.
    ctx = _ctx({"bye": True, "altitude": 7000.0, "time_zones_crossed": 0},
               {"short_week": True, "time_zones_crossed": 3, "consecutive_road_games": 3})
    ctx["vegas_spread"] = -3.0
    results = factor_registry.calculate_all_factors("HOME", "AWAY", ctx)
    for name in ("ByeAdvantage", "ShortWeek", "TravelBurden", "Altitude", "ConsecutiveRoad", "Sandwich"):
        assert name in results["factors"], f"{name} missing from factor_breakdown"
    assert results["factors"]["ByeAdvantage"]["activated"] is True
