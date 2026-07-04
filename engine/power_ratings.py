"""In-house transparent Elo power ratings (SPEC §6.1, owner decision §16.4).

Current-season-only team quality (Data Recency Principle): ratings are built from
2026 **completed** games only and are never seeded from 2025 results. A
roster-continuity preseason prior (D10) sets each team's week-0 rating so weeks 1–3
aren't garbage; its influence decays as real games accumulate (`rating_uncertainty`,
D11).

Deterministic + explainable (no black boxes): a rating set is a pure function of
`(prior inputs, completed games sorted by (week, start_date, home, away))` →
reproducible from a snapshot. The prediction path recomputes ratings from snapshot
data (memoized by `snapshot_id` upstream); `data/ratings/` is only a derived export.

**Calibration constants (D9) live in `EloConfig`.** They are NOT borrowed from
another sport's Elo (e.g. FiveThirtyEight's NFL model starts from carried-over
priors and only needs small in-season corrections — the opposite regime). They are
set empirically by the **dispersion acceptance test** (`tests/test_power_ratings.py`)
and owner-ratified in `docs/CALIBRATION_LOG.md`; frozen at `v2026-frozen`.

Sign convention here: `home_margin_points` is **positive when the home team is
favored** (predicted points by which home wins). The matchup pricer maps this to the
project's Vegas-spread convention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


# --------------------------------------------------------------------------- #
# Calibration constants (D9 / D11 / D12) — PROVISIONAL until the dispersion test
# passes and the owner ratifies the CALIBRATION_LOG entry. Do not treat as final.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EloConfig:
    """Frozen Elo/prior/uncertainty constants. Every value is a calibration input
    (owner-only, §14.3): proposed via the dispersion test, ratified in
    CALIBRATION_LOG.md, frozen at the tag."""

    baseline: float = 1500.0

    # Decaying K (D9): large early moves differentiate a flat-prior field over ~12
    # games, then damp to stability. `K(n) = k_late + (k_early-k_late)*exp(-n/scale)`
    # where n = the two teams' average games played. The SAME games-played curve
    # drives `rating_uncertainty` (D11), so one schedule serves both.
    k_early: float = 64.0
    k_late: float = 22.0
    k_decay_games: float = 6.0

    # MOV dampener (D9): mult = ln(|margin|+1) * mov_c / (mov_b*|ΔR_winner| + mov_c).
    # The ΔR term corrects autocorrelation (favorites blowing out weak teams don't
    # run away); the log dampens blowout margins.
    mov_c: float = 2.2
    mov_b: float = 0.0018

    # Home-field, in Elo (D9). hfa_elo / elo_per_point = 2.5 points — matches the ~2.5
    # measured 2025 P4 home edge, and below the eroding historical CFB HFA.
    hfa_elo: float = 50.0

    # Elo → points divisor (D9): points of spread per `elo_per_point` Elo. Tuned so the
    # dispersion test RECOVERS the injected 30-pt true spread (recovery ratio ≈ 1.0),
    # i.e. in-season Elo→points lands on the same scale as the SP+ prior (points).
    elo_per_point: float = 20.0

    # Preseason prior (D10). SP+ `rating` is already a point value → Elo offset is
    # rating*elo_per_point. The returning-production fallback is a MODEST, bounded
    # continuity nudge around baseline (NOT a talent ranking): RP above the league
    # reference nudges up, a rebuild nudges down, capped at ±prior_rp_max_elo.
    prior_rp_max_elo: float = 40.0
    rp_reference: float = 0.60  # league-typical returning-production fraction (pivot)
    rp_span: float = 0.35       # RP delta from the pivot that maps to the full nudge

    # rating_uncertainty (D11): decays from 1.0 (0 games, pure prior) to the floor by
    # `uncertainty_games_full` games; inflated for any non-SP+ prior (returning-production
    # OR flat — both weaker seeds). Weeks 1..early_season_weeks are the widen/cap window.
    uncertainty_floor: float = 0.2
    uncertainty_games_full: float = 5.0
    rp_prior_uncertainty_penalty: float = 1.15
    early_season_weeks: int = 3
    # Early-season cap (D11): the rating-derived contribution is scaled by
    # `rating_signal_floor + (1−floor)·(1−uncertainty)` — from `floor` at max
    # uncertainty (preseason) up to 1.0 once settled. A floor (not 0) so a strong
    # SP+ prior still shows through preseason; the ENGINE widens bands / NO_BETs on
    # the high `rating_uncertainty` rather than the pricer discarding the prior.
    rating_signal_floor: float = 0.4

    # spread → win-probability (D12): P(win) = Φ(spread / margin_sigma). σ is grounded
    # in CFB, NOT the NFL 13.5: the 2025 P4 archive market-residual SD is 14.1; σ=16
    # lifts that for our noisier-than-market model + the wider full-slate margins.
    margin_sigma: float = 16.0


DEFAULT_CONFIG = EloConfig()


# --------------------------------------------------------------------------- #
# Result records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PriorResult:
    """A team's preseason rating and where it came from (per-team provenance, D10)."""

    elo: float
    source: str  # "sp+" | "returning_production" | "flat"


