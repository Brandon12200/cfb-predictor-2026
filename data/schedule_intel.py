"""Schedule-intelligence dataset (SPEC §5.4.2).

Per team-week physical/situational context — rest, bye, short week, travel distance,
time zones crossed, altitude, consecutive road games, sandwich spots. This is the
substrate for Phase 2's matchup pricer and Phase 3 factors.

`compute_schedule_intel(...)` is a **pure function** (stdlib `math`/`zoneinfo` only, no
I/O) so it serves the snapshot builder and hypothetical matchups identically. Missing
inputs (e.g. a venue without coordinates, or SP+ ratings not yet posted) yield `None`
for the affected field — recorded `missing`, never fabricated.
"""

from __future__ import annotations

from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo

_EARTH_RADIUS_MILES = 3958.7613
_RANKED_THRESHOLD = 25  # SP+ ranking that counts as a "ranked" (sandwich-spot) opponent


class _TeamGame(NamedTuple):
    """One of a team's season games, from that team's perspective (typed for clarity)."""
    week: int | None
    date: date | None
    is_home: bool
    opponent: str


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/long points."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return round(2 * _EARTH_RADIUS_MILES * asin(sqrt(a)), 1)


def _utc_offset_hours(tz_name: str | None, on: date) -> float | None:
    """UTC offset (hours) for an IANA tz on a given date (handles DST)."""
    if not tz_name:
        return None
    try:
        dt = datetime(on.year, on.month, on.day, 12, tzinfo=ZoneInfo(tz_name))
    except Exception:  # noqa: BLE001 — unknown tz name
        return None
    off = dt.utcoffset()
    return off.total_seconds() / 3600 if off is not None else None


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _coords(venue: dict | None) -> tuple[float, float] | None:
    if not venue:
        return None
    lat, lon = venue.get("latitude"), venue.get("longitude")
    return (lat, lon) if lat is not None and lon is not None else None


def compute_schedule_intel(team: str, opponent: str, game_week: int, game_date: Any,
                           is_home: bool, game_venue: dict | None,
                           season_games: list[dict], venues: dict[str, dict],
                           ratings: dict[str, dict] | None = None) -> dict[str, Any]:
    """Physical/situational intel for `team`'s week-`game_week` game. Pure — works for
    real slate games and hypothetical matchups alike. `season_games` are canonical
    `ScheduleGame` dicts (week/home_team/away_team/start_date); `venues`/`ratings` are
    `{team: dict}` maps (from the snapshot). Missing inputs → `None` for that field."""
    ratings = ratings or {}
    gdate = _to_date(game_date)

    # This team's other games (perspective: week, date, is_home, opponent).
    team_up = team.upper()
    others: list[_TeamGame] = []
    for g in season_games:
        h, a = str(g.get("home_team", "")).upper(), str(g.get("away_team", "")).upper()
        wk = g.get("week")
        if team_up not in (h, a) or wk == game_week:
            continue
        others.append(_TeamGame(week=wk, date=_to_date(g.get("start_date")),
                                is_home=h == team_up, opponent=a if h == team_up else h))
    others.sort(key=lambda x: x.week if x.week is not None else 0)
    played_weeks = {o.week for o in others}

    # Rest days: gap to the most recent prior game.
    prior = [o for o in others if o.week is not None and o.week < game_week]
    rest_days: int | None = None
    if prior and gdate is not None and prior[-1].date is not None:
        rest_days = (gdate - prior[-1].date).days

    bye = game_week > 1 and (game_week - 1) not in played_weeks
    opp_prior = _opponent_bye(opponent, game_week, season_games)

    # Travel + time zones: team's home venue → the game venue.
    home_venue = venues.get(team_up)
    travel_distance = time_zones_crossed = tz_direction = None
    hc, gc = _coords(home_venue), _coords(game_venue)
    if hc and gc:
        travel_distance = haversine_miles(hc[0], hc[1], gc[0], gc[1])
    if gdate is not None and home_venue and game_venue:
        home_off = _utc_offset_hours(home_venue.get("timezone"), gdate)
        game_off = _utc_offset_hours(game_venue.get("timezone"), gdate)
        if home_off is not None and game_off is not None:
            diff = game_off - home_off
            time_zones_crossed = round(abs(diff))
            tz_direction = "none" if diff == 0 else ("west" if diff < 0 else "east")

    altitude = game_venue.get("elevation") if game_venue else None

    return {
        "team": team,
        "opponent": opponent,
        "week": game_week,
        "is_home": is_home,
        "rest_days": rest_days,
        "short_week": (rest_days is not None and rest_days <= 6),
        "bye": bye,
        "opponent_bye": opp_prior,
        "travel_distance": travel_distance,
        "time_zones_crossed": time_zones_crossed,
        "tz_direction": tz_direction,
        "altitude": altitude,
        "consecutive_road_games": _consecutive_road(others, game_week, is_home),
        "sandwich_spot": _sandwich_spot(others, game_week, ratings),
    }


def _opponent_bye(opponent: str, game_week: int, season_games: list[dict]) -> bool:
    opp_up = opponent.upper()
    weeks = {g.get("week") for g in season_games
             if opp_up in (str(g.get("home_team", "")).upper(), str(g.get("away_team", "")).upper())}
    return game_week > 1 and (game_week - 1) not in weeks


def _consecutive_road(others: list[_TeamGame], game_week: int, is_home: bool) -> int:
    """Consecutive road games ending with this one (0 if this game is at home). Counts
    prior road games regardless of bye weeks between them (a bye does not reset the
    streak — road trips separated by an off week still accumulate travel/fatigue)."""
    if is_home:
        return 0
    prior = sorted((o for o in others if o.week is not None and o.week < game_week),
                   key=lambda x: x.week, reverse=True)  # type: ignore[arg-type,return-value]
    count = 1
    for o in prior:
        if o.is_home:
            break
        count += 1
    return count


def _sandwich_spot(others: list[_TeamGame], game_week: int,
                   ratings: dict[str, dict]) -> bool | None:
    """True if a ranked (top-25 SP+) opponent sits in the adjacent week (potential
    letdown/look-ahead). None if the adjacent opponents' strength is unknown."""
    adjacent = [o for o in others if o.week in (game_week - 1, game_week + 1)]
    if not adjacent:
        return False
    known = False
    for o in adjacent:
        rank = (ratings.get(o.opponent.upper()) or {}).get("ranking")
        if rank is not None:
            known = True
            if rank <= _RANKED_THRESHOLD:
                return True
    return False if known else None
