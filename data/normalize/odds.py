"""Odds API source-native → canonical converters (layer 2).

Raw Odds events → canonical `GameLines`, resolving team names through the
normalizer and computing the consensus home spread (the load-bearing `vegas_spread`).
Line-movement history is out of scope for core Phase 1 (D6/SCHEMA §4): only the
current book spreads (+ opening where present) are carried; movement is `missing`.
"""

from __future__ import annotations

from statistics import mean

from data.normalize.models import BookLine, GameLines
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


def normalize_lines(raw_events: list[dict]) -> dict[tuple[str, str], GameLines]:
    """Raw Odds events → {(home, away) canonical: GameLines}. Unresolved/FCS games
    are skipped (the slate reconciler logs coverage gaps)."""
    out: dict[tuple[str, str], GameLines] = {}
    for event in raw_events:
        home_raw = event.get("home_team", "")
        away_raw = event.get("away_team", "")
        home = _norm(home_raw)
        away = _norm(away_raw)
        if home is None or away is None:
            continue
        lines: list[BookLine] = []
        for bm in event.get("bookmakers", []):
            point = _home_point(bm, home_raw)
            if point is None:
                continue
            lines.append(BookLine(provider=bm.get("key", "unknown"), spread=point))
        out[(home, away)] = GameLines(home_team=home, away_team=away, lines=lines)
    return out


def consensus_spread(game_lines: GameLines) -> float | None:
    """Consensus home spread across books (the `vegas_spread` gate). None if no book
    posted a spread — recorded `missing`, never fabricated as 0."""
    points = [ln.spread for ln in game_lines.lines if ln.spread is not None]
    return round(mean(points), 1) if points else None
