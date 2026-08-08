"""Odds API source-native → canonical converters (layer 2).

Raw Odds events → canonical `GameLines`, resolving team names through the
normalizer and computing the consensus home spread (the load-bearing `vegas_spread`).
Line-movement history is out of scope for core Phase 1 (D6/SCHEMA §4): only the
current book spreads (+ opening where present) are carried; movement is `missing`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from data.normalize.models import BookLine, GameLines, LineObservation
from utils.normalizer import normalizer


def _norm(name: str | None) -> str | None:
    return normalizer.normalize(name) if name else None


def _home_point(bookmaker: dict, home_raw: str) -> float | None:
    """The spread `point` for the home team from one bookmaker's `spreads` market."""
    for market in bookmaker.get("markets", []):
        if market.get("key") != "spreads":
            continue
        for outcome in market.get("outcomes", []):
            if outcome.get("name") == home_raw:
                pt = outcome.get("point")
                try:
                    return float(pt)
                except (TypeError, ValueError):
                    return None
    return None


def normalize_lines(raw_events: list[dict], fetched_at: str,
                    excluded: list[dict] | None = None) -> dict[tuple[str, str], GameLines]:
    """Raw Odds events → {(home, away) canonical: GameLines} with a single "as-of T"
    observation stamped `fetched_at` and the game's `kickoff` (`commence_time`).

    Pass ``excluded`` to collect the events whose team names did not resolve, each with a reason —
    an Odds event we cannot map is a game we may be pricing blind, so it is surfaced rather than
    skipped silently (SPEC §5.5.3/§5.5.4).
    """
    out: dict[tuple[str, str], GameLines] = {}
    for event in raw_events:
        home_raw = event.get("home_team", "")
        away_raw = event.get("away_team", "")
        home = _norm(home_raw)
        away = _norm(away_raw)
        if home is None or away is None:
            if excluded is not None:
                from data.normalize.cfbd import WEEK_NOT_APPLICABLE, classify_drop
                # Odds events carry no week, so the shared classifier is told the week is not
                # applicable rather than being handed a real-looking 0 it would have to guess at.
                excluded.append({
                    "home": home_raw, "away": away_raw, "week": None,
                    "reason": classify_drop(home_raw, away_raw, home, away, WEEK_NOT_APPLICABLE),
                })
            continue
        lines: list[BookLine] = []
        for bm in event.get("bookmakers", []):
            point = _home_point(bm, home_raw)
            if point is None:
                continue
            lines.append(BookLine(provider=bm.get("key", "unknown"), spread=point))
        points = [ln.spread for ln in lines if ln.spread is not None]
        obs = LineObservation(fetched_at=fetched_at, lines=lines,
                              consensus_spread=round(mean(points), 1) if points else None)
        out[(home, away)] = GameLines(home_team=home, away_team=away,
                                      kickoff=event.get("commence_time"), observations=[obs])
    return out


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO timestamp (accepting a trailing `Z`) to an aware datetime, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def closing_observation(game_entry: dict[str, Any]) -> dict[str, Any] | None:
    """The closing line = the last observation taken at-or-before the game's kickoff
    (SPEC §5.4.3, for CLV). Falls back to the latest observation if none precede kickoff.
    Compares parsed datetimes (robust to `Z` vs `+00:00`), not raw strings."""
    observations = game_entry.get("observations") or []
    if not observations:
        return None
    kickoff = _parse_dt(game_entry.get("kickoff"))
    _floor = datetime.min.replace(tzinfo=UTC)
    before = [o for o in observations
              if kickoff is None or (_parse_dt(o.get("fetched_at")) or _floor) <= kickoff]
    pool = before or observations
    return max(pool, key=lambda o: _parse_dt(o.get("fetched_at")) or _floor)
