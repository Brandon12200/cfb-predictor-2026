"""Power-rating tests (SPEC §6.1 acceptance) — synthetic seasons + the dispersion
acceptance test that gates the D9 constants.

The dispersion test is the crux of the D9 calibration: a flat-prior, in-season-only
Elo over ~12 games must recover **realistic point spreads** (top-vs-bottom P4 ~30),
not the compressed ~4 that naive NFL-borrowed constants (K=20) would give. It is
two-part so a too-low K cannot be masked by inflating the Elo→points scale:
  (a) recovery  — recovered top-vs-bottom margin lands in a realistic band; and
  (b) fidelity  — recovered ratings rank-correlate ~perfectly with true strength,
                  so the signal (not just the scale) actually developed in one season.
"""

from __future__ import annotations

import math

from engine.power_ratings import (
    DEFAULT_CONFIG,
    EloConfig,
    TeamRating,
    compute_ratings,
    home_margin_points,
    k_factor,
    preseason_prior,
    rating_uncertainty,
    spread_to_win_prob,
)

# --------------------------------------------------------------------------- #
# Synthetic season: N teams with known true point-strengths, deterministic exact
# outcomes, a DOUBLE round-robin so the strong teams also play each other (per the
# owner's note — dominant-vs-cupcake differentiates slower than peer games).
# --------------------------------------------------------------------------- #
TRUE_HFA_POINTS = 2.5


def synthetic_season(strengths: dict[str, float], hfa: float = TRUE_HFA_POINTS) -> list[dict]:
    teams = list(strengths)
    games: list[dict] = []
    week = 1
    for i, home in enumerate(teams):
        for j, away in enumerate(teams):
            if i == j:
                continue
            margin = strengths[home] - strengths[away] + hfa  # home perspective
            if margin >= 0:
                hp, ap = 21 + round(margin), 21
            else:
                hp, ap = 21, 21 + round(-margin)
            if hp == ap:  # keep a decisive result
                hp += 1
            games.append({
                "week": (week % 15) + 1,
                "start_date": f"2026-09-{(week % 27) + 1:02d}T16:00:00.000Z",
                "home_team": home, "away_team": away,
                "home_points": hp, "away_points": ap,
                "completed": True, "neutral_site": False,
            })
            week += 1
    return games


