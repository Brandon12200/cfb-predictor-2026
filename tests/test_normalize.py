"""Unit tests for the normalize layer (canonical dataclasses + converters). Offline."""

from data.normalize import cfbd, odds
from data.normalize.models import (
    Coaching,
    CoachingComparison,
    GameContext,
    TeamData,
    TeamInfo,
    TeamScheduleResult,
    compute_derived_metrics,
)


# -- models / context projection ----------------------------------------------
def test_context_dict_has_the_factor_facing_keys():
    ctx = GameContext(
        home_team="GEORGIA", away_team="CLEMSON", week=1, year=2026,
        vegas_spread=-3.5, has_betting_data=True,
        home_team_data=TeamData("GEORGIA"), away_team_data=TeamData("CLEMSON"),
        coaching_comparison=CoachingComparison("GEORGIA", "CLEMSON"),
        data_quality=0.8, timestamp="2026-08-29T12:00:00", snapshot_id="snap1",
    )
    d = ctx.to_context_dict()
    for key in ("home_team", "away_team", "week", "year", "timestamp", "vegas_spread",
                "has_betting_data", "home_team_data", "away_team_data",
                "coaching_comparison", "data_quality", "data_sources"):
        assert key in d
    assert d["home_team_data"]["info"]["conference"] == {"name": None}
    assert d["home_team_data"]["team_name"] == "GEORGIA"
    assert d["snapshot_id"] == "snap1"


def test_teamdata_dict_shape_matches_schema():
    td = TeamData(
        "GEORGIA",
        info=TeamInfo(status="ok", conference="SEC"),
        coaching=Coaching(head_coach_experience=9, tenure_years=4, status="ok"),
        schedule=[TeamScheduleResult(completed=True, result="W", team_score=38,
                                     opponent_score=10, is_home_game=True)],
    )
    d = td.to_dict()
    assert d["info"] == {"status": "ok", "conference": {"name": "SEC"}}
    assert d["coaching"]["head_coach_experience"] == 9
    assert d["schedule"][0]["result"] == "W"
    assert d["derived_metrics"] == {}  # no completed games passed to derived


def test_missing_coaching_fields_are_none_not_fabricated():
    c = Coaching()
    assert c.head_coach_experience is None and c.tenure_years is None


def test_compute_derived_metrics_record_and_splits():
    sched = [
        TeamScheduleResult(completed=True, result="W", is_home_game=True),
        TeamScheduleResult(completed=True, result="L", is_home_game=False),
        TeamScheduleResult(completed=True, result="W", is_home_game=True),
        TeamScheduleResult(completed=False, result=None, is_home_game=False),
    ]
    dm = compute_derived_metrics(sched)
    assert dm.current_record.wins == 2 and dm.current_record.losses == 1
    assert round(dm.current_record.win_percentage, 3) == 0.667
    assert dm.venue_performance.home_record.wins == 2
    assert dm.venue_performance.away_record.losses == 1


def test_compute_derived_metrics_empty_when_no_completed():
    assert compute_derived_metrics([]) == compute_derived_metrics(
        [TeamScheduleResult(completed=False)])


# -- CFBD converters ----------------------------------------------------------
def test_normalize_games_resolves_and_drops_unresolved():
    raw = [
        {"week": 1, "homeTeam": "Georgia", "awayTeam": "Clemson",
         "homePoints": 34, "awayPoints": 3, "startDate": "2026-08-30", "completed": True},
        {"week": 1, "homeTeam": "Not A Real Team XYZ", "awayTeam": "Georgia"},
    ]
    games = cfbd.normalize_games(raw)
    assert len(games) == 1
    assert games[0].home_team == "GEORGIA" and games[0].away_team == "CLEMSON"
    assert games[0].home_points == 34 and games[0].completed is True


def test_team_schedule_projects_perspective_and_result():
    games = cfbd.normalize_games([
        {"week": 1, "homeTeam": "Georgia", "awayTeam": "Clemson",
         "homePoints": 34, "awayPoints": 3, "completed": True},
        {"week": 2, "homeTeam": "Alabama", "awayTeam": "Georgia",
         "homePoints": 20, "awayPoints": 27, "completed": True},
    ])
    sched = cfbd.team_schedule(games, "GEORGIA")
    assert len(sched) == 2
    home_game = [g for g in sched if g.is_home_game][0]
    assert home_game.result == "W" and home_game.team_score == 34
    away_game = [g for g in sched if not g.is_home_game][0]
    assert away_game.result == "W" and away_game.team_score == 27  # Georgia won @ Alabama


def test_normalize_advanced_stats_keyed_by_canonical_team():
    rows = [{"team": "Ole Miss", "offense": {"successRate": 0.5},
             "defense": {"successRate": 0.4}}]
    out = cfbd.normalize_advanced_stats(rows)
    assert "MISSISSIPPI" in out
    assert out["MISSISSIPPI"].offense["successRate"] == 0.5


def test_normalize_venue_parses_elevation_string():
    v = cfbd.normalize_venue({"name": "Sanford", "latitude": 33.9, "longitude": -83.4,
                              "elevation": "220.5", "timezone": "America/New_York",
                              "dome": False})
    assert v.elevation == 220.5 and v.timezone == "America/New_York" and v.dome is False


# -- Odds converter -----------------------------------------------------------
def _event(home, away, points):
    return {"home_team": home, "away_team": away, "bookmakers": [
        {"key": prov, "markets": [{"key": "spreads", "outcomes": [
            {"name": home, "point": pt}, {"name": away, "point": -pt}]}]}
        for prov, pt in points]}


def test_normalize_lines_and_consensus():
    events = [_event("Georgia", "Clemson", [("fanduel", -3.5), ("draftkings", -3.0)])]
    lines = odds.normalize_lines(events)
    gl = lines[("GEORGIA", "CLEMSON")]
    assert {ln.provider for ln in gl.lines} == {"fanduel", "draftkings"}
    assert odds.consensus_spread(gl) == -3.2  # mean(-3.5,-3.0) rounded


def test_consensus_none_when_no_book_posted():
    gl = odds.normalize_lines([_event("Georgia", "Clemson", [])])[("GEORGIA", "CLEMSON")]
    assert odds.consensus_spread(gl) is None  # missing, not fabricated 0.0
