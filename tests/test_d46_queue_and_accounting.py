"""D46: the cadence group queues instead of discarding, and an exit-5 observation still lands.

Two changes, one theme — **a run that did work must not be thrown away silently.**

1. `queue: max` on the shared `cfb-pipeline` group. The default (`single`) keeps one pending run per
   group and cancels the older when a newer arrives; a cancelled run fires no `if: failure()`, so
   nothing reports it. `max` holds up to 100, FIFO, and may not be combined with
   `cancel-in-progress: true` — a workflow validation error, which would break every cadence run at
   once, so the pairing is asserted here rather than discovered on a Tuesday.
2. `fetch_lines` exit 5 (observation written, spend unrecorded) commits *before* the job fails.

**Caveat (HANDOFF_REHEARSALS §(g).1):** these read the workflow YAML as text. They prove the wiring
is written, not that Actions evaluates it — deletion and drift, not a present-but-wrong expression.
The behaviour behind it is tested directly: `tests/test_odds_ledger.py` for exit 5,
`tests/test_pipeline_preflight.py` for the timing verdict.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CADENCE = ["weekly-predict.yml", "daily-capture.yml", "weekly-grade.yml"]
CAPTURE = (WORKFLOWS / "daily-capture.yml").read_text()


def _concurrency_block(filename: str) -> str:
    """The `concurrency:` mapping's SETTINGS — a top-level key ends the block, and comments are
    dropped.

    Both halves are load-bearing. Reading the block rather than the file keeps `queue: max` in a
    step or another workflow's comment from satisfying an `in` check while the cadence ran on the
    default queue. Dropping comment lines keeps prose *about* a setting from reading as the setting:
    the first version of this module asserted `"cancel-in-progress: true" not in block` and failed
    against the comment explaining that `true` is the forbidden pairing. That is the comment-bleed
    class #55 found in the `| tee` guard, reproduced here by writing the test before the comment.
    """
    text = (WORKFLOWS / filename).read_text()
    # One block, or the extraction silently describes the first of several. A second top-level
    # `concurrency:` carrying `cancel-in-progress: true` otherwise survives every assertion here
    # (review of this PR).
    assert text.count("\nconcurrency:\n") == 1, f"{filename}: expected exactly one concurrency block"
    start = text.index("\nconcurrency:\n") + 1
    rest = text[start + len("concurrency:\n"):]
    end = len(rest)
    for m in re.finditer(r"^\S", rest, re.MULTILINE):
        end = m.start()
        break
    return "\n".join(ln for ln in rest[:end].splitlines() if not ln.strip().startswith("#"))


def _setting_indent(block: str, key: str) -> int:
    line = next(ln for ln in block.splitlines() if ln.strip().startswith(f"{key}:"))
    return len(line) - len(line.lstrip())


@pytest.mark.parametrize("filename", CADENCE)
def test_the_cadence_group_queues_rather_than_discarding(filename):
    block = _concurrency_block(filename)
    assert "group: cfb-pipeline-${{ github.ref }}" in block, "all three share one group"
    assert re.search(r"^\s+queue:\s*max\s*$", block, re.MULTILINE), (
        f"{filename}: without `queue: max` a pending run is silently replaced by a newer one"
    )
    # Indentation, because `^\s+` accepts any of it and an over-indented key is INVALID workflow
    # YAML — which would break every cadence run at once, the failure this module's docstring says
    # it exists to prevent. Nothing in this repository parses a workflow file (no PyYAML dependency,
    # no actionlint in CI), so this is the only thing standing between a mis-indented key and a
    # Tuesday. `actionlint` in `ci.yml` is the durable fix and is a drawer item (review of this PR).
    assert _setting_indent(block, "queue") == _setting_indent(block, "group"), (
        f"{filename}: `queue` must be a sibling of `group`; a deeper indent is invalid YAML"
    )


@pytest.mark.parametrize("filename", CADENCE)
def test_queue_max_is_never_paired_with_cancel_in_progress_true(filename):
    """GitHub rejects the combination with a workflow validation error — every run of it, instantly."""
    block = _concurrency_block(filename)
    assert "cancel-in-progress: false" in block
    assert "cancel-in-progress: true" not in block


def test_freeze_integrity_keeps_the_default_queue_deliberately():
    """Not an oversight: it is a daily idempotent check in its own group that writes no artifact, so
    a replaced pending run costs nothing the next day's run does not redo. Asserted so that a future
    reader sees a decision rather than an omission (D46)."""
    block = _concurrency_block("freeze-integrity.yml")
    assert "group: freeze-integrity" in block
    assert "queue:" not in block


# --- exit 5: commit, then fail -------------------------------------------------------------------

def _step_index(name: str) -> int:
    i = CAPTURE.find(name)
    assert i != -1, f"step not found: {name}"
    return i


def test_the_commit_runs_before_the_failure_step():
    """The ordering IS the fix. `cfb-commit` carries no status function, so it is implicitly
    `success()`: with "Fail on a real error" above it, an exit-5 run fails first and the commit is
    skipped — the observation stays on the runner and is discarded, which is what exit 1 did and why
    D44's finding 1 is PARTIAL rather than fixed."""
    assert _step_index("- uses: ./.github/actions/cfb-commit") < _step_index("- name: Fail on a real error")


