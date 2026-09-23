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


# --- the store is replaced in one step, never truncated in place ---------------------------------
#
# `record_observation` used to `path.write_text`, which truncates and then writes. A run killed in
# that window — a 20-minute job timeout, a cancelled run, a runner reset — left a half-written JSON
# file, and every later reader of that week died on it: `closing_observation`, grading, and the
# capture preflight, which turned one torn write into every remaining capture of the week failing
# before it fetched anything. Found by an adversarial review of the D44 cadence PR.

def _obs(at: str, spread: float) -> dict:
    return {"G@H": {"home_team": "H", "away_team": "G", "kickoff": "2026-09-05T16:00:00Z",
                    "observations": [{"fetched_at": at, "lines": [], "consensus_spread": spread}]}}


def test_a_killed_write_leaves_the_previous_store_intact(tmp_path, monkeypatch):
    import os

    from data.snapshot.lines import lines_path

    record_observation(1, _obs("2026-09-01T00:00:00Z", -3.0), base=tmp_path)
    before = lines_path(1, base=tmp_path).read_bytes()

    def killed(*args, **kwargs):
        raise OSError("runner died between the write and the rename")

    monkeypatch.setattr(os, "replace", killed)
    try:
        record_observation(1, _obs("2026-09-02T00:00:00Z", -4.0), base=tmp_path)
    except OSError:
        pass
    assert lines_path(1, base=tmp_path).read_bytes() == before, "a torn write must not be visible"
    assert load_lines(1, base=tmp_path)["G@H"]["observations"][0]["consensus_spread"] == -3.0
    assert [p.name for p in lines_path(1, base=tmp_path).parent.iterdir()] == \
        ["2026_week_01.json"], "no temp file may be left behind"


def test_identical_input_still_produces_identical_bytes(tmp_path):
    """The atomic write must not change serialization: the append-only hooks and the byte-identity
    golden compare bytes, not parsed JSON."""
    from data.snapshot.lines import lines_path

    record_observation(1, _obs("2026-09-01T00:00:00Z", -3.0), base=tmp_path)
    first = lines_path(1, base=tmp_path).read_bytes()
    record_observation(1, _obs("2026-09-01T00:00:00Z", -3.0), base=tmp_path)   # deduped no-op
    assert lines_path(1, base=tmp_path).read_bytes() == first


def test_the_temp_file_is_a_sibling_of_its_target(tmp_path, monkeypatch):
    """`os.replace` is only atomic within one filesystem, so the temp file must live in the target's
    own directory — not `/tmp`, which is often a different mount (review of the D44 PR, finding 13).
    """
    import utils.atomic_write as aw

    seen = {}
    real = aw.os.replace

    def watch(src, dst):
        seen["src"], seen["dst"] = str(src), str(dst)
        return real(src, dst)

    monkeypatch.setattr(aw.os, "replace", watch)
    target = tmp_path / "nested" / "store.json"
    target.parent.mkdir(parents=True)
    aw.write_text_atomic(target, "{}\n")
    from pathlib import Path
    assert Path(seen["src"]).parent == target.parent, "temp file must be a sibling of the target"
    assert Path(seen["src"]).name.endswith(".tmp") and Path(seen["src"]).name.startswith(".")
