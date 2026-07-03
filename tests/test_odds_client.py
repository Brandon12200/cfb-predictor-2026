"""Unit tests for the dumb Odds API client (offline, mocked)."""

import unittest
from unittest.mock import MagicMock

import requests

from data.clients.odds import OddsAPIError, OddsClient


def _fake_session(status=200, payload=None, raise_exc=None, headers=None):
    session = MagicMock(spec=requests.Session)
    session.headers = MagicMock()
    if raise_exc is not None:
        session.get.side_effect = raise_exc
    else:
        resp = MagicMock()
        resp.status_code = status
        resp.text = "" if payload is None else str(payload)
        resp.json.return_value = payload
        resp.headers = headers or {}
        session.get.return_value = resp
    return session


class TestOddsClient(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(OddsAPIError):
            OddsClient("")

    def test_apikey_and_params_sent(self):
        session = _fake_session(payload=[])
        client = OddsClient("secret", session=session)
        client.get_ncaaf_spreads()
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["apiKey"], "secret")
        self.assertEqual(params["regions"], "us")
        self.assertEqual(params["markets"], "spreads")
        url = session.get.call_args[0][0]
        self.assertTrue(url.endswith("/sports/americanfootball_ncaaf/odds"))

    def test_commence_window_params(self):
        session = _fake_session(payload=[])
        client = OddsClient("k", session=session)
        client.get_ncaaf_spreads(commence_time_from="2026-08-29T00:00:00Z",
                                 commence_time_to="2026-09-01T00:00:00Z")
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["commenceTimeFrom"], "2026-08-29T00:00:00Z")
        self.assertEqual(params["commenceTimeTo"], "2026-09-01T00:00:00Z")

    def test_returns_raw_events(self):
        events = [{"id": "abc", "home_team": "Georgia", "away_team": "Clemson",
                   "bookmakers": [{"key": "fanduel", "markets": [
                       {"key": "spreads", "outcomes": [
                           {"name": "Georgia", "point": -3.5},
                           {"name": "Clemson", "point": 3.5}]}]}]}]
        client = OddsClient("k", session=_fake_session(payload=events))
        self.assertEqual(client.get_ncaaf_spreads(), events)

    def test_captures_quota_headers(self):
        session = _fake_session(payload=[], headers={"x-requests-remaining": "487",
                                                     "x-requests-used": "13"})
        client = OddsClient("k", session=session)
        client.get_ncaaf_spreads()
        self.assertEqual(client.last_quota, {"remaining": 487, "used": 13})

    def test_missing_quota_headers_are_none(self):
        client = OddsClient("k", session=_fake_session(payload=[], headers={}))
        client.get_ncaaf_spreads()
        self.assertEqual(client.last_quota, {"remaining": None, "used": None})

    def test_non_200_raises(self):
        client = OddsClient("k", session=_fake_session(status=401))
        with self.assertRaises(OddsAPIError):
            client.get_ncaaf_spreads()

    def test_network_error_raises(self):
        client = OddsClient("k", session=_fake_session(raise_exc=requests.Timeout("boom")))
        with self.assertRaises(OddsAPIError):
            client.get_ncaaf_spreads()

    def test_bad_json_raises(self):
        session = _fake_session(payload=None)
        session.get.return_value.json.side_effect = ValueError("no json")
        client = OddsClient("k", session=session)
        with self.assertRaises(OddsAPIError):
            client.get_ncaaf_spreads()


if __name__ == "__main__":
    unittest.main()
