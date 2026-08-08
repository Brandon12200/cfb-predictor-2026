"""Phase 4 — measurement & analytics v2 (SPEC §8). Ratification-gate tests: the graded-record
schema (D22 / f2), the CLV neutral-case correction (f3), and the requirement-2 pin that grades the
canonical schema-v2 golden record shape including the full ATS ternary.

Grading NEVER touches the byte-immutable ``data/predictions/`` files (D22); it produces a separate
graded artifact. The "filled" v2 record is a JOIN only. These tests pin the *shape* of that graded
artifact and the grading arithmetic before any writer persists it.
"""
from __future__ import annotations

import json
from pathlib import Path

from analytics.calibration_evidence import ats_outcome
from analytics.grading import grade_fixture, grade_game
from utils.prediction_schema import (
    GRADED_RECORD_KEYS,
    GRADED_SCHEMA_VERSION,
    build_graded_record,
    clv,
)

ROOT = Path(__file__).resolve().parent.parent
V2_GOLDEN = ROOT / "docs" / "examples" / "prediction_schema_v2_2026_week_01.json"
GRADED_GOLDEN = ROOT / "docs" / "examples" / "graded_record_2026_week_01.json"
GRADED_FIXTURE = ROOT / "docs" / "examples" / "graded_fixture_2026_week_01.json"


# ── f3 — CLV neutral case ────────────────────────────────────────────────────────────────────────

def test_clv_neutral_no_side_returns_none_never_zero():
    # No side ⇒ no perspective ⇒ undefined ⇒ None (never 0.0, which means "matched the close").
    assert clv(-3.0, -4.0, "neutral") is None
    assert clv(-3.0, -3.0, "neutral") is None
    assert clv(2.8, 2.8, None) is None


def test_clv_zero_is_a_legit_value_for_a_taken_side():
    # 0.0 means our number exactly matched the close — a value, distinct from None.
    assert clv(2.8, 2.8, "home") == 0.0
    assert clv(-3.0, -3.0, "away") == 0.0


# ── graded-record schema shape ───────────────────────────────────────────────────────────────────

def test_graded_record_key_inventory():
    pred = {"game_id": "a-vs-b-week1", "home_team": "B", "away_team": "A", "week": 1,
            "no_bet": True, "prediction_type": "NO_BET"}
    result = {"home_score": 21, "away_score": 14}
    rec = build_graded_record(pred, result, closing_spread=-3.0, close_as_of="t",
                              clv_points=1.0, ats_result="win", graded_at="g")
    assert set(rec) == set(GRADED_RECORD_KEYS)


def test_graded_golden_records_match_key_inventory_and_schema_version():
    golden = json.loads(GRADED_GOLDEN.read_text())
    assert golden["meta"]["schema_version"] == GRADED_SCHEMA_VERSION
    assert golden["meta"]["engine"] == "grading_v1"
    for rec in golden["graded"]:
        assert set(rec) == set(GRADED_RECORD_KEYS)


# ── requirement 2 — grade the canonical schema-v2 golden record, full ATS ternary ────────────────

def test_grades_schema_v2_golden_record_reproduces_graded_golden():
    """Grading the committed v2 golden slate + the committed fixture (via the real
    ``analytics.grading.grade_fixture`` path) reproduces the committed graded golden byte-for-byte
    (structural). Pins the grading path to the canonical v2 artifact from day one."""
    v2 = json.loads(V2_GOLDEN.read_text())
    fixture = json.loads(GRADED_FIXTURE.read_text())
    produced = grade_fixture(v2, fixture)
    committed = json.loads(GRADED_GOLDEN.read_text())
    assert json.dumps(produced, sort_keys=True) == json.dumps(committed, sort_keys=True)
    assert committed["meta"]["_synthetic"] is True     # the one fake data file announces itself


def test_grade_game_is_idempotent_and_per_game():
    """The Phase-5 catch-up shape: grade_game is a pure function of (pred, result, closing_obs) —
    two calls with the same inputs produce identical records (bar the caller's graded_at)."""
    pred = {"game_id": "x-vs-y-week3", "home_team": "Y", "away_team": "X", "week": 3,
            "vegas_spread": -3.0, "edge_direction": "home", "no_bet": False,
            "prediction_type": "SLIGHT_CONTRARIAN"}
    result = {"home_score": 21, "away_score": 14}
    obs = {"consensus_spread": -4.0, "fetched_at": "2026-09-12T15:00:00+00:00"}
    a = grade_game(pred, result, obs, graded_at="g")
    b = grade_game(pred, result, obs, graded_at="g")
    assert a == b
    assert a["clv"] == 1.0 and a["ats_result"] == "win" and a["closing_spread"] == -4.0


