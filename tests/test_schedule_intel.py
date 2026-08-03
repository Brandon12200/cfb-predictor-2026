"""Unit tests for the schedule-intelligence dataset (SPEC §5.4.2 acceptance).

Known-fixture coverage of travel distance, rest days, time-zone crossings + direction,
altitude, consecutive road games, byes, and sandwich spots. Pure function → offline.
"""

from datetime import date

import pytest

from data.schedule_intel import (
    _utc_offset_hours,
    compute_schedule_intel,
    haversine_miles,
    resolve_venue_timezone,
)

# Venue fixtures (real coordinates/timezones).
ATHENS = {"name": "Sanford", "latitude": 33.9497, "longitude": -83.3733,
          "elevation": 220.0, "timezone": "America/New_York"}
LA = {"name": "Coliseum", "latitude": 34.0141, "longitude": -118.2879,
      "elevation": 50.0, "timezone": "America/Los_Angeles"}
LARAMIE = {"name": "War Memorial", "latitude": 41.3114, "longitude": -105.5666,
           "elevation": 2194.0, "timezone": "America/Denver"}  # metres — ~7198 ft, the highest FBS venue


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
    assert intel["altitude"] == pytest.approx(220.0 * 3.28084)  # metres in, FEET out (A6)


def test_road_game_travel_and_westward_tz():
    # GEORGIA @ UCLA (week 2): Athens -> LA, ~1990 mi, 3 zones west.
    intel = compute_schedule_intel("GEORGIA", "UCLA", 2, "2026-09-05", False, LA,
                                   _games(), VENUES)
    assert 1960 < intel["travel_distance"] < 2020, intel["travel_distance"]
    assert intel["time_zones_crossed"] == 3 and intel["tz_direction"] == "west"
    assert intel["rest_days"] == 7 and intel["short_week"] is False
    assert intel["consecutive_road_games"] == 1  # first road game
    assert intel["altitude"] == pytest.approx(50.0 * 3.28084)  # metres in, FEET out (A6)


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


def test_altitude_converts_metres_to_feet_for_high_venue():
    """A6 regression: elevation is metres at rest, `altitude` is FEET.

    Before A6 this asserted raw passthrough (2194.0), and the fixture's own comment said
    "~7200 ft" — the unit mismatch was documented in a comment while being asserted through.
    The factor compares this value against the ratified 4000-FOOT threshold, so a metres value
    could never clear it and `Altitude` never fired at any venue in any week.
    """
    intel = compute_schedule_intel("GEORGIA", "WYOMING", 3, "2026-09-12", False, LARAMIE,
                                   _games(), {"GEORGIA": ATHENS, "WYOMING": LARAMIE})
    assert intel["altitude"] == pytest.approx(7198.4, abs=1.0)


def test_high_altitude_venue_clears_the_ratified_threshold():
    """The check that would have caught A6: a genuinely high venue must FIRE the factor."""
    from factors.physical_coefficients import DEFAULT_PHYSICAL_COEFFICIENTS as CFG
    from factors.physical_coefficients import altitude_points

    # WYOMING is the home side at LARAMIE → its intel is what the factor reads.
    home_intel = compute_schedule_intel("WYOMING", "GEORGIA", 3, "2026-09-12", True, LARAMIE,
                                        _games(), {"GEORGIA": ATHENS, "WYOMING": LARAMIE})
    assert home_intel["altitude"] > CFG.altitude_threshold_ft, "a ~7200 ft venue must clear 4000 ft"
    assert altitude_points(home_intel, False) == CFG.altitude_value
    # ...and a neutral-site game gives no acclimation edge, however high the venue.
    assert altitude_points(home_intel, True) == 0.0


