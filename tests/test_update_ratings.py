"""Ratings-export tests (D13): the derived `data/ratings/` artifact is well-formed,
embeds the snapshot_id, and is byte-reproducible from a snapshot."""

from __future__ import annotations

import json

from engine.matchup_pricer import build_ratings_export
from scripts.update_ratings import write_ratings


def _snapshot():
    games = [
        {"week": 1, "home_team": "A", "away_team": "B", "home_points": 31,
         "away_points": 10, "completed": True, "start_date": "2026-09-05T16:00:00Z"},
        {"week": 2, "home_team": "C", "away_team": "A", "home_points": 14,
         "away_points": 17, "completed": True, "start_date": "2026-09-12T16:00:00Z"},
    ]
    return {
        "meta": {"snapshot_id": "deadbeef", "week": 3, "year": 2026,
                 "built_at": "2026-09-15T12:00:00Z"},
        "data": {"games": games, "sp_ratings": {"A": {"rating": 10.0}},
                 "returning_production": {}},
    }


def test_export_structure_and_snapshot_id():
    exp = build_ratings_export(_snapshot())
    assert exp["meta"]["snapshot_id"] == "deadbeef"
    assert exp["meta"]["generated_at"] == "2026-09-15T12:00:00Z"  # frozen from snapshot
    assert exp["meta"]["engine"] == "power_ratings"
    assert "elo_config" in exp["meta"] and exp["meta"]["elo_config"]["k_early"]
    a = exp["ratings"]["A"]
    assert set(a) == {"rating", "rating_uncertainty", "games_played", "prior_source", "prior_elo"}
    assert a["games_played"] == 2 and a["prior_source"] == "sp+"
    # B never won; A won twice → A rated above B.
    assert exp["ratings"]["A"]["rating"] > exp["ratings"]["B"]["rating"]


def test_export_is_byte_reproducible(tmp_path):
    snap = _snapshot()
    p1 = write_ratings(build_ratings_export(snap), 2026, 3, base=tmp_path)
    first = p1.read_bytes()
    p2 = write_ratings(build_ratings_export(snap), 2026, 3, base=tmp_path)
    assert p2.read_bytes() == first  # deterministic + frozen clock → byte-identical


def test_export_written_json_is_sorted_and_loads(tmp_path):
    path = write_ratings(build_ratings_export(_snapshot()), 2026, 3, base=tmp_path)
    loaded = json.loads(path.read_text())
    teams = list(loaded["ratings"])
    assert teams == sorted(teams)  # deterministic key order