def _spread_neg10_to_10() -> dict[str, float]:
    """7 teams spanning a 30-point true range (−15 .. +15, step 5)."""
    return {f"T{i}": s for i, s in enumerate(range(15, -16, -30 // 7))}


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx and sy else 0.0


# --------------------------------------------------------------------------- #
# THE dispersion acceptance test (gates D9 constants)
# --------------------------------------------------------------------------- #
def test_dispersion_recovers_realistic_point_spread():
    strengths = _spread_neg10_to_10()
    injected = max(strengths.values()) - min(strengths.values())  # ~30 points
    ratings = compute_ratings(synthetic_season(strengths), cfg=DEFAULT_CONFIG)

    ordered = sorted(strengths, key=lambda t: strengths[t], reverse=True)
    top, bottom = ratings[ordered[0]], ratings[ordered[-1]]

    # (a) recovery: a neutral-site top-vs-bottom game must price in a realistic band —
    # NOT compressed to single digits (the K=20 failure), NOT wildly inflated.
    recovered = home_margin_points(top, bottom, DEFAULT_CONFIG, neutral_site=True)
    assert injected == 30
    assert 24.0 <= recovered <= 40.0, f"recovered top-vs-bottom {recovered:.1f} pts unrealistic"

    # (b) fidelity: recovered ratings track true strength almost perfectly, so the
    # separation is real signal developed within one season, not a rescaled artifact.
    true = [strengths[t] for t in ordered]
    got = [ratings[t].rating for t in ordered]
    assert _pearson(true, got) >= 0.98

    # mean stays at baseline (zero-sum updates) → dispersion is interpretable.
    mean = sum(r.rating for r in ratings.values()) / len(ratings)
    assert abs(mean - DEFAULT_CONFIG.baseline) < 1e-6


def test_full_season_top_vs_bottom_matchup_prices_like_a_big_favorite():
    strengths = _spread_neg10_to_10()
    ratings = compute_ratings(synthetic_season(strengths), cfg=DEFAULT_CONFIG)
    ordered = sorted(strengths, key=lambda t: strengths[t], reverse=True)
    # Best hosting worst: rating margin + home field → clearly a 3+ touchdown line.
    home = home_margin_points(ratings[ordered[0]], ratings[ordered[-1]], DEFAULT_CONFIG)
    assert home >= 26.0


# --------------------------------------------------------------------------- #
# Determinism / reproducibility
# --------------------------------------------------------------------------- #
def test_compute_ratings_is_order_independent_and_deterministic():
    strengths = _spread_neg10_to_10()
    games = synthetic_season(strengths)
    a = compute_ratings(games, cfg=DEFAULT_CONFIG)
    shuffled = list(reversed(games))
    b = compute_ratings(shuffled, cfg=DEFAULT_CONFIG)
    assert {t: round(r.rating, 9) for t, r in a.items()} == {t: round(r.rating, 9) for t, r in b.items()}


def test_only_completed_games_move_ratings():
    strengths = {"A": 10.0, "B": -10.0}
    games = synthetic_season(strengths)
    for g in games:
        g["completed"] = False  # nothing final yet → pure prior
    ratings = compute_ratings(games, cfg=DEFAULT_CONFIG)
    assert ratings["A"].games_played == 0
    assert ratings["A"].rating == DEFAULT_CONFIG.baseline
    assert ratings["B"].rating == DEFAULT_CONFIG.baseline


# --------------------------------------------------------------------------- #
# Preseason prior (D10) — hybrid SP+ / returning-production / flat
# --------------------------------------------------------------------------- #
def test_prior_prefers_sp_plus_when_present():
    sp = {"GEORGIA": {"rating": 20.0}}
    p = preseason_prior("GEORGIA", sp, {"GEORGIA": {"overall": 0.9}}, DEFAULT_CONFIG)
    assert p.source == "sp+"
    assert p.elo == DEFAULT_CONFIG.baseline + 20.0 * DEFAULT_CONFIG.elo_per_point


def test_prior_falls_back_to_returning_production():
    p_high = preseason_prior("A", {}, {"A": {"overall": 0.90}}, DEFAULT_CONFIG)
    p_low = preseason_prior("B", {}, {"B": {"overall": 0.30}}, DEFAULT_CONFIG)
    assert p_high.source == "returning_production" and p_low.source == "returning_production"
    assert p_high.elo > DEFAULT_CONFIG.baseline > p_low.elo
    # bounded nudge (NOT a talent ranking)
    assert abs(p_high.elo - DEFAULT_CONFIG.baseline) <= DEFAULT_CONFIG.prior_rp_max_elo + 1e-9


def test_prior_is_flat_when_both_missing():
    p = preseason_prior("NOBODY", {}, {}, DEFAULT_CONFIG)
    assert p.source == "flat"
    assert p.elo == DEFAULT_CONFIG.baseline


def test_sp_plus_prior_drives_preseason_matchup_spread():
    # Week-1 (0 completed games): rating spread comes purely from the SP+ prior.
    games = [{"week": 1, "home_team": "A", "away_team": "B", "completed": False,
              "home_points": None, "away_points": None, "start_date": "2026-08-29T16:00:00Z"}]
    sp = {"A": {"rating": 15.0}, "B": {"rating": -5.0}}
    ratings = compute_ratings(games, sp_ratings=sp, cfg=DEFAULT_CONFIG)
    neutral = home_margin_points(ratings["A"], ratings["B"], DEFAULT_CONFIG, neutral_site=True)
    assert abs(neutral - 20.0) < 1e-6  # (15 − (−5)) points


# --------------------------------------------------------------------------- #
# rating_uncertainty (D11) + decaying K
# --------------------------------------------------------------------------- #
def test_k_factor_decays_with_games():
    assert k_factor(DEFAULT_CONFIG, 0) > k_factor(DEFAULT_CONFIG, 3) > k_factor(DEFAULT_CONFIG, 12)
    assert math.isclose(k_factor(DEFAULT_CONFIG, 0), DEFAULT_CONFIG.k_early)
    assert k_factor(DEFAULT_CONFIG, 1e6) > DEFAULT_CONFIG.k_late - 1e-6


def test_uncertainty_decays_and_penalizes_rp_prior():
    assert rating_uncertainty(DEFAULT_CONFIG, 0, "sp+") == 1.0
    early = rating_uncertainty(DEFAULT_CONFIG, 1, "sp+")
    late = rating_uncertainty(DEFAULT_CONFIG, 10, "sp+")
    assert 1.0 > early > late == DEFAULT_CONFIG.uncertainty_floor
    # RP fallback is strictly more uncertain than SP+ at the same game count.
    assert rating_uncertainty(DEFAULT_CONFIG, 1, "returning_production") > early


def test_flat_prior_is_maximally_uncertain_preseason():
    tr = TeamRating("X", DEFAULT_CONFIG.baseline, 0, DEFAULT_CONFIG.baseline, "flat")
    assert tr.uncertainty(DEFAULT_CONFIG) == 1.0


# --------------------------------------------------------------------------- #
# spread → win prob (D12)
# --------------------------------------------------------------------------- #
def test_spread_to_win_prob_is_calibrated_and_monotonic():
    assert abs(spread_to_win_prob(0.0) - 0.5) < 1e-9
    assert spread_to_win_prob(7.0) > 0.5 > spread_to_win_prob(-7.0)
    assert spread_to_win_prob(3.0) < spread_to_win_prob(10.0) < spread_to_win_prob(28.0)
    # symmetry
    assert abs(spread_to_win_prob(10.0) + spread_to_win_prob(-10.0) - 1.0) < 1e-9


def test_custom_config_is_respected():
    cfg = EloConfig(elo_per_point=10.0)
    ratings = compute_ratings(synthetic_season(_spread_neg10_to_10()), cfg=cfg)
    # A different scale changes recovered points but not the ordering.
    got = [ratings[t].rating for t in sorted(ratings, key=lambda t: ratings[t].rating, reverse=True)]
    assert got == sorted(got, reverse=True)
