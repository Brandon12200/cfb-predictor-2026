"""Name resolution fails closed across the FBS boundary (SPEC §3 exception 1).

`difflib` at cutoff 0.8 cannot tell "a typo of an FBS team" from "a different school with a similar
name". Measured against the real CFBD feed, **16 FCS programs resolved onto FBS teams**, and when
both sides of an FCS game resolved a **fabricated FBS game entered the snapshot** — including
NORTH DAKOTA STATE playing itself. Ten such games were already in the v2026-frozen vehicle.

`data["games"]` drives schedule intelligence, and in-season a completed FCS result would have moved
an FBS team's Elo — Samford's result credited to Stanford. So this is a no-fabricated-data
violation with a real downstream cost, not a cosmetic mapping issue.

The rule now: **membership in the tracked universe is decided only by exact canonical, explicit
alias, or a `CANONICAL_OVERRIDES` entry.** Fuzzy matching may not confer it. Unknown names return
`None` and are recorded with a reason by the reconciler — visible and fixable, rather than silently
becoming the wrong team.
"""

from __future__ import annotations

import pytest

from data.team_registry import (
    CANONICAL_OVERRIDES,
    get_all_tracked_teams,
    get_fbs_canonical_names,
)
from utils.normalizer import normalizer

# Every collision measured against the live CFBD feed on 2026-08-08.
KNOWN_COLLISIONS = {
    "Samford": "STANFORD",
    "Southern": "USC",
    "Southern Utah": "USC",
    "Mississippi Valley State": "MISSISSIPPI STATE",
    "Northwestern State": "NORTHWESTERN",
    "North Carolina A&T": "NORTH CAROLINA",
    "South Carolina State": "SOUTH CAROLINA",
    "Morgan State": "OREGON STATE",
    "North Dakota": "NORTH DAKOTA STATE",
    "South Dakota State": "NORTH DAKOTA STATE",
    "SE Louisiana": "LOUISIANA",
    "Southern Illinois": "NORTHERN ILLINOIS",
    "North Alabama": "SOUTH ALABAMA",
    "Western Carolina": "EAST CAROLINA",
    "Eastern Kentucky": "WESTERN KENTUCKY",
    "Jackson State": "JACKSONVILLE STATE",
}

# The ten tracked-vs-tracked games the Cal seam was dropping outright.
CAL_GAMES = [
    ("UCLA", "California"), ("Clemson", "California"), ("Stanford", "California"),
    ("Virginia Tech", "California"), ("Wake Forest", "California"), ("Pittsburgh", "California"),
    ("California", "NC State"), ("California", "SMU"), ("California", "Syracuse"),
    ("California", "Virginia"),
]


# --- the collisions -----------------------------------------------------------------------------

@pytest.mark.parametrize("school,used_to_become", sorted(KNOWN_COLLISIONS.items()))
def test_a_known_collision_never_resolves_into_the_fbs_universe(school, used_to_become):
    resolved = normalizer.normalize(school)
    assert resolved != used_to_become, (
        f"{school!r} resolved to {used_to_become!r} again — fuzzy matching is conferring FBS "
        f"membership, which fabricates games."
    )
    assert resolved not in get_fbs_canonical_names(), (
        f"{school!r} resolved to the FBS name {resolved!r} by some other route"
    )


def test_no_known_collision_reaches_the_tracked_universe():
    tracked = get_all_tracked_teams()
    leaks = {s: normalizer.normalize(s) for s in KNOWN_COLLISIONS
             if normalizer.normalize(s) in tracked}
    assert not leaks, f"names leaked into the tracked slate: {leaks}"


def test_fuzzy_matching_cannot_return_an_fbs_name_for_any_input():
    """The boundary itself, not just the 16 known cases — a 17th must fail closed too."""
    fbs = get_fbs_canonical_names()
    for probe in ("Samfordd", "Ohio Statee", "Gerogia", "Stanfrod", "Alabma State",
                  "Mississipi Valley", "Nrothwestern State", "Southrn"):
        result = normalizer._fuzzy_match(normalizer._clean_input(probe))
        assert result is None or result not in fbs, (
            f"fuzzy match conferred FBS membership on {probe!r} -> {result!r}"
        )


# --- structural impossibility -------------------------------------------------------------------

