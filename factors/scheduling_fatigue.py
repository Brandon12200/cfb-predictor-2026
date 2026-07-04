"""Physical factor layer (Phase 3b, SPEC §7.2 / L1) — schedule-intelligence-driven.

Replaces the pre-1c `SchedulingFatigueCalculator` (which home-brewed fatigue from raw `games`)
with **one PRIMARY factor per physical sub-signal**, each reading the `home_intel`/`away_intel`
tables that `data_manager.get_game_context` computes (via `data.schedule_intel`) and returning
its point value from the **single calibrated coefficient source** (`factors.physical_coefficients`,
D15 — the same values the matchup pricer's model-spread schedule adjustment consumes). Each factor
appears separately in `factor_breakdown` and is individually attributable in Phase 4.

Per D17, physical factors are the reliable signals (L1) but the coefficients rest on documented
reasoning, not 2025 performance; weights are ratified in `docs/CALIBRATION_LOG.md` before the freeze.
Point values here are POINTS from the home perspective (+ favors home). Missing intel → 0 (honest
absence, never fabricated).
"""

from typing import Any

from factors.base_calculator import BaseFactorCalculator, FactorConfidence, FactorType
from factors.physical_coefficients import (
    altitude_points,
    bye_points,
    consecutive_road_points,
    sandwich_points,
    short_week_points,
    travel_points,
)

# Physical factors mandate no context field (they degrade to 0 on missing intel), so
# `can_calculate` always passes and the factor itself records the honest absence.
_NO_REQUIRED_DATA = {"team_info": False, "coaching_data": False, "team_stats": False,
                     "schedule_data": False, "betting_data": False, "historical_data": False}


class _PhysicalFactorMixin:
    """Shared behaviour for physical sub-signal factors. NOT a `BaseFactorCalculator` subclass, so
    the registry's dynamic loader skips it; the concrete factors inherit `(mixin, BaseFactorCalculator)`."""

    sub_signal: str = ""  # concrete subclass sets

    def _points(self, home_intel: dict, away_intel: dict, neutral_site: bool) -> float:
        raise NotImplementedError

    def calculate(self, home_team: str, away_team: str,
                  context: dict[str, Any] | None = None) -> float:
        if not context:
            return 0.0
        home_intel = context.get("home_intel") or {}
        away_intel = context.get("away_intel") or {}
        neutral = bool(context.get("neutral_site"))
        return self.validate_output(self._points(home_intel, away_intel, neutral))  # type: ignore[attr-defined]

    def calculate_with_confidence(self, home_team: str, away_team: str,
                                  context: dict[str, Any] | None = None,
                                  ) -> tuple[float, FactorConfidence, list[str]]:
        value = self.calculate(home_team, away_team, context)
        if abs(value) < 1e-9:
            return value, FactorConfidence.NONE, [f"No {self.sub_signal} signal"]
        # A fired physical signal is a near-certain structural fact (L1: physical > motivational).
        strong = abs(value) >= self.max_impact * 0.6  # type: ignore[attr-defined]
        conf = FactorConfidence.VERY_HIGH if strong else FactorConfidence.HIGH
        return value, conf, [f"{self.sub_signal}: {value:+.1f} pts (physical/structural)"]

    def get_output_range(self) -> tuple[float, float]:
        return (self._min_output, self._max_output)  # type: ignore[attr-defined]

    def get_required_data(self) -> dict[str, bool]:
        return dict(_NO_REQUIRED_DATA)


def _configure(factor: BaseFactorCalculator, weight: float, threshold: float, cap: float,
               description: str) -> None:
    factor.category = "physical"
    factor.factor_type = FactorType.PRIMARY
    factor.weight = weight
    factor.activation_threshold = threshold
    factor.max_impact = cap
    factor._min_output = -cap
    factor._max_output = cap
    factor.description = description


# Weights ratified in the 3b calibration batch (docs/CALIBRATION_LOG.md, owner 2026-07-03) — the L1
# reweight to physical (52% additive share). Thresholds are low — physical signals are reliable.
class ByeAdvantageCalculator(_PhysicalFactorMixin, BaseFactorCalculator):
    sub_signal = "bye"

    def __init__(self):
        super().__init__()
        _configure(self, weight=0.16, threshold=0.4, cap=1.5, description="Bye-week prep advantage")

    def _points(self, home_intel, away_intel, neutral_site):
        return bye_points(home_intel, away_intel)


class ShortWeekCalculator(_PhysicalFactorMixin, BaseFactorCalculator):
    sub_signal = "short_week"

    def __init__(self):
        super().__init__()
        _configure(self, weight=0.14, threshold=0.4, cap=1.5, description="Short-week rest penalty")

    def _points(self, home_intel, away_intel, neutral_site):
        return short_week_points(home_intel, away_intel)


class TravelBurdenCalculator(_PhysicalFactorMixin, BaseFactorCalculator):
    sub_signal = "travel"

    def __init__(self):
        super().__init__()
        _configure(self, weight=0.16, threshold=0.4, cap=1.5, description="Travel / time-zone burden")

    def _points(self, home_intel, away_intel, neutral_site):
        return travel_points(home_intel, away_intel)


class AltitudeCalculator(_PhysicalFactorMixin, BaseFactorCalculator):
    sub_signal = "altitude"

    def __init__(self):
        super().__init__()
        _configure(self, weight=0.12, threshold=0.4, cap=1.5, description="High-altitude home acclimation")

    def _points(self, home_intel, away_intel, neutral_site):
        return altitude_points(home_intel, neutral_site)


class ConsecutiveRoadCalculator(_PhysicalFactorMixin, BaseFactorCalculator):
    sub_signal = "consecutive_road"

    def __init__(self):
        super().__init__()
        _configure(self, weight=0.10, threshold=0.4, cap=1.5, description="Consecutive-road-games wear")

    def _points(self, home_intel, away_intel, neutral_site):
        return consecutive_road_points(home_intel, away_intel)


class SandwichCalculator(_PhysicalFactorMixin, BaseFactorCalculator):
    sub_signal = "sandwich"

    def __init__(self):
        super().__init__()
        _configure(self, weight=0.12, threshold=0.4, cap=1.5,
                   description="Sandwich / look-ahead spot (ranked adjacent opponent)")

    def _points(self, home_intel, away_intel, neutral_site):
        return sandwich_points(home_intel, away_intel)
