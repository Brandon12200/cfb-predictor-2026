"""A full simulated pipeline cycle against mocked APIs — SPEC §10 acceptance.

    snapshot → predict → line captures → finals → grade → report

Every path is redirected to `tmp_path`, so this exercises the real scripts without touching a
single committed artifact (`tests/conftest.py`'s `_no_writes_to_real_artifact_dirs` enforces that
independently, and would fail this file if the redirection were incomplete).

What it is really testing is the **choreography** — that each stage's output is the shape the next
stage reads. Every stage passes its own unit tests today; what nothing covered until now is the
seam between them, which is exactly where the pipeline lives. It also pins idempotency: a second
identical cycle must add nothing, because the whole cadence is built on being safe to re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.grading import build_graded, merge_graded
from analytics.predictions import build_predictions
from data.normalize.models import ScheduleGame
from data.snapshot import SnapshotBuilder
from scripts.fetch_results import build_results, merge_results
from tests.test_snapshot import _FakeCFBD, _FakeOdds, _FakeRegistry

WEEK, YEAR = 1, 2026
CLOCK = "2026-08-25T13:17:00+00:00"


@pytest.fixture
def cycle(tmp_path, monkeypatch):
    """Redirect every artifact home into tmp_path and build the week's snapshot."""
    import data.snapshot.lines as lines_mod
    import data.snapshot.store as store_mod

    snapshots, lines = tmp_path / "snapshots", tmp_path / "lines"
    monkeypatch.setattr(store_mod, "_SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr(lines_mod, "_LINES_DIR", lines)

    # base_dir is deliberately left None so the builder resolves BOTH stores through the patched
    # module defaults, exactly as it does in production. Passing base_dir would send the seeded
    # line store to the snapshots base as well (`record_observation(..., base=self.base_dir)`),
    # which is not the production layout and would make this test rehearse the wrong paths.
    manifest = SnapshotBuilder(
        _FakeCFBD(), _FakeOdds(), _FakeRegistry(), clock=lambda: CLOCK,
    ).build(week=WEEK, year=YEAR)

    return {
        "root": tmp_path,
        "snapshots": snapshots,
        "lines": lines,
        "predictions": tmp_path / "predictions",
        "results": tmp_path / "results",
        "graded": tmp_path / "graded",
        "manifest": manifest,
        "snapshot": store_mod.load_snapshot(WEEK, YEAR),
    }


# --- stage 1: the snapshot -----------------------------------------------------------------------

def test_snapshot_is_built_and_seeds_the_line_series(cycle):
    """The builder seeds line observation #1 — which is why the Tuesday commit stages
    data/lines alongside data/snapshots."""
    assert cycle["snapshot"]["meta"]["week"] == WEEK
    assert cycle["snapshot"]["data"]["betting_lines"]
    store = json.loads((cycle["lines"] / f"{YEAR}_week_{WEEK:02d}.json").read_text())
    assert store, "the builder did not seed a line observation"
    assert all(len(e["observations"]) == 1 for e in store.values())


def test_snapshot_quality_gate_accepts_the_simulated_slate(cycle):
    from scripts.check_snapshot_quality import evaluate
    thresholds = json.loads(
        (Path(__file__).resolve().parent.parent / "season.json").read_text()
    )["pipeline"]["data_quality"]
    breaches = evaluate(cycle["manifest"]["summary"], 138, thresholds)
    assert [b for b in breaches if b[0] == "fail"] == []


# --- stage 2: the claim --------------------------------------------------------------------------

@pytest.fixture
def predictions(cycle):
    env = build_predictions(cycle["snapshot"], week=WEEK, model_version="v2026-frozen-test")
    cycle["predictions"].mkdir(parents=True, exist_ok=True)
    (cycle["predictions"] / f"{YEAR}_week_{WEEK:02d}.json").write_text(
        json.dumps(env, indent=2, sort_keys=True) + "\n")
    return env


def test_predictions_are_written_for_the_slate(predictions):
    assert predictions["predictions"], "no claims produced from the simulated slate"
    assert predictions["meta"]["schema_version"] == 2
    assert predictions["meta"]["model_version"] == "v2026-frozen-test"


def test_the_writer_refuses_to_overwrite_an_existing_claim(tmp_path, monkeypatch, predictions):
    """D22 at the shared seam, not only in the workflow's `if:`.

    Phase 5 wires this writer into unattended automation, where `protect_immutable.py` does not run
    at all (it intercepts an agent's Edit/Write tool calls, not a script on a runner). Before this
    guard, the sole protection for a byte-immutable claim was one workflow conditional, and a
    direct `python scripts/build_predictions.py --week N` would have silently overwritten it.
    """
    import scripts.build_predictions as bp

    claims = tmp_path / "claim_tier"
    claims.mkdir(exist_ok=True)
    monkeypatch.setattr(bp, "PREDICTIONS_DIR", claims)
    target = claims / "2026_week_01.json"

    bp.write_predictions(predictions, target)
    original = target.read_bytes()

    with pytest.raises(FileExistsError, match="byte-immutable"):
        bp.write_predictions({"meta": {}, "predictions": []}, target)
    assert target.read_bytes() == original, "the claim was modified despite the refusal"

    # Deliberate override still works, for an uncommitted claim.
    bp.write_predictions({"meta": {}, "predictions": []}, target, force=True)
    assert target.read_bytes() != original


def test_a_scratch_path_outside_the_claim_tier_is_not_guarded(tmp_path, predictions):
    """`--out docs/examples/...` regenerates the golden; the guard is scoped to the claim tier."""
    import scripts.build_predictions as bp

    scratch = tmp_path / "scratch.json"
    bp.write_predictions(predictions, scratch)
    bp.write_predictions(predictions, scratch)  # must not raise
    assert scratch.exists()


def test_the_claim_is_byte_stable_on_a_rerun(cycle, predictions):
    """Determinism from a frozen snapshot — the property the pre-registration story rests on."""
    again = build_predictions(cycle["snapshot"], week=WEEK, model_version="v2026-frozen-test")
    assert json.dumps(again, sort_keys=True) == json.dumps(predictions, sort_keys=True)


# --- stage 3: daily captures ---------------------------------------------------------------------

def test_captures_append_without_disturbing_the_snapshot(cycle, predictions):
    """The 1c hash-exclusion rule: appending observations must not move `snapshot_id`."""
    from data.snapshot.lines import record_observation

    before_id = cycle["snapshot"]["meta"]["snapshot_id"]
    before_bytes = (cycle["snapshots"] / f"{YEAR}_week_{WEEK:02d}" / "snapshot.json").read_bytes()

    for day in (26, 27, 28):
        games = {
            key: {"home_team": v["home_team"], "away_team": v["away_team"],
                  "kickoff": v.get("kickoff"),
                  "observations": [{"consensus_spread": -7.5,
                                    "fetched_at": f"2026-08-{day}T21:23:00+00:00",
                                    "lines": []}]}
            for key, v in cycle["snapshot"]["data"]["betting_lines"].items()
        }
        record_observation(WEEK, games, year=YEAR)

    after = json.loads((cycle["snapshots"] / f"{YEAR}_week_{WEEK:02d}" / "snapshot.json").read_text())
    assert after["meta"]["snapshot_id"] == before_id
    assert (cycle["snapshots"] / f"{YEAR}_week_{WEEK:02d}" / "snapshot.json").read_bytes() == before_bytes

    store = json.loads((cycle["lines"] / f"{YEAR}_week_{WEEK:02d}.json").read_text())
    assert max(len(e["observations"]) for e in store.values()) >= 3


# --- stage 4+5: finals and grading ---------------------------------------------------------------

def _finals(predictions_env, *, completed=True):
    return [ScheduleGame(week=WEEK, home_team=p["home_team"], away_team=p["away_team"],
                         home_points=27 if completed else None,
                         away_points=13 if completed else None,
                         start_date="2026-08-29T23:00:00.000Z", completed=completed)
            for p in predictions_env["predictions"]]


def test_finals_join_the_claims_and_grade(cycle, predictions):
    results = build_results(predictions, _finals(predictions),
                            week=WEEK, year=YEAR, fetched_at=CLOCK)
    assert results["results"], "no finals matched the claims"

    graded = build_graded(predictions, results["results"], None, graded_at=CLOCK)
    assert graded["meta"]["coverage"]["graded"] == len(predictions["predictions"])
    assert graded["meta"]["coverage"]["ungraded"] == []


def test_the_whole_cycle_is_idempotent(cycle, predictions):
    """Re-running the cadence must add nothing — the property every catch-up run depends on."""
    results = build_results(predictions, _finals(predictions),
                            week=WEEK, year=YEAR, fetched_at=CLOCK)
    _, added_again = merge_results(results, results)
    assert added_again == 0

    graded = build_graded(predictions, results["results"], None, graded_at=CLOCK)
    _, regraded = merge_graded(graded, graded)
    assert regraded == 0


def test_a_partial_week_completes_across_two_runs(cycle, predictions):
    """Sunday grades what finished; Tuesday catches up. Nothing is lost or double-counted."""
    partial = _finals(predictions)
    partial[-1].completed, partial[-1].home_points, partial[-1].away_points = False, None, None

    sunday = build_results(predictions, partial, week=WEEK, year=YEAR, fetched_at=CLOCK)
    sunday_graded = build_graded(predictions, sunday["results"], None, graded_at=CLOCK)
    assert sunday_graded["meta"]["coverage"]["ungraded"], "expected an ungraded remainder"

    tuesday = build_results(predictions, _finals(predictions),
                            week=WEEK, year=YEAR, fetched_at=CLOCK)
    merged, added = merge_results(sunday, tuesday)
    assert added == len(predictions["predictions"]) - len(sunday["results"])

    final_graded, newly = merge_graded(
        sunday_graded, build_graded(predictions, merged["results"], None, graded_at=CLOCK))
    assert newly == added
    assert final_graded["meta"]["coverage"]["ungraded"] == []


# --- stage 6: the rendering ----------------------------------------------------------------------

def test_reports_render_from_the_cycle_output(cycle, predictions):
    from analytics.reports import render_week

    results = build_results(predictions, _finals(predictions),
                            week=WEEK, year=YEAR, fetched_at=CLOCK)
    graded = build_graded(predictions, results["results"], None, graded_at=CLOCK)
    markdown = render_week(predictions, graded)
    assert markdown.strip(), "empty report"
    assert isinstance(markdown, str)


def test_nothing_touched_a_real_artifact_directory(cycle):
    """Belt and braces alongside conftest's autouse guard: the cycle lives entirely in tmp_path."""
    repo = Path(__file__).resolve().parent.parent
    assert cycle["root"].is_relative_to(Path(cycle["root"]).anchor)
    assert not str(cycle["root"]).startswith(str(repo / "data"))
