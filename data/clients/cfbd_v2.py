"""CollegeFootballData (CFBD) API **v2** client (SPEC §5.2 / §5.4).

Dumb and honest per the layer-1 contract: fetch → parse JSON → raise on failure.
No caching, no fallback, no neutral values — the snapshot builder owns policy.

v2 base is https://api.collegefootballdata.com with `Authorization: Bearer <key>`
(the old v1 host now serves v2; v1 response shapes are gone). Endpoints and
fields verified live against a Tier-1 key on 2026-07-03.

Budget note (D5): the key is CFBD Tier 1 — 5,000 requests/month **shared with
the basketball API**. Prefer the year/week-scoped league-wide methods (one call
returns all teams) over per-team calls, and cache upstream in the snapshot layer.
"""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_BASE_URL = "https://api.collegefootballdata.com"
DEFAULT_TIMEOUT = 30


class CFBDError(RuntimeError):
    """Raised when a CFBD v2 request fails (network, auth, non-200, or bad JSON)."""


class CFBDv2Client:
    """Thin, raise-on-failure wrapper over the CFBD v2 REST API."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT, session: requests.Session | None = None):
        if not api_key:
            raise CFBDError("CFBD API key is required (set CFBD_API_KEY).")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "cfb-contrarian-predictor/2026 (CFBD v2 client)",
        })

    # -- transport -------------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:  # network/DNS/timeout
            raise CFBDError(f"CFBD request failed: GET {path} params={params}: {exc}") from exc
        if resp.status_code != 200:
            body = resp.text[:200]
            raise CFBDError(f"CFBD returned {resp.status_code} for GET {path} params={params}: {body}")
        try:
            return resp.json()
        except ValueError as exc:
            raise CFBDError(f"CFBD returned non-JSON for GET {path}: {exc}") from exc

    # -- registry / calendar (league-wide; used by Phase 1a) -------------------
    def get_conferences(self) -> list[dict]:
        """All conferences (id, name, abbreviation, shortName, classification)."""
        return self._get("/conferences")

    def get_fbs_teams(self, year: int) -> list[dict]:
        """FBS teams for a season — per-season conference/division membership +
        `alternateNames` aliases. This is the canonical team-registry source."""
        return self._get("/teams/fbs", {"year": year})

    def get_teams(self, year: int) -> list[dict]:
        """ALL teams for a season across every division (FBS + FCS + …), each with
        `classification`, `conference`, and `alternateNames`. One call yields both
        the FBS registry (membership + aliases) and the FCS set that `is_fcs_team`
        needs — cheaper than two division-scoped calls against the shared budget."""
        return self._get("/teams", {"year": year})

    def get_calendar(self, year: int) -> list[dict]:
        """Season weeks with startDate/endDate/seasonType — corroborates D1."""
        return self._get("/calendar", {"year": year})

    def get_venues(self) -> list[dict]:
        """Venues with location (lat/long), elevation, timezone, dome — schedule-intel."""
        return self._get("/venues")

    # -- games / stats / ratings (year- or week-scoped; league-wide) -----------
    def get_games(self, year: int, week: int | None = None,
                  season_type: str = "regular") -> list[dict]:
        params: dict[str, Any] = {"year": year, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        return self._get("/games", params)

    def get_coaches(self, year: int) -> list[dict]:
        return self._get("/coaches", {"year": year})

    def get_season_stats(self, year: int) -> list[dict]:
        return self._get("/stats/season", {"year": year})

    def get_advanced_season_stats(self, year: int, exclude_garbage_time: bool = True) -> list[dict]:
        """EPA/PPA, success rate, explosiveness, havoc — one call, all teams."""
        return self._get("/stats/season/advanced",
                         {"year": year, "excludeGarbageTime": exclude_garbage_time})

    def get_sp_ratings(self, year: int) -> list[dict]:
        return self._get("/ratings/sp", {"year": year})

    def get_returning_production(self, year: int) -> list[dict]:
        return self._get("/player/returning", {"year": year})

    def get_lines(self, year: int, week: int | None = None,
                  season_type: str = "regular") -> list[dict]:
        """Historical/consensus betting lines (live/closing lines come from the
        Odds API, not here)."""
        params: dict[str, Any] = {"year": year, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        return self._get("/lines", params)


def get_cfbd_v2_client(api_key: str | None = None) -> CFBDv2Client:
    """Build a client from the given key or `config.config.cfbd_api_key`."""
    if api_key is None:
        from config import config
        api_key = config.cfbd_api_key
    return CFBDv2Client(api_key)
