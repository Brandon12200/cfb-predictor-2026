"""Unit tests for the market_sentiment factor (Phase 1b honesty guarantees).

market_sentiment used to fabricate a "public betting %" from hardcoded team-popularity
/rivalry lists + random noise, and simulate line movement. Phase 1b removed all of that:
signals with no data source are honestly UNAVAILABLE (no contribution + confidence
penalty), never invented (SPEC §5.2, SCHEMA §4, binding principles #2 and #4).
"""

import inspect

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
                   "def _detect_trap_patterns")
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
    assert v1 == v2  # deterministic (stable hashlib, no random)
    assert c._min_output <= v1 <= c._max_output


def test_missing_line_movement_penalises_confidence():
    """With no opening spread in the snapshot, movement is missing → confidence capped
    and the reason is surfaced (documented deliberate state, SCHEMA §4)."""
    c = _calc()
    ctx = make_context("GEORGIA", "CLEMSON", week=8, vegas_spread=-3.5)
    _, confidence, reasons = c.calculate_with_confidence("GEORGIA", "CLEMSON", ctx)
    assert any("Line-movement history unavailable" in r for r in reasons)


def test_no_context_returns_neutral_modifier():
    assert _calc().calculate("GEORGIA", "CLEMSON", None) == 1.0
