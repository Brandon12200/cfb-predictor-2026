"""The failure-signature shell is EXECUTED here, not just grepped for.

**Why this file exists.** The signature computation shipped in a form that crashed its own step:
`grep` exits 1 on no match, `pipefail` propagated it, and a bare assignment is not a tested
condition — so `set -e` killed the step before the `:-` fallback applied. It failed on exactly the
branch it was written for (an issue already open), so a second, different-cause failure would have
produced **no notification at all** — worse than the throttled duplicate it replaced.

It shipped because the tests asserted *substrings in the YAML* and never ran the code. String
presence is not behaviour. So this file extracts the real block between the `sig-begin`/`sig-end`
markers in the action and runs it under the same `set -euo pipefail` the composite uses, against
the log shapes that actually occur.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / ".github" / "actions" / "report-failure" / "action.yml"


def signature_block() -> str:
    """The live block from the action — extracted, never re-typed, so it cannot drift."""
    body = ACTION.read_text()
    assert "# --- sig-begin" in body and "# --- sig-end ---" in body, (
        "the sig markers are gone; this test would silently stop testing the real code"
    )
    block = body.split("# --- sig-begin", 1)[1].split("\n", 1)[1].split("# --- sig-end ---", 1)[0]
    return textwrap.dedent(block)


def run_block(tmp_path: Path, log_contents: str | None) -> subprocess.CompletedProcess:
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "pipeline.log"
    if log_contents is not None:
        log.write_text(log_contents)
    script = (
        "set -euo pipefail\n"
        f'RUNNER_TEMP="{tmp_path}"\n'
        + signature_block()
        + '\nprintf "SIG=%s\\n" "$SIG"\n'
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)


pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash unavailable")


def sig_of(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, f"the block exited {result.returncode}: {result.stderr}"
    line = [ln for ln in result.stdout.splitlines() if ln.startswith("SIG=")]
    assert line, f"no SIG emitted; stdout={result.stdout!r} stderr={result.stderr!r}"
    return line[-1][4:]


# --- the crash cases ------------------------------------------------------------------------------

def test_a_log_with_no_error_shaped_line_does_not_crash(tmp_path):
    """The original bug. A perfectly ordinary log with no matching keyword killed the step."""
    r = run_block(tmp_path, "everything is fine\nnothing to see here\n")
    assert sig_of(r)


def test_a_missing_log_does_not_crash(tmp_path):
    """An early failure — checkout, or cfb-setup before any tee'd command — leaves no log at all,
    and `grep` exits 2 for a missing file."""
    r = run_block(tmp_path, None)
    assert sig_of(r) == "nosig" or sig_of(r)


def test_an_empty_log_does_not_crash(tmp_path):
    r = run_block(tmp_path, "")
    assert sig_of(r)


def test_a_whitespace_only_log_does_not_crash(tmp_path):
    r = run_block(tmp_path, "\n   \n\t\n")
    assert sig_of(r)


def test_lowercase_argparse_error_is_captured(tmp_path):
    """`pipeline_week.py: error: argument --week: invalid int value` — lowercase, and the exact
    shape the original case-sensitive pattern missed."""
    r = run_block(tmp_path, "pipeline_week.py: error: argument --week: invalid int value 'x'\n")
    assert sig_of(r) not in ("", "nosig")


# --- the behaviour it exists for ------------------------------------------------------------------

def test_the_same_failure_yields_the_same_signature(tmp_path):
    log = "::error::fetch_lines exited 1\n"
    a = sig_of(run_block(tmp_path / "a", log))
    b = sig_of(run_block(tmp_path / "b", log))
    assert a == b, "an identical failure must throttle, so its signature must be stable"


def test_a_different_failure_yields_a_different_signature(tmp_path):
    """The capture job's real history: missing secrets, then a rejected push two hours later."""
    secrets = sig_of(run_block(tmp_path / "s", "ABORT: ODDS_API_KEY is unset or empty\n"))
    push = sig_of(run_block(tmp_path / "p", "::error::push failed after 3 attempts\n"))
    assert secrets != push, "a changed failure mode must produce a changed signature"


def test_signatures_differ_when_only_the_fallback_line_differs(tmp_path):
    """Even with no error keyword, two different logs must not collide into one signature."""
    a = sig_of(run_block(tmp_path / "a", "ordinary line one\n"))
    b = sig_of(run_block(tmp_path / "b", "a completely different line\n"))
    assert a != b


def test_the_last_error_line_wins(tmp_path):
    """A run can log several errors; the final one is the proximate cause."""
    first = sig_of(run_block(tmp_path / "1", "::error::first thing\n"))
    both = sig_of(run_block(tmp_path / "2", "::error::first thing\n::error::second thing\n"))
    assert first != both


@pytest.mark.parametrize("marker", ["::error::", "fatal:", "Error:", "ABORT:", "Traceback"])
def test_each_error_shape_is_recognised(tmp_path, marker):
    r = run_block(tmp_path / marker.strip(":").replace(":", ""), f"{marker} something broke\n")
    assert sig_of(r) not in ("", "nosig")
