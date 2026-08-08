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

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from utils.season_calendar import (
    DEFAULT_PIPELINE_TIMEZONE,
    WeekInferenceError,
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
