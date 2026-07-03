"""Tests for the append-only line-observation store + snapshot immutability (SPEC §5.4.3).

The headline guarantee: appending line observations (closing-line capture) NEVER changes
the content-addressed snapshot — `snapshot_id` and the snapshot bytes are untouched, so
1b's reproducibility contract survives 1c.
"""

from data.snapshot import SnapshotBuilder
from data.snapshot.lines import load_lines, record_observation
from data.snapshot.store import load_snapshot
from tests.test_snapshot import _FakeCFBD, _FakeOdds, _FakeRegistry


def _build(tmp_path):
    return SnapshotBuilder(_FakeCFBD(), _FakeOdds(), _FakeRegistry(),
                           clock=lambda: "2026-09-01T00:00:00+00:00",
                           base_dir=tmp_path).build(week=1)


def test_build_seeds_lines_store_with_observation_one(tmp_path):
    _build(tmp_path)
    store = load_lines(1, base=tmp_path)
    assert "CLEMSON@GEORGIA" in store  # the game that had a posted line
    obs = store["CLEMSON@GEORGIA"]["observations"]
    assert len(obs) == 1 and obs[0]["consensus_spread"] == -7.5
    assert obs[0]["fetched_at"] == "2026-09-01T00:00:00+00:00"


def test_snapshot_holds_only_the_frozen_prediction_time_observation(tmp_path):
    _build(tmp_path)
    bl = load_snapshot(1, base=tmp_path)["data"]["betting_lines"]["CLEMSON@GEORGIA"]
    assert bl["vegas_spread"] == -7.5
    assert bl["observation"]["consensus_spread"] == -7.5
    assert "observations" not in bl  # the series is NOT in the snapshot


def test_append_does_not_change_snapshot_id_or_bytes(tmp_path):
    manifest = _build(tmp_path)
    sid = manifest["meta"]["snapshot_id"]
    snap_before = load_snapshot(1, base=tmp_path)

    # A later fetch_lines run appends a new observation to the store.
    new = {"CLEMSON@GEORGIA": {"home_team": "GEORGIA", "away_team": "CLEMSON",
           "kickoff": None, "observations": [
               {"fetched_at": "2026-09-05T12:00:00Z", "lines": [], "consensus_spread": -8.0}]}}
    record_observation(1, new, base=tmp_path)

    snap_after = load_snapshot(1, base=tmp_path)
    assert snap_after["meta"]["snapshot_id"] == sid   # id unchanged
    assert snap_after == snap_before                  # snapshot bytes unchanged
    assert len(load_lines(1, base=tmp_path)["CLEMSON@GEORGIA"]["observations"]) == 2


def test_record_observation_dedups_by_fetched_at(tmp_path):
    obs = {"G@H": {"home_team": "H", "away_team": "G", "kickoff": None, "observations": [
        {"fetched_at": "2026-09-01T00:00:00Z", "lines": [], "consensus_spread": -3.0}]}}
    assert record_observation(1, obs, base=tmp_path) == 1
    assert record_observation(1, obs, base=tmp_path) == 0  # same fetched_at → idempotent
    assert len(load_lines(1, base=tmp_path)["G@H"]["observations"]) == 1
