"""No-network + reproducible-rerun acceptance tests (SPEC §5, Phase 1b).

These encode two of the phase's headline guarantees: the engine reads ONLY snapshots
(a full prediction runs with all networking hard-disabled), and two reruns on the same
snapshot are byte-for-byte identical (frozen-clock reproducibility contract, SCHEMA §3).
"""

import json
import socket

from data.snapshot import SnapshotBuilder
from data.snapshot import store as snapshot_store
from tests.test_snapshot import _FakeCFBD, _FakeOdds, _FakeRegistry


def _build_snapshot(tmp_path):
    SnapshotBuilder(_FakeCFBD(), _FakeOdds(), _FakeRegistry(),
                    clock=lambda: "2026-09-01T00:00:00+00:00",
                    base_dir=tmp_path).build(week=1)


def test_full_prediction_runs_with_all_networking_disabled(tmp_path, monkeypatch):
    _build_snapshot(tmp_path)
    monkeypatch.setattr(snapshot_store, "_SNAPSHOTS_DIR", tmp_path)

    # Hard block: any socket creation during the prediction raises immediately.
    def _blocked(*args, **kwargs):
        raise RuntimeError("network access attempted during a snapshot-only prediction")
    monkeypatch.setattr(socket, "socket", _blocked)

    from engine.prediction_engine import prediction_engine
    result = prediction_engine.generate_prediction("GEORGIA", "CLEMSON", week=1)

    assert not result.get("error"), result
    assert result["vegas_spread"] == -7.5  # from the snapshot's Odds line
    assert result["snapshot_id"]           # prediction records which snapshot it used


def test_two_reruns_are_bit_identical(tmp_path, monkeypatch):
    _build_snapshot(tmp_path)
    monkeypatch.setattr(snapshot_store, "_SNAPSHOTS_DIR", tmp_path)

    from engine.prediction_engine import prediction_engine
    r1 = prediction_engine.generate_prediction("GEORGIA", "CLEMSON", week=1)
    r2 = prediction_engine.generate_prediction("GEORGIA", "CLEMSON", week=1)

    def dump(r):
        return json.dumps(r, sort_keys=True, default=str)

    # Byte-for-byte identical over the FULL payload — timestamp included, because it is
    # frozen from the snapshot's build time rather than datetime.now().
    assert dump(r1) == dump(r2)
    assert r1["timestamp"] == "2026-09-01T00:00:00+00:00"
    assert r1["snapshot_id"] == r2["snapshot_id"]
