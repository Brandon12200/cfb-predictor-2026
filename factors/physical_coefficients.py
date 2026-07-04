"""Calibrated physical / schedule-intelligence coefficients — the SINGLE source of truth (D15).

These per-sub-signal point values are consumed by BOTH the matchup pricer's schedule adjustment
(model spread, `engine/matchup_pricer.py`) AND the Phase-3 physical factors (contrarian layer,
`factors/scheduling_fatigue.py`) — no parallel copy; both lanes freeze together at `v2026-frozen`.

Each function takes the two teams' `compute_schedule_intel` outputs and returns POINTS from the
HOME perspective (positive favors home). Missing inputs contribute nothing (recorded absent,
never fabricated).

**Model-spread scope (D15):** `physical_adjustments()` — what the pricer consumes — is the
**fatigue/location** subset (bye, short-week, travel/tz, altitude): pure "how good is this team in
this game" physical effects worth pricing, and behavior-preserving vs the 2a `ScheduleAdjustmentConfig`.
`consecutive_road` and `sandwich` are **contrarian-only** physical factors (cumulative wear /
motivational letdown — not team-quality pricing), so they do NOT feed the model spread; recorded
in `docs/DECISIONS.md` for ratification.

**Calibration status (D17):** PROPOSED, evidence-class **`reasoned`** — magnitudes argued from
rest/travel effects and the priced ~2.5-pt home-field scale (each bounded well under it), NOT from
2025 performance. Ratified in `docs/CALIBRATION_LOG.md` before the freeze.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalCoefficients:
    """Physical point values (home perspective). Owner-ratified calibration; frozen at the tag."""

    bye_value: float = 1.0               # prep advantage off a bye (opponent didn't have one)
    short_week_penalty: float = 1.0      # < 7 days' rest and the opponent isn't
    tz_per_zone: float = 0.6             # per net time-zone the AWAY team crosses more
    travel_cap: float = 1.5              # cap on the travel/timezone term (0.6 HFA — humility on
    #                                      an unmeasured extreme; revisit with 2026 attribution)
    altitude_threshold_ft: float = 4000.0  # home acclimated at a high-elevation stadium
    altitude_value: float = 1.2
    consecutive_road_value: float = 0.5  # wear per road game beyond the 2nd consecutive (NEW)
    consecutive_road_cap: float = 1.5
    sandwich_value: float = 1.0          # letdown when a ranked opponent sits in an adjacent week (NEW)


DEFAULT_PHYSICAL_COEFFICIENTS = PhysicalCoefficients()


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# --- per-sub-signal point functions (home perspective; + favors home) --------
def bye_points(home_intel: dict, away_intel: dict,
               cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS) -> float:
    hb, ab = bool(home_intel.get("bye")), bool(away_intel.get("bye"))
    if hb and not ab:
        return cfg.bye_value
    if ab and not hb:
        return -cfg.bye_value
    return 0.0


def short_week_points(home_intel: dict, away_intel: dict,
                      cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS) -> float:
    hs, as_ = bool(home_intel.get("short_week")), bool(away_intel.get("short_week"))
    if hs and not as_:
        return -cfg.short_week_penalty
    if as_ and not hs:
        return cfg.short_week_penalty
    return 0.0


def travel_points(home_intel: dict, away_intel: dict,
                  cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS) -> float:
    tz_diff = (away_intel.get("time_zones_crossed") or 0) - (home_intel.get("time_zones_crossed") or 0)
    if not tz_diff:
        return 0.0
    return _clamp(tz_diff * cfg.tz_per_zone, -cfg.travel_cap, cfg.travel_cap)


def altitude_points(home_intel: dict, neutral_site: bool,
                    cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS) -> float:
    if neutral_site:
        return 0.0
    elev = home_intel.get("altitude")
    if elev is not None and elev >= cfg.altitude_threshold_ft:
        return cfg.altitude_value
    return 0.0


def consecutive_road_points(home_intel: dict, away_intel: dict,
                            cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS) -> float:
    """Cumulative road wear — a team on a long road stretch is worn; the fresher side is favored.
    No wear for the first road game; grows for the 2nd+ consecutive, capped. Contrarian-only."""
    def wear(n: int | None) -> float:
        return _clamp(max(0, (n or 0) - 1) * cfg.consecutive_road_value, 0.0, cfg.consecutive_road_cap)
    return wear(away_intel.get("consecutive_road_games")) - wear(home_intel.get("consecutive_road_games"))


def sandwich_points(home_intel: dict, away_intel: dict,
                    cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS) -> float:
    """A team in a sandwich/look-ahead spot (ranked opponent adjacent) may underperform → favors
    the opponent. `sandwich_spot` is None when adjacent strength is unknown → no signal.
    Contrarian-only (motivational, not team-quality pricing)."""
    val = 0.0
    if home_intel.get("sandwich_spot"):
        val -= cfg.sandwich_value
    if away_intel.get("sandwich_spot"):
        val += cfg.sandwich_value
    return val


def physical_adjustments(home_intel: dict, away_intel: dict, neutral_site: bool,
                         cfg: PhysicalCoefficients = DEFAULT_PHYSICAL_COEFFICIENTS,
                         ) -> tuple[float, dict[str, float]]:
    """The MODEL-SPREAD physical adjustment (D15): the fatigue/location subset the pricer consumes
    (bye, short-week, travel/tz, altitude). Behavior-identical to the retired 2a `schedule_adjustment`.
    `consecutive_road`/`sandwich` are deliberately excluded here (contrarian-only)."""
    parts: dict[str, float] = {}
    for name, value in (
        ("bye", bye_points(home_intel, away_intel, cfg)),
        ("short_week", short_week_points(home_intel, away_intel, cfg)),
        ("travel", travel_points(home_intel, away_intel, cfg)),
        ("altitude", altitude_points(home_intel, neutral_site, cfg)),
    ):
        if value != 0.0:
            parts[name] = value
    return sum(parts.values()), parts
