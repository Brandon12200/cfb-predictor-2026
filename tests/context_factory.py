"""Shared factory for the snapshot-assembled game context (Phase 1b test support).

Post-1b the engine reads context from a snapshot, not live odds/ESPN clients. Tests
that exercise engine/factor behavior use `patched_context(...)` to inject a canonical
context for the teams the engine actually requests — replacing the old
`patch(OddsAPIClient)/patch(ESPNStatsClient)` mocking of the retired live-fetch path.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

from utils.normalizer import normalizer


def _default_schedule() -> list[dict[str, Any]]:
    """A plausible mid-season completed schedule (feeds momentum/desperation)."""
    return [
        {"completed": True, "date": "2026-09-05", "result": "W",
         "team_score": 31, "opponent_score": 17, "is_home_game": True},
        {"completed": True, "date": "2026-09-12", "result": "W",
         "team_score": 24, "opponent_score": 20, "is_home_game": False},
        {"completed": True, "date": "2026-09-19", "result": "L",
         "team_score": 21, "opponent_score": 28, "is_home_game": False},
    ]


def make_team_data(name: str, conference: str = "SEC", experience: int = 8,
                   tenure: int = 4, has_stats: bool = True,
                   schedule: list | None = None, record: dict | None = None,
                   is_home: bool = False) -> dict[str, Any]:
    schedule = _default_schedule() if schedule is None else schedule
    if record is None:
        wins = sum(1 for g in schedule if g.get("result") == "W")
        losses = sum(1 for g in schedule if g.get("result") == "L")
        denom = wins + losses
        record = {"wins": wins, "losses": losses,
                  "win_percentage": wins / denom if denom else 0.0}
    return {
        "team_name": name,
        "info": {"status": "cfbd", "conference": {"name": conference}},
        "coaching": {"head_coach_name": f"{name} Coach", "head_coach_experience": experience,
                     "tenure_years": tenure, "status": "cfbd"},
        "stats": {"status": "cfbd" if has_stats else None},
        "schedule": schedule,
        "derived_metrics": {
            "current_record": record,
            "venue_performance": {
                "home_record": {"wins": 1, "losses": 0, "total_games": 1, "win_percentage": 1.0},
                "away_record": {"wins": 1, "losses": 1, "total_games": 2, "win_percentage": 0.5},
            },
        },
        "is_home": is_home,
    }


def _default_advanced(team: str, off_success: float = 0.45) -> dict[str, Any]:
    return {
        "team": team,
        "offense": {"successRate": off_success, "explosiveness": 1.3, "ppa": 0.18,
                    "plays": 70, "havoc": {"total": 0.16},
                    "standardDowns": {"successRate": 0.48},
                    "passingDowns": {"successRate": 0.27}},
        "defense": {"successRate": 0.40, "explosiveness": 1.1, "ppa": 0.05,
                    "plays": 68, "havoc": {"total": 0.18},
                    "standardDowns": {"successRate": 0.43},
                    "passingDowns": {"successRate": 0.24}},
    }


def make_context(home: str = "GEORGIA", away: str = "ALABAMA", week: int | None = 1,
                 year: int = 2026, vegas_spread: float | None = -3.0,
                 home_team_data: dict | None = None, away_team_data: dict | None = None,
                 games: list | None = None, advanced_stats: dict | None = None,
                 betting_lines: dict | None = None, data_quality: float = 0.8,
                 snapshot_id: str = "test_snapshot") -> dict[str, Any]:
    home_td = home_team_data or make_team_data(home, is_home=True)
    away_td = away_team_data or make_team_data(away)
    if advanced_stats is None:
        advanced_stats = {home: _default_advanced(home, off_success=0.47),
                          away: _default_advanced(away, off_success=0.43)}
    if games is None:
        games = [
            {"week": 1, "home_team": home, "away_team": away, "home_points": 31,
             "away_points": 17, "start_date": "2026-09-05", "completed": True},
            {"week": 2, "home_team": away, "away_team": home, "home_points": 20,
             "away_points": 24, "start_date": "2026-09-12", "completed": True},
        ]
    hc, ac = home_td["coaching"], away_td["coaching"]
    he, ae = hc.get("head_coach_experience"), ac.get("head_coach_experience")
    diff = (he - ae) if (he is not None and ae is not None) else None
    return {
        "home_team": home, "away_team": away, "week": week, "year": year,
        "timestamp": "2026-08-29T12:00:00+00:00", "snapshot_id": snapshot_id,
        "data_sources": ["snapshot"],
        "vegas_spread": vegas_spread, "has_betting_data": vegas_spread is not None,
        "home_team_data": home_td, "away_team_data": away_td,
        "coaching_comparison": {
            "home_team": home, "away_team": away, "home_coaching": hc, "away_coaching": ac,
            "experience_differential": diff,
            "head_to_head_record": {"home_wins": 0, "away_wins": 0, "total_games": 0,
                                    "note": "n/a"},
        },
        "games": games or [], "advanced_stats": advanced_stats or {},
        "betting_lines": betting_lines or {},
        "data_quality": data_quality,
        "data_quality_report": {"score": data_quality, "checks": {}, "missing_fields": []},
    }


@contextmanager
def patched_context(vegas_spread: float | None = -3.0, **kwargs):
    """Patch DataManager.get_game_context to build a context from the requested teams.

    `vegas_spread=None` reproduces the no-betting-line gate. Extra kwargs pass through
    to `make_context` (e.g. `home_team_data=...`, `data_quality=...`).
    """
    def _fake(self, home_team, away_team, week=None, year=2026, snapshot=None):
        return make_context(home=normalizer.normalize(home_team) or home_team,
                            away=normalizer.normalize(away_team) or away_team,
                            week=week, vegas_spread=vegas_spread, **kwargs)

    with patch("data.data_manager.DataManager.get_game_context", _fake):
        yield


def _merge_espn(name: str, espn: dict | None, is_home: bool) -> dict:
    """Fold a scenario test's ESPN-style team dict (`info`/`derived_metrics`/`schedule`)
    into the canonical team-data shape, so the test's configured data actually drives
    the engine (rather than being silently ignored)."""
    td = make_team_data(name, is_home=is_home)
    if not isinstance(espn, dict):
        return td
    if "info" in espn and isinstance(espn["info"], dict):
        conf = espn["info"].get("conference", {})
        td["info"] = {"status": "cfbd",
                      "conference": conf if isinstance(conf, dict) else {"name": conf}}
    if "derived_metrics" in espn:
        td["derived_metrics"] = espn["derived_metrics"]
    if "schedule" in espn:
        td["schedule"] = espn["schedule"]
    return td


@contextmanager
def patched_context_from_mocks(**kwargs):
    """Migration shim for scenario tests that used to `patch(OddsAPIClient)` +
    `patch(ESPNStatsClient)`. Yields `(mock_odds, mock_espn)` and patches
    `get_game_context` so that BOTH the test's `mock_odds.return_value` (vegas spread)
    AND its `mock_espn.return_value`/`side_effect` (per-team data) actually drive the
    engine — reviving the scenario setups the retired live-fetch path used to consume.
    Extra kwargs pass through to `make_context`.
    """
    mock_odds = MagicMock()
    mock_odds.return_value = -3.0
    mock_espn = MagicMock()
    mock_espn.return_value = None
    mock_espn.side_effect = None

    def _espn_pair():
        if isinstance(mock_espn.side_effect, (list, tuple)) and mock_espn.side_effect:
            seq = list(mock_espn.side_effect)
            return seq[0], (seq[1] if len(seq) > 1 else seq[0])
        rv = mock_espn.return_value
        return (rv, rv) if isinstance(rv, dict) else (None, None)

    def _fake(self, home_team, away_team, week=None, year=2026, snapshot=None):
        spread = mock_odds.return_value
        if not isinstance(spread, (int, float)):
            spread = -3.0
        home = normalizer.normalize(home_team) or home_team
        away = normalizer.normalize(away_team) or away_team
        home_espn, away_espn = _espn_pair()
        overrides = dict(kwargs)
        overrides.setdefault("home_team_data", _merge_espn(home, home_espn, True))
        overrides.setdefault("away_team_data", _merge_espn(away, away_espn, False))
        return make_context(home=home, away=away, week=week, vegas_spread=spread, **overrides)

    with patch("data.data_manager.DataManager.get_game_context", _fake):
        yield mock_odds, mock_espn
