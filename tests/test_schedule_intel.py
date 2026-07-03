"""Unit tests for the schedule-intelligence dataset (SPEC §5.4.2 acceptance).

Known-fixture coverage of travel distance, rest days, time-zone crossings + direction,
altitude, consecutive road games, byes, and sandwich spots. Pure function → offline.
"""

from datetime import date

from data.schedule_intel import (
    _utc_offset_hours,
    compute_schedule_intel,
    haversine_miles,
)

# Venue fixtures (real coordinates/timezones).
ATHENS = {"name": "Sanford", "latitude": 33.9497, "longitude": -83.3733,
          "elevation": 220.0, "timezone": "America/New_York"}
LA = {"name": "Coliseum", "latitude": 34.0141, "longitude": -118.2879,
      "elevation": 50.0, "timezone": "America/Los_Angeles"}
LARAMIE = {"name": "War Memorial", "latitude": 41.3114, "longitude": -105.5666,
           "elevation": 2194.0, "timezone": "America/Denver"}  # ~7200 ft altitude


# -- geometry / timezone helpers ----------------------------------------------
def test_haversine_known_city_pair():
    # NYC (40.7128,-74.0060) -> LA (34.0522,-118.2437) ≈ 2445 miles.
    d = haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
    assert abs(d - 2445) < 25, d


def test_haversine_zero_for_same_point():
    assert haversine_miles(33.9, -83.3, 33.9, -83.3) == 0.0


def test_utc_offset_dst_aware():
    # Mid-September: Eastern = -4 (EDT), Pacific = -7 (PDT).
    assert _utc_offset_hours("America/New_York", date(2026, 9, 12)) == -4
    assert _utc_offset_hours("America/Los_Angeles", date(2026, 9, 12)) == -7
    assert _utc_offset_hours(None, date(2026, 9, 12)) is None


# -- compute_schedule_intel ---------------------------------------------------
def _games():
    # GEORGIA: wk1 home vs CLEMSON, wk2 @ UCLA (LA), wk4 @ someone (bye in wk3).
    return [
        {"week": 1, "home_team": "GEORGIA", "away_team": "CLEMSON",
         "start_date": "2026-08-29", "completed": True},
        {"week": 2, "home_team": "UCLA", "away_team": "GEORGIA",
         "start_date": "2026-09-05", "completed": True},
        {"week": 4, "home_team": "GEORGIA", "away_team": "AUBURN",
         "start_date": "2026-09-19", "completed": False},
    ]


VENUES = {"GEORGIA": ATHENS, "UCLA": LA}


def test_home_game_no_travel_no_tz_crossing():
    intel = compute_schedule_intel("GEORGIA", "CLEMSON", 1, "2026-08-29", True, ATHENS,
                                   _games(), VENUES)
    assert intel["travel_distance"] == 0.0
    assert intel["time_zones_crossed"] == 0 and intel["tz_direction"] == "none"
    assert intel["consecutive_road_games"] == 0
    assert intel["altitude"] == 220.0


def test_road_game_travel_and_westward_tz():
    # GEORGIA @ UCLA (week 2): Athens -> LA, ~1990 mi, 3 zones west.
    intel = compute_schedule_intel("GEORGIA", "UCLA", 2, "2026-09-05", False, LA,
                                   _games(), VENUES)
    assert 1960 < intel["travel_distance"] < 2020, intel["travel_distance"]
    assert intel["time_zones_crossed"] == 3 and intel["tz_direction"] == "west"
    assert intel["rest_days"] == 7 and intel["short_week"] is False
    assert intel["consecutive_road_games"] == 1  # first road game
    assert intel["altitude"] == 50.0


def test_short_week_flag():
    games = [
        {"week": 5, "home_team": "GEORGIA", "away_team": "X", "start_date": "2026-09-26"},
        {"week": 6, "home_team": "GEORGIA", "away_team": "Y", "start_date": "2026-10-01"},  # 5 days
    ]
    intel = compute_schedule_intel("GEORGIA", "Y", 6, "2026-10-01", True, ATHENS,
                                   games, {"GEORGIA": ATHENS})
    assert intel["rest_days"] == 5 and intel["short_week"] is True


def test_bye_detection():
    # Week 4 game with no week-3 game → bye. (week-2 was the last game.)
    intel = compute_schedule_intel("GEORGIA", "AUBURN", 4, "2026-09-19", True, ATHENS,
                                   _games(), VENUES)
    assert intel["bye"] is True


def test_altitude_passthrough_for_high_venue():
    intel = compute_schedule_intel("GEORGIA", "WYOMING", 3, "2026-09-12", False, LARAMIE,
                                   _games(), {"GEORGIA": ATHENS, "WYOMING": LARAMIE})
    assert intel["altitude"] == 2194.0  # ~7200 ft — the schedule-intel altitude signal


def test_missing_venue_coords_yield_none_not_fabricated():
    intel = compute_schedule_intel("GEORGIA", "CLEMSON", 1, "2026-08-29", False,
                                   {"name": "Unknown"}, _games(), {})
    assert intel["travel_distance"] is None and intel["time_zones_crossed"] is None


def test_sandwich_spot_ranked_adjacent_opponent():
    games = [
        {"week": 7, "home_team": "GEORGIA", "away_team": "VANDERBILT", "start_date": "2026-10-10"},
        {"week": 8, "home_team": "GEORGIA", "away_team": "FLORIDA", "start_date": "2026-10-17"},
    ]
    ratings = {"FLORIDA": {"ranking": 4}}  # ranked opponent next week
    intel = compute_schedule_intel("GEORGIA", "VANDERBILT", 7, "2026-10-10", True, ATHENS,
                                   games, {"GEORGIA": ATHENS}, ratings)
    assert intel["sandwich_spot"] is True


def test_sandwich_spot_none_when_strength_unknown():
    games = [
        {"week": 7, "home_team": "GEORGIA", "away_team": "VANDERBILT", "start_date": "2026-10-10"},
        {"week": 8, "home_team": "GEORGIA", "away_team": "FLORIDA", "start_date": "2026-10-17"},
    ]
    intel = compute_schedule_intel("GEORGIA", "VANDERBILT", 7, "2026-10-10", True, ATHENS,
                                   games, {"GEORGIA": ATHENS}, ratings={})
    assert intel["sandwich_spot"] is None  # adjacent opponents' SP+ unknown → missing
