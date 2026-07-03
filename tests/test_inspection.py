"""Tests for the inspection tooling render functions (SPEC §5.3). Offline."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import inspect_snapshot  # noqa: E402
import status  # noqa: E402

from data.snapshot.store import load_manifest, load_snapshot  # noqa: E402


def _committed():
    return load_manifest(1, 2026), load_snapshot(1, 2026)


def test_render_manifest_shows_sources_and_coverage():
    manifest, snapshot = _committed()
    out = inspect_snapshot.render_manifest(manifest, snapshot)
    assert manifest["meta"]["snapshot_id"] in out
    assert "coverage:" in out and "% " not in out.split("coverage:")[0]
    assert "sources:" in out
    assert "team field-group coverage:" in out
    # New 1c field-groups appear in the coverage tally.
    assert "venue" in out and "sp_rating" in out
    assert "slate games" in out


def test_render_manifest_game_drilldown():
    manifest, snapshot = _committed()
    game = next(iter(manifest["coverage"]["games"]))  # a real slate game
    out = inspect_snapshot.render_manifest(manifest, snapshot, game=game)
    assert f"game {game}:" in out
    assert "betting:" in out
    assert "intel[" in out  # schedule-intel drilldown for the participants


def test_render_manifest_unknown_game_is_graceful():
    manifest, snapshot = _committed()
    out = inspect_snapshot.render_manifest(manifest, snapshot, game="NOBODY@NOWHERE")
    assert "not in slate" in out


def test_render_status_with_known_quota():
    out = status.render_status(
        cfbd_key=True, odds_key=True, odds_budget=500,
        quota_snapshot="2026_week_01", quota={"remaining": 488, "used": 12}, cfbd_ping=True)
    assert "CFBD v2" in out and "ping OK" in out
    assert "488 remaining / 500 monthly budget" in out


def test_render_status_without_quota():
    out = status.render_status(True, False, 500, None, None, cfbd_ping=None)
    assert "not pinged" in out and "unknown" in out


def test_latest_odds_quota_reads_committed_snapshot():
    name, quota = status.latest_odds_quota()
    assert name is not None  # the committed 2026_week_01 exists
