"""Unit tests for the CFBD v2 client (offline, mocked)."""

import unittest
from unittest.mock import MagicMock

import requests

from data.clients.cfbd_v2 import CFBDError, CFBDv2Client


def _fake_session(status=200, payload=None, raise_exc=None):
    session = MagicMock(spec=requests.Session)
    session.headers = MagicMock()
    if raise_exc is not None:
        session.get.side_effect = raise_exc
    else:
        resp = MagicMock()
        resp.status_code = status
        resp.text = "" if payload is None else str(payload)
        resp.json.return_value = payload
        session.get.return_value = resp
    return session


class TestCFBDv2Client(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(CFBDError):
            CFBDv2Client("")

    def test_sets_bearer_auth_header(self):
        session = _fake_session(payload=[])
        CFBDv2Client("secret", session=session)
        session.headers.update.assert_called_once()
        headers = session.headers.update.call_args[0][0]
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_get_conferences_hits_path_and_parses(self):
        session = _fake_session(payload=[{"id": 1, "name": "SEC"}])
        client = CFBDv2Client("k", session=session)
        result = client.get_conferences()
        self.assertEqual(result, [{"id": 1, "name": "SEC"}])
        url = session.get.call_args[0][0]
        self.assertTrue(url.endswith("/conferences"))

    def test_year_scoped_params(self):
        session = _fake_session(payload=[])
        client = CFBDv2Client("k", session=session)
        client.get_fbs_teams(2026)
        self.assertEqual(session.get.call_args.kwargs["params"], {"year": 2026})
        client.get_games(2026, week=7)
        self.assertEqual(session.get.call_args.kwargs["params"],
                         {"year": 2026, "seasonType": "regular", "week": 7})

    def test_non_200_raises(self):
        client = CFBDv2Client("k", session=_fake_session(status=401))
        with self.assertRaises(CFBDError):
            client.get_conferences()

    def test_network_error_raises_cfbderror(self):
        client = CFBDv2Client("k", session=_fake_session(raise_exc=requests.Timeout("boom")))
        with self.assertRaises(CFBDError):
            client.get_conferences()

    def test_bad_json_raises(self):
        session = _fake_session(payload=None)
        session.get.return_value.json.side_effect = ValueError("no json")
        client = CFBDv2Client("k", session=session)
        with self.assertRaises(CFBDError):
            client.get_conferences()


if __name__ == "__main__":
    unittest.main()
