"""Preflight, snapshot-quality and SP+ watch (Phase 5).

The load-bearing property is the **two-severity split** (owner ruling, 2026-08-07): the freeze and
provenance checks ABORT before any spend or commit, and the timing check only WARNS. Collapsing
them either way is a real failure — abort-on-late turns a degraded capture into no capture, and
warn-on-drift lets an unfrozen model write a byte-immutable claim.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts.check_snapshot_quality import evaluate
from scripts.pipeline_preflight import (
    Preflight,
    check_freeze,
    check_model_version,
    check_secrets,
    check_timing,
    emit,
)

ROOT = Path(__file__).resolve().parent.parent
CAL = json.loads((ROOT / "season.json").read_text())
ET = ZoneInfo(CAL["pipeline"]["timezone"])


# --- ABORT class: the freeze -------------------------------------------------------------------

def test_freeze_check_passes_against_the_real_tag():
    pf = Preflight()
    check_freeze(pf, CAL["pipeline"]["freeze_tag"])
    if pf.aborts and "not in this checkout" in pf.aborts[0]:
        pytest.skip("freeze tag unavailable (shallow checkout)")
    assert pf.aborts == []
    assert len(pf.notes) == 2  # factors/ and engine/


def test_freeze_check_aborts_when_the_tag_is_missing():
    """A shallow checkout cannot prove the freeze, and must not be allowed to proceed."""
    pf = Preflight()
    check_freeze(pf, "v-does-not-exist")
    assert len(pf.aborts) == 2
    assert all("fetch-depth: 0" in a for a in pf.aborts)
    assert pf.warns == []


# --- ABORT class: provenance -------------------------------------------------------------------

def test_model_version_check_passes_against_the_real_tag():
    pf = Preflight()
    check_model_version(pf, CAL["pipeline"]["freeze_tag"])
    assert pf.aborts == []


def test_model_version_aborts_on_a_bare_sha(monkeypatch):
    """The shallow-checkout failure mode: `git describe --always` returns a commit hash, which
    would stamp every claim of the season with a SHA where the freeze tag belongs."""
    import scripts.pipeline_preflight as pp
    monkeypatch.setattr(pp, "model_version", lambda: "b7a4a33")
    pf = Preflight()
    check_model_version(pf, "v2026-frozen")
    assert len(pf.aborts) == 1 and "fetch-depth: 0" in pf.aborts[0]


def test_model_version_aborts_when_unknown(monkeypatch):
    import scripts.pipeline_preflight as pp
    monkeypatch.setattr(pp, "model_version", lambda: "unknown")
    pf = Preflight()
    check_model_version(pf, "v2026-frozen")
    assert len(pf.aborts) == 1


def test_describe_suffix_is_accepted():
    """`v2026-frozen-8-gb7a4a33` is the NORMAL post-tag form and must not abort — freeze-exempt
    commits legitimately move HEAD past the tag all season (D-6/F3)."""
    import scripts.pipeline_preflight as pp
    pf = Preflight()
    original = pp.model_version
    try:
        pp.model_version = lambda: "v2026-frozen-8-gb7a4a33"
        check_model_version(pf, "v2026-frozen")
    finally:
        pp.model_version = original
    assert pf.aborts == []


# --- ABORT class: secrets ----------------------------------------------------------------------

@pytest.mark.parametrize("role,expected", [
    ("capture", ["ODDS_API_KEY"]),
    ("grade", ["CFBD_API_KEY"]),
    ("predict", ["CFBD_API_KEY", "ODDS_API_KEY"]),
])
def test_missing_secrets_abort(role, expected, monkeypatch):
    for name in ("CFBD_API_KEY", "ODDS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    pf = Preflight()
    check_secrets(pf, role)
    assert len(pf.aborts) == len(expected)
    for name in expected:
        assert any(name in a for a in pf.aborts)


def test_blank_secret_counts_as_missing(monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "   ")
    pf = Preflight()
    check_secrets(pf, "capture")
    assert len(pf.aborts) == 1


# --- WARN class: timing (D44) -------------------------------------------------------------------
#
# Every case below is one of the shapes the week 1-3 measurement found the old check got wrong,
# replayed from the real run history: the Saturday 10:23 slot of 2026-09-12 fired at 13:15 and was
# reported as "74 min of slack before the 15:30 ET window"; the 20:23 slot fired Sunday 00:58 and was
# scored against Sunday's 13:00 window; and every Sunday grade warned. The crons are now the D44
# ones, so the replays use D44 slots firing with the same lateness.

SAT = "50 10 * * 6"        # Sat 06:50 ET, guarantee, precedes 12:00
SAT_BEST = "20 13 * * 6"   # Sat 09:20 ET, best-effort, precedes 12:00
SAT_LATE = "50 23 * * 6"   # Sat 19:50 ET, best-effort, precedes 22:30
SAT_G4 = "20 21 * * 6"     # Sat 17:20 ET, guarantee, precedes 22:30


def _t(pf, now, schedule, role="capture", event="schedule"):
    return check_timing(pf, CAL, now, role=role, event_name=event, schedule=schedule)


def test_a_guarantee_miss_warns_annotates_and_never_aborts():
    """Aborting a late capture converts a degraded observation into no observation."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 12, 5, tzinfo=ET), SAT)   # 06:50 slot, 315 min late
    assert v.status == "missed" and v.guarantee_miss
    assert pf.aborts == []
    assert len(pf.warns) == 1 and "missed its 12:00 ET window by 5 min" in pf.warns[0]
    assert pf.annotations == pf.warns
    assert emit(pf, "capture", 4, quiet=True) == 0


