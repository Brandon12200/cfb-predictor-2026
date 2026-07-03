"""The Odds API client (layer 1, SPEC §5.2).

Dumb and honest per the layer-1 contract: fetch → parse JSON → raise on failure.
No caching, no fallback, no consensus math, no team normalization — the snapshot
builder owns policy and the normalize layer owns consensus/name resolution.

Base is https://api.the-odds-api.com/v4; auth is an `apiKey` query param. This is
the market/CLV source (live + closing spreads) — CFBD `/lines` is a separate,
historical source. Budget note (D5): free tier = 500 credits/month; a call costs
len(markets)×len(regions) credits, so `regions=us&markets=spreads` ≈ 1 credit.
Each response's quota headers are captured in `last_quota` for the budget guard.
"""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_BASE_URL = "https://api.the-odds-api.com/v4"
DEFAULT_SPORT = "americanfootball_ncaaf"
DEFAULT_TIMEOUT = 30


class OddsAPIError(RuntimeError):
    """Raised when an Odds API request fails (network, auth, non-200, or bad JSON)."""


class OddsClient:
    """Thin, raise-on-failure wrapper over The Odds API v4."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL,
                 sport: str = DEFAULT_SPORT, timeout: int = DEFAULT_TIMEOUT,
                 session: requests.Session | None = None):
        if not api_key:
            raise OddsAPIError("Odds API key is required (set ODDS_API_KEY).")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._sport = sport
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "cfb-contrarian-predictor/2026 (Odds client)",
        })
        # Remaining/used monthly credits from the last response's quota headers.
        self.last_quota: dict[str, int | None] = {"remaining": None, "used": None}

    # -- transport -------------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any]) -> Any:
        params = {**params, "apiKey": self._api_key}
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:  # network/DNS/timeout
            raise OddsAPIError(f"Odds API request failed: GET {path}: {exc}") from exc
        self._capture_quota(resp)
        if resp.status_code != 200:
            body = resp.text[:200]
            raise OddsAPIError(f"Odds API returned {resp.status_code} for GET {path}: {body}")
        try:
            return resp.json()
        except ValueError as exc:
            raise OddsAPIError(f"Odds API returned non-JSON for GET {path}: {exc}") from exc

    def _capture_quota(self, resp: requests.Response) -> None:
        def _int(header: str) -> int | None:
            try:
                return int(resp.headers.get(header))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
        self.last_quota = {
            "remaining": _int("x-requests-remaining"),
            "used": _int("x-requests-used"),
        }

    # -- odds ------------------------------------------------------------------
    def get_ncaaf_spreads(self, regions: str = "us", markets: str = "spreads",
                          odds_format: str = "american",
                          commence_time_from: str | None = None,
                          commence_time_to: str | None = None) -> list[dict]:
        """Raw NCAAF odds events — each with `home_team`/`away_team`/`commence_time`
        and `bookmakers[].markets[].outcomes[].point`. Consensus and team-name
        resolution happen in the normalize layer, not here. Optional ISO
        `commence_time_from`/`to` window a specific slate."""
        params: dict[str, Any] = {"regions": regions, "markets": markets,
                                  "oddsFormat": odds_format, "dateFormat": "iso"}
        if commence_time_from:
            params["commenceTimeFrom"] = commence_time_from
        if commence_time_to:
            params["commenceTimeTo"] = commence_time_to
        return self._get(f"/sports/{self._sport}/odds", params)


def get_odds_client(api_key: str | None = None) -> OddsClient:
    """Build a client from the given key or `config.config.odds_api_key`."""
    if api_key is None:
        from config import config
        api_key = config.odds_api_key
    return OddsClient(api_key)
