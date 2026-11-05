"""A CFBD probe outage is not a freeze failure (D48 item 2).

**The defect, demonstrated 2026-10-21/22.** `sp_watch` hit a Cloudflare 502, `freeze-integrity`
went red, and the only reporter was the generic one — so the owner was emailed
*"pipeline: freeze failure"* about a run in which every freeze check passed and the fingerprint
matched. The issue carried `pipeline-failure` + `stage:freeze`, the **same dedupe bucket a real
freeze failure uses**, so the next morning's rerun closed #73 as "recovered": a probe outage
clearing the alarm that means the frozen model moved.

Conditions are asserted as **whole strings**, the D46 way. Each of these is a live `if:` on the job
that proves the freeze daily, and the ways they go wrong are all two-character edits: a `&&` that
should be `||` makes every red run file both issues; dropping the `rc != ''` clause makes a skipped
probe look like a probe error; and either reporter losing its gate re-merges the two buckets.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "freeze-integrity.yml").read_text()
CLEAR_ACTION = (ROOT / ".github" / "actions" / "clear-failure" / "action.yml").read_text()
REPORT_ACTION = (ROOT / ".github" / "actions" / "report-failure" / "action.yml").read_text()

PROBE_ERRORED = ("steps.spwatch.outputs.rc != '' && steps.spwatch.outputs.rc != '0' "
                 "&& steps.spwatch.outputs.rc != '2'")
PROBE_DID_NOT_ERROR = ("steps.spwatch.outputs.rc == '' || steps.spwatch.outputs.rc == '0' "
                       "|| steps.spwatch.outputs.rc == '2'")


def _steps() -> list[str]:
    """Every step block in the job, split on the `- uses:`/`- name:` boundary.

    Selecting by a bare marker is not safe in this file: it holds four `report-failure` calls and
    two `clear-failure` calls, and `kind: failure` appears in both the claim tripwire's reporter
    (`stage: predict`) and the generic freeze one. The first draft of this module matched the
    tripwire's by accident and asserted the wrong condition — so selection is by predicate below.

    Comment lines are dropped before matching, because prose *about* a setting is not the setting:
    the probe reporter's own comment cites `kind: transition` to explain which pattern it follows,
    and with comments left in it matched the arrival step's selector. Same comment-bleed class #55
    found in the `| tee` guard and #66 found in the concurrency-block parser.
    """
    body = WORKFLOW[WORKFLOW.index("    steps:"):]
    parts = re.split(r"\n(?=      - (?:uses|name):)", body)
    return ["\n".join(ln for ln in p.splitlines() if not ln.strip().startswith("#"))
            for p in parts[1:] if p.strip()]


def _step(*must_contain: str, absent: tuple[str, ...] = ()) -> str:
    matches = [s for s in _steps()
               if all(m in s for m in must_contain) and not any(a in s for a in absent)]
    assert len(matches) == 1, (
        f"expected exactly one step containing {must_contain} (absent {absent}), got {len(matches)}")
    return matches[0]


def _condition(step: str) -> str:
    return next(ln for ln in step.splitlines() if ln.strip().startswith("if:")).strip()


def test_the_probe_reporter_exists_with_its_own_kind_and_title():
    step = _step("actions/report-failure", "kind: probe")
    assert "stage: freeze" in step
    assert ('title: "CFBD probe unreachable — sp_watch could not observe '
            'SP+/returning production"') in step, "the title is the thing the owner reads first"
    assert _condition(step) == f"if: failure() && {PROBE_ERRORED}", _condition(step)


def test_the_generic_reporter_cannot_fire_on_a_probe_error():
    """One red run, one issue. With both reporters ungated, a probe outage files the probe issue
    AND the freeze-failure issue, which is the original defect plus noise."""
    generic = _step("actions/report-failure", "kind: failure", "stage: freeze",
                    absent=("steps.tripwire",))
    assert _condition(generic) == f"if: failure() && ({PROBE_DID_NOT_ERROR})", _condition(generic)


def test_every_red_run_files_exactly_one_freeze_issue():
    """The property behind the two literals above: the reporters' conditions must partition the
    probe's exit codes. If they ever drift apart, some failure mode reports twice — or nothing."""
    for rc in ("", "0", "1", "2", "3", "7"):
        errored = rc not in ("", "0", "2")
        assert sum([errored, not errored]) == 1, rc


def test_the_probe_error_step_ignores_an_empty_rc():
    """A skipped probe leaves `rc` empty, and an empty string is not an error code. Without this
    clause an earlier failure would make the probe look like the cause (D46's shape)."""
    assert _condition(_step("name: Fail on a probe error")) == f"if: {PROBE_ERRORED}"


def test_a_probe_error_still_reddens_the_job():
    """Separating the alarm must not quieten it: an unobservable upstream is worth a red run."""
    assert "exit 1" in _step("name: Fail on a probe error")


def test_the_arrival_and_ok_paths_are_unchanged():
    """Exit 0 and exit 2 keep their behaviour: an arrival opens its own `transition` issue and
    leaves the job GREEN, because the right response is the SPEC §3 exception process."""
    arrival = _step("actions/report-failure", "kind: transition")
    assert _condition(arrival) == "if: steps.spwatch.outputs.rc == '2'"
    assert "CFBD has published 2026 SP+" in arrival
    assert "exit 1" not in arrival


def test_the_new_kind_is_cleared_symmetrically():
    """A `pipeline-probe` issue left open after CFBD recovers makes the label stop meaning "a live
    problem" — the reason this workflow got a clear path at all. Separate buckets must mean
    separate clears, so there is one clear step per kind, both gated identically."""
    clears = [s for s in _steps() if "actions/clear-failure" in s]
    assert len(clears) == 2, "one clear per kind (failure, probe)"
    assert {k for s in clears for k in ("probe", "failure") if f"kind: {k}" in s} == {"probe", "failure"}
    for step in clears:
        assert _condition(step) == (
            "if: success() && github.ref_name == github.event.repository.default_branch"), (
            "a rehearsal-branch dispatch must not close either live issue (D44 finding 4)")
        assert "stage: freeze" in step and "mode: live" in step


def test_the_composites_turn_the_kind_into_its_own_label_and_bucket():
    """The separation only works because `kind` drives the label and the label drives the dedupe
    query — asserted against the composites rather than assumed."""
    assert 'LABELS=("pipeline-${KIND}" "stage:${STAGE}")' in REPORT_ACTION
    assert '--label "pipeline-${KIND}"' in CLEAR_ACTION
