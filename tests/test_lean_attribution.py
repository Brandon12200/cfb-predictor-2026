"""D27's lean-side split and the naive always-lean-home baseline.

The obligation exists because the model's live signal is asymmetric **by construction** —
`TravelBurden`/`ConsecutiveRoad` only penalise the visitor, `Altitude` only advantages the host —
so preseason leans ran 195 home / 35 away (5.57:1). A blended headline over that skew measures how
home teams did against the spread and reports it as skill. That is D17's retired 57.0%, exactly.

The load-bearing test here is `test_a_pure_home_bias_shows_no_edge_over_the_baseline`: it builds a
model that always leans home on a slate where home covers 57% of the time, and asserts the report
says the model added **nothing** over the naive baseline. Before this split, that same input
produced a 57% headline and nothing contradicted it.
"""

from __future__ import annotations

import pytest

from analytics.attribution import by_lean_side
from analytics.reports import _lean_block, report_context


def rec(gid: str, *, side, vegas, home_score, away_score, closing=None, graded=True,
        is_hypothetical=False):
    """A joined record (predictions ⋈ graded) with only the fields the split reads."""
    from analytics.calibration_evidence import ats_outcome
    from utils.prediction_schema import clv as clv_from_close

    base = {
        "game_id": gid, "edge_direction": side, "vegas_spread": vegas,
        "home_score": home_score, "away_score": away_score,
        "closing_spread": closing, "graded": graded,
        "home_team": "H", "away_team": "A", "week": 1,
    }
    # `join` only sets is_hypothetical when a graded record exists, so an ungraded record carries
    # None — mirrored here so the fixture cannot be more forgiving than the real join.
    base["is_hypothetical"] = is_hypothetical if graded else None
    base["ats_result"] = ats_outcome(base, base) if graded else None
    base["clv"] = clv_from_close(vegas, closing, side)
    return base


# --- the D17 failure this exists to prevent -----------------------------------------------------

def _always_home_slate(n_home_covers: int, n_home_fails: int):
    """A model that ALWAYS leans home, on a slate where home covers `n_home_covers` of the time."""
    games = []
    # vegas -3.0: home covers iff (hs-as) - 3 > 0
    for i in range(n_home_covers):
        games.append(rec(f"cover{i}", side="home", vegas=-3.0, home_score=28, away_score=10))
    for i in range(n_home_fails):
        games.append(rec(f"fail{i}", side="home", vegas=-3.0, home_score=10, away_score=28))
    return games


def test_a_pure_home_bias_shows_no_edge_over_the_baseline():
    """171-129 is D17's exact 57.0%. The split must show the model added nothing."""
    lean = by_lean_side(_always_home_slate(171, 129))

    assert lean["model_overall"]["ats_win_pct"] == pytest.approx(0.57, abs=0.005)
    # The naive baseline scores identically, because the model IS the naive baseline here.
    assert lean["baseline_always_home"]["ats_win_pct"] == pytest.approx(0.57, abs=0.005)
    assert lean["vs_baseline"]["ats_delta"] == 0.0
    assert lean["sides"]["away"]["n_games"] == 0
    assert lean["meta"]["home_away_ratio"] is None  # no away games to divide by


def test_the_report_says_so_in_words():
    ctx = report_context(_always_home_slate(171, 129))
    text = "\n".join(_lean_block(ctx))
    assert "always lean home" in text
    assert "+0.0%" in text
    assert "has not beaten 'always take the home team'" in text


def test_real_side_selection_beats_the_baseline():
    """A model that leans away exactly when away covers must show a positive delta."""
    games = [rec(f"h{i}", side="home", vegas=-3.0, home_score=28, away_score=10) for i in range(20)]
    games += [rec(f"a{i}", side="away", vegas=-3.0, home_score=10, away_score=28) for i in range(20)]
    lean = by_lean_side(games)

    assert lean["model_overall"]["ats_win_pct"] == 1.0
    assert lean["baseline_always_home"]["ats_win_pct"] == 0.5  # always-home wins only the 20 home
    assert lean["vs_baseline"]["ats_delta"] == 0.5


# --- the split itself ---------------------------------------------------------------------------

