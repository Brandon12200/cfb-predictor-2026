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
from data.schedule_intel import compute_schedule_intel
from data.snapshot.lines import record_observation
from data.snapshot.store import compute_snapshot_id, write_snapshot

logger = logging.getLogger(__name__)

# Per-team field-groups the manifest accounts for (100% coverage).
_TEAM_FIELD_GROUPS = ("info", "coaching", "stats", "schedule", "advanced_stats",
                      "venue", "sp_rating", "returning_production")


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
        # `excluded_*` collect what did NOT survive normalization, with a reason each. They feed
        # the manifest's reconciliation block — never `data` — so they cannot move `snapshot_id`.
        excluded_games: list[dict] = []
        excluded_odds: list[dict] = []

        raw_games = self._fetch("games", lambda: self.cfbd.get_games(year), sources)
        games = cfbd.normalize_games(raw_games or [], excluded=excluded_games)

        raw_adv = self._fetch("advanced_stats",
                              lambda: self.cfbd.get_advanced_season_stats(year), sources)
        advanced = cfbd.normalize_advanced_stats(raw_adv or [])

        raw_coaches = self._fetch("coaching", lambda: self.cfbd.get_coaches(year), sources)
        coaching = cfbd.normalize_coaching(raw_coaches or [], year)

        raw_season = self._fetch("season_stats",
                                 lambda: self.cfbd.get_season_stats(year), sources)
        season_stat_teams = _teams_with_season_stats(raw_season or [])

        raw_sp = self._fetch("sp_ratings", lambda: self.cfbd.get_sp_ratings(year), sources)
        sp_ratings = cfbd.normalize_sp_ratings(raw_sp or [])

        raw_rp = self._fetch("returning_production",
                             lambda: self.cfbd.get_returning_production(year), sources)
        returning_production = cfbd.normalize_returning_production(raw_rp or [])

        raw_odds = self._fetch("betting_lines",
                               lambda: self.odds.get_ncaaf_spreads(), sources)
        lines = odds_norm.normalize_lines(raw_odds or [], sources["betting_lines"]["fetched_at"],
                                          excluded=excluded_odds)
        sources["betting_lines"]["quota"] = getattr(self.odds, "last_quota", None)
        sources["registry"] = {"source": "cfbd",
                               "fetched_at": self.registry.provenance.get("fetched_at")}

        # 4. Assemble per-team canonical data + coverage.
        tracked = sorted(self.registry.get_all_tracked_teams())
        teams_data: dict[str, dict] = {}
        team_coverage: dict[str, dict[str, str]] = {}
        venues: dict[str, dict] = {}
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
            venue = self.registry.get_venue(team)
            if venue is not None:
                venues[team] = asdict(venue)
            team_coverage[team] = {
                "info": "cfbd",
                "coaching": "cfbd" if team in coaching else "missing",
                "stats": "cfbd" if team in season_stat_teams else "missing",
                "schedule": "cfbd" if schedule_ok else "missing",
                "advanced_stats": "cfbd" if team in advanced else "missing",
                "venue": "registry" if team in venues else "missing",
                "sp_rating": "cfbd" if team in sp_ratings else "missing",
                "returning_production": "cfbd" if team in returning_production else "missing",
            }

        # 5. Slate games: betting-line + schedule-intel coverage (both teams tracked).
        tracked_set = set(tracked)
        games_dicts = [asdict(g) for g in games]
        betting: dict[str, dict] = {}
        slate_lines: dict[str, dict] = {}  # full GameLines for the append-only store
        schedule_intel: dict[str, dict] = {}
        game_coverage: dict[str, dict[str, str]] = {}
        out_of_scope: list[dict] = []
        for g in games:
            if g.week != week or g.home_team not in tracked_set or g.away_team not in tracked_set:
                # Scope filtering is a legitimate exclusion, but SPEC §5.5.3 requires it be
                # visible: only this week's games, and only tracked-vs-tracked, reach the slate.
                if g.week == week:
                    untracked = sorted({t for t in (g.home_team, g.away_team)
                                        if t not in tracked_set})
                    out_of_scope.append({"home": g.home_team, "away": g.away_team,
                                         "week": g.week, "reason": "not_tracked",
                                         "untracked": untracked})
                continue
            key = f"{g.away_team}@{g.home_team}"
            gl = lines.get((g.home_team, g.away_team))
            if gl is not None and gl.observations:
                # The snapshot freezes ONLY the prediction-time observation (in the hash);
                # the full series goes to the append-only store, not snapshot.json.
                obs = asdict(gl.observations[0])
                betting[key] = {"home_team": g.home_team, "away_team": g.away_team,
                                "kickoff": gl.kickoff, "observation": obs,
                                "vegas_spread": obs["consensus_spread"]}
                slate_lines[key] = asdict(gl)
                game_coverage[key] = {"betting_lines": "odds"}
            else:
                betting[key] = {"home_team": g.home_team, "away_team": g.away_team,
                                "kickoff": None, "observation": None, "vegas_spread": None}
                game_coverage[key] = {"betting_lines": "missing"}
            # Schedule intel for both participants. Neutral-site games have no team
            # home venue, so their game venue (and thus travel/tz/altitude) is unknown
            # → recorded missing, not the home team's venue (which would be wrong).
            game_venue = None if g.neutral_site else venues.get(g.home_team)
            for t, opp, is_home in ((g.home_team, g.away_team, True),
                                    (g.away_team, g.home_team, False)):
                schedule_intel[t] = compute_schedule_intel(
                    t, opp, week, g.start_date, is_home, game_venue,
                    games_dicts, venues, sp_ratings)
            # Honest coverage: the physical intel resolves only with venue coordinates.
            has_geo = bool(game_venue and game_venue.get("latitude") is not None)
            game_coverage[key]["schedule_intel"] = "derived" if has_geo else "missing"

        data = {
            "teams": teams_data,
            "games": games_dicts,
            "advanced_stats": {t: asdict(a) for t, a in advanced.items()},
            "sp_ratings": sp_ratings,
            "returning_production": returning_production,
            "venues": venues,
            "schedule_intel": schedule_intel,
            "betting_lines": betting,
        }
        snapshot_id = compute_snapshot_id(data)
        built_at = self.clock()
        meta = {"snapshot_id": snapshot_id, "week": week, "year": year, "built_at": built_at}

        # Built AFTER compute_snapshot_id, and stored in the manifest rather than in `data` — so
        # the reconciliation record provably cannot move `snapshot_id`, the schema-v2 golden or the
        # behavioural fingerprint. That ordering is the whole reason this is safe to add
        # post-freeze; it is pinned by a test.
        reconciliation = self._reconcile(
            week, raw_games or [], games, betting, lines,
            excluded_games, excluded_odds, out_of_scope)

        manifest = self._manifest(meta, sources, team_coverage, game_coverage,
                                  calendar_warnings, reconciliation)
        write_snapshot(week, {"meta": meta, "data": data}, manifest, year=year,
                       base=self.base_dir)
        # Seed the append-only line-observation store (observation #1). This is OUTSIDE
        # the snapshot hash — it does not affect snapshot_id or rerun reproducibility.
        if slate_lines:
            record_observation(week, slate_lines, year=year, base=self.base_dir)
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

    def _reconcile(self, week: int, raw_games: list[dict], games: list,
                   betting: dict, lines: dict, excluded_games: list[dict],
                   excluded_odds: list[dict], out_of_scope: list[dict]) -> dict[str, Any]:
        """The weekly slate reconciliation (SPEC §5.5.3): every game excluded, WITH its reason.

        The rule this implements is "a game can be excluded, but never invisibly". Before it, a
        CFBD row that failed name resolution and a row correctly filtered as FBS-vs-FCS both just
        `continue`d, so an FBS game lost to an unresolved alias was indistinguishable from working
        as designed — and the code comments claimed a "slate reconciler" that did not exist.

        Cross-references the two sources both ways, which is the half §5.5.3 asks for and nothing
        provided: Odds events that match no tracked slate game, and slate games with no line.
        """
        by_reason: dict[str, list[dict]] = {}
        for row in excluded_games:
            by_reason.setdefault(row["reason"], []).append(row)

        slate_pairs = {(g["home_team"], g["away_team"]) for g in betting.values()}
        odds_pairs = set(lines.keys())
        unmatched_odds = sorted(f"{a}@{h}" for h, a in odds_pairs - slate_pairs)
        no_line = sorted(k for k, v in betting.items() if v.get("observation") is None)

        return {
            "cfbd_rows_fetched": len(raw_games),
            "games_normalized": len(games),
            "excluded_from_normalization": {
                "total": len(excluded_games),
                "by_reason": {r: len(v) for r, v in sorted(by_reason.items())},
                # The defect class is listed game-by-game; the in-scope-by-design class is counted
                # only, because 150+ FCS rows a week would bury the thing worth reading.
                "unresolved_team_name": sorted(
                    f"{r['away']}@{r['home']}" for r in by_reason.get("unresolved_team_name", [])),
            },
            "week_slate": {
                "week": week,
                "tracked_games": len(betting),
                "out_of_scope": len(out_of_scope),
                "out_of_scope_games": sorted(f"{r['away']}@{r['home']}" for r in out_of_scope),
            },
            "odds_cross_reference": {
                "events_normalized": len(lines),
                "excluded_events": len(excluded_odds),
                "unresolved_events": sorted(
                    f"{r['away']}@{r['home']}" for r in excluded_odds),
                "matched_to_slate": len(slate_pairs & odds_pairs),
                "unmatched_odds_events": unmatched_odds,
                "slate_games_without_a_line": no_line,
            },
        }

    def _manifest(self, meta: dict, sources: dict, team_coverage: dict,
                  game_coverage: dict, calendar_warnings: list[str],
                  reconciliation: dict[str, Any] | None = None) -> dict[str, Any]:
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
            "reconciliation": reconciliation or {},
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
