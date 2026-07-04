"""Projection roll-up tests (SPEC §6.5): projected-win-total arithmetic, FBS scoping,
determinism/byte-reproducibility, and the experimental/meta contract."""

from __future__ import annotations

import json

from analytics.projections import SCHEMA_VERSION, build_projections


def _snap(games, sp=None):
    return {"meta": {"snapshot_id": "projtest", "week": 3, "year": 2026,
                     "built_at": "2026-09-15T12:00:00Z"},
            "data": {"games": games, "sp_ratings": sp or {},
                     "returning_production": {}, "venues": {}}}


def _completed(wk, home, away, hp, ap):
    return {"week": wk, "home_team": home, "away_team": away, "home_points": hp,
            "away_points": ap, "completed": True,
            "start_date": f"2026-09-{wk:02d}", "neutral_site": False}


def _remaining(wk, home, away):
    return {"week": wk, "home_team": home, "away_team": away, "home_points": None,
            "away_points": None, "completed": False,
            "start_date": f"2026-09-{wk:02d}", "neutral_site": False}


def test_projected_wins_arithmetic_and_symmetry():
    games = [
        _completed(5, "GEORGIA", "ALABAMA", 30, 10),   # Georgia beats Alabama
        _remaining(12, "CLEMSON", "GEORGIA"),          # Clemson hosts Georgia
        _remaining(19, "ALABAMA", "CLEMSON"),
    ]
    proj = build_projections(_snap(games))
    g = proj["teams"]["GEORGIA"]
    assert (g["wins_so_far"], g["losses_so_far"], g["remaining"]) == (1, 0, 1)
    remaining_wp = sum(x["win_prob"] for x in g["games"] if not x["completed"])
    assert abs(g["projected_wins"] - (1 + remaining_wp)) < 5e-3  # within stored rounding
    assert abs(g["projected_wins"] + g["projected_losses"] - 2) < 1e-6  # 2 games total

    a = proj["teams"]["ALABAMA"]
    assert (a["wins_so_far"], a["losses_so_far"]) == (0, 1)

    # win-prob symmetry: the same game viewed from both sides sums to 1.
    g_vs_clem = next(x for x in g["games"] if x["opponent"] == "CLEMSON")
    c_vs_g = next(x for x in proj["teams"]["CLEMSON"]["games"] if x["opponent"] == "GEORGIA")
    assert abs(g_vs_clem["win_prob"] + c_vs_g["win_prob"] - 1.0) < 1e-6
    # opposite perspective → opposite-signed model spread.
    assert abs(g_vs_clem["model_spread"] + c_vs_g["model_spread"]) < 1e-6


def test_completed_games_score_deterministically():
    proj = build_projections(_snap([_completed(5, "GEORGIA", "ALABAMA", 30, 10)]))
    g_game = proj["teams"]["GEORGIA"]["games"][0]
    assert g_game["completed"] and g_game["won"] is True and g_game["win_prob"] == 1.0
    assert g_game["model_spread"] is None  # already played


def test_only_fbs_teams_projected_fcs_priced_but_not_listed():
    # FCS opponent: priced (flat prior) so Georgia gets a win prob, but FCS not projected.
    proj = build_projections(_snap([_remaining(1, "GEORGIA", "AUSTIN PEAY")]))
    assert "GEORGIA" in proj["teams"] and "AUSTIN PEAY" not in proj["teams"]
    assert proj["teams"]["GEORGIA"]["remaining"] == 1


def test_meta_experimental_and_frozen_clock():
    m = build_projections(_snap([]))["meta"]
    assert m["schema_version"] == SCHEMA_VERSION and m["experimental"] is True
    assert m["generated_at"] == "2026-09-15T12:00:00Z"  # frozen from snapshot built_at
    assert m["snapshot_id"] == "projtest" and m["margin_sigma"] == 16.0
    assert "FCS" in m["counts"] and "regular season" in m["counts"]


def test_byte_reproducible():
    games = [_completed(5, "GEORGIA", "ALABAMA", 30, 10), _remaining(12, "GEORGIA", "CLEMSON")]
    a = json.dumps(build_projections(_snap(games)), sort_keys=True)
    b = json.dumps(build_projections(_snap(games)), sort_keys=True)
    assert a == b


def test_unscheduled_fbs_teams_surfaced_not_dropped():
    # Only Georgia + Alabama have a game; every other FBS team is still present with
    # schedule_missing (loud coverage), and meta.coverage records the gap.
    proj = build_projections(_snap([_remaining(1, "GEORGIA", "ALABAMA")]))
    cov = proj["meta"]["coverage"]
    assert cov["fbs_total"] == len(proj["teams"])  # every FBS team present, none dropped
    assert cov["scheduled"] == 2 and "CAL" in cov["unscheduled"]
    cal = proj["teams"]["CAL"]
    assert cal["schedule_missing"] is True and cal["projected_wins"] is None
    assert proj["teams"]["GEORGIA"]["schedule_missing"] is False


def test_write_projections_byte_reproducible(tmp_path):
    from scripts.build_projections import write_projections
    games = [_completed(5, "GEORGIA", "ALABAMA", 30, 10), _remaining(12, "GEORGIA", "CLEMSON")]
    first = write_projections(build_projections(_snap(games)), 2026, 3, base=tmp_path).read_bytes()
    again = write_projections(build_projections(_snap(games)), 2026, 3, base=tmp_path).read_bytes()
    assert again == first
    loaded = json.loads(first)
    assert list(loaded["teams"]) == sorted(loaded["teams"])  # deterministic key order


def test_sp_plus_favorite_projects_more_wins():
    # A strong SP+ prior should out-project a weak one over identical remaining games.
    games = [_remaining(1, "GEORGIA", "VANDERBILT"), _remaining(2, "VANDERBILT", "GEORGIA")]
    proj = build_projections(_snap(games, sp={"GEORGIA": {"rating": 25.0},
                                              "VANDERBILT": {"rating": -15.0}}))
    assert proj["teams"]["GEORGIA"]["projected_wins"] > proj["teams"]["VANDERBILT"]["projected_wins"]