def test_the_commit_step_fires_on_exit_five_as_well_as_zero():
    i = _step_index("- uses: ./.github/actions/cfb-commit")
    step = CAPTURE[i:CAPTURE.index("push:", i)]
    assert "steps.capture.outputs.rc == '0' || steps.capture.outputs.rc == '5'" in step
    assert "paths: data/lines data/quota" in step


def test_exit_five_still_fails_the_job():
    """5 is not a designed state. The failure step excludes 0, 3 and 4 — and NOTHING else.

    Pinned as the whole expression, not as a bag of substrings. Two edits survived the substring
    form (review of this PR), both of them two characters in a live workflow: appending
    `&& rc != '1'` turns a genuine fetch error green, and flipping the `&&`s to `||` makes the
    condition a tautology that fails every run — including `rc == 0`, which would also skip
    `clear-failure` and file a `stage:capture` issue on every scheduled capture.
    """
    fail = CAPTURE[_step_index("- name: Fail on a real error"):]
    cond = next(ln for ln in fail.splitlines() if ln.strip().startswith("if:")).strip()
    expected = ("if: steps.capture.outputs.rc != '0' && steps.capture.outputs.rc != '3' "
                "&& steps.capture.outputs.rc != '4'")
    assert cond == expected, f"the failure condition must be exactly:\n  {expected}\ngot:\n  {cond}"


def test_exit_five_says_so_in_the_log_and_the_summary():
    i = _step_index("- name: Accounting failed, observation kept (run will fail)")
    step = CAPTURE[i:_step_index("- uses: ./.github/actions/cfb-commit")]
    assert "if: steps.capture.outputs.rc == '5'" in step
    assert "GITHUB_STEP_SUMMARY" in step and "::warning::" in step


def test_an_exit_five_run_cannot_clear_a_real_failure_issue():
    """A run that could not record its spend has not recovered anything. `clear-failure` stays on
    `rc == '0'` — the same rule that keeps exits 3 and 4 from closing a live issue (D44, finding 6).

    Asserted as the exact condition. The substring form here and in
    `test_d44_capture_escalation.py` both let `rc == '0' || rc == '4'` through, so D44's finding 6
    was pinned by nothing despite two tests citing it (review of this PR).
    """
    i = CAPTURE.index("actions/clear-failure")
    cond = next(ln for ln in CAPTURE[i:].splitlines() if ln.strip().startswith("if:")).strip()
    assert cond == "if: steps.capture.outputs.rc == '0' && inputs.dry_run != true", cond


def test_the_failure_step_still_precedes_the_tier_two_late_issue():
    """D46 §(2) records as accepted that an exit-5 run which also missed its guarantee window does
    not open the weekly `pipeline-late` issue: the tier-2 step carries no status function, and the
    job has already failed. That is an ordering fact, and moving the tier-2 block above the failure
    step silently inverts it — it survived the whole suite before this assertion (review of this
    PR). Commit < fail < tier 2 is the invariant; the other half is pinned above.
    """
    assert _step_index("- name: Fail on a real error") < _step_index("kind: late")