def test_sides_are_stratified_not_blended():
    games = [rec(f"h{i}", side="home", vegas=-3.0, home_score=28, away_score=10) for i in range(8)]
    games += [rec(f"a{i}", side="away", vegas=-3.0, home_score=28, away_score=10) for i in range(2)]
    lean = by_lean_side(games)

    assert lean["sides"]["home"]["n_games"] == 8
    assert lean["sides"]["away"]["n_games"] == 2
    assert lean["sides"]["home"]["ats_win_pct"] == 1.0
    assert lean["sides"]["away"]["ats_win_pct"] == 0.0
    assert lean["meta"]["home_away_ratio"] == 4.0


def test_the_away_cell_carries_a_wilson_interval():
    """D27: the away cell is thin (~35) and must never be read as a point estimate."""
    games = [rec(f"a{i}", side="away", vegas=-3.0, home_score=10, away_score=28) for i in range(3)]
    lean = by_lean_side(games)
    lo, hi = lean["sides"]["away"]["wilson_95"]
    assert 0.0 <= lo < hi <= 1.0
    assert hi - lo > 0.3, "a 3-game cell must show a wide interval, not a confident 100%"


def test_the_report_flags_a_thin_away_cell():
    games = [rec(f"h{i}", side="home", vegas=-3.0, home_score=28, away_score=10) for i in range(40)]
    games += [rec(f"a{i}", side="away", vegas=-3.0, home_score=10, away_score=28) for i in range(5)]
    text = "\n".join(_lean_block(report_context(games)))
    assert "away cell is thin" in text
    assert "Wilson" in text


def test_neutral_games_are_their_own_bucket_never_win_rated():
    games = [rec(f"h{i}", side="home", vegas=-3.0, home_score=28, away_score=10) for i in range(5)]
    games += [rec(f"n{i}", side=None, vegas=-3.0, home_score=28, away_score=10) for i in range(4)]
    lean = by_lean_side(games)

    assert lean["meta"]["n_neutral"] == 4
    assert lean["neutral"]["n_games"] == 4
    assert "null rather than 0.0" in lean["neutral"]["reason"]
    # Neutral games contribute to neither side.
    assert lean["sides"]["home"]["n_games"] + lean["sides"]["away"]["n_games"] == 5


def test_clv_is_split_by_side_and_uses_the_ratified_convention():
    """CLV is from the bet side's perspective: home ⇒ vegas − close, away ⇒ close − vegas (D21.3)."""
    games = [rec("h", side="home", vegas=-3.0, closing=-5.0, home_score=28, away_score=10),
             rec("a", side="away", vegas=-3.0, closing=-5.0, home_score=10, away_score=28)]
    lean = by_lean_side(games)
    assert lean["sides"]["home"]["avg_clv"] == pytest.approx(2.0)
    assert lean["sides"]["away"]["avg_clv"] == pytest.approx(-2.0)


def test_the_baseline_is_graded_against_vegas_not_the_models_own_number():
    """The retired D17 diagnostic graded always-home against the MODEL's contrarian spread, which is
    how 57% happened. This baseline must use the Vegas line — a different, honest question."""
    games = [rec("g", side="away", vegas=-3.0, home_score=28, away_score=10,
                 closing=-9.0)]
    games[0]["contrarian_spread"] = -99.0  # would flip the result if it were used
    lean = by_lean_side(games)
    # home covered the VEGAS line (+18-3 > 0), so the always-home baseline wins.
    assert lean["baseline_always_home"]["ats_win_pct"] == 1.0
    # and the model, having leaned away, lost.
    assert lean["model_overall"]["ats_win_pct"] == 0.0


def test_baseline_is_computed_over_the_matched_game_set():
    """Comparing over different game sets would confound side-selection with slate composition."""
    games = [rec(f"g{i}", side="home", vegas=-3.0, home_score=28, away_score=10) for i in range(6)]
    games += [rec("ungraded", side="home", vegas=-3.0, home_score=None, away_score=None,
                  graded=False)]
    lean = by_lean_side(games)
    assert lean["model_overall"]["n_graded"] == 6
    assert lean["baseline_always_home"]["n_graded"] == 6