@dataclass(frozen=True)
class TeamRating:
    """A team's current rating plus what produced it. `games_played` drives both the
    decaying K and `rating_uncertainty`; `prior_*` preserve the seed for explainability."""

    team: str
    rating: float
    games_played: int
    prior_elo: float
    prior_source: str

    def uncertainty(self, cfg: EloConfig = DEFAULT_CONFIG) -> float:
        return rating_uncertainty(cfg, self.games_played, self.prior_source)


# --------------------------------------------------------------------------- #
# Core Elo math (pure)
# --------------------------------------------------------------------------- #
def k_factor(cfg: EloConfig, games_played: float) -> float:
    """Decaying per-game K: high early, → k_late as games accumulate (D9)."""
    decay = math.exp(-max(0.0, games_played) / cfg.k_decay_games)
    return cfg.k_late + (cfg.k_early - cfg.k_late) * decay


def expected_score(rating_team: float, rating_opp: float, hfa: float) -> float:
    """Logistic expected score for `team` (with home-field applied to its side)."""
    return 1.0 / (1.0 + 10 ** (-((rating_team + hfa) - rating_opp) / 400.0))


def mov_multiplier(cfg: EloConfig, margin: float, winner_rating_diff: float) -> float:
    """Margin-of-victory dampener (D9). `winner_rating_diff` = winner_pre − loser_pre
    (home-field folded into the winner's side), which corrects autocorrelation."""
    return math.log(abs(margin) + 1.0) * cfg.mov_c / (cfg.mov_b * abs(winner_rating_diff) + cfg.mov_c)


def rating_uncertainty(cfg: EloConfig, games_played: float, prior_source: str) -> float:
    """Per-team uncertainty in [floor, 1]: 1.0 at 0 games (pure prior) decaying to the floor
    by `uncertainty_games_full`, inflated for any **non-SP+** prior — returning-production OR
    flat (both are weaker seeds than SP+, so both are at least as uncertain; D11)."""
    base = max(cfg.uncertainty_floor, 1.0 - max(0.0, games_played) / cfg.uncertainty_games_full)
    penalty = 1.0 if prior_source == "sp+" else cfg.rp_prior_uncertainty_penalty
    return min(1.0, base * penalty)


# --------------------------------------------------------------------------- #
# Preseason prior (D10)
# --------------------------------------------------------------------------- #
def _rp_overall(rp: dict[str, Any] | None) -> float | None:
    """Extract an overall returning-production fraction (0–1) from a snapshot RP row.
    Tolerant of the field the normalize converter lands on; None if unusable."""
    if not rp:
        return None
    for key in ("overall", "percent_ppa", "total_ppa"):
        val = rp.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def preseason_prior(team: str, sp_ratings: dict[str, dict] | None,
                    returning_production: dict[str, dict] | None,
                    cfg: EloConfig = DEFAULT_CONFIG) -> PriorResult:
    """Hybrid roster-continuity prior (D10): prefer preseason SP+ when present (its
    `rating` is a point value → Elo offset), else a bounded returning-production
    continuity nudge, else honest flat baseline (recorded, never fabricated)."""
    sp = (sp_ratings or {}).get(team)
    if sp is not None and sp.get("rating") is not None:
        try:
            return PriorResult(cfg.baseline + float(sp["rating"]) * cfg.elo_per_point, "sp+")
        except (TypeError, ValueError):
            pass
    overall = _rp_overall((returning_production or {}).get(team))
    if overall is not None:
        delta = max(-1.0, min(1.0, (overall - cfg.rp_reference) / cfg.rp_span))
        return PriorResult(cfg.baseline + delta * cfg.prior_rp_max_elo, "returning_production")
    return PriorResult(cfg.baseline, "flat")


