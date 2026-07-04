"""Phase 3c — situational discipline (L2), NO_BET (L4), confidence tiers (L3), and the two
cleanup items. Offline, deterministic. See docs/CALIBRATION_LOG.md (Phase 3c batch)."""

import pytest

from engine.prediction_engine import (
    CONFIDENCE_TIER_A_MIN,
    CONFIDENCE_TIER_B_MIN,
    NO_BET_CONFIDENCE_FLOOR,
    PredictionEngine,
)
from factors.coaching_edge import (
    ExperienceDifferentialCalculator,
    PressureSituationCalculator,
)
from factors.factor_registry import confirm_situational, factor_registry
from factors.market_sentiment import MarketSentimentCalculator
from factors.momentum_factors import (
    CloseGamePerformanceCalculator,
    PointDifferentialTrendsCalculator,
)
from factors.situational_context import DesperationIndexCalculator, RevengeGameCalculator

# ── L2: neutralization — no fabricated fallback; honest-missing 0.0 ───────────────────────────

def _ctx(**kw):
    base = {"week": 8, "vegas_spread": -3.0, "home_team_data": {}, "away_team_data": {}}
    base.update(kw)
    return base


def test_desperation_honest_missing_without_record():
    # No current W-L record (the preseason / dry-run default) -> no signal, never fabricated.
    assert DesperationIndexCalculator().calculate("GEORGIA", "ALABAMA", _ctx()) == 0.0


def test_desperation_uses_real_record_when_present():
    # With a real record the honest bowl/playoff math runs and can produce a non-zero differential.
    ctx = _ctx(
        home_team_data={"derived_metrics": {"current_record": {"wins": 2, "losses": 4}}},
        away_team_data={"derived_metrics": {"current_record": {"wins": 6, "losses": 0}}},
    )
    val = DesperationIndexCalculator().calculate("HOME", "AWAY", ctx)
    assert val != 0.0  # a real desperation gap exists between a 2-4 and a 6-0 team


def test_revenge_dormant():
    assert RevengeGameCalculator().calculate("MICHIGAN", "OHIO STATE", _ctx()) == 0.0


def test_momentum_honest_missing_without_schedule():
    assert PointDifferentialTrendsCalculator().calculate("A", "B", _ctx()) == 0.0
    assert CloseGamePerformanceCalculator().calculate("A", "B", _ctx()) == 0.0


def test_pressure_situation_dormant():
    # Proposed 3c disposition: dormant (was almost entirely fabricated; residue overlaps + double-
    # counted the pricer HFA). Returns 0.0 regardless of inputs.
    assert PressureSituationCalculator().calculate("ALABAMA", "GEORGIA", _ctx()) == 0.0


# ── L2: confirming-signal gate (D15 base-only) ────────────────────────────────────────────────

def _sit(v, name="DesperationIndex"):
    return {"factor_name": name, "category": "situational_context", "value": v, "activated": True}


def _phys(v, name="ByeAdvantage"):
    return {"factor_name": name, "category": "physical", "value": v, "activated": True}


def test_confirm_situational_no_corroboration_withheld():
    assert confirm_situational([_sit(1.2)], None) == {"DesperationIndex"}


def test_confirm_situational_base_gap_agrees():
    assert confirm_situational([_sit(1.2)], base_gap=2.0) == set()


def test_confirm_situational_base_gap_disagrees_withheld():
    assert confirm_situational([_sit(1.2)], base_gap=-2.0) == {"DesperationIndex"}


def test_confirm_situational_physical_agrees_overrides_gap():
    assert confirm_situational([_sit(1.2), _phys(0.8)], base_gap=-2.0) == set()


def test_confirm_situational_physical_opposite_withheld():
    assert confirm_situational([_sit(1.2), _phys(-0.8)], base_gap=-2.0) == {"DesperationIndex"}


def test_confirm_situational_ignores_dormant_and_nonsituational():
    dormant = {"factor_name": "RevengeGame", "category": "situational_context",
               "value": 0.0, "activated": False}
    matchup = {"factor_name": "StyleMismatch", "category": "matchup", "value": 1.0, "activated": True}
    assert confirm_situational([dormant, matchup], None) == set()


# ── Cleanup 1: multiplicative modifier activation keys on abs(value - 1.0) ─────────────────────

def test_dormant_modifier_not_activated():
    r = MarketSentimentCalculator().safe_calculate("A", "B", {"week": 5, "vegas_spread": -3.0})
    assert r["activated"] is False
    assert r["value"] == pytest.approx(1.0)  # neutral, in range (0.85, 1.15)


def test_dormant_modifier_not_counted_in_registry_activation():
    res = factor_registry.calculate_all_factors("GEORGIA", "ALABAMA", {"week": 5, "vegas_spread": -3.0})
    ms = res["factors"].get("MarketSentiment")
    assert ms is not None and ms["activated"] is False


# ── Cleanup 2: ExperienceDifferential handles None/missing coaching data ───────────────────────

def test_experience_differential_none_is_honest_missing_not_crash():
    ctx = {"coaching_comparison": {
        "home_coaching": {"head_coach_experience": None, "tenure_years": None},
        "away_coaching": {"head_coach_experience": 5, "tenure_years": 3}}}
    r = ExperienceDifferentialCalculator().safe_calculate("A", "B", ctx)
    assert r["value"] == 0.0 and r.get("error") is None