# --- placed vs hypothetical: the labelling that keeps this from reading as a bet record ----------
#
# Preseason EVERY game is NO_BET, so the block that now leads every report can be 100%
# "what would have happened". An unlabelled measurement read as a track record is D17 in
# miniature, which is why each branch is pinned rather than eyeballed once.

def _slate(n_hyp: int, n_placed: int, graded: bool = True):
    games = [rec(f"hyp{i}", side="home", vegas=-3.0, home_score=28, away_score=10,
                 graded=graded, is_hypothetical=True) for i in range(n_hyp)]
    games += [rec(f"plc{i}", side="home", vegas=-3.0, home_score=28, away_score=10,
                  graded=graded, is_hypothetical=False) for i in range(n_placed)]
    return games


def test_an_all_no_bet_slate_is_labelled_hypothetical():
    lean = by_lean_side(_slate(n_hyp=6, n_placed=0))
    assert lean["meta"]["all_hypothetical"] is True
    assert (lean["meta"]["n_hypothetical"], lean["meta"]["n_placed"]) == (6, 0)
    assert lean["sides"]["home"]["n_hypothetical"] == 6

    text = "\n".join(_lean_block(report_context(_slate(n_hyp=6, n_placed=0))))
    assert "hypothetical leans, not placed bets" in text
    assert "No wager was recommended" in text
    assert "Mixed:" not in text


def test_a_mixed_slate_says_which_is_which():
    lean = by_lean_side(_slate(n_hyp=3, n_placed=2))
    assert lean["meta"]["all_hypothetical"] is False
    assert (lean["meta"]["n_hypothetical"], lean["meta"]["n_placed"]) == (3, 2)

    text = "\n".join(_lean_block(report_context(_slate(n_hyp=3, n_placed=2))))
    assert "Mixed: 2 placed bet(s) and 3 hypothetical" in text
    assert "hypothetical leans, not placed bets" not in text


def test_an_all_placed_slate_carries_no_caveat():
    lean = by_lean_side(_slate(n_hyp=0, n_placed=5))
    assert lean["meta"]["all_hypothetical"] is False
    assert (lean["meta"]["n_hypothetical"], lean["meta"]["n_placed"]) == (0, 5)

    text = "\n".join(_lean_block(report_context(_slate(n_hyp=0, n_placed=5))))
    assert "hypothetical" not in text.lower().split("| lean")[0]


def test_an_ungraded_slate_claims_neither():
    """`all_hypothetical` is computed over the GRADED set, so an empty one must not assert it."""
    lean = by_lean_side(_slate(n_hyp=4, n_placed=0, graded=False))
    assert lean["meta"]["all_hypothetical"] is False
    assert lean["meta"]["n_graded"] == 0

    text = "\n".join(_lean_block(report_context(_slate(n_hyp=4, n_placed=0, graded=False))))
    assert "hypothetical leans, not placed bets" not in text
    assert "Mixed:" not in text
    assert "No graded bets yet" in text


def test_the_committed_preseason_golden_carries_the_label():
    """The real artifact the first live reports will look like — every game NO_BET."""
    import json
    from pathlib import Path

    from analytics.reports import render_week
    root = Path(__file__).resolve().parent.parent
    golden = root / "docs" / "examples" / "prediction_schema_v2_2026_week_01.json"
    graded = root / "docs" / "examples" / "graded_record_2026_week_01.json"
    if not (golden.exists() and graded.exists()):
        pytest.skip("goldens not present")
    text = render_week(json.loads(golden.read_text()), json.loads(graded.read_text()))
    assert "hypothetical leans, not placed bets" in text


# --- honest-empty -------------------------------------------------------------------------------

def test_an_ungraded_slate_states_its_reason_rather_than_showing_a_dash():
    games = [rec(f"g{i}", side="home", vegas=-3.0, home_score=None, away_score=None, graded=False)
             for i in range(10)]
    lean = by_lean_side(games)
    assert lean["vs_baseline"]["ats_delta"] is None

    text = "\n".join(_lean_block(report_context(games)))
    assert "No graded bets yet" in text
    # Was `assert "honest-missing" in text`, which pinned wording that blamed line CAPTURE for an
    # empty cell. These games simply have not kicked off. The 2026 week-1 report proved the
    # distinction matters: every graded record carried a real closing line, yet the cell read
    # "no closing lines captured yet" (D40). Honest-missing is now reserved for its real case —
    # graded, but no closing line.
    assert "no games graded on this side yet" in text
    assert "no closing lines captured" not in text


