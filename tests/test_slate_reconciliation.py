"""The dropped-game detector (SPEC §5.5.3) — a game may be excluded, never invisibly.

Before this, CFBD returned ~888 season rows and ~734 became tracked games, and **nothing recorded
the 154-row difference or its reason**. Both drop sites just `continue`d, so an FBS game lost to an
unresolved alias was indistinguishable from an FBS-vs-FCS game correctly filtered out (§16.1) — and
the comments at both sites claimed a "slate reconciler" that did not exist.

The load-bearing test here is `test_the_reconciliation_cannot_move_the_snapshot_id`. This detector
is added **after the freeze**, and the one way it could do damage is by reaching hashed `data` —
which would move `snapshot_id`, the schema-v2 golden and the behavioural fingerprint, and look
exactly like a freeze violation. `compute_snapshot_id(data)` runs strictly before the manifest is
built; that ordering is what makes this safe, so it is pinned rather than trusted.
"""

from __future__ import annotations

import pytest

from data.normalize.cfbd import classify_drop, normalize_games
from data.normalize.odds import normalize_lines
from data.snapshot import SnapshotBuilder, compute_snapshot_id
from tests.test_snapshot import _FakeCFBD, _FakeOdds, _FakeRegistry

CLOCK = "2026-08-08T12:00:00+00:00"


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    import data.snapshot.lines as lines_mod
    import data.snapshot.store as store_mod
    monkeypatch.setattr(store_mod, "_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(lines_mod, "_LINES_DIR", tmp_path / "lines")
    return SnapshotBuilder(_FakeCFBD(), _FakeOdds(), _FakeRegistry(),
                           clock=lambda: CLOCK).build(week=1)


# --- the freeze-safety property -----------------------------------------------------------------

def test_the_reconciliation_cannot_move_the_snapshot_id(tmp_path, monkeypatch):
    """`data` must be byte-identical with and without the reconciliation block."""
    import data.snapshot.lines as lines_mod
    import data.snapshot.store as store_mod
    monkeypatch.setattr(store_mod, "_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(lines_mod, "_LINES_DIR", tmp_path / "lines")

    SnapshotBuilder(_FakeCFBD(), _FakeOdds(), _FakeRegistry(), clock=lambda: CLOCK).build(week=1)
    snap = store_mod.load_snapshot(1, 2026)

    # The id recomputes from `data` alone, and `data` carries no reconciliation key anywhere.
    assert compute_snapshot_id(snap["data"]) == snap["meta"]["snapshot_id"]
    assert "reconciliation" not in snap["data"]
    assert set(snap) == {"data", "meta"}


def test_the_reconciliation_lives_in_the_manifest(manifest):
    assert "reconciliation" in manifest
    assert manifest["reconciliation"]["cfbd_rows_fetched"] == 2  # the fake's two rows


def test_the_snapshot_id_is_stable_across_builds(tmp_path, monkeypatch):
    ids = []
    for i in range(2):
        import data.snapshot.lines as lines_mod
        import data.snapshot.store as store_mod
        base = tmp_path / f"run{i}"
        monkeypatch.setattr(store_mod, "_SNAPSHOTS_DIR", base / "snapshots")
        monkeypatch.setattr(lines_mod, "_LINES_DIR", base / "lines")
        SnapshotBuilder(_FakeCFBD(), _FakeOdds(), _FakeRegistry(),
                        clock=lambda: CLOCK).build(week=1)
        ids.append(store_mod.load_snapshot(1, 2026)["meta"]["snapshot_id"])
    assert ids[0] == ids[1]


# --- the classification that is the point -------------------------------------------------------

def test_an_fcs_opponent_is_out_of_scope_not_a_defect():
    """FBS-vs-FCS is correctly excluded per §16.1 — it must not read as a lost game."""
    from data.team_registry import get_fcs_names
    fcs = sorted(get_fcs_names())
    if not fcs:
        pytest.skip("registry carries no FCS names")
    assert classify_drop(fcs[0], "GEORGIA", None, "GEORGIA", 1) == "fcs_opponent_out_of_scope"


def test_an_unresolvable_fbs_name_is_flagged_as_a_defect():
    """The case worth catching: a tracked game silently lost to an alias gap."""
    assert classify_drop("Zzz Tech", "GEORGIA", None, "GEORGIA", 1) == "unresolved_team_name"


def test_an_unparseable_week_has_its_own_reason():
    assert classify_drop("Georgia", "Clemson", "GEORGIA", "CLEMSON", None) == "unparseable_week"


def test_normalize_games_records_drops_with_reasons():
    rows = [
        {"week": 1, "homeTeam": "Georgia", "awayTeam": "Clemson"},
        {"week": 1, "homeTeam": "Georgia", "awayTeam": "Zzz Tech"},
        {"week": None, "homeTeam": "Georgia", "awayTeam": "Clemson"},
    ]
    excluded: list[dict] = []
    games = normalize_games(rows, excluded=excluded)

    assert len(games) == 1
    assert len(excluded) == 2
    reasons = {e["reason"] for e in excluded}
    assert "unresolved_team_name" in reasons
    assert "unparseable_week" in reasons
    # The raw names are preserved so the gap can actually be fixed.
    assert any(e["away"] == "Zzz Tech" for e in excluded)


def test_normalize_games_is_unchanged_when_no_collector_is_passed():
    """Backwards compatible: every existing caller keeps its exact behaviour."""
    rows = [{"week": 1, "homeTeam": "Georgia", "awayTeam": "Zzz Tech"}]
    assert normalize_games(rows) == []


def test_normalize_lines_records_unresolved_events():
    excluded: list[dict] = []
    normalize_lines([{"home_team": "Zzz Tech", "away_team": "Qqq State", "bookmakers": []}],
                    "2026-08-08T00:00:00Z", excluded=excluded)
    assert len(excluded) == 1
    # Neither side is a program we know, so this is `non_fbs_matchup` — informational, not the
    # defect class. `unresolved_team_name` is reserved for "an FBS team's opponent could not be
    # identified", which is the only case that means a tracked game is being lost.
    assert excluded[0]["reason"] == "non_fbs_matchup"


def test_the_defect_class_is_reserved_for_a_lost_tracked_game():
    """Crying wolf is a real failure mode: CFBD posts ~114 lower-division matchups a season, and
    if those share a reason with a genuinely lost FBS game nobody reads the warning."""
    from data.normalize.cfbd import classify_drop
    # Two unknown lower-division schools -> informational.
    assert classify_drop("Aurora", "Rockford", None, None, 1) == "non_fbs_matchup"
    # An FBS team whose opponent we cannot identify -> the defect class.
    assert classify_drop("Zzz Tech", "Georgia", None, "GEORGIA", 1) == "unresolved_team_name"


# --- the cross-reference §5.5.3 asks for --------------------------------------------------------

def test_scope_filtered_games_are_counted_not_hidden(manifest):
    """The fake slate has Alabama/Duke tracked but without a line, and Georgia/Clemson with one."""
    rec = manifest["reconciliation"]["week_slate"]
    assert rec["week"] == 1
    assert rec["tracked_games"] == manifest["summary"]["slate_games"]


def test_a_slate_game_without_a_line_is_surfaced(manifest):
    """The fake Odds client prices only Georgia/Clemson, so Duke@Alabama has no line."""
    odds = manifest["reconciliation"]["odds_cross_reference"]
    assert "DUKE@ALABAMA" in odds["slate_games_without_a_line"]
    assert odds["matched_to_slate"] == 1


def test_an_odds_event_with_no_tracked_game_is_surfaced(tmp_path, monkeypatch):
    """A game present in one source but not the other — the §5.5.3 cross-reference."""
    import data.snapshot.lines as lines_mod
    import data.snapshot.store as store_mod
    monkeypatch.setattr(store_mod, "_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(lines_mod, "_LINES_DIR", tmp_path / "lines")

    class _OddsWithAStrayEvent(_FakeOdds):
        def get_ncaaf_spreads(self):
            return super().get_ncaaf_spreads() + [{
                "home_team": "Duke", "away_team": "Clemson", "bookmakers": [
                    {"key": "fanduel", "markets": [{"key": "spreads", "outcomes": [
                        {"name": "Duke", "point": -1.5}, {"name": "Clemson", "point": 1.5}]}]}]}]

    manifest = SnapshotBuilder(_FakeCFBD(), _OddsWithAStrayEvent(), _FakeRegistry(),
                               clock=lambda: CLOCK).build(week=1)
    odds = manifest["reconciliation"]["odds_cross_reference"]
    assert "CLEMSON@DUKE" in odds["unmatched_odds_events"]


# --- it is actually rendered ---------------------------------------------------------------------

def test_the_inspector_renders_the_reconciliation(manifest, tmp_path, monkeypatch):
    import data.snapshot.store as store_mod
    from scripts.inspect_snapshot import render_manifest
    text = render_manifest(manifest, store_mod.load_snapshot(1, 2026))
    assert "reconciliation:" in text
    assert "CFBD rows" in text


def test_the_inspector_tolerates_a_snapshot_without_the_block():
    """The committed July snapshot predates the detector and must still inspect."""
    from scripts.inspect_snapshot import _render_reconciliation
    text = "\n".join(_render_reconciliation({"meta": {}, "summary": {}}))
    assert "predates the detector" in text


def test_the_committed_snapshot_still_inspects():
    from pathlib import Path

    from scripts.inspect_snapshot import render_manifest
    root = Path(__file__).resolve().parent.parent
    if not (root / "data" / "snapshots" / "2026_week_01" / "manifest.json").exists():
        pytest.skip("no committed snapshot")
    import json
    manifest = json.loads((root / "data/snapshots/2026_week_01/manifest.json").read_text())
    snapshot = json.loads((root / "data/snapshots/2026_week_01/snapshot.json").read_text())
    assert render_manifest(manifest, snapshot)


# --- the false comments this replaces -------------------------------------------------------------

def test_the_false_reconciler_comments_are_gone():
    """Both sites claimed a reconciler that did not exist. Both were fixed, not one."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for path in ("data/normalize/cfbd.py", "data/normalize/odds.py"):
        text = (root / path).read_text()
        assert "the slate reconciler logs" not in text, f"{path} still claims a phantom reconciler"
