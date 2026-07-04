"""Matchup pricer (SPEC §6.3): price any matchup → a model spread.

`model spread = rating differential + home-field value + Phase-1 schedule-intelligence
adjustments`, on the **identical path** for real slate games and hypotheticals. The
rating differential comes from the in-house Elo (`engine.power_ratings`); the schedule
adjustment is a pure function of `data.schedule_intel.compute_schedule_intel`, so a
hypothetical for any two FBS teams at any venue/date reuses the same code.

**Sign convention:** `model_spread` is the home team's spread in the project's Vegas
convention — **negative when home is favored** (like `vegas_spread`). `home_margin` is
the predicted points by which home wins (positive = home favored).

**Determinism:** ratings are a pure function of snapshot `data` (memoized by
`snapshot_id`); the pricer adds only arithmetic → reproducible from a snapshot.

**Freeze / scope note:** the schedule-adjustment coefficients (`ScheduleAdjustmentConfig`)
are a conservative Phase-2 baseline over the most robust physical signals. Phase 3's
calibrated factor system (activation thresholds, confirming factors, per-sub-signal
breakdown) supersedes them; they are proposed for owner ratification like the D9 Elo
constants and kept intentionally small so a mis-set value can't dominate a model spread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data.schedule_intel import compute_schedule_intel
from engine.power_ratings import (
    DEFAULT_CONFIG,
    EloConfig,
    PriorResult,
    TeamRating,
    compute_ratings,
    matchup_uncertainty,
    preseason_prior,
    rating_signal_weight,
)


@dataclass(frozen=True)
class ScheduleAdjustmentConfig:
    """Proposed (owner-ratified) Phase-2 physical-adjustment coefficients, in POINTS,
    from the home team's perspective. Bounded and conservative; Phase 3 recalibrates."""

    bye_value: float = 1.0          # prep advantage off a bye (the other team didn't)
    short_week_penalty: float = 1.0  # < 7 days' rest and the other team isn't
    tz_per_zone: float = 0.6         # per net time-zone the AWAY team crosses more
    travel_cap: float = 2.0          # cap on the travel/timezone term
    altitude_threshold_ft: float = 4000.0  # home acclimated at a high-elevation stadium
    altitude_value: float = 1.2


DEFAULT_SCHEDULE_CONFIG = ScheduleAdjustmentConfig()


@dataclass(frozen=True)
class PricedMatchup:
    """A priced matchup — the model spread plus a fully explainable breakdown."""

    home_team: str
    away_team: str
    model_spread: float           # = total_spread; home spread, NEGATIVE = home favored (Vegas conv.)
    home_margin: float            # = total margin; predicted points home wins by (+ = home favored)
    rating_component: float       # early-season-weighted rating margin (points, home persp)
    schedule_component: float     # = schedule_adjustment; net physical adjustment (points, home persp)
    # D15 decomposition. In MARGIN space (positive = home favored): total = base +
    # schedule_adjustment, i.e. home_margin = base_margin + schedule_component. In SPREAD space
    # the sign flips (spread = −margin), so model_spread = base_spread − schedule_component — a
    # SUBTRACTION. base = team quality (Elo diff + HFA); schedule_adjustment = physical. Consumers
    # pick the honest lane: hypothetical → total; the model-vs-market diagnostic + any
    # confirming-signal rule → the BASE gap (base_spread − vegas), which excludes schedule so it
    # can't confirm a schedule factor with itself.
    base_margin: float            # rating_component + home field (team quality only, + = home)
    base_spread: float            # = −base_margin (home spread; the diagnostic/confirm lane)
    rating_uncertainty: float
    neutral_site: bool
    home_rating: float
    away_rating: float
    home_prior_source: str
    away_prior_source: str
    rating_signal_weight: float
    breakdown: dict[str, Any] = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "model_spread": round(self.model_spread, 2),
            "home_margin": round(self.home_margin, 2),
            "base_spread": round(self.base_spread, 2),
            "base_margin": round(self.base_margin, 2),
            "schedule_adjustment": round(self.schedule_component, 2),
            "rating_component": round(self.rating_component, 2),
            "schedule_component": round(self.schedule_component, 2),
            "rating_uncertainty": round(self.rating_uncertainty, 3),
            "rating_signal_weight": round(self.rating_signal_weight, 3),
            "neutral_site": self.neutral_site,
            "home_rating": round(self.home_rating, 1),
            "away_rating": round(self.away_rating, 1),
            "home_prior_source": self.home_prior_source,
            "away_prior_source": self.away_prior_source,
            "breakdown": self.breakdown,
            "caveats": list(self.caveats),
        }


