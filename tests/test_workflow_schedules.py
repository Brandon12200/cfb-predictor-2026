"""The workflow files agree with `season.json`, and carry the settings the design depends on.

The crons live in two places — `season.json` (readable by our code, documented with the intended
ET time) and `.github/workflows/` (readable by Actions, which cannot read our config). A duplicated
schedule is a schedule that drifts, and the drift would be silent: the workflow keeps running, just
at the wrong time, and nobody notices until a close is captured after kickoff.

Parsed with regex rather than a YAML library on purpose: this project is deliberately
minimal-dependency (SPEC §13), and D24 declined a YAML parser for exactly this reason. Every
assertion here is a line-level fact that regex reads reliably.

The parsing itself lives in `scripts/workflow_triggers.py`, shared with `scripts/verify_phase_5.py`:
after the season stop both guards depend on *not* finding a cron, which is the one direction where a
parser bug reports success. Two copies of that parser would have to agree forever; one copy with
mutation tests (`TestTheTriggerParserSeesEveryCronShape` below) does not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.workflow_triggers import (
    norm_cron,
    on_block,
    on_keys,
    quoted_crons,
    unattended_triggers,
)

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

def crons_in(filename: str) -> set[str]:
    """Every QUOTED cron in the file. Quoted only, because that is the form whose value can be
    compared against `season.json`; `unattended_triggers` is what detects a cron in any form."""
    return quoted_crons((WORKFLOWS / filename).read_text())


def triggers_in(filename: str) -> list[str]:
    return unattended_triggers((WORKFLOWS / filename).read_text())


def configured(job: str) -> set[str]:
    return {norm_cron(e["cron_utc"]) for e in PIPELINE["schedule_et"][job]}


@pytest.mark.parametrize("filename", ALL_FILES)
def test_workflow_exists(filename):
    assert (WORKFLOWS / filename).exists(), f"missing .github/workflows/{filename}"


@pytest.mark.parametrize("action", ["cfb-setup", "cfb-commit", "report-failure", "clear-failure"])
def test_composite_exists(action):
    assert (ACTIONS / action / "action.yml").exists()


@pytest.mark.parametrize("job,filename", sorted(JOB_FILE.items()))
def test_no_workflow_is_scheduled_after_the_season_stop(job, filename):
    """**Inverted by the season stop (D48, owner 2026-11-05).** This asserted that each workflow's
    crons equalled `season.json`'s. All four `schedule:` blocks are now deleted, so what has to hold
    is that **none of them comes back by accident** — a cron restored here would resume unattended
    writes to an append-only record after the season it describes has ended.

    `season.json`'s `pipeline.schedule_et` is deliberately **retained**: it is the record of the
    cadence that ran, it is still shape-checked by `tests/test_season_pipeline_config.py`, and the
    timing guard still reads it to name a slot. Retained config plus no cron is the intended state,
    which is why "they disagree" is no longer the failure.
    """
    assert crons_in(filename) == set(), (
        f"{filename} has regained a `schedule:` cron after the season stop. If the 2027 season is "
        f"being started deliberately, update this test and `scripts/verify_phase_5.py` together — "
        f"and see the re-enable test below, which is what keeps the two sources in step."
    )
    # Quoting-independent, because `- cron: 1 2 * * 3` is a live schedule that the quoted-value
    # regex does not see. Asserted on the `on:` block so the trigger, not the plumbing, is what is
    # checked; the parser's own mutation tests are below.
    assert triggers_in(filename) == [], (
        f"{filename}: `on:` still declares "
        f"{' and '.join(triggers_in(filename))}:\n{on_block((WORKFLOWS / filename).read_text())}"
    )
    # And the positive form, which is the stronger one: `workflow_dispatch` is the ONLY trigger
    # these four may carry. `push`, `workflow_run` and `repository_dispatch` also fire without
    # anybody asking, and "dispatch-only" is what D48 (1) ratified — not "no cron specifically".
    assert on_keys((WORKFLOWS / filename).read_text()) == ["workflow_dispatch"], (
        f"{filename}: `on:` declares "
        f"{on_keys((WORKFLOWS / filename).read_text())}, not workflow_dispatch alone"
    )
    assert configured(job), (
        f"season.json pipeline.schedule_et.{job} is empty. The cadence is kept as the record of "
        f"what ran; deleting it loses the only documented statement of the season's schedule."
    )


@pytest.mark.parametrize("job,filename", sorted(JOB_FILE.items()))
def test_a_restored_cron_must_still_match_season_json(job, filename):
    """The old guarantee, preserved for whoever re-enables a season.

    The reason the two sources had to agree has not gone away — a duplicated schedule drifts
    silently, and the drift shows up as a close captured after kickoff. So the rule is kept in a
    form that survives the stop: **zero crons is fine, and any cron that exists must match
    `season.json`.** A 2027 re-enable that edits only the workflow fails here rather than running
    at a time nothing documents.
    """
    present = crons_in(filename)
    assert present <= configured(job), (
        f"{filename} schedules {sorted(present - configured(job))}, which is not in season.json "
        f"pipeline.schedule_et.{job}. Both sources change together or not at all."
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
    assert "actions/clear-failure" in text
    # A successful run clears its stage's issue — but `daily-capture` clears on `rc == '0'` rather
    # than `success()`, because exits 3 and 4 are designed states that leave the job green having
    # captured nothing, and a run that did no work must not mark a real failure recovered (D44).
    assert "if: success()" in text or "steps.capture.outputs.rc == '0'" in text


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


def test_the_lean_split_is_in_place_so_the_report_gate_is_gone():
    """The D36 gate withheld the Sunday report commit until D27's split landed. The split is in
    (`analytics/attribution.py::by_lean_side`), so the gate is removed — and this asserts BOTH
    halves, so the gate cannot be dropped while the split is still missing."""
    assert "edge_direction" in (ROOT / "analytics" / "attribution.py").read_text(), (
        "the lean-side split is gone from attribution.py — restore it, or restore the D36 gate: "
        "an unsplit season headline over a 5.57:1 structural home skew repeats D17."
    )
    text = (WORKFLOWS / "weekly-grade.yml").read_text()
    assert "report_gate" not in text, "the D36 gate is obsolete once the split has landed"


def test_the_report_leads_with_the_lean_split_not_the_blend():
    """D27: a blended headline is not acceptable as the primary result. Ordering is behaviour, so
    it is pinned here as well as in the renderer's own tests."""
    reports = (ROOT / "analytics" / "reports.py").read_text()
    assert reports.index("_lean_block(ctx)") < reports.index("_kpi_block(ctx)")


