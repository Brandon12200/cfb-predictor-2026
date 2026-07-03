"""Snapshot builder (SPEC §5.2) — the ONLY place fallback policy lives.

For a week it: (1) runs registry validation (hard-fail on membership drift, warn on
calendar divergence — the 1a→1b baton, SPEC §5.5.2); (2) fetches league-wide from
CFBD + Odds; (3) normalizes to canonical dataclasses; (4) applies `CFBD → [ESPN
staged] → declared-missing` — a source that raises is recorded `missing` with a
`fallback_reason`, never neutral-filled; (5) writes the bundle + a provenance
manifest covering 100% of fields. ESPN fallback is staged (later slice): fields CFBD
can't supply are honestly `missing`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data.normalize import cfbd
from data.normalize import odds as odds_norm
from data.normalize.models import (
    Coaching,
    TeamData,
    TeamInfo,
    compute_derived_metrics,
)
from data.snapshot.store import compute_snapshot_id, write_snapshot

logger = logging.getLogger(__name__)

# Per-team field-groups the manifest accounts for (100% coverage).
_TEAM_FIELD_GROUPS = ("info", "coaching", "stats", "schedule", "advanced_stats")


class SnapshotBuilder:
    """Builds a week's snapshot from injected clients + the season registry."""

    def __init__(self, cfbd_client: Any, odds_client: Any, registry: Any,
                 clock: Callable[[], str] | None = None, base_dir: Path | None = None):
        self.cfbd = cfbd_client
        self.odds = odds_client
        self.registry = registry
        self.clock = clock or (lambda: datetime.now(UTC).isoformat())
        self.base_dir = base_dir

    def build(self, week: int, year: int = 2026) -> dict[str, Any]:
        # 1. Registry validation at build time (SPEC §5.5.2). Membership drift is a
        #    structural error → abort; calendar divergence is a loud warning.
        self.registry.validate_membership_counts()
        calendar_warnings = self.registry.corroborate_calendar()

        sources: dict[str, Any] = {}

        # 2-3. Fetch + normalize each league-wide group; a raising source degrades to
        #      missing (recorded), it does not abort the build.
        raw_games = self._fetch("games", lambda: self.cfbd.get_games(year), sources)
        games = cfbd.normalize_games(raw_games or [])

        raw_adv = self._fetch("advanced_stats",
                              lambda: self.cfbd.get_advanced_season_stats(year), sources)
        advanced = cfbd.normalize_advanced_stats(raw_adv or [])

        raw_coaches = self._fetch("coaching", lambda: self.cfbd.get_coaches(year), sources)
        coaching = cfbd.normalize_coaching(raw_coaches or [], year)

        raw_season = self._fetch("season_stats",
                                 lambda: self.cfbd.get_season_stats(year), sources)
        season_stat_teams = _teams_with_season_stats(raw_season or [])

        raw_odds = self._fetch("betting_lines",
                               lambda: self.odds.get_ncaaf_spreads(), sources)
        lines = odds_norm.normalize_lines(raw_odds or [])
        sources["betting_lines"]["quota"] = getattr(self.odds, "last_quota", None)
        sources["registry"] = {"source": "cfbd",
                               "fetched_at": self.registry.provenance.get("fetched_at")}

        # 4. Assemble per-team canonical data + coverage.
        tracked = sorted(self.registry.get_all_tracked_teams())
        teams_data: dict[str, dict] = {}
        team_coverage: dict[str, dict[str, str]] = {}
        schedule_ok = sources["games"]["source"] is not None
        for team in tracked:
            schedule = cfbd.team_schedule(games, team)
            td = TeamData(
                team_name=team,
                info=TeamInfo(status="cfbd", conference=self.registry.get_team_conference(team)),
                coaching=coaching.get(team, Coaching()),
                stats={"status": "cfbd" if team in season_stat_teams else None},
                schedule=schedule,
                derived_metrics=compute_derived_metrics(schedule),
            )
            teams_data[team] = td.to_dict()
            team_coverage[team] = {
                "info": "cfbd",
                "coaching": "cfbd" if team in coaching else "missing",
                "stats": "cfbd" if team in season_stat_teams else "missing",
                "schedule": "cfbd" if schedule_ok else "missing",
                "advanced_stats": "cfbd" if team in advanced else "missing",
            }

        # 5. Slate games + betting-line coverage (both teams tracked, this week).
        tracked_set = set(tracked)
        betting: dict[str, dict] = {}
        game_coverage: dict[str, dict[str, str]] = {}
        for g in games:
            if g.week != week or g.home_team not in tracked_set or g.away_team not in tracked_set:
                continue
            key = f"{g.away_team}@{g.home_team}"
            gl = lines.get((g.home_team, g.away_team))
            if gl is not None:
                betting[key] = {**_gamelines_dict(gl),
                                "vegas_spread": odds_norm.consensus_spread(gl)}
                game_coverage[key] = {"betting_lines": "odds"}
            else:
                betting[key] = {"home_team": g.home_team, "away_team": g.away_team,
                                "lines": [], "vegas_spread": None}
                game_coverage[key] = {"betting_lines": "missing"}

        data = {
            "teams": teams_data,
            "games": [asdict(g) for g in games],
            "advanced_stats": {t: asdict(a) for t, a in advanced.items()},
            "betting_lines": betting,
        }
        snapshot_id = compute_snapshot_id(data)
        built_at = self.clock()
        meta = {"snapshot_id": snapshot_id, "week": week, "year": year, "built_at": built_at}

        manifest = self._manifest(meta, sources, team_coverage, game_coverage,
                                  calendar_warnings)
        write_snapshot(week, {"meta": meta, "data": data}, manifest, year=year,
                       base=self.base_dir)
        logger.info("Built snapshot %s (week %d): %d teams, %d slate games, coverage %.1f%%",
                    snapshot_id, week, len(tracked), len(betting),
                    manifest["summary"]["coverage_pct"])
        return manifest

    # -- helpers --------------------------------------------------------------
    def _fetch(self, group: str, call: Callable[[], list], sources: dict) -> list | None:
        """Run a fetch; on failure record the group `missing` with a reason (the
        CFBD→ESPN→missing chain, ESPN staged) rather than aborting the build."""
        fetched_at = self.clock()
        try:
            result = call()
            sources[group] = {"source": _source_of(group), "fetched_at": fetched_at,
                              "count": len(result), "fallback_reason": None}
            return result
        except Exception as exc:  # noqa: BLE001 — degrade to missing, don't crash
            logger.warning("Snapshot fetch for %s failed, recording missing: %s", group, exc)
            sources[group] = {"source": None, "fetched_at": fetched_at, "count": 0,
                              "fallback_reason": f"{type(exc).__name__}: {exc}"}
            return None

    def _manifest(self, meta: dict, sources: dict, team_coverage: dict,
                  game_coverage: dict, calendar_warnings: list[str]) -> dict[str, Any]:
        present = missing = 0
        for cov in team_coverage.values():
            for v in cov.values():
                present += v != "missing"
                missing += v == "missing"
        for cov in game_coverage.values():
            for v in cov.values():
                present += v != "missing"
                missing += v == "missing"
        total = present + missing
        return {
            "meta": meta,
            "sources": sources,
            "coverage": {"teams": team_coverage, "games": game_coverage},
            "calendar_warnings": calendar_warnings,
            "summary": {
                "teams": len(team_coverage),
                "slate_games": len(game_coverage),
                "fields_total": total,
                "fields_present": present,
                "fields_missing": missing,
                "coverage_pct": round(100.0 * present / total, 1) if total else 100.0,
            },
        }


def _source_of(group: str) -> str:
    return "odds" if group == "betting_lines" else "cfbd"


def _teams_with_season_stats(raw_season: list[dict]) -> set[str]:
    teams: set[str] = set()
    for row in raw_season:
        name = cfbd._norm(row.get("team"))
        if name:
            teams.add(name)
    return teams


def _gamelines_dict(gl: Any) -> dict[str, Any]:
    return {"home_team": gl.home_team, "away_team": gl.away_team,
            "lines": [asdict(ln) for ln in gl.lines]}