def test_a_miss_is_judged_against_its_own_window_not_a_later_one():
    """The old check reported this shape as healthy slack before the NEXT window."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 13, 15, tzinfo=ET), SAT)   # after 12:00, before 15:30
    assert v.status == "missed" and v.window_et.strftime("%H:%M") == "12:00"
    assert not any("15:30" in n for n in pf.notes)


def test_a_best_effort_miss_is_tier_zero_only():
    """Owner ruling 2026-09-15: a best-effort slot is designed to miss about four times in ten."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 12, 30, tzinfo=ET), SAT_BEST)
    assert v.status == "missed" and not v.guarantee_miss
    assert pf.warns == [] and pf.annotations == []
    assert any("best-effort" in n for n in pf.notes)


def test_a_slot_that_fires_after_midnight_is_judged_on_its_own_et_date():
    """Sat 19:50 firing Sun 00:58 must be a miss of SATURDAY's 22:30 window, not slack before Sunday's."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 27, 0, 58, tzinfo=ET), SAT_LATE)
    assert v.status == "missed"
    assert v.slot_et.date().isoformat() == "2026-09-26" and v.window_et.date().isoformat() == "2026-09-26"


def test_an_on_time_run_records_its_margin_and_does_not_warn():
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 17, 40, tzinfo=ET), SAT_G4)   # 20 min late, 290 min to spare
    assert v.status == "on_time" and v.margin_min == 290
    assert pf.warns == []
    assert any("290 min before the 22:30 ET window" in n for n in pf.notes)


def test_a_late_run_before_its_window_is_late_not_missed():
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 20, 0, tzinfo=ET), SAT_G4)    # 160 min late, still before 22:30
    assert v.status == "late" and pf.warns == []


# --- B1: timing is WARN-only, so nothing in the guard may abort a capture -----------------------
#
# The guard runs in the preflight, BEFORE the fetch. An exception there fails cfb-setup and the
# capture never happens: a timing check deciding there is no observation at all, which inverts the
# severity split the module exists to keep. Found by an adversarial review of the D44 PR, which
# demonstrated an uncaught ValueError escaping `main()`.

def test_a_corrupt_lines_store_warns_and_the_capture_still_proceeds(tmp_path, monkeypatch):
    import scripts.pipeline_preflight as pp
    (tmp_path / "data" / "lines").mkdir(parents=True)
    (tmp_path / "data" / "lines" / "2026_week_04.json").write_text('{"A@B": {"kickoff"')  # truncated
    monkeypatch.setattr(pp, "ROOT", tmp_path)
    pf = Preflight()
    v = check_timing(pf, CAL, datetime(2026, 9, 26, 12, 5, tzinfo=ET), role="capture",
                     event_name="schedule", schedule=SAT, week=4, year=2026)
    assert v.status == "missed" and v.guarantee_miss, "the verdict still stands"
    assert any("could not be read" in w for w in pf.warns)
    assert emit(pf, "capture", 4, quiet=True) == 0, "a corrupt store must not fail the preflight"


def test_an_unparseable_kickoff_warns_and_the_capture_still_proceeds(tmp_path, monkeypatch):
    import scripts.pipeline_preflight as pp
    (tmp_path / "data" / "lines").mkdir(parents=True)
    (tmp_path / "data" / "lines" / "2026_week_04.json").write_text(
        json.dumps({"A@B": {"kickoff": "not-a-timestamp"}}))
    monkeypatch.setattr(pp, "ROOT", tmp_path)
    pf = Preflight()
    v = check_timing(pf, CAL, datetime(2026, 9, 26, 12, 5, tzinfo=ET), role="capture",
                     event_name="schedule", schedule=SAT, week=4, year=2026)
    assert v.status == "missed"
    assert any("could not be read" in w for w in pf.warns)
    assert emit(pf, "capture", 4, quiet=True) == 0


def test_any_failure_inside_the_verdict_is_a_warning_not_a_raise(monkeypatch):
    """Whatever breaks — the slot maths, the config shape, an unreadable file — the capture runs."""
    import scripts.pipeline_preflight as pp

    def boom(*a, **k):
        raise ValueError("anything at all")

    monkeypatch.setattr(pp, "evaluate_timing", boom)
    pf = Preflight()
    v = pp.check_timing(pf, CAL, datetime(2026, 9, 26, 12, 5, tzinfo=ET), role="capture",
                        event_name="schedule", schedule=SAT, week=4, year=2026)
    assert v.status == "unknown_slot"
    assert len(pf.warns) == 1 and "could not judge this run" in pf.warns[0]
    assert pf.annotations == pf.warns
    assert emit(pf, "capture", 4, quiet=True) == 0


def test_the_preflight_exits_zero_when_the_guard_breaks(monkeypatch, tmp_path):
    """End to end through main(): the adversarial review's exact reproduction."""
    import scripts.pipeline_preflight as pp
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("CFB_EVENT_SCHEDULE", SAT)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setattr(pp, "_games_in_window", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("torn file")))
    assert pp.main(["--role", "capture", "--week", "4", "--skip-secrets"]) == 0


