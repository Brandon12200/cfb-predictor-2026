"""Unified data manager — assembles game context from the versioned snapshot (SPEC §5.2).

Post-1b this reads ONLY the weekly snapshot bundle (`data/snapshots/YYYY_week_NN/`):
no live fetch at prediction time, no `safe_api_call`, no neutral fabrication. A field
a source did not supply is `None`/absent and *lowers* `data_quality` — it is never
replaced with a made-up value, so the owner can always tell a real number from a gap.
The engine reads context only through here and passes a no-network test.

Diagnostic helpers (`test_all_connections`, `validate_data_availability`) still touch
clients, but they are never on the prediction path.
"""

import logging
from typing import Any

from config import config
from data.cache_manager import cache_manager
from data.normalize.models import TeamData
from data.snapshot.store import SnapshotNotFoundError, load_snapshot
from utils.normalizer import normalizer

# Relative weights for the honest, presence-based data-quality score. Missing
# coaching/stats (e.g. preseason) genuinely lower the score — no neutral masking.
_QUALITY_WEIGHTS = {
    "betting_line": 1.5,
    "home_info": 1.0, "away_info": 1.0,
    "home_coaching": 0.75, "away_coaching": 0.75,
    "home_stats": 0.5, "away_stats": 0.5,
}

_H2H_PLACEHOLDER = {
    "home_wins": 0, "away_wins": 0, "total_games": 0,
    "note": "Historical coaching H2H not yet implemented",
}