def test_experience_differential_missing_key_is_honest_missing():
    ctx = {"coaching_comparison": {"home_coaching": {}, "away_coaching": {}}}
    assert ExperienceDifferentialCalculator().calculate("A", "B", ctx) == 0.0


def test_experience_differential_real_data_computes():
    ctx = {"coaching_comparison": {
        "home_coaching": {"head_coach_experience": 15, "tenure_years": 8},
        "away_coaching": {"head_coach_experience": 1, "tenure_years": 1}}}
    assert ExperienceDifferentialCalculator().calculate("A", "B", ctx) != 0.0


# ── L4: NO_BET floors ─────────────────────────────────────────────────────────────────────────

ENGINE = PredictionEngine()


def _pred(edge_size=2.0, has_edge=True, min_edge=1.0):
    return {"edge_size": edge_size, "has_edge": has_edge, "min_edge_threshold": min_edge,
            "contrarian_spread": -2.0}


def test_no_bet_on_edge_below_threshold():
    no_bet, reasons = ENGINE._evaluate_no_bet(_pred(edge_size=0.3, has_edge=False), 0.7, None)
    assert no_bet and any("edge" in r for r in reasons)


def test_no_bet_on_low_confidence():
    no_bet, reasons = ENGINE._evaluate_no_bet(_pred(), NO_BET_CONFIDENCE_FLOOR - 0.01, None)
    assert no_bet and any("confidence" in r for r in reasons)


def test_no_bet_on_primary_disagreement():
    var = {"variance_level": "moderate", "directional_agreement": {"primary_disagreement": True},
           "recommendation": {"action": "PROCEED_CAUTIOUSLY"}}
    no_bet, reasons = ENGINE._evaluate_no_bet(_pred(), 0.7, var)
    assert no_bet and any("disagree" in r for r in reasons)


def test_no_bet_on_extreme_variance():
    var = {"variance_level": "extreme", "directional_agreement": {"primary_disagreement": False},
           "recommendation": {"action": "AVOID_OR_MINIMUM"}}
    no_bet, _ = ENGINE._evaluate_no_bet(_pred(), 0.7, var)
    assert no_bet


def test_clean_bet_is_not_no_bet():
    var = {"variance_level": "consensus", "directional_agreement": {"primary_disagreement": False},
           "recommendation": {"action": "PROCEED"}}
    no_bet, reasons = ENGINE._evaluate_no_bet(_pred(edge_size=2.5, has_edge=True), 0.7, var)
    assert not no_bet and reasons == []


# ── L3: A/B/C confidence tiers ────────────────────────────────────────────────────────────────

def test_tier_boundaries():
    assert ENGINE._confidence_tier(CONFIDENCE_TIER_A_MIN, "MODERATE_CONTRARIAN") == "A"
    assert ENGINE._confidence_tier(CONFIDENCE_TIER_A_MIN - 0.01, "MODERATE_CONTRARIAN") == "B"
    assert ENGINE._confidence_tier(CONFIDENCE_TIER_B_MIN, "MODERATE_CONTRARIAN") == "B"
    assert ENGINE._confidence_tier(CONFIDENCE_TIER_B_MIN - 0.01, "MODERATE_CONTRARIAN") == "C"


def test_tier_monotonic_in_confidence():
    rank = {"A": 3, "B": 2, "C": 1, None: 0}
    scores = [i / 100 for i in range(15, 96, 5)]
    tiers = [ENGINE._confidence_tier(s, "STRONG_CONTRARIAN") for s in scores]
    assert all(rank[tiers[i]] <= rank[tiers[i + 1]] for i in range(len(tiers) - 1))


def test_only_no_line_and_error_have_no_tier():
    # No-line / error have no meaningful confidence -> no tier.
    assert ENGINE._confidence_tier(0.9, "NO_BETTING_DATA") is None
    assert ENGINE._confidence_tier(0.9, "ERROR") is None
    # A NO_BET game still gets a DIAGNOSTIC tier (explains why it was passed).
    assert ENGINE._confidence_tier(0.9, "NO_BET") == "A"
    assert ENGINE._confidence_tier(0.30, "NO_BET") == "C"


def test_tier_C_is_never_a_bet_grade():
    # The confidence floor equals the B/C boundary, so any bettable prediction clears >= 0.50 -> A/B.
    # Tier C (conf < 0.50) can only occur on a NO_BET (a diagnostic grade), never on a live bet.
    assert NO_BET_CONFIDENCE_FLOOR == CONFIDENCE_TIER_B_MIN
    # A confidence in the C band is below the NO_BET confidence floor -> the game is NO_BET.
    c_band = CONFIDENCE_TIER_B_MIN - 0.05
    no_bet, _ = ENGINE._evaluate_no_bet(_pred(edge_size=2.5, has_edge=True), c_band, None)
    assert no_bet is True


# ── Fabrication extermination tripwire: catches a planted hash/random ─────────────────────────

def test_fabrication_tripwire_would_flag_planted_tokens():
    tokens = ("hashlib", "md5", "random.")
    planted = "team_hash = hashlib.md5(name.encode())"
    assert any(tok in planted for tok in tokens)
    clean = "trend = home_diff - away_diff  # real completed games only"
    assert not any(tok in clean for tok in tokens)
