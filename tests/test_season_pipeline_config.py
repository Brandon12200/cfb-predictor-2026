"""`season.json`'s `pipeline` block (SPEC §10.6, Phase 5).

Two jobs:

1. **Shape.** Every key is asserted here, so config that nothing reads cannot accumulate — the
   `pipeline` block is a live contract, not a scratchpad. `docs/PIPELINE.md` carries the
   key→consumer table; this test is what keeps it honest.
2. **Cron ↔ ET agreement.** The crons are duplicated into `.github/workflows/` because Actions
   cannot read this file, and a duplicated schedule is a schedule that drifts. Each `cron_utc` is
   re-derived here from its stated ET time under EDT. That check is not ceremonial: the Saturday
   20:23 ET capture is `23 0 * * 0` — **Sunday** in UTC — and an eyeballed cron gets that wrong.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "season.json").read_text())
PIPELINE = CONFIG.get("pipeline", {})

# Concrete EDT dates, one per weekday (2026-09-08 is a Tuesday — week 2 opens on it, D8).
REFERENCE_DAY = {
    "sun": 6, "mon": 7, "tue": 8, "wed": 9, "thu": 10, "fri": 11, "sat": 12,
}
CRON_DOW = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}

ALL_ENTRIES = [(job, entry)
               for job, entries in PIPELINE.get("schedule_et", {}).items()
               for entry in entries]


def test_pipeline_block_exists():
    assert PIPELINE, "season.json has no `pipeline` block (SPEC §10.6)"


def test_top_level_keys_are_exactly_the_documented_set():
    expected = {
        "_note", "timezone", "freeze_tag", "slate_filter", "schedule_et", "dst_note",
        "kickoff_windows_et", "jitter_slack_minutes", "data_quality", "odds_budget", "rehearsal",
    }
    assert set(PIPELINE) == expected, (
        "the pipeline block gained or lost a key. Every key must have a named consumer in "
        "docs/PIPELINE.md — add it there and here, or remove it."
    )


def test_scalar_values():
    assert PIPELINE["timezone"] == "America/New_York"
    # Deliberately NOT a hardcoded tag name. `freeze_tag` moves at every SPEC §3 exception, and a
    # literal here is one more place the retag has to remember — exactly what broke after
    # v2026-frozen-2. Assert the SHAPE and that it resolves to a real tag; identity is asserted
    # against git in tests/test_frozen_status.py.
    assert PIPELINE["freeze_tag"].startswith("v2026-frozen")
    assert PIPELINE["slate_filter"] == "fbs_vs_fbs"  # SPEC §16.1
    assert isinstance(PIPELINE["jitter_slack_minutes"], int)
    assert PIPELINE["jitter_slack_minutes"] > 0


def test_freeze_tag_matches_the_actual_tag():
    """A typo here would make the preflight's freeze assertion silently unresolvable."""
    import subprocess
    out = subprocess.run(["git", "rev-parse", "--verify", f"{PIPELINE['freeze_tag']}^{{commit}}"],
                         capture_output=True, cwd=str(ROOT))
    if out.returncode != 0:
        pytest.skip("git or the tag is unavailable (shallow checkout)")
    assert out.stdout.strip(), "freeze_tag does not resolve to a commit"


def test_schedule_covers_every_job():
    assert set(PIPELINE["schedule_et"]) == {"predict", "capture", "grade", "freeze_integrity"}


@pytest.mark.parametrize("job,entry", ALL_ENTRIES,
                         ids=[f"{j}-{e['time']}" for j, e in ALL_ENTRIES])
def test_entry_shape(job, entry):
    # Capture slots also name the window they precede and their kind (D44); the timing guard reads
    # both. No other job is time-critical, so no other job carries them.
    extra = {"precedes", "kind"} if job == "capture" else set()
    assert set(entry) == {"days", "time", "cron_utc"} | extra
    assert entry["days"], "entry declares no days"
    hh, mm = entry["time"].split(":")
    assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
    assert len(entry["cron_utc"].split()) == 5, "cron must have 5 fields"


@pytest.mark.parametrize("job,entry", ALL_ENTRIES,
                         ids=[f"{j}-{e['time']}" for j, e in ALL_ENTRIES])
def test_cron_utc_matches_the_stated_et_time(job, entry):
    """Re-derive the cron from the ET time under EDT (the anchor documented in `dst_note`)."""
    minute, hour, _, _, dow = entry["cron_utc"].split()
    hh, mm = (int(x) for x in entry["time"].split(":"))

    if entry["days"] == ["daily"]:
        assert dow == "*", "a daily job must not pin a weekday"
    else:
        assert dow != "*", "a weekday job must pin its weekday"
    # NOTE: the cron weekday is deliberately NOT compared against `days` directly — for the
    # Saturday 20:23 ET capture the two legitimately differ (ET Sat = UTC Sun). The per-day
    # conversion below is the real check.

    for day in entry["days"]:
        if day == "daily":
            et = datetime(2026, 9, 9, hh, mm, tzinfo=ZoneInfo(PIPELINE["timezone"]))
        else:
            et = datetime(2026, 9, REFERENCE_DAY[day], hh, mm,
                          tzinfo=ZoneInfo(PIPELINE["timezone"]))
        utc = et.astimezone(UTC)
        assert (utc.hour, utc.minute) == (int(hour), int(minute)), (
            f"{job} {entry['time']} ET -> {utc:%H:%M} UTC, but cron says {hour}:{minute}"
        )
        if dow != "*":
            # cron weekday: 0=Sunday. Compare against the UTC weekday, which may differ from the
            # ET one — that is the whole point of this assertion.
            utc_cron_dow = (utc.weekday() + 1) % 7
            assert utc_cron_dow in {int(d) for d in dow.split(",")}, (
                f"{job} {entry['time']} ET on {day} falls on UTC weekday {utc_cron_dow}, "
                f"not in cron field '{dow}'"
            )


