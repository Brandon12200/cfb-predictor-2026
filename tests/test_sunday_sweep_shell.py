"""The Sunday sweep that closes D44's weekly `pipeline-late` issue — executed, not grepped.

D44's review left this as the one piece of new shell with no behavioural test (finding 14: "the
Sunday sweep's shell gets an extract-and-run test in the report PR"). It is worth executing rather
than reading, because its correctness lives in two `--jq` filters and a label query, and every
mistake it can make is silent: sweeping a rehearsal drill's issue into a live grade, closing an
issue with the wrong tally, or closing none at all while reporting success.

**How this runs the real thing.** The step's `run:` block is lifted out of `weekly-grade.yml` by
step name and executed under `bash -e -o pipefail`, as Actions runs it, with `gh` replaced by a stub
that serves canned issues and applies the step's own `--jq` filters through **real jq** — so the
filters under test are the ones that run in production, not a paraphrase. `_assert_parsed` guards
against a parser that finds nothing making every case pass vacuously.

**Caveat (HANDOFF_REHEARSALS §(g).1):** this proves the script behaves; it does not prove the step's
`if:` or its `env:` wiring, which are YAML the runner evaluates. Those are asserted separately in
`tests/test_d44_capture_escalation.py`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "weekly-grade.yml"
STEP_NAME = "Close the week's late-capture issue with its tally"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="jq is required to apply the step's own --jq filters faithfully (present on the runners)",
)

_GH_STUB = r"""#!/usr/bin/env bash
# Enough of `gh issue` for this step: list/view apply the caller's --jq filter to canned JSON with
# real jq, exactly as gh does; comment/close are recorded rather than performed.
#
# One deliberate simplification: `--json <fields>` is ignored, so the full canned object reaches the
# filter rather than a projection of it. Immaterial for this step — both of its filters name fields
# the canned issues carry — but a future step whose filter depends on field scoping would need it
# (review of this PR).
set -u
sub="${2:-}"
num="${3:-}"
filter=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [ "${args[$i]}" = "--jq" ]; then filter="${args[$((i + 1))]}"; fi
done
case "$sub" in
  list)
    jq -r "$filter" "$ISSUES_JSON" ;;
  view)
    jq -r --argjson n "$num" '.[] | select(.number == $n)' "$ISSUES_JSON" | jq -r "$filter" ;;
  comment)
    printf 'comment %s %s\n' "$num" "${5:-}" >> "$CALL_LOG" ;;
  close)
    printf 'close %s\n' "$num" >> "$CALL_LOG"
    if [ "${CLOSE_FAILS:-}" = "$num" ]; then exit 1; fi ;;
  *)
    echo "unexpected gh call: $*" >&2; exit 64 ;;
esac
"""


def _steps() -> list[dict]:
    """The grade job's steps as {name, if, run}, parsed by indentation.

    Same approach as `tests/test_catch_up_clv_gate.py`: PyYAML is not a declared dependency, this
    file has one job, its steps sit at a fixed indent, and a `run: |` block is every following line
    indented deeper than the step's keys.
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
        i += 1
    return steps


def _sweep_script() -> str:
    step = next(s for s in _steps() if s.get("name") == STEP_NAME)
    script = step["run"]
    assert "${{" not in script, "an unsubstituted expression would make these tests vacuous"
    return script


def test_the_parser_finds_the_real_sweep_step():
    """Without this, a parser returning nothing would make every case below pass on an empty script."""
    names = [s.get("name") for s in _steps()]
    assert STEP_NAME in names
    script = _sweep_script()
    assert "gh issue close" in script and "pipeline-late" in script and "late-miss" in script
    assert "set -euo pipefail" in script