def test_grade_and_other_roles_are_not_time_critical():
    """Every Sunday grade warned under the old check (6 of 6), 15+ min after a 12:47 slot."""
    for role in ("grade", "predict", "freeze"):
        pf = Preflight()
        v = _t(pf, datetime(2026, 9, 20, 15, 0, tzinfo=ET), "47 16 * * 0", role=role)
        assert v.status == "not_time_critical" and pf.warns == []


def test_a_manual_capture_is_not_judged():
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 23, 0, tzinfo=ET), "", event="workflow_dispatch")
    assert v.status == "manual" and pf.warns == []


def test_a_scheduled_run_with_no_cron_warns_instead_of_passing_as_manual():
    """Empty `github.event.schedule` on a scheduled run is wiring drift (D39 class), and every D44
    tier would go silent. It must not look like a harmless manual run (D44 audit)."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 13, 0, tzinfo=ET), "")
    assert v.status == "unknown_slot" and len(pf.warns) == 1 and pf.annotations == pf.warns
    assert "no github.event.schedule" in pf.warns[0]


def test_a_run_more_than_a_day_late_is_still_matched_to_its_own_weekday():
    """Wed-Fri crons are one line per weekday. With a shared `3,4,5` line, a Wednesday slot firing
    Thursday afternoon would have matched Thursday's slot and reported on time (D44 audit)."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 24, 14, 0, tzinfo=ET), "50 17 * * 3")   # Wed slot, fired Thu 14:00
    assert v.slot_et.strftime("%a %Y-%m-%d") == "Wed 2026-09-23" and v.status == "missed"


