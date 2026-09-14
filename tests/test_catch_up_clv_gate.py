"""The Tuesday catch-up must CLV-check every week it grades, and a disagreement must stop the job.

Owner ruling 2026-09-13 (PR D): `weekly-predict`'s catch-up loop grades earlier weeks and commits
append-only `data/graded` with no sign check. That is how 2026 week 1 reached 11/11 on 2026-09-08. The
same validator #60 put before `weekly-grade`'s commit (`scripts/check_clv.py`) goes here.

**These tests execute the step, not grep it.** HANDOFF_REHEARSALS §(g).1: string-presence-in-YAML
is not behaviour. The existing `weekly-grade` wiring test checks token order in the file text. That
would pass a check placed after the loop's `done` (checking only the last week), or one whose exit
status a `| tee` swallows. Here the real `run:` block is lifted out of the workflow and run under
`bash -e`, as Actions runs it, with `python` replaced by a stub that records each call and fails
on demand.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "weekly-predict.yml"
STEP_NAME = "Catch-up grade (Sunday/Monday finishers + postponements)"

_STUB = """#!/usr/bin/env bash
# Records "<script> <week> <year>" and exits with FAIL_RC when "<script>:<week>" equals FAIL_ON.
script=$(basename "$1"); shift
week=""; year=""
while [ $# -gt 0 ]; do
  case "$1" in --week) week=$2; shift ;; --year) year=$2; shift ;; esac
  shift
done
echo "$script $week $year" >> "$CALL_LOG"
if [ "${FAIL_ON:-}" = "$script:$week" ]; then exit "${FAIL_RC:-1}"; fi
exit 0
"""


def _steps() -> list[dict]:
    """The `predict` job's steps as {name, uses, if, continue-on-error, paths, run}.

    Parsed by indentation rather than with a YAML library: PyYAML is not a declared dependency, and
    this file has one job whose steps sit at a fixed indent. A step starts at `      - `, its keys
    sit at eight spaces, and a `run: |` block is every following line indented deeper than eight, or
    blank. `_assert_parsed` guards against the parser silently finding nothing.
    """
    lines = WORKFLOW.read_text().splitlines()
    steps: list[dict] = []
    i = next(k for k, ln in enumerate(lines) if ln.strip() == "steps:") + 1
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("      - "):
            steps.append({})
            ln = "        " + ln[len("      - "):]
        if steps and (m := re.match(r"^ {8}([\w-]+):\s*(.*)$", ln)):
            key, val = m.group(1), m.group(2).strip()
            if key == "run" and val.startswith("|"):
                body, j = [], i + 1
                while j < len(lines) and (not lines[j].strip() or lines[j].startswith(" " * 10)):
                    body.append(lines[j][10:])
                    j += 1
                steps[-1]["run"] = "\n".join(body).rstrip() + "\n"
                i = j
                continue
            steps[-1][key] = val.strip('"')
        elif steps and (m := re.match(r"^ {10}paths:\s*(.*)$", ln)):
            steps[-1]["paths"] = m.group(1).strip()
        i += 1
    return steps


def test_the_step_parser_finds_the_real_steps():
    """Without this, a parser that found nothing would make the fail-closed test pass vacuously."""
    steps = _steps()
    names = [s.get("name") for s in steps]
    assert STEP_NAME in names and "Build predictions" in names
    assert len(steps) >= 12
    assert any(s.get("paths") == "data/predictions" for s in steps)
    assert "for W in" in steps[_catch_up_index(steps)]["run"]


def _catch_up_index(steps: list[dict]) -> int:
    return next(i for i, s in enumerate(steps) if s.get("name") == STEP_NAME)


def _run(tmp_path: Path, weeks: str, fail_on: str = "", fail_rc: int = 1) -> tuple[int, list[str]]:
    """Run the catch-up step's real script. Returns (exit status, recorded calls)."""
    script = _steps()[_catch_up_index(_steps())]["run"]
    script = (script.replace("${{ steps.setup.outputs.grade_weeks }}", weeks)
                    .replace("${{ steps.setup.outputs.year }}", "2026"))
    assert "${{" not in script, "an unsubstituted expression would make this test vacuous"

    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "python"
    stub.write_text(_STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "calls.log"
    log.touch()
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "CALL_LOG": str(log), "RUNNER_TEMP": str(tmp_path),
           "FAIL_ON": fail_on, "FAIL_RC": str(fail_rc)}
    (tmp_path / "step.sh").write_text(script)
    proc = subprocess.run(["bash", "-e", str(tmp_path / "step.sh")], env=env, cwd=tmp_path,
                          capture_output=True, text=True)
    return proc.returncode, log.read_text().splitlines()


def test_every_graded_week_is_checked_right_after_it_is_graded(tmp_path):
    rc, calls = _run(tmp_path, "1 2")
    assert rc == 0
    assert calls == [
        "fetch_results.py 1 2026", "grade.py 1 2026", "check_clv.py 1 2026",
        "fetch_results.py 2 2026", "grade.py 2 2026", "check_clv.py 2 2026",
    ]


@pytest.mark.parametrize("week", ["1", "2"])
def test_a_disagreement_on_any_week_fails_the_step(tmp_path, week):
    """A check placed after the loop's `done` would still catch week 2, but it would miss week 1. A
    `| tee` that swallows the exit status would miss both."""
    rc, calls = _run(tmp_path, "1 2", fail_on=f"check_clv.py:{week}")
    assert rc != 0, f"check_clv failed on week {week} and the step still exited 0"
    assert calls[-1] == f"check_clv.py {week} 2026", "nothing may run after a disagreement"


def test_nothing_completed_yet_is_still_checked_and_still_green(tmp_path):
    """fetch_results exit 3 is a designed state. The loop carries on, and the check still runs. The real
    check exits 0 when nothing is graded (`test_check_clv.py`)."""
    rc, calls = _run(tmp_path, "3", fail_on="fetch_results.py:3", fail_rc=3)
    assert rc == 0
    assert calls == ["fetch_results.py 3 2026", "grade.py 3 2026", "check_clv.py 3 2026"]


def test_no_claimed_week_means_no_calls(tmp_path):
    rc, calls = _run(tmp_path, "")
    assert (rc, calls) == (0, [])


def test_a_failed_catch_up_stops_the_graded_commit_and_the_claim():
    """Fail-closed, by design. If only the commit were skipped, the modified graded files would stay in
    the working tree. Any that are tracked would make `model_version` (`git describe --dirty`) stamp
    the week's claim `-dirty`. So no step after the catch-up may run on failure except the failure reporter."""
    steps = _steps()
    i = _catch_up_index(steps)
    assert steps[i].get("continue-on-error", "false") == "false", "the catch-up must not swallow its failure"
    tolerant = ("always()", "failure()", "cancelled()")
    for s in steps[i + 1:]:
        cond = str(s.get("if", ""))
        label = s.get("name") or s.get("uses")
        if s.get("uses") == "./.github/actions/report-failure":
            assert "failure()" in cond
            continue
        assert not any(t in cond for t in tolerant), f"step {label!r} would run after a failed catch-up"
        assert s.get("continue-on-error", "false") == "false", f"step {label!r} tolerates failure"
    graded_commit = next(k for k, s in enumerate(steps) if "data/graded" in s.get("paths", ""))
    assert graded_commit == i + 1, "the graded commit must directly follow the checked catch-up"
