"""The claim tripwire fires when a due claim is missing or dirty, and stays silent otherwise.

Owner ruling 2026-09-15 (D44): detection only for the cancelled-while-pending predict hazard, with
two conditions. There must be a test that it fires on a synthetic missing claim and is silent when the
claim exists. And a claim whose `model_version` carries `-dirty` fires as well, because a dirty claim
is not a claim.

Week 4 (2026-09-21 to 09-27, `season.json`) is used throughout: Wed 09-23 is inside its claim window.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.claim_tripwire import EXIT_NO_VALID_CLAIM, EXIT_OK, evaluate, main
from utils.season_calendar import load_calendar

ROOT = Path(__file__).resolve().parent.parent
CAL = load_calendar()
WED = date(2026, 9, 23)


def _claim(base: Path, week: int = 4, model_version: str | None = "v2026-frozen-3-70-gabc1234",
           raw: str | None = None) -> Path:
    d = base / "data" / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"2026_week_{week:02d}.json"
    meta = {"week": week, "year": 2026}
    if model_version is not None:
        meta["model_version"] = model_version
    path.write_text(raw if raw is not None else json.dumps({"meta": meta, "predictions": []}))
    return path


def test_fires_on_a_synthetic_missing_claim(tmp_path):
    rc, week, reason = evaluate(WED, CAL, tmp_path)
    assert (rc, week) == (EXIT_NO_VALID_CLAIM, 4) and "no claim file" in reason


def test_silent_when_the_claim_exists(tmp_path):
    _claim(tmp_path)
    assert evaluate(WED, CAL, tmp_path)[0] == EXIT_OK


def test_fires_when_the_claim_is_dirty(tmp_path):
    """A claim stamped from a modified working tree is not a claim of the frozen model."""
    _claim(tmp_path, model_version="v2026-frozen-3-70-gabc1234-dirty")
    rc, _, reason = evaluate(WED, CAL, tmp_path)
    assert rc == EXIT_NO_VALID_CLAIM and "-dirty" in reason


@pytest.mark.parametrize("model_version, raw", [(None, None), (None, "{not json")])
def test_fires_when_the_claim_is_unreadable_or_unstamped(tmp_path, model_version, raw):
    _claim(tmp_path, model_version=model_version, raw=raw)
    assert evaluate(WED, CAL, tmp_path)[0] == EXIT_NO_VALID_CLAIM


@pytest.mark.parametrize("day", [date(2026, 9, 22), date(2026, 9, 27), date(2026, 9, 21)])
def test_silent_outside_wednesday_to_saturday(tmp_path, day):
    """Tuesday is predict day ("not yet"); Sunday and Monday are after the week's games."""
    assert evaluate(day, CAL, tmp_path)[0] == EXIT_OK


@pytest.mark.parametrize("day", [date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26)])
def test_fires_every_day_wednesday_to_saturday(tmp_path, day):
    assert evaluate(day, CAL, tmp_path)[0] == EXIT_NO_VALID_CLAIM


def test_silent_when_the_claim_window_is_not_open(tmp_path):
    """Pre-season: 2026-08-19 resolves to week 1, whose window (D38) opens 08-22."""
    assert evaluate(date(2026, 8, 19), CAL, tmp_path)[0] == EXIT_OK


def test_checks_the_week_being_played_not_the_next(tmp_path):
    _claim(tmp_path, week=5)
    rc, week, _ = evaluate(WED, CAL, tmp_path)
    assert (rc, week) == (EXIT_NO_VALID_CLAIM, 4), "a week-5 claim does not satisfy week 4"


def test_the_cli_exit_code_is_the_signal(tmp_path, capsys):
    assert main(["--today", "2026-09-23", "--base", str(tmp_path)]) == EXIT_NO_VALID_CLAIM
    assert "::error::claim tripwire: week 4" in capsys.readouterr().out
    _claim(tmp_path)
    assert main(["--today", "2026-09-23", "--base", str(tmp_path)]) == EXIT_OK


WORKFLOW = (ROOT / ".github/workflows/freeze-integrity.yml").read_text()


def test_it_runs_in_freeze_integrity_whatever_else_fails():
    """Its own concurrency group is why it lives here; `!cancelled()` keeps a failed fingerprint
    from also hiding a missing claim."""
    assert "group: freeze-integrity" in WORKFLOW
    i = WORKFLOW.index("scripts/claim_tripwire.py")
    step = WORKFLOW[WORKFLOW.rindex("- name:", 0, i):i]
    assert "if: ${{ !cancelled() }}" in step and "id: tripwire" in step


def test_a_tripped_wire_opens_a_predict_issue_that_a_successful_predict_clears():
    i = WORKFLOW.index("steps.tripwire.outputs.rc == '2'")
    step = WORKFLOW[i:WORKFLOW.index("token:", i)]
    assert "stage: predict" in step and "kind: failure" in step
    assert "week: ${{ steps.tripwire.outputs.week_padded }}" in step
    # weekly-predict's clear-failure closes exactly this label set on success.
    predict = (ROOT / ".github/workflows/weekly-predict.yml").read_text()
    assert "actions/clear-failure" in predict and "stage: predict" in predict
    fail = WORKFLOW[WORKFLOW.index("- name: Fail on a tripwire error"):]
    assert "rc != '0' && steps.tripwire.outputs.rc != '2'" in fail.split("run:")[0]