def _issue(number: int, *, week: str | None = "04", rehearsal: bool = False,
           misses: int = 0, comments: int = 0) -> dict:
    labels = [{"name": "pipeline-late"}, {"name": "stage:capture"}]
    if week:
        labels.append({"name": f"week:{week}"})
    if rehearsal:
        labels.append({"name": "rehearsal"})
    body = "late-miss" if misses else "a late capture"
    extra = [{"body": "late-miss"} for _ in range(max(0, misses - 1))]
    return {"number": number, "labels": labels, "body": body,
            "comments": extra + [{"body": "noise"} for _ in range(comments)]}


def _run(tmp_path: Path, issues: list[dict], *, mode: str = "live", week: str = "05",
         close_fails: str = "") -> tuple[int, list[str], str]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "gh"
    stub.write_text(_GH_STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    issues_json = tmp_path / "issues.json"
    issues_json.write_text(json.dumps(issues))
    log = tmp_path / "calls.log"
    log.touch()
    (tmp_path / "step.sh").write_text(_sweep_script())
    env = {**os.environ,
           "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "ISSUES_JSON": str(issues_json), "CALL_LOG": str(log), "CLOSE_FAILS": close_fails,
           "GH_TOKEN": "stub", "IN_WEEK": week, "IN_MODE": mode}
    proc = subprocess.run(["bash", str(tmp_path / "step.sh")], env=env, cwd=tmp_path,
                          capture_output=True, text=True)
    return proc.returncode, log.read_text().splitlines(), proc.stdout + proc.stderr


def test_a_live_grade_closes_the_live_issue_and_leaves_the_rehearsal_one(tmp_path):
    rc, calls, _ = _run(tmp_path, [_issue(11, misses=2), _issue(12, rehearsal=True, misses=1)])
    assert rc == 0
    assert [c for c in calls if c.startswith("close")] == ["close 11"]
    assert not any(" 12" in c for c in calls), "a live grade must not touch a rehearsal issue"


def test_a_rehearsal_grade_closes_only_the_rehearsal_issue(tmp_path):
    """The filter has to work in both directions: `--label` is AND-only with no negation, so a live
    query matches rehearsal issues too, and the jq post-filter is what keeps them apart."""
    rc, calls, _ = _run(tmp_path, [_issue(11, misses=2), _issue(12, rehearsal=True, misses=1)],
                        mode="rehearsal")
    assert rc == 0
    assert [c for c in calls if c.startswith("close")] == ["close 12"]


def test_the_tally_counts_every_late_miss_marker_in_the_body_and_comments(tmp_path):
    rc, calls, _ = _run(tmp_path, [_issue(11, misses=3, comments=2)])
    comment = next(c for c in calls if c.startswith("comment"))
    assert "3 guarantee slot(s) missed their window" in comment
    assert rc == 0


def test_the_comment_names_the_issue_week_not_the_grading_week(tmp_path):
    """The sweep closes EVERY open late issue, so the issue being closed is often not the week being
    graded — reading the week off the issue's own label is what keeps the note truthful."""
    rc, calls, _ = _run(tmp_path, [_issue(11, week="04", misses=1)], week="06")
    comment = next(c for c in calls if c.startswith("comment"))
    assert "Week 04 captures are complete" in comment
    assert "week 06 Sunday grade" in comment


def test_an_issue_with_no_week_label_still_closes_with_a_readable_week(tmp_path):
    rc, calls, _ = _run(tmp_path, [_issue(11, week=None, misses=1)])
    assert rc == 0
    comment = next(c for c in calls if c.startswith("comment"))
    assert "Week ? captures are complete" in comment, comment


def test_no_open_issues_is_a_clean_no_op(tmp_path):
    rc, calls, _ = _run(tmp_path, [])
    assert rc == 0 and calls == []


def test_a_failing_close_fails_the_step(tmp_path):
    """`set -euo pipefail`: a sweep that could not close an issue must not report success, or the
    issue stays open and the next Sunday reports a tally nobody asked for."""
    rc, calls, _ = _run(tmp_path, [_issue(11, misses=1)], close_fails="11")
    assert rc != 0
    assert any(c.startswith("close 11") for c in calls)
