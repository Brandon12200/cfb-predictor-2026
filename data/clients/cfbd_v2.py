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

import logging
import time
from typing import Any

import requests

DEFAULT_BASE_URL = "https://api.collegefootballdata.com"
DEFAULT_TIMEOUT = 30

# D48 (owner 2026-11-05): ONE retry, on transport errors and 5xx only.
#
# Three scheduled runs failed this season on a transient CFBD fault and each was fixed by the owner
# re-dispatching the identical job: #56 (09-05, `sp_watch` read timeout), #71 (10-20, the catch-up
# grade's `fetch_results` read timeout) and #72 (10-21, `sp_watch` Cloudflare 502). That met the
# drawer's third-occurrence condition. The retry lives here, at the single `_get` chokepoint, so it
# covers the probe, the catch-up grade and the predict alike rather than whichever caller someone
# remembered — two of the three failures were the probe and one blocked a week's claim.
#
# **One** retry, not a policy: a transient 502 or a dropped connection clears on an immediate
# second attempt, and anything that does not is a real outage the alarm should report rather than
# something to grind against. A 4xx is NEVER retried — 401, 403 and 404 are answers, not faults,
# and repeating them wastes a call against a 5,000/month key shared with the basketball API (D5).
RETRY_ON_5XX_FROM = 500
RETRY_ATTEMPTS = 2          # the first try plus one retry
RETRY_BACKOFF_SECONDS = 2.0

_log = logging.getLogger(__name__)


class CFBDError(RuntimeError):
    """Raised when a CFBD v2 request fails (network, auth, non-200, or bad JSON)."""


class CFBDv2Client:
    """Thin, raise-on-failure wrapper over the CFBD v2 REST API."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT, session: requests.Session | None = None,
                 retry_backoff: float = RETRY_BACKOFF_SECONDS):
        if not api_key:
            raise CFBDError("CFBD API key is required (set CFBD_API_KEY).")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # Injectable so a test can exercise the retry without sleeping through it. A test that has
        # to wait two seconds is a test someone eventually marks slow and skips.
        self._retry_backoff = retry_backoff
        self._session = session or requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "cfb-contrarian-predictor/2026 (CFBD v2 client)",
        })

    # -- transport -------------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET and parse, with one retry on a transient fault (D48).

        Retryable: a `requests.RequestException` (DNS, connection, read timeout) and any status at
        or above 500. Not retryable, and raised on the first attempt: every 4xx, and a 200 whose
        body will not parse as JSON — a malformed answer is a different fault from an unreachable
        server, and repeating the call neither diagnoses nor fixes it.
        """
        url = f"{self._base_url}{path}"
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            retryable: bool
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:  # network/DNS/timeout
                error = CFBDError(f"CFBD request failed: GET {path} params={params}: {exc}")
                error.__cause__ = exc
                retryable = True
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise CFBDError(f"CFBD returned non-JSON for GET {path}: {exc}") from exc
                body = resp.text[:200]
                error = CFBDError(
                    f"CFBD returned {resp.status_code} for GET {path} params={params}: {body}")
                retryable = resp.status_code >= RETRY_ON_5XX_FROM

            if retryable and attempt < RETRY_ATTEMPTS:
                # Logged at WARNING so it reaches the Actions log of a run that then SUCCEEDS:
                # a retry that rescues a run is the only evidence the outage happened at all, and
                # a silent rescue would hide a degrading upstream until it stopped being rescuable.
                _log.warning("CFBD GET %s failed (%s); retrying once in %.1fs",
                             path, error, self._retry_backoff)
                time.sleep(self._retry_backoff)
                continue
            raise error
        raise AssertionError("unreachable: the loop either returns or raises")  # pragma: no cover

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
