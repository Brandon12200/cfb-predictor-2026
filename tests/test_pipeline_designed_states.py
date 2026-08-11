"""Designed states are not failures, and a dry run has no side effects.

Three defects found by the first live runs and the first dry-run smokes, pinned so they cannot
return. The theme is one the pipeline keeps re-teaching: **a working pipeline in an early-season
state must not look like a broken one.** Every false alarm spends the operator's trust in the
alarm, and the alarm is the only thing standing between a silent failure and the season.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.fetch_results import EXIT_ERROR, EXIT_NO_CLAIM, EXIT_NOTHING_COMPLETED

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CADENCE = ["weekly-predict.yml", "daily-capture.yml", "weekly-grade.yml"]


def wf(name: str) -> str:
    return (WORKFLOWS / name).read_text()


# --- item 7: "no claim yet" is a preseason state, not a failure ----------------------------------

def test_no_claim_has_its_own_exit_code():
    assert EXIT_NO_CLAIM == 4
    assert len({EXIT_ERROR, EXIT_NOTHING_COMPLETED, EXIT_NO_CLAIM}) == 3, "codes must be distinct"


def test_fetch_results_returns_no_claim_not_error(tmp_path, monkeypatch):
    """It returned EXIT_ERROR, so every preseason Sunday opened a failure issue (#36) for a
    pipeline that was working correctly."""
    import scripts.fetch_results as fr
    monkeypatch.setattr(fr, "PREDICTIONS_DIR", tmp_path)   # no claim for any week
    assert fr.main(["--week", "1", "--year", "2026"]) == EXIT_NO_CLAIM


def test_the_grade_workflow_treats_no_claim_as_a_notice():
    body = wf("weekly-grade.yml")
    assert "rc == '3' || steps.results.outputs.rc == '4'" in body
    assert "rc != '3' && steps.results.outputs.rc != '4'" in body, (
        "exit 4 must not reach the 'Fail on a real error' step"
    )


# --- item 8: a path that does not exist yet is not an error --------------------------------------

def test_the_commit_action_stages_only_existing_paths():
    """`git add` on a pathspec matching nothing exits 128; under `set -e` that killed the step.
    The Tuesday job stages `data/results data/graded` first, and neither exists until something has
    been graded — so the first live run would have died before building a snapshot."""
    body = (ROOT / ".github" / "actions" / "cfb-commit" / "action.yml").read_text()
    assert 'if [ -e "$P" ]; then EXISTING+=("$P"); fi' in body
    assert "git add -- \"${EXISTING[@]}\"" in body
    assert "git add -- ${{ inputs.paths }}" not in body, "the unguarded form is back"


def test_no_existing_paths_is_a_clean_no_op():
    body = (ROOT / ".github" / "actions" / "cfb-commit" / "action.yml").read_text()
    block = body.split("if [ ${#EXISTING[@]} -eq 0 ]; then", 1)[1][:300]
    assert "committed=false" in block and "exit 0" in block, (
        "an all-missing path set must report no-commit and succeed, not fail"
    )


def test_the_tuesday_job_still_stages_the_dirs_that_do_not_exist_yet():
    """The fix must not be 'stop staging them' — they are staged, just tolerated when absent."""
    body = wf("weekly-predict.yml")
    assert "paths: data/results data/graded" in body


# --- item 9: a dry run has NO issue side effects, in either direction -----------------------------

@pytest.mark.parametrize("workflow", CADENCE)
def test_a_dry_run_cannot_open_an_issue(workflow):
    """Observed: a failing dry-run smoke filed #38, labelled exactly like a live failure."""
    assert "if: failure() && inputs.dry_run != true" in wf(workflow)


@pytest.mark.parametrize("workflow", CADENCE)
def test_a_dry_run_cannot_close_an_issue(workflow):
    """**The worse half.** A PASSING dry run would have cleared a real, unresolved failure issue.
    Only run ordering avoided it when the live capture proof happened to run before any dry smoke —
    and sequencing is not a control."""
    assert "if: success() && inputs.dry_run != true" in wf(workflow)


@pytest.mark.parametrize("workflow", CADENCE)
def test_a_scheduled_run_still_reports(workflow):
    """`inputs.dry_run` is null on a schedule event, so `!= true` holds and the issue path stays
    live. If this ever inverted, real failures would go silent — the opposite failure."""
    body = wf(workflow)
    assert "if: failure() && inputs.dry_run != true" in body
    assert "if: failure() && inputs.dry_run == true" not in body


# --- item 1: a changed failure mode is never silenced by the cooldown ------------------------------

def test_the_cooldown_is_bypassed_when_the_failure_signature_changes():
    """The capture job failed on missing secrets, then two hours later on a rejected push — a
    completely different diagnosis, suppressed because it shared a stage and a week."""
    body = (ROOT / ".github" / "actions" / "report-failure" / "action.yml").read_text()
    assert "failure-signature:" in body
    assert "failure signature CHANGED — commenting despite the cooldown" in body


def test_the_cooldown_still_throttles_an_identical_repeat():
    body = (ROOT / ".github" / "actions" / "report-failure" / "action.yml").read_text()
    assert "SAME failure signature" in body and "IN_COOLDOWN" in body
