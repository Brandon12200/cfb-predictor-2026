"""D44 wiring: the Tuesday snapshot-pending state, and escalation tier 2 from capture to grade.

The timing verdict itself is tested in `tests/test_pipeline_preflight.py`. What is pinned here is the
connective tissue, which D39 showed can be computed correctly and still never connected: a composite
output that is not declared reads as the empty string, and a gate on it silently never fires.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import scripts.fetch_lines as fl

ROOT = Path(__file__).resolve().parent.parent
CAPTURE = (ROOT / ".github/workflows/daily-capture.yml").read_text()
GRADE = (ROOT / ".github/workflows/weekly-grade.yml").read_text()
SETUP = (ROOT / ".github/actions/cfb-setup/action.yml").read_text()
REPORT = (ROOT / ".github/actions/report-failure/action.yml").read_text()


# --- exit 4: a scheduled Tuesday capture that beat the predict job ------------------------------

@pytest.mark.parametrize("event, cron, designed", [
    ("schedule", "50 17 * * 2", True),           # the Tuesday capture slot
    ("schedule", "50  17 * * 2", True),          # whitespace does not matter
    ("schedule", "50 17 * * 3", False),          # Wednesday's guarantee slot
    ("schedule", "", False),                     # a scheduled run with no cron: fail loud
    ("workflow_dispatch", "50 17 * * 2", False), # a manual run
    ("schedule", "17 13 * * 2", False),          # the Tuesday PREDICT cron is not a capture slot
])
def test_snapshot_pending_is_designed_only_for_the_scheduled_tuesday_slot(monkeypatch, event, cron, designed):
    """Keyed on the slot, not the clock. A weekday check turned a Tuesday capture delayed past
    midnight into a false failure, because it ran on Wednesday (D44 audit)."""
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("CFB_EVENT_SCHEDULE", cron)
    assert fl.snapshot_pending_is_designed() is designed


@pytest.mark.parametrize("designed, rc", [(True, fl.EXIT_SNAPSHOT_PENDING), (False, fl.EXIT_ERROR)])
def test_a_missing_snapshot_maps_to_4_or_1_and_spends_nothing(monkeypatch, designed, rc):
    def no_snapshot(week, year):
        raise fl.SnapshotNotFoundError("none")

    def must_not_fetch():
        raise AssertionError("no Odds client may be created without a snapshot")

    monkeypatch.setattr(fl, "load_snapshot", no_snapshot)
    monkeypatch.setattr(fl, "snapshot_pending_is_designed", lambda: designed)
    monkeypatch.setattr(fl, "last_remaining", must_not_fetch)
    assert fl.main(["--week", "6"]) == rc


def test_the_capture_step_receives_the_slot_that_fired_it():
    step = CAPTURE[CAPTURE.index("- name: Capture line observation"):CAPTURE.index("scripts/fetch_lines.py")]
    assert "CFB_EVENT_SCHEDULE: ${{ github.event.schedule }}" in step


def test_the_capture_workflow_treats_4_as_a_notice_and_1_as_a_failure():
    assert "if: steps.capture.outputs.rc == '4'" in CAPTURE
    fail = re.search(r"- name: Fail on a real error\n\s+if: (.+)", CAPTURE)
    assert fail and "rc != '4'" in fail.group(1) and "rc != '3'" in fail.group(1)
    commit = CAPTURE[CAPTURE.index("paths: data/lines") - 200:CAPTURE.index("paths: data/lines")]
    assert "if: steps.capture.outputs.rc == '0'" in commit, "nothing may be committed on exit 4"


# --- tier 2: open on a guarantee miss, close on Sunday ------------------------------------------

def test_the_timing_verdict_is_declared_on_the_composite():
    """Undeclared composite outputs read as '' (D39), which would disable tier 2 silently."""
    for name in ("timing_status", "timing_guarantee_miss", "timing_detail"):
        assert f"{name}:\n    value: ${{{{ steps.preflight.outputs.{name} }}}}" in SETUP
    assert "id: preflight" in SETUP
    assert "CFB_EVENT_SCHEDULE: ${{ github.event.schedule }}" in SETUP


def test_a_guarantee_miss_opens_the_weekly_late_issue():
    i = CAPTURE.index("kind: late")
    step = CAPTURE[CAPTURE.rindex("- uses: ./.github/actions/report-failure", 0, i):i + 400]
    assert "if: steps.setup.outputs.timing_guarantee_miss == 'true' && inputs.dry_run != true" in step
    assert 'cooldown-minutes: "0"' in step, "every guarantee miss must reach the tally"
    assert "late-miss" in step, "the Sunday tally counts this marker"
    assert "failure()" not in step.split("with:")[0], "tier 2 fires on a GREEN run"


def test_the_sunday_grade_closes_the_late_issue_with_the_tally():
    i = GRADE.index("- name: Close the week's late-capture issue with its tally")
    step = GRADE[i:GRADE.index("- uses: ./.github/actions/report-failure", i)]
    assert "if: success() && inputs.dry_run != true" in step
    assert "--label pipeline-late --label stage:capture" in step
    assert '--label "week:${IN_WEEK}"' not in step, (
        "the close must sweep every open late issue: one opened after its week's grade has no later "
        "Sunday that targets it (D44 audit)")
    assert 'test("late-miss")' in step and "gh issue close" in step
    assert "set -euo pipefail" in step


def test_one_run_can_report_two_kinds_without_an_artifact_name_collision():
    assert "name: pipeline-${{ inputs.stage }}-${{ inputs.kind }}-${{ github.run_id }}" in REPORT
