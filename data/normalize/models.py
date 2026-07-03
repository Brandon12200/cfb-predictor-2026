"""Canonical typed schema for the data layer (SPEC §5.2, docs/SCHEMA.md §1-3).

Stdlib dataclasses (minimal-deps policy). These model exactly what the engine and
factors consume; `GameContext.to_context_dict()` renders the factor-facing context
dict with the same keys/types `data_manager.get_game_context` produced before 1b,
so the snapshot→context adapter is a straight projection (enforced by the
context-shape parity test).

**No neutral fabrication.** Fields that a source did not supply are `None` here and
recorded `missing` in the provenance manifest — distinguishable from a real value.
Factors may still apply their own defensive defaults at calculation time (e.g.
`head_coach_experience` → 5); that is a documented factor behavior, not fabricated
snapshot data, and the honest `data_quality`/manifest reflect the absence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# --- team schedule (completed-game results the momentum/desperation factors read) ---
@dataclass
class TeamScheduleResult:
    """One completed/scheduled game from a team's own perspective (SCHEMA §1)."""
    completed: bool
    date: str | None = None
    result: str | None = None  # 'W' / 'L'
    team_score: int | None = None
    opponent_score: int | None = None
    is_home_game: bool = False


@dataclass
class CurrentRecord:
    wins: int
    losses: int
    win_percentage: float


@dataclass
class VenueRecord:
    wins: int
    losses: int
    total_games: int
    win_percentage: float


@dataclass
class VenuePerformance:
    home_record: VenueRecord
    away_record: VenueRecord


@dataclass
class DerivedMetrics:
    """Computed from a team's completed schedule (SCHEMA §1)."""
    current_record: CurrentRecord | None = None
    venue_performance: VenuePerformance | None = None


@dataclass
class TeamInfo:
    """Basic team info the engine reads (`status`, `conference.name`)."""
    status: str | None = None
    conference: str | None = None  # canonical conference key, or None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "conference": {"name": self.conference}}


@dataclass
class Coaching:
    """Head-coach info (SCHEMA §1). None = not supplied (recorded missing)."""
    head_coach_name: str | None = None
    head_coach_experience: int | None = None
    tenure_years: int | None = None
    status: str | None = None


@dataclass
class TeamData:
    """Per-team context block (SCHEMA §1). `info`/`stats`/`coaching` open where the
    content is source-varied; the read fields are typed."""
    team_name: str
    info: TeamInfo = field(default_factory=TeamInfo)
    coaching: Coaching = field(default_factory=Coaching)
    stats: dict[str, Any] = field(default_factory=lambda: {"status": None})
    schedule: list[TeamScheduleResult] = field(default_factory=list)
    derived_metrics: DerivedMetrics = field(default_factory=DerivedMetrics)
    is_home: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_name": self.team_name,
            "info": self.info.to_dict(),
            "coaching": asdict(self.coaching),
            "stats": dict(self.stats),
            "schedule": [asdict(g) for g in self.schedule],
            "derived_metrics": _derived_to_dict(self.derived_metrics),
            "is_home": self.is_home,
        }


@dataclass
class CoachingComparison:
    home_team: str
    away_team: str
    home_coaching: Coaching = field(default_factory=Coaching)
    away_coaching: Coaching = field(default_factory=Coaching)
    experience_differential: float | None = None
    head_to_head_record: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_coaching": asdict(self.home_coaching),
            "away_coaching": asdict(self.away_coaching),
            "experience_differential": self.experience_differential,
            "head_to_head_record": dict(self.head_to_head_record),
        }


# --- out-of-band datasets the 3 network-bypassing factors consume (SCHEMA §1) ---
@dataclass
class ScheduleGame:
    """A season game (league-wide), for `scheduling_fatigue`. Canonical snake_case."""
    week: int
    home_team: str
    away_team: str
    home_points: int | None = None
    away_points: int | None = None
    start_date: str | None = None
    completed: bool = False


@dataclass
class AdvancedStats:
    """Advanced season stats for one team (`style_mismatch`). Offense/defense are
    open dicts of the CFBD metric fields (successRate, explosiveness, ppa, havoc…)."""
    team: str
    offense: dict[str, Any] = field(default_factory=dict)
    defense: dict[str, Any] = field(default_factory=dict)


@dataclass
class BookLine:
    """One book's line for a game (`market_sentiment`)."""
    provider: str
    spread: float | None = None
    spread_open: float | None = None


@dataclass
class GameLines:
    """All book lines for one game (`market_sentiment`). Line-movement history is
    `missing` in core Phase 1 (D6/SCHEMA §4) — only current + opening are present."""
    home_team: str
    away_team: str
    lines: list[BookLine] = field(default_factory=list)


@dataclass
class Venue:
    """Stadium geo/altitude for schedule-intelligence (1c). From the registry artifact."""
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    timezone: str | None = None
    dome: bool = False


@dataclass
class GameContext:
    """Top-level context the engine feeds factors (SCHEMA §1). `to_context_dict()`
    is the factor-facing projection; `snapshot_id`/`data_quality_report` are new in
    v2 and additive (old keys preserved for parity)."""
    home_team: str
    away_team: str
    week: int | None
    year: int
    vegas_spread: float | None
    has_betting_data: bool
    home_team_data: TeamData
    away_team_data: TeamData
    coaching_comparison: CoachingComparison
    data_quality: float
    timestamp: str
    snapshot_id: str | None = None
    data_sources: list[str] = field(default_factory=list)
    data_quality_report: dict[str, Any] = field(default_factory=dict)

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "week": self.week,
            "year": self.year,
            "timestamp": self.timestamp,
            "data_sources": list(self.data_sources),
            "vegas_spread": self.vegas_spread,
            "has_betting_data": self.has_betting_data,
            "home_team_data": self.home_team_data.to_dict(),
            "away_team_data": self.away_team_data.to_dict(),
            "coaching_comparison": self.coaching_comparison.to_dict(),
            "data_quality": self.data_quality,
            "data_quality_report": dict(self.data_quality_report),
            "snapshot_id": self.snapshot_id,
        }


def _derived_to_dict(dm: DerivedMetrics) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if dm.current_record is not None:
        out["current_record"] = asdict(dm.current_record)
    if dm.venue_performance is not None:
        out["venue_performance"] = {
            "home_record": asdict(dm.venue_performance.home_record),
            "away_record": asdict(dm.venue_performance.away_record),
        }
    return out


def compute_derived_metrics(schedule: list[TeamScheduleResult]) -> DerivedMetrics:
    """Current record + home/away splits from completed games (mirrors the retired
    `data_manager._calculate_derived_metrics`, but over canonical results)."""
    completed = [g for g in schedule if g.completed]
    if not completed:
        return DerivedMetrics()

    def _record(games: list[TeamScheduleResult]) -> VenueRecord:
        wins = sum(1 for g in games if g.result == "W")
        losses = sum(1 for g in games if g.result == "L")
        total = len(games)
        return VenueRecord(wins, losses, total, wins / total if total else 0.0)

    wins = sum(1 for g in completed if g.result == "W")
    losses = sum(1 for g in completed if g.result == "L")
    denom = wins + losses
    current = CurrentRecord(wins, losses, wins / denom if denom else 0.0)
    home = _record([g for g in completed if g.is_home_game])
    away = _record([g for g in completed if not g.is_home_game])
    return DerivedMetrics(current, VenuePerformance(home, away))