def test_sea_level_venue_does_not_clear_the_threshold():
    """The other half of the pin: a low venue must NOT fire (no blanket-fire regression)."""
    from factors.physical_coefficients import DEFAULT_PHYSICAL_COEFFICIENTS as CFG
    from factors.physical_coefficients import altitude_points

    home_intel = compute_schedule_intel("UCLA", "GEORGIA", 2, "2026-09-05", True, LA,
                                        _games(), VENUES)
    assert home_intel["altitude"] < CFG.altitude_threshold_ft, "a ~164 ft venue must not clear 4000 ft"
    assert altitude_points(home_intel, False) == 0.0


def test_missing_elevation_is_honest_missing_not_sea_level():
    """`None`, never 0.0 — a fabricated 'sea level' would be binding-principle #4 violation."""
    no_elev = {**ATHENS}
    no_elev.pop("elevation")
    intel = compute_schedule_intel("GEORGIA", "CLEMSON", 1, "2026-08-29", True, no_elev,
                                   _games(), VENUES)
    assert intel["altitude"] is None


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

# ── Venue timezone fallback (owner-ratified 2026-08-03) ───────────────────────────────────────
# CFBD serves `timezone: null` for 8 of 138 FBS venues, two of them tracked. Because
# `travel_points` keys ONLY on `time_zones_crossed`, a null made a real multi-zone trip score as
# zero zones — a ratified coefficient neutered by an input that never arrives (the A6 family).
# These pins assert the MEANING of the fix, not stored values (the LARAMIE doctrine).

# The two tracked venues CFBD serves without a timezone.
EVANSTON = {"name": "Lanny and Sharon Martin Stadium", "latitude": None, "longitude": None,
            "elevation": None, "timezone": None}          # Northwestern — Central
PISCATAWAY = {"name": "SHI Stadium", "latitude": 40.5462553, "longitude": -74.4660408,
              "elevation": None, "timezone": None}        # Rutgers — Eastern


def test_every_tracked_venue_resolves_a_timezone():
    """Load-bearing pin: no tracked venue may be left without a resolvable timezone.

    Fails if CFBD drops the timezone for another venue and the static table is not updated — the
    exact regression that produced this fix, caught before it can silently zero a travel term.
    """
    pytest.importorskip("data.snapshot")
    from data.snapshot import load_snapshot
    from data.team_registry import get_all_tracked_teams

    venues = load_snapshot(1, 2026)["data"]["venues"]
    tracked = get_all_tracked_teams()
    unresolved = sorted(t for t, v in venues.items()
                        if t in tracked and not resolve_venue_timezone(v))
    assert unresolved == [], f"tracked venues with no resolvable timezone: {unresolved}"


def test_three_zone_eastward_trip_prices_at_the_ratified_cap():
    """A 3-zone crossing must clamp to `travel_cap`, not scale linearly.

    Asserts the physical meaning: LA -> Piscataway is three zones east, which at the ratified
    `tz_per_zone` would be 1.8 pts — the ratified `travel_cap` holds it at 1.5.
    """
    from factors.physical_coefficients import DEFAULT_PHYSICAL_COEFFICIENTS as C
    from factors.physical_coefficients import travel_points

    games = [{"week": 3, "home_team": "RUTGERS", "away_team": "USC", "start_date": "2026-09-12"}]
    venues = {"RUTGERS": PISCATAWAY, "USC": LA}
    home = compute_schedule_intel("RUTGERS", "USC", 3, "2026-09-12", True, PISCATAWAY,
                                  games, venues)
    away = compute_schedule_intel("USC", "RUTGERS", 3, "2026-09-12", False, PISCATAWAY,
                                  games, venues)

    assert away["time_zones_crossed"] == 3
    assert away["tz_direction"] == "east"
    assert home["time_zones_crossed"] == 0        # the host crosses nothing

    pts = travel_points(home, away)
    assert pts == pytest.approx(C.travel_cap), "3 zones must clamp to travel_cap, not 3 x tz_per_zone"
    assert pts < 3 * C.tz_per_zone