def test_an_empty_slate_does_not_crash():
    lean = by_lean_side([])
    assert lean["meta"]["n_games"] == 0
    assert lean["vs_baseline"]["ats_delta"] is None
    assert "\n".join(_lean_block(report_context([])))


def test_the_baseline_reproduces_d17s_independently_recorded_54_4_pct():
    """**The strongest available check on this implementation.**

    D17's ratified table records, for the 2025 archive under the canonical cover rule:
    always-home graded against the **Vegas line** = **54.4% (160/294)**. That figure was measured
    in July by a different harness, for a different purpose, and is recorded in `docs/DECISIONS.md`
    — so it is an independent oracle for the naive baseline built here. If this reproduces it to
    the game, the baseline is grading what D17 graded.
    """
    from pathlib import Path

    archive = Path(__file__).resolve().parent.parent / "data" / "archive" / "2025"
    if not (archive / "predictions").exists():
        pytest.skip("2025 archive not present")

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase4 import _retro_weeks

    from analytics.join import join
    joined: list[dict] = []
    for pred_env, graded_env in _retro_weeks():
        joined += join(pred_env, graded_env)

    base = by_lean_side(joined)["baseline_always_home"]
    assert base["wins"] == 160, f"D17 records 160 always-home wins; got {base['wins']}"
    assert base["n_graded"] == 294, f"D17 records 294 decided games; got {base['n_graded']}"
    assert base["ats_win_pct"] == pytest.approx(0.544, abs=0.001)


def test_the_retro_model_number_still_reconciles_to_d17():
    """The other half of the same table: the placeable strategy graded 46.6% (137/294)."""
    from pathlib import Path

    archive = Path(__file__).resolve().parent.parent / "data" / "archive" / "2025"
    if not (archive / "predictions").exists():
        pytest.skip("2025 archive not present")

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_phase4 import _retro_weeks

    from analytics.join import join
    joined: list[dict] = []
    for pred_env, graded_env in _retro_weeks():
        joined += join(pred_env, graded_env)

    lean = by_lean_side(joined)
    assert lean["model_overall"]["ats_win_pct"] == pytest.approx(0.466, abs=0.001)
    # And the delta is the number D27 exists to surface: the model lost to the naive baseline.
    assert lean["vs_baseline"]["ats_delta"] == pytest.approx(-0.078, abs=0.002)


def test_the_lean_block_precedes_the_blended_kpis_in_a_rendered_report():
    """D27: a blended headline is not acceptable as the PRIMARY result, so ordering is behaviour."""
    from analytics.reports import render_season

    preds = {"meta": {"week": 1, "year": 2026}, "predictions": [
        {"game_id": "g", "edge_direction": "home", "vegas_spread": -3.0,
         "home_team": "H", "away_team": "A", "week": 1, "factor_breakdown": {}},
    ]}
    text = render_season([(preds, None)], title="T")
    assert text.index("by lean side") < text.index("Placeable strategy")


# --- the partial-week seam: buckets must come from the CLAIM, not from gradedness ----------------