class TestTheTriggerParserSeesEveryCronShape:
    """Mutations of the `on:` block, asserted against the shared parser.

    The stop makes "no cron found" the passing answer, so every blind spot in the parser is a way
    for a live schedule to pass both guards. Two were found by review rather than by tests — an
    unquoted cron value, and a column-0 comment that ended the block early — and this is where any
    third one gets added. Each case is a complete `on:` block, so these tests fail if the parser
    narrows, not merely if the workflows change.
    """

    DISPATCH = "name: x\n\non:\n  workflow_dispatch:\n\njobs:\n  a:\n    runs-on: ubuntu-latest\n"

    @staticmethod
    def _wrap(on_body: str) -> str:
        return f"name: x\n\non:{on_body}\njobs:\n  a:\n    runs-on: ubuntu-latest\n"

    def test_the_dispatch_only_shape_is_the_passing_case(self):
        assert unattended_triggers(self.DISPATCH) == []
        assert quoted_crons(self.DISPATCH) == set()

    def test_a_quoted_cron_is_seen(self):
        text = self._wrap('\n  workflow_dispatch:\n  schedule:\n    - cron: "1 2 * * 3"\n')
        assert unattended_triggers(text) == ["schedule", "cron"]
        assert quoted_crons(text) == {"1 2 * * 3"}

    def test_an_unquoted_cron_is_seen(self):
        """`- cron: 1 2 * * 3` is valid YAML and a live schedule. `crons_in` cannot read its value,
        which was harmless while the rule was set-equality and is the hole the stop opens."""
        text = self._wrap("\n  workflow_dispatch:\n  schedule:\n    - cron: 1 2 * * 3\n")
        assert unattended_triggers(text) == ["schedule", "cron"]
        assert quoted_crons(text) == set()

    def test_a_column_zero_comment_inside_the_block_does_not_hide_a_cron(self):
        """The blocker found in review of this PR: ending the block at the first column-0
        non-whitespace character ended it at `# note` too, and everything below was invisible."""
        text = self._wrap("\n  workflow_dispatch:\n# note\n  schedule:\n    - cron: 1 2 * * 3\n")
        assert unattended_triggers(text) == ["schedule", "cron"]

    def test_a_blank_line_inside_the_block_does_not_hide_a_cron(self):
        text = self._wrap("\n  workflow_dispatch:\n\n  schedule:\n    - cron: 1 2 * * 3\n")
        assert unattended_triggers(text) == ["schedule", "cron"]

    def test_the_flow_style_block_is_seen(self):
        text = self._wrap("\n  {schedule: [{cron: 1 2 * * 3}]}\n")
        assert unattended_triggers(text) == ["schedule", "cron"]

    def test_a_flow_mapping_on_the_on_line_itself_is_seen(self):
        """`on: {schedule: …}` puts the whole mapping on the key's own line, where a parser that
        reads only the lines below it sees nothing at all."""
        text = self._wrap(" {schedule: [{cron: 1 2 * * 3}]}\n")
        assert unattended_triggers(text) == ["schedule", "cron"]

    def test_the_quoted_on_key_is_found(self):
        """YAML 1.1 reads a bare `on` as a boolean, so some authors write `"on":`."""
        text = 'name: x\n\n"on":\n  schedule:\n    - cron: 1 2 * * 3\n\njobs:\n  a:\n'
        assert unattended_triggers(text) == ["schedule", "cron"]

    def test_trailing_whitespace_after_the_on_key_is_tolerated(self):
        text = "name: x\n\non: \n  schedule:\n    - cron: 1 2 * * 3\n\njobs:\n  a:\n"
        assert unattended_triggers(text) == ["schedule", "cron"]

    def test_a_comment_mentioning_a_schedule_is_not_a_schedule(self):
        """Comment bleed, the other direction. Prose about a setting is not the setting, and this
        project has lost four defects to the confusion — including comments added by this very PR,
        which say the word `schedule:` in all four workflow headers."""
        text = self._wrap("\n  # the schedule: block was removed by the season stop (cron, D48)\n"
                          "  workflow_dispatch:\n")
        assert unattended_triggers(text) == []

    def test_an_indented_comment_after_a_trigger_is_not_a_trigger(self):
        text = self._wrap("\n  workflow_dispatch:\n    # no schedule / cron here any more\n")
        assert unattended_triggers(text) == []

    def test_event_plumbing_outside_the_on_block_is_not_a_trigger(self):
        """`github.event.schedule` in a step is how the timing guard names its slot. It is not a
        trigger, and scoping the read to the `on:` block is what keeps it from reading as one."""
        text = ("name: x\n\non:\n  workflow_dispatch:\n\njobs:\n  a:\n    runs-on: x\n"
                "    steps:\n      - run: echo ${{ github.event.schedule }} cron\n")
        assert unattended_triggers(text) == []

    def test_a_file_with_no_on_key_fails_closed(self):
        """A workflow whose triggers cannot be located must not read as one with no triggers."""
        with pytest.raises(ValueError):
            on_block("name: x\n\njobs:\n  a:\n    runs-on: ubuntu-latest\n")

    def test_the_declared_trigger_names_are_read_at_the_top_level_only(self):
        """`workflow_dispatch:` with `inputs:` under it declares ONE trigger, not four."""
        text = self._wrap(
            "\n  workflow_dispatch:\n    inputs:\n      week:\n        required: false\n"
        )
        assert on_keys(text) == ["workflow_dispatch"]

    def test_a_second_trigger_is_reported_even_though_it_is_not_a_cron(self):
        """`push` fires unattended too, and the stop is "dispatch-only", not "no cron"."""
        text = self._wrap("\n  workflow_dispatch:\n  push:\n    branches: [main]\n")
        assert on_keys(text) == ["workflow_dispatch", "push"]
        assert unattended_triggers(text) == []

    def test_a_flow_style_block_is_not_mistaken_for_no_triggers(self):
        text = self._wrap(" {schedule: [{cron: 1 2 * * 3}]}\n")
        assert on_keys(text) == ["<flow>"]

    def test_every_real_workflow_parses(self):
        """The parser is only load-bearing if it can actually read the files it guards."""
        for filename in ALL_FILES:
            on_block((WORKFLOWS / filename).read_text())