def test_graded_golden_exercises_win_loss_and_null_no_side():
    golden = json.loads(GRADED_GOLDEN.read_text())
    by_id = {r["game_id"]: r for r in golden["graded"]}
    # win (clv +1.0), win (clv 0.0 legit), loss (clv -1.0), loss (honest-missing close -> clv null)
    assert by_id["clemson-vs-lsu-week1"]["ats_result"] == "win"
    assert by_id["clemson-vs-lsu-week1"]["clv"] == 1.0
    assert by_id["smu-vs-florida-state-week1"]["ats_result"] == "win"
    assert by_id["smu-vs-florida-state-week1"]["clv"] == 0.0            # legit 0.0, not null
    assert by_id["colorado-vs-georgia-tech-week1"]["ats_result"] == "loss"
    assert by_id["colorado-vs-georgia-tech-week1"]["clv"] == -1.0
    # graded, no closing line: ats present, closing/ clv honest-missing (null)
    assert by_id["miami-vs-stanford-week1"]["ats_result"] == "loss"
    assert by_id["miami-vs-stanford-week1"]["closing_spread"] is None
    assert by_id["miami-vs-stanford-week1"]["clv"] is None
    # neutral no-lean: ats + clv null even when a closing line WAS captured (no side to value)
    assert by_id["baylor-vs-auburn-week1"]["ats_result"] is None
    assert by_id["baylor-vs-auburn-week1"]["clv"] is None
    assert by_id["baylor-vs-auburn-week1"]["closing_spread"] == -7.0
    # every NO_BET game is graded as hypothetical
    assert all(r["is_hypothetical"] for r in golden["graded"])


def test_grades_the_push_ternary_on_an_integer_line():
    """The 4th ATS outcome. A push needs an integer line (margin == -vegas exactly), which the
    non-integer golden lines can't produce — so it's pinned here on a crafted v2-shaped record."""
    pred = {"game_id": "x-vs-y-week1", "home_team": "Y", "away_team": "X", "week": 1,
            "vegas_spread": -7.0, "edge_direction": "home", "no_bet": False,
            "prediction_type": "SLIGHT_CONTRARIAN"}
    result = {"home_score": 28, "away_score": 21}          # margin +7, cover = 7 + (-7.0) = 0 -> push
    ats = ats_outcome(pred, result)
    assert ats == "push"
    rec = build_graded_record(pred, result, closing_spread=-7.0, close_as_of="t",
                              clv_points=clv(-7.0, -7.0, "home"), ats_result=ats, graded_at="g")
    assert rec["ats_result"] == "push"
    assert rec["clv"] == 0.0            # a real bet whose number matched the close
    assert rec["is_hypothetical"] is False
    assert set(rec) == set(GRADED_RECORD_KEYS)


# ── reporting / attribution cluster (Step 3) ─────────────────────────────────────────────────────

def _golden_joined():
    from analytics.join import join
    v2 = json.loads(V2_GOLDEN.read_text())
    g = json.loads(GRADED_GOLDEN.read_text())
    return join(v2, g)


def test_join_merges_graded_fields_by_game_id():
    from analytics.join import join
    v2 = json.loads(V2_GOLDEN.read_text())
    g = json.loads(GRADED_GOLDEN.read_text())
    joined = join(v2, g)
    assert len(joined) == len(v2["predictions"])
    lsu = next(r for r in joined if r["game_id"] == "clemson-vs-lsu-week1")
    assert lsu["graded"] is True and lsu["ats_result"] == "win" and lsu["clv"] == 1.0
    # the on-disk prediction record's grading slots stay null (join is in memory only)
    disk = next(r for r in v2["predictions"] if r["game_id"] == "clemson-vs-lsu-week1")
    assert disk["clv"] is None and disk["closing_spread"] is None