CAPTURE = PIPELINE.get("schedule_et", {}).get("capture", [])
# D44: the worst Saturday lateness observed through week 3 was 309 min. A guarantee slot must land
# before its window even at that lateness, so it sits at least 310 min ahead of it.
GUARANTEE_LEAD_MIN = 310


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@pytest.mark.parametrize("entry", CAPTURE, ids=[f"{'/'.join(e['days'])}-{e['time']}" for e in CAPTURE])
def test_capture_slot_precedes_a_real_window_on_every_day_it_runs(entry):
    assert entry["kind"] in {"guarantee", "best_effort"}
    for day in entry["days"]:
        assert entry["precedes"] in PIPELINE["kickoff_windows_et"].get(day, []), (
            f"{day} {entry['time']} precedes {entry['precedes']}, which is not a {day} kickoff window"
        )
    assert _minutes(entry["time"]) < _minutes(entry["precedes"]), "a slot must be before its window"


@pytest.mark.parametrize("entry", [e for e in CAPTURE if e["kind"] == "guarantee"],
                         ids=[f"{'/'.join(e['days'])}-{e['time']}" for e in CAPTURE if e["kind"] == "guarantee"])
def test_guarantee_slots_absorb_the_worst_observed_lateness(entry):
    lead = _minutes(entry["precedes"]) - _minutes(entry["time"])
    assert lead >= GUARANTEE_LEAD_MIN, (
        f"{entry['time']} is {lead} min before {entry['precedes']}; a guarantee slot needs "
        f"{GUARANTEE_LEAD_MIN}. At :23, 06:53 and 10:23 missed this by 2 minutes."
    )


def test_every_window_on_a_capture_day_has_exactly_one_guarantee_slot():
    """Tiers 1–2 of the D44 escalation fire only on a guarantee miss, so a window without one could
    never escalate, and a window with two would double-count."""
    days = {d for e in CAPTURE for d in e["days"]}
    for day in days:
        for window in PIPELINE["kickoff_windows_et"][day]:
            g = [e for e in CAPTURE if e["kind"] == "guarantee" and day in e["days"] and e["precedes"] == window]
            assert len(g) == 1, f"{day} {window}: {len(g)} guarantee slots"


def test_cron_strings_are_unique_so_the_triggering_slot_is_identifiable():
    """The guard maps `github.event.schedule` back to its entry, so no two entries may share a cron."""
    crons = [" ".join(e["cron_utc"].split()) for es in PIPELINE["schedule_et"].values() for e in es]
    assert len(crons) == len(set(crons))


def test_cron_minutes_are_never_top_of_hour():
    """Top-of-hour Actions crons are the most heavily delayed; the cadence deliberately avoids them."""
    for job, entry in ALL_ENTRIES:
        assert entry["cron_utc"].split()[0] != "0", f"{job} {entry['time']} is scheduled at :00"


def test_kickoff_windows_are_lists_of_times():
    for day, windows in PIPELINE["kickoff_windows_et"].items():
        assert day in CRON_DOW, day
        assert isinstance(windows, list) and windows
        for w in windows:
            hh, mm = w.split(":")
            assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59


def test_data_quality_thresholds():
    dq = PIPELINE["data_quality"]
    assert set(dq) == {"min_slate_games", "min_registry_teams", "min_snapshot_coverage_pct",
                       "on_breach", "_note"}
    assert set(dq["on_breach"]) == {"min_slate_games", "min_registry_teams",
                                    "min_snapshot_coverage_pct"}
    assert set(dq["on_breach"].values()) <= {"fail", "warn"}
    # The committed preseason manifest reports 39% coverage; a stricter floor fails every
    # August build, which is exactly the false alarm that trains an operator to ignore the gate.
    assert dq["min_snapshot_coverage_pct"] <= 39.0
    assert dq["on_breach"]["min_snapshot_coverage_pct"] == "warn"


def test_odds_budget_is_internally_consistent():
    b = PIPELINE["odds_budget"]
    assert set(b) == {"monthly_credits", "min_credits_capture", "min_credits_snapshot",
                      "expected_weekly_credits", "alert_below", "_note"}
    assert b["min_credits_snapshot"] > b["min_credits_capture"], (
        "the weekly snapshot is the week's foundation and must hold the higher floor"
    )
    assert b["alert_below"] < b["monthly_credits"]
    assert b["expected_weekly_credits"] * 5 < b["monthly_credits"], (
        "a month of the ratified cadence must fit inside the monthly tier with headroom"
    )


def test_expected_weekly_credits_matches_the_scheduled_capture_count():
    """One capture run = one Odds credit, plus one for the Tuesday snapshot build. If the cadence
    changes, this figure must move with it or the burn-rate alarm goes quietly wrong."""
    capture_runs = sum(len(e["days"]) for e in PIPELINE["schedule_et"]["capture"])
    assert PIPELINE["odds_budget"]["expected_weekly_credits"] == capture_runs + 1


def test_rehearsal_prefix():
    assert PIPELINE["rehearsal"]["branch_prefix"].endswith("/")
