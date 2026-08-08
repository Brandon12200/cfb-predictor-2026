"""The workflow files agree with `season.json`, and carry the settings the design depends on.

The crons live in two places — `season.json` (readable by our code, documented with the intended
ET time) and `.github/workflows/` (readable by Actions, which cannot read our config). A duplicated
schedule is a schedule that drifts, and the drift would be silent: the workflow keeps running, just
at the wrong time, and nobody notices until a close is captured after kickoff.

Parsed with regex rather than a YAML library on purpose: this project is deliberately
minimal-dependency (SPEC §13), and D24 declined a YAML parser for exactly this reason. Every
assertion here is a line-level fact that regex reads reliably.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
ACTIONS = ROOT / ".github" / "actions"
PIPELINE = json.loads((ROOT / "season.json").read_text())["pipeline"]

# season.json job name -> workflow file
JOB_FILE = {
    "predict": "weekly-predict.yml",
    "capture": "daily-capture.yml",
    "grade": "weekly-grade.yml",
    "freeze_integrity": "freeze-integrity.yml",
}
CADENCE_FILES = ["weekly-predict.yml", "daily-capture.yml", "weekly-grade.yml"]
ALL_FILES = [*CADENCE_FILES, "ci.yml", "freeze-integrity.yml"]

_CRON = re.compile(r'^\s*-\s*cron:\s*["\'](?P<cron>[^"\']+)["\']', re.M)


def _norm(cron: str) -> str:
    """Collapse whitespace so `23  0 * * 0` and `23 0 * * 0` compare equal."""
    return " ".join(cron.split())


def crons_in(filename: str) -> set[str]:
    return {_norm(m.group("cron")) for m in _CRON.finditer((WORKFLOWS / filename).read_text())}


def configured(job: str) -> set[str]:
    return {_norm(e["cron_utc"]) for e in PIPELINE["schedule_et"][job]}


@pytest.mark.parametrize("filename", ALL_FILES)
def test_workflow_exists(filename):
    assert (WORKFLOWS / filename).exists(), f"missing .github/workflows/{filename}"


@pytest.mark.parametrize("action", ["cfb-setup", "cfb-commit", "report-failure", "clear-failure"])
def test_composite_exists(action):
    assert (ACTIONS / action / "action.yml").exists()


@pytest.mark.parametrize("job,filename", sorted(JOB_FILE.items()))
def test_workflow_crons_match_season_json(job, filename):
    assert crons_in(filename) == configured(job), (
        f"{filename} and season.json pipeline.schedule_et.{job} disagree. "
        f"Both must change together, or the pipeline runs at a time nothing documents."
    )


def test_ci_is_not_scheduled():
    assert crons_in("ci.yml") == set(), "CI is event-driven, not scheduled"


@pytest.mark.parametrize("filename", ALL_FILES)
def test_every_job_checks_out_with_tags(filename):
    """fetch-depth: 0 is mandatory everywhere.

    Without tags `git describe --always` silently returns a bare SHA, which would stamp every
    claim of the season with a commit hash where the freeze tag belongs, and the freeze assertion
    cannot resolve the tag at all. cfb-setup and the preflight both refuse in that state; this
    keeps the refusal from ever being reached.
    """
    text = (WORKFLOWS / filename).read_text()
    checkouts = text.count("actions/checkout@")
    assert checkouts >= 1
    # The `no-rehearsal-merge` job legitimately needs no history.
    expected = checkouts - (1 if filename == "ci.yml" else 0)
    assert text.count("fetch-depth: 0") == expected, (
        f"{filename}: {checkouts} checkout(s) but {text.count('fetch-depth: 0')} with fetch-depth 0"
    )


@pytest.mark.parametrize("filename", CADENCE_FILES)
def test_cadence_workflows_share_one_concurrency_group(filename):
    """All three push to the same branch, so they must serialize against each other."""
    text = (WORKFLOWS / filename).read_text()
    assert "group: cfb-pipeline-${{ github.ref }}" in text


@pytest.mark.parametrize("filename", CADENCE_FILES)
def test_cadence_runs_are_never_cancelled(filename):
    """Cancelling can tear a run between an Odds spend and record_quota, or between two of the
    three Sunday commits. A queued run is always better than a torn one."""
    assert "cancel-in-progress: false" in (WORKFLOWS / filename).read_text()


@pytest.mark.parametrize("filename", ALL_FILES)
def test_every_job_has_a_timeout(filename):
    """cancel-in-progress: false without a timeout means one hung job blocks the whole cadence."""
    text = (WORKFLOWS / filename).read_text()
    assert text.count("timeout-minutes:") >= text.count("runs-on:")


@pytest.mark.parametrize("filename", CADENCE_FILES)
def test_cadence_workflows_report_and_clear_failures(filename):
    text = (WORKFLOWS / filename).read_text()
    assert "actions/report-failure" in text and "if: failure()" in text
    assert "actions/clear-failure" in text and "if: success()" in text


@pytest.mark.parametrize("filename", CADENCE_FILES)
def test_cadence_workflows_can_write_artifacts_and_issues(filename):
    text = (WORKFLOWS / filename).read_text()
    assert "contents: write" in text and "issues: write" in text


def test_ci_is_read_only():
    assert "contents: read" in (WORKFLOWS / "ci.yml").read_text()


def test_the_claim_commit_stages_only_predictions():
    """The pre-registration artifact stands alone: no report, snapshot or graded file rides in the
    commit whose timestamp is the evidence (D22)."""
    text = (WORKFLOWS / "weekly-predict.yml").read_text()
    block = text.split("paths: data/predictions", 1)
    assert len(block) == 2, "the predictions commit step is missing"
    line = block[1].splitlines()[0].strip()
    assert line == "", f"predictions are staged alongside something else: 'data/predictions{line}'"


def test_snapshot_is_committed_before_predictions_are_built():
    """model_version is `git describe --dirty`: an uncommitted snapshot in the tree would stamp
    every claim of the week `-dirty`. The ordering is the fix, so it is pinned."""
    text = (WORKFLOWS / "weekly-predict.yml").read_text()
    assert text.index("paths: data/snapshots") < text.index("Build predictions")


def test_grade_commits_reports_separately_from_outcomes():
    """A rendering never rides with an outcome (D23) — it is what keeps `git log -- reports/`
    readable as a regeneration history."""
    text = (WORKFLOWS / "weekly-grade.yml").read_text()
    for tier in ("paths: data/results", "paths: data/graded", "paths: reports"):
        assert text.count(tier) == 1, f"{tier} staged more or less than once"


def test_report_commit_is_gated_until_the_lean_split_lands():
    """D36: an unsplit season headline over a 5.57:1 structural home skew repeats D17, and
    publishing it automatically every Sunday is worse than publishing nothing."""
    text = (WORKFLOWS / "weekly-grade.yml").read_text()
    assert "report_gate" in text
    assert "steps.report_gate.outputs.ready == 'true'" in text


def test_the_gate_opens_exactly_when_attribution_gains_the_split():
    """The gate greps analytics/attribution.py for `edge_direction`, so it must be closed NOW and
    must open on its own when the split lands — not need a second edit someone could forget."""
    text = (WORKFLOWS / "weekly-grade.yml").read_text()
    assert 'grep -q "edge_direction" analytics/attribution.py' in text
    have_split = "edge_direction" in (ROOT / "analytics" / "attribution.py").read_text()
    assert not have_split, (
        "analytics/attribution.py now has edge_direction — the D36 gate has served its purpose. "
        "Remove the gate step from weekly-grade.yml and delete this assertion."
    )