def test_an_unknown_cron_warns_about_drift():
    pf = Preflight()
    v = _t(pf, datetime(2026, 9, 26, 13, 0, tzinfo=ET), "23 14 * * 6")   # the retired 10:23 slot
    assert v.status == "unknown_slot" and len(pf.warns) == 1


def test_the_tuesday_slot_is_judged():
    pf = Preflight()
    v = _t(pf, datetime(2026, 10, 6, 19, 10, tzinfo=ET), "50 17 * * 2")
    assert v.status == "missed" and v.guarantee_miss and v.window_et.strftime("%a %H:%M") == "Tue 19:00"


def test_after_the_dst_flip_the_slot_is_an_hour_earlier_in_et():
    """17:50 UTC is 13:50 EDT but 12:50 EST (dst_note); the window stays 19:00 ET on the slot's date."""
    pf = Preflight()
    v = _t(pf, datetime(2026, 11, 7, 12, 55, tzinfo=ET), "50 17 * * 6")
    assert v.slot_et.strftime("%H:%M") == "12:50" and v.window_et.strftime("%H:%M") == "19:00"
    assert v.status == "on_time"


def test_games_in_the_window_come_from_the_week_lines(tmp_path, monkeypatch):
    import scripts.pipeline_preflight as pp
    (tmp_path / "data" / "lines").mkdir(parents=True)
    (tmp_path / "data" / "lines" / "2026_week_04.json").write_text(json.dumps({
        "A@B": {"kickoff": "2026-09-26T16:00:00Z"},   # 12:00 ET: in the 12:00 window
        "C@D": {"kickoff": "2026-09-26T19:30:00Z"},   # 15:30 ET: the next window
        "E@F": {"kickoff": "2026-09-25T23:00:00Z"},   # Friday
    }))
    monkeypatch.setattr(pp, "ROOT", tmp_path)
    pf = Preflight()
    v = check_timing(pf, CAL, datetime(2026, 9, 26, 12, 5, tzinfo=ET), role="capture",
                     event_name="schedule", schedule=SAT, week=4, year=2026)
    assert v.games == ["A@B"] and "A@B" in pf.warns[0]


def test_timing_outputs_feed_tier_two(tmp_path, monkeypatch):
    from scripts.pipeline_preflight import write_timing_outputs
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    pf = Preflight()
    write_timing_outputs(_t(pf, datetime(2026, 9, 26, 12, 5, tzinfo=ET), SAT))
    text = out.read_text()
    assert "timing_status=missed" in text and "timing_guarantee_miss=true" in text
    write_timing_outputs(_t(Preflight(), datetime(2026, 9, 26, 12, 30, tzinfo=ET), SAT_BEST))
    assert out.read_text().count("timing_guarantee_miss=false") == 1


def test_quiet_timing_outputs_do_not_touch_github_output(tmp_path, monkeypatch):
    from scripts.pipeline_preflight import write_timing_outputs
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    write_timing_outputs(_t(Preflight(), datetime(2026, 9, 26, 12, 5, tzinfo=ET), SAT), quiet=True)
    assert not out.exists()


def test_a_freeze_abort_does_set_the_exit_code():
    pf = Preflight()
    check_freeze(pf, "v-does-not-exist")
    assert emit(pf, "capture", 2, quiet=True) == 1


# --- the self-test must not write to the production report --------------------------------------