# --------------------------------------------------------------------------- #
# Schedule-intelligence adjustment (pure; POINTS, positive favors home)
# --------------------------------------------------------------------------- #
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def schedule_adjustment(home_intel: dict, away_intel: dict, neutral_site: bool,
                        cfg: ScheduleAdjustmentConfig = DEFAULT_SCHEDULE_CONFIG,
                        ) -> tuple[float, dict[str, float]]:
    """Net physical adjustment in points (positive favors home), from the two teams'
    `compute_schedule_intel` outputs. Uses only robust, non-overlapping signals; missing
    inputs simply contribute nothing (recorded absent, never fabricated)."""
    parts: dict[str, float] = {}

    hb, ab = bool(home_intel.get("bye")), bool(away_intel.get("bye"))
    if hb and not ab:
        parts["bye"] = cfg.bye_value
    elif ab and not hb:
        parts["bye"] = -cfg.bye_value

    hs, as_ = bool(home_intel.get("short_week")), bool(away_intel.get("short_week"))
    if hs and not as_:
        parts["short_week"] = -cfg.short_week_penalty
    elif as_ and not hs:
        parts["short_week"] = cfg.short_week_penalty

    tz_diff = (away_intel.get("time_zones_crossed") or 0) - (home_intel.get("time_zones_crossed") or 0)
    if tz_diff:
        parts["travel"] = _clamp(tz_diff * cfg.tz_per_zone, -cfg.travel_cap, cfg.travel_cap)

    if not neutral_site:
        elev = home_intel.get("altitude")
        if elev is not None and elev >= cfg.altitude_threshold_ft:
            parts["altitude"] = cfg.altitude_value

    return sum(parts.values()), parts


# --------------------------------------------------------------------------- #
# Rating memoization (pure fn of snapshot data → identical for identical inputs)
# --------------------------------------------------------------------------- #
_RATINGS_CACHE: dict[Any, dict[str, TeamRating]] = {}


def _ratings_cache_key(snapshot: dict, cfg: EloConfig) -> tuple:
    """A cache key over the ACTUAL rating determinants — not `snapshot_id` alone.

    `snapshot_id` is a content hash of `data` for real snapshots, but test fixtures and
    ad-hoc callers can fabricate/reuse it (e.g. a literal id shared across contexts with
    different `games`). Keying on the games/prior inputs + `cfg` makes a cache hit provably
    correct regardless, and includes `cfg` so a different config can't return a stale
    answer. The cache only decides recompute-vs-reuse; it never affects the ratings' values,
    so `hash()`-based keying does not touch determinism of output."""
    data = snapshot["data"]
    games_sig = tuple(
        (g.get("week"), g.get("home_team"), g.get("away_team"),
         g.get("home_points"), g.get("away_points"),
         bool(g.get("completed")), bool(g.get("neutral_site")))
        for g in data.get("games", [])
    )
    sp_sig = tuple(sorted((t, (r or {}).get("rating"))
                          for t, r in (data.get("sp_ratings") or {}).items()))
    rp_sig = tuple(sorted((t, (r or {}).get("overall"))
                          for t, r in (data.get("returning_production") or {}).items()))
    return (snapshot["meta"].get("snapshot_id"), cfg, games_sig, sp_sig, rp_sig)


def compute_ratings_for_snapshot(snapshot: dict, cfg: EloConfig = DEFAULT_CONFIG,
                                 ) -> dict[str, TeamRating]:
    """Ratings for a loaded snapshot bundle, memoized by its content + `cfg`. The engine's
    prediction path calls this (reads ONLY the snapshot) — never `data/ratings/`."""
    data = snapshot["data"]
    key = _ratings_cache_key(snapshot, cfg)
    cached = _RATINGS_CACHE.get(key)
    if cached is not None:
        return cached
    ratings = compute_ratings(
        data.get("games", []),
        sp_ratings=data.get("sp_ratings", {}),
        returning_production=data.get("returning_production", {}),
        cfg=cfg,
    )
    _RATINGS_CACHE[key] = ratings
    return ratings