def _partial_week_join():
    """A slate where SOME games are graded and some are not — the shape that broke.

    Built from the committed 2026 week-1 artifacts when present (the real thing), else synthesised.

    **Partiality is guaranteed by construction, not by the calendar.** `data/predictions/` is
    byte-immutable, but `data/graded/` accumulates every Sunday: joining against all of it was
    partial only while the week was mid-grade, and would have stopped being partial once week 1
    finished grading (2026-09-13) — failing the caller's own `0 < graded < total` guard for a
    scheduling reason, on the very test that pins the D40 defect. Truncating to a strict subset
    keeps the records real and the premise permanently true.
    """
    import json
    from pathlib import Path

    from analytics.join import join

    _REPO_ROOT = Path(__file__).resolve().parent.parent
    pred_p = _REPO_ROOT / "data" / "predictions" / "2026_week_01.json"
    grad_p = _REPO_ROOT / "data" / "graded" / "2026_week_01.json"
    if pred_p.exists() and grad_p.exists():
        preds = json.loads(pred_p.read_text())
        rows = json.loads(grad_p.read_text()).get("graded", [])
        keep = min(len(rows), max(len(preds.get("predictions", [])) - 1, 0))
        if keep:
            return join(preds, {"graded": rows[:keep]})

    preds = {"predictions": [
        {"game_id": f"g{i}-week1", "week": 1, "no_bet": True, "prediction_type": "NO_BET",
         "edge_direction": "home" if i < 4 else "neutral", "confidence_tier": "A",
         "predicted_edge": 0.0, "vegas_spread": -3.0, "clv": None, "closing_spread": None,
         "ats_result": None, "graded_at": None}
        for i in range(11)]}
    graded = {"graded": [
        {"game_id": "g9-week1", "is_hypothetical": True, "ats_result": None, "clv": None,
         "closing_spread": -4.1, "close_as_of": "t", "home_score": 34, "away_score": 8,
         "graded_at": "t"},
        {"game_id": "g10-week1", "is_hypothetical": True, "ats_result": None, "clv": None,
         "closing_spread": -8.5, "close_as_of": "t", "home_score": 10, "away_score": 15,
         "graded_at": "t"}]}
    return join(preds, graded)


def test_partial_week_buckets_come_from_the_claim_not_from_gradedness():
    """**The assertion the pre-R0 adversary said was missing, and the defect it would have caught.**

    `is_hypothetical` is written onto GRADED records only, so on an ungraded row
    `not r.get("is_hypothetical")` reads absence as an affirmative "this was a placed bet". The
    first partially-graded render in the project's history (2026 week 1, 2 of 11 graded) therefore
    reported **"placed bets: 9"** over a slate whose byte-immutable claim is 11/11 NO_BET — and
    suppressed the dormancy note, because `all_no_bet` requires `placed == 0`.

    Buckets are a property of the CLAIM. Gradedness is tracked separately. This pins both.
    """
    from analytics.selectivity import selectivity_report
    from utils.prediction_schema import is_no_bet

    joined = _partial_week_join()
    graded_rows = [r for r in joined if r.get("graded")]
    assert 0 < len(graded_rows) < len(joined), (
        "this test is meaningless unless the week is PARTIALLY graded — some rows graded, some not"
    )

    s = selectivity_report(joined)
    placed = s["placed"]["n_games"]
    lean = s["no_bet_hypothetical"]["n_games"]
    neutral = s["no_lean"]["n_games"]

    assert placed == sum(1 for r in joined if not is_no_bet(r)), (
        "`placed` must equal the count of non-NO_BET predictions in the claim. Any other number "
        "means the bucketing is reading gradedness (or the absence of a graded-only field) as a bet."
    )
    assert placed + lean + neutral == len(joined), (
        f"buckets must partition the slate by construction: {placed}+{lean}+{neutral} != {len(joined)}"
    )
    if placed == 0:
        assert s["all_no_bet_slate"] is True
        assert "selectivity working as designed" in s["note"], (
            "an all-NO_BET slate must carry the dormancy note; suppressing it is how a declined "
            "slate reads as a broken one"
        )


def test_an_ungraded_no_bet_is_never_counted_as_a_placed_bet():
    """The specific inversion, isolated: one NO_BET game, not yet graded."""
    from analytics.join import join
    from analytics.selectivity import selectivity_report

    joined = join({"predictions": [{"game_id": "x-week1", "week": 1, "no_bet": True,
                                    "prediction_type": "NO_BET", "edge_direction": "home"}]}, None)
    assert "is_hypothetical" not in joined[0], "precondition: the ungraded row has no such key"
    s = selectivity_report(joined)
    assert s["placed"]["n_games"] == 0, "an ungraded NO_BET was counted as a placed bet"
    assert s["no_bet_hypothetical"]["n_games"] == 1
