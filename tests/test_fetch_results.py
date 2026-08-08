"""`scripts/fetch_results.py` — the Sunday job's input (Phase 5).

The failure this file exists to prevent: if the results writer's `game_id` and the prediction's
`game_id` disagree, `analytics.grading` joins nothing and `scripts/grade.py` reports a fully
**ungraded** week — which reads as "no games have finished", not as an error. It would be found in
October, against claims that can never be re-made.

So the join is pinned end-to-end against the **committed** week-1 claims rather than asserted on
the id's string format: synthesized finals go through `build_results` into the real
`analytics.grading.build_graded`, and the graded count must come out right.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.grading import build_graded
from data.normalize.models import ScheduleGame
from scripts.fetch_results import RESULT_KEYS, build_results, merge_results

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "docs" / "examples" / "prediction_schema_v2_2026_week_01.json"

pytestmark = pytest.mark.skipif(not GOLDEN.exists(), reason="requires the committed golden slate")

FETCHED_AT = "2026-09-06T18:00:00+00:00"


@pytest.fixture
def predictions() -> dict:
    return json.loads(GOLDEN.read_text())


def _games_for(predictions_env: dict, *, week: int = 1, completed: bool = True,
               home: int = 24, away: int = 17) -> list[ScheduleGame]:
    """A synthetic completed season for exactly the predicted matchups."""
    return [
        ScheduleGame(week=week, home_team=p["home_team"], away_team=p["away_team"],
                     home_points=home if completed else None,
                     away_points=away if completed else None,
                     start_date="2026-09-05T23:00:00.000Z", completed=completed)
        for p in predictions_env["predictions"]
    ]


# --- the join ------------------------------------------------------------------------------------

def test_every_claim_gets_a_result_with_the_claim_s_own_game_id(predictions):
    env = build_results(predictions, _games_for(predictions),
                        week=1, year=2026, fetched_at=FETCHED_AT)
    claim_ids = {p["game_id"] for p in predictions["predictions"]}
    assert {r["game_id"] for r in env["results"]} == claim_ids


def test_results_actually_grade_through_the_real_grader(predictions):
    """The end-to-end pin: predictions ⋈ results must produce graded records, not an empty week."""
    env = build_results(predictions, _games_for(predictions),
                        week=1, year=2026, fetched_at=FETCHED_AT)
    graded = build_graded(predictions, env["results"], None, graded_at=FETCHED_AT)

    assert graded["meta"]["coverage"]["graded"] == len(predictions["predictions"])
    assert graded["meta"]["coverage"]["ungraded"] == []
    assert len(graded["graded"]) == len(predictions["predictions"])
    # Every graded record carries the finals it was graded against — not a null shell.
    assert all(r["home_score"] is not None and r["away_score"] is not None
               for r in graded["graded"])


def test_a_mismatched_id_would_be_caught(predictions):
    """Sanity on the pin itself: corrupt the ids and the grader must report an ungraded week."""
    env = build_results(predictions, _games_for(predictions),
                        week=1, year=2026, fetched_at=FETCHED_AT)
    for r in env["results"]:
        r["game_id"] = r["game_id"] + "-wrong"
    graded = build_graded(predictions, env["results"], None, graded_at=FETCHED_AT)
    assert graded["meta"]["coverage"]["graded"] == 0


def test_record_keys_are_exactly_the_documented_set(predictions):
    env = build_results(predictions, _games_for(predictions),
                        week=1, year=2026, fetched_at=FETCHED_AT)
    for r in env["results"]:
        assert set(r) == set(RESULT_KEYS)


def test_scores_are_carried_through(predictions):
    env = build_results(predictions, _games_for(predictions, home=31, away=10),
                        week=1, year=2026, fetched_at=FETCHED_AT)
    assert all(r["home_score"] == 31 and r["away_score"] == 10 for r in env["results"])


# --- honest-missing ------------------------------------------------------------------------------

def test_incomplete_games_are_pending_not_half_null(predictions):
    env = build_results(predictions, _games_for(predictions, completed=False),
                        week=1, year=2026, fetched_at=FETCHED_AT)
    assert env["results"] == []
    assert len(env["coverage"]["pending"]) == len(predictions["predictions"])


def test_a_claim_with_no_cfbd_game_is_unmatched(predictions):
    games = _games_for(predictions)[1:]  # drop one
    env = build_results(predictions, games, week=1, year=2026, fetched_at=FETCHED_AT)
    assert len(env["coverage"]["unmatched"]) == 1
    assert len(env["results"]) == len(predictions["predictions"]) - 1


def test_postponed_game_still_grades_and_is_flagged(predictions):
    """A game CFBD moved to a later week must still join its week-1 claim — and say so."""
    games = _games_for(predictions)
    games[0] = ScheduleGame(week=7, home_team=games[0].home_team, away_team=games[0].away_team,
                            home_points=21, away_points=14, completed=True)
    env = build_results(predictions, games, week=1, year=2026, fetched_at=FETCHED_AT)

    assert len(env["results"]) == len(predictions["predictions"])  # nothing lost
    moved = [r for r in env["results"] if r["completed_in_week"] == 7]
    assert len(moved) == 1
    assert moved[0]["game_id"] in env["coverage"]["postponed"]
    assert moved[0]["week"] == 1  # keyed to the claim, not to CFBD's week

    graded = build_graded(predictions, env["results"], None, graded_at=FETCHED_AT)
    assert graded["meta"]["coverage"]["graded"] == len(predictions["predictions"])


def test_a_rematch_does_not_overwrite_the_earlier_meeting(predictions):
    """Two meetings of the same pair: the week-1 claim must bind to the earlier one."""
    games = _games_for(predictions)
    first = games[0]
    games.append(ScheduleGame(week=13, home_team=first.home_team, away_team=first.away_team,
                              home_points=99, away_points=0, completed=True))
    env = build_results(predictions, games, week=1, year=2026, fetched_at=FETCHED_AT)
    rec = next(r for r in env["results"] if r["home_team"] == first.home_team)
    assert (rec["home_score"], rec["away_score"]) == (24, 17)


# --- append-only merge ---------------------------------------------------------------------------

def test_merge_into_nothing_adds_everything(predictions):
    fresh = build_results(predictions, _games_for(predictions),
                          week=1, year=2026, fetched_at=FETCHED_AT)
    merged, added = merge_results(None, fresh)
    assert added == len(fresh["results"]) and merged is fresh


def test_rerun_adds_nothing_and_is_a_no_op(predictions):
    fresh = build_results(predictions, _games_for(predictions),
                          week=1, year=2026, fetched_at=FETCHED_AT)
    merged, added = merge_results(fresh, fresh)
    assert added == 0
    assert merged["results"] == fresh["results"]


def test_an_existing_final_is_never_rewritten(predictions):
    """Append-only: a recorded score stays put even if the source later disagrees."""
    first = build_results(predictions, _games_for(predictions, home=24, away=17),
                          week=1, year=2026, fetched_at=FETCHED_AT)
    corrected = build_results(predictions, _games_for(predictions, home=0, away=0),
                              week=1, year=2026, fetched_at=FETCHED_AT)
    merged, added = merge_results(first, corrected)
    assert added == 0
    assert all(r["home_score"] == 24 for r in merged["results"])


def test_catch_up_appends_only_the_newly_completed(predictions):
    """The Sunday/Tuesday shape: half the slate finishes, then the rest."""
    early = _games_for(predictions)
    for g in early[5:]:
        g.completed, g.home_points, g.away_points = False, None, None

    sunday = build_results(predictions, early, week=1, year=2026, fetched_at=FETCHED_AT)
    assert len(sunday["results"]) == 5

    tuesday = build_results(predictions, _games_for(predictions),
                            week=1, year=2026, fetched_at=FETCHED_AT)
    merged, added = merge_results(sunday, tuesday)
    assert added == len(predictions["predictions"]) - 5
    assert len(merged["results"]) == len(predictions["predictions"])
    assert len({r["game_id"] for r in merged["results"]}) == len(merged["results"])
