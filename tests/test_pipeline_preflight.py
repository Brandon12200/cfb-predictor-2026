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


# --- WARN class: timing ------------------------------------------------------------------------

def test_a_late_run_warns_and_never_aborts():
    """Aborting a jittered capture converts a degraded observation into no observation."""
    pf = Preflight()
    # Saturday 2026-09-12, 23:30 ET — past every kickoff window for the day.
    check_timing(pf, CAL, datetime(2026, 9, 12, 23, 30, tzinfo=ET))
    assert pf.aborts == []
    assert len(pf.warns) == 1
    assert "Continuing deliberately" in pf.warns[0]


def test_an_early_run_records_its_slack():
    pf = Preflight()
    check_timing(pf, CAL, datetime(2026, 9, 12, 10, 23, tzinfo=ET))
    assert pf.aborts == [] and pf.warns == []
    assert any("slack before the 12:00 ET window" in n for n in pf.notes)


def test_timing_never_contributes_to_the_exit_code():
    pf = Preflight()
    check_timing(pf, CAL, datetime(2026, 9, 12, 23, 59, tzinfo=ET))
    assert emit(pf, "capture", 2, quiet=True) == 0


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
