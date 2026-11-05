"""The pipeline's operational week resolver (Phase 5).

`resolve_week`/`infer_week_for_date` answer "which week's games are being played today". The
pipeline asks a different question — "which week am I working on" — and the two diverge exactly
where it hurts most: **the week-1 prediction run is the Tuesday before kickoff (2026-08-25), which
falls inside no game window**, so the game-window resolver raises and the first live cycle dies
before doing anything. These tests pin that divergence so the two resolvers can never be conflated.

The game-window calendar itself (`season.json` `weeks`, D8, CFBD-corroborated) is deliberately
unchanged — `test_resolve_week_still_raises_...` pins that too.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import scripts.pipeline_week as pw
from utils.season_calendar import (
    DEFAULT_PIPELINE_TIMEZONE,
    WeekInferenceError,
    claim_window_open,
    load_calendar,
    pipeline_timezone,
    pipeline_today,
    pipeline_week,
    resolve_week,
)

CAL = load_calendar()


# --- the failure this exists to fix -------------------------------------------------------------

@pytest.mark.parametrize("day", [
    date(2026, 8, 25),  # week-1 predict (Tuesday before kickoff)
    date(2026, 8, 26),  # week-1 captures, Wed
    date(2026, 8, 27),  # Thu
    date(2026, 8, 28),  # Fri
])
def test_week1_pipeline_dates_resolve_to_week_1(day):
    assert pipeline_week(day, CAL) == 1


@pytest.mark.parametrize("day", [date(2026, 8, 25), date(2026, 8, 28)])
def test_resolve_week_still_raises_on_those_dates(day):
    """The game-window resolver is unchanged — that is why a second resolver was needed."""
    with pytest.raises(WeekInferenceError):
        resolve_week(None, today=day, calendar=CAL)


# --- the rule: lowest-numbered week whose end >= today ------------------------------------------

@pytest.mark.parametrize("day,expected", [
    (date(2026, 8, 1), 1),    # before the season opens
    (date(2026, 8, 29), 1),   # kickoff Saturday
    (date(2026, 9, 7), 1),    # week-1 window closes (Monday)
    (date(2026, 9, 8), 2),    # week 2 opens
    (date(2026, 9, 13), 2),   # Sunday grade for week 2
    (date(2026, 9, 14), 3),   # Monday -> week 3
    (date(2026, 12, 12), 15), # final window closes
    (date(2026, 12, 13), 15), # clamped, never raises
    (date(2027, 3, 1), 15),   # far past the season, still clamped
])
def test_pipeline_week_rule(day, expected):
    assert pipeline_week(day, CAL) == expected


@pytest.mark.parametrize("day", [date(2026, 12, 14), date(2026, 12, 15), date(2026, 12, 20),
                                 date(2027, 1, 5)])
def test_after_the_final_grade_the_week_clamps_and_the_claim_window_stays_open(day):
    """The two facts D48's recorded fallback rests on, pinned so the record stays checkable.

    If the season-stop PR is not merged, every later run still resolves **week 15** (the clamp), and
    `claim_window_open(15)` is still **True** — the gate tests only the lead edge, `start - today <=
    CLAIM_LEAD_DAYS`, and week 15 started 2026-12-07, so it never closes behind the week. Neither
    fact is a defect; together they are why the stop had to be the removal of the trigger rather
    than anything the pipeline could decide for itself. **What actually protects the claim is the
    weld** — `write_predictions` refuses an existing claim with `FileExistsError`
    (`tests/test_pipeline_cycle.py::test_the_writer_refuses_to_overwrite_an_existing_claim`), and
    the workflow skips the step anyway on `prediction_exists`.
    """
    assert pipeline_week(day, CAL) == 15
    assert claim_window_open(15, day, CAL) is True


def test_pipeline_week_never_raises_across_the_whole_season():
    day = date(2026, 8, 1)
    while day <= date(2027, 1, 15):
        wk = pipeline_week(day, CAL)
        assert 1 <= wk <= 15
        day = date.fromordinal(day.toordinal() + 1)


def test_pipeline_week_is_monotonic_non_decreasing():
    """A pipeline week must never go backwards as the season advances."""
    day, previous = date(2026, 8, 1), 0
    while day <= date(2026, 12, 31):
        wk = pipeline_week(day, CAL)
        assert wk >= previous, f"{day} resolved to {wk} after {previous}"
        previous = wk
        day = date.fromordinal(day.toordinal() + 1)


def test_every_week_is_reachable():
    """No week is skipped — a gap would mean a slate never gets predicted."""
    reached = set()
    day = date(2026, 8, 1)
    while day <= date(2026, 12, 12):
        reached.add(pipeline_week(day, CAL))
        day = date.fromordinal(day.toordinal() + 1)
    assert reached == {int(w) for w in CAL["weeks"]}


# --- timezone: the UTC trap ---------------------------------------------------------------------

def test_pipeline_today_uses_et_not_the_runner_clock():
    """A Saturday-evening ET capture is already Sunday in UTC. Deriving the date from the runner's
    UTC clock would file the observation under the following week."""
    sat_evening_et = datetime(2026, 9, 12, 20, 23, tzinfo=ZoneInfo("America/New_York"))
    assert sat_evening_et.astimezone(ZoneInfo("UTC")).date() == date(2026, 9, 13)  # the trap
    assert pipeline_today(CAL, now=sat_evening_et) == date(2026, 9, 12)


def test_pipeline_timezone_defaults_when_the_block_is_absent():
    assert pipeline_timezone({"weeks": {}}) == DEFAULT_PIPELINE_TIMEZONE


def test_pipeline_timezone_reads_the_config_block():
    assert pipeline_timezone({"pipeline": {"timezone": "UTC"}}) == "UTC"


# --- D48: the catch-up loop only visits weeks that could still have a late finisher -------------
#
# The loop calls CFBD once per week it iterates. `gradable_weeks` is every claimed week, which put
# seven calls in front of the week-8 claim and would have put fourteen in front of week 15's — and
# #71 is one of those calls having failed the job that writes the claim. These pin the narrowing,
# and the first two are the cases the ruling names.

def _week_files(base, week, claim_ids, graded_ids=None, *, raw_graded=None):
    """Write a claim (and optionally a graded file) for `week` under `base`."""
    (base / "data" / "predictions").mkdir(parents=True, exist_ok=True)
    (base / "data" / "graded").mkdir(parents=True, exist_ok=True)
    (base / "data" / "predictions" / f"2026_week_{week:02d}.json").write_text(
        json.dumps({"meta": {"week": week}, "predictions": [{"game_id": g} for g in claim_ids]}))
    if raw_graded is not None:
        (base / "data" / "graded" / f"2026_week_{week:02d}.json").write_text(raw_graded)
    elif graded_ids is not None:
        (base / "data" / "graded" / f"2026_week_{week:02d}.json").write_text(
            json.dumps({"meta": {"week": week}, "graded": [{"game_id": g} for g in graded_ids]}))


@pytest.fixture()
def tmp_record(tmp_path, monkeypatch):
    """Point the resolver's directories at a scratch tree; the real record is read-only here."""
    monkeypatch.setattr(pw, "PREDICTIONS_DIR", tmp_path / "data" / "predictions")
    monkeypatch.setattr(pw, "GRADED_DIR", tmp_path / "data" / "graded")
    return tmp_path


