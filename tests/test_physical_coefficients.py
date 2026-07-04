"""Physical-coefficient function tests (Phase 3b, D15) — the single source of truth the pricer
and the physical factors both consume. Covers each per-sub-signal point function (home
perspective, + favors home) and the model-spread subset boundary."""

from __future__ import annotations

from factors.physical_coefficients import (
    DEFAULT_PHYSICAL_COEFFICIENTS as C,
)
from factors.physical_coefficients import (
    altitude_points,
    bye_points,
    consecutive_road_points,
    physical_adjustments,
    sandwich_points,
    short_week_points,
    travel_points,
)


def test_bye_points_directional():
    assert bye_points({"bye": True}, {"bye": False}) == C.bye_value        # home off a bye → +
    assert bye_points({"bye": False}, {"bye": True}) == -C.bye_value       # away off a bye → −
    assert bye_points({"bye": True}, {"bye": True}) == 0.0                 # both → wash
    assert bye_points({}, {}) == 0.0


def test_short_week_points_directional():
    assert short_week_points({"short_week": True}, {}) == -C.short_week_penalty   # home short → favors away
    assert short_week_points({}, {"short_week": True}) == C.short_week_penalty    # away short → favors home
    assert short_week_points({"short_week": True}, {"short_week": True}) == 0.0


def test_travel_points_clamped_and_signed():
    # away crosses 3 zones, home 0 → favors home, capped at travel_cap.
    assert travel_points({"time_zones_crossed": 0}, {"time_zones_crossed": 3}) == min(3 * C.tz_per_zone, C.travel_cap)
    assert travel_points({"time_zones_crossed": 3}, {"time_zones_crossed": 0}) < 0   # home traveled → favors away
    assert travel_points({"time_zones_crossed": None}, {"time_zones_crossed": None}) == 0.0


def test_altitude_points_home_only_non_neutral():
    assert altitude_points({"altitude": 7000.0}, neutral_site=False) == C.altitude_value
    assert altitude_points({"altitude": 7000.0}, neutral_site=True) == 0.0     # neutral → no acclimation edge
    assert altitude_points({"altitude": 200.0}, neutral_site=False) == 0.0     # below threshold
    assert altitude_points({"altitude": None}, neutral_site=False) == 0.0


def test_consecutive_road_points_wear_and_cap():
    # away on its 3rd straight road game is worn (favors home); 1st road game → no wear.
    assert consecutive_road_points({"consecutive_road_games": 0}, {"consecutive_road_games": 1}) == 0.0
    assert consecutive_road_points({"consecutive_road_games": 0}, {"consecutive_road_games": 3}) > 0
    # symmetric: home on a long road stretch favors away
    assert consecutive_road_points({"consecutive_road_games": 3}, {"consecutive_road_games": 0}) < 0
    # capped
    assert consecutive_road_points({"consecutive_road_games": 0}, {"consecutive_road_games": 20}) == C.consecutive_road_cap


def test_sandwich_points_directional_and_none_safe():
    assert sandwich_points({"sandwich_spot": True}, {"sandwich_spot": False}) == -C.sandwich_value  # home distracted → favors away
    assert sandwich_points({"sandwich_spot": False}, {"sandwich_spot": True}) == C.sandwich_value
    assert sandwich_points({"sandwich_spot": None}, {"sandwich_spot": None}) == 0.0   # unknown adjacent strength → no signal


def test_model_spread_subset_excludes_consecutive_road_and_sandwich():
    # physical_adjustments = the pricer's model-spread subset (D15): fatigue/location only.
    home = {"bye": True, "consecutive_road_games": 5, "sandwich_spot": True}
    away = {"consecutive_road_games": 5, "sandwich_spot": True}
    total, parts = physical_adjustments(home, away, neutral_site=False)
    assert set(parts) <= {"bye", "short_week", "travel", "altitude"}
    assert "consecutive_road" not in parts and "sandwich" not in parts
    assert parts.get("bye") == C.bye_value and total == sum(parts.values())