def test_neutral_site_stays_honestly_none():
    """A neutral site has no host venue, so there is no acclimation edge however far the travel."""
    games = [{"week": 3, "home_team": "RUTGERS", "away_team": "USC", "start_date": "2026-09-12"}]
    intel = compute_schedule_intel("USC", "RUTGERS", 3, "2026-09-12", False, None,
                                   games, {"RUTGERS": PISCATAWAY, "USC": LA})
    assert intel["time_zones_crossed"] is None
    assert intel["tz_direction"] is None


def test_venue_in_neither_source_records_missing():
    """Unknown to CFBD and to the static table -> None, never a fabricated offset (binding #4)."""
    unknown = {"name": "Nowhere Field", "latitude": 40.0, "longitude": -75.0,
               "elevation": None, "timezone": None}
    assert resolve_venue_timezone(unknown) is None

    games = [{"week": 3, "home_team": "NOWHERE", "away_team": "USC", "start_date": "2026-09-12"}]
    intel = compute_schedule_intel("USC", "NOWHERE", 3, "2026-09-12", False, unknown,
                                   games, {"NOWHERE": unknown, "USC": LA})
    assert intel["time_zones_crossed"] is None


def test_dateless_input_still_yields_none():
    """A dateless hypothetical has no answer: UTC offset is DST-dependent, so `None` is correct.

    Pinned so a later change cannot silently fabricate an offset for a matchup with no date. The
    distance, which needs only coordinates, still computes — that asymmetry is by design.
    """
    games = [{"week": 3, "home_team": "RUTGERS", "away_team": "USC", "start_date": "2026-09-12"}]
    intel = compute_schedule_intel("USC", "RUTGERS", 3, None, False, PISCATAWAY,
                                   games, {"RUTGERS": PISCATAWAY, "USC": LA})
    assert intel["time_zones_crossed"] is None
    assert intel["tz_direction"] is None
    assert intel["travel_distance"] is not None    # date-free geometry still resolves


def test_no_static_table_key_is_ambiguous():
    """Guards the `Memorial Stadium` class: a venue NAME shared by two differently-zoned venues.

    The table is keyed by name, so a key shared by venues in different zones would be wrong for one
    of them. Any snapshot venue matching a table key must either have no timezone of its own, or
    agree with the table.
    """
    pytest.importorskip("data.snapshot")
    from data.snapshot import load_snapshot
    from data.venue_timezones import STATIC_VENUE_TIMEZONES

    conflicts = []
    for team, v in load_snapshot(1, 2026)["data"]["venues"].items():
        table_tz = STATIC_VENUE_TIMEZONES.get(v.get("name"))
        own_tz = v.get("timezone")
        if table_tz and own_tz and own_tz != table_tz:
            conflicts.append((team, v.get("name"), own_tz, table_tz))
    assert conflicts == [], f"static-table keys conflict with a venue's own timezone: {conflicts}"


def test_both_layers_resolve_the_same_value_from_the_same_table():
    """Two-layer consistency: the builder path and the read seam must never disagree.

    `normalize_venue` bakes the fallback into FUTURE snapshots; `resolve_venue_timezone` backfills
    already-built ones. If those two ever drew on different tables, a snapshot rebuild would
    silently change model output. This pin fails the moment they diverge.
    """
    from data.normalize.cfbd import normalize_venue
    from data.venue_timezones import STATIC_VENUE_TIMEZONES

    for name, expected in STATIC_VENUE_TIMEZONES.items():
        loc = {"name": name, "latitude": None, "longitude": None,
               "elevation": None, "timezone": None}
        assert normalize_venue(loc).timezone == expected, f"normalize layer: {name}"
        assert resolve_venue_timezone(loc) == expected, f"read seam: {name}"

    # A source value always wins over the table, in both layers.
    override = {"name": "SHI Stadium", "latitude": None, "longitude": None,
                "elevation": None, "timezone": "America/Denver"}
    assert normalize_venue(override).timezone == "America/Denver"
    assert resolve_venue_timezone(override) == "America/Denver"
