"""Matchup-pricer tests (SPEC §6.3/§6.4 acceptance): the pricer works for any two FBS
teams (real or hypothetical), is deterministic from a snapshot, prices home-field and
schedule intel with the right sign, and caps the rating signal early season."""

from __future__ import annotations

from engine.matchup_pricer import (
    DEFAULT_SCHEDULE_CONFIG,
    ScheduleAdjustmentConfig,
    compute_ratings_for_snapshot,
    price,
    schedule_adjustment,
)
from engine.power_ratings import DEFAULT_CONFIG, TeamRating, compute_ratings

# Real venue fixtures for travel/altitude.
ATHENS = {"name": "Sanford", "latitude": 33.9497, "longitude": -83.3733,
          "elevation": 220.0, "timezone": "America/New_York"}
LARAMIE = {"name": "War Memorial", "latitude": 41.3114, "longitude": -105.5666,
           "elevation": 7220.0, "timezone": "America/Denver"}
LA = {"name": "Coliseum", "latitude": 34.0141, "longitude": -118.2879,
      "elevation": 50.0, "timezone": "America/Los_Angeles"}


def _rating(team, elo, games=6, source="sp+"):
    return TeamRating(team=team, rating=elo, games_played=games, prior_elo=elo, prior_source=source)


# --------------------------------------------------------------------------- #
# Core pricing + sign convention
# --------------------------------------------------------------------------- #
def test_stronger_home_team_gets_negative_model_spread():
    ratings = {"HOME": _rating("HOME", 1600), "AWAY": _rating("AWAY", 1400)}
    p = price("HOME", "AWAY", ratings=ratings, season_games=[], venues={})
    # 200 Elo / 20 per point = 10 pts + 2.5 HFA, settled weight ~ full → home favored.
    assert p.home_margin > 10.0
    assert p.model_spread < 0  # negative = home favored, matching Vegas convention
    assert abs(p.model_spread + p.home_margin) < 1e-9


def test_neutral_site_drops_home_field():
    ratings = {"A": _rating("A", 1550), "B": _rating("B", 1450)}
    home = price("A", "B", ratings=ratings, season_games=[], venues={})
    neut = price("A", "B", ratings=ratings, season_games=[], venues={}, neutral_site=True)
    assert home.home_margin > neut.home_margin  # HFA removed on neutral
    assert neut.breakdown["hfa_points"] == 0.0


def test_pricer_is_deterministic():
    ratings = {"A": _rating("A", 1580), "B": _rating("B", 1470)}
    a = price("A", "B", ratings=ratings, season_games=[], venues={}, week=8)
    b = price("A", "B", ratings=ratings, season_games=[], venues={}, week=8)
    assert a.to_dict() == b.to_dict()


# --------------------------------------------------------------------------- #
# Hypothetical for ARBITRARY teams (SPEC §6.4 acceptance)
# --------------------------------------------------------------------------- #
def test_prices_any_two_teams_even_absent_from_ratings():
    # No precomputed ratings, no SP+/RP → both fall to flat prior; still prices.
    p = price("NEBRASKA", "WYOMING", ratings={}, season_games=[], venues={})
    assert p.home_prior_source == "flat" and p.away_prior_source == "flat"
    assert abs(p.rating_component) < 1e-9  # equal flat priors → no rating edge
    assert any("No preseason prior" in c for c in p.caveats)


def test_sp_plus_prior_drives_preseason_hypothetical_with_capped_signal():
    sp = {"BLUE": {"rating": 18.0}, "GRAY": {"rating": -2.0}}
    p = price("BLUE", "GRAY", ratings={}, season_games=[], venues={}, sp_ratings=sp, week=1)
    # Raw prior margin = 20 pts; week-1 uncertainty=1 → signal capped to the floor (40%).
    assert p.rating_uncertainty == 1.0
    assert p.rating_signal_weight == DEFAULT_CONFIG.rating_signal_floor
    assert abs(p.breakdown["rating_margin_raw"] - 20.0) < 1e-6
    assert abs(p.rating_component - 20.0 * DEFAULT_CONFIG.rating_signal_floor) < 1e-6
    assert any("Early season" in c for c in p.caveats)