class DataManager:
    """Assembles the factor-facing game context from a snapshot bundle."""

    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.logger = logging.getLogger(__name__)
        self.cache = cache_manager
        self.normalizer = normalizer
        # Clients are constructed lazily and ONLY for diagnostics — never used to
        # assemble context (that comes from the snapshot).
        self._odds_client = None
        self._espn_client = None
        self._cfbd_client = None

    # -- context assembly (snapshot-only) -------------------------------------
    def get_game_context(self, home_team: str, away_team: str, week: int | None = None,
                         year: int = 2026, snapshot: dict | None = None) -> dict[str, Any]:
        """Assemble game context for a matchup from the week's snapshot.

        Pass `snapshot` (a loaded bundle) to run against an in-memory bundle — used by
        the no-network test and `predict rerun`; otherwise the bundle is loaded from
        disk. Raises `SnapshotNotFoundError` if no snapshot exists (no live fallback).
        """
        home = self.normalizer.normalize(home_team) or home_team
        away = self.normalizer.normalize(away_team) or away_team

        if snapshot is not None:
            snap = snapshot
        elif week is None:
            raise SnapshotNotFoundError(
                "get_game_context requires a week to locate the snapshot bundle.")
        else:
            snap = load_snapshot(week, year)
        data = snap["data"]
        meta = snap["meta"]

        home_data = {**(data["teams"].get(home) or self._empty_team(home)), "is_home": True}
        away_data = {**(data["teams"].get(away) or self._empty_team(away)), "is_home": False}

        line = data["betting_lines"].get(f"{away}@{home}", {})
        vegas_spread = line.get("vegas_spread")

        context: dict[str, Any] = {
            "home_team": home,
            "away_team": away,
            "week": week,
            "year": year,
            # Frozen from the snapshot's build time → reproducible reruns (SCHEMA §3).
            "timestamp": meta.get("built_at"),
            "snapshot_id": meta.get("snapshot_id"),
            "data_sources": ["snapshot"],
            "vegas_spread": vegas_spread,
            "has_betting_data": vegas_spread is not None,
            "home_team_data": home_data,
            "away_team_data": away_data,
            "coaching_comparison": self._coaching_comparison(home, away, home_data, away_data),
            # Out-of-band datasets the 3 (formerly live-fetching) factors read from context.
            "games": data.get("games", []),
            "advanced_stats": data.get("advanced_stats", {}),
            "betting_lines": data.get("betting_lines", {}),
        }
        report = self._data_quality_report(context)
        context["data_quality"] = report["score"]
        context["data_quality_report"] = report
        return context

    def _empty_team(self, team: str) -> dict[str, Any]:
        """A tracked team absent from the snapshot — everything honestly missing."""
        return TeamData(team_name=team).to_dict()

    def _coaching_comparison(self, home: str, away: str, home_data: dict,
                             away_data: dict) -> dict[str, Any]:
        hc = home_data.get("coaching", {})
        ac = away_data.get("coaching", {})
        he, ae = hc.get("head_coach_experience"), ac.get("head_coach_experience")
        diff = (he - ae) if (he is not None and ae is not None) else None
        return {
            "home_team": home, "away_team": away,
            "home_coaching": hc, "away_coaching": ac,
            "experience_differential": diff,
            "head_to_head_record": dict(_H2H_PLACEHOLDER),
        }

    def _data_quality_report(self, context: dict) -> dict[str, Any]:
        """Itemized, honest data-quality report + a derived scalar `score` (0-1).

        Presence is read straight from the assembled context — a `status` of `None`
        (nothing supplied) counts as missing. Replaces the single percentage that
        used to read 1.0 even when every field was neutral-filled (SPEC §5.1)."""
        home, away = context["home_team_data"], context["away_team_data"]
        checks = {
            "betting_line": context["vegas_spread"] is not None,
            "home_info": _present(home.get("info", {}).get("status")),
            "away_info": _present(away.get("info", {}).get("status")),
            "home_coaching": _present(home.get("coaching", {}).get("status")),
            "away_coaching": _present(away.get("coaching", {}).get("status")),
            "home_stats": _present(home.get("stats", {}).get("status")),
            "away_stats": _present(away.get("stats", {}).get("status")),
        }
        present = sum(_QUALITY_WEIGHTS[k] for k, ok in checks.items() if ok)
        total = sum(_QUALITY_WEIGHTS.values())
        return {
            "score": round(present / total, 3),
            "checks": checks,
            "missing_fields": sorted(k for k, ok in checks.items() if not ok),
            "snapshot_id": context.get("snapshot_id"),
        }

    # -- diagnostics (never on the prediction path) ---------------------------
    @property
    def odds_client(self):
        if self._odds_client is None and self.config.odds_api_key:
            from data.odds_client import OddsAPIClient
            self._odds_client = OddsAPIClient(self.config.odds_api_key)
        return self._odds_client

    @property
    def espn_client(self):
        if self._espn_client is None:
            from data.espn_client import ESPNStatsClient
            self._espn_client = ESPNStatsClient()
        return self._espn_client

    @property
    def cfbd_client(self):
        if self._cfbd_client is None and self.config.cfbd_api_key:
            from data.clients.cfbd_v2 import get_cfbd_v2_client
            self._cfbd_client = get_cfbd_v2_client()
        return self._cfbd_client

    def validate_data_availability(self, home_team: str, away_team: str) -> dict[str, bool]:
        """Best-effort live check of source reachability (diagnostic only)."""
        availability = {
            "teams_normalized": True,
            "odds_api_available": self.odds_client is not None,
            "espn_api_available": True,
            "home_team_data": False,
            "away_team_data": False,
            "betting_data": False,
        }
        for team, key in ((home_team, "home_team_data"), (away_team, "away_team_data")):
            try:
                self.espn_client.get_team_info(team)
                availability[key] = True
            except Exception:  # noqa: BLE001 — reachability probe
                pass
        if self.odds_client:
            try:
                availability["betting_data"] = self.odds_client.get_consensus_spread(
                    home_team, away_team) is not None
            except Exception:  # noqa: BLE001
                pass
        return availability

    def test_all_connections(self) -> dict[str, bool]:
        """Ping each source (diagnostic only)."""
        results: dict[str, bool] = {}
        # CFBD v2 client is dumb (no test_connection) — a light /conferences call pings it.
        try:
            results["cfbd_api"] = bool(self.cfbd_client and self.cfbd_client.get_conferences())
        except Exception as exc:  # noqa: BLE001
            self.logger.error("cfbd_api connection test failed: %s", exc)
            results["cfbd_api"] = False
        for name, client in (("espn_api", self.espn_client), ("odds_api", self.odds_client)):
            try:
                results[name] = bool(client and client.test_connection())
            except Exception as exc:  # noqa: BLE001
                self.logger.error("%s connection test failed: %s", name, exc)
                results[name] = False
        return results

    def get_cache_stats(self) -> dict[str, Any]:
        return self.cache.get_stats()

    def clear_all_caches(self) -> None:
        self.cache.clear_all()
        self.logger.info("All caches cleared")


def _present(status: Any) -> bool:
    """A field-group is present when its source stamped a real status (e.g. 'cfbd')."""
    return bool(status)


# Global data manager instance
data_manager = DataManager()
