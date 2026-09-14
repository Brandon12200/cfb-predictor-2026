"""The pipeline's CLV sign check must fail the run on an inverted sign, and pass a correct one.

Owner ruling 2026-09-13: the CLV sign check moves from a human step after the Sunday report into the
pipeline, between "Grade" and the grading commit, because the scheduled job commits grades about
thirty seconds after producing them and `data/graded/` is append-only.

The case that matters is an **away** lean. Week 2 carried the season's first four, and the away
branch of the CLV formula is the mirror of the home branch — `closing - vegas` rather than
`vegas - closing`. A sign convention applied to the wrong side does not look like an error; it looks
like a consistent, plausible result.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_clv import EXIT_DISAGREE, EXIT_OK, check_lean, main

ROOT = Path(__file__).resolve().parent.parent


def _tree(tmp_path: Path, leans: list[tuple[str, str, float, float, float]]) -> Path:
    """Write a claim + graded pair for week 3. Each lean: (game_id, side, vegas, close, stored_clv)."""
    (tmp_path / "data" / "predictions").mkdir(parents=True)
    (tmp_path / "data" / "graded").mkdir(parents=True)
    preds = [{"game_id": g, "edge_direction": side, "vegas_spread": v} for g, side, v, _, _ in leans]
    graded = [{"game_id": g, "closing_spread": c, "clv": s} for g, _, _, c, s in leans]
    (tmp_path / "data/predictions/2026_week_03.json").write_text(json.dumps({"predictions": preds}))
    (tmp_path / "data/graded/2026_week_03.json").write_text(json.dumps({"graded": graded}))
    return tmp_path


def test_a_correct_home_and_away_slate_passes(tmp_path):
    base = _tree(tmp_path, [
        ("h1", "home", -10.6, -12.0, +1.40),     # the owner's worked example
        ("a1", "away", -6.9, -5.0, +1.90),       # market moved toward away: we held the better number
        ("a2", "away", -6.9, -8.0, -1.10),       # market moved toward home: against the away lean
    ])
    assert main(["--week", "3", "--base", str(base)]) == EXIT_OK


def test_an_inverted_away_lean_fails_the_run(tmp_path, capsys):
    """Grading applied the HOME formula to an away lean: stored -1.90 where +1.90 is correct."""
    base = _tree(tmp_path, [
        ("h1", "home", -10.6, -12.0, +1.40),
        ("a1", "away", -6.9, -5.0, -1.90),       # WRONG SIGN
    ])
    assert main(["--week", "3", "--base", str(base)]) == EXIT_DISAGREE
    out = capsys.readouterr().out
    assert "a1" in out and "disagree" in out.lower()
    assert "h1" not in out.split("check_clv:")[-1], "the correct home lean must not be blamed"


def test_the_movement_check_catches_what_the_formula_check_would_pass():
    """If the CHECK's own formula were inverted too, formula_ok would agree with the wrong value.

    That is the failure this second check exists for: a convention inverted consistently agrees with
    itself. The movement check derives the expected sign from which way the line moved, without the
    formula, so it still flags it.
    """
    vegas, close, wrong = -6.9, -5.0, -1.90                # away lean, inverted sign
    assert abs(round(vegas - close, 2) - wrong) < 1e-9     # an inverted formula WOULD agree with it
    _, movement_ok, moved = check_lean("away", vegas, close, wrong)
    assert moved == "away" and movement_ok is False


@pytest.mark.parametrize("side, vegas, close, clv, moved", [
    ("home", -10.6, -10.1, -0.50, "away"),
    ("home", -6.5, -6.5, 0.00, "none"),
    ("away", -3.1, -2.9, +0.20, "away"),
    ("away", -13.9, -14.1, -0.20, "home"),
])
def test_real_week_1_and_2_leans_pass(side, vegas, close, clv, moved):
    """Four real graded leans, both sides and an unmoved line, taken from the committed grades."""
    formula_ok, movement_ok, got = check_lean(side, vegas, close, clv)
    assert (formula_ok, movement_ok, got) == (True, True, moved)


def test_nothing_graded_is_not_a_failure(tmp_path):
    assert main(["--week", "3", "--base", str(tmp_path)]) == EXIT_OK


def test_neutral_and_ungraded_rows_are_skipped_not_failed(tmp_path):
    base = _tree(tmp_path, [("h1", "home", -3.0, -3.5, +0.50)])
    preds = json.loads((base / "data/predictions/2026_week_03.json").read_text())
    preds["predictions"] += [{"game_id": "n1", "edge_direction": "neutral", "vegas_spread": -2.0},
                             {"game_id": "u1", "edge_direction": "away", "vegas_spread": -2.0}]
    (base / "data/predictions/2026_week_03.json").write_text(json.dumps(preds))
    assert main(["--week", "3", "--base", str(base)]) == EXIT_OK


def test_the_check_gates_the_grading_commit_in_weekly_grade():
    """Wired, not just written: it must sit between "Grade" and the commit that stages data/graded,
    and propagate its exit code. D39's defect was a gate that was computed and never connected."""
    text = (ROOT / ".github/workflows/weekly-grade.yml").read_text()
    grade = text.index("- name: Grade\n")
    check = text.index("scripts/check_clv.py")
    graded_commit = text.index("paths: data/graded")
    assert grade < check < graded_commit, "check_clv must run after Grade and before its commit"
    step = text[text.rindex("- name:", 0, check):graded_commit]
    assert 'exit "${PIPESTATUS[0]}"' in step, "the check's failure must fail the step"
