"""CFBD source-native → canonical converters (layer 2).

CFBD v2 returns camelCase fields (homeTeam, homePoints, successRate…). These
functions map raw client output to the canonical dataclasses in `models`, resolving
team names through the registry-backed normalizer. Missing fields become `None`
(recorded `missing` in the manifest), never neutral-filled.
"""

from __future__ import annotations

from typing import Any

from data.normalize.models import (
    AdvancedStats,
    Coaching,
    ScheduleGame,
    TeamScheduleResult,
    Venue,
)
from utils.normalizer import normalizer


def _norm(name: str | None) -> str | None:
    return normalizer.normalize(name) if name else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_games(raw_games: list[dict]) -> list[ScheduleGame]:
    """CFBD `/games` rows → canonical league-wide season games (scheduling_fatigue)."""
    out: list[ScheduleGame] = []
    for g in raw_games:
        home = _norm(g.get("homeTeam"))
        away = _norm(g.get("awayTeam"))
        week = _int(g.get("week"))
        if home is None or away is None or week is None:
            continue  # unresolved teams are dropped here; the slate reconciler logs them
        out.append(ScheduleGame(
            week=week,
            home_team=home,
            away_team=away,
            home_points=_int(g.get("homePoints")),
            away_points=_int(g.get("awayPoints")),
            start_date=g.get("startDate"),
            completed=bool(g.get("completed", False)),
            neutral_site=bool(g.get("neutralSite", False)),
        ))
    return out


def team_schedule(games: list[ScheduleGame], team: str) -> list[TeamScheduleResult]:
    """Project league games into one team's own-perspective completed results
    (replaces the retired ESPN schedule fetch)."""
    results: list[TeamScheduleResult] = []
    for g in games:
        is_home = g.home_team == team
        if not is_home and g.away_team != team:
            continue
        team_score = g.home_points if is_home else g.away_points
        opp_score = g.away_points if is_home else g.home_points
        result: str | None = None
        if team_score is not None and opp_score is not None:
            result = "W" if team_score > opp_score else "L" if team_score < opp_score else "T"
        results.append(TeamScheduleResult(
            completed=bool(g.completed),
            date=g.start_date,
            result=result,
            team_score=team_score,
            opponent_score=opp_score,
            is_home_game=is_home,
        ))
    return results


def normalize_advanced_stats(raw_rows: list[dict]) -> dict[str, AdvancedStats]:
    """CFBD `/stats/season/advanced` rows → {canonical_team: AdvancedStats}."""
    out: dict[str, AdvancedStats] = {}
    for row in raw_rows:
        team = _norm(row.get("team"))
        if team is None:
            continue
        out[team] = AdvancedStats(
            team=team,
            offense=dict(row.get("offense") or {}),
            defense=dict(row.get("defense") or {}),
        )
    return out


def normalize_sp_ratings(raw_rows: list[dict]) -> dict[str, dict[str, Any]]:
    """CFBD `/ratings/sp` rows → {canonical_team: {rating, ranking, offense, defense}}.
    The opponent-strength source for schedule-intel sandwich spots + a Phase-2 prior."""
    out: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        team = _norm(row.get("team"))
        if team is None:
            continue
        offense = row.get("offense") or {}
        defense = row.get("defense") or {}
        out[team] = {
            "rating": row.get("rating"),
            "ranking": _int(row.get("ranking")),
            "offense_rating": offense.get("rating"),
            "defense_rating": defense.get("rating"),
        }
    return out


def normalize_returning_production(raw_rows: list[dict]) -> dict[str, dict[str, Any]]:
    """CFBD `/player/returning` rows → {canonical_team: {overall, usage, ...}}.

    A Phase-2 roster-continuity preseason prior (D10). `overall` = `percentPPA`, the
    standard returning-production fraction (share of last year's PPA returning); the
    sub-splits are kept for explainability. Preseason this endpoint is often empty
    (like SP+) — those teams simply don't appear and are recorded `missing`, never
    neutral-filled; the prior then falls back to flat baseline with max uncertainty."""
    out: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        team = _norm(row.get("team"))
        if team is None:
            continue
        out[team] = {
            "overall": _float(row.get("percentPPA")),
            "usage": _float(row.get("usage")),
            "passing": _float(row.get("percentPassingPPA")),
            "rushing": _float(row.get("percentRushingPPA")),
            "receiving": _float(row.get("percentReceivingPPA")),
        }
    return out


def normalize_venue(location: dict | None) -> Venue:
    """A CFBD team `location` object (from the registry artifact) → canonical Venue."""
    loc = location or {}
    elevation = loc.get("elevation")
    try:
        elevation = float(elevation) if elevation is not None else None
    except (TypeError, ValueError):
        elevation = None
    return Venue(
        name=loc.get("name"),
        latitude=loc.get("latitude"),
        longitude=loc.get("longitude"),
        elevation=elevation,
        timezone=loc.get("timezone"),
        dome=bool(loc.get("dome", False)),
    )


def normalize_coaching(raw_coaches: list[dict], year: int) -> dict[str, Coaching]:
    """CFBD `/coaches` rows → {canonical_team: Coaching} for the head coach in `year`.

    Each coach row carries a `seasons[]` history. For a team we pick the coach whose
    `year` season is at that team; `head_coach_experience` = total seasons coached
    (across schools), `tenure_years` = trailing consecutive seasons at THIS school
    ending in `year`. Teams with no `year` season resolve to no entry (recorded
    `missing` by the builder) — never a fabricated default.
    """
    out: dict[str, Coaching] = {}
    for coach in raw_coaches:
        seasons = coach.get("seasons") or []
        for season in seasons:
            if _int(season.get("year")) != year:
                continue
            team = _norm(season.get("school"))
            if team is None:
                continue
            name_parts = [coach.get("firstName"), coach.get("lastName")]
            head_coach_name = " ".join(p for p in name_parts if p) or None
            tenure = _tenure_at(seasons, season.get("school"), year)
            out[team] = Coaching(
                head_coach_name=head_coach_name,
                head_coach_experience=len(seasons),
                tenure_years=tenure,
                status="cfbd",
            )
    return out


def _tenure_at(seasons: list[dict], school: str | None, year: int) -> int:
    """Trailing consecutive seasons at `school` ending at `year`."""
    if not school:
        return 0
    years_at_school = {
        _int(s.get("year")) for s in seasons if s.get("school") == school
    }
    tenure = 0
    y = year
    while y in years_at_school:
        tenure += 1
        y -= 1
    return tenure
