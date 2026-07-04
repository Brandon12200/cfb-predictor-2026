"""Unit tests for the market_sentiment factor (Phase 1b honesty guarantees).

market_sentiment used to fabricate a "public betting %" from hardcoded team-popularity
/rivalry lists + random noise, and simulate line movement. Phase 1b removed all of that:
signals with no data source are honestly UNAVAILABLE (no contribution + confidence
penalty), never invented (SPEC §5.2, SCHEMA §4, binding principles #2 and #4).
"""

import inspect

import pytest

from factors.market_sentiment import MarketSentimentCalculator
from tests.context_factory import make_context


def _calc():
    return MarketSentimentCalculator()


def test_no_hardcoded_team_names_or_randomness_in_source():
    """The factor's source carries no hardcoded team names, no random, no public-betting
    simulation — the whole point of the Phase 1b cleanup. Checks CODE signatures (not
    bare tokens) so a comment noting a removed symbol doesn't false-trip."""
    src = inspect.getsource(MarketSentimentCalculator)
    banned_code = ("random.uniform(", "random.seed(", "import random",
                   "popular_teams =", "popular_teams=", "rivalry_pairs =", "rivalry_pairs=",
                   "service_academies =", "big_names =", "big_names=",
                   "def _get_public_betting_percentage", "def _simulate_line_movement",
                   "def _detect_trap_patterns",
                   # D19: the team-name hash + game-characteristic heuristics manufactured a
                   # signal from nothing (binding #4) and are removed. Lock them out.
                   "hashlib", "team_hash", "hash_adjustment", "def _analyze_game_characteristics")
    for banned in banned_code:
        assert banned not in src, f"fabrication/hardcoding still present: {banned}"


def test_line_freeze_is_unavailable_not_fabricated():
    """Trap/freeze needs movement history + public-betting share (no source) → 0.0."""
    c = _calc()
    ctx = make_context("GEORGIA", "CLEMSON", week=8, vegas_spread=-7.5)
    assert c._detect_line_freeze("GEORGIA", "CLEMSON", ctx) == 0.0


def test_modifier_is_bounded_and_deterministic():
    c = _calc()
    ctx = make_context("GEORGIA", "CLEMSON", week=8, vegas_spread=-9.5)
    v1 = c.calculate("GEORGIA", "CLEMSON", ctx)
    v2 = c.calculate("GEORGIA", "CLEMSON", ctx)
    assert v1 == v2  # deterministic
    assert c._min_output <= v1 <= c._max_output
    assert (c._min_output, c._max_output) == (0.85, 1.15)  # D19 dormant cap for slice 1.5


def test_dormant_neutral_without_real_line_movement():
    """D19: with line-movement data deferred to slice 1.5, the factor is DORMANT — it returns a
    neutral 1.0 (no effect), never a signal fabricated from a team-name hash or spread heuristics."""
    c = _calc()
    ctx = make_context("GEORGIA", "CLEMSON", week=8, vegas_spread=-9.5)
    assert c._has_line_movement("GEORGIA", "CLEMSON", ctx) is False
    assert c.calculate("GEORGIA", "CLEMSON", ctx) == 1.0
    # different matchup, same absence of movement → still exactly 1.0 (no hash-driven variation)
    assert c.calculate("OHIO STATE", "MICHIGAN", ctx) == 1.0


def test_is_multiplicative_flag_set():
    assert _calc().is_multiplicative is True  # D19: routed through the multiplicative path


def test_active_multiplier_maps_real_sentiment_into_range(monkeypatch):
    """The active branch (reachable once slice 1.5 brings movement data) maps [-1, 1] real
    sentiment into the ratified [0.85, 1.15] cap. Exercised now so the clamp/direction logic
    isn't first tested in production."""
    c = _calc()
    ctx = make_context("GEORGIA", "CLEMSON", week=8, vegas_spread=-7.0)
    monkeypatch.setattr(c, "_has_line_movement", lambda h, a, x: True)
    monkeypatch.setattr(c, "_analyze_game_sentiment", lambda h, a, v, x: 1.0)
    assert c.calculate("GEORGIA", "CLEMSON", ctx) == pytest.approx(1.15)   # full amplify
    monkeypatch.setattr(c, "_analyze_game_sentiment", lambda h, a, v, x: -1.0)
    assert c.calculate("GEORGIA", "CLEMSON", ctx) == pytest.approx(0.85)   # full dampen
    monkeypatch.setattr(c, "_analyze_game_sentiment", lambda h, a, v, x: 0.0)
    assert c.calculate("GEORGIA", "CLEMSON", ctx) == pytest.approx(1.0)    # neutral


def test_missing_line_movement_penalises_confidence():
    """With no opening spread in the snapshot, movement is missing → confidence capped
    and the reason is surfaced (documented deliberate state, SCHEMA §4)."""
    c = _calc()
    ctx = make_context("GEORGIA", "CLEMSON", week=8, vegas_spread=-3.5)
    _, confidence, reasons = c.calculate_with_confidence("GEORGIA", "CLEMSON", ctx)
    assert any("Line-movement history unavailable" in r for r in reasons)


def test_no_context_returns_neutral_modifier():
    assert _calc().calculate("GEORGIA", "CLEMSON", None) == 1.0
