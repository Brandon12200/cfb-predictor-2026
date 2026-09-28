"""Close-age buckets (D44 §(4)) and capture timeliness (tiers 3–4) — `analytics/cadence.py`.

The measurement these render is the point of the cadence change, so the tests pin the measurement,
not the wording: the bucket edges, what an unknown age does, that the eras are never summed, and
that a week before the boundary is not judged against slots it never had.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.cadence import (
    BOUNDARY_WEEK,
    bucket_for,
    capture_runs,
    close_age_hours,
    close_age_table,
    escalation_due,
    guarantee_slots,
    kickoffs_from_lines,
    timeliness,
)
from analytics.reports import render_season, render_week

ROOT = Path(__file__).resolve().parent.parent
CAL = json.loads((ROOT / "season.json").read_text())


# --- close age ----------------------------------------------------------------------------------

def test_close_age_is_kickoff_minus_the_close_observation():
    assert close_age_hours("2026-09-26T16:00:00Z", "2026-09-26T13:00:00Z") == pytest.approx(3.0)


@pytest.mark.parametrize("hours, label", [
    (0.0, "≤3 h"), (2.99, "≤3 h"), (3.0, "≤3 h"),        # the edge belongs to the fresher bucket
    (3.01, "3–12 h"), (12.0, "3–12 h"), (12.01, ">12 h"), (16.7, ">12 h"),
])
def test_the_bucket_edges_are_closed_below(hours, label):
    assert bucket_for(hours) == label


@pytest.mark.parametrize("kickoff, close", [
    (None, "2026-09-26T13:00:00Z"), ("2026-09-26T16:00:00Z", None),
    ("not-a-date", "2026-09-26T13:00:00Z"), ("2026-09-26T16:00:00Z", ""),
])
def test_an_unknown_age_is_never_bucketed_as_a_fresh_one(kickoff, close):
    """Absence and freshness are different propositions — D40's lesson, in a new place. A missing
    kickoff must not land in `≤3 h` and flatter the cadence."""
    assert close_age_hours(kickoff, close) is None
    assert bucket_for(close_age_hours(kickoff, close)) is None


def test_rows_with_an_unknown_age_are_counted_separately_not_dropped():
    joined = [{"away_team": "A", "home_team": "B", "clv": 0.5, "close_as_of": "2026-09-26T13:00:00Z"}]
    table = close_age_table(joined, {})          # no kickoff for A@B
    assert table["n_unknown_age"] == 1 and table["n_clv"] == 0
    assert all(b["n"] == 0 for b in table["buckets"])


def test_a_neutral_lean_is_not_counted_in_a_clv_table():
    """CLV is null for a neutral lean (D22 f3) — counting it would pad the denominator of a CLV
    table with games that can never contribute one."""
    joined = [{"away_team": "A", "home_team": "B", "clv": None, "close_as_of": "2026-09-26T13:00:00Z"}]
    table = close_age_table(joined, {"A@B": "2026-09-26T16:00:00Z"})
    assert table["n_clv"] == 0 and table["n_unknown_age"] == 0
    # Excluded AND counted: the report states the gap, so nobody closes it by coercing a null to 0.0.
    assert table["n_no_clv"] == 1


def _week(week: int) -> tuple[list[dict], dict[str, str]]:
    """The committed graded rows and kickoffs for a week, **exactly as they are on disk.**

    An earlier version of this helper coerced a null CLV to 0.0 before calling `close_age_table`,
    which fabricated agreement between two different populations and would have let a regression
    that counted nulls as zeros keep passing (review of this PR). Nothing is coerced here.
    """
    graded = json.loads((ROOT / "data" / "graded" / f"2026_week_{week:02d}.json").read_text())
    lines = json.loads((ROOT / "data" / "lines" / f"2026_week_{week:02d}.json").read_text())
    return graded["graded"], kickoffs_from_lines(lines)


def test_the_table_buckets_real_graded_weeks():
    """The CLV-scoped table, over the committed artifacts, with no coercion.

    These counts are smaller than the week's graded count because a neutral lean has no CLV: week 2
    grades 16 with 1 neutral, week 4 grades 25 with 2. The raw close-age population is the test
    below; keeping them apart is the point.
    """
    rows, kicks = _week(2)
    table = close_age_table(rows, kicks)
    assert table["n_clv"] == 15 and table["n_no_clv"] == 1
    assert next(b for b in table["buckets"] if b["bucket"] == ">12 h")["n"] == 4, (
        "week 2 took four closes more than 12 h old")

    rows, kicks = _week(BOUNDARY_WEEK)
    table = close_age_table(rows, kicks)
    assert table["n_clv"] == 23 and table["n_no_clv"] == 2, (
        "25 graded, 2 neutral leans with no CLV — counted as excluded, never as zeros")
    assert next(b for b in table["buckets"] if b["bucket"] == "≤3 h")["n"] == 23
    assert all(b["n"] == 0 for b in table["buckets"] if b["bucket"] != "≤3 h")


def test_every_week_four_game_closed_within_three_hours_of_kickoff():
    """The cadence fact, over ALL graded games rather than the CLV-scoped subset.

    This is the number the cadence change is judged by, and it is computed straight from
    `close_age_hours` — not through `close_age_table`, whose population is deliberately narrower.
    Weeks 1–3 each carry four closes older than 12 h; week 4, the first under D44, carries none.
    """
    for week, over_12h in ((1, 4), (2, 4), (3, 4)):
        rows, kicks = _week(week)
        ages = [close_age_hours(kicks.get(f"{r['away_team']}@{r['home_team']}"), r.get("close_as_of"))
                for r in rows]
        assert all(a is not None for a in ages), f"week {week}: every graded game has a datable close"
        assert sum(1 for a in ages if a > 12) == over_12h

    rows, kicks = _week(BOUNDARY_WEEK)
    ages = [close_age_hours(kicks.get(f"{r['away_team']}@{r['home_team']}"), r.get("close_as_of"))
            for r in rows]
    assert len(ages) == 25 and all(a <= 3 for a in ages)
    assert max(ages) < 3, f"the stalest week-4 close was {max(ages):.2f} h old"


def test_a_season_wide_lookup_cannot_date_a_rematch_against_the_wrong_kickoff():
    """The same two teams can meet twice in one era. Keyed by matchup alone, the later week's
    kickoff overwrites the earlier one's and one meeting's close is aged against the other's game —
    silently, with no missing value to notice (review of this PR)."""
    rows = [
        {"week": 4, "away_team": "A", "home_team": "B", "clv": 0.5,
         "close_as_of": "2026-09-26T15:00:00Z"},        # 1 h before its own kickoff
        {"week": 12, "away_team": "A", "home_team": "B", "clv": 0.5,
         "close_as_of": "2026-11-28T15:00:00Z"},        # 1 h before its own kickoff
    ]
    scoped = {(4, "A@B"): "2026-09-26T16:00:00Z", (12, "A@B"): "2026-11-28T16:00:00Z"}
    table = close_age_table(rows, scoped)
    assert next(b for b in table["buckets"] if b["bucket"] == "≤3 h")["n"] == 2

    flat = {"A@B": "2026-11-28T16:00:00Z"}   # what a season-wide merge used to produce
    assert next(b for b in close_age_table(rows, flat)["buckets"]
                if b["bucket"] == ">12 h")["n"] == 1, (
        "the flat key dates week 4's close against week 12's kickoff — the shape being prevented")


def test_a_negative_age_is_counted_in_the_freshest_bucket_not_dropped():
    """`closing_observation` only selects pre-kickoff observations, so an observation timestamped
    after kickoff should not arise. If it ever does it is still counted — a dropped row would shrink
    the denominator and flatter the cadence, which is the opposite of what this table is for."""
    assert bucket_for(-0.5) == "≤3 h"
    rows = [{"week": 4, "away_team": "A", "home_team": "B", "clv": 0.1,
             "close_as_of": "2026-09-26T17:00:00Z"}]
    table = close_age_table(rows, {"A@B": "2026-09-26T16:00:00Z"})
    assert table["n_clv"] == 1 and table["n_unknown_age"] == 0


# --- timeliness ---------------------------------------------------------------------------------

def test_capture_runs_are_the_distinct_observation_timestamps():
    lines = {
        "A@B": {"kickoff": "x", "observations": [{"fetched_at": "2026-09-23T16:52:00Z"},
                                                 {"fetched_at": "2026-09-23T23:46:00Z"}]},
        "C@D": {"kickoff": "x", "observations": [{"fetched_at": "2026-09-23T16:52:00Z"}]},
    }
    assert len(capture_runs(lines, "America/New_York")) == 2, "one run appends to every game"


def test_a_week_before_the_boundary_is_not_judged(tmp_path):
    """Weeks 1–3 had no guarantee slots at all, so a miss count for them would describe a schedule
    that never ran (D44 §(2))."""
    t = timeliness(BOUNDARY_WEEK - 1, CAL, {})
    assert t["applies"] is False and "no guarantee slots" in t["reason"]


def test_a_slot_whose_run_beat_its_window_is_covered():
    runs = capture_runs({"A@B": {"observations": [
        {"fetched_at": "2026-09-23T16:52:00Z"},   # Wed 12:52 ET, before the 19:00 window
    ]}}, "America/New_York")
    slots = [s for s in guarantee_slots(BOUNDARY_WEEK, CAL, runs) if s["day"] == "wed"]
    assert slots and slots[0]["covered"] is True


def test_a_slot_whose_run_landed_after_its_window_missed():
    runs = capture_runs({"A@B": {"observations": [
        {"fetched_at": "2026-09-23T23:40:00Z"},   # Wed 19:40 ET, after the 19:00 window
    ]}}, "America/New_York")
    slots = [s for s in guarantee_slots(BOUNDARY_WEEK, CAL, runs) if s["day"] == "wed"]
    assert slots and slots[0]["covered"] is False


def test_a_slot_that_produced_no_run_at_all_is_a_miss():
    slots = guarantee_slots(BOUNDARY_WEEK, CAL, [])
    assert slots and all(s["covered"] is False for s in slots)
    assert all(s["run_et"] is None for s in slots)


def test_week_four_is_fully_covered_in_the_committed_record():
    lines = json.loads((ROOT / "data" / "lines" / f"2026_week_{BOUNDARY_WEEK:02d}.json").read_text())
    t = timeliness(BOUNDARY_WEEK, CAL, lines)
    assert t["applies"] and t["n_slots"] == 8 and t["n_missed"] == 0


@pytest.mark.parametrize("misses, due", [
    ({4: 0, 5: 0, 6: 0}, False),
    ({4: 1, 5: 0, 6: 0}, False),          # one week alone never escalates
    ({4: 1, 5: 2, 6: 0}, True),           # two of three
    ({4: 1, 5: 0, 6: 3}, True),           # not required to be consecutive
    ({4: 1, 5: 0, 6: 0, 7: 1}, False),    # four weeks apart: no 3-week window holds both
    ({4: 1, 5: 0, 6: 1, 7: 0}, True),     # weeks 4 and 6 share the window 4–6
])
def test_tier_four_fires_on_two_guarantee_misses_in_any_three_weeks(misses, due):
    assert escalation_due(misses)["due"] is due


# --- rendering ----------------------------------------------------------------------------------

def _envs(week: int) -> tuple[dict, dict, dict]:
    pred = json.loads((ROOT / "data" / "predictions" / f"2026_week_{week:02d}.json").read_text())
    graded = json.loads((ROOT / "data" / "graded" / f"2026_week_{week:02d}.json").read_text())
    lines = json.loads((ROOT / "data" / "lines" / f"2026_week_{week:02d}.json").read_text())
    return pred, graded, lines


def test_the_week_report_carries_both_blocks_and_names_its_era():
    pred, graded, lines = _envs(BOUNDARY_WEEK)
    out = render_week(pred, graded, lines=lines, calendar=CAL)
    assert "### CLV by close age (D44)" in out
    assert "### Capture timeliness (D44 tier 3)" in out
    assert "under the D44 capture cadence" in out
    assert "not triggered" in out


def test_a_pre_boundary_week_says_which_cadence_it_ran():
    pred, graded, lines = _envs(2)
    out = render_week(pred, graded, lines=lines, calendar=CAL)
    assert "pre-D44 cadence" in out
    assert "Not applicable" in out, "week 2 has no guarantee slots to judge"


def test_the_season_report_renders_the_eras_separately_and_never_sums_them():
    weeks, lines_by_week = [], {}
    for wk in (1, 2, 3, BOUNDARY_WEEK):
        pred, graded, lines = _envs(wk)
        weeks.append((pred, graded))
        lines_by_week[wk] = lines
    out = render_season(weeks, title="t", lines_by_week=lines_by_week, calendar=CAL)
    assert f"Weeks 01–{BOUNDARY_WEEK - 1:02d} — pre-D44 cadence" in out
    assert f"Week {BOUNDARY_WEEK:02d} onward — D44 cadence" in out
    assert "never summed" in out
    # The boundary is announced before the numbers, not buried under them.
    assert out.index(f"cadence changed at **week {BOUNDARY_WEEK:02d}**") < out.index("CLV by close age")


def test_a_report_without_a_line_store_omits_the_blocks_rather_than_faking_them():
    """The 2025 retro has no line store at all. A close-age table over absent kickoffs would be
    three empty buckets implying the question was asked and answered."""
    pred, graded, _ = _envs(BOUNDARY_WEEK)
    out = render_week(pred, graded)
    assert "CLV by close age" not in out and "Capture timeliness" not in out