def test_kpi_pack_empty_when_all_no_bet():
    from analytics.kpis import kpi_pack
    graded = json.loads(GRADED_GOLDEN.read_text())["graded"]
    pack = kpi_pack(graded)                          # all hypothetical -> no placed bets
    assert pack["ats"]["n_graded"] == 0
    assert pack["roi_at_110"]["roi"] is None and pack["max_drawdown"] == 0.0


def test_selectivity_flags_all_no_bet_slate():
    from analytics.selectivity import selectivity_report
    s = selectivity_report(_golden_joined())
    assert s["all_no_bet_slate"] is True
    assert s["no_bet_hypothetical"]["n_games"] == 4       # 4 home-lean NO_BETs graded hypothetically
    assert s["no_lean"]["n_games"] == 7                   # 7 neutral no-side


def test_attribution_measures_per_sub_signal_on_golden():
    from analytics.attribution import per_factor
    a = per_factor(_golden_joined())
    assert a["meta"]["attributable"] is True
    tb = a["factors"]["TravelBurden"]
    assert tb["n_activated"] == 4 and tb["wins"] == 2 and tb["losses"] == 2


def test_attribution_unavailable_on_v1_flat_archive():
    from analytics.attribution import per_factor
    from utils.prediction_schema import convert_v1_to_v2
    arch = json.loads((ROOT / "data/archive/2025/predictions/2025_week_01.json").read_text())
    joined = [convert_v1_to_v2(p) for p in arch["predictions"]]
    for r in joined:
        r["ats_result"] = "win"
    a = per_factor(joined)
    assert a["meta"]["attributable"] is False       # v1 flat breakdown — never faked per-signal


def _retro_weeks():
    from analytics.grading import build_graded
    from utils.prediction_schema import convert_v1_to_v2
    weeks = []
    for pf in sorted((ROOT / "data/archive/2025/predictions").glob("*.json")):
        wk = int(pf.stem.split("_week_")[1])
        v1 = json.loads(pf.read_text())
        env = {"meta": {"week": wk, "year": 2025},
               "predictions": [convert_v1_to_v2(p) for p in v1["predictions"]]}
        res = json.loads((ROOT / f"data/archive/2025/results/2025_week_{wk:02d}_results.json").read_text())
        weeks.append((env, build_graded(env, res["results"], None, graded_at="t")))
    return weeks


def test_report_cells_state_their_reason_inline():
    """The general rule: any honest-missing / honest-empty cell explains itself inline (September
    readers see cells, not preambles)."""
    from analytics.reports import render_season, render_week
    # 2025 retro: honest-missing CLV, the tier non-separation finding, and the v1 no-NO_BET note.
    retro = render_season(_retro_weeks(), title="retro")
    assert "no closing lines captured (honest-missing)" in retro
    assert "Finding:" in retro and "not distinguishing anything" in retro
    assert "predates the NO_BET concept" in retro
    assert "Mixed slate." not in retro                     # the orphaned fragment is gone
    # all-NO_BET golden week: empty KPI + empty tier table each say why.
    weekly = render_week(json.loads(V2_GOLDEN.read_text()), json.loads(GRADED_GOLDEN.read_text()))
    assert "No bets placed" in weekly
    assert "No graded bets in these tiers yet" in weekly


def test_retro_reconciles_the_d17_baseline():
    """The 2025 retro over the full archive must reproduce the honest D17 baseline (~46.6% ATS over
    294 graded bets) — a regression pin on the whole grading + KPI stack."""
    from analytics.grading import build_graded
    from analytics.kpis import kpi_pack
    from utils.prediction_schema import convert_v1_to_v2
    pred_dir = ROOT / "data/archive/2025/predictions"
    res_dir = ROOT / "data/archive/2025/results"
    all_graded = []
    for pf in sorted(pred_dir.glob("*.json")):
        wk = int(pf.stem.split("_week_")[1])
        v1 = json.loads(pf.read_text())
        env = {"meta": {"week": wk, "year": 2025},
               "predictions": [convert_v1_to_v2(p) for p in v1["predictions"]]}
        results = json.loads((res_dir / f"2025_week_{wk:02d}_results.json").read_text())["results"]
        all_graded += build_graded(env, results, None, graded_at="t")["graded"]
    pack = kpi_pack(all_graded)
    assert pack["ats"]["n_graded"] == 294
    assert 0.45 <= pack["ats"]["ats_win_pct"] <= 0.48      # 46.6%
    assert pack["roi_at_110"]["roi"] < 0                    # honest slightly-losing season
