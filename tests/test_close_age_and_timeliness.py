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


def test_the_table_buckets_real_graded_weeks():
    """Measured against the committed artifacts, not a fixture: weeks 1–3 each carry stale closes
    and week 4, the first under D44, carries none."""
    def load(week: int) -> tuple[list[dict], dict[str, str]]:
        graded = json.loads((ROOT / "data" / "graded" / f"2026_week_{week:02d}.json").read_text())
        lines = json.loads((ROOT / "data" / "lines" / f"2026_week_{week:02d}.json").read_text())
        rows = [dict(r, clv=r.get("clv") if r.get("clv") is not None else 0.0) for r in graded["graded"]]
        return rows, kickoffs_from_lines(lines)

    rows, kicks = load(2)
    stale = next(b for b in close_age_table(rows, kicks)["buckets"] if b["bucket"] == ">12 h")
    assert stale["n"] == 4, "week 2 took four closes more than 12 h old"

    rows, kicks = load(BOUNDARY_WEEK)
    table = close_age_table(rows, kicks)
    assert next(b for b in table["buckets"] if b["bucket"] == "≤3 h")["n"] == 25
    assert all(b["n"] == 0 for b in table["buckets"] if b["bucket"] != "≤3 h")


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