def test_quiet_suppresses_the_step_summary_write(tmp_path, monkeypatch):
    """`quiet` suppressed stdout but NOT the `$GITHUB_STEP_SUMMARY` write, so these very tests
    appended synthetic ABORT blocks to the real Actions run summary — a reader saw
    "ABORT: factors/ has drifted" against a tag that does not exist, produced by a passing test.
    Fixed, and pinned here because the fix had no regression test."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    pf = Preflight()
    check_freeze(pf, "v-does-not-exist")
    assert emit(pf, "capture", 2, quiet=True) == 1
    assert not summary.exists() or summary.read_text() == "", (
        "a quiet self-test wrote to the production step summary"
    )


def test_a_real_run_does_write_the_step_summary(tmp_path, monkeypatch):
    """The other direction: suppression must be scoped to quiet, not blanket."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    pf = Preflight()
    pf.note("hello")
    assert emit(pf, "capture", 2) == 0
    assert "hello" in summary.read_text()


def test_a_missing_freeze_tag_aborts_and_reaches_the_summary(tmp_path, monkeypatch):
    """The one abort that used to print to stdout and return, invisible on the summary page."""
    import scripts.pipeline_preflight as pp
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(pp, "load_calendar", lambda: {"pipeline": {"timezone": "America/New_York"}})
    assert pp.main(["--role", "capture", "--skip-secrets"]) == 1
    assert "freeze_tag" in summary.read_text()


# --- snapshot quality --------------------------------------------------------------------------

THRESHOLDS = CAL["pipeline"]["data_quality"]


def test_the_committed_preseason_snapshot_passes_its_own_thresholds():
    """Guards against a threshold set from in-season intuition that fails every August build."""
    manifest = json.loads(
        (ROOT / "data" / "snapshots" / "2026_week_01" / "manifest.json").read_text())
    breaches = evaluate(manifest["summary"], 138, THRESHOLDS)
    assert [b for b in breaches if b[0] == "fail"] == []


def test_low_coverage_warns_rather_than_fails():
    breaches = evaluate({"slate_games": 10, "coverage_pct": 5.0}, 138, THRESHOLDS)
    assert [(s, k) for s, k, _ in breaches] == [("warn", "min_snapshot_coverage_pct")]


def test_an_empty_slate_fails():
    breaches = evaluate({"slate_games": 0, "coverage_pct": 90.0}, 138, THRESHOLDS)
    assert ("fail", "min_slate_games") in [(s, k) for s, k, _ in breaches]


def test_a_collapsed_registry_fails():
    breaches = evaluate({"slate_games": 60, "coverage_pct": 90.0}, 12, THRESHOLDS)
    assert ("fail", "min_registry_teams") in [(s, k) for s, k, _ in breaches]


def test_the_real_registry_clears_the_floor():
    from data.team_registry import get_fbs_canonical_names
    assert len(get_fbs_canonical_names()) >= THRESHOLDS["min_registry_teams"]


# --- SP+ watch ---------------------------------------------------------------------------------
#
# Moved to tests/test_sp_watch_baseline.py. These assertions pinned the PRE-transition baseline
# ({"sp_ratings": 0, "returning_production": 0}), which SPEC §3 exception 1 superseded when
# returning production published at 136 rows. Keeping a second, overlapping set of baseline
# assertions here is how the two would drift — the dedicated file is the single home.


def test_a_torn_quota_ledger_warns_and_the_capture_still_proceeds(monkeypatch):
    """`report_budget` is reporting only, and it reads a committed ledger a killed run could have
    left torn. Like the timing check, it must never be the thing that stops a capture. The pre-spend
    guard is unaffected: it lives in fetch_lines and reads the balance itself."""
    import scripts.pipeline_preflight as pp

    def torn(*a, **k):
        raise ValueError("Expecting property name enclosed in double quotes")

    monkeypatch.setattr(pp, "last_remaining", torn)
    pf = Preflight()
    pp.report_budget(pf, CAL, "capture")
    assert pf.aborts == []
    assert len(pf.warns) == 1 and "could not be reported" in pf.warns[0]
    assert emit(pf, "capture", 4, quiet=True) == 0