# --------------------------------------------------------------------------- #
# Rating computation over a season's completed games (pure, deterministic)
# --------------------------------------------------------------------------- #
def _game_sort_key(g: dict) -> tuple:
    """Stable ordering: week, then kickoff, then teams — snapshot games carry no id."""
    return (
        g.get("week") if g.get("week") is not None else 0,
        str(g.get("start_date") or ""),
        str(g.get("home_team") or ""),
        str(g.get("away_team") or ""),
    )


def _is_completed(g: dict) -> bool:
    return bool(g.get("completed")) and g.get("home_points") is not None and g.get("away_points") is not None


def compute_ratings(games: list[dict], sp_ratings: dict[str, dict] | None = None,
                    returning_production: dict[str, dict] | None = None,
                    teams: list[str] | None = None,
                    cfg: EloConfig = DEFAULT_CONFIG) -> dict[str, TeamRating]:
    """Full-season Elo from the preseason prior over completed games only.

    `games` are canonical `ScheduleGame` dicts (UPPERCASE teams). The team universe is
    every team appearing in `games` (union `teams` if given). Updates are zero-sum
    (winner +Δ, loser −Δ) so the mean stays at baseline and dispersion is meaningful.
    Pure and order-stable → identical output for a given snapshot."""
    universe: set[str] = set(teams or [])
    for g in games:
        if g.get("home_team"):
            universe.add(str(g["home_team"]))
        if g.get("away_team"):
            universe.add(str(g["away_team"]))

    priors = {t: preseason_prior(t, sp_ratings, returning_production, cfg) for t in universe}
    ratings: dict[str, float] = {t: p.elo for t, p in priors.items()}
    played: dict[str, int] = {t: 0 for t in universe}

    for g in sorted((g for g in games if _is_completed(g)), key=_game_sort_key):
        home, away = str(g["home_team"]), str(g["away_team"])
        if home not in ratings or away not in ratings:
            continue
        hp, ap = float(g["home_points"]), float(g["away_points"])
        if hp == ap:  # CFB has no ties in the modern era; skip defensively
            continue
        neutral = bool(g.get("neutral_site"))
        hfa = 0.0 if neutral else cfg.hfa_elo

        r_home, r_away = ratings[home], ratings[away]
        e_home = expected_score(r_home, r_away, hfa)
        s_home = 1.0 if hp > ap else 0.0

        # Winner rating diff (home-field folded into the winner's side) for the dampener.
        if hp > ap:
            winner_diff = (r_home + hfa) - r_away
        else:
            winner_diff = r_away - (r_home + hfa)
        mult = mov_multiplier(cfg, hp - ap, winner_diff)

        k = k_factor(cfg, 0.5 * (played[home] + played[away]))
        delta = k * mult * (s_home - e_home)
        ratings[home] = r_home + delta
        ratings[away] = r_away - delta
        played[home] += 1
        played[away] += 1

    return {
        t: TeamRating(team=t, rating=ratings[t], games_played=played[t],
                      prior_elo=priors[t].elo, prior_source=priors[t].source)
        for t in universe
    }


# --------------------------------------------------------------------------- #
# Matchup helpers (used by the pricer and projections)
# --------------------------------------------------------------------------- #
def home_margin_points(home: TeamRating, away: TeamRating,
                       cfg: EloConfig = DEFAULT_CONFIG, neutral_site: bool = False) -> float:
    """Rating-only predicted margin, **positive when home is favored** (points)."""
    hfa = 0.0 if neutral_site else cfg.hfa_elo
    return ((home.rating + hfa) - away.rating) / cfg.elo_per_point


def matchup_uncertainty(home: TeamRating, away: TeamRating,
                        cfg: EloConfig = DEFAULT_CONFIG) -> float:
    """The matchup's `rating_uncertainty` — the less-established side dominates."""
    return max(home.uncertainty(cfg), away.uncertainty(cfg))


def rating_signal_weight(uncertainty: float, cfg: EloConfig = DEFAULT_CONFIG) -> float:
    """Early-season cap (D11): scale the rating-derived signal from `rating_signal_floor`
    (max uncertainty, preseason) up to 1.0 (settled). Weeks 1–3 thus lean more on
    physical/scheduling factors while ratings are unsettled, without zeroing the prior."""
    floor = cfg.rating_signal_floor
    return floor + (1.0 - floor) * (1.0 - uncertainty)


def spread_to_win_prob(margin_points: float, cfg: EloConfig = DEFAULT_CONFIG) -> float:
    """P(win) from a predicted point margin via the normal CDF (D12). σ is a CFB
    margin SD (owner-ratified), documented in docs/SCHEMA.md."""
    return 0.5 * (1.0 + math.erf(margin_points / (cfg.margin_sigma * math.sqrt(2.0))))