def test_a_fully_graded_week_is_not_revisited(tmp_record):
    """The case the ruling names: every claimed game has a graded row, so there is nothing left to
    fetch and the loop must not spend a CFBD call on it."""
    _week_files(tmp_record, 1, ["a", "b"], graded_ids=["a", "b"])
    assert pw.gradable_weeks(1, 2026) == [1], "still gradable: Sunday re-renders it (#58)"
    assert pw.weeks_needing_grade(1, 2026) == []


def test_a_week_with_an_ungraded_game_is_revisited(tmp_record):
    _week_files(tmp_record, 1, ["a", "b"], graded_ids=["a"])
    assert pw.weeks_needing_grade(1, 2026) == [1]


def test_a_week_with_no_graded_file_at_all_is_revisited(tmp_record):
    _week_files(tmp_record, 1, ["a"])
    assert pw.weeks_needing_grade(1, 2026) == [1]


def test_an_unreadable_file_means_assume_there_is_work(tmp_record):
    """A week whose files will not parse is exactly a week somebody needs to look at. Skipping it as
    an optimisation would hide the problem behind the optimisation."""
    _week_files(tmp_record, 1, ["a"], raw_graded='{"graded": [{"game_id"')
    assert pw.weeks_needing_grade(1, 2026) == [1]


def test_a_postponed_game_keeps_its_week_in_the_set(tmp_record):
    """Correct, not a leak: a game that has not been played is the definition of a late finisher
    still to come, so that week keeps being checked."""
    _week_files(tmp_record, 1, ["played", "postponed"], graded_ids=["played"])
    assert pw.weeks_needing_grade(1, 2026) == [1]


def test_only_the_open_weeks_survive_a_realistic_season(tmp_record):
    for wk in (1, 2, 3):
        _week_files(tmp_record, wk, ["a", "b"], graded_ids=["a", "b"])
    _week_files(tmp_record, 4, ["a", "b"], graded_ids=["a"])
    _week_files(tmp_record, 5, ["a"])
    assert pw.gradable_weeks(5, 2026) == [1, 2, 3, 4, 5]
    assert pw.weeks_needing_grade(5, 2026) == [4, 5], "three CFBD calls saved out of five"


def test_the_resolver_emits_both_sets_so_each_consumer_reads_its_own(tmp_record):
    """`grade_weeks` stays the full set for Sunday's render loop; `catchup_weeks` is the narrowed
    one. Emitting only the narrow set would have silently retired #58's self-healing render."""
    _week_files(tmp_record, 1, ["a"], graded_ids=["a"])
    _week_files(tmp_record, 2, ["a"])
    out = pw.resolve(2, 2026, CAL)
    assert out["grade_weeks"] == "1 2"
    assert out["catchup_weeks"] == "2"