# --------------------------------------------------------------------------- #
# The pricer
# --------------------------------------------------------------------------- #
def price(home: str, away: str, *, ratings: dict[str, TeamRating],
          season_games: list[dict], venues: dict[str, dict],
          sp_ratings: dict[str, dict] | None = None,
          returning_production: dict[str, dict] | None = None,
          week: int | None = None, game_date: Any = None,
          neutral_site: bool = False, venue: str | None = None,
          cfg: EloConfig = DEFAULT_CONFIG,
          sched_cfg: ScheduleAdjustmentConfig = DEFAULT_SCHEDULE_CONFIG) -> PricedMatchup:
    """Price `away @ home` → a `PricedMatchup`. Identical for real and hypothetical
    matchups: a team absent from `ratings` is priced from its preseason prior at
    baseline uncertainty (so any two FBS teams can be priced, even preseason)."""
    home, away = home.upper(), away.upper()
    caveats: list[str] = []

    hr = ratings.get(home) or _prior_rating(home, sp_ratings, returning_production, cfg)
    ar = ratings.get(away) or _prior_rating(away, sp_ratings, returning_production, cfg)

    uncertainty = matchup_uncertainty(hr, ar, cfg)
    w = rating_signal_weight(uncertainty, cfg)

    # Separate the rating differential (capped early season, D11) from home-field, which
    # is STRUCTURAL — like the schedule factors it is not damped by rating uncertainty.
    hfa_points = 0.0 if neutral_site else cfg.hfa_elo / cfg.elo_per_point
    rating_diff_points = (hr.rating - ar.rating) / cfg.elo_per_point
    rating_component = rating_diff_points * w

    # Schedule intel for both participants at the game location (identical helper the
    # snapshot builder uses). Non-neutral → the game is at home's venue; neutral → the
    # named venue if resolvable, else unknown (travel/altitude simply not modeled).
    game_venue = None
    if neutral_site:
        game_venue = venues.get((venue or "").upper()) if venue else None
    else:
        game_venue = venues.get((venue or home).upper())
    ratings_for_intel = sp_ratings or {}
    home_intel = compute_schedule_intel(home, away, week or 1, game_date, not neutral_site,
                                        game_venue, season_games, venues, ratings_for_intel)
    away_intel = compute_schedule_intel(away, home, week or 1, game_date, False,
                                        game_venue, season_games, venues, ratings_for_intel)
    schedule_component, schedule_parts = schedule_adjustment(
        home_intel, away_intel, neutral_site, sched_cfg)

    # D15 decomposition: base (team quality) + schedule_adjustment = total.
    base_margin = rating_component + hfa_points
    base_spread = -base_margin
    home_margin = base_margin + schedule_component  # total margin
    model_spread = -home_margin  # total spread; home favored → negative (Vegas convention)

    # Caveats — the honest state, surfaced for the CLI/engine.
    if hr.prior_source == "flat" or ar.prior_source == "flat":
        caveats.append("No preseason prior for one/both teams (SP+ & returning production "
                       "unposted) — rating starts at baseline.")
    if week is not None and week <= cfg.early_season_weeks:
        caveats.append(f"Early season (week {week} ≤ {cfg.early_season_weeks}): ratings "
                       f"unsettled (uncertainty {uncertainty:.2f}); rating signal capped "
                       f"at {w:.0%}. Treat as low confidence.")
    elif uncertainty > 0.5:
        caveats.append(f"High rating uncertainty ({uncertainty:.2f}); rating signal capped "
                       f"at {w:.0%}.")
    if not neutral_site and game_venue is None:
        caveats.append("Home venue coordinates missing — travel/altitude not modeled.")
    if neutral_site and venue and game_venue is None:
        caveats.append(f"Neutral venue '{venue}' not resolved — travel/altitude not modeled.")

    return PricedMatchup(
        home_team=home, away_team=away,
        model_spread=model_spread, home_margin=home_margin,
        rating_component=rating_component, schedule_component=schedule_component,
        base_margin=base_margin, base_spread=base_spread,
        rating_uncertainty=uncertainty, neutral_site=neutral_site,
        home_rating=hr.rating, away_rating=ar.rating,
        home_prior_source=hr.prior_source, away_prior_source=ar.prior_source,
        rating_signal_weight=w,
        breakdown={
            "rating_margin_raw": round(rating_diff_points, 2),
            "rating_signal_weight": round(w, 3),
            "rating_component": round(rating_component, 2),
            "hfa_points": round(hfa_points, 2),
            "schedule": {k: round(v, 2) for k, v in schedule_parts.items()},
            "schedule_component": round(schedule_component, 2),
            "home_intel": home_intel,
            "away_intel": away_intel,
        },
        caveats=caveats,
    )


def build_ratings_export(snapshot: dict, cfg: EloConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """Derived per-week ratings artifact (D13) for `data/ratings/YYYY_week_NN.json`.

    Per team: rating, `rating_uncertainty`, `games_played`, prior source + seed. Embeds
    the `snapshot_id` it derives from and the `EloConfig` used, so the export is auditable
    and byte-reproducible (`generated_at` is frozen from the snapshot's build time, not the
    wall clock). This is inspection/projection data — NOT read on the prediction path."""
    from dataclasses import asdict

    ratings = compute_ratings_for_snapshot(snapshot, cfg)
    meta = snapshot["meta"]
    return {
        "meta": {
            "snapshot_id": meta.get("snapshot_id"),
            "week": meta.get("week"),
            "year": meta.get("year"),
            "generated_at": meta.get("built_at"),
            "engine": "power_ratings",
            "elo_config": asdict(cfg),
        },
        "ratings": {
            t: {
                "rating": round(r.rating, 4),
                "rating_uncertainty": round(r.uncertainty(cfg), 4),
                "games_played": r.games_played,
                "prior_source": r.prior_source,
                "prior_elo": round(r.prior_elo, 4),
            }
            for t, r in sorted(ratings.items())
        },
    }


def _prior_rating(team: str, sp_ratings: dict | None, returning_production: dict | None,
                  cfg: EloConfig) -> TeamRating:
    """A never-seen team's rating = its preseason prior at 0 games (max uncertainty).
    Lets the pricer price ANY two FBS teams, including preseason hypotheticals."""
    p: PriorResult = preseason_prior(team, sp_ratings, returning_production, cfg)
    return TeamRating(team=team, rating=p.elo, games_played=0,
                      prior_elo=p.elo, prior_source=p.source)