def test_a_self_matchup_is_structurally_impossible_in_a_normalized_slate():
    """`NORTH DAKOTA STATE @ NORTH DAKOTA STATE` was real, produced by two different FCS schools
    collapsing onto one FBS name. Assert the class, not that one instance."""
    from data.normalize.cfbd import normalize_games
    rows = [
        {"week": 7, "homeTeam": "North Dakota", "awayTeam": "South Dakota State"},
        {"week": 1, "homeTeam": "Southern", "awayTeam": "Southern Utah"},
        {"week": 1, "homeTeam": "Georgia", "awayTeam": "Clemson"},
    ]
    games = normalize_games(rows)
    assert all(g.home_team != g.away_team for g in games), \
        [(g.away_team, g.home_team) for g in games if g.home_team == g.away_team]


def test_the_committed_snapshot_contains_no_self_matchup():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    snap = root / "data" / "snapshots" / "2026_week_01" / "snapshot.json"
    if not snap.exists():
        pytest.skip("no committed snapshot")
    games = json.loads(snap.read_text())["data"]["games"]
    assert [g for g in games if g["home_team"] == g["away_team"]] == []


def test_no_fabricated_game_signature_survives_in_the_committed_snapshot():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    snap = root / "data" / "snapshots" / "2026_week_01" / "snapshot.json"
    if not snap.exists():
        pytest.skip("no committed snapshot")
    games = {(g["away_team"], g["home_team"])
             for g in json.loads(snap.read_text())["data"]["games"]}
    for sig in (("STANFORD", "UAB"), ("USC", "HOUSTON"), ("USC", "COLORADO STATE"),
                ("OREGON STATE", "ARIZONA STATE"), ("NORTH CAROLINA", "GEORGIA STATE"),
                ("NORTHWESTERN", "LOUISIANA TECH"), ("VIRGINIA TECH", "SOUTH CAROLINA"),
                ("STANFORD", "AUBURN"), ("MISSISSIPPI STATE", "SACRAMENTO STATE")):
        assert sig not in games, f"fabricated game {sig[0]} @ {sig[1]} is back"


# --- the Cal seam -------------------------------------------------------------------------------

def test_canonical_overrides_reach_the_runtime_alias_vocabulary():
    """They governed the registry BUILD only, so `normalize("California")` returned None and every
    Cal game was dropped. One source of truth, applied in both places."""
    for cfbd_spelling, canonical in CANONICAL_OVERRIDES.items():
        if canonical in get_fbs_canonical_names():
            assert normalizer.normalize(cfbd_spelling) == canonical, (
                f"CANONICAL_OVERRIDES has {cfbd_spelling!r} -> {canonical!r} but the normalizer "
                f"returns {normalizer.normalize(cfbd_spelling)!r}"
            )


@pytest.mark.parametrize("away,home", CAL_GAMES)
def test_cals_games_resolve_on_both_sides(away, home):
    ra, rh = normalizer.normalize(away), normalizer.normalize(home)
    tracked = get_all_tracked_teams()
    assert ra in tracked and rh in tracked, f"{away}@{home} -> {ra}@{rh}"


def test_cals_ten_games_are_present_in_the_committed_snapshot():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    snap = root / "data" / "snapshots" / "2026_week_01" / "snapshot.json"
    if not snap.exists():
        pytest.skip("no committed snapshot")
    games = {(g["away_team"], g["home_team"])
             for g in json.loads(snap.read_text())["data"]["games"]}
    expected = {(normalizer.normalize(a), normalizer.normalize(h)) for a, h in CAL_GAMES}
    missing = sorted(expected - games)
    assert not missing, f"Cal games still missing from the snapshot: {missing}"


def test_the_reconciler_reports_no_lost_tracked_game():
    """The defect class must be empty: `unresolved_team_name` means an FBS team's opponent could
    not be identified, i.e. a game we track is being lost."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    man = root / "data" / "snapshots" / "2026_week_01" / "manifest.json"
    if not man.exists():
        pytest.skip("no committed manifest")
    rec = json.loads(man.read_text()).get("reconciliation") or {}
    if not rec:
        pytest.skip("snapshot predates the detector")
    excluded = rec["excluded_from_normalization"]
    assert excluded["unresolved_team_name"] == [], excluded["unresolved_team_name"]
    assert excluded["by_reason"].get("unresolved_team_name", 0) == 0
