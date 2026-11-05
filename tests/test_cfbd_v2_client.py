"""Unit tests for the CFBD v2 client (offline, mocked)."""

import logging
import unittest
from unittest.mock import MagicMock, patch

import requests

from data.clients import cfbd_v2
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



def _sequence_session(*responses):
    """A session whose successive GETs yield the given responses.

    Each item is either an exception instance (raised) or a ``(status, payload)`` pair. Used to
    exercise the retry, which needs the first and second attempts to differ.
    """
    session = MagicMock(spec=requests.Session)
    session.headers = MagicMock()
    prepared = []
    for item in responses:
        if isinstance(item, BaseException):
            prepared.append(item)
            continue
        status, payload = item
        resp = MagicMock()
        resp.status_code = status
        resp.text = "" if payload is None else str(payload)
        resp.json.return_value = payload
        prepared.append(resp)
    session.get.side_effect = prepared
    return session


class TestOneRetryOnTransientFaults(unittest.TestCase):
    """D48: one retry, transport errors and 5xx only, never a 4xx.

    Three scheduled runs died on a transient CFBD fault this season (#56, #71, #72) and each was
    fixed by re-dispatching the same job unchanged — the definition of retryable. The call counts
    below are asserted as literals rather than against ``RETRY_ATTEMPTS``, so raising the constant
    fails these tests and has to be a deliberate, reviewed change rather than a quiet one.
    """

    def _client(self, session):
        return CFBDv2Client("k", session=session, retry_backoff=0)

    def test_a_transport_error_is_retried_once_and_can_succeed(self):
        session = _sequence_session(requests.Timeout("read timeout"), (200, [{"ok": 1}]))
        with self.assertLogs(cfbd_v2.__name__, level=logging.WARNING) as logs:
            self.assertEqual(self._client(session).get_conferences(), [{"ok": 1}])
        self.assertEqual(session.get.call_count, 2)
        self.assertIn("retrying once", logs.output[0])
        self.assertIn("/conferences", logs.output[0])

    def test_a_502_is_retried_once_and_can_succeed(self):
        """#72's exact shape: CFBD behind Cloudflare returning 502 on ``/ratings/sp``."""
        session = _sequence_session((502, "<html>Bad gateway</html>"), (200, [{"team": "X"}]))
        with self.assertLogs(cfbd_v2.__name__, level=logging.WARNING):
            self.assertEqual(self._client(session).get_sp_ratings(2026), [{"team": "X"}])
        self.assertEqual(session.get.call_count, 2)

    def test_a_persistent_5xx_raises_after_exactly_one_retry(self):
        session = _sequence_session((503, "down"), (503, "down"))
        with self.assertRaises(CFBDError), self.assertLogs(cfbd_v2.__name__, level=logging.WARNING):
            self._client(session).get_conferences()
        self.assertEqual(session.get.call_count, 2, "one retry, then report the outage")

    def test_a_persistent_transport_error_raises_after_exactly_one_retry(self):
        session = _sequence_session(requests.ConnectionError("no route"),
                                    requests.ConnectionError("no route"))
        with self.assertRaises(CFBDError), self.assertLogs(cfbd_v2.__name__, level=logging.WARNING):
            self._client(session).get_conferences()
        self.assertEqual(session.get.call_count, 2)

    def test_a_4xx_is_never_retried(self):
        """401/403/404 are answers, not faults. Repeating one burns a call against a 5,000/month
        key shared with the basketball API (D5) and cannot change the result."""
        for status in (400, 401, 403, 404, 429):
            session = _sequence_session((status, "nope"), (200, [{"unreachable": True}]))
            with self.subTest(status=status), self.assertRaises(CFBDError):
                self._client(session).get_conferences()
            self.assertEqual(session.get.call_count, 1, f"{status} must not be retried")

    def test_a_200_that_is_not_json_is_not_retried(self):
        """A malformed answer is a different fault from an unreachable server; a second identical
        call neither diagnoses nor fixes it."""
        session = MagicMock(spec=requests.Session)
        session.headers = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html>"
        resp.json.side_effect = ValueError("no json")
        session.get.return_value = resp
        with self.assertRaises(CFBDError):
            self._client(session).get_conferences()
        self.assertEqual(session.get.call_count, 1)

    def test_the_backoff_is_waited_once_before_the_retry(self):
        """``tests/conftest.py`` no-ops ``time.sleep`` suite-wide, so the wait is asserted by
        recording the call rather than by elapsed time — otherwise this would pass with no backoff
        at all."""
        session = _sequence_session(requests.Timeout("t"), (200, []))
        with patch.object(cfbd_v2.time, "sleep") as slept, \
                self.assertLogs(cfbd_v2.__name__, level=logging.WARNING):
            CFBDv2Client("k", session=session, retry_backoff=1.5).get_conferences()
        slept.assert_called_once_with(1.5)

    def test_a_first_attempt_success_neither_sleeps_nor_warns(self):
        session = _sequence_session((200, [{"ok": 1}]))
        with patch.object(cfbd_v2.time, "sleep") as slept:
            self.assertEqual(self._client(session).get_conferences(), [{"ok": 1}])
        slept.assert_not_called()
        self.assertEqual(session.get.call_count, 1)

if __name__ == "__main__":
    unittest.main()