# --------------------------------------------------------------------------- #
# Schedule-intelligence adjustment
# --------------------------------------------------------------------------- #
def test_schedule_adjustment_bye_short_week_travel_altitude():
    # Home off a bye, away on a short week, away crossed 2 zones, home at altitude.
    home_intel = {"bye": True, "short_week": False, "time_zones_crossed": 0, "altitude": 7220.0}
    away_intel = {"bye": False, "short_week": True, "time_zones_crossed": 2, "altitude": 7220.0}
    adj, parts = schedule_adjustment(home_intel, away_intel, neutral_site=False)
    assert parts["bye"] == DEFAULT_SCHEDULE_CONFIG.bye_value
    assert parts["short_week"] == DEFAULT_SCHEDULE_CONFIG.short_week_penalty  # away short → favors home
    assert parts["travel"] > 0  # away crossed more zones → favors home
    assert parts["altitude"] == DEFAULT_SCHEDULE_CONFIG.altitude_value
    assert adj == sum(parts.values()) > 0


def test_schedule_adjustment_is_symmetric_in_sign():
    # Mirror image: away off a bye, home on a short week → net favors away (negative).
    adj, _ = schedule_adjustment(
        {"bye": False, "short_week": True}, {"bye": True, "short_week": False}, neutral_site=False)
    assert adj < 0


def test_neutral_site_ignores_altitude():
    adj, parts = schedule_adjustment(
        {"altitude": 7220.0}, {"altitude": 7220.0}, neutral_site=True)
    assert "altitude" not in parts


def test_travel_favours_home_with_real_venues():
    # LA team travels to Athens (2 zones east); model spread shifts toward home.
    ratings = {"GEORGIA": _rating("GEORGIA", 1500), "USC": _rating("USC", 1500)}
    venues = {"GEORGIA": ATHENS, "USC": LA}
    season = [
        {"week": 1, "home_team": "GEORGIA", "away_team": "USC",
         "start_date": "2026-09-12T16:00:00Z", "completed": False},
    ]
    p = price("GEORGIA", "USC", ratings=ratings, season_games=season, venues=venues,
              week=2, game_date="2026-09-12")
    assert p.schedule_component > 0  # equal ratings, but travel/altitude favor Georgia
    assert p.model_spread < 0  # home favored purely on schedule intel


# --------------------------------------------------------------------------- #
# Snapshot memoization (reads only the snapshot; identical for a snapshot_id)
# --------------------------------------------------------------------------- #
def test_compute_ratings_for_snapshot_memoizes_by_id():
    games = [{"week": 1, "home_team": "A", "away_team": "B", "home_points": 30,
              "away_points": 10, "completed": True, "start_date": "2026-09-05Z"}]
    snap = {"meta": {"snapshot_id": "abc123"},
            "data": {"games": games, "sp_ratings": {}, "returning_production": {}}}
    r1 = compute_ratings_for_snapshot(snap)
    r2 = compute_ratings_for_snapshot(snap)
    assert r1 is r2  # memoized by snapshot_id
    direct = compute_ratings(games)
    assert {t: round(r.rating, 9) for t, r in r1.items()} == \
           {t: round(r.rating, 9) for t, r in direct.items()}
    assert r1["A"].rating > r1["B"].rating  # A won → higher rating


def _snap(sid, games):
    return {"meta": {"snapshot_id": sid},
            "data": {"games": games, "sp_ratings": {}, "returning_production": {}}}


def test_ratings_cache_does_not_collide_on_reused_snapshot_id():
    # Two snapshots share a (fabricated) snapshot_id but hold DIFFERENT games — the cache
    # must not return the first's ratings for the second (the reviewer-found hazard).
    g1 = [{"week": 1, "home_team": "A", "away_team": "B", "home_points": 30,
           "away_points": 10, "completed": True, "start_date": "2026-09-05Z"}]
    g2 = [{"week": 1, "home_team": "X", "away_team": "Y", "home_points": 30,
           "away_points": 10, "completed": True, "start_date": "2026-09-05Z"}]
    r1 = compute_ratings_for_snapshot(_snap("dup", g1))
    r2 = compute_ratings_for_snapshot(_snap("dup", g2))
    assert set(r1) == {"A", "B"} and set(r2) == {"X", "Y"}


def test_ratings_cache_respects_cfg():
    from engine.power_ratings import EloConfig
    g = [{"week": 1, "home_team": "A", "away_team": "B", "home_points": 40,
          "away_points": 10, "completed": True, "start_date": "2026-09-05Z"}]
    snap = _snap("cfgtest", g)
    r_default = compute_ratings_for_snapshot(snap)
    r_hotk = compute_ratings_for_snapshot(snap, cfg=EloConfig(k_early=200.0, k_late=200.0))
    assert r_default["A"].rating != r_hotk["A"].rating  # cfg change not masked by the cache


def test_custom_schedule_config_scales_adjustment():
    cfg = ScheduleAdjustmentConfig(bye_value=3.0)
    adj, parts = schedule_adjustment({"bye": True}, {"bye": False}, False, cfg)
    assert parts["bye"] == 3.0 and adj == 3.0
